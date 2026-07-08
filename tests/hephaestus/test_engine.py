"""Phase 2 tests: the event loop's sequencing guarantees.

The ones that matter most: an order decided on bar t cannot fill during
bar t (next-open timing), and a last-bar order expires on the record.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from chronos.hephaestus.engine import EngineConfig, _execute
from chronos.hephaestus.types import Order, OrderEventKind, OrderType, Side
from chronos.oceanus.model import Timeframe

from .scaffolding import BuyOnceStrategy, DoNothingStrategy, StubBroker, StubPortfolio
from .test_view import START, hourly_frame

CONFIG = EngineConfig(initial_cash=Decimal("10000"), seed=42)


def run(strategy, n_bars=24, config=CONFIG):
    return _execute(
        {"BTC/USDT": hourly_frame(n_bars)},
        Timeframe.H1,
        strategy,
        StubBroker(),
        StubPortfolio(config.initial_cash),
        config,
    )


def test_do_nothing_strategy_yields_flat_equity():
    out = run(DoNothingStrategy())
    assert out.bars_processed == 24
    assert not out.fills and not out.order_events
    assert (out.equity_curve == 10000.0).all()  # never traded, never charged


def test_order_created_at_t_fills_at_t_plus_1_never_before():
    out = run(BuyOnceStrategy(trigger_bars=3))
    assert len(out.fills) == 1
    fill = out.fills[0]
    # The strategy first sees 3 closed bars at the close of bar 2 (02:00
    # opens, closes 03:00). So the order is created on bar 2 and must fill
    # during bar 3 — at bar 3's open, not bar 2's anything.
    assert fill.bar_time == START + timedelta(hours=3)
    assert fill.price == Decimal("103")  # bar 3's open is 100 + 3


def test_last_bar_order_expires_on_the_record():
    # Trigger on the very last bar: there is no next bar to fill in.
    out = run(BuyOnceStrategy(trigger_bars=24), n_bars=24)
    assert not out.fills
    expiries = [e for e in out.order_events if e.kind is OrderEventKind.EXPIRED]
    assert len(expiries) == 1
    assert "final bar" in expiries[0].reason
    assert expiries[0].qty == Decimal("0.1")


def test_engine_stamps_ids_and_created_at_no_forgery():
    class ForgingStrategy:
        """Tries to lie about when its order was created and claim id 999."""

        def on_bar(self, view, ctx):
            if len(view.bars("BTC/USDT", 100)) != 5:
                return []
            return [Order(id=999, symbol="BTC/USDT", side=Side.BUY,
                          type=OrderType.MARKET, qty=Decimal("1"),
                          created_at=datetime(1999, 1, 1, tzinfo=timezone.utc))]

    out = run(ForgingStrategy())
    fill = out.fills[0]
    assert fill.order_id == 1  # engine's counter, not the forged 999
    # Decided at the close of bar 4 -> fills at bar 5's open.
    assert fill.bar_time == START + timedelta(hours=5)


def test_strategy_returning_junk_is_refused():
    class JunkStrategy:
        def on_bar(self, view, ctx):
            return ["not an order"]

    with pytest.raises(TypeError, match="expected Order"):
        run(JunkStrategy())


def test_order_for_unknown_symbol_is_refused():
    class WrongSymbolStrategy:
        def on_bar(self, view, ctx):
            return [Order(id=0, symbol="DOGE/USDT", side=Side.BUY,
                          type=OrderType.MARKET, qty=Decimal("1"), created_at=view.now)]

    with pytest.raises(ValueError, match="universe"):
        run(WrongSymbolStrategy())


def test_same_seed_same_everything():
    a = run(BuyOnceStrategy())
    b = run(BuyOnceStrategy())
    assert a.fills == b.fills
    assert a.equity_curve.equals(b.equity_curve)  # early determinism check (I5)


def test_unsafe_same_bar_fill_is_not_available():
    with pytest.raises(NotImplementedError, match="never be the default"):
        run(DoNothingStrategy(), config=EngineConfig(unsafe_same_bar_fill=True))


def test_loop_runs_end_to_end_on_oceanus_served_data(tmp_path):
    # Through the real one door: get_bars() backed by the fake exchange.
    from chronos.oceanus.access import get_bars
    from tests.oceanus.test_ingest import FakeExchange

    start_ms = int(START.timestamp() * 1000)
    fake = FakeExchange(start_ms, n_bars=200)
    bars = get_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=200),
                    root=tmp_path, exchange=fake)

    out = _execute({"BTC/USDT": bars}, Timeframe.H1, DoNothingStrategy(),
                   StubBroker(), StubPortfolio(Decimal("10000")), CONFIG)
    assert out.bars_processed == len(bars) > 0
    assert (out.equity_curve == 10000.0).all()
