```yaml
id: B10
title: Trial store II — ids, code coordinate, hypotheses, SEARCH/VERIFICATION, honest N
size: M
model: opus
who: loop
needs: [B09]
ticks: 3
touches:
  - v2/migrations/**
  - v2/src/chronos2/mnemosyne/**
  - v2/tests/mnemosyne/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B10 — Trial store II

## Why
The single most valuable number v1 produced was a count: the same strategy scored 0.563 when treated as one try and 0.054 once its 280 tries were counted [Certain — v1 fixture]. This build makes that count impossible to get wrong by accident: a result can't be stored without a hypothesis written first, every try says whether it was a search or a check, and the same try filed twice counts once.

## Read first
- v1 `src/chronos/run.py`: `Hypothesis`, `RunKind`, `register_search`, `compute_search_n` and their docstrings (lines ~40–130 and ~290–335). v1 `tests/hephaestus/test_run.py` for the cases worth keeping.
- `BUILD_NOTES.md` §6, the first five bullets. Master doc §10: V2-D03, V2-D31, V2-D42 (code coordinate only; the data footprint is B11).

## The rules (fixed here)
- A **hypothesis** is registered before any trial: `statement`, `prediction`, `strategy_class`, and, for a search, the grid as structured data `{axis: [values]}` (no string parsing in v2).
- A **trial** has a `kind`, always given explicitly: `SEARCH` (one point of a sweep over one hypothesis) or `VERIFICATION` (a check on a chosen candidate: cost stress, a null draw, a sub-window, a re-run).
- **A trial is registered when it starts, before it has a result.** The trial row is its identity and never changes. What happens next goes into an append-only **event** table: `started`, then one of `completed`, `pruned`, `errored`, `partial`. (Rows can't be updated, so a status stored on the trial row itself could never move from "started" to "completed"; and a run that crashed before registering would never be counted.)
- **Honest N** for a hypothesis = the number of **distinct** `SEARCH` trials registered under it, **whatever happened to them afterwards**. Rationale: a pruned try was looked at and rejected, which is selection; counting crashed tries too can only raise the bar. `VERIFICATION` trials never count.
- **Ids come from content.**
  - `code_coordinate = {git_commit, lock_hash, engine}`: `lock_hash` is the SHA-256 of `v2/uv.lock`; `engine` is a name and version string (for now `"none"`).
  - `version_id = content_hash({strategy_class, params, code_coordinate})`.
  - `trial_key = content_hash({strategy_class, kind, params, dataset_hash, window, cost_config_hash, seed, code_coordinate})`: the try itself, whoever filed it.
  - `trial_id = content_hash({hypothesis_id, trial_key})`.
  - Free text is in none of them. Registering the same trial twice returns the first record and doesn't change N.
- v1's JSONL records are never imported.

## Deliver
1. `0002_ontology.sql`: tables `mnemosyne.hypothesis`, `mnemosyne.trial`, `mnemosyne.trial_event`, all append-only with row hashes and journal lines (B09's machinery); `trial.kind` a Postgres enum; `trial.hypothesis_id` a foreign key (no orphan trials); `trial_id` the primary key; `trial_key` stored and indexed; `trial_event.state` in `started|completed|pruned|errored|partial`, at most one terminal event per trial (a unique index), and `started` written in the same transaction as the trial row.
2. `mnemosyne/ids.py`: `code_coordinate()`, `version_id(...)`, `trial_key(...)`, `trial_id(...)`.
3. `mnemosyne/ontology.py`: `register_hypothesis(...)`, `start_trial(...)` (requires `kind`; no default), `finish_trial(trial_id, state)`, `search_n(hypothesis_id)`, `trials_for(hypothesis_id, kind=None)`, `state_of(trial_id)`.
4. Tests.

## Steps
1. Commit the tests below (red).
2. Migration `0002`.
3. `ids.py`, `ontology.py` → green.
4. Run B09's attack list against the two new tables (a parametrised re-use of that test, not an edit of it).
5. Docs, report.

## Known answers and checks
- **No hypothesis, no trial:** `start_trial` with an unknown `hypothesis_id` raises; nothing is stored.
- **Kind is explicit:** `start_trial(...)` without `kind` is a `TypeError`.
- **The count:** one hypothesis; start 280 `SEARCH` trials with distinct params, then 5 `VERIFICATION` trials → `search_n == 280`. Start 3 of the 280 again → still 280. Finish 10 as `pruned` and 4 as `errored`, and leave 6 with no terminal event (crashed before finishing) → still 280.
- **Lifecycle:** `state_of` returns `started` right after `start_trial`; `completed` after `finish_trial(…, "completed")`; a second terminal event for the same trial is refused by the database.
- **The laundering pair, end to end:** with B06's `dsr` and the values of v1's committed fixture, typed into the test (v2 tests don't read v1 files): `sr_hat = 0.0024061391952578497` per bar, `T = 4344`, `V = 8.659587301602424e-05`, `skew = 0.7203182819604969`, `kurt = 16.842229132109118` [Certain — computed from `te_laundering_winner.json` with v1's functions, 16 Nov]. `dsr` at `N = search_n` of a hypothesis holding 280 SEARCH trials is `0.05423064441493044`; at `N = 1.0001` it is `0.563048882547666`; both to 1e-12. (Without the skew and kurtosis the values are 0.05438 and 0.56300: a test that passes with those is wrong.)
- **Ids:** same inputs → same id across two processes. Changing one param → different `trial_key` and `trial_id`. Changing only free text (`statement` wording) → same ids. Changing `lock_hash` → different `version_id`. The same try filed under two hypotheses → same `trial_key`, different `trial_id`.
- **Code coordinate:** `lock_hash` equals `sha256sum v2/uv.lock`; `git_commit` equals `git rev-parse HEAD`; with uncommitted changes under `v2/src/`, `code_coordinate()` raises (a result must be tied to committed code).
- **Attacks:** 8 of 8 refused, with B09's error codes, on `hypothesis`, `trial` and `trial_event`.
- **Two sweeps, one hypothesis each:** two hypotheses with 2 and 3 SEARCH trials → `search_n` 2 and 3 (the cross-hypothesis union is B18's job).

## Not in this build
Returns, trade lists, footprints (B11) · lineage and siblings (B18) · the version registry's stages (phase 6).

## Halt if
- "Uncommitted changes raise" makes tests impossible to run during development. (Expected answer: tests pass a fake coordinate explicitly; only the real `code_coordinate()` is strict. If that isn't enough, flag it.)

## For the gate
`COMPONENTS.md` §2 "Trial ontology" (this build edits that row): ported in B10, with the N rule above stated.
