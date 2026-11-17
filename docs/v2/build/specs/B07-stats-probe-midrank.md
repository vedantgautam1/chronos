```yaml
id: B07
title: Statistics II — the math probe as tests, mid-rank counters, the floating-point tie case
size: M
model: opus
who: loop
needs: [B06]
ticks: 3
touches:
  - v2/src/chronos2/stats/**
  - v2/tests/stats/**
  - v2/tests/known_answers/**
  - v2/tests/test_no_naive_rank.py
  - docs/v2/BUILD_NOTES.md
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B07 — Statistics II

## Why
Two things. First, v1's 28-check probe becomes ordinary tests, so it runs on every change instead of when someone remembers. Second, v2 needs one shared way to count "how many random results beat ours", with ties handled correctly. Counting ties the naive way made pure noise look non-random in a published reproducer (mean rank 37.6 where 50 is correct) [Certain — run, S8a]; v1 has that naive count at one spot (`null_bench.py` line 125). v2 never will.

## Read first
- v1 `chronos_math_probe.py` (340 lines).
- Master doc §6 "Null benchmark (V2-D21)". `BUILD_NOTES.md` §2, first bullet and the bullet "Bootstrap p-values in outside libraries…".
- Project note `claude/item-analyses.md`, S8a, "Permutation testing" (for what the reproducer shows; don't copy its code, its licence isn't stated).

## The definitions (fixed here, before any code — V2-D25 rule 2)
Let `null` be B values from a null distribution and `obs` the observed value. `G` = how many null values are strictly greater than `obs`, `L` = strictly less, `E` = exactly equal.

- **Upper-tail p-value:** `p = (1 + G + 0.5·E) / (1 + B)`.
  - Never 0. With no ties it is the standard permutation p-value with the +1 correction. With everything tied it is ≈ 0.5, not 1/(B+1) and not 1.
- **Lower-tail:** the same with `L` in place of `G`.
- **Percentile rank of `obs` in the null:** `100 · (L + 0.5·E) / B`.
- Ties are **exact equality** of float64 values. No tolerance. (A tolerance would be a tunable threshold; exact mid-rank already removes the bias, because rounding noise is symmetric.)
- Any NaN in `null` or `obs` raises. `B == 0` raises.

## Deliver
1. `v2/tests/stats/test_math_probe.py`: the probe's 28 checks as parametrised tests, same expected values and tolerances as v1's `check(name, got, want, tol)` calls, same names.
2. `v2/src/chronos2/stats/ranks.py`: `p_upper(null, obs)`, `p_lower(null, obs)`, `percentile_rank(null, obs)`, and `strict_percentile_rank(null, obs)` (= `100·L/B`; exists only so the tie case can show the artefact; its docstring says never to use it for a decision).
3. `v2/tests/stats/test_ranks.py` and `test_fp_tie_case.py`.
4. A repo-wide test `v2/tests/test_no_naive_rank.py`: scans `v2/src/` and fails on the patterns `np.mean(<x> < <y>)`, `np.mean(<x> > <y>)`, `(<x> >= <y>).mean()` and their variants outside `stats/ranks.py`. (Crude on purpose; a false alarm is cheap, a missed naive count isn't.)

## Steps
1. Commit `test_ranks.py`, `test_fp_tie_case.py` with the known answers below (red).
2. `ranks.py` → green.
3. Port the probe → 28 green.
4. `test_no_naive_rank.py`, with a planted offender in a temp file to prove it fires.
5. The two doc lines below; report.

## Known answers and checks
**Ranks, by hand:**
- `null = [1, 2, 3, 4]`, `obs = 2.5` → `G=2, L=2, E=0` → `p_upper = 3/5 = 0.6`, `percentile_rank = 50.0`.
- `null = [1, 2, 2, 3]`, `obs = 2` → `G=1, L=1, E=2` → `p_upper = (1+1+1)/5 = 0.6`, `percentile_rank = 50.0`, `strict_percentile_rank = 25.0`.
- `null = [5]*999`, `obs = 5` → `p_upper = (1 + 0 + 499.5)/1000 = 0.5005`.
- `null = [0]*999`, `obs = 1` → `p_upper = 1/1000 = 0.001` (never 0).
- `p_upper + p_lower == (2 + B) / (1 + B)` for any input (checked on 200 random integer-valued draws with heavy ties, seed 7).

**Uniformity (seed 11):** 5,000 worlds from one `numpy.random.default_rng(11)`; in each world draw `null` = 999 standard normals, then `obs` = 1 standard normal. The 5,000 `p_upper` values have mean in **[0.484, 0.517]** (the theoretical 0.5005 ± 4 standard errors) and a Kolmogorov–Smirnov distance from uniform below **0.03**.

**The floating-point tie case** (the idea, re-implemented from scratch): one `numpy.random.default_rng(23)`; in each of 2,000 worlds draw `x` = 60 trade returns (normal, mean 0, sd 0.01). `obs = float(numpy.sum(x))`. `null` = `float(numpy.sum(x[perm]))` for 500 permutations drawn from the same generator. Every one of those sums is the same number mathematically.
- Mean of `strict_percentile_rank` over the worlds is **below 45** (the artefact; the published reproducer shows 37.6 with its own sizes).
- Mean of `percentile_rank` is in **[49, 51]**.
- On average at least **5%** of null sums are bit-for-bit equal to `obs` (which is why exact-tie mid-rank works).

*Design note, for the record (V2-D25).* The three bounds were written first. A first version of the construction used Python's built-in `sum()`, and showed no artefact at all: since Python 3.12 the built-in compensates for rounding, so every ordering gives the identical float. The construction was changed to `numpy.sum` (what real code uses); **the bounds were not changed.** One design-time run of the construction above (16 Nov, numpy 2.5.5): strict 38.9, mid-rank 50.2, equal share 22.6% [Certain — run]. A plain running total (`acc += v`) gives 42.9 / 50.2 / 14.6%.

*Recorded as a deviation (G0 red team, finding 24).* V2-D25 says the rules are committed before the test runs. Here the pass/fail bounds were, but the construction was changed once after a first look. It is disclosed rather than hidden; the founder sees it in the G0 report. From here on the construction is frozen as well: the builder may not change sizes, seeds or the summation method.

**Probe:** 28 of 28 pass; the report lists them by name next to v1's output from the same commit.

## Not in this build
The null benchmark itself (B45) · any decision rule that uses a p-value.

## Halt if
- Any of the three tie-case bounds fails with the stated construction. Don't change sizes, seeds or the summation method to get there: report the numbers. The definitions above stand either way; only the demonstration would need rethinking.
- A probe check needs a wider tolerance than v1's.

## For the gate
This build edits two rows itself. `BUILD_NOTES.md` §2 first bullet: add "v2: `stats/ranks.py` is the only place ranks and p-values are counted (B07)", and the trap "Python's built-in `sum()` hides order-dependent rounding (compensated since 3.12); `numpy.sum` and running totals don't, so the tie artefact is real in our stack". `COMPONENTS.md` §2 rows "Known-answer tests" and "Null benchmark".
