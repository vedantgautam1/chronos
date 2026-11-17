```yaml
id: B01
title: v2 project scaffold, core helpers, automatic tests
size: M
model: opus
who: founder          # run by hand: the loop doesn't exist until B05
needs: [G0]
ticks: 3
touches:
  - v2/pyproject.toml
  - v2/uv.lock
  - v2/README.md
  - v2/src/chronos2/__init__.py
  - v2/src/chronos2/core/**
  - v2/tests/core/**
  - v2/tests/test_environment.py
  - v2/tests/test_workflow_file.py
  - v2/tests/conftest.py
  - v2/tools/v1_oracle/README.md
  - .github/workflows/v2.yml
  - scratch/.gitkeep
  - docs/drafts/.gitkeep
may_modify_tests: []
adds_dependencies: [numpy, scipy, pandas, pyarrow, pytest, ruff, pyyaml]
```

# B01 — v2 project scaffold, core helpers, automatic tests

## Why
Everything later stands on this: a separate v2 project that can't see v1, two small helpers every later build uses (time rules; a stable fingerprint of any piece of data), and tests that run by themselves on every change. The workflow is written **once, here, with every job later builds will need**, so no later build has a reason to touch it.

## Read first
- Master doc §10: V2-D29, V2-D45. `BUILD_NOTES.md` §1 (all code).
- v1 `src/chronos/moirai/config.py` (`_canonical`, `config_hash`) and `src/chronos/run.py` (`_canonical`, `_config_hash`): the idea to port.
- `.github/workflows/tests.yml` (the v1 job; leave it untouched).

## Deliver
1. Branch `v2-build`, created from `main` after gate G0.
2. `v2/pyproject.toml`: project `chronos2`, `requires-python = ">=3.14,<3.15"`, src layout (`v2/src/chronos2`), runtime deps `numpy`, `scipy`, `pandas`, `pyarrow`; dev group `pytest`, `ruff`, `pyyaml`. `v2/uv.lock` committed. No `addopts`, no markers that deselect.
3. `core/timeutil.py`: `require_utc(dt)` (raises on naive or non-UTC), `assert_process_utc()` (raises unless the process time zone is UTC), `HalfOpen(start, end)` (both tz-aware UTC, `start < end`, `contains(ts)` true for `start <= ts < end`).
4. `core/canonical.py`: `canonical_json(obj) -> str` and `content_hash(obj) -> str` (SHA-256 hex). Sorted keys; `Decimal` → its string; `datetime` → ISO-8601 UTC with `Z`; floats by `repr`; tuples as lists; enums by value. Raises on NaN, infinities, naive datetimes, sets, and unknown types.
5. `v2/tests/conftest.py`: empty apart from a docstring saying that hooks which change test collection are forbidden (B02 enforces it).
6. `.github/workflows/v2.yml`, on `pull_request` and on pushes to `v2-build` and `main`, with `permissions: contents: read` at the top (these jobs run the pull request's own code, so they get a read-only token and use no secrets). Jobs:
   - **tests**: `TZ=UTC`; `astral-sh/setup-uv`; a `postgres:16` service with a health check, and `CHRONOS2_TEST_DSN` exported; `uv sync --frozen --all-groups` in `v2/`; `uv run pytest -q -rsx --junitxml=junit.xml`; the junit file uploaded as an artifact.
   - **lint**: `ruff check`.
   - **v1-oracle**: in the **v1** environment (repo root, `uv sync --frozen`), run every `v2/tools/v1_oracle/dump_*.py` and fail if `git diff --exit-code v2/tests/known_answers/v1_oracle/` is non-empty. With no dump scripts yet, it passes.
7. `v2/README.md`: how to run the tests, in under ten lines. `v2/tools/v1_oracle/README.md`: what an oracle dump script is (B06 writes the first).

## Steps
1. Scaffold; lock; one smoke test (`import chronos2`). Commit.
2. Commit the known-answer tests below (red).
3. `timeutil.py`, `canonical.py` → green.
4. The workflow. Open the pull request; see all three jobs green.
5. Report.

## Known answers and checks
- `content_hash({"b": 1, "a": [1.0, Decimal("0.10")]}) == content_hash({"a": [1.0, Decimal("0.10")], "b": 1})`; changing `1.0` to `1.0000000000000002` changes the hash; `float("nan")` and a naive `datetime` each raise `ValueError`.
- `canonical_json({"t": datetime(2026, 4, 1, tzinfo=UTC)}) == '{"t":"2026-04-01T00:00:00Z"}'`.
- `HalfOpen(2026-03-31T00:00Z, 2026-04-01T00:00Z)`: contains `2026-03-31T23:59:59Z`; does **not** contain `2026-04-01T00:00:00Z`; constructing it with a bare `date` raises.
- `assert_process_utc()` passes under `TZ=UTC` and raises under `TZ=America/Toronto` (run in a subprocess).
- Environment test: Python is 3.14; `importlib.util.find_spec("chronos") is None` (v1 isn't importable from the v2 environment).
- The workflow file contains `permissions:` with only `contents: read`, and no `secrets.` reference (asserted by a test that reads the file).
- On GitHub: three green jobs on the pull request. The **tests** job's log shows a Postgres connection succeeded (one trivial `SELECT 1` test, so B09 inherits a working service).

## Not in this build
The guards (B02) · any use of Postgres beyond `SELECT 1` (B09) · the loop (B03–B05).

## Halt if
- Any listed dependency won't install on Python 3.14 (V2-D45 says fall back to 3.13: that changes a locked decision's wording, so flag it, don't just do it).

## For the gate
Status board: "v2 code skeleton" → in progress. `CODEBASE.md`: the real `v2/` tree.
