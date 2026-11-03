# Closing handoff — Moirai Phase 5 Step 3 COMPLETE (T-b…T-e pinned); Step 4 (Mode S) next

**Date:** 2026-08-07 · **Model:** Opus · **Tests:** 315 green (+4 CI assertions). Committed +
pushed this session. **Step 4 (Mode S) and Step 5 (GATE C) build in a FRESH session** — Mode S is a
statistics-level context switch with its own stop-the-build condition and should not inherit this
long touchstone-building context.

---

## What landed (committed this session)

- `moirai/calibration/touchstones.py` (+283): `build_t_b()`, `build_t_c()`, `build_t_d()`,
  `evaluate_t_e()`, and `_tb_prep` (registers T-b's grid as SEARCH). Verdicts + rationale pinned
  beside each build, immutable.
- `moirai/calibration/fixtures/te_laundering_winner.json` — NEW committed, provenance-stamped fixture
  (the 280-sweep winner's per-bar returns; cell 25/60 = trial 117, snapshot 7c0b19aa, V=8.6596e-05).
  Self-verifying — T-e needs no gitignored records. Extracted ONCE; regenerate note inside.
- `tests/moirai/test_touchstones.py` — the 4 CI assertions (any flipped verdict fails CI).

Full measured tables: SESSION_FINDINGS 2026-08-07. Decisions log: HANDOFF 2026-08-07.

## The four DIE/reject verdicts (all threshold-robust, pinned now)

| ID | Verdict | Mechanism |
|---|---|---|
| **T-b** | FAIL, cause ∈ {4.2, 4.3} | MA 8-cell fast×slow grid searched over ZERO-EDGE noise, registered `kind=SEARCH` → **honest N=8** → dies at 4.2 (plateau spike) + 4.3 (DSR 0.483 @ N=8). 4.8 fails too but is NOT asserted (unratified until v002). |
| **T-c** | NON_PROMOTABLE at 4.0 | `unsafe_same_bar_fill=True` (flag-gated, I1 untouched) → 4.0 reads the warning → terminal. |
| **T-d** | FAIL; 4.9 self-pct 27.5% ∈ [0.2,0.8] | seeded price-blind `NullStrategy`. CI asserts the BAND, not the point. Honest draw, not reseeded. |
| **T-e** | DSR@N=1 0.56300 > DSR@N=280 0.05438 < 0.95 | shipped `statistics.dsr` on the committed fixture. Honest two-part form, NOT the §6 chained form (v002 defect: 0.5630 ≯ 0.95). |

**Founder decision (2026-08-07): T-b = MA-grid-over-noise (Option 1)** — the spec's "8-parameter
rule" was illustrative of overfit CAPACITY, not a mechanism; an 8-cell grid over 2 knobs charges the
same selection bias 4.2/4.3 test, and mirrors the real laundering demo (T-e). Three conditions all
met: (1) honest N via SEARCH records (N=8, not 1 — verified); (2) full-eval, table printed, cause ∈
{4.2,4.3}, stop-if-only-4.8 (did not trigger); (3) grid/seed/noise-frame pinned a priori, winner
drift-guarded, no seed-shopping.

## STANDING — do NOT re-open

- **T-a1/T-a2 are DEFERRED** (`BLOCKED-ON-PHASE-6-CALIBRATION`, not CI-asserted). Do NOT try to
  pin/PASS them. They pin only once Phase-6 reconciles `min_round_trips`/`subperiod`/`ruin_dd` (the
  meta-finding). §6 is amended to SIX touchstones.
- **GATE A**, the four fork constraints, T-e framing A — all still hold.
- **CI budget:** the touchstone set runs ~5.1 min (4.9's 40 nulls ≈ 80 s per full-eval touchstone).
  Within §6's ≤10-min budget. If it must shrink, T-b's window is the lever (it does not assert 4.8);
  that is a Step-5 budget call, deliberately left to the founder.

---

## Next session — Step 4: Mode S calibration (opening move)

**Opening guard:** read committed STATE + newest HANDOFF + this handoff + SPEC §7.1/§7.3/§7.4 and
`chronos_math_probe.py` Part 2. Confirm HEAD==origin, suite green (315). Do NOT touch the pinned
touchstones or the DEFERRED canaries.

**Mode S (statistics-level, NO engine — spec §7.1):** inject known effects directly into synthetic
*returns series* and drive the statistical stages (4.3, 4.1, and 4.8's aggregate) ALONE, pointed at
the SHIPPED `moirai/statistics.py` — NOT a scratch reimplementation. The whole point is to prove the
shipped statistics reproduce the verified probe's Monte Carlo (`chronos_math_probe.py` Part 2, whose
machinery this is). Fast (no engine).

**The reconciliation targets (SPEC §7.1; brief Phase 5) — reproduce within tolerance:**
- detection ≈ **0.3%** at true S=1.0 after a 280-wide search — tolerance **±0.5 pp**
- **~40–50%** pre-registered (N=1) at S=1.0 — tolerance **±10 pp**
- detection **floor ≈ 2.3** annualized — tolerance **±0.2**

**STOP-THE-BUILD condition (NOT a tolerance to widen):** any divergence beyond the bands above means
the shipped statistics differ from the verified probe — stop and surface, do not tune. (Distinct in
spirit from GATE A, but the same discipline: the instrument is proven, not adjusted to look proven.)

**CHECKPOINT then Step 5 — GATE C (Phase 6 scoping):** present to the founder (a) the Mode S three
numbers matching the probe, and (b) the three throughput numbers already measured (SESSION_FINDINGS
2026-08-04): full-window engine run **28.2 s**, short-circuit pipeline **48.1 s**, full-eval pipeline
**39.8 min** (4.9 = 35.7 min); null cadence median **8.96 s**. The founder picks the Phase-6 budget
resolution — A (split modes) / B (reduced n_nulls) / C — **sized against 28.2 s per-run and the ~9 s
null cadence, NOT the stale 0.566 s short-window figure.** This is the one genuinely open item.

**Commit:** Step 4 (+ Step 5 scoping notes) land as their own commit. Protected paths
(`moirai/`, `configs/gauntlet/`) — full diff + founder approval before committing, as always.
