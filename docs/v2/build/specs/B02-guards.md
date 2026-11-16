```yaml
id: B02
title: The guards — tripwire checks on every pull request, protected values, code owners
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
Three red-team passes shaped this build (`gates/G0-redteam.md`).

The first found that a check which runs from the pull request's own copy of the checking code, or reads its limits from the pull request's own copy of the spec, can be loosened by the build it judges. So the guard **code** and the **spec** are always read from the base branch.

The second found that the first fix leaned on a GitHub feature that no longer does what the plan assumed, and that several protections had been called walls when they are tripwires. So this spec says plainly what each guard is: **a tripwire that catches mistakes and shortcuts, not proof against a session that sets out to cheat.** The walls are elsewhere: GitHub's own rules on `main` (B05), and the audit at each gate.

**Two GitHub facts this design rests on** [Certain — GitHub changelog, read 16 Nov 2026]:
- Since 8 Dec 2025 a `pull_request_target` workflow is always taken from the repository's **default branch** (`main`), whatever the pull request's base branch is. A guard workflow living on `v2-build` would never run that way.
- From 2 Dec 2026 `pull_request_target` is **blocked by default in public repositories**. This repository is public.

So the guards run on the ordinary `pull_request` event. The consequence, stated honestly: on that event the **workflow file itself** comes from the pull request, so a pull request that edits `.github/` can change what runs. What stops that is not this build; it is the founder's required review of any change under `.github/` (CODEOWNERS here, made binding by the ruleset in B05).

## Read first
- `gates/G0-redteam.md`, all three passes. `specs/README.md` ("Who may write what"). BLUEPRINT 2.4–2.6.
- GitHub docs, **read fresh at build time; do not design from memory** (the first design of this build was wrong for exactly that reason): events that trigger workflows (`pull_request`: which workflow file runs, which commit is checked out by default), CODEOWNERS (which branch's file applies), default `GITHUB_TOKEN` permissions.

## Deliver
1. `.github/workflows/v2-guards.yml`, on **`pull_request`**, with `permissions: contents: read` and no secrets. Two jobs:
   - **guards**: checks out the pull request with full history; then checks out the guard code **at the base commit** (`github.event.pull_request.base.sha`) into a separate folder outside the work tree; runs that copy with `python -I` against the pull request's commits, which it reads through `git` as data and never imports or executes.
     - *Bootstrap rule:* if the base commit has no guard code at all, the job runs the pull request's own copy and says so in bold at the top of its summary. By construction that happens exactly twice: on this build's own pull request, and on the first gate move (`main` has no guard code until G1 lands). Both happen with the founder present.
   - **earlier-tests**: the earlier builds' tests, run as they were approved, against this pull request's code. It starts from a clean checkout of **the base commit's** `v2/` folder and takes from the pull request only: `v2/src/chronos2/**`, `v2/migrations/**`, `v2/pyproject.toml`, `v2/uv.lock`, and any test file the base spec lists in `may_modify_tests`. Everything else under `v2/` (the tests, every `conftest.py`, any `pytest.ini`, `tox.ini` or `setup.cfg`, anything else beside the package) is the base's copy, so nothing the pull request added there is present. It then runs pytest with plugin auto-loading off (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`), the base's pytest settings (`-c` pointing at a saved copy of the base's `pyproject.toml`), `--confcutdir=v2/tests`, `-o addopts=""`, `-p no:cacheprovider`, and the same Postgres service as B01's tests job. **It fails unless the set of test ids that ran equals the set collected on an untouched base checkout.** Passes trivially when the base has no `v2/tests/`.
2. Guards under `v2/tools/guards/` (each a function returning findings; `run_all.py` exits non-zero on any, and prints a plain-language summary):
   - `v1_frozen`: the diff against `origin/v1-final` on `src`, `tests`, root `pyproject.toml`, `uv.lock` is empty. [Certain — run 16 Nov: empty on `main` today.]
   - `branch_kind`: classify by head and base.
     - `claude/bNN` into `v2-build` → **build**.
     - `lane/…` into `v2-build` → **lane** (may touch only `scratch/**`, `docs/drafts/**`).
     - `spec/…` into `v2-build` → **spec correction** (may touch only `docs/v2/build/**`).
     - `doc/…` into `v2-build` or `main` → **documents** (may touch only `docs/**` outside `docs/v2/build/specs/`, plus `CLAUDE.md`).
     - `gate/gN` into `v2-build` → **gate write-up** (may touch only `docs/v2/build/gates/**`, `docs/v2/build/sabotage/**`, `docs/v2/build/LEDGER.md` and the five v2 docs; may contain a merge of `main`).
     - `v2-build` into `main` → **gate move** (requires `docs/v2/build/gates/G<n>-report.md` for the next gate in the diff).
     - Anything else → fail. Only branches in this repository count; a pull request from a fork always fails.
   - `scope` (build branches): every changed path is allowed for the role of the commit that changed it (`specs/README.md` table), with `touches` read from the spec **at the base commit**.
   - `roles`: every commit carries a `Chronos-Role` trailer; builder commits don't touch `reviews/` or `LEDGER.md` and don't set status `passed`/`merged`/`changes_requested`; reviewer commits touch nothing but `reviews/`, `status/`, `LEDGER.md`; status `passed` or `merged` requires a review file with verdict `PASS` whose "code commit reviewed" equals the last builder commit. **A trailer is a label a session puts on its own commit. This guard catches a session doing the wrong role's work by mistake; it can't catch one that labels its commits falsely.**
   - `frozen_files`: no file that exists at the base commit under `v2/tests/`, `v2/tools/v1_oracle/` or `v2/migrations/` may be changed, renamed or deleted, unless the base spec lists it in `may_modify_tests`. New files may be added. This is a comparison of file lists and contents; it is what stops a later build from quietly weakening an earlier build's assertion or emptying an earlier build's oracle script (several builds share those folders, so `scope` alone doesn't).
   - `plumbing` (text scans of the pull request's files, never importing them; each is a tripwire with known ways around it, listed in "What these guards don't stop"):
     - no file named `CLAUDE.md`, `CLAUDE.local.md` or `AGENTS.md`, and no `.claude` folder, anywhere except the repository root (an instruction file placed in a source folder would be read by later sessions working there);
     - no function named `pytest_*` and no `pytest_plugins` under `v2/`; every `autouse=True` fixture in the diff is printed for the reviewer;
     - `v2/pyproject.toml`: `[tool.pytest.ini_options]` holds only `testpaths` and `pythonpath`; no `[project.entry-points]`; the set of dependency names (all groups) changes only by the names in the base spec's `adds_dependencies` header (absent = none); any change under `[tool.ruff]` is printed;
     - `v2/uv.lock`: every package added to or removed from the lock is printed by name and version (a lock file can pull in a library, or a different copy of one, that `pyproject.toml` never names); a change to the lock in a build whose spec has no `adds_dependencies` fails.
   - `protected`: a lane branch never changes a founder-owned path (deliverable 3). A build branch changes one only if its spec at the base commit lists that path in `touches` (B01–B05, B08, B09 and B20 do). Never, on any build or lane branch, whatever a spec says: the master doc, `docs/v2/build/specs/`, `LADDER.yaml`, `BLUEPRINT.md`, `BUILD_CARDS.md`, `docs/v2/build/gates/`. When `v2/config/protected/` changes on any branch, the guard prints the old and new values, so the founder sees the diff he is approving (CLAUDE.md hard rule 7).
3. `.github/CODEOWNERS`, written as **"everything is the founder's, except the folders builds work in"**. Listing only the files to protect is how the earlier drafts kept missing some (the lock file, the loop's own code, a `conftest.py` beside the package). So:
   - first line: `*` owned by the founder's account;
   - then these paths with **no owner** (later lines win in a CODEOWNERS file): `/v2/src/chronos2/`, `/v2/tests/`, `/v2/migrations/`, `/v2/tools/v1_oracle/`, `/v2/tools/sabotage/`, `/v2/config/venues/`, `/docs/v2/build/reports/`, `/docs/v2/build/reviews/`, `/docs/v2/build/status/`, `/docs/v2/build/sabotage/`, `/docs/v2/build/LEDGER.md`, `/docs/v2/CHANGELOG.md`, `/docs/v2/COMPONENTS.md`, `/docs/v2/BUILD_NOTES.md`, `/docs/v2/CODEBASE.md`, `/docs/v2/research/`, `/docs/drafts/`, `/scratch/`;
   - then, owned by the founder again inside those: `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md` and `.claude/` at any depth; `/v2/src/chronos2/fixtures/touchstones/`.
   - Everything else is therefore the founder's: `.github/`, the root `CLAUDE.md` and `.claude/`, the master doc, the specs, ladder, blueprint, cards, handbook and `gates/`, `v2/tools/guards/`, `v2/tools/loop/`, `v2/config/protected/`, `v2/pyproject.toml`, `v2/uv.lock`, and anything directly under `v2/` or `v2/src/` beside the package.
   - **Until B05 this file has no force:** nothing requires a code owner's review yet, and every session acts as the founder.
4. `v2/config/protected/validation.yaml`, containing only numbers the master doc has already locked, each with its decision id:
   - `seal: {BTC: "2026-04-01T00:00:00Z", ETH: "2026-04-01T00:00:00Z"}` (V2-D38)
   - `stress_friction_multiplier: 2.0` (V2-D35)
   - `adverse_funding_percentile: 95`; `adverse_funding_hourly_rate: {}` (V2-D39; empty until the spike computes it)
   - `fragmentation_window_days: 90` (V2-D31)
   - `sealed_confirm_min_trades: 200` (V2-D38)
5. A schema test for that file under `v2/tests/tools/guards/`. (Loading it at run time belongs to the builds that use it: B11, B14, B16, B18.)

## What these guards don't stop (and what does)
Written here so nobody later mistakes a green guard for proof.

| A session determined to cheat could… | Not stopped by the guards because… | What does catch it |
|---|---|---|
| Label a commit `Chronos-Role: reviewer` and write its own review | A trailer is self-declared; builder and reviewer use the same GitHub account | The gate audit checks every review against the session each commit came from; a reviewer with its own GitHub identity (a founder decision at G1) would make it a wall |
| Neutralise an earlier test from **source** (the package detects it is under test, or an earlier module is changed to return what the test wants) | `earlier-tests` runs the earlier tests unchanged, but against the pull request's package | The reviewer reads the source diff; the sabotage run (B22) at the gate; blind re-derivation at the gate |
| Add a hook, a `pytest.ini`, a `conftest.py` beside the package, or a `sitecustomize.py` | — | **Stopped** for the earlier tests: `earlier-tests` takes only the package, migrations and dependency files from the pull request. (For the build's *own new* tests nothing stops it but the reviewer) |
| Slip a pytest plugin in through the lock file | — | **Stopped** for the earlier tests: plugin auto-loading is off. And the lock diff is printed; the lock file is founder-owned |
| Change the workflow in the same pull request | On `pull_request`, the workflow file comes from the pull request | From B05: `.github/` needs the founder's review before merge |
| Post a fake "guards passed" status | A collaborator account can post statuses | From B05: required checks are pinned to GitHub Actions as their source |

## Steps
1. Guard tests (red): each guard gets throwaway git repositories built in a temp folder.
2. `branch_kind`, `v1_frozen`, `scope`.
3. `roles`, `protected`, `frozen_files`.
4. `plumbing`.
5. `validation.yaml` + schema test; `CODEOWNERS`.
6. The workflow. On this build's own pull request both jobs run under the bootstrap rule (the base has no guard code yet); the report quotes the bold notice.

**The proofs on GitHub are not in this build.** They need this build's guard code to be on the base branch already, so they are the first step of B03, which records them. (Run inside this build they would go red for the wrong reason, and prove nothing.)

## Known answers and checks
One failing and one passing case per rule, in temp repositories:

| Guard | Must fail | Must pass |
|---|---|---|
| `v1_frozen` | a comment added to a v1 file | no v1 change |
| `branch_kind` | `feature/x`; `claude/b6`; `claude/b06-stats`; `gate/g1` touching `v2/src/`; `doc/x` touching `v2/src/`; `v2-build`→`main` without the gate report; a head branch from a fork | `claude/b06`; `lane/notes`; `spec/b10-fix`; `doc/decision-52` touching the master doc; `gate/g1` touching the report and the master doc; `v2-build`→`main` with the gate report |
| `scope` | a build changes a file outside its `touches` | inside |
| `scope` (base spec) | the branch edits its own spec to add a path, then changes that path | — |
| `roles` | a commit with no trailer; a builder commit writing `reviews/b06-r1.md`; a builder commit setting status `merged`; a reviewer commit touching `v2/src/`; status `passed` with a review naming an older code commit | builder then reviewer then merge, in order |
| `frozen_files` | an existing test file with one assertion changed from `==` to `>=`; an existing test file deleted; one renamed; an existing `dump_*.py` emptied; an existing migration edited | a new test file; a new dump script; a new migration; an existing test file changed that the base spec lists in `may_modify_tests` |
| `plumbing` | `v2/src/chronos2/stats/CLAUDE.md`; a `.claude/` folder under `v2/`; a new `conftest.py` defining `pytest_collection_modifyitems`; a test file defining `pytest_runtest_makereport`; `addopts = "-k not slow"`; a dependency added that the base spec doesn't name; a `[project.entry-points.pytest11]` table; a `uv.lock` change in a build with no `adds_dependencies` | a new `conftest.py` with fixtures only; a dependency added that the base spec names in `adds_dependencies` |
| `protected` | a build branch changes `validation.yaml`, a guard or a workflow that its base spec doesn't list; any build branch changes the master doc or a spec, even if its spec lists them | B20 creating the touchstones folder (listed in its base spec) |
| lane | `lane/x` touching `v2/src/chronos2/__init__.py` | `lane/x` touching `scratch/note.md` |

- **Guard code comes from the base:** a temp-repository test in which the pull-request branch replaces `run_all.py` with `exit(0)` and also edits a v1 file → the guards still fail (the runner used the base copy).
- **Bootstrap rule:** with no guard code at the base, the runner uses the head's copy and its summary starts with the notice; with guard code at the base, the head's copy is never used.
- **`earlier-tests`, in a temp repository with one passing and one failing earlier test** (each case must end with the failing test still failing, and the job red): the pull request adds `v2/conftest.py` whose hook name is built from two strings and drops the failing test; adds `v2/pytest.ini` with `python_functions = test_ok`; adds `v2/src/sitecustomize.py` that patches the package; adds a plugin package to `uv.lock` only. (The third red-team pass ran the first two against a simpler version of this job on pytest 9.1.1 and both beat it.) And one case that must be red for the count: the pull request deletes nothing but the run reports fewer test ids than the base's collection.
- **`CODEOWNERS` resolves as intended** (a test that evaluates the file's patterns in order): owned: `.github/workflows/v2.yml`, `v2/uv.lock`, `v2/conftest.py`, `v2/tools/loop/next_action.py`, `v2/src/sitecustomize.py`, `v2/src/chronos2/stats/CLAUDE.md`, `docs/v2/build/specs/B06-stats-core.md`, `v2/config/protected/validation.yaml`. Not owned: `v2/src/chronos2/stats/dsr.py`, `v2/tests/stats/test_dsr.py`, `docs/v2/build/reports/b06.md`, `docs/v2/CHANGELOG.md`.
- `validation.yaml` holds exactly the six keys above with exactly those values; a schema test rejects an unknown key.
- The workflow file contains `permissions:` with only `contents: read`, the string `pull_request_target` nowhere, and no `secrets.` reference (a test reads the file).

## Not in this build
GitHub rulesets and the automation's own identity (B05: they need the founder's clicks, and they are what turn some of these tripwires into walls) · the loop (B03) · mutation testing (B22).

## Halt if
- The base commit's guard code can't be checked out into a separate folder inside a `pull_request` job.
- `earlier-tests` can't be made to run the base's tests against the pull request's package (for example because the base's pytest settings can't be applied with `-c`): say what blocks it and propose the narrowest alternative.
- A CODEOWNERS file can't express "owned by default, with un-owned folders" the way the test above requires.
- Anything in the GitHub docs read at build time contradicts the two facts at the top.

## For the gate
`BUILD_NOTES.md` §1 (this build edits it): "v2 guards run on `pull_request` with guard code and specs read from the base commit (B02). They are tripwires. `pull_request_target` is not used: GitHub takes it from the default branch (since Dec 2025) and blocks it in public repos (from 2 Dec 2026)." Status board: guards built.
