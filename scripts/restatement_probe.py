"""Restatement probe: has Binance quietly revised old candles since we looked?

Run:  uv run python scripts/restatement_probe.py            # check for drift
      uv run python scripts/restatement_probe.py --update   # reset the baseline

The FIRST run records a BASELINE — a fresh fetch of a fixed historical
range straight from the exchange, plus its snapshot hash. Every later run
fetches that same range fresh again and compares. If Binance has restated
any candle since, this prints exactly which bars changed and how.

This deliberately IGNORES the local cache (that's the whole point): it
always re-fetches from the exchange, so it can see changes the normal
load-if-present path would never re-download. Because of that it reaches
into ingestion internals — it is diagnostic tooling, not application code.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from chronos.oceanus.ingest import fetch_bars, make_exchange
from chronos.oceanus.model import Timeframe
from chronos.oceanus.store import snapshot_hash

# The fixed window we watch. Old enough that every bar is final; small
# enough that the baseline file stays tiny. If you change these, delete
# the baseline file (or pass --update) so you're comparing like with like.
SYMBOL = "BTC/USDT"
TIMEFRAME = Timeframe.H1
RANGE_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
RANGE_END = datetime(2026, 1, 8, tzinfo=timezone.utc)  # one week of hourly bars

BASELINE = REPO / "diagnostics" / f"restatement_{SYMBOL.replace('/', '-')}_{TIMEFRAME.value}.json"
FIELDS = ["open", "high", "low", "close", "volume"]


def fetch_fresh() -> tuple[list[dict], str]:
    """Fetch the fixed range straight from the exchange (no cache)."""
    bars = fetch_bars(SYMBOL, TIMEFRAME, RANGE_START, RANGE_END, exchange=make_exchange())
    bars = bars[bars["is_final"]]  # compare only completed bars
    records = [
        {
            "open_time": row.open_time.isoformat(),
            "open": float(row.open), "high": float(row.high), "low": float(row.low),
            "close": float(row.close), "volume": float(row.volume),
        }
        for row in bars.itertuples(index=False)
    ]
    return records, snapshot_hash(bars)


def save_baseline(records: list[dict], digest: str) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps(
            {
                "symbol": SYMBOL,
                "timeframe": TIMEFRAME.value,
                "range_start": RANGE_START.isoformat(),
                "range_end": RANGE_END.isoformat(),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "snapshot_hash": digest,
                "bars": records,
            },
            indent=2,
        )
    )


def diff(old: list[dict], new: list[dict]):
    """Compare two bar lists keyed by open_time: what's gone, new, changed."""
    old_by_t = {r["open_time"]: r for r in old}
    new_by_t = {r["open_time"]: r for r in new}
    removed = sorted(set(old_by_t) - set(new_by_t))
    added = sorted(set(new_by_t) - set(old_by_t))
    changed = []
    for t in sorted(set(old_by_t) & set(new_by_t)):
        deltas = {f: (old_by_t[t][f], new_by_t[t][f]) for f in FIELDS if old_by_t[t][f] != new_by_t[t][f]}
        if deltas:
            changed.append((t, deltas))
    return removed, added, changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="reset the baseline to current data")
    args = parser.parse_args()

    print(f"Probing {SYMBOL} {TIMEFRAME.value}  {RANGE_START:%Y-%m-%d} → {RANGE_END:%Y-%m-%d}")
    print("Fetching fresh from the exchange (ignoring the local cache)...\n")
    records, digest = fetch_fresh()

    if args.update or not BASELINE.exists():
        save_baseline(records, digest)
        how = "reset" if args.update else "recorded"
        print(f"Baseline {how}: {len(records)} bars, hash {digest[:12]}…")
        print(f"Saved to {BASELINE.relative_to(REPO)}")
        print("Re-run this in a few days or weeks to detect any restatement.")
        return

    baseline = json.loads(BASELINE.read_text())
    print(f"Baseline from {baseline['recorded_at'][:19]}  (hash {baseline['snapshot_hash'][:12]}…)")
    print(f"Right now     {datetime.now(timezone.utc).isoformat()[:19]}  (hash {digest[:12]}…)\n")

    if digest == baseline["snapshot_hash"]:
        print("✓ NO RESTATEMENT — every bar is identical to the baseline.")
        return

    removed, added, changed = diff(baseline["bars"], records)
    print("⚠ DATA CHANGED since the baseline:")
    if changed:
        print(f"\n  {len(changed)} RESTATED bar(s) — same time, different values:")
        for t, deltas in changed[:20]:
            parts = ", ".join(f"{f} {o} → {n}" for f, (o, n) in deltas.items())
            print(f"    {t}:  {parts}")
        if len(changed) > 20:
            print(f"    ...and {len(changed) - 20} more")
    if removed:
        print(f"\n  {len(removed)} bar(s) DISAPPEARED (were in baseline): {removed[:5]}")
    if added:
        print(f"\n  {len(added)} bar(s) APPEARED (not in baseline): {added[:5]}")
    print("\nThis is exactly the reproducibility risk the versioned snapshots guard against.")
    print("To accept the new data as the truth going forward, re-run with:  --update")


if __name__ == "__main__":
    main()
