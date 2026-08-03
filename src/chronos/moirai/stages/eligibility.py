"""eligibility.py — stage 4.0, Eligibility & breadth (spec §4.0).

Pure inspection of the BacktestResult and the store — no execution. Checks run in
this order (spec §4.0): completeness → unsafe flags → provisional-cost flag →
data-quality warnings → breadth → search-fragmentation screen.

Terminal signals ride in evidence via `TERMINAL_STATUS_KEY` (Phase 3 mechanism):
an unsafe flag stamps NON_PROMOTABLE (terminal, probe G8's target); too few round
trips stamps INSUFFICIENT_BREADTH. The fragmentation screen is warn-only — it
stamps a record and never gates (intent cannot be inferred mechanically; §4.0).

Reads thresholds `eligibility.min_round_trips` and
`eligibility.fragmentation_window_days` from config (I9). No numeric gate literals.
"""

import re
from datetime import datetime, timedelta

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.context import GauntletContext
from chronos.moirai.round_trips import reconstruct_round_trips
from chronos.moirai.types import (
    INSUFFICIENT_BREADTH,
    NON_PROMOTABLE,
    TERMINAL_STATUS_KEY,
    TestOutcome,
)

MOIRA_ID = "M4.0-eligibility"

# Substrings the engine stamps into `warnings` (hephaestus/engine.py, costs.py).
_UNSAFE_FLAG = "unsafe_same_bar_fill"
_PROVISIONAL_FLAG = "provisional_cost_constants"

_MIN_ROUND_TRIPS_KEY = "eligibility.min_round_trips"
_FRAGMENTATION_WINDOW_KEY = "eligibility.fragmentation_window_days"


def _grid_axes(param_grid_description) -> frozenset:
    """The set of parameter-axis names named in a `param_grid_description` string,
    e.g. "fast in range(5,55,5) x slow in range(60,200,5)" -> {fast, slow}. Two
    grids over the same axes are candidate siblings for the fragmentation screen.
    Stringly and heuristic by nature (§4.2 failure-mode note) — kept warn-only."""
    if not param_grid_description:
        return frozenset()
    axes = set()
    for part in str(param_grid_description).split("x"):
        token = part.strip().split(" in ")
        if len(token) == 2 and token[0].strip():
            axes.add(token[0].strip())
    return frozenset(axes)


class GridUnparseable(ValueError):
    """A `param_grid_description` cannot be turned into unambiguous axis→values
    geometry. Stage 4.2 catches this and records `executed: true, passed: false`
    with reason `grid_unparseable` — it never guesses the geometry (§4.2,
    CLAUDE.md rule 8). Distinct from the *no-grid* case (a `None`/absent
    description), which the caller handles before ever calling the parser."""


# "axis in range(a,b[,step])" or "axis in [v1, v2, ...]"; axes joined by " x ".
_RANGE_RE = re.compile(r"^range\(\s*(-?\d+)\s*,\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?\)$")


def parse_grid_geometry(param_grid_description) -> dict[str, list[int]]:
    """THE documented legacy-string grid parser (§4.2), kept in one place with
    `_grid_axes`. Parses e.g. "fast in range(5,55,5) x slow in range(60,200,5)"
    into `{"fast": [5,10,…,50], "slow": [60,65,…,195]}` — each axis a sorted list
    of the integer grid points along it.

    Strictness is deliberate: any segment that is not `<axis> in <range()/[list]>`
    of integers raises `GridUnparseable` rather than yielding a half-guessed
    geometry. Axes are split on " x " (space-delimited) so an axis name containing
    the letter x does not fracture. The structured `param_grid` sidecar (for new
    searches) is preferred by the caller when present; this parser is the fallback
    for legacy string descriptions."""
    if not param_grid_description or not str(param_grid_description).strip():
        raise GridUnparseable("empty/absent param_grid_description")
    geometry: dict[str, list[int]] = {}
    for part in str(param_grid_description).split(" x "):
        token = part.strip()
        if not token:
            raise GridUnparseable(f"empty grid segment in {param_grid_description!r}")
        name, sep, spec = token.partition(" in ")
        if not sep or not name.strip():
            raise GridUnparseable(f"segment is not '<axis> in <spec>': {token!r}")
        axis = name.strip()
        if axis in geometry:
            raise GridUnparseable(f"duplicate axis {axis!r}")
        geometry[axis] = _parse_axis_values(spec.strip())
    if not geometry:
        raise GridUnparseable(f"no axes parsed from {param_grid_description!r}")
    return geometry


def _parse_axis_values(spec: str) -> list[int]:
    """One axis's integer grid points from a `range(a,b[,step])` or `[v1,v2,…]`
    spec. Any deviation → GridUnparseable."""
    m = _RANGE_RE.match(spec)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        step = int(m.group(3)) if m.group(3) is not None else 1
        if step == 0:
            raise GridUnparseable(f"range step is 0 in {spec!r}")
        values = list(range(a, b, step))
        if not values:
            raise GridUnparseable(f"empty range {spec!r}")
        return sorted(values)
    if spec.startswith("[") and spec.endswith("]"):
        inner = spec[1:-1].strip()
        if not inner:
            raise GridUnparseable(f"empty value list {spec!r}")
        try:
            return sorted(int(tok.strip()) for tok in inner.split(","))
        except ValueError as exc:
            raise GridUnparseable(f"non-integer value in list {spec!r}") from exc
    raise GridUnparseable(f"unrecognized axis spec {spec!r}")


class Eligibility:
    """Stage 4.0. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        evidence: dict = {}

        # (a) completeness — five coordinates, returns length, hypothesis link.
        missing = self._completeness_failures(result)
        if missing:
            evidence["completeness_failures"] = missing
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        # (b) unsafe flags → NON_PROMOTABLE, terminal (probe G8).
        unsafe = [w for w in result.warnings if _UNSAFE_FLAG in w]
        if unsafe:
            evidence[TERMINAL_STATUS_KEY] = NON_PROMOTABLE
            evidence["unsafe_warnings"] = unsafe
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        # (c) provisional-cost flag → record the signal only. Its consumer is stage
        #     4.5 (a later phase), which reads result.warnings directly; 4.0 does
        #     NOT thread mutable state through ctx for a stage that doesn't exist yet.
        provisional = [w for w in result.warnings if _PROVISIONAL_FLAG in w]
        evidence["provisional_cost_constants"] = bool(provisional)

        # (d) data-quality warnings copied into evidence (everything not already
        #     categorised above).
        evidence["warnings"] = list(result.warnings)

        # (e) breadth — completed round trips vs the configured minimum.
        round_trips = reconstruct_round_trips(result.trades)
        n_round_trips = len(round_trips)
        min_round_trips = ctx.config.thresholds[_MIN_ROUND_TRIPS_KEY]
        evidence["round_trips"] = n_round_trips
        evidence["min_round_trips"] = min_round_trips

        # (f) search-fragmentation screen (warn-only) — runs regardless of breadth
        #     so the record carries it even on an INSUFFICIENT_BREADTH exit.
        self._fragmentation_screen(result, ctx, evidence)

        if n_round_trips < min_round_trips:
            evidence[TERMINAL_STATUS_KEY] = INSUFFICIENT_BREADTH
            return TestOutcome(moira_id=self.moira_id, passed=False, score=float(n_round_trips),
                               evidence=evidence)

        return TestOutcome(moira_id=self.moira_id, passed=True,
                           score=float(n_round_trips), evidence=evidence)

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _completeness_failures(result: BacktestResult) -> list[str]:
        failures = []
        for coord in ("run_id", "core_version", "config_hash", "data_snapshot_hash"):
            if not getattr(result, coord):
                failures.append(f"missing coordinate: {coord}")
        if result.seed is None:
            failures.append("missing coordinate: seed")
        if not result.hypothesis_id:
            failures.append("missing hypothesis link")
        if len(result.returns) != result.bars_processed:
            failures.append(
                f"returns length {len(result.returns)} != bars_processed "
                f"{result.bars_processed}"
            )
        return failures

    def _fragmentation_screen(self, result, ctx, evidence: dict) -> None:
        """Scan the store for sibling hypotheses (same grid axes, registered within
        the window). If found, stamp `possible_search_fragmentation` with the
        sibling ids and the UNION N. Warn-only — never a gate (§4.0)."""
        records = ctx.store.read_all()
        hypotheses = {}
        for r in records:
            if r.get("type") == "hypothesis":
                # Last registration of an id wins (append-only; ids are stable).
                hypotheses[r["hypothesis"]["id"]] = r

        candidate = hypotheses.get(result.hypothesis_id)
        if candidate is None:
            evidence["fragmentation_screen"] = "skipped: candidate hypothesis not in store"
            return
        candidate_axes = _grid_axes(candidate["hypothesis"].get("param_grid_description"))
        if not candidate_axes:
            evidence["fragmentation_screen"] = "skipped: candidate has no param_grid_description"
            return

        window_days = ctx.config.thresholds[_FRAGMENTATION_WINDOW_KEY]
        candidate_time = _parse_time(candidate.get("registered_at"))
        siblings = []
        for hyp_id, rec in hypotheses.items():
            if hyp_id == result.hypothesis_id:
                continue
            axes = _grid_axes(rec["hypothesis"].get("param_grid_description"))
            if axes != candidate_axes:
                continue
            other_time = _parse_time(rec.get("registered_at"))
            if candidate_time is not None and other_time is not None:
                if abs(other_time - candidate_time) > timedelta(days=window_days):
                    continue
            siblings.append(hyp_id)

        if not siblings:
            evidence["fragmentation_screen"] = "no siblings found"
            return

        union_ids = {result.hypothesis_id, *siblings}
        union_n = sum(
            1 for r in records
            if r.get("type") == "run" and r.get("kind") == "SEARCH"
            and r.get("hypothesis_id") in union_ids
        )
        evidence["possible_search_fragmentation"] = {
            "sibling_ids": sorted(siblings),
            "union_n": union_n,
            "shared_axes": sorted(candidate_axes),
        }


def _parse_time(iso: str | None):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None
