# S13–S17 deep pass: results

Rules and expectations were written first: `PREREGISTERED.md` (2026-11-05 13:34 UTC). Raw numbers: `s13_results.json`. Reasoning and verdicts: claude.ai Project `claude/item-analyses-3.md`. Synthetic data only.

Environment: Python 3.13, numpy 2.5.4, scipy 1.18.1, numba 0.68.1; the author's full pack (`agentlab-code.zip`, Part 7 folder), 157/157 tests passing.

## K0 — the author's numbers reproduce

Each Part 3–7 script rerun at the author's settings, compared value by value with the pack's shipped `figs/results_p*.json` (timings excluded):

| Part | Values compared | Differences |
|---|---|---|
| 3 (evaluation gate; incl. 200-world decoy run) | 789 | 0 |
| 4 (agent team) | 484 | 0 |
| 5 (improvement loop) | 661 | 0 |
| 6 (validation and safety layer) | 5,362 | 0 |
| 7 (complete architecture; incl. the five phase gates: 22, 40, 33, 13, 50 tests) | 31,184 | 0 |

Note: under `python -I` the author's `p6_experiments.py` stops at its last line (`import p6_example`, the script folder isn't on the path). `run_p6_example.py` runs that last step the same way; the worked example then matched too (seed 6001 was the first seed tried and it passed, as the book says).

## K1 — forged promotion evidence (expectation: accepted) → **all three accepted**

| Attempt | Result |
|---|---|
| K1a: hand-built ladder record for the decoy (its real ladder stopped at the cost-stress rung) | ACCEPTED; decoy LIVE |
| K1b: hand-typed monitor calibration (false alarms 0%) | ACCEPTED |
| K1c: real audit log tampered (real chain no longer verifies), fresh log passed instead, no anchor | ACCEPTED |

## K2 — is the sealed look one look?

- K2a (expect: two looks) → **two looks** with the default call; with a shared `SealedTest` the second call is refused (as designed).
- K2b (expect: ≥ 99% overlap, second look allowed) → different hashes (`1ebae2658dc4` vs `dc350ecf13d4`), first 1,500 days identical, sealed windows [1125, 1500) and [1125, 1501): **100% overlap, second look allowed**.
- K2c (expect ≈ 43/50/56%) → **43.0%, 50.0%, 55.6%**.
- K2d (descriptive) → 60 edge worlds: 50 sealed looks in 36 worlds; **6 repeat looks** of the same idea on the same version (6 worlds; `vol<=1.0`, `vol<=1.25`), median 50% of their days already looked at; **0 of 6 repeats confirmed** (23 first looks confirmed).
- K2e (expect ≈ 5% at k=1, 11–15% at k=4; finding if > 7.5%) → P(null idea confirmed at least once): overlapping loop windows **4.9%, 8.9%, 12.6%, 16.0%**; non-overlapping windows 5.0%, 10.0%, 14.8%, 19.1%. Finding confirmed; k=4 came in above my expected range.

## K3 — risk-engine bypass with the engine in its own process

- K3a (expect: fill) → **filled**; control order through `submit` rejected (MAX_ORDER_SIZE, MAX_POSITION); the bypass order is absent from the audit log, which still verifies.
- K3b (expect: FILLED) → **FILLED**.
- K3c (expect: un-halted, invisible to audit) → INSERT and DELETE variants both: `halted()` False, next order **FILLED**, audit chain verifies, no RESUME entry.
- K3d (expect: exception, no fill) → **BrokenPipeError, 0 fills** (fail-closed; the design works).
- K3e (finding if ×1.6 or smaller blocks no entries) → **confirmed**. 100 healthy worlds, 3× leverage, limit 5×:

| Bug | Size-limit rejections | Engine: max DD median / p90 | Kill fired | Final median (engine) | No engine: ruined |
|---|---|---|---|---|---|
| none | 0 | 17% / 26% | 5% | 1.96 | 0% |
| ×1.25 | 0 | 19% / 27% | 7% | 2.10 | 0% |
| ×1.5 | 0 | 21% / 30% | 13% | 2.20 | 0% |
| ×1.6 | 0 | 22% / 31% | 16% | 2.27 | 0% |
| ×2 | every buggy entry | 11% / 22% | 1% | 1.32 | 0% |
| ×5 | every buggy entry | 11% / 22% | 1% | 1.32 | 0% (median DD 54%) |
| ×20 | every buggy entry | 11% / 22% | 1% | 1.32 | 49% |

## K4 — CUSUM slack and the break-even monitor (200 calibration + 200 test worlds)

| Detector | h | Test false alarms | Dead edges found | Early alarms | Median delay |
|---|---|---|---|---|---|
| 1 shadow reference, k 0.10 (book) | 64.5 | 4.5% | 61.0% | 1.5% | 424 days / 226.5 trades |
| 2 break-even, k 0.10 (book) | 29.5 | 3.5% | 30.0% | 1.0% | 434.5 days / 234.5 trades |
| 3 break-even, k 0.065 | 31.0 | 4.5% | **56.5%** | 1.5% | 454 days / 242 trades |
| 4 shadow reference, k 0.17 | 39.0 | 6.0% | 60.0% | 2.0% | 344.5 days / 180.5 trades |

Rule: explanation supported if detector 3 finds ≥ 1.3× detector 2's share at ≤ 3 points more false alarms → **supported (1.88×, +1.0 point).** Reference statistics in these worlds: shadow-period mean ≈ +5.5 bps, sd ≈ 32 bps; mean after the edge dies ≈ −4.0 bps per trade (so the k = 0.065 choice, made from the book’s ~30 bps, is close to half the actual shift: 4 / 32 ≈ 0.125). The author's 500-world run (reproduced in K0) gives 69% / 36%; the gap to my 61% / 30% is sampling.

## Also found by reading (no check needed)

- Part 3's ablation lists six unused checks while saying "five"; two of them (net > 0 at 1×, t > 0) can't change an accept by construction.
- Both worked examples (Parts 6 and 7) pass the checklist's monitor item with a 10% false-alarm budget after measuring 8% and 6% against a 5% calibration target; the PDFs don’t mention it (one script comment does).
- The registry table has append-only triggers; the halt table doesn't (basis of K3c).
