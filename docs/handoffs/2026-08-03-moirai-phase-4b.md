# Closing handoff — Moirai Phase 4b (signal null 4.1, plateau 4.2, N finalization, probe G6)

**Date:** 2026-08-03 (brief drafted 2026-07-30; work done today) · **Model:** Opus ·
**Protected paths touched:** `moirai/`, `tests/moirai/`, `tests/statistics/` (full
diff shown, founder-approved before commit). **Tests: 234 → 258, all green.**

---

## What landed

The two stages with genuinely new machinery — the first re-run stages of the gauntlet:

| moira_id (byte-matches v001 `pipeline_order`) | file | gate |
|---|---|---|
| `M4.1-signal-null` | `moirai/stages/signal_null.py` | one-sided bootstrap p ≤ `null_signal.alpha` |
| `M4.2-plateau` | `moirai/stages/plateau.py` | plateau (median + cliff); the ONLY stage that spends N, then freezes it |

Supporting:
- `statistics.block_p_from_returns` — the D-R5-p mean block length (pure math on
  `circ_autocov`; pinned by `tests/statistics/test_block_p.py`).
- `context.Candidate` (strategy + base config + hypothesis) carried on
  `GauntletContext`; `ctx.search_frozen` read-only property; optional `candidate=` on
  both context builders — the channel every re-run stage consumes.
- `eligibility.parse_grid_geometry` + `GridUnparseable` — THE documented grid parser,
  kept beside `_grid_axes`.
- `pipeline.run_gauntlet` — resolves the verdict's frozen N post-loop and enforces the
  `VerdictNMismatch` divergence invariant; `search_n` is now an optional override.
- `deflated_sharpe` (4.3) — stamps `n_frozen = ctx.search_frozen`; deflation-note
  wording made conditional on the freeze state.
- Probe **G6** (`tests/moirai/test_plateau.py`): a fragmentation union-N, b SEARCH
  refused after 4.2, c neighbor run ⇒ N+1 ⇒ 4.3 reads FROZEN N ⇒ SR* strictly up.

## The four pre-code resolutions (done in the repo, not from memory)

1. **v001 key binding.** Bound every threshold to v001's ACTUAL key names. Found a
   FOURTH drift beyond the three known: spec `null_signal.p_block` → v001
   `bootstrap_p.formula` (`"autocov_procedure"`). Nominal only — v001 carries no
   numeric p; D-R5-p computes p per window. Full v002 reconciliation list is in the
   dated HANDOFF.md entry.
2. **`_DecisionRecorder` pattern.** The real Strategy method IS `on_bar(view, ctx) ->
   list[Order]` and `_DecisionRecorder` wraps it exactly as the spec's shorthand
   describes — no divergence; `SignalCapture` copies it and returns `[]`.
3. **How 4.3 learns N is frozen.** The clean path: 4.2 runs neighbors then
   `ctx.freeze_search()`; 4.3 reads `compute_search_n` LIVE (stable post-freeze,
   since `ctx.run` refuses SEARCH) and stamps `n_frozen = ctx.search_frozen`. No
   cached frozen-N field.
4. **Bootstrap primitives consumed, not reimplemented.** `stationary_bootstrap_indices`
   / `circ_autocov` are consumed; no bootstrap logic in a Moira.

## Two founder decisions taken this phase (2026-08-03)

- **No-grid 4.2 semantics (Option 1 + two conditions).** No grid + no `kind=SEARCH`
  breadth + no grid-bearing sibling → PASS `no_neighborhood_defined` (note never
  implies exemption). No grid + SEARCH breadth or grid-bearing sibling → FAIL
  `undeclared_search_breadth`. Trigger fires only on `kind=SEARCH`/grid-bearing
  siblings, never legacy `kind=None`. Empirically confirmed the milestone takes the
  PASS branch.
- **Verdict N finalization.** `run_gauntlet` recomputes the frozen N post-loop and
  raises `VerdictNMismatch` if the verdict N, 4.3's `search_n_raw`, and post-freeze
  `compute_search_n` ever disagree. `n_frozen` is False on a short-circuit before 4.2.

## One scoped deviation (founder-approved)

The structured `param_grid` sidecar (a `Hypothesis`/Mnemosyne schema field) is
**deferred to Phase 7**, landing with the live sweep re-run — when new `kind=SEARCH`
records first make stringly-parsing a live risk. Until then `parse_grid_geometry` is
THE grid parser and ambiguous geometry returns `grid_unparseable`, never a guess.

## A real bug fixed (worth reading)

4.1's first null was CONSERVATIVE (empirical rejection ≈0.005 at α=0.05, 10× too few)
because it pre-detrended once then resampled — over-dispersing the bootstrap θ vs θ̂'s
mean-constrained variance. Fix: detrend INSIDE the statistic so every replicate carries
the identical constraint → rejection ≈ α (0.063/300 reps; the CI test asserts ≈α over
200 seeded reps ±2σ). Same pass fixed a `np.diff` START-indexing off-by-one (signal
`s_j` pairs `forward_returns[j]`, not `[j+1]`).

## Checkpoints (real output)

1. **4.1 on the milestone (#285):** p = **0.1045** > α → fails the pre-cost signal
   gate; bracket {0.103, 0.122} stable; `block_p=1.0` verified genuine (BTC hourly acf
   inside the band). Unremarkable, as predicted.
2. **Synthetic 4.2→4.3:** N 3→4 (exactly +1), freeze fired, 4.3 read frozen N=4,
   `n_frozen: true`, SR* 0.457→0.564, `verdict.search_n=4` (invariant held).

Numbers in `SESSION_FINDINGS.md`.

## For Phase 4c (next session)

The re-run gates 4.5–4.10, all consuming the `Candidate` bundle via
`ctx.run(kind=VERIFICATION)` (SEARCH is frozen after 4.2). 4.9's ~200-null full-engine
benchmark is where the Phase 6 calibration-budget open item bites. The
throughput/budget decision (STATE.md "Blocking") is still the one genuinely open item.
