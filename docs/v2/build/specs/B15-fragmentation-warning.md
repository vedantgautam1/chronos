```yaml
id: B15
title: Search-fragmentation warning
size: M
model: opus
who: loop
needs: [B05, B08]
ticks: 3
touches:
  - v2/migrations/**
  - v2/src/chronos2/moirai/**
  - v2/src/chronos2/mnemosyne/**
  - v2/tests/moirai/**
  - v2/config/protected/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B15 — Search-fragmentation warning

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
4. registered within `fragmentation_window_days` of each other (90, from protected config).

A **lineage** is a hypothesis together with all its siblings, taken transitively (a sibling of a sibling is in). `union_n` = distinct SEARCH trials across the lineage.

v2 grids are structured data (B08), so v1's string parser is ported only as `parse_legacy_grid()` for reading old descriptions, with v1's strictness (anything it can't parse raises; it never guesses).

## Deliver
1. `mnemosyne/lineage.py`: `siblings(hypothesis_id)`, `lineage(hypothesis_id)`, `union_n(hypothesis_id)`.
2. `moirai/fragmentation.py`: `fragmentation_warning(hypothesis_id, sr_hat, T, V, skew, kurt) -> Warning | None` returning the sibling ids (sorted), the shared axes (sorted), `union_n`, `dsr_at_own_n`, `dsr_at_union_n`.
3. `moirai/legacy_grid.py`: `parse_legacy_grid(description)`.
4. `v2/config/protected/validation.yaml`: add `fragmentation_window_days: 90`.
5. Tests.

## Steps
1. Tests (red). 2. `lineage.py`. 3. `fragmentation.py`. 4. Legacy parser with v1's cases. 5. Docs, report.

## Known answers and checks
**v1's case, re-expressed.** Class `ma_crossover`. A: `fast ∈ {5,10,…,50}`, `slow ∈ {60,65,…,195}`, 2 SEARCH trials. B: `fast ∈ {10,…,55}`, `slow ∈ {65,…,200}`, 3 SEARCH trials. Registered a day apart.
- `siblings(A) == ["B"]`; shared axes `["fast", "slow"]`; `union_n == 5`.
- With `sr_hat = 0.05, T = 1000, V = 0.0004`: `dsr_at_own_n` uses N = 2 and `dsr_at_union_n` uses N = 5; both equal B04's `dsr` at those N to 1e-12, and `dsr_at_union_n < dsr_at_own_n`.

**Not siblings** (each alone breaks it):
- C: same as B but class `breakout` → no.
- D: `fast ∈ {100,…,150}` (no overlap on one axis) → no.
- E: axes `fast, slow, stop` → no (different axis set).
- F: same as B, registered 91 days after A → no; at 90 days → yes.

**Transitive:** A–B siblings, B–G siblings, A–G not directly (ranges don't overlap) → `lineage(A) == {A, B, G}` and `union_n` counts all three.

**No double counting:** a trial registered under A and again, identically, under B (same `trial_id`, B08) counts once in `union_n`.

**No siblings:** a lone hypothesis returns `None`, and the edge-check report line reads "no siblings found" (string pinned in the test).

**Legacy parser:** `"fast in range(5,55,5) x slow in range(60,200,5)"` → `{"fast": [5,…,50], "slow": [60,…,195]}`; an axis named `max_x` isn't split on its `x`; `"fast in 5..50"` raises.

**Protected:** adding `fragmentation_window_days` edits a protected file: **stop and ask**, as in B13.

## Not in this build
Making the warning binding (revisit when research agents file hypotheses, V2-D31) · the edge check that prints this warning (B42) · effective-N from stored returns.

## Halt if
- The overlap rule (3) and v1's behaviour disagree on v1's own test case.
- Transitive lineages make `union_n` grow without bound on a realistic registry (then the definition needs the founder).

## Doc rows to update
`COMPONENTS.md` §2 "Search-fragmentation screen": ported in B15 with the sibling rule above.
