```yaml
id: B18
title: Search-fragmentation warning
size: M
model: opus
who: loop
needs: [B06, B11]
ticks: 3
touches:
  - v2/src/chronos2/moirai/**
  - v2/src/chronos2/mnemosyne/lineage.py
  - v2/tests/moirai/**
  - v2/tests/mnemosyne/test_lineage.py
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B18 — Search-fragmentation warning

## Why
Honest counting has a hole: split one big search into several small "different" hypotheses and each faces an easier bar. On pure noise, 12 candidates counted together gave 1% false finds; split into families, 13%; one each, 28% [Certain — run, S12]. v1 already had the answer: look for sibling hypotheses and report the score at their combined count. It is a **warning**, not a gate (V2-D31), because deciding what counts as a sibling takes judgement.

## Read first
- v1 `src/chronos/moirai/stages/eligibility.py`: `_grid_axes`, `parse_grid_geometry`, `_fragmentation_screen` (lines ~39–110 and ~192–245). v1 `tests/moirai/test_free_stages.py::test_eligibility_fragmentation_screen_union_n`. v1 `tests/moirai/test_plateau.py`, probe G6a.
- Master doc §6 "Search-fragmentation warning", §10 V2-D31. `BUILD_NOTES.md` §2, the "Count attempts across related hypotheses" bullet.

## The rule (fixed here)
Two hypotheses are **siblings** when all four hold:
1. same `strategy_class`;
2. same set of grid axis names;
3. on every axis, their value ranges overlap: `max(min_a, min_b) <= min(max_a, max_b)`;
4. registered within `fragmentation_window_days` of each other (90, read from the protected file through `core.protected`; this build doesn't change that file).

A **lineage** is a hypothesis together with its **direct** siblings. That is what V2-D31 and V2-D34 say ("the hypothesis plus its V2-D31 siblings"); a sibling of a sibling that isn't itself a sibling is not in. `union_n` = the number of distinct `trial_key` values (B10) among the SEARCH trials of the lineage, so the same try filed under two hypotheses counts once.

*Open question for the founder, not decided here:* direct siblings leave a chain open (A overlaps B, B overlaps C, A doesn't overlap C: three lineages that share members, so three sealed looks). Whether the sealed-look ledger should close that chain is put to the founder when B46 is specified. This build reports the chain when it sees one and decides nothing.

v2 grids are structured data (B10), so v1's string parser is ported only as `parse_legacy_grid()` for reading old descriptions, with v1's strictness (anything it can't parse raises; it never guesses).

## Deliver
1. `mnemosyne/lineage.py`: `siblings(hypothesis_id)`, `lineage(hypothesis_id)`, `union_n(hypothesis_id)`.
2. `moirai/fragmentation.py`: `fragmentation_warning(hypothesis_id, sr_hat, T, V, skew, kurt) -> Warning | None` returning the sibling ids (sorted), the shared axes (sorted), `union_n`, `dsr_at_own_n`, `dsr_at_union_n`, and `chained: list` (siblings of siblings that aren't direct siblings; reported, not counted).
3. `moirai/legacy_grid.py`: `parse_legacy_grid(description)`.
4. Tests.

## Steps
1. Tests (red). 2. `lineage.py`. 3. `fragmentation.py`. 4. Legacy parser with v1's cases. 5. Report.

## Known answers and checks
**v1's case, re-expressed.** Class `ma_crossover`. A: `fast ∈ {5,10,…,50}`, `slow ∈ {60,65,…,195}`, 2 SEARCH trials. B: `fast ∈ {10,…,55}`, `slow ∈ {65,…,200}`, 3 SEARCH trials. Registered a day apart.
- `siblings(A) == ["B"]`; shared axes `["fast", "slow"]`; `union_n == 5`.
- With `sr_hat = 0.05, T = 1000, V = 0.0004`: `dsr_at_own_n` uses N = 2 and `dsr_at_union_n` uses N = 5; both equal B06's `dsr` at those N to 1e-12, and `dsr_at_union_n < dsr_at_own_n`.

**Not siblings** (each alone breaks it):
- C: same as B but class `breakout` → no.
- D: `fast ∈ {100,…,150}` (no overlap on one axis) → no.
- E: axes `fast, slow, stop` → no (different axis set).
- F: same as B, registered 91 days after A → no; at 90 days → yes.

**A chain is reported, not merged:** A–B siblings, B–G siblings, A–G not (ranges don't overlap) → `lineage(A) == {A, B}`, `union_n(A)` counts A and B only, and the warning for A has `chained == ["G"]`.

**No double counting:** the same try (same class, kind, params, dataset, window, costs, seed, code) started under A and again under B has two `trial_id`s and one `trial_key`; it counts once in `union_n`. With A holding 2 trials, B holding 3, and one of B's identical to one of A's: `union_n == 4`.

**No siblings:** a lone hypothesis returns `None`, and the edge-check report line reads "no siblings found" (string pinned in the test).

**Legacy parser:** `"fast in range(5,55,5) x slow in range(60,200,5)"` → `{"fast": [5,…,50], "slow": [60,…,195]}`; an axis named `max_x` isn't split on its `x`; `"fast in 5..50"` raises.

## Not in this build
Making the warning binding (revisit when research agents file hypotheses, V2-D31) · the edge check that prints this warning (B47) · effective-N from stored returns.

## Halt if
- The overlap rule (3) and v1's behaviour disagree on v1's own test case.
- The protected file doesn't hold `fragmentation_window_days: 90`.

## For the gate
`COMPONENTS.md` §2 "Search-fragmentation screen" (this build edits it): ported in B18 with the sibling rule above. Open question to add to the master doc §12: whether sealed looks should treat a chain of siblings as one lineage (see "The rule").
