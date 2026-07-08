"""Phase 1 tests: a well-formed Bar is accepted; impossible ones are rejected.

The Bar validates itself at creation, so "rejected" means creating it
raises ValueError. These tests plant one specific flaw at a time and
assert the model refuses it.
"""

from datetime import datetime, timezone

import pytest

from chronos.oceanus.model import Bar, Timeframe

# A perfectly valid set of field values, reused by every test below.
GOOD = dict(
    symbol="BTC/USDT",
    timeframe=Timeframe.H1,
    open_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    open=100.0,
    high=110.0,
    low=95.0,
    close=105.0,
    volume=42.5,
    is_final=True,
)


def test_valid_bar_is_accepted():
    bar = Bar(**GOOD)
    assert bar.symbol == "BTC/USDT"
    assert bar.is_final is True


def test_close_time_is_open_time_plus_duration():
    bar = Bar(**GOOD)
    assert bar.close_time == datetime(2026, 7, 1, 13, 0, tzinfo=timezone.utc)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="naive"):
        Bar(**{**GOOD, "open_time": datetime(2026, 7, 1, 12, 0)})  # no tzinfo


def test_non_utc_timestamp_is_rejected():
    from datetime import timedelta, timezone as tz

    tokyo = tz(timedelta(hours=9))
    with pytest.raises(ValueError, match="not UTC"):
        Bar(**{**GOOD, "open_time": datetime(2026, 7, 1, 12, 0, tzinfo=tokyo)})


def test_high_below_low_is_rejected():
    with pytest.raises(ValueError, match="low .* > high"):
        Bar(**{**GOOD, "high": 90.0, "low": 95.0, "open": 92.0, "close": 92.0})


def test_open_outside_low_high_is_rejected():
    with pytest.raises(ValueError, match="open .* outside"):
        Bar(**{**GOOD, "open": 120.0})  # above high=110


def test_close_outside_low_high_is_rejected():
    with pytest.raises(ValueError, match="close .* outside"):
        Bar(**{**GOOD, "close": 90.0})  # below low=95


def test_non_positive_price_is_rejected():
    with pytest.raises(ValueError, match="must be > 0"):
        Bar(**{**GOOD, "low": 0.0})


def test_negative_volume_is_rejected():
    with pytest.raises(ValueError, match="volume"):
        Bar(**{**GOOD, "volume": -1.0})


def test_bar_is_immutable():
    bar = Bar(**GOOD)
    with pytest.raises(Exception):  # frozen dataclass refuses assignment
        bar.close = 999.0


def test_timeframe_durations():
    from datetime import timedelta

    assert Timeframe.M1.duration == timedelta(minutes=1)
    assert Timeframe.H1.duration == timedelta(hours=1)
    assert Timeframe.D1.duration == timedelta(days=1)
