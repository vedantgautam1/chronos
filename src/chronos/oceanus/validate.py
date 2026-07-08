"""Phase 4 — detect data problems and report them (never fix them here).

validate() is a PURE function: it reads a table of bars and returns a
report of every integrity problem it finds. It never modifies the data,
never fills a gap, never drops a row. Detection and repair are kept
strictly separate so nothing is ever "fixed" silently — repair happens
in clean.py (Phase 5), explicitly and on the record.

Outlier definition (documented threshold, recorded in HANDOFF.md):
a bar whose close is more than OUTLIER_THRESHOLD (default 25%) away
from the previous bar's close. Crypto is volatile, but a >25% move
within a single bar is rare enough to deserve a human look. Outliers
are FLAGGED, never removed — a real crash looks like an outlier too.
"""

from dataclasses import dataclass, field
from datetime import timedelta, timezone

from pandas import DataFrame

from chronos.oceanus.model import Timeframe

OUTLIER_THRESHOLD = 0.25  # 25% single-bar close-to-close move


@dataclass(frozen=True)
class Issue:
    """One problem found in the data: what kind, and where."""

    kind: str  # "gap", "duplicate", "out_of_order", "ohlc", "impossible_value", "naive_timestamp", "outlier"
    message: str  # plain-English description with the location


@dataclass
class ValidationReport:
    """Everything validate() found, in a form a person can read."""

    n_bars: int
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def kinds(self) -> set[str]:
        return {issue.kind for issue in self.issues}

    def summary(self) -> str:
        lines = [f"Validation report — {self.n_bars} bars checked"]
        if self.ok:
            lines.append("  ✓ no problems found")
        else:
            lines.append(f"  ✗ {len(self.issues)} problem(s) found:")
            for issue in self.issues:
                lines.append(f"    [{issue.kind}] {issue.message}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()


def validate(
    frame: DataFrame,
    timeframe: Timeframe,
    outlier_threshold: float = OUTLIER_THRESHOLD,
) -> ValidationReport:
    """Inspect a table of bars; report every problem; change nothing."""
    issues: list[Issue] = []
    if frame.empty:
        return ValidationReport(n_bars=0)

    times = list(frame["open_time"])

    # --- timezone problems: a naive timestamp is ambiguous, hence invalid.
    naive_rows = [i for i, t in enumerate(times) if t.tzinfo is None]
    for i in naive_rows[:5]:  # list the first few, count the rest
        issues.append(Issue("naive_timestamp", f"row {i}: {times[i]} has no timezone"))
    if len(naive_rows) > 5:
        issues.append(Issue("naive_timestamp", f"...and {len(naive_rows) - 5} more naive timestamps"))

    # For the order/duplicate/gap checks below, naive timestamps are
    # TREATED AS UTC so the checks can still run. That's a comparison
    # convenience only — the naive rows are already reported above.
    keys = [t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc) for t in times]

    # --- duplicates: the same open_time appearing more than once.
    seen: dict = {}
    for i, key in enumerate(keys):
        if key in seen:
            issues.append(Issue("duplicate", f"row {i}: open_time {key} already appeared at row {seen[key]}"))
        else:
            seen[key] = i

    # --- non-monotonic order: time must strictly increase down the table.
    for i in range(1, len(keys)):
        if keys[i] < keys[i - 1]:
            issues.append(Issue("out_of_order", f"row {i}: {keys[i]} comes after {keys[i - 1]} but is earlier"))

    # --- gaps: with a fixed timeframe, consecutive bars must be exactly
    # one duration apart. A bigger step means bars are missing.
    step: timedelta = timeframe.duration
    ordered = sorted(set(keys))
    for prev, cur in zip(ordered, ordered[1:]):
        hole = cur - prev
        if hole > step:
            n_missing = int(hole / step) - 1
            issues.append(Issue("gap", f"{n_missing} bar(s) missing between {prev} and {cur}"))

    # --- OHLC violations and impossible values, row by row.
    for i, row in enumerate(frame.itertuples(index=False)):
        o, h, l, c, v = float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume)
        when = keys[i]
        if min(o, h, l, c) <= 0:
            issues.append(Issue("impossible_value", f"row {i} ({when}): non-positive price (O={o} H={h} L={l} C={c})"))
        if v < 0:
            issues.append(Issue("impossible_value", f"row {i} ({when}): negative volume ({v})"))
        if h < l:
            issues.append(Issue("ohlc", f"row {i} ({when}): high ({h}) < low ({l})"))
        else:
            if not (l <= o <= h):
                issues.append(Issue("ohlc", f"row {i} ({when}): open ({o}) outside [low, high] = [{l}, {h}]"))
            if not (l <= c <= h):
                issues.append(Issue("ohlc", f"row {i} ({when}): close ({c}) outside [low, high] = [{l}, {h}]"))

    # --- outliers: implausibly large single-bar moves. Flagged only.
    closes = [float(c) for c in frame["close"]]
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            move = abs(closes[i] / closes[i - 1] - 1)
            if move > outlier_threshold:
                issues.append(
                    Issue(
                        "outlier",
                        f"row {i} ({keys[i]}): close moved {move:.1%} vs previous bar "
                        f"({closes[i - 1]} → {closes[i]}); threshold is {outlier_threshold:.0%} — "
                        "flagged for a human look, not removed",
                    )
                )

    return ValidationReport(n_bars=len(frame), issues=issues)
