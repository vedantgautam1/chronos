"""Phase 4 tests: cost math against hand-computed values, and the
no-bypass guarantee (I2).

Hand derivations (the quant should re-do these on paper):
  taker 10 bps, half-spread 1 bp, slippage 10 bps — taker/half-spread are
  CostConfig's actual defaults; slippage is explicitly PINNED to 10 bps
  in these fixtures via CostConfig(slippage_bps=Decimal("10")), not read
  from the default. This decouples the cost-model arithmetic (what these
  tests verify) from R6's current best-guess slippage value (a
  measurement that will keep changing — see HANDOFF.md 2026-07-17): the
  fixture's hand-derived numbers below stay correct regardless of what
  the default becomes.
  Bar open = 100. BUY market order, qty 0.5, volume 10.

  slippage/unit = 100 × 10/10000              = 0.10
  half-spread/unit = 100 × 1/10000            = 0.01
  exec price   = 100 + 0.10 + 0.01            = 100.11   (buy pays MORE)
  notional     = 0.5 × 100.11                 = 50.055
  fee          = 50.055 × 10/10000            = 0.050055
  slippage_cost = 0.10 × 0.5                  = 0.05
  spread_cost   = 0.01 × 0.5                  = 0.005
  All exact Decimals — no tolerance, no rounding.
"""

import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from chronos.hephaestus.broker import Broker, BrokerConfig
from chronos.hephaestus.costs import (
    ZERO_COSTS,
    CostConfig,
    FixedBpsCostModel,
    PROVISIONAL_WARNING,
)
from chronos.hephaestus.types import Side

from .scaffolding import StubPortfolio
from .test_broker import bar, limit, market

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_fee_hand_computed():
    model = FixedBpsCostModel()  # taker 10 bps
    assert model.fee(Side.BUY, Decimal("10000")) == Decimal("10")  # 10k × 0.001
    assert model.fee(Side.SELL, Decimal("50.055")) == Decimal("0.050055")


def test_slippage_and_spread_hand_computed():
    model = FixedBpsCostModel(CostConfig(slippage_bps=Decimal("10")))
    assert model.slippage(market("0.5"), bar(), Decimal("0.05")) == Decimal("0.1")
    assert model.spread(bar()) == Decimal("0.01")
    # A limit order's slippage references its limit price, not the open.
    assert model.slippage(limit("0.1", "90"), bar(), Decimal("0.01")) == Decimal("0.09")


def test_full_fill_is_costed_exactly_as_derived():
    broker = Broker(FixedBpsCostModel(CostConfig(slippage_bps=Decimal("10"))),
                    StubPortfolio(Decimal("10000")), BrokerConfig())
    fills, _ = broker.process([market("0.5")], {"BTC/USDT": bar()})
    f = fills[0]
    assert f.price == Decimal("100.11")  # 100 + 0.10 slippage + 0.01 half-spread
    assert f.fee == Decimal("0.050055")
    assert f.slippage_cost == Decimal("0.05")
    assert f.spread_cost == Decimal("0.005")


def test_sell_side_costs_are_adverse_downward():
    broker = Broker(FixedBpsCostModel(CostConfig(slippage_bps=Decimal("10"))),
                    StubPortfolio(Decimal("0")), BrokerConfig())
    broker._portfolio.qty["BTC/USDT"] = Decimal("1")
    fills, _ = broker.process([market("0.5", side=Side.SELL)], {"BTC/USDT": bar()})
    assert fills[0].price == Decimal("99.89")  # 100 − 0.10 − 0.01: seller receives LESS


def test_zero_vs_real_costs_visibly_differ():
    def run_with(config):
        broker = Broker(FixedBpsCostModel(config), StubPortfolio(Decimal("10000")), BrokerConfig())
        fills, _ = broker.process([market("0.5")], {"BTC/USDT": bar()})
        return fills[0]

    free = run_with(ZERO_COSTS)
    real = run_with(CostConfig())
    assert free.price == Decimal("100") and free.fee == 0
    assert real.price > free.price and real.fee > 0  # friction exists (I2)


def test_provisional_warning_reaches_the_broker():
    broker = Broker(FixedBpsCostModel(), StubPortfolio(Decimal("100")), BrokerConfig())
    assert any("provisional_cost_constants" in w for w in broker.warnings)
    quiet = FixedBpsCostModel(CostConfig(provisional_constants=False))
    assert quiet.warnings == ()


def test_funding_is_spot_only():
    with pytest.raises(NotImplementedError, match="spot-only"):
        FixedBpsCostModel().funding(None, None)


def test_negative_bps_are_refused():
    with pytest.raises(ValueError, match=">= 0"):
        CostConfig(taker_fee_bps=Decimal("-1"))


def test_no_bypass_broker_cannot_fill_without_the_cost_model():
    """I2, statically: broker.py constructs Fill in exactly one place, and
    Broker has no default cost model and no skip/bypass parameter."""
    source = (Path(__file__).resolve().parents[2]
              / "src" / "chronos" / "hephaestus" / "broker.py").read_text()
    tree = ast.parse(source)

    fill_sites = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == "Fill"]
    assert len(fill_sites) == 1, "Fill must be constructed in exactly one audited place"

    init = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    cost_arg = init.args.args[1]  # (self, cost_model, ...)
    assert cost_arg.arg == "cost_model"
    n_defaults = len(init.args.defaults)
    required = len(init.args.args) - n_defaults
    assert init.args.args.index(cost_arg) < required, "cost_model must have NO default"

    assert "skip" not in source.lower().replace("skipped", "")
    assert "bypass" not in source.lower() or "no bypass" in source.lower()
