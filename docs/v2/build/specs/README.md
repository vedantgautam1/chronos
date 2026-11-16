# BUILD SPECS — how to read one, and the rules every build follows

One file per build. A build session reads: `CLAUDE.md` (automatic), the master doc §1–§2, **this file**, **its own spec**, and the files its spec lists under "Read first". Nothing else is needed, and nothing else should be loaded.

*Revised 16 Nov after the G0 red team (`gates/G0-redteam.md`): roles are separated by what each may write, checks run from the base branch, and builds no longer touch the master doc.*

## The header

```yaml
id: B06                      # matches LADDER.yaml
title: ...
size: M                      # S or M (BLUEPRINT 2.7)
model: opus                  # the loop obeys this; by hand, /tick refuses to start on another model
who: loop                    # loop = may run unattended · founder = needs the founder present
needs: [G1]
ticks: 3                     # build ticks allowed; one more is an overrun and a halt
touches:                     # the ONLY paths the builder may change (globs)
  - v2/src/chronos2/stats/**
may_modify_tests: []         # earlier test files this build may edit (normally none)
```

## Who may write what

Every commit on a build branch ends with a trailer, `Chronos-Role: builder` or `Chronos-Role: reviewer`. A commit without one fails the checks.

| Role | May change | May set the status to |
|---|---|---|
| **Builder** | the spec's `touches` · `docs/v2/build/reports/<id>.md` · one new section at the top of `docs/v2/CHANGELOG.md` · `docs/v2/build/status/<id>.json` | `building`, `needs_review`, `halted` |
| **Reviewer** | `docs/v2/build/reviews/<id>-r<n>.md` · `docs/v2/build/status/<id>.json` · `docs/v2/build/LEDGER.md` | `changes_requested`, `passed`, `merged`, `halted` |

Nobody on a build branch may change: the master doc, `CLAUDE.md`, `.claude/`, `.github/`, `v2/tools/guards/`, anything in `docs/v2/build/` except the paths above and any its spec lists (and never a spec, the ladder, the blueprint, the cards or `gates/`, whatever a spec lists), `v2/config/protected/`, `CODEOWNERS`. Those change only in pull requests the founder approves (gate pull requests, or `spec/…` branches for corrections).

**These rules are checked by code that runs from the base branch (`v2-build`), not from the pull request** (build B02), so a build can't loosen the checks that judge it, and editing your own spec on your branch changes nothing.

`CODEBASE.md`, `COMPONENTS.md` and `BUILD_NOTES.md` are ordinary paths: a build may change them only if its `touches` lists them. The master doc's status board (§2), decisions (§10) and open questions (§12) are updated **at gates**, from the build reports; a build that has something for them says so in its report under "For the gate".

## Rules for the builder (every build)

1. **Claim first.** The branch is `claude/<id>` in lower case, nothing else (`claude/b06`). Take the lock (`/tick` does it), create the branch from `v2-build`, write `status/<id>.json` with state `building`, push, open a draft pull request into `v2-build`. Then work.
2. **Tests before code.** Step 1 of every spec commits the known-answer tests exactly as the spec states them. Run them; they must fail because the code doesn't exist or is wrong, not because of a typo. Paste the failing summary line into the report. A known answer in a spec is never changed by the builder: if you think it is wrong, halt (rule 9).
3. **One step, one commit.** After each numbered step: run the tests, commit (`B06 step 3: …`, with the trailer), push. Each push renews the lock. If usage or time runs out, the next session resumes from the last commit. Never leave uncommitted work.
4. **Stay inside `touches`.** Needing another file means the spec is wrong: halt.
5. **Never:** edit anything under `src/`, `tests/`, the root `pyproject.toml` or `uv.lock` (v1 is frozen) · change, rename or delete any test file that already exists on `v2-build` (new tests go in new files; the header's `may_modify_tests` is the only exception) · skip, deselect or xfail a test · define a pytest hook (`pytest_*`) or add a pytest option · loosen a tolerance or a threshold · choose or change a seed after seeing a result · add a dependency the spec doesn't list · import `chronos` (v1) from v2 code · write a review file · merge anything.
6. **Conventions** (CLAUDE.md): tz-aware UTC everywhere; half-open `[start, end)` ranges with full timestamps, never bare dates; Decimal for money, float64 for series maths; every money amount is configuration; run with `TZ=UTC`.
7. **Finish.** All of these pass locally from `v2/`: `TZ=UTC uv run pytest -q`, `uv run ruff check .`, `uv run python tools/guards/run_all.py`. Then write `reports/<id>.md` from the template, add the CHANGELOG section, set the status to `needs_review`, mark the pull request ready.
8. **The report is for a non-technical reader first.** First paragraph: what now exists that didn't before, in plain words. Then: red-then-green evidence; every deviation from the spec (there should be none); "For the gate" (status-board changes, new traps, adopted libraries, open questions); the actuals (ticks used, lines of code and tests, wall-clock time).
9. **Halt, don't improvise,** when: the spec is ambiguous or wrong · two reasonable designs would give different results · a known answer can't be reproduced · the size budget won't hold · anything conflicts with the master doc · a protected value would have to change. Halting = set the status to `halted` with a one-paragraph reason and the options you see, push, stop.

## Rules for the reviewer (every build)

The reviewer is a different session from the builder, on Opus, and has not seen the builder's reasoning. It takes the lock for the review, like any other action.

1. Check out the branch. **Run everything yourself**: tests, lint, guards. Don't trust the report's numbers.
2. Read the diff against the spec **as it is on `v2-build`**, step by step. Every "Deliver" item exists; every "Known answers" item is a test that asserts exactly the stated value and tolerance; nothing outside `touches` changed.
3. **Break one thing on purpose.** Pick the function the build is about, change one operator or constant locally, and confirm a test goes red. Revert. If nothing goes red, the build fails review.
4. Check the hard rules (CLAUDE.md 1–10) and the standing rules above. Look specifically for: a tolerance wider than the spec's; a seed not in the spec; a test that asserts something weaker than the spec; a skipped, deselected or xfail test; look-ahead; a bare date used as a range end; a local-time read.
5. Write `reviews/<id>-r<round>.md`: the code commit reviewed (its hash), verdict `PASS` or `CHANGES`, findings as a numbered list (each with file, line, what is wrong, what the spec says), and what you broke in step 3 and which test caught it.
6. `PASS` → set the status to `passed`. When the automatic checks are green on that commit: add one last commit that writes the ledger row and sets the status to `merged`, wait for green again, then squash-merge into `v2-build`. (If a session dies between that commit and the merge, the next tick sees `merged` on an unmerged branch and finishes the merge.) `CHANGES` → set `changes_requested`. A second `CHANGES` on the same build → `halted`.
7. The reviewer never edits code or tests, even for a one-character fix.

**What is enforced and what isn't.** The checks reject: a commit with no role trailer; a builder commit that writes a review file or sets `passed`/`merged`; a reviewer commit that touches code; a `passed` or `merged` status with no review file naming the current code commit. What no check can prove is that the session calling itself "reviewer" is a different session from the builder: both act with the same GitHub identity. That separation comes from the loop starting a fresh session for each action, and it stays a guard rail until a reviewer with its own identity exists (BLUEPRINT 2.5).

## Sections of a spec

**Why** · **Read first** · **Deliver** · **Steps** · **Known answers and checks** (written before the code; these are the pass/fail rules of V2-D25) · **Not in this build** · **Halt if** · **For the gate**.

Tags on facts follow the rest of the pack: [Certain — run] = executed and seen · [Certain — read] = read in the source · [Likely] · [Guessing].
