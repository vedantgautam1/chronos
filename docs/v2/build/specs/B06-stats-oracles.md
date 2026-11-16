```yaml
id: B06
title: Statistics III — cross-checks against outside libraries
size: S
model: opus
who: loop
needs: [B05]
ticks: 2
touches:
  - v2/pyproject.toml
  - v2/uv.lock
  - v2/tests/stats/oracles/**
  - docs/v2/COMPONENTS.md
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B06 — Statistics III

## Why
B04 proved v2 equals v1. This build asks a different question: does v1 equal the rest of the world? Three well-tested libraries compute some of the same things. Where they agree with us, good. Where they differ, the difference must be one we already know about and have written down, and nothing else.

These libraries are **test-only**: nothing under `v2/src/` may import them.

## Read first
- `COMPONENTS.md` §1 rows `arch`, `quantstats`, `ml4t-diagnostic`. `BUILD_NOTES.md` §2: the quantstats bullet, the "Not every DSR is v1's DSR" bullet, the bootstrap-coverage bullet.

## Deliver
1. A `oracles` dependency group in `v2/pyproject.toml`: `arch`, `quantstats`, `ml4t-diagnostic`, pinned by the lock. Installed in CI's **tests** job.
2. `v2/tests/stats/oracles/test_arch.py`, `test_quantstats.py`, `test_ml4t_diagnostic.py`.
3. `v2/tests/test_oracles_are_test_only.py`: fails if any file under `v2/src/` imports one of the three.

## Steps
1. Add the group, lock, confirm all three install on Python 3.14 together with the rest. Commit.
2. Commit the three test files (red where our function isn't imported yet; then green).
3. The test-only guard.
4. Docs, report (with the installed versions).

## Known answers and checks
Fixed inputs: series A = 2,000 normals (mean 2e-4, sd 1e-2), seed 101; series B = AR(1) with φ = 0.5 on the same shocks.

- **arch, Newey–West:** our `newey_west(B − mean(B), m)` for m ∈ {0, 4, 12} equals arch's Bartlett-kernel long-run variance at the same lag to a relative **1e-10**. (Sort out the convention first, in the test's docstring: population vs sample scaling, whether the mean is removed. The tolerance isn't negotiable; the convention mapping is the work.)
- **arch, stationary bootstrap:** with block probability p from our `block_p_from_returns(B)`, the bootstrap variance of the mean from 5,000 arch resamples and from 5,000 of ours agree within **6%** of each other and each is within 6% of `pr_lemma1_variance(B, p)` (the same band v1's probe uses).
- **quantstats:** with `periods=365`, its Sharpe on A equals `per_bar_sharpe(A) · sqrt(365)` to **1e-9**. Called without `periods`, the two differ by the factor `sqrt(252/365)`: assert that too, as the trap on record.
- **ml4t-diagnostic DSR:** for a normal series (skew 0, kurtosis 3) with N = 10, its DSR and ours differ, and the difference is the documented one (variance at the threshold, T not T−1, the max-of-N table). The test computes ours and theirs, and asserts **the size of the gap we expect from those three known causes** (the builder derives it in the docstring) within 1e-6. With N = 1,000 its value equals its own N = 100 value (the table cap): assert it.
- No file under `v2/src/` imports `arch`, `quantstats` or `ml4t_diagnostic`.

## Not in this build
SPA/StepM/MCS (need stored trial returns and a use for them) · reports with quantstats.

## Halt if
- A library disagrees with us beyond the stated tolerance for a reason not already in `BUILD_NOTES.md` §2. That is a finding, possibly about v1: write up both numbers and the suspected cause, and stop.
- `ml4t-diagnostic` can't be installed alongside the others (its notes say it conflicts with `ml4t-live`, which we don't install).

## Doc rows to update
`COMPONENTS.md` §1: versions installed, check level stays **Run**, "test-only, B06". `BUILD_NOTES.md` §2: any convention mapping that took effort to find.
