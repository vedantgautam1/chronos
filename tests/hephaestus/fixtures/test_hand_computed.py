"""Phase 5 — the hand-computed accounting fixtures (spec §7).

Every expected number below was derived BY HAND, longhand, in the
comments. The quant's job is to re-do the arithmetic on paper and check
the derivations, not just trust the asserts. All assertions are EXACT
Decimal equality — "close enough" is not accepted on the ledger.

Cost parameters used throughout:
    taker fee     10 bps  (0.10%)  of executed notional  (CostConfig default)
    slippage      10 bps  of base price, adverse direction  (PINNED in
                  fixture 3's CostConfig — decoupled from R6's actual
                  default, which is a measured value that changes
                  independently; see HANDOFF.md 2026-07-17)
    half-spread    1 bp   of base price, adverse direction  (CostConfig default)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from chronos.hephaestus.broker import Broker, BrokerConfig
from chronos.hephaestus.costs import CostConfig, FixedBpsCostModel
from chronos.hephaestus.portfolio import (
    AccountingDriftError,
    AccountingError,
    Portfolio,
    returns_from_equity,
)
from chronos.hephaestus.types import Fill, Order, OrderType, Side

import pandas as pd

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def buy_fill(qty: str, price: str, fee: str, slip: str = "0", spread: str = "0") -> Fill:
    return Fill(order_id=1, symbol="BTC/USDT", side=Side.BUY,
                qty_filled=Decimal(qty), price=Decimal(price), fee=Decimal(fee),
                slippage_cost=Decimal(slip), spread_cost=Decimal(spread), bar_time=T0)


def sell_fill(qty: str, price: str, fee: str, slip: str = "0", spread: str = "0") -> Fill:
    return Fill(order_id=2, symbol="BTC/USDT", side=Side.SELL,
                qty_filled=Decimal(qty), price=Decimal(price), fee=Decimal(fee),
                slippage_cost=Decimal(slip), spread_cost=Decimal(spread), bar_time=T0)


def test_fixture_1_single_buy_hold_mark_over_three_bars():
    """FIXTURE 1 — buy 2 units, hold, mark at three closes.

    HAND DERIVATION
    ---------------
    Start: cash = 10,000.00

    The fill (as the broker would price it from a bar opening at 100):
        base price            = 100
        slippage  = 100 × 0.0010 = 0.10  per unit   (10 bps, adverse: up)
        half-spread = 100 × 0.0001 = 0.01 per unit  ( 1 bp,  adverse: up)
        exec price = 100 + 0.10 + 0.01  = 100.11
        notional   = 2 × 100.11         = 200.22
        fee        = 200.22 × 0.0010    = 0.20022

    After the buy:
        cash  = 10,000 − 200.22 − 0.20022 = 9,799.57978
        qty   = 2,  basis = 200.22

    Marks:
        close = 105:  equity = 9,799.57978 + 2×105 = 10,009.57978
                      (identity: unrealized = 210 − 200.22 = 9.78;
                       10,000 + 0 + 9.78 − 0.20022 = 10,009.57978 ✓)
        close =  95:  equity = 9,799.57978 + 190  =  9,989.57978
        close = 110:  equity = 9,799.57978 + 220  = 10,019.57978
    """
    p = Portfolio(Decimal("10000"))
    p.apply_fill(buy_fill("2", "100.11", "0.20022", slip="0.20", spread="0.02"))

    assert p.cash == Decimal("9799.57978")
    assert p.position_qty("BTC/USDT") == Decimal("2")

    closes = [("105", "10009.57978"), ("95", "9989.57978"), ("110", "10019.57978")]
    for i, (close, expected_equity) in enumerate(closes):
        equity = p.mark_to_market({"BTC/USDT": Decimal(close)}, at=T0 + timedelta(hours=i))
        assert equity == Decimal(expected_equity), f"at close {close}"


def test_fixture_2_round_trip_with_fees_and_slippage():
    """FIXTURE 2 — buy 2, sell 2, full costs; exact realized PnL.

    HAND DERIVATION
    ---------------
    Buy exactly as fixture 1:
        exec 100.11, notional 200.22, fee 0.20022
        cash after buy = 9,799.57978 ; basis = 200.22

    The sell (bar opens at 120):
        slippage  = 120 × 0.0010 = 0.12 per unit    (adverse: DOWN)
        half-spread = 120 × 0.0001 = 0.012 per unit (adverse: DOWN)
        exec price = 120 − 0.12 − 0.012 = 119.868
        notional   = 2 × 119.868       = 239.736
        fee        = 239.736 × 0.0010  = 0.239736

    Realized PnL = proceeds-at-exec − basis = 239.736 − 200.22 = 39.516
    Cash  = 9,799.57978 + 239.736 − 0.239736 = 10,039.076044
    Flat position -> equity = cash = 10,039.076044

    Identity: 10,000 + 39.516 + 0 − (0.20022 + 0.239736) = 10,039.076044 ✓

    Itemized cost totals:
        fees     = 0.20022 + 0.239736      = 0.439956
        slippage = 2×0.10 + 2×0.12         = 0.44
        spread   = 2×0.01 + 2×0.012        = 0.044
    """
    p = Portfolio(Decimal("10000"))
    p.apply_fill(buy_fill("2", "100.11", "0.20022", slip="0.20", spread="0.02"))
    p.apply_fill(sell_fill("2", "119.868", "0.239736", slip="0.24", spread="0.024"))

    assert p.realized_pnl == Decimal("39.516")
    assert p.cash == Decimal("10039.076044")
    assert p.position_qty("BTC/USDT") == Decimal("0")
    assert p.fees_paid == Decimal("0.439956")
    assert p.slippage_paid == Decimal("0.44")
    assert p.spread_paid == Decimal("0.044")

    equity = p.mark_to_market({"BTC/USDT": Decimal("999")}, at=T0)  # price irrelevant: flat
    assert equity == Decimal("10039.076044")


def test_fixture_3_partial_fill_through_the_real_broker():
    """FIXTURE 3 — a too-big order, capped by participation; exact
    position and remainder accounting THROUGH the broker.

    HAND DERIVATION
    ---------------
    Bar: open=100, volume=10. Cap = 5% × 10 = 0.5 units.
    Order: MARKET BUY 2.0  ->  fills 0.5, remainder 1.5 cancelled.

        exec price = 100 + 0.10 + 0.01 = 100.11   (same per-unit costs)
        notional   = 0.5 × 100.11      = 50.055
        fee        = 50.055 × 0.0010   = 0.050055
        cash  = 10,000 − 50.055 − 0.050055 = 9,949.894945
        qty   = 0.5 ; basis = 50.055

    Mark at close 105:
        equity = 9,949.894945 + 0.5×105 = 10,002.394945
        (identity: unrealized = 52.5 − 50.055 = 2.445;
         10,000 + 0 + 2.445 − 0.050055 = 10,002.394945 ✓)
    """
    portfolio = Portfolio(Decimal("10000"))
    # slippage pinned to 10 bps (see module docstring) — decoupled from
    # CostConfig's default, which is R6's current best-guess and changes
    # independently of this hand-derived fixture (HANDOFF.md 2026-07-17).
    broker = Broker(FixedBpsCostModel(CostConfig(slippage_bps=Decimal("10"))),
                    portfolio, BrokerConfig())
    bar = pd.Series({"open_time": pd.Timestamp(T0), "open": 100.0, "high": 110.0,
                     "low": 90.0, "close": 105.0, "volume": 10.0, "is_final": True})
    order = Order(id=1, symbol="BTC/USDT", side=Side.BUY, type=OrderType.MARKET,
                  qty=Decimal("2.0"), created_at=T0)

    fills, events = broker.process([order], {"BTC/USDT": bar})
    for f in fills:
        portfolio.apply_fill(f)

    assert fills[0].qty_filled == Decimal("0.5")
    assert fills[0].price == Decimal("100.11")
    assert events[0].qty == Decimal("1.5")  # the recorded cancelled remainder
    assert portfolio.cash == Decimal("9949.894945")
    assert portfolio.position_qty("BTC/USDT") == Decimal("0.5")

    equity = portfolio.mark_to_market({"BTC/USDT": Decimal("105")}, at=T0)
    assert equity == Decimal("10002.394945")


def test_partial_sale_apportions_basis_and_identity_still_exact():
    """Sell HALF the holding: basis apportions pro-rata, identity exact.

    Buy 2 @ 100 flat (fee 0): cash 9,800, basis 200.
    Sell 1 @ 110 (fee 0): sold_basis = 200 × 1/2 = 100
        realized = 110 − 100 = 10 ; cash = 9,910 ; qty 1, basis 100.
    Mark at 120: equity = 9,910 + 120 = 10,030
        identity: 10,000 + 10 + (120−100) − 0 = 10,030 ✓
    """
    p = Portfolio(Decimal("10000"))
    p.apply_fill(buy_fill("2", "100", "0"))
    p.apply_fill(sell_fill("1", "110", "0"))
    assert p.realized_pnl == Decimal("10")
    assert p.cash == Decimal("9910")
    assert p.mark_to_market({"BTC/USDT": Decimal("120")}, at=T0) == Decimal("10030")


def test_oversell_cannot_reach_the_ledger():
    p = Portfolio(Decimal("10000"))
    p.apply_fill(buy_fill("1", "100", "0"))
    with pytest.raises(AccountingError, match="oversell"):
        p.apply_fill(sell_fill("2", "100", "0"))


def test_identity_violation_is_caught_not_logged():
    p = Portfolio(Decimal("10000"))
    p.apply_fill(buy_fill("1", "100", "0"))
    p._cash += Decimal("5")  # simulate a ledger bug: cash appears from nowhere
    with pytest.raises(AccountingDriftError, match="reconciliation failed"):
        p.mark_to_market({"BTC/USDT": Decimal("100")}, at=T0)


def test_returns_derived_once_and_hand_checked():
    """equity [100, 110, 99] -> returns [0, +10%, −10%]."""
    equity = pd.Series([100.0, 110.0, 99.0])
    returns = returns_from_equity(equity)
    assert list(returns) == [0.0, pytest.approx(0.10), pytest.approx(-0.10)]
