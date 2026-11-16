```yaml
id: B01
title: v2 project scaffold, automatic tests, the guards
size: M
model: opus
who: founder          # run by hand: the loop doesn't exist until B02
needs: [G0]
ticks: 3
touches:
  - v2/**
  - .github/workflows/v2.yml
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B01 — v2 project scaffold, automatic tests, the guards

## Why
Everything later stands on this: a separate v2 project that can't touch v1, tests that run by themselves on every change, and guards that fail loudly when a rule is broken. A guard that doesn't work gives false safety, so each guard is itself tested with a case it must catch.

## Read first
- Master doc §10: V2-D29, V2-D45. `BUILD_NOTES.md` §1 (all code).
- v1 `src/chronos/moirai/config.py` (`_canonical`, `config_hash`) and `src/chronos/run.py` (`_canonical`, `_config_hash`): the idea to port.
- `.github/workflows/tests.yml` (the v1 job; leave it untouched).
- `BLUEPRINT.md` 2.4–2.6.

## Deliver
1. Branch `v2-build`, created from the commit tagged `gate/G0`.
2. `v2/pyproject.toml`: project `chronos2`, `requires-python = ">=3.14,<3.15"`, src layout (`v2/src/chronos2`), runtime deps `numpy`, `scipy`, `pandas`, `pyarrow`; dev deps `pytest`, `ruff`, `pyyaml`. `v2/uv.lock` committed.
3. `v2/src/chronos2/__init__.py`; `core/timeutil.py`: `require_utc(dt)` (raises on naive or non-UTC), `assert_process_utc()` (raises unless the process time zone is UTC), `HalfOpen(start, end)` (both tz-aware UTC, `start < end`, `contains(ts)` true for `start <= ts < end`).
4. `core/canonical.py`: `canonical_json(obj) -> str` and `content_hash(obj) -> str` (SHA-256 hex). Sorted keys; `Decimal` → its string; `datetime` → ISO-8601 UTC with `Z`; floats by `repr`; tuples as lists; enums by value. Raises on NaN, infinities, naive datetimes, sets, and unknown types.
5. Guards under `v2/tools/guards/`, each a small script with a `main()` that exits non-zero on failure, plus `run_all.py`:
   - `v1_frozen.py`: `git diff --quiet origin/v1-final -- src tests pyproject.toml uv.lock` must be empty. [Certain — run 16 Nov: it is empty on `main` today.]
   - `scope.py`: reads the build id from the branch name (`claude/b04-…` → B04), loads that spec's `touches` + the always-allowed paths (`specs/README.md`), and fails if the diff against `v2-build` touches anything else.
   - `test_integrity.py`: any file under `v2/tests/` that exists on `v2-build` may not be modified or deleted unless listed in `may_modify_tests`.
   - `protected.py`: any change under `v2/config/protected/`, `v2/migrations/protected/` or `v2/src/chronos2/fixtures/touchstones/` fails unless the pull request carries the label `founder-approved`.
6. `.github/workflows/v2.yml`, on pull requests and on pushes to `v2-build` and `main`: job **tests** (`TZ=UTC`, `astral-sh/setup-uv`, `uv sync --frozen` in `v2/`, `uv run pytest -q`, with a `postgres:16` service declared now for B07); job **guards** (full fetch, fetch `v1-final`, `run_all.py`); job **lint** (`ruff check`).
7. `v2/README.md`: how to run the tests and the guards, in under ten lines.

## Steps
1. Scaffold the project; lock; one smoke test (`import chronos2`). Commit.
2. Commit the known-answer tests below (red).
3. `timeutil.py`, `canonical.py` → green.
4. The four guards, each with tests that build a throwaway git repository in a temp folder.
5. The workflow. Open the pull request and see all three jobs green.
6. **Prove the v1 guard on GitHub:** push a scratch branch `claude/b01-guard-proof` that adds one comment to `src/chronos/__init__.py`, open a draft pull request, record the red **guards** job's URL in the report, close the pull request and delete the branch.
7. Docs, report.

## Known answers and checks
- `content_hash({"b": 1, "a": [1.0, Decimal("0.10")]}) == content_hash({"a": [1.0, Decimal("0.10")], "b": 1})`; changing `1.0` to `1.0000000000000002` changes the hash; `float("nan")` and a naive `datetime` each raise `ValueError`.
- `canonical_json({"t": datetime(2026, 4, 1, tzinfo=UTC)}) == '{"t":"2026-04-01T00:00:00Z"}'`.
- `HalfOpen(2026-03-31T00:00Z, 2026-04-01T00:00Z)`: contains `2026-03-31T23:59:59Z`; does **not** contain `2026-04-01T00:00:00Z`; constructing it with a bare `date` raises.
- `assert_process_utc()` passes under `TZ=UTC` and raises under `TZ=America/Toronto` (run in a subprocess).
- Environment test: Python is 3.14; `importlib.util.find_spec("chronos") is None` (v1 isn't importable from the v2 environment).
- Guard tests, one failing and one passing case each: v1 file edited → fail; file outside `touches` → fail, inside → pass; an existing test deleted → fail, a new test added → pass; a file under `v2/config/protected/` changed without the label → fail.
- On GitHub: three green jobs on the B01 pull request; one red **guards** job on the proof branch.

## Not in this build
Postgres use (B07) · the loop (B02) · any statistics.

## Halt if
- Any listed dependency won't install on Python 3.14 (V2-D45 says fall back to 3.13: that changes a locked decision's wording, so flag it, don't just do it).
- The v1 guard isn't empty on a clean checkout.

## Doc rows to update
Master doc §2a row "v2 code skeleton" → In progress (B01 of B01–B18). `CODEBASE.md` "What v2 will add" → the real `v2/` tree. `BUILD_NOTES.md` §1: one line naming the four guards.
