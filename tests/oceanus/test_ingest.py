"""Phase 2 tests: pagination, idempotency, dedup/sort, is_final marking.

These use a FakeExchange instead of the real network, so they are fast,
free, and deterministic. The fake behaves like Binance's public API:
it holds a full candle series and serves it in limited pages.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from chronos.oceanus.ingest import fetch_bars
from chronos.oceanus.model import Timeframe

HOUR_MS = 3_600_000


class FakeExchange:
    """Serves a synthetic hourly candle series, `page_limit` bars per call."""

    def __init__(self, first_ts_ms: int, n_bars: int, page_limit: int = 100):
        self.candles = [
            [first_ts_ms + i * HOUR_MS, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0]
            for i in range(n_bars)
        ]
        self.page_limit = page_limit
        self.calls = 0

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params={}):
        self.calls += 1
        page = [c for c in self.candles if c[0] >= since]
        return page[: min(limit or self.page_limit, self.page_limit)]


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
START_MS = int(START.timestamp() * 1000)


def test_pagination_assembles_the_full_range():
    # 250 hourly bars available, 100 per page -> needs 3 pages.
    fake = FakeExchange(START_MS, n_bars=250, page_limit=100)
    frame = fetch_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=250), exchange=fake)
    assert len(frame) == 250
    assert fake.calls >= 3  # proves it really paginated


def test_end_is_excluded_and_start_included():
    fake = FakeExchange(START_MS, n_bars=50)
    frame = fetch_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=10), exchange=fake)
    assert len(frame) == 10
    assert frame["open_time"].iloc[0] == START
    assert frame["open_time"].iloc[-1] == START + timedelta(hours=9)


def test_idempotent_same_range_twice_gives_identical_rows():
    fake = FakeExchange(START_MS, n_bars=100)
    a = fetch_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=100), exchange=fake)
    b = fetch_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=100), exchange=fake)
    pd.testing.assert_frame_equal(a, b)
    assert not a["open_time"].duplicated().any()


def test_overlapping_pages_are_deduplicated():
    class OverlappingFake(FakeExchange):
        # Steps back 10 bars each page, like an exchange overlapping pages.
        def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params={}):
            page = [c for c in self.candles if c[0] >= since - 10 * HOUR_MS]
            return page[: self.page_limit]

    fake = OverlappingFake(START_MS, n_bars=250, page_limit=100)
    frame = fetch_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=250), exchange=fake)
    assert len(frame) == 250
    assert not frame["open_time"].duplicated().any()
    assert frame["open_time"].is_monotonic_increasing


def test_forming_bar_is_marked_not_final():
    # Build a series that runs right up to the current hour: the last
    # bar's window hasn't closed yet, so it must be is_final=False.
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    first = current_hour - timedelta(hours=23)
    fake = FakeExchange(int(first.timestamp() * 1000), n_bars=24)
    frame = fetch_bars("BTC/USDT", Timeframe.H1, first, current_hour + timedelta(hours=1), exchange=fake)
    assert len(frame) == 24
    assert not frame["is_final"].iloc[-1]  # still forming
    assert frame["is_final"].iloc[:-1].all()  # all earlier bars complete


def test_naive_datetimes_are_rejected():
    fake = FakeExchange(START_MS, n_bars=10)
    with pytest.raises(ValueError, match="naive"):
        fetch_bars("BTC/USDT", Timeframe.H1, datetime(2026, 1, 1), START + timedelta(hours=5), exchange=fake)


def test_start_must_be_before_end():
    fake = FakeExchange(START_MS, n_bars=10)
    with pytest.raises(ValueError, match="before"):
        fetch_bars("BTC/USDT", Timeframe.H1, START, START, exchange=fake)


def test_empty_result_when_no_data_exists_yet():
    # Requesting a range entirely before the pair existed -> empty frame,
    # not an error and not an infinite loop.
    fake = FakeExchange(START_MS, n_bars=10)
    frame = fetch_bars("BTC/USDT", Timeframe.H1, START - timedelta(days=30), START - timedelta(days=29), exchange=fake)
    assert frame.empty
