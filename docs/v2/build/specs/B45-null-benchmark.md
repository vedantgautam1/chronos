```yaml
id: B45
title: Null benchmark — random entries with matched exposure (V2-D21), with its four known-answer tests
size: M
model: opus
who: loop
needs: [B43]
ticks: 3
touches:
  - v2/src/chronos2/moirai/null/**
  - v2/tests/moirai/null/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B45 — Null benchmark

## Why
A strategy can make money for reasons that have nothing to do with its timing: it was long while the market rose, or it trades rarely and so pays little. The null benchmark asks the one question that separates skill from that: **would the same amount of trading, at random times, have done as well?** It builds a thousand strategies that trade as often, hold as long, lean long or short as much and pay the same costs as the candidate, but pick their moments by chance. The candidate passes only if it beats nearly all of them. v1 got one detail of the counting wrong (a strict "less than" that floating-point noise turns into a bias); this build inherits the corrected counters from B07 and adds the four tests the founder locked.

## Read first
- Master doc §6 "Null benchmark (V2-D21, Locked)". `BUILD_NOTES.md` §2, first three bullets.
- v1 `src/chronos/moirai/nulls.py` (`place_null_entries`, `_random_composition`) and `stages/null_bench.py`: the ideas to port. v1 `tests/moirai/test_null_bench.py` for the property tests worth keeping.
- Specs B07 (`stats/ranks.py`: `p_upper`), B11 (`Trade`), B16 (`price_trade`).

## The rules (fixed here)

**What a draw keeps from the candidate** (V2-D21):
- the number of trades;
- the holding times: each draw's durations, in bars, are resampled **with replacement** from the candidate's own (a draw whose durations add up to more than the bars available is redrawn);
- the long/short mix: the candidate's sides, in a random order;
- the sizes: the candidate's contract counts, in a random order *(v0 of "sizing rule": realised sizes. A rule that depends on conditions at the entry bar is out of scope here and is a halt, not a guess)*;
- the costs: every draw's trades are priced by the same pricer as the candidate's, at 1× costs;
- no two positions overlap; an entry may only fall on an **eligible** bar (a bar on which the real strategy could have opened a trade: not inside a data gap, not before its warm-up, not outside its declared trading hours).

**Placement can't see prices.** `place(n_bars, durations, eligible, rng)` returns start bars and has no price parameter, so nothing about price can leak into where a random trade goes. Two methods, chosen by how crowded the timeline is:
- *Sparse* (durations add up to at most 60% of the bars): trades are placed one at a time, longest first; each goes to a start chosen uniformly among the eligible bars where it fits without overlap. A dead end restarts the draw (at most 200 restarts).
- *Dense* (more than 60%): v1's method. The spare bars are split at random into the gaps before, between and after the trades, taken in a random order. A draw with an ineligible entry bar is redrawn (at most 200 times).
- If either limit is hit, the benchmark stops with `PlacementInfeasible`. It never relaxes a rule to get a draw.

**The statistic** is the total net P&L at 1× costs, summed in Decimal. **The p-value** is `p_upper(null, candidate)` from B07 and nothing else: `(1 + G + E/2) / (1 + B)`. **Pass** is decided in B47, not here.

**Draws:** at least `null_min_draws` (1,000) in any real run; fewer is refused. Tests may use fewer through an explicit test-only argument. One seed (`numpy.random.default_rng(seed)`) fixes every draw; the seed comes from the frozen edge-check configuration.

**Never** in this module: shuffling trade order to test a sum; resampling prices.

## Deliver
1. `moirai/null/placement.py`: `place(...)`, `PlacementInfeasible`.
2. `moirai/null/pricer.py`: the `Pricer` protocol (`price(entry_bar, exit_bar, side, contracts) -> Trade`) and `OpenToOpenPricer(bars, venue, cost_inputs)`: entry at the entry bar's open, exit at the exit bar's open, cost components from B16.
3. `moirai/null/benchmark.py`: `null_benchmark(candidate_trades, n_bars, bar_of, eligible, pricer, n_draws, seed) -> NullResult` with `p_upper`, `percentile_rank`, `n_draws`, `candidate_stat`, a seven-number summary of the null, and the restart count.
4. Tests, including a float test pricer (`price difference × side × contracts`, no costs) used by the statistical tests below for speed.

## Steps
1. The property tests and the four known-answer tests (red). 2. `placement.py`. 3. `pricer.py`. 4. `benchmark.py` → green. 5. Report, including how long the statistical tests take.

## Known answers and checks

**Placement properties** (500 random cases, seed 45000, both methods): no overlap; every entry eligible; every trade ends inside the bars; the draw has the candidate's trade count, the same multiset of sides and of sizes; every duration is one the candidate had. Same seed → same placement. `place` takes exactly four parameters, `n_bars`, `durations`, `eligible`, `rng` (signature inspected): there is nowhere to pass a price. Durations adding up to more than the bars → redrawn, never truncated.

**(a) The tie case.** Flat prices (every open equal), zero costs, 20 trades, 1,000 draws: every draw and the candidate make exactly 0. `p_upper == 501/1001 = 0.5004995004995005` exactly; `strict_percentile_rank == 0.0`. (B07 holds the floating-point version of this test. Here money is Decimal, so the ties are exact.)

**(b) Random entries give uniform p-values.** Worlds from `numpy.random.default_rng(45001)`: 1,500 bars; price `= 1000 + cumulative sum of standard normals`; a candidate of 20 trades with durations drawn from {5, 10, 20}, random sides, **placed by `place` itself**; float pricer; 199 draws. Over 1,000 worlds the p-values have: mean in **[0.466, 0.539]**, Kolmogorov–Smirnov distance from uniform below **0.067**, and a share at or below 0.05 in **[0.022, 0.078]**. The bands are four standard errors around the theoretical values (0.5025; 0; 0.05), fixed before any run. A prototype written for this spec gave 0.5001, 0.027 and 0.040 [Certain — run, 16 Nov; the builder's draws will differ, the bands won't].
- **(b2) With trading hours.** The same with eligibility true only on 8 bars in every 24, 400 worlds, seed 45002: mean in **[0.445, 0.560]**, KS below **0.103**. (Prototype: 0.522, 0.065.)

**(c) A planted timing edge is found.** Seed 45003, 200 worlds: 20 long trades of 10 bars, placed at random; the price path is noise plus `1.5/√10` per bar during each of the candidate's own holding periods. The share of worlds with `p <= 0.05` is at least **0.95**. (Prototype: 1.000.)

**(d) Constant exposure on a trend does not pass.**
- *(d1) Always in the market.* 1,500 bars rising 0.5 a bar; 15 long trades of 100 bars, back to back. Every draw is the same arrangement, so `p_upper == (1 + B/2)/(1 + B)` exactly. Not a pass, at any trend strength.
- *(d2) 60% exposure, no timing.* Seed 45004, 300 worlds: price `= 1000 + cumulative sum of (0.5 + standard normal)`; 18 long trades of 50 bars at fixed, evenly spaced starts. The share with `p <= 0.05` is at most **0.10** (prototype: 0.063). In the same worlds, a plain one-sided t-test on the trades' P&L "passes" in at least **95%** (prototype: 100%). The test asserts both: the wrong test is fooled by the trend and this one isn't.

**Refusals.** Fewer than 1,000 draws without the test-only argument → refused. A candidate with no trades → refused. A sizing rule passed as a callable → `NotImplementedError` naming this spec.

## Not in this build
The pass decision (B47) · running nulls through the real engine (after G3; the `Pricer` protocol is where it plugs in) · storing each draw as its own trial (the result records the seed, so any draw can be rebuilt).

## Halt if
- The statistical tests take more than about five minutes in CI. Propose smaller worlds with recomputed bands; don't thin the tests quietly.
- A band is missed by a build that passes every property test. Don't change a seed or a band (hard rule 10); report the numbers.

## For the gate
`COMPONENTS.md` §2 "Null benchmark" (this build edits it): rebuilt in B45 on mid-rank counters, with the four locked tests.
