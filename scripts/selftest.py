"""A live, plain-English self-test of Oceanus.

Run:  uv run python scripts/selftest.py

Unlike the pytest suite (which uses a fake exchange for speed), this hits
REAL Binance and actively tries to break things, printing PASS/FAIL and a
one-line explanation for each check. Nothing here touches your real data/
folder — the sabotage checks use a throwaway temporary directory.
"""

import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so we can reuse the exact test fixtures

from chronos.oceanus.access import DataIntegrityError, get_bars, universe_at
from chronos.oceanus.clean import clean
from chronos.oceanus.model import BAR_COLUMNS, Timeframe
from chronos.oceanus.store import snapshot_hash, store_dir
from chronos.oceanus.validate import validate
from tests.oceanus.corrupted_fixture import PLANTED, make_corrupted_frame
from tests.oceanus.test_acceptance import (
    test_acceptance_5_one_door_guard_nothing_bypasses_oceanus as one_door_guard,
)

results: list[tuple[str, bool, str]] = []


def check(name):
    """Decorator: run a check, record PASS/FAIL, never crash the whole run."""
    def wrap(fn):
        try:
            detail = fn()
            results.append((name, True, detail))
        except AssertionError as e:
            results.append((name, False, f"assertion failed: {e}"))
        except Exception as e:  # unexpected error is itself a failure
            results.append((name, False, f"unexpected {type(e).__name__}: {e}"))
        return fn
    return wrap


NOW = datetime.now(timezone.utc)


@check("1. Live data comes through the one door, clean")
def _():
    bars = get_bars("BTC/USDT", Timeframe.D1, NOW - timedelta(days=30), NOW)
    report = validate(bars, Timeframe.D1)
    assert len(bars) >= 25, f"expected ~29 daily bars, got {len(bars)}"
    assert report.ok, f"real data had problems: {report.summary()}"
    return f"{len(bars)} real daily bars fetched and validated clean"


@check("2. No future leakage — the still-forming bar is excluded")
def _():
    bars = get_bars("BTC/USDT", Timeframe.D1, NOW - timedelta(days=5), NOW + timedelta(days=1))
    assert bars["is_final"].all(), "an unfinished bar was served!"
    today = NOW.date()
    served_days = {t.date() for t in bars["open_time"]}
    assert today not in served_days, "today's forming bar leaked into the result!"
    return f"today ({today}) correctly absent; all {len(bars)} served bars are final"


@check("3. Reproducible — same request twice gives identical data + hash")
def _():
    lo, hi = NOW - timedelta(days=15), NOW - timedelta(days=2)  # fully in the past
    a = get_bars("BTC/USDT", Timeframe.D1, lo, hi)
    b = get_bars("BTC/USDT", Timeframe.D1, lo, hi)
    pd.testing.assert_frame_equal(a, b)
    assert snapshot_hash(a) == snapshot_hash(b)
    return f"identical rows and matching hash {snapshot_hash(a)[:12]}…"


@check("4. Snapshot pinning refuses data that has changed")
def _():
    lo, hi = NOW - timedelta(days=15), NOW - timedelta(days=2)
    try:
        get_bars("BTC/USDT", Timeframe.D1, lo, hi, snapshot="0" * 64)
    except DataIntegrityError:
        return "a wrong snapshot hash was correctly rejected"
    raise AssertionError("a wrong hash was NOT rejected")


@check("5. The door REFUSES corrupted stored data")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        folder = store_dir("BTC/USDT", Timeframe.H1, root=root)
        folder.mkdir(parents=True)
        # 6 clean-ish hourly bars, then sabotage two of them:
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        rows = [
            {"open_time": pd.Timestamp(start + timedelta(hours=i)), "open": 100.0 + i,
             "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i, "volume": 10.0,
             "is_final": True}
            for i in range(6)
        ]
        rows.append(dict(rows[2]))          # duplicate timestamp
        rows[4]["high"], rows[4]["low"] = 99.0, 101.0  # high < low
        pd.DataFrame(rows, columns=BAR_COLUMNS).sort_values("open_time").to_parquet(
            folder / "v0001.parquet", index=False)
        try:
            get_bars("BTC/USDT", Timeframe.H1, start, start + timedelta(hours=6), root=root)
        except DataIntegrityError as e:
            assert "duplicate" in str(e) and "high" in str(e)
            return "corrupted data was refused with a clear error naming the problems"
    raise AssertionError("corrupted data was NOT refused")


@check("6. Validation catches EVERY kind of planted problem")
def _():
    report = validate(make_corrupted_frame(), Timeframe.H1)
    missed = [k for k in PLANTED if k not in report.kinds()]
    assert not missed, f"validation missed: {missed}"
    return f"all {len(PLANTED)} planted problem types were flagged"


@check("7. Cleaning drops garbage, keeps gaps/outliers, reports every change")
def _():
    result = clean(make_corrupted_frame())
    assert result.actions, "clean() reported no changes"
    after = validate(result.frame, Timeframe.H1).kinds()
    assert "duplicate" not in after and "ohlc" not in after, "garbage survived cleaning"
    assert "gap" in after and "outlier" in after, "policy should leave gaps/outliers flagged"
    return f"{len(result.actions)} changes made and reported; gaps/outliers left flagged"


@check("8. Bad input is rejected (naive, non-UTC timestamp)")
def _():
    try:
        get_bars("BTC/USDT", Timeframe.D1, datetime(2026, 1, 1), NOW)  # no timezone
    except ValueError as e:
        assert "naive" in str(e)
        return "a timezone-less start date was correctly rejected"
    raise AssertionError("a naive datetime was NOT rejected")


@check("9. universe_at() is point-in-time (survivorship-bias guard)")
def _():
    before = universe_at(date(2015, 1, 1))
    after = universe_at(date.today())
    assert before == [], f"expected nothing tradeable in 2015, got {before}"
    assert "BTC/USDT" in after
    return f"2015 → {before} (empty), today → {after}"


@check("10. One-door guard — nothing bypasses Oceanus")
def _():
    one_door_guard()  # raises if any file outside oceanus/ reads ccxt or data/
    return "no code outside oceanus/ reads the exchange or data files directly"


def main():
    print("Running Oceanus live self-test (this makes real calls to Binance)...\n")
    for name, passed, detail in results:
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name}\n         → {detail}")
    n_pass = sum(1 for _, p, _ in results if p)
    print(f"\n{n_pass}/{len(results)} checks passed.")
    if n_pass != len(results):
        print("Something failed — copy the output above and share it for a look.")
        sys.exit(1)
    print("Everything Oceanus promises is holding up on live data.")


if __name__ == "__main__":
    main()
