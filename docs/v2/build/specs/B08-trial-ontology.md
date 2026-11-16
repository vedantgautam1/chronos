```yaml
id: B08
title: Trial store II — ids, code coordinate, hypotheses, SEARCH/VERIFICATION, honest N
size: M
model: opus
who: loop
needs: [B07]
ticks: 3
touches:
  - v2/migrations/**
  - v2/src/chronos2/mnemosyne/**
  - v2/tests/mnemosyne/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B08 — Trial store II

## Why
The single most valuable number v1 produced was a count: the same strategy scored 0.563 when treated as one try and 0.054 once its 280 tries were counted [Certain — v1 fixture]. This build makes that count impossible to get wrong by accident: a result can't be stored without a hypothesis written first, every try says whether it was a search or a check, and the same try filed twice counts once.

## Read first
- v1 `src/chronos/run.py`: `Hypothesis`, `RunKind`, `register_search`, `compute_search_n` and their docstrings (lines ~40–130 and ~290–335). v1 `tests/hephaestus/test_run.py` for the cases worth keeping.
- `BUILD_NOTES.md` §6, the first five bullets. Master doc §10: V2-D03, V2-D31, V2-D42 (code coordinate only; the data footprint is B09).

## The rules (fixed here)
- A **hypothesis** is registered before any trial: `statement`, `prediction`, `strategy_class`, and, for a search, the grid as structured data `{axis: [values]}` (no string parsing in v2).
- A **trial** has a `kind`, always given explicitly: `SEARCH` (one point of a sweep over one hypothesis) or `VERIFICATION` (a check on a chosen candidate: cost stress, a null draw, a sub-window, a re-run).
- **Honest N** for a hypothesis = the number of **distinct** `SEARCH` trials registered under it, **whatever their status** (completed, pruned early, crashed). Rationale: a pruned try was looked at and rejected, which is selection; counting crashed tries too can only raise the bar. `VERIFICATION` trials never count.
- **Ids come from content.** `version_id = content_hash({strategy_class, params, code_coordinate})`. `trial_id = content_hash({hypothesis_id, kind, params, dataset_hash, window, cost_config_hash, seed, code_coordinate})`, free text left out. Registering the same trial twice returns the first record and doesn't change N.
- **Code coordinate** = `{git_commit, lock_hash, engine}` where `lock_hash` is the SHA-256 of `v2/uv.lock` and `engine` is a name and version string (for now `"none"`).
- v1's JSONL records are never imported.

## Deliver
1. `0002_ontology.sql`: tables `mnemosyne.hypothesis`, `mnemosyne.trial`, both append-only with row hashes and journal lines (B07's machinery); `trial.kind` a Postgres enum; `trial.hypothesis_id` a foreign key (no orphan trials); `trial.status` in `completed|pruned|errored|partial`; unique `trial_id`.
2. `mnemosyne/ids.py`: `code_coordinate()`, `version_id(...)`, `trial_id(...)`.
3. `mnemosyne/ontology.py`: `register_hypothesis(...)`, `register_trial(...)` (requires `kind`; no default), `search_n(hypothesis_id)`, `trials_for(hypothesis_id, kind=None)`.
4. Tests.

## Steps
1. Commit the tests below (red).
2. Migration `0002`.
3. `ids.py`, `ontology.py` → green.
4. Run B07's attack list against the two new tables (a parametrised re-use of that test, not an edit of it).
5. Docs, report.

## Known answers and checks
- **No hypothesis, no trial:** `register_trial` with an unknown `hypothesis_id` raises; nothing is stored.
- **Kind is explicit:** `register_trial(...)` without `kind` is a `TypeError`.
- **The count:** one hypothesis; register 280 `SEARCH` trials with distinct params, then 5 `VERIFICATION` trials → `search_n == 280`. Register 3 of the 280 again → still 280. Mark 10 as `pruned` and 4 as `errored` at registration → still 280.
- **The laundering pair, end to end:** with B04's `dsr` and the values from v1's committed fixture (`sr_hat = 0.0024061391952578497` per bar, `T = 4344`, `V = 8.659587301602424e-05`) [Certain — read from `te_laundering_winner.json`]: `dsr` at `N = search_n` of a hypothesis holding 280 SEARCH trials is `0.0542` (± 5e-5); at `N = 1.0001` it is `0.5630` (± 5e-5). The numbers are typed into the test; v2 tests don't read v1 files.
- **Ids:** same inputs → same id across two processes. Changing one param → different id. Changing only free text (`statement` wording) → same `trial_id`. Changing `lock_hash` → different `version_id`.
- **Code coordinate:** `lock_hash` equals `sha256sum v2/uv.lock`; `git_commit` equals `git rev-parse HEAD`; with uncommitted changes under `v2/src/`, `code_coordinate()` raises (a result must be tied to committed code).
- **Attacks:** 8 of 8 refused on `hypothesis` and on `trial`.
- **Two sweeps, one hypothesis each:** two hypotheses with 2 and 3 SEARCH trials → `search_n` 2 and 3 (the cross-hypothesis union is B15's job).

## Not in this build
Returns, trade lists, footprints (B09) · lineage and siblings (B15) · the version registry's stages (phase 6).

## Halt if
- "Uncommitted changes raise" makes tests impossible to run during development. (Expected answer: tests pass a fake coordinate explicitly; only the real `code_coordinate()` is strict. If that isn't enough, flag it.)

## Doc rows to update
`COMPONENTS.md` §2 "Trial ontology": ported in B08, with the N rule above stated.
