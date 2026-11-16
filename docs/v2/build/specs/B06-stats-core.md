```yaml
id: B06
title: Statistics I — the ported core, its known-answer tests, the v1 oracle
size: M
model: opus
who: loop
needs: [G1]
ticks: 3
touches:
  - v2/src/chronos2/stats/**
  - v2/tests/stats/**
  - v2/tests/known_answers/v1_oracle/**
  - v2/tools/v1_oracle/**
  - docs/v2/COMPONENTS.md
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B06 — Statistics I

## Why
These functions decide whether a strategy's result is luck. v1 has them, tested against the published papers, and they pass today (28/28 probe checks, 35 tests) [Certain — run in the pre-build audit]. The job is to move them without changing a digit, and to prove that with a second, independent comparison against v1 itself.

## Read first
- v1 `src/chronos/moirai/statistics.py` (270 lines) and `tests/statistics/` (7 files, 407 lines, 35 tests).
- `BUILD_NOTES.md` §2, the bullets on DSR/PSR conventions.
- `COMPONENTS.md` §2, row "Statistics core".

## Deliver
1. `v2/src/chronos2/stats/core.py` with these 17 functions, same signatures, same maths: `lo_se_sharpe`, `lo_eta`, `newey_west`, `nw_weights`, `circ_autocov`, `pr_lemma1_variance`, `stationary_bootstrap_indices`, `block_p_from_returns`, `sr_star`, `psr`, `dsr`, `per_bar_sharpe`, `sample_skewness`, `sample_kurtosis`, `mean_pairwise_correlation`, `effective_trials`, and `years_to_significance` (v1's `atropos_years`, renamed; docstring says so).
   - Not ported: `sweep_trial_variance` (a v1 measurement helper with a Binance-era cost default).
   - Docstrings keep the paper references. Remove v1 stage numbers ("stage 4.1") from them.
2. `v2/tests/stats/`: the six v1 test files and `conftest.py`, with **only** import paths and the renamed function changed. Same assertions, same tolerances, same seeds.
3. **The v1 oracle.** `v2/tools/v1_oracle/dump_stats.py`, run in the **v1** environment (`uv run python v2/tools/v1_oracle/dump_stats.py` from the repo root), calls v1's functions on fixed inputs and writes `v2/tests/known_answers/v1_oracle/stats.json` (floats by `repr`; a header with the v1 commit, numpy and scipy versions).
   - Inputs: for each function, seeds 1000–1049 into `numpy.random.default_rng`, drawing arguments from ranges written at the top of the script (returns: normal, mean 1e-4, sd 2e-3, length 500–5,000; AR(1) series with φ ∈ {0, 0.3, 0.6}; N ∈ {1.0001, 2, 10, 280, 5,000}; V ∈ [1e-6, 1e-3]; T ∈ [100, 50,000]).
4. `v2/tests/stats/test_v1_parity.py`: every v2 function reproduces the oracle to a relative tolerance of **1e-10** (the two environments use different numpy versions, so last-digit differences are allowed and nothing larger).
5. Nothing to add to the workflow: B01's **v1-oracle** job already runs every `v2/tools/v1_oracle/dump_*.py` in the v1 environment and fails if a committed JSON differs. That proves the oracle file really comes from v1.

## Steps
1. Copy the six test files with the import changes; commit (red: module missing).
2. `core.py` → the 35 tests green.
3. `dump_stats.py`; generate and commit `stats.json`.
4. `test_v1_parity.py` → green.
5. The `v1-oracle` job is green on the pull request, and its log shows `dump_stats.py` ran.
6. Docs, report.

## Known answers and checks
- All 35 ported tests pass. Count asserted in the report: block_p 7, effective_trials 10, lo_2002 2, newey_west_1987 5, politis_romano_1994 3, psr_dsr 8.
- `years_to_significance(1.0) == 6.182557232019766`, `(0.5) == 24.730228928079065`, `(2.0) == 1.5456393080049415` (to 1e-12) [Certain — run on v1, 16 Nov].
- `dsr(0.05, T=1000, V=0.0004, N=1) == 0.9428733922457418` and `N=280 → 0.4066753996037846` (to 1e-12) [Certain — run on v1, 16 Nov].
- `sr_star` goes negative for N just above 1 and `dsr(..., floor_at_zero=True)` floors it at 0 (a ported test covers this; confirm it is among the 35).
- Parity: 17 functions × 50 seeds, all within 1e-10.
- `stats/core.py` imports only `numpy` and `scipy.stats`.

## Not in this build
The math probe (B07) · mid-rank counters (B07) · outside-library cross-checks (B08) · any use of these functions.

## Halt if
- A ported test needs any change beyond imports and the one rename.
- Parity fails beyond 1e-10 for any function. For `stationary_bootstrap_indices` specifically: if the cause is a change in numpy's random methods between versions, say so with the evidence and stop; the fix (compare distributions, or pin the draw order) is a statistical choice.

## For the gate
`COMPONENTS.md` §2 "Statistics core": ported in B06 (this build edits that row). `BUILD_NOTES.md` §2: the oracle method (the v1 environment writes a JSON of known answers; a CI job regenerates and diffs it).
