"""test_capacity.py — stage 4.6, capacity (spec §4.6). Protected.

Covers: remainder-notional extraction on a hand-built REMAINDER_CANCELLED fixture
(including the unpriced limit-remainder case); the 10× degradation-gate boundary; the
100× run recorded but never gating; and Decimal cash scaling (base × 10, base × 100,
in Decimal — never float).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pytest

from chronos.hephaestus.types import OrderEvent, OrderEventKind
from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.rerun import Rerun
from chronos.moirai.stages import capacity as capacity_mod
from chronos.moirai.stages.capacity import Capacity, remainder_notional_fraction
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result, make_fill

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _returns_with_sr(target_sr, n=64):
    rng = np.random.default_rng(abs(int(target_sr * 1e6)) + n)
    x = rng.standard_normal(n)
    x = (x - x.mean()) / x.std(ddof=1)
    return list(x * 1e-3 + target_sr * 1e-3)


def _res(target_sr):
    return build_result(returns_values=_returns_with_sr(target_sr))


def _candidate(cash="10000"):
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=START,
                    end=START + timedelta(hours=64), strategy_params={},
                    initial_cash=Decimal(cash))
    return Candidate(strategy=ToyMomentum(), base_config=cfg,
                     hypothesis=Hypothesis(id="H-cap", statement="x", prediction="y"))


def _ctx(tmp_path, candidate, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, build_config(("M4.6-capacity",)),
                             gauntlet_seed=seed, candidate=candidate)
    return store, ctx


# --- remainder-notional extraction (pure) --------------------------------------

def test_remainder_fraction_from_fixture():
    """Order 1 fills 0.5 @ 100 (notional 50) and cancels a 0.5 remainder (same order,
    same price) → cancelled 50, total 100 → fraction 0.5."""
    t = START
    fills = (make_fill(1, "BUY", "0.5", "100", t),)
    events = (OrderEvent(OrderEventKind.REMAINDER_CANCELLED, 1, t,
                         "participation cap", Decimal("0.5")),)
    frac, detail = remainder_notional_fraction(fills, events)
    assert frac == pytest.approx(0.5)
    assert detail["cancelled_notional"] == "50.0"
    assert detail["total_intended_notional"] == "100.0"
    assert detail["unpriced_remainders"] == 0


def test_remainder_fraction_ignores_non_remainder_and_unpriced():
    t = START
    fills = (make_fill(1, "BUY", "1", "100", t),)  # full fill, no remainder
    events = (
        OrderEvent(OrderEventKind.REJECTED, 2, t, "no cash", Decimal("1")),  # not a remainder
        OrderEvent(OrderEventKind.REMAINDER_CANCELLED, 9, t,
                   "limit not traded through", Decimal("0.3")),  # no matching fill → unpriced
    )
    frac, detail = remainder_notional_fraction(fills, events)
    assert frac == pytest.approx(0.0)     # nothing priced-and-cancelled
    assert detail["unpriced_remainders"] == 1


def test_remainder_fraction_zero_when_no_trades():
    frac, detail = remainder_notional_fraction((), ())
    assert frac == 0.0
    assert detail["total_intended_notional"] == "0"


# --- degradation gate + Decimal scaling (rerun monkeypatched) ------------------

def _fake_rerun(by_scale, base_cash=Decimal("10000"), captured=None):
    def fake(ctx, config, **kw):
        if captured is not None:
            captured.append(config)
        scale = int(config.initial_cash / base_cash)
        return Rerun(result=by_scale[scale], wall_clock_s=0.001)
    return fake


def test_degradation_boundary(tmp_path, monkeypatch):
    """base Sharpe 0.10, max_degradation_frac 0.3 → floor 0.07. 10× at 0.08 passes;
    at 0.06 fails."""
    base = _res(0.10)
    # pass side
    _, ctx = _ctx(tmp_path, _candidate())
    monkeypatch.setattr(capacity_mod, "rerun_candidate",
                        _fake_rerun({10: _res(0.08), 100: _res(0.01)}))
    ok = Capacity().evaluate(base, ctx)
    assert ok.passed and ok.evidence["degradation_ok"] is True

    # fail side
    _, ctx2 = _ctx(tmp_path / "b", _candidate())
    monkeypatch.setattr(capacity_mod, "rerun_candidate",
                        _fake_rerun({10: _res(0.06), 100: _res(0.01)}))
    bad = Capacity().evaluate(base, ctx2)
    assert not bad.passed
    assert "sharpe_degradation" in bad.evidence["capacity_gate_fail_detail"]


def test_100x_recorded_but_never_gates(tmp_path, monkeypatch):
    """A catastrophic 100× Sharpe does not fail the gate (gate is the 10× run)."""
    base = _res(0.10)
    _, ctx = _ctx(tmp_path, _candidate())
    monkeypatch.setattr(capacity_mod, "rerun_candidate",
                        _fake_rerun({10: _res(0.09), 100: _res(-5.0)}))
    outcome = Capacity().evaluate(base, ctx)
    assert outcome.passed                      # 100× degradation is reporting-only
    assert "100" in outcome.evidence["runs"]   # but it IS recorded
    assert 100 in outcome.evidence["reporting_only_scales"]
    assert 10 not in outcome.evidence["reporting_only_scales"]


def test_decimal_cash_scaling(tmp_path, monkeypatch):
    base = _res(0.10)
    captured: list = []
    _, ctx = _ctx(tmp_path, _candidate(cash="10000"))
    monkeypatch.setattr(capacity_mod, "rerun_candidate",
                        _fake_rerun({10: _res(0.09), 100: _res(0.08)}, captured=captured))
    Capacity().evaluate(base, ctx)
    cashes = [c.initial_cash for c in captured]
    assert cashes == [Decimal("100000"), Decimal("1000000")]  # base×10, base×100
    assert all(isinstance(c, Decimal) for c in cashes)         # Decimal, never float


def test_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, None)
    with pytest.raises(ValueError, match="ctx.candidate"):
        Capacity().evaluate(_res(0.10), ctx)
