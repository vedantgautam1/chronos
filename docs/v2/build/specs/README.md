# BUILD SPECS — how to read one, and the rules every build follows

One file per build. A build session reads: `CLAUDE.md` (automatic), the master doc §1–§2, **this file**, **its own spec**, and the files its spec lists under "Read first". Nothing else is needed, and nothing else should be loaded.

*Revised 16 Nov after three red-team passes (`gates/G0-redteam.md`): roles are separated by what each may write, the checking code and the spec are read from the base branch, builds no longer touch the master doc, and this file says which protections are tripwires.*

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
adds_dependencies: []        # libraries this build may add to v2/pyproject.toml (normally none; adding one needs the founder's review)
```

## Who may write what

Every commit on a build branch ends with a trailer, `Chronos-Role: builder` or `Chronos-Role: reviewer`. A commit without one fails the checks.

| Role | May change | May set the status to |
|---|---|---|
| **Builder** | the spec's `touches` · `docs/v2/build/reports/<id>.md` · one new section at the top of `docs/v2/CHANGELOG.md` · `docs/v2/build/status/<id>.json` | `building`, `needs_review`, `halted` |
| **Reviewer** | `docs/v2/build/reviews/<id>-r<n>.md` · `docs/v2/build/status/<id>.json` · `docs/v2/build/LEDGER.md` | `changes_requested`, `passed`, `merged`, `halted` |

Nobody on a build branch may change: the master doc, a spec, the ladder, the blueprint, the cards or `gates/`, **whatever a spec lists**. And unless the build's own spec lists the path in `touches` (only the founder builds B01, B02 and B04; B08, B09 and B43, which add libraries; and B20, B47 and B50, which create protected files, do): `CLAUDE.md`, `.claude/`, `.github/`, `v2/tools/guards/`, `v2/config/protected/`, `v2/pyproject.toml`, `CODEOWNERS`, the touchstones folder. Those are founder-owned: from B05 a pull request touching one can't merge without the founder's review. Nobody, ever, creates a `CLAUDE.md`, `AGENTS.md` or `.claude` folder below the repository root.

**How this is checked, and what kind of check it is.** The checking code and the spec are read from the base branch (`v2-build`), not from the pull request (build B02), so editing your own spec or the guard code on your branch changes nothing. These checks are **tripwires**: they catch a session that makes a mistake or takes a shortcut. They are not proof against a session that sets out to deceive. What stands behind them: GitHub's own rules on `main` and on founder-owned files (from B05), and the audit at every gate, which re-runs the previous gate's tests unmodified and checks every review against the session records.

`CODEBASE.md`, `COMPONENTS.md` and `BUILD_NOTES.md` are ordinary paths: a build may change them only if its `touches` lists them. The master doc's status board (§2), decisions (§10) and open questions (§12) are updated **at gates**, from the build reports; a build that has something for them says so in its report under "For the gate".

## Rules for the builder (every build)

1. **Claim first.** The branch is `claude/<id>` in lower case, nothing else (`claude/b06`). Take the lock (`/tick` does it), create the branch from `v2-build`, write `status/<id>.json` with state `building`, push, open a draft pull request into `v2-build`. Then work.
2. **Tests before code.** Step 1 of every spec commits the known-answer tests exactly as the spec states them. Run them; they must fail because the code doesn't exist or is wrong, not because of a typo. Paste the failing summary line into the report. A known answer in a spec is never changed by the builder: if you think it is wrong, halt (rule 9).
3. **One step, one commit.** After each numbered step: run the tests, commit (`B06 step 3: …`, with the trailer), push. Each push renews the lock; before each push, check the lock is still yours (`/tick` does both), and if it isn't, stop without pushing. If usage or time runs out, the next session resumes from the last commit. Never leave uncommitted work.
4. **Stay inside `touches`.** Needing another file means the spec is wrong: halt.
5. **Never:** edit anything under `src/`, `tests/`, the root `pyproject.toml` or `uv.lock` (v1 is frozen) · change, rename or delete any test file that already exists on `v2-build` (new tests go in new files; the header's `may_modify_tests` is the only exception) · skip, deselect or xfail a test · define a pytest hook (`pytest_*`) or add a pytest option · patch or replace, from a test file or a conftest, anything in a module an earlier build delivered · create a `CLAUDE.md`, `AGENTS.md` or `.claude` folder · loosen a tolerance or a threshold · choose or change a seed after seeing a result · add a dependency the spec doesn't list · import `chronos` (v1) from v2 code · write a review file · merge anything.
6. **Conventions** (CLAUDE.md): tz-aware UTC everywhere; half-open `[start, end)` ranges with full timestamps, never bare dates; Decimal for money, float64 for series maths; every money amount is configuration; run with `TZ=UTC`.
7. **Finish.** All of these pass locally from `v2/`: `TZ=UTC uv run pytest -q`, `uv run ruff check .`, `uv run python tools/guards/run_all.py`. Then write `reports/<id>.md` from the template, add the CHANGELOG section, set the status to `needs_review`, mark the pull request ready.
8. **The report is for a non-technical reader first.** First paragraph: what now exists that didn't before, in plain words. Then: red-then-green evidence; every deviation from the spec (there should be none); "For the gate" (status-board changes, new traps, adopted libraries, open questions); the actuals (ticks used, lines of code and tests, wall-clock time).
9. **Halt, don't improvise,** when: the spec is ambiguous or wrong · two reasonable designs would give different results · a known answer can't be reproduced · the size budget won't hold · anything conflicts with the master doc · a protected value would have to change. Halting = set the status to `halted` with a one-paragraph reason and the options you see, push, stop.

## Rules for the reviewer (every build)

The reviewer is a different session from the builder, on Opus, and has not seen the builder's reasoning. It takes the lock for the review, like any other action.

1. Check out the branch. **Run everything yourself**: tests, lint, guards. Don't trust the report's numbers.
2. Read the diff against the spec **as it is on `v2-build`**, step by step. Every "Deliver" item exists; every "Known answers" item is a test that asserts exactly the stated value and tolerance; nothing outside `touches` changed.
3. **Break one thing on purpose.** Pick the function the build is about, change one operator or constant locally, and confirm a test goes red. Revert. If nothing goes red, the build fails review.
4. Check the hard rules (CLAUDE.md 1–10) and the standing rules above. Look specifically for: anything in the diff that changes how tests run or what they import (a new `conftest.py`, an autouse fixture, a test that assigns into another module, source code that behaves differently under test); a tolerance wider than the spec's; a seed not in the spec; a test that asserts something weaker than the spec; a skipped, deselected or xfail test; look-ahead; a bare date used as a range end; a local-time read.
5. Write `reviews/<id>-r<round>.md`: the code commit reviewed (its hash), verdict `PASS` or `CHANGES`, findings as a numbered list (each with file, line, what is wrong, what the spec says), and what you broke in step 3 and which test caught it.
6. `PASS` → set the status to `passed`. When the automatic checks are green on that commit: add one last commit that writes the ledger row and sets the status to `merged`, wait for green again, then squash-merge into `v2-build`. (If a session dies between that commit and the merge, the next tick sees `merged` on an unmerged branch and finishes the merge.) **If the pull request touches founder-owned files, stop after that last commit:** GitHub won't merge it without the founder's review, and anything pushed after he approves cancels his approval. The loop lists it as waiting on him and merges it, without pushing, once he has approved. `CHANGES` → set `changes_requested`. A second `CHANGES` on the same build → `halted`.
7. The reviewer never edits code or tests, even for a one-character fix.

**What the role checks can and can't do.** They reject: a commit with no role trailer; a builder commit that writes a review file or sets `passed`/`merged`; a reviewer commit that touches code; a `passed` or `merged` status with no review file naming the current code commit. A trailer is a label a session puts on its own commit, and builder and reviewer act with the same GitHub account, so these checks catch a session doing the wrong role's work by mistake. They can't catch a session that labels its commits falsely. The separation between builder and reviewer comes from the loop starting a fresh session for each action; the gate audit checks it afterwards against the session records; and it becomes a wall only if the founder gives the reviewer its own identity (BLUEPRINT 2.5; a decision at G1).

**Migration numbers** are fixed in each spec by the build's place on the ladder (B09 `0001` … B49 `0008`), so two builds never claim the same number. If a build merges before an earlier-numbered one (because the earlier one halted), the runner applies the lower number when it arrives; each migration only adds its own tables, so the order between builds doesn't matter.

## Sections of a spec

**Why** · **Read first** · **Deliver** · **Steps** · **Known answers and checks** (written before the code; these are the pass/fail rules of V2-D25) · **Not in this build** · **Halt if** · **For the gate**.

Tags on facts follow the rest of the pack: [Certain — run] = executed and seen · [Certain — read] = read in the source · [Likely] · [Guessing].
