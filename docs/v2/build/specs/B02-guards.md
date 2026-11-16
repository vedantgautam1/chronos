```yaml
id: B02
title: The guards — checks that run from the base branch, protected values, code owners
size: M
model: opus
who: founder          # creates protected values and the rules for who may change what
needs: [B01]
ticks: 3
touches:
  - v2/tools/guards/**
  - v2/tests/tools/guards/**
  - v2/config/protected/**
  - .github/workflows/v2-guards.yml
  - .github/CODEOWNERS
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B02 — The guards

## Why
The G0 red team's central finding: a check that runs from the pull request's own copy of the checking code, or reads its limits from the pull request's own copy of the spec, can be loosened by the very build it judges. So every guard here runs **from the base branch** and reads specs **from the base branch**. And the files that define the rules (guards, workflows, specs, the ladder, the master doc, protected values) get a named owner, the founder, so that GitHub itself refuses a change to them without his review once the automation has its own identity (B05).

## Read first
- `gates/G0-redteam.md` findings 1–4, 12, 16. `specs/README.md` ("Who may write what"). BLUEPRINT 2.4–2.6.
- GitHub docs, read fresh: `pull_request_target` (what it runs and from where), CODEOWNERS (which branch's file applies), rulesets.

## Deliver
1. `.github/workflows/v2-guards.yml`, triggered by **`pull_request_target`** (so the workflow definition and the guard code come from the base branch). It checks out the base branch, fetches the pull request's commits as data, and runs `v2/tools/guards/run_all.py` from the base checkout against them. **It never executes code from the pull request** and uses no secrets.
2. Guards under `v2/tools/guards/` (each a function returning findings; `run_all.py` exits non-zero on any):
   - `v1_frozen`: the diff against `origin/v1-final` on `src`, `tests`, root `pyproject.toml`, `uv.lock` is empty. [Certain — run 16 Nov: empty on `main` today.]
   - `branch_kind`: classify by head and base. `claude/bNN` → **build**. `lane/…` → **lane** (may touch only `scratch/**`, `docs/drafts/**`). `spec/…` → **spec correction** (may touch only `docs/v2/build/**`). `gate/gN` → **gate write-up** (may touch only `docs/v2/build/gates/**`, `docs/v2/build/sabotage/**`, `docs/v2/build/LEDGER.md`, and the five v2 docs: master doc, `BUILD_NOTES.md`, `COMPONENTS.md`, `CODEBASE.md`, `CHANGELOG.md`). Head `v2-build` into base `main` → **gate move** (no scope check; requires `docs/v2/build/gates/G<n>-report.md` for the next gate in the diff). Anything else → fail. Spec corrections and gate write-ups touch founder-owned paths, so GitHub asks for the founder's review on them (deliverable 3).
   - `scope` (build branches): every changed path is allowed for the role of the commit that changed it (`specs/README.md` table), with `touches` read from the spec **on the base branch**.
   - `roles`: every commit carries a `Chronos-Role` trailer; builder commits don't touch `reviews/` or `LEDGER.md` and don't set status `passed`/`merged`/`changes_requested`; reviewer commits touch nothing but `reviews/`, `status/`, `LEDGER.md`; status `passed` or `merged` requires a review file with verdict `PASS` whose "code commit reviewed" equals the last builder commit.
   - `test_set`: collect test ids on the base branch and on the pull request (`pytest --collect-only -q`, run by the **tests** workflow and passed as artifacts; the guard only compares lists). The pull request's ids must be a superset of the base's, except files listed in `may_modify_tests`. From the junit file: zero skipped, zero xfailed. `v2/pyproject.toml` must contain no `addopts`, `-k`, `--deselect` or `-m`; no `conftest.py` may define `pytest_collection_modifyitems`, `pytest_ignore_collect` or `pytest_runtest_setup`.
   - `protected`: a lane branch never changes a founder-owned path (the list in deliverable 3). A build branch changes one only if its spec **on the base branch** lists that path in `touches` (B01, B02, B04 and B20 do; the founder approved those specs, and GitHub still asks for his review of the pull request). Never, on any build or lane branch, whatever a spec says: the master doc, `docs/v2/build/specs/`, `LADDER.yaml`, `BLUEPRINT.md`, `BUILD_CARDS.md`, `docs/v2/build/gates/`. When `v2/config/protected/` changes on any branch, the guard prints the old and new values in its summary, so the founder sees the diff he is approving (CLAUDE.md hard rule 7).
3. `.github/CODEOWNERS` naming the founder's account as owner of: `/.github/`, `/CLAUDE.md`, `/.claude/`, `/docs/v2/CHRONOS_V2.md`, `/docs/v2/build/specs/`, `/docs/v2/build/LADDER.yaml`, `/docs/v2/build/BLUEPRINT.md`, `/docs/v2/build/BUILD_CARDS.md`, `/docs/v2/build/gates/`, `/v2/tools/guards/`, `/v2/config/protected/`, `/v2/src/chronos2/fixtures/touchstones/`.
4. `v2/config/protected/validation.yaml`, containing only numbers the master doc has already locked, each with its decision id:
   - `seal: {BTC: "2026-04-01T00:00:00Z", ETH: "2026-04-01T00:00:00Z"}` (V2-D38)
   - `stress_friction_multiplier: 2.0` (V2-D35)
   - `adverse_funding_percentile: 95`; `adverse_funding_hourly_rate: {}` (V2-D39; empty until the spike computes it)
   - `fragmentation_window_days: 90` (V2-D31)
   - `sealed_confirm_min_trades: 200` (V2-D38)
5. A schema test for that file under `v2/tests/tools/guards/`. (Loading it at run time belongs to the builds that use it: B11, B14, B16, B18.)

## Steps
1. Guard tests (red): each guard gets throwaway git repositories built in a temp folder.
2. `branch_kind`, `v1_frozen`, `scope`.
3. `roles`, `protected`.
4. `test_set`.
5. `validation.yaml` + schema test; `CODEOWNERS`.
6. The workflow. **Prove it on GitHub** with three scratch pull requests into `v2-build`, each closed afterwards, URLs in the report: (a) `claude/b98` that edits `src/chronos/__init__.py`; (b) `claude/b98` that edits its own spec to widen `touches` and then uses the wider scope; (c) `claude/b98` that adds a `conftest.py` hook deselecting one B01 test. All three must show a red **guards** check.

## Known answers and checks
One failing and one passing case per rule, in temp repositories:

| Guard | Must fail | Must pass |
|---|---|---|
| `v1_frozen` | a comment added to a v1 file | no v1 change |
| `branch_kind` | branch `feature/x`; `claude/b6`; `claude/b06-stats`; `gate/g1` touching `v2/src/`; `v2-build`→`main` without the gate report | `claude/b06`; `lane/notes`; `spec/b10-fix`; `gate/g1` touching the report and the master doc; `v2-build`→`main` with the gate report |
| `scope` | a build changes a file outside its `touches` | inside |
| `scope` (base spec) | the branch edits its own spec to add a path, then changes that path | — |
| `roles` | a commit with no trailer; a builder commit writing `reviews/b06-r1.md`; a builder commit setting status `merged`; a reviewer commit touching `v2/src/`; status `passed` with a review naming an older code commit | builder then reviewer then merge, in order |
| `test_set` | a base test id missing from the pull request; one skipped test; `addopts = "-k not slow"` in `pyproject.toml`; a `conftest.py` with `pytest_collection_modifyitems` | a new test added |
| `protected` | a build branch changes `validation.yaml`, a guard or a workflow that its base spec doesn't list; any build branch changes the master doc or a spec, even if its spec lists them | B20 creating the touchstones folder (listed in its base spec) |
| lane | `lane/x` touching `v2/src/chronos2/__init__.py` | `lane/x` touching `scratch/note.md` |

- `validation.yaml` holds exactly the six keys above with exactly those values; a schema test rejects an unknown key.
- The three GitHub proofs are red, and the workflow log shows the guard code path is the base checkout.

## Not in this build
GitHub rulesets and the automation's own identity (B05: they need the founder's clicks) · the loop (B03) · mutation testing (B22).

## Halt if
- `pull_request_target` can't see the pull request's commits without executing its code, or needs a secret.
- The test-id artifact can't be passed from the tests workflow to the guards workflow safely. (Fallback to propose: the guard re-collects test ids itself from a static scan of test files, which is weaker; say so.)

## For the gate
`BUILD_NOTES.md` §1: "v2 guards run from the base branch (B02); a build can't change its own checks." Status board: guards built.
