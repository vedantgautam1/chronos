"""Tests for the sealed-range mechanism (invariant I4 — the holdout is
sealed). Seals live in a SealRegistry (JSON file); get_bars() is the
enforcement point. Every test isolates both the bar-data root (tmp_path,
like the rest of the Oceanus suite) and the seal registry (a separate
file under tmp_path) — never the real project's data/ or configs/ paths.
"""

from datetime import datetime, timedelta, timezone

import pytest

from chronos.oceanus.access import DataIntegrityError, SealedDataError, get_bars
from chronos.oceanus.model import Timeframe
from chronos.oceanus.seal import FinalEvaluationToken, SealedRange, SealRegistry

from .test_ingest import FakeExchange
from .test_store import START, START_MS


def registry_at(tmp_path) -> SealRegistry:
    return SealRegistry(tmp_path / "sealed_ranges.json")


def fake_bars(n=48):
    return FakeExchange(START_MS, n_bars=n)


def test_sealed_range_without_token_is_refused(tmp_path):
    registry = registry_at(tmp_path)
    seal_start = START + timedelta(hours=10)
    seal_end = START + timedelta(hours=20)
    registry.seal("BTC/USDT", Timeframe.H1, seal_start, seal_end, reason="held out for Atropos")

    with pytest.raises(SealedDataError) as caught:
        get_bars("BTC/USDT", Timeframe.H1, seal_start, seal_end,
                 root=tmp_path, exchange=fake_bars(), seal_registry=registry)
    assert "sealed" in str(caught.value).lower()
    assert "held out for Atropos" in str(caught.value)
    assert isinstance(caught.value, DataIntegrityError)  # required subclass relationship


def test_sealed_range_with_valid_token_returns_data(tmp_path, capsys):
    registry = registry_at(tmp_path)
    seal_start = START + timedelta(hours=10)
    seal_end = START + timedelta(hours=20)
    registry.seal("BTC/USDT", Timeframe.H1, seal_start, seal_end, reason="held out for Atropos")

    token = FinalEvaluationToken(reason="Atropos final evaluation, run #1")
    bars = get_bars("BTC/USDT", Timeframe.H1, seal_start, seal_end,
                    root=tmp_path, exchange=fake_bars(), seal_registry=registry,
                    seal_token=token)
    assert len(bars) == 10
    log = capsys.readouterr().out
    assert "SEALED" in log
    assert "Atropos final evaluation, run #1" in log


def test_non_overlapping_request_needs_no_token(tmp_path):
    registry = registry_at(tmp_path)
    registry.seal("BTC/USDT", Timeframe.H1,
                  START + timedelta(hours=10), START + timedelta(hours=20),
                  reason="held out for Atropos")

    # Entirely before the seal: must work exactly as before, no token.
    bars = get_bars("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=5),
                    root=tmp_path, exchange=fake_bars(), seal_registry=registry)
    assert len(bars) == 5


def test_partial_overlap_is_also_refused(tmp_path):
    registry = registry_at(tmp_path)
    registry.seal("BTC/USDT", Timeframe.H1,
                  START + timedelta(hours=10), START + timedelta(hours=20),
                  reason="held out for Atropos")

    # Request straddles the seal boundary: hours 5-15 partially overlaps 10-20.
    with pytest.raises(SealedDataError):
        get_bars("BTC/USDT", Timeframe.H1, START + timedelta(hours=5), START + timedelta(hours=15),
                 root=tmp_path, exchange=fake_bars(), seal_registry=registry)


def test_different_symbol_or_timeframe_is_unaffected(tmp_path):
    registry = registry_at(tmp_path)
    registry.seal("BTC/USDT", Timeframe.H1,
                  START + timedelta(hours=10), START + timedelta(hours=20),
                  reason="held out for Atropos")
    assert not registry.is_sealed("ETH/USDT", Timeframe.H1,
                                   START + timedelta(hours=10), START + timedelta(hours=20))
    assert not registry.is_sealed("BTC/USDT", Timeframe.D1,
                                   START + timedelta(hours=10), START + timedelta(hours=20))


def test_registry_persists_across_instances(tmp_path):
    path = tmp_path / "sealed_ranges.json"
    SealRegistry(path).seal("BTC/USDT", Timeframe.H1,
                             START, START + timedelta(hours=5), reason="persisted seal")
    reloaded = SealRegistry(path)
    assert len(reloaded.sealed_ranges()) == 1
    assert reloaded.sealed_ranges()[0].reason == "persisted seal"


def test_sealed_ranges_returns_a_copy_not_the_live_list(tmp_path):
    registry = registry_at(tmp_path)
    registry.seal("BTC/USDT", Timeframe.H1, START, START + timedelta(hours=5), reason="x")
    ranges = registry.sealed_ranges()
    ranges.clear()
    assert len(registry.sealed_ranges()) == 1  # registry unaffected


def test_sealed_range_rejects_naive_and_reversed_and_empty_reason():
    naive = datetime(2026, 1, 1)
    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="naive"):
        SealedRange(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=naive, end=aware, sealed_at=aware, reason="x")
    with pytest.raises(ValueError, match="before"):
        SealedRange(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=aware, end=aware, sealed_at=aware, reason="x")
    with pytest.raises(ValueError, match="non-empty"):
        SealedRange(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=aware, end=aware + timedelta(hours=1), sealed_at=aware, reason="  ")


def test_final_evaluation_token_rejects_empty_reason():
    with pytest.raises(ValueError, match="non-empty"):
        FinalEvaluationToken(reason="   ")
