# S18 Skylit — results (5 Nov 2026)

Rules: `PREREGISTERED.md` (committed in `3e7209a` before anything ran). Script: `s18_checks.py`. Raw output: `s18_results.json`. Environment: Python 3.13.18, standard library only, no Skylit key, network calls blocked and recorded by a socket guard.

| Check | Pre-registered rule | Result | Verdict |
|---|---|---|---|
| **C1** test suites pass | `python -I -m unittest discover -s tests`, 0 failures/errors in both repos | agent-kit: 13 import errors; agent-lab: 13 failures, 14 errors, 1 skip | **FAIL as specified**, see note |
| **C2** offline modes make no network call | 0 recorded attempts over 12 offline commands | 0 attempts; all 12 exit 0 | **PASS** |
| **C3** live mode without a key stays off the network | 0 attempts and a refusal | 0 attempts; both commands exit 1 | **PASS** |

## Why C1 failed, and the rerun (a deviation from the pre-registered command, reported as such)

Two causes, neither a defect in Skylit's code:

1. **My command was wrong for a test suite.** `-I` drops the working directory from Python's import path. A repo's own tests must import that repo's package, so every agent-kit test module failed to import. The isolation rule (BUILD_NOTES §1) protects *our* scripts from importing files planted in someone else's folder; it can't be applied to running that folder's own tests. (Trap added to BUILD_NOTES §1.)
2. **agent-lab pins an older agent-kit commit** (`0f82039`, 1 Oct). The natural layout (both repos cloned side by side, kit at its latest commit `0e7b068`) makes 22 lab tests fail and 6 error with a clear "Kit revision must be 0f82039…" message. With no kit present they skip (35 skips, OK). Lab's `docs/checks.md` says that without the pinned kit the kit tests "visibly skip"; that holds only when the kit is absent. A wrong-revision kit gives loud failures, not skips. Minor.

**Rerun with the repos' documented commands** (no `-I`, run from each repo root; lab pointed at a clean worktree of the kit at its pin):
- agent-kit: **167 tests, OK**.
- agent-lab: **345 tests, OK**, no skips.

## What these checks do not cover

Nothing here touches Skylit's service: data accuracy, how its scores and dealer-positioning levels are computed, history quality, or whether any of it predicts prices. Those need a paid key and are out of scope for the current crypto track (see the S18 note in `claude/item-analyses-3.md`). The repos' own docs say the same: authenticated end-to-end checks are still pending.
