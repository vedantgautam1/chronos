# Closing handoff — Moirai Phase 5 Step 3 (T-a built & split; verdicts DEFERRED); T-b…T-e next

**Date:** 2026-08-06 · **Model:** Opus · **Tests:** 311 green (no new CI assertions — T-a1/T-a2
are DEFERRED). Committed this session. **T-b, T-c, T-d, T-e build in a fresh session** (the
die/reject cases — threshold-robust, pinnable now).

---

## What landed

- `moirai/calibration/touchstones.py` — the touchstone judge harness (`judge()`: runs a synthetic
  candidate through the full eleven-stage gauntlet in the Step-2 ISOLATED store, serving synthetic
  candles via a synthetic `exchange=` into an isolated data root, with the test-time
  `available_range` monkeypatch for 4.7/4.10; reduced touchstone `null_bench.n_nulls`=40 via a
  dev-config override, v001 untouched). Plus `build_t_a1()` and `build_t_a2()`.
- `moirai/calibration/generator.py` — `generate_regime_frame()` (2-state bull/bear Markov regime
  switch) + `regime_drift_schedule()` + `_assemble_frame()` refactor (shared with `generate_frame`);
  and the L1 provenance pin (`provenance()` → `synthetic:v1@7c0b19aa`).

## T-a: front-loaded, run honestly ~6×, SPLIT — verdicts DEFERRED (BLOCKED-ON-PHASE-6-CALIBRATION)

Two a-priori rules discovered and pinned (NOT tuned):
- **SNR rule** — a regime edge is timeable only if `L_bars ≥ 8760/S²` (regime move ≥ within-regime
  noise). A 21-day/S=3 regime is noise-dominated (SNR 0.72).
- **MA timescale rule** — slow = regime half-life in hours, fast = slow/4.

| | fixture | 11-stage result |
|---|---|---|
| **T-a1** | S=±3, 45-day regimes, σ=0.60, MA 270/1080h | edge gates 4.1/4.3/4.4/4.5/4.9 PASS; **4.0** (10 trips, INSUFFICIENT_BREADTH) + **4.8** FAIL |
| **T-a2** | S=±6, 12-day regimes, σ=0.60, MA 72/288h | breadth clears (47 trips) + 4.1/4.3/4.5/4.6/4.7/4.9 PASS; **4.4** (maxDD 0.535 > 0.40) + **4.8** FAIL |

Both verdicts are **PASS_DEFERRED — neither PASS nor FAIL** (scoping a PASS would rig the canary;
FAIL would slander a real edge). Recorded in three places: the `PASS_DEFERRED` sentinel
(`touchstones.py`), the §6 amendment (`SPEC_MOIRAI.md`), and STATE.

## Meta-finding — the Phase-6 PRECONDITION for pinning T-a1/T-a2

Under provisional §14, **no honest strategy clears all eleven gates.** `min_round_trips`=30 (4.0)
and the subperiod gate (4.8) encode a hidden high-frequency assumption; `ruin_dd`=0.40 vs σ=0.60
(4.4) is exposure-dependent. Mutually tensioned (T-a1 trips 4.0/4.8; T-a2 trips 4.4/4.8). Phase-6
calibration MUST reconcile `min_round_trips`/`subperiod`/`ruin_dd` before the should-PASS canaries
pin. (SESSION_FINDINGS 2026-08-06.)

---

## Next session — build T-b, T-c, T-d, T-e (opening move)

Opening guard: read committed STATE + newest HANDOFF + this handoff + SPEC §6 (amended) / §7;
confirm HEAD==origin, suite green (311); confirm T-a1/T-a2 are DEFERRED (do NOT try to pin/PASS
them). Bind to v001's ACTUAL keys. Then build the four die/reject cases through
`touchstones.judge(...)` (isolated harness, ≈40 nulls, ≤10-min set budget):

- **T-b — should-DIE (GATE A).** 8-param rule curve-fit to seeded noise; register the grid as
  SEARCH-kind records in the isolated store so `compute_search_n()` returns honest N (verify N
  reflects the grid, not 1) and 4.3 charges it. Run FULL-EVAL, PRINT the per-stage table (esp.
  4.2/4.3/4.8). Pin `cause_of_death ∈ {4.2, 4.3}` — NOT {4.2,4.3,4.8}, NOT bare FAIL.
  STOP-AND-SURFACE if 4.2 AND 4.3 both PASS and death is via 4.8/downstream. Docstring verbatim:
  "Stage 4.8 form unratified per 2026-08-04; touchstones must not assert on 4.8 until v002
  calibration."
- **T-c — should-DIE via safety.** `unsafe_same_bar_fill` flag-gated fixture (do NOT touch I1) →
  NON_PROMOTABLE, terminal at 4.0. Cheap (short-circuits at 4.0). Short frame, no nulls.
- **T-d — null baseline.** Seeded random strategy → FAIL, AND 4.9 self-percentile ∈ [0.2, 0.8].
  Run FULL-EVAL (to reach 4.9), PRINT the actual percentile before pinning; if outside the band,
  surface it — do not reseed to fit.
- **T-e — laundering demo (framing A).** Build from a COMMITTED provenance-stamped fixture
  (winner returns + V=8.6596e-05, cell fast=25/slow=60 = trial 117, snapshot 7c0b19aa,
  extract-once regeneration note) — NOT `records/runs.jsonl` (gitignored, 119 MB). Assert
  `DSR@N=1 (0.5630) > DSR@N=280 (0.0542) AND DSR@N=280 < dsr.confidence (0.95)`. Do NOT write the
  §6 chained form (`DSR@N=1 > dsr.confidence > DSR@N=280` — confirmed v002 defect; 0.5630 !> 0.95);
  add that as a code comment at the T-e site. Docstring notes the Phase-7 live-sweep dependency.

Founder checkpoint before pinning any verdict: report T-b's table + T-d's percentile + T-e's
reproduced values, wait for ack. Then Step 4 (Mode S reconciliation) and Step 5 (GATE C —
budget A/B, sized against ~9 s null cadence / 28.2 s per-run, NOT 0.566 s).

**Budget note (fork 2):** with T-a1/T-a2 DEFERRED (not CI-run), the CI set is T-b (short-circuit
~15 s) + T-c (~5 s) + T-d (full-eval ~60 s) + T-e (stats <1 s) ≈ well under 10 min. If T-a1/T-a2
are later added to CI as regression runs (post-Phase-6), re-check the budget then.
