"""Phase 3 — Parquet storage, load-if-present, snapshot hashing.

Layout on disk (one folder per symbol+timeframe, "/" made filesystem-safe):

    data/bars/BTC-USDT/1h/v0001.parquet
    data/bars/BTC-USDT/1h/v0002.parquet   <- newer version, older kept forever

Versioning approach (recorded in HANDOFF.md): every write that changes
anything produces a NEW numbered file holding the complete current view;
existing files are never modified or deleted. If the exchange restates an
old candle, v0002 carries the correction while v0001 still shows exactly
what we had before — so any past result can be traced to the exact bytes
it was computed from. Loading always reads the highest version.

Only COMPLETED bars (is_final=True) are ever stored. A still-forming bar
changes by the second; persisting it would poison idempotency.
"""

import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd

from chronos.oceanus.ingest import fetch_bars
from chronos.oceanus.model import BAR_COLUMNS, Timeframe

# data/bars at the repo root (this file lives in src/chronos/oceanus/).
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "bars"


def store_dir(symbol: str, timeframe: Timeframe, root: Path | None = None) -> Path:
    """Folder holding all versions for one (symbol, timeframe)."""
    safe_symbol = symbol.replace("/", "-")
    return (root or DEFAULT_ROOT) / safe_symbol / timeframe.value


def load_stored(symbol: str, timeframe: Timeframe, root: Path | None = None) -> pd.DataFrame:
    """Read the latest stored version, or an empty frame if nothing stored."""
    versions = sorted(store_dir(symbol, timeframe, root).glob("v*.parquet"))
    if not versions:
        return _empty_frame()
    return pd.read_parquet(versions[-1])


def store_bars(
    symbol: str, timeframe: Timeframe, new_bars: pd.DataFrame, root: Path | None = None
) -> Path | None:
    """Merge new_bars into what's stored and write a new version file.

    Never edits existing files. If the merge changes nothing (same data
    fetched again), no new version is written. Where a timestamp exists
    in both old and new data with different values (a restated candle),
    the NEW values win in the new version — the old version still holds
    the old values. Returns the path written, or None if nothing changed.
    """
    final_only = new_bars[new_bars["is_final"]][BAR_COLUMNS]
    stored = load_stored(symbol, timeframe, root)

    merged = (
        pd.concat([stored, final_only])
        .drop_duplicates(subset="open_time", keep="last")  # restatement: new wins
        .sort_values("open_time")
        .reset_index(drop=True)
    )
    if snapshot_hash(merged) == snapshot_hash(stored):
        return None  # nothing new and nothing restated -> no new version

    folder = store_dir(symbol, timeframe, root)
    folder.mkdir(parents=True, exist_ok=True)
    n_existing = len(list(folder.glob("v*.parquet")))
    path = folder / f"v{n_existing + 1:04d}.parquet"
    merged.to_parquet(path, index=False)
    return path


def get_range(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    root: Path | None = None,
    exchange=None,
) -> pd.DataFrame:
    """Load-if-present: return stored bars for [start, end), fetching from
    the exchange only what disk doesn't already have.

    Storage only extends the EDGES of what's stored (before the first
    stored bar, after the last). It never tries to patch holes in the
    middle — detecting those honestly is validation's job (Phase 4).
    """
    stored = load_stored(symbol, timeframe, root)

    if stored.empty:
        print(f"  [store] nothing on disk for {symbol} {timeframe.value} — fetching full range")
        fetched = fetch_bars(symbol, timeframe, start, end, exchange=exchange)
        store_bars(symbol, timeframe, fetched, root)
    else:
        first, last = stored["open_time"].iloc[0], stored["open_time"].iloc[-1]
        next_after_last = last + timeframe.duration
        missing = []
        if start < first:
            missing.append((start, min(end, first)))
        if end > next_after_last:
            missing.append((max(start, next_after_last), end))
        if missing:
            for miss_start, miss_end in missing:
                print(
                    f"  [store] fetching missing edge {miss_start:%Y-%m-%d %H:%M} → {miss_end:%Y-%m-%d %H:%M}"
                )
                fetched = fetch_bars(symbol, timeframe, miss_start, miss_end, exchange=exchange)
                store_bars(symbol, timeframe, fetched, root)
        else:
            print(f"  [store] loaded from disk — nothing re-downloaded")

    bars = load_stored(symbol, timeframe, root)
    in_range = bars[(bars["open_time"] >= start) & (bars["open_time"] < end)]
    return in_range.reset_index(drop=True)


def snapshot_hash(frame: pd.DataFrame) -> str:
    """Content hash (SHA-256) of a table of bars.

    Built from a canonical text form of the data itself — not from the
    Parquet file bytes, which could differ across library versions. The
    same bars therefore give the same hash on any machine, forever.
    """
    hasher = hashlib.sha256()
    hasher.update("|".join(BAR_COLUMNS).encode())
    ordered = frame.sort_values("open_time") if len(frame) else frame
    for row in ordered.itertuples(index=False):
        # repr() of a Python float is exact (shortest round-trip form),
        # so no precision is lost and no platform formatting sneaks in.
        line = (
            f"{row.open_time.isoformat()}|{float(row.open)!r}|{float(row.high)!r}"
            f"|{float(row.low)!r}|{float(row.close)!r}|{float(row.volume)!r}"
            f"|{bool(row.is_final)}\n"
        )
        hasher.update(line.encode())
    return hasher.hexdigest()


def _empty_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=BAR_COLUMNS)
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame["is_final"] = frame["is_final"].astype(bool)
    return frame
