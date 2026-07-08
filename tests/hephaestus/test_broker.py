"""Phase 3 tests: every fill convention has a direct test.

The standing bar used everywhere: open=100, high=110, low=90, volume=10.
With the default 5% participation rate the cap is 0.5 units per bar.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest

from chronos.hephaestus.broker import Broker, BrokerConfig
from chronos.hephaestus.costs import PassthroughCostModel
from chronos.hephaestus.types import Order, OrderEventKind, OrderType, Side

from .scaffolding import StubPortfolio

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def bar(open_=100.0, high=110.0, low=90.0, close=105.0, volume=10.0) -> pd.Series:
    return pd.Series({"open_time": pd.Timestamp(T0), "open": open_, "high": high,
                      "low": low, "close": close, "volume": volume, "is_final": True})


def make_broker(cash="10000", holdings=None, config=BrokerConfig(), costs=None):
    portfolio = StubPortfolio(Decimal(cash))
    portfolio.qty.update(holdings or {})
    return Broker(costs or PassthroughCostModel(), portfolio, config)


def market(qty, side=Side.BUY, oid=1):
    return Order(id=oid, symbol="BTC/USDT", side=side, type=OrderType.MARKET,
                 qty=Decimal(qty), created_at=T0)


def limit(qty, price, side=Side.BUY, oid=1):
    return Order(id=oid, symbol="BTC/USDT", side=side, type=OrderType.LIMIT,
                 qty=Decimal(qty), created_at=T0, limit_price=Decimal(price))


def test_market_order_under_cap_fills_fully_at_open():
    fills, events = make_broker().process([market("0.3")], {"BTC/USDT": bar()})
    assert len(fills) == 1 and not events
    assert fills[0].qty_filled == Decimal("0.3")
    assert fills[0].price == Decimal("100")  # open, zero-cost passthrough


def test_order_over_cap_partially_fills_and_remainder_is_cancelled():
    # volume 10 × 5% = cap 0.5; order 2.0 -> fill 0.5, cancel 1.5.
    fills, events = make_broker().process([market("2.0")], {"BTC/USDT": bar()})
    assert fills[0].qty_filled == Decimal("0.5")
    cancels = [e for e in events if e.kind is OrderEventKind.REMAINDER_CANCELLED]
    assert len(cancels) == 1
    assert cancels[0].qty == Decimal("1.5")
    assert "participation cap" in cancels[0].reason


def test_buy_limit_fills_only_on_strict_trade_through():
    # low=90. A limit at 95 is traded through (90 < 95) -> fills AT 95.
    fills, _ = make_broker().process([limit("0.1", "95")], {"BTC/USDT": bar()})
    assert fills[0].price == Decimal("95")


def test_buy_limit_touch_is_not_a_fill():
    # low == limit == 90 exactly: conservative convention says NO fill.
    fills, events = make_broker().process([limit("0.1", "90")], {"BTC/USDT": bar()})
    assert not fills
    assert events[0].kind is OrderEventKind.REMAINDER_CANCELLED
    assert "not traded through" in events[0].reason


def test_optimistic_touch_fills_only_behind_flag_with_warning():
    config = BrokerConfig(optimistic_touch_fills=True)
    broker = make_broker(config=config)
    assert any("optimistic" in w for w in broker.warnings)  # stamped up front
    fills, _ = broker.process([limit("0.1", "90")], {"BTC/USDT": bar()})
    assert len(fills) == 1  # the touch now fills — flattering, flagged


def test_sell_limit_symmetric_trade_through():
    # high=110: sell limit 105 traded through (110 > 105) -> fills at 105;
    # sell limit exactly at high=110 does not.
    broker = make_broker(holdings={"BTC/USDT": Decimal("1")})
    fills, _ = broker.process([limit("0.1", "105", side=Side.SELL)], {"BTC/USDT": bar()})
    assert fills[0].price == Decimal("105")

    broker2 = make_broker(holdings={"BTC/USDT": Decimal("1")})
    fills2, events2 = broker2.process([limit("0.1", "110", side=Side.SELL)], {"BTC/USDT": bar()})
    assert not fills2 and events2[0].kind is OrderEventKind.REMAINDER_CANCELLED


def test_zero_volume_bar_rejects():
    fills, events = make_broker().process([market("0.1")], {"BTC/USDT": bar(volume=0.0)})
    assert not fills
    assert events[0].kind is OrderEventKind.REJECTED
    assert "zero-volume" in events[0].reason


def test_insufficient_cash_rejects_with_reason():
    fills, events = make_broker(cash="10").process([market("0.5")], {"BTC/USDT": bar()})
    assert not fills
    assert events[0].kind is OrderEventKind.REJECTED
    assert "insufficient cash" in events[0].reason


def test_earlier_buy_consumes_cash_later_buy_lacks():
    # Two 0.4-unit buys at 100 = 40 each; cash 50 affords only the first.
    orders = [market("0.4", oid=1), market("0.4", oid=2)]
    fills, events = make_broker(cash="50").process(orders, {"BTC/USDT": bar()})
    assert len(fills) == 1 and fills[0].order_id == 1
    assert events[0].kind is OrderEventKind.REJECTED and events[0].order_id == 2


def test_selling_more_than_held_rejects_no_shorting():
    broker = make_broker(holdings={"BTC/USDT": Decimal("0.2")})
    fills, events = broker.process([market("0.5", side=Side.SELL)], {"BTC/USDT": bar()})
    assert not fills
    assert "no shorting" in events[0].reason


def test_every_fill_passes_through_the_cost_model():
    class CountingCosts(PassthroughCostModel):
        def __init__(self):
            self.calls = {"fee": 0, "slippage": 0, "spread": 0}

        def fee(self, side, notional):
            self.calls["fee"] += 1
            return super().fee(side, notional)

        def slippage(self, order, bar, participation):
            self.calls["slippage"] += 1
            return super().slippage(order, bar, participation)

        def spread(self, bar):
            self.calls["spread"] += 1
            return super().spread(bar)

    costs = CountingCosts()
    make_broker(costs=costs).process([market("0.1")], {"BTC/USDT": bar()})
    assert costs.calls == {"fee": 1, "slippage": 1, "spread": 1}  # I2 path exercised
