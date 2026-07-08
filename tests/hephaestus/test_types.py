"""Phase 1 tests: the engine's vocabulary validates itself."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from chronos.hephaestus.types import (
    Fill,
    Order,
    OrderIdSequence,
    OrderType,
    Side,
    to_decimal,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_order_ids_are_deterministic():
    seq = OrderIdSequence()
    assert [seq.next(), seq.next(), seq.next()] == [1, 2, 3]
    # A fresh run starts over — same run, same ids (invariant I5).
    assert OrderIdSequence().next() == 1


def test_to_decimal_is_exact_not_binary_noise():
    assert to_decimal(64123.45) == Decimal("64123.45")
    assert to_decimal(0.1) == Decimal("0.1")
    d = Decimal("7.25")
    assert to_decimal(d) is d  # already a Decimal: passes straight through


def test_valid_market_order():
    order = Order(id=1, symbol="BTC/USDT", side=Side.BUY, type=OrderType.MARKET,
                  qty=Decimal("0.5"), created_at=T0)
    assert order.limit_price is None


def test_limit_order_requires_limit_price():
    with pytest.raises(ValueError, match="limit_price"):
        Order(id=1, symbol="BTC/USDT", side=Side.BUY, type=OrderType.LIMIT,
              qty=Decimal("1"), created_at=T0)


def test_market_order_must_not_carry_limit_price():
    with pytest.raises(ValueError, match="must not"):
        Order(id=1, symbol="BTC/USDT", side=Side.BUY, type=OrderType.MARKET,
              qty=Decimal("1"), created_at=T0, limit_price=Decimal("100"))


def test_non_positive_qty_rejected():
    with pytest.raises(ValueError, match="qty"):
        Order(id=1, symbol="BTC/USDT", side=Side.SELL, type=OrderType.MARKET,
              qty=Decimal("0"), created_at=T0)


def test_naive_created_at_rejected():
    with pytest.raises(ValueError, match="naive"):
        Order(id=1, symbol="BTC/USDT", side=Side.BUY, type=OrderType.MARKET,
              qty=Decimal("1"), created_at=datetime(2026, 1, 1))


def test_fill_validates_costs_and_time():
    fill = Fill(order_id=1, symbol="BTC/USDT", side=Side.BUY,
                qty_filled=Decimal("0.5"), price=Decimal("60000"),
                fee=Decimal("30"), slippage_cost=Decimal("3"),
                spread_cost=Decimal("1.5"), bar_time=T0)
    assert fill.fee == Decimal("30")
    with pytest.raises(ValueError, match="fee"):
        Fill(order_id=1, symbol="BTC/USDT", side=Side.BUY,
             qty_filled=Decimal("0.5"), price=Decimal("60000"),
             fee=Decimal("-1"), slippage_cost=Decimal("0"),
             spread_cost=Decimal("0"), bar_time=T0)
