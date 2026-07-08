"""Phase 6 tests: the door's guarantees — no partial bars, no bad data,
snapshot pinning, point-in-time universe."""

from datetime import date, datetime, timedelta, timezone

import pytest

from chronos.oceanus.access import DataIntegrityError, get_bars, universe_at
from chronos.oceanus.model import Timeframe
from chronos.oceanus.store import snapshot_hash, store_dir

from .corrupted_fixture import make_corrupted_frame
from .test_ingest import FakeExchange
from .test_store import START, START_MS, make_bars


def test_get_bars_returns_a_clean_sorted_table(tmp_path):
    fake = FakeExchange(START_MS, n_bars=48)
    bars = get_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=48),
                    root=tmp_path, exchange=fake)
    assert len(bars) == 48
    assert bars["is_final"].all()
    assert bars["open_time"].is_monotonic_increasing
    assert not bars["open_time"].duplicated().any()


def test_forming_bar_is_never_served(tmp_path):
    # A series running right up to the present: the current hour's bar
    # exists at the exchange but must NOT come out of the door.
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    first = current_hour - timedelta(hours=23)
    fake = FakeExchange(int(first.timestamp() * 1000), n_bars=24)

    bars = get_bars("BTC/USDT", Timeframe.H1, first, current_hour + timedelta(hours=1),
                    root=tmp_path, exchange=fake)
    assert len(bars) == 23  # 24 exist, the forming one is excluded
    assert bars["open_time"].iloc[-1] == current_hour - timedelta(hours=1)
    assert bars["is_final"].all()


def test_corrupted_stored_data_is_refused(tmp_path):
    # Plant a corrupted parquet directly on disk, bypassing store_bars'
    # own hygiene — simulating damage the pipeline didn't cause.
    folder = store_dir("BTC/USDT", Timeframe.H1, root=tmp_path)
    folder.mkdir(parents=True)
    make_corrupted_frame().to_parquet(folder / "v0001.parquet", index=False)

    with pytest.raises(DataIntegrityError) as caught:
        get_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=24), root=tmp_path)
    message = str(caught.value)
    assert "Refusing to serve" in message
    assert "duplicate" in message
    assert "never serves" in message


def test_gaps_are_served_with_a_notice_not_refused(tmp_path, capsys):
    folder = store_dir("BTC/USDT", Timeframe.H1, root=tmp_path)
    folder.mkdir(parents=True)
    bars = make_bars(24)
    with_gap = bars.drop(index=5)  # hour 5 missing: honest market fact
    with_gap.to_parquet(folder / "v0001.parquet", index=False)

    served = get_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=24), root=tmp_path)
    assert len(served) == 23
    assert "gap" in capsys.readouterr().out


def test_snapshot_pinning(tmp_path):
    fake = FakeExchange(START_MS, n_bars=24)
    end = START + timedelta(hours=24)
    bars = get_bars("BTC/USDT", Timeframe.H1, START, end, root=tmp_path, exchange=fake)
    pin = snapshot_hash(bars)

    # Same request with the right pin: fine.
    again = get_bars("BTC/USDT", Timeframe.H1, START, end, snapshot=pin,
                     root=tmp_path, exchange=fake)
    assert snapshot_hash(again) == pin

    # Wrong pin: refused, with an explanation about reproducibility.
    with pytest.raises(DataIntegrityError, match="Snapshot mismatch"):
        get_bars("BTC/USDT", Timeframe.H1, START, end, snapshot="0" * 64,
                 root=tmp_path, exchange=fake)


def test_universe_at_is_point_in_time():
    assert universe_at(date(2017, 1, 1)) == []  # before BTC/USDT listed
    assert universe_at(date(2017, 8, 17)) == ["BTC/USDT"]  # listing day
    assert universe_at(datetime(2026, 7, 1, tzinfo=timezone.utc)) == ["BTC/USDT"]


def test_universe_at_rejects_naive_datetimes():
    with pytest.raises(ValueError, match="naive"):
        universe_at(datetime(2026, 7, 1))
