"""Phase 6 — the single data door: get_bars() and universe_at().

Every other part of Chronos gets its market data by calling get_bars().
Nothing else may read the Parquet files, call ccxt, or import the
ingestion/storage modules directly (Phase 7 adds an automated guard).

What the door guarantees about anything it returns:
- only COMPLETED bars (is_final=True) — the still-forming bar is never
  served, so downstream code can never peek at a not-yet-knowable close;
- sorted by open_time, no duplicates, timezone-aware UTC;
- validated — if the requested range intersects data with an INTEGRITY
  failure (duplicates, high<low, impossible values, naive timestamps,
  out-of-order rows), the door raises DataIntegrityError instead of
  returning questionable data. Fix the stored data (clean.py) first.

Gaps and outliers are different: they are honest facts about real
markets (exchanges have outages; crashes happen), not corruption. The
door serves such data but prints a notice pointing at the validation
report. Recorded as a decision in HANDOFF.md — reviewers may tighten it.
"""

from datetime import date, datetime, time, timezone

from pandas import DataFrame

from chronos.oceanus.model import Timeframe
from chronos.oceanus.store import get_range, snapshot_hash
from chronos.oceanus.validate import validate

# Validation issue kinds that mean "corrupt data" -> the door refuses.
HARD_FAILURES = {"duplicate", "out_of_order", "ohlc", "impossible_value", "naive_timestamp"}
# Kinds that are honest market facts -> served, with a printed notice.
SOFT_NOTICES = {"gap", "outlier"}


class DataIntegrityError(Exception):
    """Raised when a requested range contains data that failed validation."""


# First version of the tradeable universe: which symbols exist as of a
# given date, so research never accidentally includes a coin before it
# was listed (survivorship bias guard). Grows as symbols are added;
# listing dates = first bar available on Binance, verified by fetching.
UNIVERSE_LISTINGS = {
    "BTC/USDT": datetime(2017, 8, 17, tzinfo=timezone.utc),
}


def get_bars(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    snapshot: str | None = None,
    root=None,  # internal: overridden only by tests
    exchange=None,  # internal: overridden only by tests
) -> DataFrame:
    """THE way to get market data: validated, completed bars in [start, end).

    If `snapshot` (a hash from a previous run) is given, the returned
    data must hash to exactly that value — otherwise the data has changed
    (e.g. the exchange restated a candle) and we raise rather than let a
    result silently stop being reproducible.
    """
    bars = get_range(symbol, timeframe, start, end, root=root, exchange=exchange)

    # The concrete no-future-leakage guard: never serve a forming bar.
    bars = bars[bars["is_final"]].reset_index(drop=True)

    report = validate(bars, timeframe)
    hard = [issue for issue in report.issues if issue.kind in HARD_FAILURES]
    soft = [issue for issue in report.issues if issue.kind in SOFT_NOTICES]
    if hard:
        details = "\n".join(f"  [{i.kind}] {i.message}" for i in hard)
        raise DataIntegrityError(
            f"Refusing to serve {symbol} {timeframe.value} {start} → {end}: "
            f"the stored data has {len(hard)} integrity problem(s):\n{details}\n"
            "Nothing was returned. Inspect with validate() and repair the "
            "stored data explicitly with clean() — the door never serves "
            "questionable data and never fixes it silently."
        )
    if soft:
        print(f"  [access] note: {len(soft)} data fact(s) in this range "
              f"({', '.join(sorted({i.kind for i in soft}))}) — run validate() for details")

    if snapshot is not None:
        actual = snapshot_hash(bars)
        if actual != snapshot:
            raise DataIntegrityError(
                f"Snapshot mismatch for {symbol} {timeframe.value}: expected "
                f"{snapshot[:12]}…, got {actual[:12]}…. The underlying data has "
                "changed since that hash was recorded (e.g. a restated candle), "
                "so a result computed from it would not be reproducible."
            )

    return bars


def universe_at(as_of: datetime | date) -> list[str]:
    """The symbols tradeable as of `as_of` — and only those.

    Backtests must call this instead of hard-coding today's coin list;
    otherwise they quietly pre-select the survivors (survivorship bias).
    """
    if isinstance(as_of, datetime):
        if as_of.tzinfo is None:
            raise ValueError(f"as_of is naive (no timezone): {as_of}")
        moment = as_of
    else:  # a plain date means "end of that day, UTC"
        moment = datetime.combine(as_of, time.max, tzinfo=timezone.utc)

    return sorted(s for s, listed in UNIVERSE_LISTINGS.items() if listed <= moment)
