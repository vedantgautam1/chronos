"""Phase 3 tests: roundtrip, versioning, load-if-present, snapshot hash.

Everything runs against a temporary directory (pytest's tmp_path) and the
FakeExchange from the ingestion tests — no network, no touching data/.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from chronos.oceanus.model import BAR_COLUMNS, Timeframe
from chronos.oceanus.store import get_range, load_stored, snapshot_hash, store_bars

from .test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
START_MS = int(START.timestamp() * 1000)


def make_bars(n: int, first: datetime = START, base_price: float = 100.0) -> pd.DataFrame:
    """A frame of n completed hourly bars starting at `first`."""
    rows = [
        {
            "open_time": pd.Timestamp(first + timedelta(hours=i)),  # already UTC-aware
            "open": base_price + i,
            "high": base_price + i + 1,
            "low": base_price + i - 1,
            "close": base_price + i + 0.5,
            "volume": 10.0,
            "is_final": True,
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows, columns=BAR_COLUMNS)


def test_store_then_load_roundtrip(tmp_path):
    bars = make_bars(24)
    store_bars("BTC/USDT", Timeframe.H1, bars, root=tmp_path)
    loaded = load_stored("BTC/USDT", Timeframe.H1, root=tmp_path)
    pd.testing.assert_frame_equal(loaded, bars)


def test_non_final_bars_are_never_stored(tmp_path):
    bars = make_bars(5)
    bars.loc[4, "is_final"] = False  # pretend the last bar is still forming
    store_bars("BTC/USDT", Timeframe.H1, bars, root=tmp_path)
    loaded = load_stored("BTC/USDT", Timeframe.H1, root=tmp_path)
    assert len(loaded) == 4
    assert loaded["is_final"].all()


def test_storing_same_data_again_writes_no_new_version(tmp_path):
    bars = make_bars(24)
    first_path = store_bars("BTC/USDT", Timeframe.H1, bars, root=tmp_path)
    second_path = store_bars("BTC/USDT", Timeframe.H1, bars, root=tmp_path)
    assert first_path is not None
    assert second_path is None  # unchanged -> no v0002
    folder = first_path.parent
    assert len(list(folder.glob("v*.parquet"))) == 1


def test_new_data_creates_new_version_and_old_is_untouched(tmp_path):
    v1 = store_bars("BTC/USDT", Timeframe.H1, make_bars(24), root=tmp_path)
    v1_bytes = v1.read_bytes()

    more = make_bars(24, first=START + timedelta(hours=24))  # the next day
    v2 = store_bars("BTC/USDT", Timeframe.H1, more, root=tmp_path)

    assert v2 is not None and v2 != v1
    assert v1.read_bytes() == v1_bytes  # old version byte-identical
    assert len(load_stored("BTC/USDT", Timeframe.H1, root=tmp_path)) == 48


def test_restated_candle_new_wins_old_version_preserved(tmp_path):
    original = make_bars(24)
    v1 = store_bars("BTC/USDT", Timeframe.H1, original, root=tmp_path)

    restated = make_bars(24)
    restated.loc[10, "close"] = 999.0  # exchange revised one candle
    restated.loc[10, "high"] = 999.0
    v2 = store_bars("BTC/USDT", Timeframe.H1, restated, root=tmp_path)

    assert v2 is not None
    latest = load_stored("BTC/USDT", Timeframe.H1, root=tmp_path)
    assert latest.loc[10, "close"] == 999.0  # new value won
    old = pd.read_parquet(v1)
    assert old.loc[10, "close"] == original.loc[10, "close"]  # history intact


def test_get_range_fetches_once_then_serves_from_disk(tmp_path):
    fake = FakeExchange(START_MS, n_bars=48)
    end = START + timedelta(hours=48)

    first = get_range("BTC/USDT", Timeframe.H1, START, end, root=tmp_path, exchange=fake)
    calls_after_first = fake.calls
    assert calls_after_first > 0 and len(first) == 48

    second = get_range("BTC/USDT", Timeframe.H1, START, end, root=tmp_path, exchange=fake)
    assert fake.calls == calls_after_first  # zero new network calls
    pd.testing.assert_frame_equal(first, second)


def test_get_range_fetches_only_the_missing_edge(tmp_path):
    fake = FakeExchange(START_MS, n_bars=72)
    get_range("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=24), root=tmp_path, exchange=fake)

    # Extend the request one day further: only hours 24-48 are fetched.
    frame = get_range("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=48), root=tmp_path, exchange=fake)
    assert len(frame) == 48
    assert not frame["open_time"].duplicated().any()


def test_snapshot_hash_is_stable_and_content_sensitive(tmp_path):
    bars = make_bars(24)
    assert snapshot_hash(bars) == snapshot_hash(bars.copy())  # same data, same hash
    assert snapshot_hash(bars) == snapshot_hash(bars.sample(frac=1))  # row order irrelevant

    changed = make_bars(24)
    changed.loc[3, "close"] += 0.00001  # one tiny change anywhere
    assert snapshot_hash(changed) != snapshot_hash(bars)  # -> different hash

    # And the hash survives a disk roundtrip (Parquet preserves the values).
    store_bars("BTC/USDT", Timeframe.H1, bars, root=tmp_path)
    assert snapshot_hash(load_stored("BTC/USDT", Timeframe.H1, root=tmp_path)) == snapshot_hash(bars)
