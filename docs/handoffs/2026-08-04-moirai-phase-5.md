# Closing handoff — Moirai Phase 5 (Steps 1–2 done; Steps 3–5 for the next session)

**Date:** 2026-08-04 · **Model:** Opus · **Commits:** `36f1ff1` (Step 1 throughput),
`c15705e` (Step 2 generator + quarantine + G5, WIP checkpoint — explicitly NOT the bundled
Phase 5 commit). **Tests: 311 green.** This session did Steps 1–2 and took FOUNDER GATE A;
Steps 3 (touchstones), 4 (Mode S), and 5 (GATE C) remain.

---

## Step 1 — throughput on the canonical window (DONE, committed `36f1ff1`)

The canonical full-history window was NOT on disk (only 188 days). With founder approval it
was ingested: **BTC/USDT H1, 2017-08-17 → 2026-08-03, 78,444 bars**, Oceanus snapshot
`7c0b19aa91b9b662d9c7a3623b6aae8947ea9d8a0b1f7e80bcfe814e52e551c2`, 28 pre-2023 gap windows
(128 bars; soft notices, no hard failures). Measured (SESSION_FINDINGS 2026-08-04):

- **(a) full-window engine run: 28.20 s** (median, n=5) — the engine is SUPER-LINEAR (18×
  bars → ~50× time); the old 0.566 s figure understated canonical cost ~50×.
- **(b) short-circuit pipeline: 48.09 s** (median, n=3; stops at 4.1).
- **(c) full-eval pipeline: 2385.85 s ≈ 39.8 min** (n=1; 4.9 = 35.7 min).
- **Calibration per-run is the NULL cadence, median 8.96 s** (n=200), not 28.2 s.
- **Recomputed naive Mode-E calibration wall ≈ 72–97 days** (vs the stale ~4.5 days) — the
  measured Phase 6 budget problem; makes A+B necessary. Sizes Step 5 (GATE C).

## Step 2 — calibration generator + quarantine + G5 (DONE, committed `c15705e`)

- **`moirai/calibration/generator.py`** — `generate_frame(target_sharpe, n_bars, seed,
  ann_vol=0.60, ...)` returns an Oceanus-valid H1 OHLCV frame whose log-return annualized
  Sharpe = target S. Drift μ = ann_vol·S/8760; σ_bar = ann_vol/√8760; geometric close path;
  seeded intra-bar OHLC bridge; volume ~ lognormal(m=7.188979, s=1.169015) MEASURED from the
  canonical bars. Versioned `GENERATOR_VERSION="v1"`; `provenance()` → `"synthetic:v1"`.
  `realized_annualized_sharpe(frame)` for the self-test. Deterministic in `seed`.
- **`moirai/calibration/harness.py`** — `CalibrationHarness(store_path=None)` raises
  `ProductionStoreError` if the store resolves to the production records root (or an
  ancestor); default `records/calibration/`. `run_synthetic(strategy, frame, hypothesis,
  kind, *, symbol="SYNTH/USDT", timeframe=H1, strategy_params=None)` serves the frame via a
  synthetic `exchange=` (Oceanus stores/validates — no `store` back-door; passes the one-door
  guard) into an isolated per-run `data_root`, runs the engine into the isolated store, and
  stamps `data_provenance:synthetic:v1` on a `calibration_run` record. Returns `CalibrationRun`.
- **Probe G5** (`tests/moirai/test_calibration_quarantine.py`): refuses production; a synthetic
  ladder leaves a production-like store's `trial_counter.txt` + `compute_search_n()` identical.
- **Generator self-test** (`tests/moirai/test_calibration_generator.py`): 1,000 draws/rung
  center within ±0.05 annualized (n_bars=35040 for ~3σ headroom; seed 2026, no seed-shopping);
  Oceanus-validity; determinism.
- Also: vectorized the generator's timestamp construction; made `test_descriptive.py`
  hermetic against the now-present BTC history (monkeypatch `available_range → None`).

## FOUNDER GATE A (2026-08-04) — Stage 4.8 gate (ii) deferred

**Decision:** 4.8's statistical form (per-window-means HAC, as built; pooled-per-bar rejected
for warmup-seam contamination) is ratified LATER, at v002/Phase 6, with calibration data — NOT
now. **Binding constraint: no touchstone asserts on Stage 4.8 until v002.** (Recorded in
HANDOFF and STATE; must also go in T-b's docstring.)

---

## Step 3 — touchstones T-a…T-e (NEXT; §6)

Each `build(seed) -> (data, Strategy)` deterministic; each with an **immutable pre-registered
verdict + rationale committed beside the code**; CI-required (any flipped verdict fails CI);
**set runtime ≤ 10 min** (T-a/T-b/T-d use short synthetic windows via the generator; run them
through the `CalibrationHarness` isolated store, per §6/§7.2's same isolation rule). §6 table:

- **T-a** should-PASS: synthetic S=3.0 (above the ~2.3 floor), MA strategy that captures it → PASS.
- **T-b** should-DIE: 8-parameter rule curve-fit to noise (great IS, garbage OOS). Spec cause
  ∈ {4.2,4.3,4.8}, but **GATE A: assert cause ∈ {4.2, 4.3} ONLY**. **RUN IT FIRST, report the
  actual `cause_of_death`, and DO NOT pin the verdict until the founder has seen it. If it dies
  via 4.8, STOP and surface it** (means 4.2/4.3 aren't catching an overfit they should). The
  mechanism will need SEARCH records in the isolated store so 4.3 charges honest N (and/or 4.2
  sees a lonely spike). Put the "no 4.8 assertion until v002" note in the docstring.
- **T-c** should-DIE: future leak via the `unsafe_same_bar_fill` flag-gated fixture →
  NON_PROMOTABLE at 4.0.
- **T-d** null baseline: seeded random strategy → FAIL, and its 4.9 self-percentile ∈ [0.2, 0.8].
- **T-e** the laundering demo as regression: the 280-sweep winner's returns judged at N=1 vs
  honest N → assert **DSR@N=1 > `dsr.confidence` > DSR@N=280** (0.563 vs 0.054 on real data). It
  runs against **LEGACY** records until Phase 7 re-runs the sweep live — mark that dependency in
  the test docstring. (Ingredients exist: SESSION_FINDINGS 2026-07-16 has V=8.6596e-05 and the
  winning cell fast=25/slow=60 Sharpe 0.0024061 at T=4344.)

## Step 4 — Mode S calibration run (NEXT)

Statistics-level, NO engine (§7.1). Its numbers must reproduce `chronos_math_probe.py` Part 2's
Monte Carlo: **detection ≈0.3% at S=1.0 after a 280-wide search (±0.5pp), ~40–50% pre-registered
(±10pp), floor ≈2.3 (±0.2)**. Divergence = stop-the-build (the shipped statistics differ from the
verified probe), NOT a tolerance to widen.

## Step 5 — GATE C (Phase 6 scoping)

Present the three Step-1 throughput numbers + the Mode S reconciliation together; founder picks
A (split modes) / B (reduced n_nulls) — sized against measured (a)=28.2 s and the ~9 s null
cadence, NOT 0.566 s. Recommended A+B; C (shorter synthetic window) rejected (biases V, which
shrinks with T). Append the decision to HANDOFF before Phase 6.

## Bundled commit (after Step 5, on founder approval)

`feat(moirai): touchstones, calibration generator, quarantine probe, Mode S` — Steps 3–4
land here (Step 2's WIP checkpoint `c15705e` is already pushed; do not re-commit it).
