# B<nn> — <title>: build report

<!--
How to use this file: copy it to docs/v2/build/reports/B<nn>.md and replace
every <angle-bracketed> placeholder. Delete a section only if it genuinely
does not apply, and say in one line why rather than leaving it blank.

The order is builder rule 8's and it is deliberate: the founder is
non-technical and reads the first paragraph first. Evidence comes before
numbers, and the numbers come last because they are the part the gate
re-reads, not the part he does.

Measure the actuals AFTER your last code commit, and re-measure rather than
adjusting them. B03 gave its clearance figures from a tree four commits old
and understated its own overrun by more than the overrun it disclosed.
-->

**Builder:** <a fresh Opus session / on Sonnet; run by the loop, or by hand
with the founder present>
**Branch:** `claude/b<nn>` · **pull request** [#<n>](<url>) · **base:**
`v2-build` at `<full sha>`
**Spec read from:** `docs/v2/build/specs/B<nn>-<slug>.md` on `origin/v2-build`,
sha256 `<hash you computed yourself>`
**Date:** <DD Mon YYYY> UTC · **status: `<building|needs_review|halted>`** ·
**tick <n> of <allowed>**

---

## What now exists that didn't before

<!--
Plain words, no jargon, for a reader who does not read code. What can the
system do today that it could not yesterday, and why does that matter? Two
or three short paragraphs. If you cannot say it without naming a function,
say it again.

If something could not be done and was left undone, say so here rather than
burying it below.
-->

---

## Red then green, step by step

<!-- One row per numbered step in the spec. Builder rules 2 and 3. -->

| Step | Commit | What | Result |
|---|---|---|---|
| <n> | `<sha>` | <what it did> | <red, for the right reason / N passed> |

**Step 1's red, pasted** — it must fail because the code does not exist or is
wrong, **not because of a typo**, and the text below is how a reader checks
that:

```
<the failing summary line, exactly as pytest printed it>
```

**The baseline, measured before anything was written** — so a later reader can
tell what this build changed from what was already true:

```
TZ=UTC uv run pytest -q                  <n> passed
uv run ruff check .                      <result>
uv run python tools/guards/run_all.py    <n> ok, <findings>
```

### Known answers, item by item

<!--
One row per entry in the spec's "Known answers and checks", with what
actually happened. This is the table the reviewer checks line by line against
the spec, so leaving an entry out reads as an omission rather than a pass.

Added to this template after writing the first report from it: the section
turned out to be the one a reviewer most needs and the shape did not ask for
it (B04).
-->

| The spec's known answer | Result |
|---|---|
| <quote it> | <what happened, with the number> |

### What I broke on purpose

<!--
Reviewer rule 3 makes this the reviewer's job and it does it independently.
Do it anyway: a check that has never been seen red proves nothing
(BLUEPRINT 2.5). Each break reverted, each confirmed red, and the file
confirmed byte-identical afterwards.

A break that changes no behaviour proves nothing about the test. Check the
*reason* a break went red, not only that the count moved.
-->

| | Break | Red |
|---|---|---|
| 1 | <the one line changed> | <n failed — which tests, and why those> |

---

## Deviations from the spec

<!--
There should be none. Where there is one, give it a number, a reason, and
**the time the founder cleared it** — B02 left four clearances with no
artifact anywhere and the gate audit had to settle them from memory.

"Addition" and "deviation" are different: an addition makes the spec's own
intent work (a missing fetch, a missing guard) and is still recorded here
with its reason. Changing what the spec asks for is a deviation and usually
a halt instead.

Design choices that are neither, but that a reviewer should see stated
rather than discover, go in a short list under this one.
-->

**<None / N, each cleared at the time shown>.**

---

## What this build proves less than it looks

<!--
The most useful section in the file, and the easiest to skip. What is thin?
What ran once? What has only ever been exercised against a stub? Name the
specific functions and say what would exercise them for real.

Every collector defect found in this project so far has lived in the seam
between a pure function and the thing that feeds it, invisible to a suite
that passed. If your build has that shape, say where the join is tested and
where it is not.
-->

---

## For the gate

<!--
The master document is updated at gates, from these reports, never by a
build. So anything that belongs in it goes here:

- `CODEBASE.md` / `COMPONENTS.md` / `BUILD_NOTES.md` additions
- status-board changes
- new traps worth writing down, each one a thing that cost time
- open questions, with the options and who decides
- anything the spec got wrong, which is a spec defect and not a build defect
- size evidence for the re-sizing at G1
-->

---

## The actuals

| | Estimate (size <S\|M>, BLUEPRINT 2.7) | Actual |
|---|---|---|
| Code | ≤ <150\|400> lines | <n> excluding blanks, comments and docstrings; <n> raw |
| Tests | ≤ <300\|600> lines | <n> strict; <n> raw; <n> test cases |
| Files touched | ≤ <8\|14> | <n> (<how you counted>) |
| New outside libraries | ≤ <0-1\|2> | <n> |
| Build ticks | <2\|3> | <n> |
| Review rounds | — | to be filled by the reviewer |

Wall clock about <n>, <HH:MM>–<HH:MM> UTC, and say **which span** — the
building session, or the branch end to end. <n> commits, each carrying
`Chronos-Role: builder`.

<!--
If anything here is over its cap, say so plainly, state the multiple, and say
when the founder cleared it. Builder rule 9 makes a size overrun a halt that
only he clears, and it goes to him at the point it becomes clear — not at the
end, and never left for him to find in this table.

If the figure you gave him when you asked differs from the final one, say
both and say by how much. He cleared the number he was told.
-->
