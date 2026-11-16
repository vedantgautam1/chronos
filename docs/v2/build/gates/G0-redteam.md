# G0 — red-team of the build blueprint

**Status: NOT COMPLETE. Gate G0 should not be approved until this file lists the findings and what was done about each.**

## What a red team is
A separate AI agent that has never seen the plan being written. It gets only the finished plan and the governing documents, and its one job is to find what is wrong: contradictions with locked decisions, checks that can't fail, builds that are too big, holes in the loop, claims that aren't true. The author then fixes or answers every finding in writing. It exists so the author isn't grading its own work (master doc V2-D25, rule 3).

## Log
| When (UTC) | What happened |
|---|---|
| 16 Nov 2026, ~05:40 | Red-team agent started on a different model (Opus) from the one that wrote the plan (Fable), with no access to the planning conversation. Brief: ten attack areas, findings ranked by severity, a final "real walls vs honour system" list. |
| 16 Nov 2026, ~05:50 | **Stopped before reporting anything:** the account's five-hour usage allowance ran out (resets 09:50 UTC / 4:50 am Toronto). No findings were delivered. Its partial work is saved and it resumes from where it stopped. |

## Findings
*None delivered yet.*

## What the author already knows is weak (self-reported; not a substitute for the red team)
These were found while writing, and are fixed or stated in the plan. They are listed so the red team's findings can be compared with them.

| # | Weakness | Status |
|---|---|---|
| 1 | **The "founder-approved" label is not a wall.** The loop acts with the founder's GitHub identity, so it could add the label itself. Same for merging into `main`. | Stated in BLUEPRINT 2.4 and the table below. Real fix (a separate GitHub identity for automation) is scheduled before anything can trade (Part 7, phase 6) |
| 2 | **Reviewer and builder are the same model family.** A fresh session removes shared reasoning, not shared blind spots. | Stated. Proposal P-20 (a reviewer from another AI family) is the fix; decided at G1 |
| 3 | **Size estimates are guesses.** B02, B09, B12 and B13 are at the top of the M budget. | LEDGER + re-sizing at G1 and G2; the halt-on-overrun rule |
| 4 | **Session counts can't be promised.** | Stated in BLUEPRINT 2.7 |
| 5 | **Cards for B19–B49 are not buildable.** They fix what must be proved, not how. | By design; the loop halts on a card |
| 6 | **Several facts about plans, prices and local models come from third-party pages**, some from a single source. | Tagged [Likely] in the handbook, with sources |

## Real walls vs guard rails (author's own classification, to be challenged)
| Protection | Wall (enforced by code, CI or the database) | Guard rail (instructions; depends on the agent behaving) |
|---|---|---|
| v1 can't be edited | CI compares v1 paths with `v1-final` on every pull request (B01) | — |
| A build can't touch files outside its spec | CI scope guard (B01) | — |
| Earlier tests can't be deleted or changed | CI test-integrity guard (B01) | A new test that asserts something weaker than the spec is caught only by the reviewer |
| Known answers are right | Tests assert the numbers written in the spec; v1 oracle files are regenerated in CI from v1 itself (B04) | The spec's own numbers must be right: checked by the red team and at each gate |
| Trial records can't be changed or deleted | Database triggers and permissions, attacked in tests (B07) | A database superuser can still disable triggers; `audit()` detects it afterwards |
| Research can't read sealed data | The data door refuses; `audit_seal` scans every footprint (B09, B12) | Code that bypasses the door by reading files directly is caught by an import-boundary test, not by the operating system |
| Protected values need the founder | CI fails without the label | **The label itself** (weakness 1) |
| `main` moves only at gates | Pull request + green checks required by GitHub | **Who clicks merge** (weakness 1); unattended sessions are told not to, and the platform doesn't treat a scheduled prompt as the user's approval |
| The reviewer never edits code | — | Instructions; a CI check on commit trailers is possible and is listed for B02 |
| Specs are frozen once a build starts | Scope guard: a build branch can't touch `specs/` | A separate pull request could edit a spec; it would be visible in history and needs review |
| The builder doesn't review itself | Each tick is a fresh session by construction | A manual session could do both if the founder asked it to |
| The loop can't spend money | Never runs Fable; usage-credit limit set by the founder in Claude settings | The founder must actually set the limit (HANDBOOK §6) |
