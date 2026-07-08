"""Phase 5 — apply an explicit, documented cleaning policy.

clean() is validation's counterpart: validate() only *reports*, clean()
is the only place data may be *changed* — and every change it makes is
listed in its result, never silent.

THE POLICY (chosen by the founder 2026-07-08, recorded in HANDOFF.md):
- Gaps:      LEAVE AND FLAG. Never invent bars to bridge a hole; a gap
             stays visible and validation keeps reporting it. Asking for
             gap-filling raises an error rather than quietly interpolating.
- Outliers:  FLAG ONLY (default). A real crash looks exactly like a data
             error; deleting it could erase the most important bar in the
             dataset. (drop_outliers=True exists but is off by default.)
- Unambiguous garbage: DROP AND REPORT. Exact-duplicate timestamps
             (first copy kept) and physically impossible rows (high < low,
             open/close outside [low, high], non-positive prices, negative
             volume) are removed. Each removal is reported; any hole left
             behind shows up as an honest gap in the next validation.
- Ordering:  rows are sorted by open_time (non-destructive; reported).
"""

from dataclasses import dataclass, field
from datetime import timezone

from pandas import DataFrame

from chronos.oceanus.validate import OUTLIER_THRESHOLD


@dataclass(frozen=True)
class CleaningPolicy:
    """What clean() is allowed to do. The defaults are the founder's policy."""

    drop_broken_rows: bool = True  # duplicates + impossible rows
    drop_outliers: bool = False  # founder chose flag-only
    fill_gaps: bool = False  # must stay False; True raises (no interpolation)
    outlier_threshold: float = OUTLIER_THRESHOLD


DEFAULT_POLICY = CleaningPolicy()


@dataclass
class CleaningResult:
    """The cleaned table plus a full account of what was done to it."""

    frame: DataFrame
    actions: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Cleaning report — {len(self.frame)} bars out"]
        if not self.actions:
            lines.append("  ✓ no changes were needed")
        else:
            lines.append(f"  {len(self.actions)} change(s) made:")
            for action in self.actions:
                lines.append(f"    - {action}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()


def clean(frame: DataFrame, policy: CleaningPolicy = DEFAULT_POLICY) -> CleaningResult:
    """Apply the policy to a copy of `frame`; report every change made.

    The input frame is never modified. Gaps are NEVER filled — that would
    fabricate a price path that never happened.
    """
    if policy.fill_gaps:
        raise ValueError(
            "Gap-filling is not supported: the chosen policy is leave-and-flag. "
            "Inventing bars fabricates a price path that never existed."
        )

    result = frame.copy(deep=True)
    actions: list[str] = []

    # Sortable timestamps even if some rows are naive (naive treated as
    # UTC for ordering only — the rows themselves are left as they are).
    def sort_key(t):
        return t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)

    keys = result["open_time"].map(sort_key)
    if not keys.is_monotonic_increasing:
        order = keys.sort_values(kind="stable").index
        result = result.loc[order]
        actions.append("rows were out of time order — sorted by open_time (no data altered)")

    if policy.drop_broken_rows:
        # Exact duplicate timestamps: keep the first copy, drop the rest.
        dup_mask = result["open_time"].map(sort_key).duplicated(keep="first")
        for t in result.loc[dup_mask, "open_time"]:
            actions.append(f"dropped duplicate bar at {t} (first copy kept)")
        result = result[~dup_mask]

        # Physically impossible rows: meaningless as prices, so removed.
        o, h, l, c, v = (result[col] for col in ["open", "high", "low", "close", "volume"])
        impossible = (
            (h < l)
            | (o < l) | (o > h)
            | (c < l) | (c > h)
            | (o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)
            | (v < 0)
        )
        for row in result[impossible].itertuples(index=False):
            actions.append(
                f"dropped impossible bar at {row.open_time} "
                f"(O={row.open} H={row.high} L={row.low} C={row.close} V={row.volume})"
            )
        result = result[~impossible]

    if policy.drop_outliers:
        closes = result["close"].astype(float)
        moves = (closes / closes.shift(1) - 1).abs()
        outlier_mask = moves > policy.outlier_threshold
        for t, move in zip(result.loc[outlier_mask, "open_time"], moves[outlier_mask]):
            actions.append(f"dropped outlier bar at {t} ({move:.1%} single-bar move)")
        result = result[~outlier_mask]

    return CleaningResult(frame=result.reset_index(drop=True), actions=actions)
