```yaml
id: B48
title: Edge check II — evidence for the null, the neighbourhood and the sealed look; warnings; break-even cost multiple
size: M
model: opus
who: loop
needs: [B45, B47]
ticks: 3
touches:
  - v2/migrations/0006_search_frozen.sql
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
2. **Neighbourhood:** find the neighbours; run each one not yet in the store as a SEARCH trial of the same hypothesis; then **freeze the search** (an append-only `search_frozen` event for the hypothesis). After that, starting another SEARCH trial for it is refused.
3. C2 (DSR at the now-final N), C3 (costs), C4 (null), C5 (rule), warnings. Decide (B47).
4. Only if the verdict is `PENDING_SEALED_LOOK`: take the look (B46), run the candidate on the sealed block as a VERIFICATION trial, gather C6, decide again, store the final verdict.

B47's `run_edge_check` is rewritten to follow this order; its signature stays one parameter.

**Neighbours.** From the hypothesis's grid (structured, B10): every grid point that differs from the candidate on exactly one axis, by 1 or 2 steps along that axis's list of values. A point off the grid → `grid_unparseable`, C5 fails. A hypothesis with no grid and N = 1: C5 is `pass` with reason `no_neighbourhood_defined` (it was a single pre-registered point; there is nothing to compare). No grid and N > 1: C5 fails with `undeclared_search_breadth` (a searched point wearing a pre-registered label). These three cases are v1's, kept as they were [Certain — read].

**The neighbourhood rule is pluggable.** A rule takes the candidate's per-bar Sharpe and its neighbours' and returns pass or fail with a reason. Two are built:
- `v1_plateau`: pass if the neighbours' median is at least `0.5 ×` the candidate's, **and** no more than 25% of neighbours are negative while the candidate is positive (v1's values, `plateau.median_frac` and `plateau.max_cliff`) [Certain — read];
- `test_rule`: always pass; tests only, refused by the loader for real runs.
Which rule is active is `neighbourhood_rule` in the protected file (B47). It stays `null` until G5, so C5 is unavailable and nothing passes.

**Lone spike** (independent of the active rule): the candidate's per-bar Sharpe is positive, there are at least three neighbours, and their median is below `0.25 ×` the candidate's. It sets `lookahead_review_required`, which stops the strategy until a person has run the look-ahead kit (B44) and written the result down. *(The 0.25 is set here as a starting value for the founder; it only decides when a review opens, never a verdict.)*

**C4 evidence** = B45's `null_benchmark` on the candidate's trades over the research window, with the seed and draw count from the frozen config.

**C6 evidence.** The candidate is run on `[seal date, look end)` through the door with `purpose="sealed_look"` and the look's id, as a VERIFICATION trial (it never raises N). Evidence: sealed trade count, `net_x2`, and `net_adverse` where funding applies, computed exactly as C3. The record also lists any post-seal dates of this asset that other families' research has read through series joins (V2-D46), from the stored footprints: reported, never decisive.

**Warnings** (`v2/config/edge_warnings.yaml`, an ordinary file: warnings never decide, so these are not protected values; starting values are v1's [Certain — read]):
- *subperiods:* 12-month windows; warn if fewer than 60% have a positive mean net return, or one window holds more than 60% of total net P&L;
- *trade count:* warn below 30 round trips;
- *capacity:* warn if, at the configured capital × 10, the median trade's notional is more than 1% of the median dollar volume of its entry bar;
- *fragmentation:* B18's warning, with the DSR at union N.

**Break-even cost multiple** (reported, never decides): the largest k for which the net result with frictions × k is still positive: `k* = (Σ gross − Σ funding − Σ basis) ÷ Σ frictions`, frictions being the five that the 2× run doubles. `k* > 2` is the same statement as "passes the 2× run".

## Deliver
1. `moirai/neighbourhood/`: `neighbours(grid, point, steps=2)`, the two rules, `lone_spike(...)`, `NeighbourhoodResult`.
2. `moirai/edge/gather.py`: `gather_c4`, `gather_c5` (runs missing neighbours through B43's runner, then freezes the search), `gather_c6`. `moirai/edge/run.py`: the order above.
3. `moirai/warnings/`: the four warnings and `break_even_multiple`.
4. `v2/config/edge_warnings.yaml`.
5. Tests, including the end-to-end worlds below.

## Steps
1. Tests (red). 2. Neighbourhood and rules. 3. Search freezing. 4. `gather_c4`, `gather_c5`, `gather_c6`; the new `run.py`. 5. Warnings, break-even. 6. End-to-end worlds. 7. Report.

## Known answers and checks

**Neighbours.** Grid `{fast: [5, 10, 20, 40], slow: [50, 100, 200]}`, candidate `(10, 100)`: neighbours are `(5,100)`, `(20,100)`, `(40,100)`, `(10,50)`, `(10,200)`: five, sorted. Candidate `(5, 50)`: `(10,50)`, `(20,50)`, `(5,100)`, `(5,200)`. Candidate `(7, 100)` → `grid_unparseable`.

**Rules** (candidate per-bar Sharpe 1.0):

| Neighbours | `v1_plateau` | Lone spike |
|---|---|---|
| 0.9, 0.8, 0.7, 0.6 | pass | no |
| 0.45, 0.40, 0.42, 0.38 (median 0.41) | fail (median) | no |
| 0.9, 0.8, −0.1, −0.2 (median 0.35; 50% negative) | fail (cliff) | no |
| 0.1, −0.2, 0.05, −0.1 (median −0.025) | fail | **yes** |
| 0.1, 0.05 (two neighbours) | fail | no (fewer than three) |
| candidate −0.5, neighbours anything | — | no (candidate not positive) |

**The count stays honest.** A hypothesis with 6 SEARCH trials, candidate `(10, 100)`, two of its five neighbours not yet run. After C5: `search_n == 8`, the C2 evidence shows `N == 8` (not 6), and a 9th `start_trial(kind=SEARCH)` for that hypothesis is refused. VERIFICATION trials (the sealed run) are still accepted.

**No grid.** N = 1, no grid → C5 `pass`, `no_neighbourhood_defined`. N = 3, no grid → C5 `fail`, `undeclared_search_breadth`.

**The sealed look is taken only when allowed.** A candidate that fails C3: no look row exists afterwards. A candidate whose verdict is `PENDING_SEALED_LOOK` (with `test_rule`): exactly one look row, one VERIFICATION trial with a footprint naming the look, and a second `run_edge_check` on the same config ends `LOOK_SPENT` without reading sealed data.

**Warnings.**
- Subperiods: four windows with mean returns `+, +, +, −` → no warning; `+, +, −, −` → warning (50%). Window P&Ls `10, 1, 1, 1` → warning (10/13 = 76.9%).
- Trade count: 29 → warning; 30 → none.
- Break-even: trade A of B47 (gross 10, frictions 8, funding −5): `k* = 15/8 = 1.875`. Trades A and B together: `k* = 40/16 = 2.5`. With all frictions zero → `k*` is reported as unbounded, not a division error.
- A result with every warning raised and a passing table still ends `PASS` (repeats B47 row 23, end to end).

**End-to-end worlds** (B19's generator; B43's runner; `test_rule` active; the null at 1,000 draws):
- *Planted edge* (a world with a planted timing edge strong enough that B45's test (c) finds it, eight years of daily-resolution bars, N = 1): verdict `PENDING_SEALED_LOOK` before the look; after a sealed run with ≥ 200 positive trades, `PASS`.
- *Noise:* the same strategy on a noise world: `FAIL`.
- *T-e* (B20's fixture as a stored trial under a hypothesis with 280 SEARCH trials): `FAIL`, on C2.
- *Doubled funding income* (B47's trade A pattern repeated): `FAIL`, on C3 only.
- Every verdict row points to a frozen config, and every trial it read has a footprint inside the research window except the one sealed run.

## Not in this build
Choosing the neighbourhood rule (B52, B53) · the look-ahead kit itself (B44; this build only raises the flag) · the basis check (P-15, not accepted) · running on the real engine (after G3).

## Halt if
- Running missing neighbours needs something B43's runner doesn't offer.
- Freezing the search can't be done as one new append-only table, `mnemosyne.search_freeze` (`hypothesis_id` primary key, `frozen_at`), checked by a trigger on `trial` inserts of kind SEARCH (migration `0006`). That is the design; anything else is a halt.
- The end-to-end worlds take more than about five minutes in CI.

## For the gate
`BUILD_NOTES.md` §2 (this build edits it): "neighbour runs raise N; N is frozen before the DSR is read (B48)". The G2-onwards status board: edge check runs end to end; cannot pass until the neighbourhood rule is chosen at G5.
