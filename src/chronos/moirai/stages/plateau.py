"""plateau.py — stage 4.2, Parameter plateau & the finalization of N (spec §4.2).

The selected parameter point must sit on a broad performance plateau, not a lonely
spike. Take the candidate's immediate neighborhood (axis-aligned ±1…±`plateau.steps`
grid steps per tunable parameter, from the grid geometry in
`param_grid_description`). For every neighbor **already present in the store as a
SEARCH record of this hypothesis**, read its per-bar Sharpe free. For any neighbor
*not* yet run, running it now is **new search**, executed `kind=SEARCH` under the
same hypothesis — **N increases, and that is the point** (spec forbids optimizing
this away). This is the ONLY stage permitted to add SEARCH runs.

**After this stage runs, N is frozen for the verdict:** `ctx.freeze_search()` is
called on EVERY exit path of `evaluate` (pass, fail, grid-unparseable, no-grid),
because 4.2 is the N-finalization stage — no later stage may spend SEARCH budget
regardless of 4.2's verdict. `ctx.run(kind=SEARCH)` raises `SearchFrozenError`
thereafter (probe G6b).

Pass: median neighbor Sharpe ≥ `plateau.median_frac` × candidate Sharpe, AND no more
than `plateau.max_cliff` of neighbors have a negative Sharpe while the candidate's
is positive.

Ambiguity is never guessed (§4.2, CLAUDE.md rule 8):
  - grid geometry unparseable, or the candidate is not located on its own grid →
    `executed: true, passed: false`, reason `grid_unparseable`.
  - NO `param_grid_description` at all (a genuinely pre-registered single point,
    e.g. the milestone) → there is no neighborhood to check. This is DISTINCT from
    `grid_unparseable`. Founder-approved semantics (2026-07-31):
      * no countable SEARCH breadth (`compute_search_n == 0`) and no grid-bearing
        fragmentation siblings → PASS, reason `no_neighborhood_defined`, with a note
        that states plainly there is no search breadth to deflate — never implying
        the point is exempt/blessed.
      * BUT if the store shows `kind=SEARCH` breadth under this hypothesis, or a
        grid-bearing fragmentation sibling → FAIL, reason `undeclared_search_breadth`
        (a searched point wearing a pre-registered label). This trigger fires ONLY on
        `kind=SEARCH` or grid-bearing siblings — never on legacy `kind=None` records
        (which `compute_search_n` already excludes by construction).
"""

import numpy as np

from chronos.hephaestus.types import BacktestResult
from chronos.moirai import statistics as stats
from chronos.moirai.context import GauntletContext
from chronos.moirai.stages.eligibility import (
    GridUnparseable,
    _grid_axes,
    parse_grid_geometry,
)
from chronos.moirai.types import TestOutcome
from chronos.run import RunKind, compute_search_n

MOIRA_ID = "M4.2-plateau"

_MEDIAN_FRAC_KEY = "plateau.median_frac"
_MAX_CLIFF_KEY = "plateau.max_cliff"          # spec name: plateau.max_cliff_frac (v002 reconciliation)
_STEPS_KEY = "plateau.steps"                  # spec name: plateau.neighborhood_steps (v002 reconciliation)

_NO_NEIGHBORHOOD_NOTE = (
    "no param_grid_description on this hypothesis: a genuinely pre-registered single "
    "point with no neighborhood to check. No countable SEARCH breadth "
    "(compute_search_n == 0); the legacy sweep, if any, is kind=None and excluded by "
    "construction, re-established under kind=SEARCH in Phase 7. This is NOT a blessing "
    "or exemption — there is simply no search breadth here to deflate against."
)


class Plateau:
    """Stage 4.2. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        try:
            return self._evaluate(result, ctx)
        finally:
            # 4.2 is the N-finalization stage: freeze on EVERY exit path so no later
            # stage can spend SEARCH budget, whatever 4.2's verdict was.
            ctx.freeze_search()

    def _evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.2 needs ctx.candidate (strategy + base config + hypothesis) "
                "to evaluate the plateau and run neighbors; none was provided."
            )
        hyp = ctx.candidate.hypothesis
        base_config = ctx.candidate.base_config
        cand_sr = stats.per_bar_sharpe(_returns_list(result.returns))

        evidence: dict = {
            "candidate_sharpe": cand_sr,
            "median_frac": ctx.config.thresholds[_MEDIAN_FRAC_KEY],
            "max_cliff": ctx.config.thresholds[_MAX_CLIFF_KEY],
            "steps": ctx.config.thresholds[_STEPS_KEY],
        }

        grid_desc = hyp.param_grid_description

        # --- Branch: NO grid (pre-registered single point) --------------------
        if not grid_desc or not str(grid_desc).strip():
            return self._no_grid(result, ctx, evidence)

        # --- Branch: parse the grid geometry (never guess) --------------------
        try:
            geometry = parse_grid_geometry(grid_desc)
        except GridUnparseable as exc:
            evidence["reason"] = "grid_unparseable"
            evidence["grid_unparseable_detail"] = str(exc)
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        base_params = dict(base_config.strategy_params)
        off_grid = self._candidate_off_grid(geometry, base_params)
        if off_grid is not None:
            evidence["reason"] = "grid_unparseable"
            evidence["grid_unparseable_detail"] = off_grid
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        return self._plateau(result, ctx, geometry, base_params, cand_sr,
                             evidence)

    # -- no-grid branch ---------------------------------------------------------

    def _no_grid(self, result, ctx, evidence) -> TestOutcome:
        raw_n = compute_search_n(result.hypothesis_id, ctx.store)
        grid_siblings = self._grid_bearing_siblings(result, ctx)
        evidence["search_n_at_4.2"] = raw_n
        evidence["grid_bearing_siblings"] = sorted(grid_siblings)

        # Trigger ONLY on kind=SEARCH breadth or grid-bearing siblings; legacy
        # kind=None is already excluded by compute_search_n (founder condition b).
        if raw_n > 0 or grid_siblings:
            evidence["reason"] = "undeclared_search_breadth"
            evidence["undeclared_note"] = (
                "no param_grid_description, yet the store carries search breadth for "
                f"this hypothesis (compute_search_n={raw_n}, grid-bearing siblings="
                f"{sorted(grid_siblings)}). A searched point wearing a pre-registered "
                "label — flagged, not free-passed.")
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        evidence["reason"] = "no_neighborhood_defined"
        evidence["no_neighborhood_note"] = _NO_NEIGHBORHOOD_NOTE
        return TestOutcome(moira_id=self.moira_id, passed=True, score=0.0,
                           evidence=evidence)

    @staticmethod
    def _grid_bearing_siblings(result, ctx) -> set:
        """Other hypotheses that share this candidate's (non-empty) grid axes — the
        same match 4.0's fragmentation screen makes. Empty for a no-grid candidate
        (∅ axes match nothing), so this only ever fires for a candidate that itself
        carries a grid; kept for completeness and to honor the founder's second
        trigger explicitly."""
        records = ctx.store.read_all()
        hypotheses = {r["hypothesis"]["id"]: r for r in records
                      if r.get("type") == "hypothesis"}
        candidate = hypotheses.get(result.hypothesis_id)
        if candidate is None:
            return set()
        candidate_axes = _grid_axes(candidate["hypothesis"].get("param_grid_description"))
        if not candidate_axes:
            return set()
        return {
            hid for hid, rec in hypotheses.items()
            if hid != result.hypothesis_id
            and _grid_axes(rec["hypothesis"].get("param_grid_description")) == candidate_axes
        }

    # -- plateau branch ---------------------------------------------------------

    @staticmethod
    def _candidate_off_grid(geometry, base_params):
        """None if the candidate's params locate it on the grid; else a reason
        string (an ambiguity → grid_unparseable, never guessed)."""
        for axis, values in geometry.items():
            if axis not in base_params:
                return f"candidate missing grid axis {axis!r} in strategy_params"
            try:
                cand_val = int(base_params[axis])
            except (TypeError, ValueError):
                return f"candidate axis {axis!r}={base_params[axis]!r} is not an integer"
            if cand_val not in values:
                return f"candidate {axis!r}={cand_val} not on parsed grid {values}"
        return None

    def _plateau(self, result, ctx, geometry, base_params, cand_sr,
                 evidence) -> TestOutcome:
        steps = int(ctx.config.thresholds[_STEPS_KEY])
        neighbors = _neighbor_points(geometry, base_params, steps)
        axes = list(geometry.keys())
        stored = _stored_search_sharpes(ctx.store, result.hypothesis_id, axes)

        sharpes: list[float] = []
        ran, read_free, errored = [], [], []
        for point in neighbors:
            key = tuple(int(point[a]) for a in axes)
            if key in stored:
                sharpes.append(stored[key])
                read_free.append(key)
                continue
            # Not yet run → run it now as SEARCH (N increases — the point of 4.2).
            neighbor_config = _with_params(ctx.candidate.base_config, point)
            try:
                record = ctx.run(kind=RunKind.SEARCH, config=neighbor_config,
                                 strategy=ctx.candidate.strategy,
                                 hypothesis=ctx.candidate.hypothesis)
            except Exception as exc:  # structurally-invalid neighbor for this strategy
                errored.append({"point": key, "error": f"{type(exc).__name__}: {exc}"})
                continue
            sharpes.append(stats.per_bar_sharpe(_returns_list(record.result.returns)))
            ran.append(key)

        evidence.update({
            "n_neighbors": len(neighbors),
            "neighbors_read_free": [list(k) for k in read_free],
            "neighbors_run_as_search": [list(k) for k in ran],
            "neighbors_errored": errored,
            "neighbor_sharpes": sharpes,
        })

        if not sharpes:
            evidence["reason"] = "no_evaluable_neighbors"
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        arr = np.asarray(sharpes, float)
        median_neighbor = float(np.median(arr))
        median_frac = ctx.config.thresholds[_MEDIAN_FRAC_KEY]
        max_cliff = ctx.config.thresholds[_MAX_CLIFF_KEY]

        median_ok = median_neighbor >= median_frac * cand_sr
        neg_frac = float(np.mean(arr < 0.0))
        # Cliff clause only bites when the candidate is actually positive (§4.2).
        cliff_ok = True if cand_sr <= 0.0 else (neg_frac <= max_cliff)

        evidence.update({
            "median_neighbor_sharpe": median_neighbor,
            "median_threshold": median_frac * cand_sr,
            "median_ok": median_ok,
            "neighbor_negative_fraction": neg_frac,
            "cliff_ok": cliff_ok,
        })
        if cand_sr <= 0.0:
            evidence["candidate_nonpositive_note"] = (
                "candidate per-bar Sharpe ≤ 0: the median_frac criterion is ill-posed "
                "for a non-positive candidate and the cliff clause is vacuous (its "
                "'while candidate>0' guard fails). 4.2 checks plateau SHAPE, not "
                "profitability — 4.3 is the profitability/selection-bias gate.")

        passed = bool(median_ok and cliff_ok)
        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=median_neighbor, evidence=evidence)


# --- module helpers ------------------------------------------------------------

def _returns_list(returns) -> list:
    if hasattr(returns, "to_list"):
        return returns.to_list()
    return list(returns)


def _neighbor_points(geometry, base_params, steps) -> list:
    """Axis-aligned ±1…±`steps` grid-step neighbors: for each axis, hold every other
    param at the candidate value and step that axis, clipped at the grid edges. Each
    neighbor differs from the candidate in exactly one axis."""
    neighbors = []
    for axis, values in geometry.items():
        idx = values.index(int(base_params[axis]))
        for delta in range(-steps, steps + 1):
            if delta == 0:
                continue
            j = idx + delta
            if 0 <= j < len(values):
                point = dict(base_params)
                point[axis] = values[j]
                neighbors.append(point)
    return neighbors


def _with_params(base_config, point):
    from dataclasses import replace
    return replace(base_config, strategy_params=dict(point))


def _stored_search_sharpes(store, hypothesis_id, axes) -> dict:
    """Map {grid-axis value tuple → per-bar Sharpe} for existing SEARCH records of
    this hypothesis — the SAME kind/hypothesis filter compute_search_n uses. Legacy
    kind=None records never match (no 'kind' key), so they are excluded, exactly as N
    is. If a point recurs, the last COMPLETED record wins."""
    out: dict = {}
    for r in store.read_all():
        if r.get("type") != "run" or r.get("kind") != RunKind.SEARCH.value:
            continue
        if r.get("hypothesis_id") != hypothesis_id:
            continue
        res = r.get("result")
        if not res:
            continue
        params = (r.get("config") or {}).get("strategy_params") or {}
        try:
            key = tuple(int(params[a]) for a in axes)
        except (KeyError, TypeError, ValueError):
            continue  # a SEARCH record that doesn't carry these axes — not a neighbor
        series = [v for _, v in res.get("returns", [])]
        if series:
            out[key] = stats.per_bar_sharpe(series)
    return out
