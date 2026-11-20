# G<n> — <the gate's one-line claim>: gate report

<!--
Copy to docs/v2/build/gates/G<n>-report.md. The eight sections below are
BLUEPRINT Part 6's, in its order, and they are the same every gate so the
founder learns the shape once.

Written by the auditor: a session that built none of this phase and reviewed
none of it. A gate is done when this report is on `main`.
-->

**Auditor:** a fresh Opus session, which built and reviewed none of this
phase.
**Phase:** <n> · **builds covered:** B<nn>–B<nn> · **branch:** `gate/g<n>`
**Previous gate:** <G<n-1>, and the commit on `main` its report landed in>
**Date:** <DD Mon YYYY> UTC

---

## 1. Verdict

**<Ready to approve / Not ready, because …>** — one line, first thing on the
page.

## 2. What was built since the last gate

<!-- One plain line per build. No jargon. What can the system do now? -->

| Build | What it added, in plain words | Rounds | Merged (UTC) |
|---|---|---|---|

## 3. What the audit tried to break, and what broke

<!--
The heart of the gate. Four things, each with its evidence:

- **The previous gate's tests, re-run unmodified from `main`'s own copy**
  against today's code. Give the count that ran and `main`'s own collection
  count; they must match.
- **The sabotage run** (build B22). Every survivor listed one by one and
  answered. A change the tests did not notice is a test that cannot fail.
  Some survivors are genuinely behaviour-preserving — say which, and show
  why.
- **Every rule file that changed in the phase, with its diff**: the guards,
  the workflows, CLAUDE.md, .claude/, the specs, the ladder, the blueprint,
  the library list, the protected values.
- **Which protections are walls today and which are not.** Claim a wall only
  where an attack test exists and was refused for the reason named.
  Otherwise say tripwire or guard rail.
-->

### Sabotage survivors

| | Change made | Caught? | Answer |
|---|---|---|---|

### Walls, tripwires and guard rails as at this gate

| Protection | Claimed | Evidence | What it actually is |
|---|---|---|---|

## 4. Numbers re-derived blind

<!--
From the papers, from v1's own passing tests, or from a second library —
never from a build's report, and never from the auditor's own memory. Yours
beside theirs. A number that does not reproduce is a finding, not a rounding
difference.
-->

| Quantity | The build's figure | Re-derived here | Source | Agrees? |
|---|---|---|---|---|

## 5. Plan vs reality

| | Estimated | Actual |
|---|---|---|
| Builds in the phase | <n> | <n> |
| Ticks | <n> | <n> |
| Review rounds | <n> | <n> |
| Halts | — | <n> |
| Code lines vs cap | — | <n> |
| Test lines vs cap | — | <n> |

**The re-sized ladder**, if the estimates were off: <what changes, and why>.

## 6. Three things you can check yourself

<!--
No code, no terminal. Each one is "open this page or file, find this line, it
should say X". If a check genuinely needs a command, give the sentence to say
to Claude and the answer to expect.

These exist so the founder's approval rests on something he verified, not on
the auditor's word.
-->

1. **<what it proves>** — open <page or file>, find <the line>. It should say
   <X>.
2. **<what it proves>** — …
3. **<what it proves>** — …

## 7. Decisions waiting for you

<!-- Each with the options, the trade-off in plain words, and a recommendation. -->

| | Decision | Options | Recommendation |
|---|---|---|---|

## 8. Master-document changes this gate will make

<!--
Exactly what §2 and §10 of docs/v2/CHRONOS_V2.md will say once approved.
Decisions go in §10 **only** where the founder locked them; a proposal stays
a proposal.
-->

| Section | Change |
|---|---|

---

## What this audit did not cover

<!--
Say it plainly. Three red-team passes on this pack each found real problems,
and the honest summary every time was what had not been looked at. An
unchecked thing named here is worth more than a confident sweep that was not
run.
-->

## How to approve

Two pull requests, in this order: **the write-up** (this report plus the
master-document changes — this is the one to read), then **the move of
`main`**. Approving has to come from the founder's own GitHub account.
Anything pushed to either pull request after he approves throws the approval
away and asks again; that is deliberate.
