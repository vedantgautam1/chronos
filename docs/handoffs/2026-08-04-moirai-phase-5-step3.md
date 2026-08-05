# Closing handoff — Moirai Phase 5 Step 3.0 + T-e escalation (touchstones deferred, built together next)

**Date:** 2026-08-04 · **Model:** Opus · **Committed:** `36f000f` (Step 3.0). No touchstone
code written — T-e's framing is DECIDED but unbuilt; all five touchstones build together next
session. Suite green at **311**. HEAD == origin/main.

---

## Done this session

**Step 3.0 (committed + pushed, `36f000f`).**
- **L1 provenance pin:** `generator.provenance()` → `synthetic:v1@7c0b19aa` (generator version
  + the Oceanus snapshot the volume constants m=7.189/s=1.169 were measured from).
- **L2 ambient-coupling audit:** only `test_descriptive` was materially coupled (200d-MA +
  cross-asset availability depend on coverage EXTENT) — fixed last session (hermetic
  `available_range` monkeypatch, all 5 tests confirmed hermetic). Everything else is hermetic
  (all `get_bars` test sites pass `root=tmp` + a fake exchange; `test_shift` monkeypatches
  `available_range`) or value-stable. **Value-stability VERIFIED BY HASH:** the 2026 dev window
  is byte-identical `fe8be146d37544d7` (4344 bars) across parquet v0004/v0005/v0006 — the
  Step-1 ingest appended pre-2026 history and extended the tail to 2026-08-03 only, restating no
  2026 bar. So `test_milestone`/`run_experiment` sites reading the real default store are safe.

**T-e escalation resolved (FOUNDER, 2026-08-04) — framing A, decided-but-UNBUILT.**
Three live values (shipped `statistics.py` dsr + active `dsr.confidence`, legacy 280-sweep
winner fast=25/slow=60, trial 117, sr_hat=0.0024061, T=4344, V=8.6596e-05, skew 0.720,
kurt 16.84 — reproduces the historical 0.563/0.054):

| DSR @ N=1 | dsr.confidence | DSR @ N=280 |
|---|---|---|
| **0.5630** | **0.95** | **0.0542** |

**§6 chained form is a CONFIRMED v002 spec defect:** `DSR@N=1 > dsr.confidence > DSR@N=280`
needs `0.5630 > 0.95` — impossible on the real winner. **T-e pins framing A instead:**
`DSR@N=1 (0.5630) > DSR@N=280 (0.0542) AND DSR@N=280 (0.0542) < dsr.confidence (0.95)`.

---

## Next session — build ALL FIVE touchstones together, then Step 4, then Step 5

Baseline to re-confirm first: commits `36f1ff1`/`c15705e`/`36f000f`, HEAD==origin, suite green
311, GATE A + T-e-framing-A in committed STATE/HANDOFF. Bind to v001's ACTUAL keys (drift table
in HANDOFF: `plateau.max_cliff`, `plateau.steps`, `null_signal.B`, `mc_shuffle.luck_threshold`,
etc.). NO verdict-fitting: seed/window/params chosen a priori and pinned; a non-matching verdict
is a FINDING to surface, never a cue to shop seeds.

Touchstone contract (§6): each `build(seed) -> (data, Strategy)` deterministic; immutable
pre-registered verdict + written rationale beside the code; CI-required (any flip fails CI);
runs execute through the Step-2 `CalibrationHarness` ISOLATED store (`moirai/calibration/
harness.py` — `run_synthetic(strategy, frame, hypothesis, kind, symbol=, strategy_params=)`);
total CI runtime ≤10 min (short synthetic windows via `generator.generate_frame`). Judge a
touchstone by: generate data → `harness.run_synthetic` for the base result → build a
`GauntletContext` with `candidate=Candidate(strategy, config, hypothesis)` and the full 11-stage
REGISTRY → `run_gauntlet(result, REGISTRY, ctx)`. (The Phase-4c checkpoint script
`scripts/moirai_phase4c_checkpoint.py` is the working reference for wiring the full pipeline.)

- **T-a** should-PASS: synthetic S=3.0 (above the ~2.3 floor), MA strategy that captures it →
  PASS. Pick n_bars a priori large enough to detect S=3.0, small enough for budget; pin it.
- **T-b** should-DIE (GATE A applies — the careful one). 8-param rule curve-fit to noise; register
  the grid as SEARCH-kind records in the isolated store so `compute_search_n()` returns the honest
  N (verify N reflects the grid, not 1). **RUN in full-eval, print the per-stage 4.2/4.3/4.8
  table, report to founder; then pin short-circuit `cause_of_death ∈ {4.2, 4.3}` (NOT
  {4.2,4.3,4.8}, NOT bare FAIL). If 4.2 AND 4.3 both PASS and death is via 4.8/downstream, STOP
  and surface (the overfit gates aren't catching an overfit they should).** Docstring verbatim:
  "Stage 4.8 form unratified per 2026-08-04; touchstones must not assert on 4.8 until v002."
- **T-c** should-DIE via safety: future leak through the sanctioned `unsafe_same_bar_fill`
  flag-gated fixture (do NOT touch I1) → NON_PROMOTABLE, terminal at 4.0.
- **T-d** null baseline: seeded random strategy → FAIL, AND 4.9 self-percentile ∈ [0.2, 0.8].
  **Run and print the actual percentile before pinning; if outside [0.2,0.8], surface it (null
  machinery mis-calibrated), do NOT reseed to fit.**
- **T-e** laundering demo: **framing A is DECIDED** — assert `DSR@N=1 (0.5630) > DSR@N=280
  (0.0542) AND DSR@N=280 < dsr.confidence (0.95)`. Do NOT write the §6 chained form. Add a
  comment at the T-e site recording the §6 chained-form defect + the three live values +
  "impossible on the real winner." Runs against LEGACY records until Phase 7 re-runs the sweep
  live — mark that dependency in the docstring. (Ingredients confirmed present:
  `records/runs.jsonl` trials 5–284; V=8.6596e-05; winner fast=25/slow=60.)

**FOUNDER CHECKPOINT before pinning any verdict:** report T-b's full-eval table, T-d's percentile,
and re-confirm T-e's framing; wait for ack. Then commit (all five, as `feat(moirai): touchstones
T-a..T-e (Phase 5 Step 3)`).

- **Step 4 — Mode S** (only if context holds): statistics-level, no engine; reproduce the probe's
  Monte Carlo — detection ≈0.3% at S=1.0 after a 280-wide search (±0.5pp), ~40–50% pre-registered
  (±10pp), floor ≈2.3 (±0.2). Divergence = stop-the-build.
- **Step 5 — GATE C** (Phase 6 budget): present the three throughput numbers (a=28.2s, b=48.1s,
  c=39.8min; null cadence median 8.96s) + Mode S; founder picks A (split modes) / B (reduced
  n_nulls), sized against the ~9 s null cadence and 28.2 s per-run — NOT 0.566 s. C rejected
  (biases V, which shrinks with T). Append the decision to HANDOFF before Phase 6.
