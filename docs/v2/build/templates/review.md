# B<nn> round <n> — review

<!--
Copy to docs/v2/build/reviews/B<nn>-r<n>.md. Reviewer rules 1-7 and the
Severity block in specs/README.md are the authority; this is the shape.

You are a different session from the builder and you have not seen its
reasoning. Run everything yourself. Do not trust a single number in the
report.
-->

**Reviewer:** a fresh Opus session, which did not write this build.
**Build:** B<nn> · **branch** `claude/b<nn>` · **pull request** [#<n>](<url>)
**Base:** `v2-build` at `<full sha>` — <confirm it is still both the branch's
base and its merge base, so no hash here drifts>

**Code commit reviewed:** `<full sha>` — <one line: what it is>
**Last commit on the branch:** `<full sha>` — <usually a report-and-status
commit>

<!--
Both hashes, deliberately. Reviewer rule 5 asks for "the code commit reviewed",
and a build that ends on a report-and-status commit has caught
out three reviewers so far (B02-r2 finding 11, and B03 predicted a third).
The rule's field name is unchanged; this template just asks for the other
hash as well, so the ambiguity cannot bite. B03's report raises renaming the
field as a suggestion for specs/README.md, which is the founder's to make.
-->

**Spec read from:** `origin/v2-build`, sha256 `<hash>` — <confirm it matches
what the builder says it read; a build cannot widen its own instructions>
**Date:** <DD Mon YYYY> UTC

## Verdict: `<PASS|CHANGES>`

<!--
Only a **blocking** finding may produce CHANGES. Paperwork never costs a
build round. A second CHANGES on the same build means `halted`, and only
blocking findings count toward it.
-->

<one paragraph, in plain words, for the founder: is this build sound, and
what if anything does he need to do>

---

## What I ran myself

| | Command | Result |
|---|---|---|
| Tests | `TZ=UTC uv run pytest -q` | <n passed> |
| Lint | `uv run ruff check .` | <result> |
| Guards | `uv run python tools/guards/run_all.py` | <n ok, findings> |

<!--
All three from v2/. If a number differs from the report's, say so and say
which is right and why. If a figure in the report was right when written and
is now stale, that is staleness rather than misstatement — say which it is.
-->

## What I broke on purpose, and which test caught it

<!--
Reviewer rule 3, and it is not optional: pick the function the build is
about, change one operator or constant, confirm a test goes red, revert. **If
nothing goes red, the build fails review.** Pick ground the builder's own
breaks did not cover.

A break that changes no behaviour proves nothing. Say why the test that went
red is the right one.
-->

| | Break | Red | Reverted |
|---|---|---|---|
| 1 | <the one line changed> | <n failed — which> | yes |

## Findings

<!--
Numbered. Each one: file, line, what is wrong, what the spec says, and its
**severity**. For every blocking finding, write the **exact patch** — the
text as it is and the text it should be — so the next round is mechanical
rather than a re-diagnosis.

Blocking: the code or the tests are wrong. Non-blocking: the record or the
polish is. The one deliberate exception — **a false statement in the record
is blocking** however small, because the gate audit and LEDGER.md stand on
these documents.
-->

### 1. <short title> — **<blocking|non-blocking>**

**Where:** `<path>:<line>`
**What is wrong:** <...>
**What the spec says:** <quote it>
**Patch** (blocking findings only):

```diff
- <the text as it is>
+ <the text it should be>
```

---

## Role deviation

<!--
Reviewer rule 7 lets you correct the **record** for non-blocking findings —
the build's report and its own CHANGELOG section — and nothing else. Every
such correction is marked in place, says what the text previously said and
why it was wrong, and is listed here, so the gate audit finds a reason
rather than an anomaly.

Code and tests stay untouchable, including a one-character fix. A reviewer
that edits them is reviewing its own work.

Write "None" if you corrected nothing.
-->

## What I did not check

<!--
Say it plainly. An unchecked thing named here is worth more to the gate than
a confident sweep that was not run.
-->

## Status set

`<passed|changes_requested|merged|halted>`, and <what happens next>.

<!--
On PASS for builds B01-B05: stop there; the founder merges, because until
B05 nothing on GitHub stops a wrong merge. Then somebody records the merge —
"done" means the status file says `merged` on v2-build.

**If the pull request touches founder-owned files, push your last commit
BEFORE he is asked to approve, and never after.** Anything pushed after his
approval cancels it, and he would be approving content he never saw.
-->
