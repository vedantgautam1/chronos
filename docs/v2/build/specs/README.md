# BUILD SPECS — how to read one, and the rules every build follows

One file per build. A build session reads: `CLAUDE.md` (automatic), the master doc §1–§2, **this file**, **its own spec**, and the files its spec lists under "Read first". Nothing else is needed, and nothing else should be loaded.

*Revised 16 Nov after three red-team passes (`gates/G0-redteam.md`): roles are separated by what each may write, the checking code and the spec are read from the base branch, builds no longer touch the master doc, and this file says which protections are tripwires.*

*Revised 18 Nov after B01/B01A took three review rounds for one real defect (**V2-D51**, locked 19 Nov): findings now carry a severity, only a blocking finding produces `CHANGES`, and the reviewer attaches the patch and corrects the record itself. See reviewer rules 6–7 and "Severity".*

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
| **Reviewer** | `docs/v2/build/reviews/<id>-r<n>.md` · `docs/v2/build/status/<id>.json` · `docs/v2/build/LEDGER.md` · and, as record corrections for non-blocking findings only (rule 7): `docs/v2/build/reports/<id>.md` · the build's own section of `docs/v2/CHANGELOG.md` | `changes_requested`, `passed`, `merged`, `halted` |

Nobody on a build branch may change: the master doc, a spec, the ladder, the blueprint, the cards or `gates/`, **whatever a spec lists**. And unless the build's own spec lists the path in `touches` (only the founder builds B01, B02 and B04, the two that add libraries, B08 and B09, and B20 do): `CLAUDE.md`, `.claude/`, `.github/`, `v2/tools/guards/`, `v2/config/protected/`, `v2/pyproject.toml`, `CODEOWNERS`, the touchstones folder. Those are founder-owned: from B05 a pull request touching one can't merge without the founder's review. Nobody, ever, creates a `CLAUDE.md`, `AGENTS.md` or `.claude` folder below the repository root.

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
6. `PASS` → set the status to `passed`. **Builds B01–B05: stop here; the founder merges** (until B05 nothing on GitHub stops a wrong merge, so he is the check; HANDBOOK §1A). **Then somebody records the merge,** because "done" means `status/<id>.json` with state `merged` on `v2-build` (B03's rule) and nothing here used to assign that write for B01–B05 — which is why B01A and B02 both sat merged-in-fact and `passed`-on-paper. The reviewer does it if still in session when the founder merges; otherwise the next session of any kind does, as a `doc/…` pull request that sets the state to `merged` and fills the build's "Merged (UTC)" cell in `LEDGER.md`. It is a `doc/…` branch because the build branch is gone by then. From B06: when the automatic checks are green on that commit: add one last commit that writes the ledger row and sets the status to `merged`, wait for green again, then squash-merge into `v2-build`. (If a session dies between that commit and the merge, the next tick sees `merged` on an unmerged branch and finishes the merge.) **If the pull request touches founder-owned files, stop after that last commit:** GitHub won't merge it without the founder's review, and anything pushed after he approves cancels his approval. The loop lists it as waiting on him and merges it, without pushing, once he has approved. `CHANGES` → set `changes_requested`. A second `CHANGES` on the same build → `halted`. **Only a blocking finding can produce `CHANGES`** (see "Severity" below), so only blocking findings count toward that second-round halt.
7. The reviewer never edits code or tests, even for a one-character fix. Two things it **does** do instead: for every blocking finding it writes the **exact patch** into the review — the file, the line, the text as it is and the text it should be — so the builder round is mechanical rather than a re-diagnosis; and it **corrects the record itself** for non-blocking findings, which means it may edit `docs/v2/build/reports/<id>.md` and the build's `docs/v2/CHANGELOG.md` section where they are inaccurate. Every such correction is marked in place, says what the text previously said and why it was wrong, and is listed in the review under a "Role deviation" heading so the gate audit finds a reason rather than an anomaly. Code and tests remain untouchable: a reviewer that edits them is reviewing its own work.

### Severity: what blocks and what doesn't

Each finding is **blocking** or **non-blocking**, and the review says which.

**Blocking** — the code or the tests are wrong: a "Deliver" item missing or wrong; a "Known answers" item with no test, or a test asserting less than the spec states (a bare `pytest.raises` where the spec names the message, a widened tolerance, a seed not in the spec); a test weakened between red and green; a skipped, deselected or xfail test; a change outside `touches`; a protected value, threshold or limit changed; look-ahead, a bare date as a range end, a local-time read; anything that changes how tests run or what they import. These produce `CHANGES`, with the patch attached per rule 7.

**Non-blocking** — the code is right and the record or the polish is not: the report or CHANGELOG inaccurate, incomplete or self-contradictory; a cosmetic code change that is provably behaviour-preserving (say so and show the evidence); a test that could be tighter but is not wrong; a weakness in the **spec** rather than the build; anything for the gate. The reviewer records these, fixes what falls inside rule 7, and **still passes the build**. Paperwork never costs a build round.

**One exception, and it is deliberate: a false statement in the record is blocking.** A report or changelog that asserts a founder decision, an approval, a review or a measurement that did not happen is blocking however small it looks, because the gate audit and `LEDGER.md` are built on these documents and the role checks cannot catch a session that labels its own work falsely. Inaccurate is non-blocking; untrue is not.

**What the role checks can and can't do.** They reject: a commit with no role trailer; a builder commit that writes a review file or sets `passed`/`merged`; a reviewer commit that touches code; a `passed` or `merged` status with no review file naming the current code commit. A trailer is a label a session puts on its own commit, and builder and reviewer act with the same GitHub account, so these checks catch a session doing the wrong role's work by mistake. They can't catch a session that labels its commits falsely. The separation between builder and reviewer comes from the loop starting a fresh session for each action; the gate audit checks it afterwards against the session records; and it becomes a wall only if the founder gives the reviewer its own identity (BLUEPRINT 2.5; a decision at G1).

## Sections of a spec

**Why** · **Read first** · **Deliver** · **Steps** · **Known answers and checks** (written before the code; these are the pass/fail rules of V2-D25) · **Not in this build** · **Halt if** · **For the gate**.

Tags on facts follow the rest of the pack: [Certain — run] = executed and seen · [Certain — read] = read in the source · [Likely] · [Guessing].
