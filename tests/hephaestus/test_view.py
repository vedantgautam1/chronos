"""Phase 1 tests: the MarketView's time bound is structural (invariant I1).

The scenario used throughout: 24 hourly bars opening 00:00–23:00 on
2026-01-01. Bar k opens at k:00 and CLOSES at (k+1):00. So at decision
time t = 05:00, exactly bars 0..4 have closed — bar 5 is mid-flight and
must be invisible.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from chronos.hephaestus.view import Context, Feed, MarketView
from chronos.oceanus.model import BAR_COLUMNS, Timeframe

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def hourly_frame(n: int) -> pd.DataFrame:
    rows = [
        {
            "open_time": pd.Timestamp(START + timedelta(hours=i)),
            "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i,
            "close": 100.5 + i, "volume": 10.0, "is_final": True,
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows, columns=BAR_COLUMNS)


def feed_of(n: int = 24) -> Feed:
    return Feed({"BTC/USDT": hourly_frame(n)}, Timeframe.H1)


def test_only_closed_bars_are_visible():
    view = feed_of().view_at(START + timedelta(hours=5))  # t = 05:00
    bars = view.bars("BTC/USDT", lookback=100)
    assert len(bars) == 5  # bars opening 00..04 have closed by 05:00
    assert bars["open_time"].iloc[-1] == START + timedelta(hours=4)


def test_the_bar_closing_exactly_at_t_is_included():
    # Bar 4 closes at exactly 05:00; spec says open_time + timeframe <= t.
    view = feed_of().view_at(START + timedelta(hours=5))
    assert view.bars("BTC/USDT", 1)["open_time"].iloc[0] == START + timedelta(hours=4)


def test_one_second_before_the_close_the_bar_is_invisible():
    view = feed_of().view_at(START + timedelta(hours=5) - timedelta(seconds=1))
    bars = view.bars("BTC/USDT", 100)
    assert len(bars) == 4  # bar 4 hasn't closed yet at 04:59:59
    assert bars["open_time"].iloc[-1] == START + timedelta(hours=3)


def test_before_any_bar_has_closed_the_view_is_empty():
    view = feed_of().view_at(START + timedelta(minutes=30))
    assert view.bars("BTC/USDT", 10).empty


def test_lookback_returns_exactly_the_last_n_bars():
    view = feed_of().view_at(START + timedelta(hours=10))
    bars = view.bars("BTC/USDT", 3)
    assert list(bars["open_time"]) == [START + timedelta(hours=h) for h in (7, 8, 9)]


def test_the_view_physically_contains_no_future_rows():
    # The structural claim itself: even reaching into the view's private
    # state (which a strategy could do — this is Python), there is nothing
    # beyond t to find. The future was never put in.
    t = START + timedelta(hours=7)
    view = feed_of().view_at(t)
    internal = view._frames["BTC/USDT"]  # deliberate white-box poke
    close_times = internal["open_time"] + Timeframe.H1.duration
    assert (close_times <= t).all()


def test_mutating_the_returned_frame_does_not_touch_the_engine():
    feed = feed_of()
    view = feed.view_at(START + timedelta(hours=10))
    bars = view.bars("BTC/USDT", 5)
    bars.loc[:, "close"] = 999999.0  # strategy scribbles on its copy

    again = view.bars("BTC/USDT", 5)
    assert (again["close"] != 999999.0).all()  # view unaffected
    assert (feed._frames["BTC/USDT"]["close"] != 999999.0).all()  # feed unaffected


def test_feed_refuses_unsorted_input():
    frame = hourly_frame(5).iloc[[0, 2, 1, 3, 4]].reset_index(drop=True)
    with pytest.raises(ValueError, match="get_bars"):
        Feed({"BTC/USDT": frame}, Timeframe.H1)


def test_view_rejects_naive_now_and_unknown_symbol():
    feed = feed_of()
    with pytest.raises(ValueError, match="naive"):
        feed.view_at(datetime(2026, 1, 1, 5))
    view = feed.view_at(START + timedelta(hours=5))
    with pytest.raises(KeyError, match="universe"):
        view.bars("DOGE/USDT", 5)


def test_context_is_read_only():
    ctx = Context(rng=np.random.default_rng(42), portfolio={"cash": 100},
                  params={"fast": 10})
    with pytest.raises(TypeError):
        ctx.params["fast"] = 20  # MappingProxyType refuses
    with pytest.raises(TypeError):
        ctx.portfolio["cash"] = 0


def test_context_rng_is_seeded_and_reproducible():
    a = Context(rng=np.random.default_rng(42), portfolio={}, params={})
    b = Context(rng=np.random.default_rng(42), portfolio={}, params={})
    assert a.rng.random() == b.rng.random()  # same seed, same stream (I5)
