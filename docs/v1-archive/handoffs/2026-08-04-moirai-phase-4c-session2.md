# Closing handoff — Moirai Phase 4c session 2 (sub-period 4.8, null benchmark 4.9, descriptive 4.10, probe G7)

**Date:** 2026-08-04 · **Model:** Opus · **Protected paths touched:** `moirai/`,
`tests/moirai/` (full diff shown, founder-approved before commit). **Tests: 284 → 303,
all green.** This session COMPLETES Phase 4c — **the full eleven-stage pipeline
(4.0–4.10) now exists.**

---

## What landed

| moira_id (byte-matches v001 `pipeline_order`) | file | gate |
|---|---|---|
| `M4.8-subperiod` | `moirai/stages/subperiod.py` | (i) per-bar Sharpe positive in ≥ `subperiod.positive_sharpe_frac` of windows; (ii) one-sided HAC t > `subperiod.hac_t_threshold`; (iii) no window > `subperiod.max_single_window_pnl_frac` of net PnL |
| `M4.9-null-bench` | `moirai/nulls.py` + `moirai/stages/null_bench.py` | candidate net > the `null_bench.percentile_gate`-th percentile of 200 cadence-matched null net returns |
| `M4.10-descriptive` | `moirai/stages/descriptive.py` | NONE — reporting-only (passed always True) |

**`rerun.py` extended (session-1 file, re-touched).** Keyword-only `strategy=`/
`hypothesis=` overrides so 4.9 pushes cadence-matched nulls (different strategy, id
`<candidate>:null:<i>`) through the SAME wall-clock-timed VERIFICATION door. Additive,
backward-compatible — 4.5/4.6/4.7 unchanged, all prior tests green.

## Pre-code ground truth (confirmed fresh, not from memory)

- D-R4-m = m = ⌈T^⅓⌉; `dateutil.relativedelta` available for the 12-month partition;
  Newey–West present and pinned in `statistics.py` (consumed, not reimplemented).
- Milestone: 42 round trips, durations 1–148 bars over 4344 bars → nulls fit easily.
- The dev window (6 months) yields **K=1** twelve-month sub-window → 4.8 is unjudgeable
  there (handled as `insufficient_subperiods`, not a crash).
- ETH/USDT data is NOT cached and `MACrossover` is symbol-bound → 4.10 cross-asset
  skips-with-note rather than fetching offline or running a degenerate trace.

## The three subtle decisions

1. **Look-ahead forbidden by construction (4.9).** `place_null_entries(n_bars,
   durations, n_entries, rng)` has no price parameter — it literally cannot see prices.
   `NullStrategy` decides off an internal bar counter; it reads the current close only to
   size the order (present-price sizing, not look-ahead). Tested structurally (signature)
   and for determinism (fixed `ctx.rng` → identical placements).
2. **Stage 4.8 gate (ii) — OPEN/UNRATIFIED methodology decision (founder 2026-08-04).**
   During review the founder's two answers diverged (switch to pooled-per-bar HAC vs keep
   per-window-means), resolved to **keep per-window-means as built, treat gate (ii) as
   unratified.** As built: HAC t on the K≈6 window mean returns (T=K, m=⌈K^⅓⌉) — matches
   the spec's literal "pooled mean of per-window mean returns," but at K≈6 Newey–West is
   near-empty. The pooled-per-bar alternative is more powered BUT contaminated by K−1
   warmup-reset SEAMS (each sub-window re-runs fresh; concatenation splices
   autocorrelation artifacts exactly where NW reads them) — the worse failure for this
   project, so NOT defaulted to. It was verified the code was never switched (nothing to
   revert); a unit test matches the as-built HAC t directly against
   `statistics.newey_west` on K=6 windows. **v002/Phase 6:** the quant ratifies the form
   AND calibrates the threshold; `gate_ii_methodology_status` is stamped in evidence;
   gates (i)/(iii) and the {m/2, 2m} bracket stand.
3. **4.10 cross-asset limitation (non-gating).** Skipped-with-note: no ETH data cached
   AND `MACrossover` is symbol-bound (a faithful trace needs a symbol-agnostic rule or a
   rebound instance — a Candidate-design question, deferred). 200d-MA regime skipped on
   windows shorter than 200 days of prior history. Neither affects a verdict.

## Probe G7 (CI-required)

`tests/moirai/test_seal_respect.py`: a re-run stage whose evaluation window touches a
constructed SEALED range → `SealedDataError` propagates UNCAUGHT → ERRORED verdict (I11)
then re-raise. DISTINCT from 4.7's forward guard (which gracefully refuses an auxiliary
shifted window entering sealed/past-data ranges). No stage catches `SealedDataError`.

## v002 reconciliation — rename list now 12 (+ 1 dropped gate + 1 open form)

Added (5 renames): `wf.window_months`→`subperiod.window_months`;
`wf.min_positive_frac`→`subperiod.positive_sharpe_frac`;
`wf.hac_t_min`→`subperiod.hac_t_threshold`;
`wf.max_window_pnl_frac`→`subperiod.max_single_window_pnl_frac`;
`null_bench.percentile` (0.95)→`null_bench.percentile_gate` (95, **read as a percentile,
not a fraction**). Kept SEPARATE: the 4.7 dropped sign-agreement gate (dormant) and the
4.8 gate (ii) open methodology form.

## Full-pipeline checkpoint (real output; numbers in SESSION_FINDINGS)

`status FAIL`, `authority NO_AUTHORITY`, cause = M4.1, M4.3, M4.5, M4.7, M4.8, M4.9 — a
COMPLETE verdict with every stage present.
- 4.8: K=1 → `insufficient_subperiods`.
- 4.9: candidate at the **88.5th percentile** of 200 nulls (p95 gate = −2.93% net;
  candidate −9.08%) → FAIL — beats most random same-cadence trading but not the bar.
- 4.10: CAGR −17.5%, maxDD 15.1%, Sortino −0.79, profit factor 0.77, turnover 78×;
  annualized Lo AR(1) −0.5507 ≈ naive −0.5518 (ρ≈0).
- Throughput: 207 re-runs, **median 0.566 s/run** (4.9 ≈ 113 s; pipeline ≈ 2¼ min) →
  Phase 6 calibration budget ≈ **~4.5 days naive** (down from ~11 days at 1.4 s).

## Tests added (19 → 303 total)

`test_subperiod.py` (partition exactness, one-regime-wonder fails (iii), HAC consumed
from `statistics.newey_west`, {m/2,2m} bracket, K<2 insufficient, candidate guard),
`test_null_bench.py` (no-price-parameter, fixed-seed placement determinism, percentile-95
read, below-band fail, no-round-trips unjudgeable, real nulls tagged `:null:`,
determinism, candidate guard), `test_descriptive.py` (never gates, all sections present,
annualized names window, cross-asset symbol-bound note, 200d-MA compute path, candidate
guard), `test_seal_respect.py` (G7).

## STOP-AND-FLAG items (none forced a halt)

- 4.9 null construction made structurally price-blind (no contortion). ✅
- 4.8 HAC did not "look wrong" — it is unjudgeable (K=1) on the dev window and tested
  against `statistics.py` at K=6; the gate-(ii) FORM is flagged as an open decision. ✅
- Full-pipeline wall-clock BETTER than 1.4 s (0.566 s). ✅
- No spec-vs-v001 drift beyond those recorded. ✅

## For Phase 5 (next)

Touchstones (§6), the calibration harness (§7 power curve across `calibration.ladder_S`),
and the budget decision — sized against 0.566 s/run. The full eleven-stage gauntlet
exists to calibrate. Session 1's open items still stand for v002/Phase 6: the 4.7
sign-agreement dropped gate, and now the 4.8 gate (ii) methodology form.
