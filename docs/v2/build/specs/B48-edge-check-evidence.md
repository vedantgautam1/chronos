```yaml
id: B48
title: Edge check II — evidence for the null, the neighbourhood and the sealed look; warnings; break-even cost multiple
size: M
model: opus
who: loop
needs: [B45, B47]
ticks: 3
touches:
  - v2/migrations/0007_search_freeze.sql
  - v2/src/chronos2/mnemosyne/ontology.py
  - v2/src/chronos2/moirai/edge/**
  - v2/src/chronos2/moirai/neighbourhood/**
  - v2/src/chronos2/moirai/warnings/**
  - v2/config/edge_warnings.yaml
  - v2/tests/moirai/edge/**
  - v2/tests/moirai/neighbourhood/**
  - v2/tests/moirai/warnings/**
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B48 — Edge check II: the rest of the evidence

## Why
B47 wrote the decision table and gathered the evidence for the first three criteria. This build gathers the other three (does it beat random timing; is it a broad hill or a lone spike; does it hold up on the sealed data), adds the warnings, and puts the steps in the one order that keeps the trial count honest. After this build the edge check runs end to end, and the only thing that stops a strategy from passing is that the neighbourhood rule hasn't been chosen yet (that happens with planted edges in B53, V2-D20).

## Read first
- Master doc §6 (all); §10 V2-D20, V2-D21, V2-D31, V2-D34, V2-D38, V2-D46. `BUILD_NOTES.md` §2.
- v1 `src/chronos/moirai/stages/plateau.py` (the docstring: neighbours, freezing N) and `tests/moirai/test_plateau.py`. v1 `configs/gauntlet/v001.json` (`plateau`, `subperiod`, `eligibility`, `capacity`).
- Specs B43 (the screening runner), B45 (`null_benchmark`), B46 (`take_look`, the door's `sealed_look`), B47 (all of it), B18 (`fragmentation_warning`).

## The rules (fixed here)

**The order of a run.** Running a missing neighbour is a new search try and raises N. So N can only be read after the neighbourhood is complete:
1. C1 (data sufficiency). If it fails, stop.
2. **Neighbourhood:** if `neighbourhood_rule` is `null`, C5 is unavailable and no neighbour is run (red team F24). Otherwise find the neighbours; run each one not yet in the store as a SEARCH trial of the same hypothesis; then **freeze the search** (a row in `mnemosyne.search_freeze` for the hypothesis). After that, starting another SEARCH trial for it is refused. If a later candidate of the same hypothesis has a neighbour that was never run, C5 is **unavailable** with reason `search_frozen_missing_neighbours`; the founder decides whether to open a new hypothesis (red team F14).
3. C2 (DSR at the now-final N), C3 (costs), C4 (null), C5 (rule), warnings. Decide (B47).
4. Only if the verdict is `PENDING_SEALED_LOOK`: take the look (B46), run the candidate on the sealed block as a VERIFICATION trial, gather C6, decide again, store the final verdict.

B47's `run_edge_check` is rewritten to follow this order; its signature stays one parameter.

**Neighbours.** From the hypothesis's grid (structured, B10): every grid point that differs from the candidate on exactly one axis, by 1 or 2 steps along that axis's list of values. A point off the grid → `grid_unparseable`, C5 fails. A hypothesis with no grid and N = 1: C5 is `pass` with reason `no_neighbourhood_defined` (it was a single pre-registered point; there is nothing to compare). *This exemption is v1's and is a founder question (proposal P-22 (f)): the alternative is to require a declared neighbourhood for every candidate, run as SEARCH trials, which raises N honestly and keeps V2-D20's "binding" for every idea. It only applies once a rule is chosen; while the rule is `null` it never fires.* No grid and N > 1: C5 fails with `undeclared_search_breadth` (a searched point wearing a pre-registered label). These three cases are v1's, kept as they were [Certain — read].

**The neighbourhood rule is pluggable.** A rule takes the candidate's per-bar Sharpe and its neighbours' and returns pass or fail with a reason. Two are built:
- `v1_plateau`: pass if the neighbours' median is at least `0.5 ×` the candidate's, **and** no more than 25% of neighbours are negative while the candidate is positive (v1's values, `plateau.median_frac` and `plateau.max_cliff`) [Certain — read];
- `test_rule`: always pass; tests only, refused by the loader for real runs.
Which rule is active is `neighbourhood_rule` in the protected file (B47). It stays `null` until G5, so C5 is unavailable and nothing passes.

**Lone spike** (independent of the active rule): the candidate's per-bar Sharpe is positive, there are at least `lone_spike.min_neighbours` (3) neighbours, and their median is below `lone_spike.frac` (0.25) × the candidate's. Both values come from the protected file (B47). A lone spike **fails C5** and opens a row in `mnemosyne.lookahead_review`. While a hypothesis has an open review, `run_edge_check` refuses every candidate of it; a review closes only with a row in `lookahead_review_resolution` that names the B44 report it rests on. (Who writes that row is a guard rail: the code can check the report exists, not that a person read it.)

**C4 evidence** = B45's `null_benchmark` on the candidate's trades over the research window, with the seed derived in the frozen config and `min_draws` = the protected `null_min_draws`. **Eligible bars** = bars not inside a gap the door reported, at or after `warmup_bars`, and inside the strategy's `trading_hours` if it declares them (B43). **One pricer:** B45's `OpenToOpenPricer` with the candidate's venue and cost inputs prices both the candidate's statistic and every draw (red team F12).

**C6 evidence.** The look is taken for the config (B46), with `look_end` from the config. One VERIFICATION trial of the candidate's strategy and parameters is started, bound to the look as its only reader, and run on `[seal date, look end)` through B43's `run_sealed` (it never raises N). Evidence: sealed trade count, `net_x2`, and `net_adverse` where funding applies, computed exactly as C3. The record also lists any post-seal dates of this asset that other families' research has read through series joins (V2-D46), from the stored footprints: reported, never decisive.

**Warnings** (`v2/config/edge_warnings.yaml`, an ordinary file: warnings never decide, so these are not protected values; starting values are v1's [Certain — read]):
- *subperiods:* 12-month windows; warn if fewer than 60% have a positive mean net return, or one window holds more than 60% of total net P&L;
- *trade count:* warn below 30 round trips;
- *capacity* (v1's rule, ported [Certain — read, v1 `stages/capacity.py`, `v001.json`]): re-run the candidate at 10× its size with each trade capped at 5% of its bar's volume; warn if the per-bar Sharpe falls by more than 30%, or if more than 20% of the wanted size couldn't be filled;
- *fragmentation:* B18's warning, with the DSR at union N.

**Break-even cost multiple** (reported, never decides): the largest k for which the net result with frictions × k is still positive: `k* = (Σ gross − Σ funding − Σ basis) ÷ Σ frictions`, frictions being the five that the 2× run doubles. `k* > 2` is the same statement as "passes the 2× run".

## Deliver
1. `moirai/neighbourhood/`: `neighbours(grid, point, steps=2)`, the two rules, `lone_spike(...)`, `NeighbourhoodResult`.
2. `0007_search_freeze.sql`: `mnemosyne.search_freeze`, with a trigger refusing SEARCH inserts for a frozen hypothesis; `mnemosyne.verification_of` (`trial_id` primary key, `search_trial_id`) with a constraint trigger, deferred to commit, that refuses a VERIFICATION trial without a row naming a SEARCH trial of the same hypothesis, strategy class and parameters (red team F6: this makes B43's rule a wall); `mnemosyne.lookahead_review` and `lookahead_review_resolution`. All append-only, hashed, journaled.
3. `moirai/edge/gather.py`: `gather_c4`, `gather_c5` (runs missing neighbours through B43's runner, then freezes the search), `gather_c6`. `moirai/edge/run.py`: the order above.
4. `moirai/warnings/`: the four warnings and `break_even_multiple`.
5. `v2/config/edge_warnings.yaml`.
6. Tests, including the end-to-end worlds below.

## Steps
1. Tests (red). 2. Neighbourhood and rules. 3. Search freezing. 4. `gather_c4`, `gather_c5`, `gather_c6`; the new `run.py`. 5. Warnings, break-even. 6. End-to-end worlds. 7. Report.

## Known answers and checks

**Neighbours.** Grid `{fast: [5, 10, 20, 40], slow: [50, 100, 200]}`, candidate `(10, 100)`: neighbours are `(5,100)`, `(20,100)`, `(40,100)`, `(10,50)`, `(10,200)`: five, in this order (axes in the grid's order, then values in the axis's order). Candidate `(5, 50)`: `(10,50)`, `(20,50)`, `(5,100)`, `(5,200)`. Candidate `(7, 100)` → `grid_unparseable`.

**Rules** (candidate per-bar Sharpe 1.0):

| Neighbours | `v1_plateau` | Lone spike |
|---|---|---|
| 0.9, 0.8, 0.7, 0.6 | pass | no |
| 0.45, 0.40, 0.42, 0.38 (median 0.41) | fail (median) | no |
| 0.9, 0.8, −0.1, −0.2 (median 0.35; 50% negative) | fail (both) | no |
| 0.9, 0.8, 0.7, −0.1, −0.2 (median 0.7; 40% negative) | fail (**cliff only**) | no |
| 0.1, −0.2, 0.05, −0.1 (median −0.025) | fail | **yes** |
| 0.1, 0.05 (two neighbours) | fail | no (fewer than three) |
| candidate −0.5, neighbours anything | — | no (candidate not positive) |

**The count stays honest.** A hypothesis with 6 SEARCH trials, candidate `(10, 100)`, two of its five neighbours not yet run. After C5: `search_n == 8`, the C2 evidence shows `N == 8` (not 6), and a 9th `start_trial(kind=SEARCH)` for that hypothesis is refused. VERIFICATION trials (the sealed run) are still accepted.

**No grid** (with `test_rule` active). N = 1, no grid → C5 `pass`, `no_neighbourhood_defined`. N = 3, no grid → C5 `fail`, `undeclared_search_breadth`. With the rule `null`: both → C5 unavailable.

**After the freeze.** A second candidate `(40, 200)` of the same hypothesis, whose neighbour `(20, 200)` was never run → C5 unavailable, `search_frozen_missing_neighbours`; `search_n` unchanged.

**VERIFICATION is a wall now.** Inserting a VERIFICATION trial with no `verification_of` row → refused at commit; one naming a SEARCH trial of another hypothesis, or with other parameters → refused.

**Lone-spike review.** A candidate that is a lone spike → `FAIL`, one `lookahead_review` row; a second candidate of the same hypothesis → refused before anything is read; after a resolution row naming a passing B44 report → accepted.

**The sealed look is taken only when allowed.** A candidate that fails C3: no look row exists afterwards. A candidate whose verdict is `PENDING_SEALED_LOOK` (with `test_rule`): exactly one look row, one VERIFICATION trial with a footprint naming the look, and a second `run_edge_check` on the same config returns the stored final verdict and writes nothing (B47's one-final-verdict rule). `LOOK_SPENT` appears only for a config whose lineage's look was used by **another** config: H2's candidate, after H1 (its sibling) has looked.

**Warnings.**
- Subperiods: four windows with mean returns `+, +, +, −` → no warning; `+, +, −, −` → warning (50%). Window P&Ls `10, 1, 1, 1` → warning (10/13 = 76.9%).
- Trade count: 29 → warning; 30 → none.
- Break-even: trade A of B47 (gross 10, frictions 8, funding −5): `k* = 15/8 = 1.875`. Trades A and B together: `k* = 40/16 = 2.5`. With all frictions zero → `k*` is reported as unbounded, not a division error.
- A result with every warning raised and a passing table still ends `PASS` (repeats B47 row 23, end to end).

**End-to-end worlds**, pinned here so the pass/fail is committed before anything runs (red team F13). All use B43's runner, `test_rule` as the active rule, the null at 1,000 draws, and a **test venue** whose costs at 1× are 5 bps per round trip, with no funding.
- *The planted-edge world* [values from a prototype, run 17 Nov]. Hourly bars from `2018-01-01T00:00Z` to `2026-11-01T00:00Z` (77,424 bars; 72,288 before the seal, 8.25 years). Hourly log returns `0.004 × standard normal` from `numpy.random.default_rng(48001)`, plus `0.25 × 0.004 = 0.001` in every hour from 03:00 to 06:59 UTC. Prices `100 × exp(cumulative sum)`. The strategy: go long at the start of UTC hour `h` and hold `d` hours; grid `h ∈ {1, 2, 3, 4, 5}`, `d ∈ {2, 4, 6}`, all 15 run with `run_grid` (N = 15); candidate `(3, 4)`; target Sharpe 1.0 (C1 needs 6.18 years); `look_end = 2026-11-01T00:00Z`. Expected: `PENDING_SEALED_LOOK` before the look; 214 sealed trades; then **`PASS`**. The prototype's candidate DSR was 1.0000 at N = 15 already with half this edge; each planted trade earns about 40 bps before costs.
- *Noise:* the same world with the planted 0.001 removed, the same grid and candidate: **`FAIL`**, with C3 failing (about 3,000 trades at 10 bps each against no edge).
- *T-e:* B47's 280-trial construction, given a 280-point grid: **`FAIL`**, with C2 failing. (T-e has returns, not trades, so C3 and C4 may be unavailable; a fail outranks a gap.)
- *Doubled funding income* (B47's trade A pattern repeated): `FAIL`, on C3 only.
- *A sibling after a look:* H1 and H2 are siblings; H1's candidate (the planted world) looks; H2's candidate reaches `PENDING_SEALED_LOOK` and ends `LOOK_SPENT`.
- Every verdict row points to a frozen config, and every trial it read has a footprint inside the research window except the one sealed run.

## Not in this build
Choosing the neighbourhood rule (B52, B53) · the look-ahead kit itself (B44; this build only raises the flag) · the basis check (P-15, not accepted) · running on the real engine (after G3).

## Halt if
- Running missing neighbours needs something B43's runner doesn't offer.
- Freezing the search can't be done as one new append-only table, `mnemosyne.search_freeze` (`hypothesis_id` primary key, `frozen_at`), checked by a trigger on `trial` inserts of kind SEARCH (migration `0007`). That is the design; anything else is a halt.
- A deferred constraint trigger for `verification_of` isn't possible with B09's append-only machinery.
- The planted-edge world doesn't end `PASS`: report which criterion stopped it, with its numbers. Don't change the world, the seed or the strategy.
- The end-to-end worlds take more than about five minutes in CI.

## For the gate
`BUILD_NOTES.md` §2 (this build edits it): "neighbour runs raise N; N is frozen before the DSR is read (B48)". The G2-onwards status board: edge check runs end to end; cannot pass until the neighbourhood rule is chosen at G5.
