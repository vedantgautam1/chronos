# BUILD SPECS — how to read one, and the rules every build follows

One file per build. A build session reads: `CLAUDE.md` (automatic), the master doc §1–§2, **this file**, **its own spec**, and the files its spec lists under "Read first". Nothing else is needed, and nothing else should be loaded.

## The header

```yaml
id: B04                      # matches LADDER.yaml
title: ...
size: M                      # S or M (BLUEPRINT 2.7)
model: opus                  # the loop obeys this; by hand, /tick refuses to start on another model
who: loop                    # loop = may run unattended · founder = needs the founder present
needs: [G1]
ticks: 3                     # build ticks allowed; one more is an overrun and a halt
touches:                     # the ONLY paths this build may change (globs)
  - v2/src/chronos2/stats/**
may_modify_tests: []         # earlier test files this build may edit (normally none)
```

Paths always allowed, for every build: `docs/v2/build/status/<id>.json`, `docs/v2/build/reports/<id>.md`, `docs/v2/build/reviews/<id>-*.md`, `docs/v2/build/LEDGER.md`, `docs/v2/CHANGELOG.md`, `docs/v2/CODEBASE.md`, and the build's own row in the master doc §2.

## Rules for the builder (every build)

1. **Claim first.** Create the branch `claude/<id>-<slug>` from `v2-build`, write `status/<id>.json` with state `building`, push, open a draft pull request into `v2-build`. Then work.
2. **Tests before code.** Step 1 of every spec commits the known-answer tests exactly as the spec states them. Run them; they must fail because the code doesn't exist or is wrong, not because of a typo. Paste the failing summary line into the report. A known answer in a spec is never edited by the builder: if you think it is wrong, halt (rule 9).
3. **One step, one commit.** After each numbered step: run the tests, commit (`B04 step 3: …`), push. If usage or time runs out, the next session resumes from the last commit. Never leave uncommitted work.
4. **Stay inside `touches`.** Needing another file means the spec is wrong: halt.
5. **Never:** edit anything under `src/`, `tests/`, the root `pyproject.toml` or `uv.lock` (v1 is frozen) · edit or delete a test from an earlier build · loosen a tolerance or a threshold · choose or change a seed after seeing a result · add a dependency the spec doesn't list · import `chronos` (v1) from v2 code · merge anything.
6. **Conventions** (CLAUDE.md): tz-aware UTC everywhere; half-open `[start, end)` ranges with full timestamps, never bare dates; Decimal for money, float64 for series maths; every money amount is configuration; run with `TZ=UTC`.
7. **Finish.** All of these pass locally from `v2/`: `TZ=UTC uv run pytest -q`, `uv run ruff check .`, `uv run python tools/guards/run_all.py`. Then write `reports/<id>.md` from the template, update the doc rows the spec names, set the status to `needs_review`, mark the pull request ready.
8. **The report is for a non-technical reader first.** First paragraph: what now exists that didn't before, in plain words. Then: red-then-green evidence, every deviation from the spec (there should be none), open questions, and the actuals (ticks used, lines of code and tests, wall-clock time).
9. **Halt, don't improvise,** when: the spec is ambiguous or wrong · two reasonable designs would give different results · a known answer can't be reproduced · the size budget won't hold · anything conflicts with the master doc · a protected value would change. Halting = write `status` `halted` with a one-paragraph reason and the options you see, push, stop.

## Rules for the reviewer (every build)

The reviewer is a different session from the builder, on Opus, and has not seen the builder's reasoning.

1. Check out the branch. **Run everything yourself**: tests, lint, guards. Don't trust the report's numbers.
2. Read the diff against the spec, step by step. Every "Deliver" item exists; every "Known answers" item is a test that asserts exactly the stated value and tolerance; nothing outside `touches` changed.
3. **Break one thing on purpose.** Pick the function the build is about, change one operator or constant locally, and confirm a test goes red. Revert. If nothing goes red, the build fails review.
4. Check the hard rules (CLAUDE.md 1–10) and the standing rules above. Look specifically for: a tolerance wider than the spec's; a seed not in the spec; a test that asserts something weaker than the spec; a skipped or xfail test; look-ahead; a bare date used as a range end; a local-time read.
5. Write `reviews/<id>-r<round>.md`: verdict `PASS` or `CHANGES`, findings as a numbered list (each with file, line, what is wrong, what the spec says), and what you broke in step 3 and which test caught it.
6. `PASS` + automatic tests green → set status `passed`, squash-merge into `v2-build`, write the ledger row. `CHANGES` → set `changes_requested`. A second `CHANGES` on the same build → `halted`.
7. The reviewer commits only under `docs/v2/build/reviews/`, `status/` and `LEDGER.md`. It never edits code or tests, even for a one-character fix.

## Sections of a spec

**Why** · **Read first** · **Deliver** · **Steps** · **Known answers and checks** (written before the code; these are the pass/fail rules of V2-D25) · **Not in this build** · **Halt if** · **Doc rows to update**.

Tags on facts follow the rest of the pack: [Certain — run] = executed and seen · [Certain — read] = read in the source · [Likely] · [Guessing].
