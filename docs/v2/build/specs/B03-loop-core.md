```yaml
id: B03
title: The loop's decision core — ladder reader, facts, next action, locks
size: M
model: opus
who: founder          # run by hand: this build creates the loop
needs: [B02]
ticks: 3
touches:
  - v2/tools/loop/**
  - v2/tests/tools/loop/**
may_modify_tests: []
```

# B03 — The loop's decision core

## Why
This replaces the founder as the message bus. The important design choice: **an ordinary script decides what happens next, not an AI.** The AI sessions only do the work the script names. That makes "what is the loop doing?" a question with one checkable answer. This build is only the script and its tests; the agents that act on it are B04.

## Read first
- `BLUEPRINT.md` Part 2, `LADDER.yaml`, `specs/README.md`. `gates/G0-redteam.md` findings 12, 13, 18.

## The rules (fixed here)
- **Done.** A build is done when `docs/v2/build/status/<id>.json` with state `merged` is on `v2-build`. A gate is done when `docs/v2/build/gates/<id>-report.md` is on **`main`** (only a founder-approved pull request can put it there). A gate takes two pull requests, both opened by the loop, both needing the founder: the **write-up** (`gate/gN` into `v2-build`: the report and the master-doc updates) and then the **move** (`v2-build` into `main`).
- **Next** = the first ladder entry, in file order, that isn't done and whose `needs` are all done. One **active** build at a time: a build is active when its branch exists, isn't merged and isn't `halted`; while one is active, the loop works on that one. A halted build is parked: it blocks only the builds that need it.
- **Locks.** Every action (build, resume, review, fix, merge, gate audit) first takes a lock: it creates the branch `lock/<id>` through the GitHub API, pointing at a commit whose message records who, what and when. Creating a branch that exists fails, so two sessions can't both win. The holder moves the lock forward on every push (renewal). A lock whose last commit is older than `claim_hours` is stale and may be taken over. The lock is deleted when the action ends.
- **Global halt** = an open GitHub issue labelled `chronos-halt`. While one is open, every action is `NONE`.
- Branch names are exactly `claude/<id>` in lower case.

## Deliver
1. `v2/tools/loop/ladder.py`: load and validate `LADDER.yaml` (unique ids; every `needs` exists and appears earlier; `size`, `model`, `who` from the allowed sets; `ticks` matches size; gates have no spec; a spec path exists unless it is `card`).
2. `v2/tools/loop/facts.py`: gather repository facts and nothing else: done builds and gates (per the rules above), open build branches and their status files, lock branches and their ages, check results on a branch head and on `v2-build`, open `chronos-halt` issues. `git` and `gh api` (REST only) sit behind one small function each, which tests replace.
3. `v2/tools/loop/next_action.py`: **a pure function** `decide(ladder, facts, now) -> Action` with no I/O, and a thin `main()` that prints the action as JSON. Actions: `START_BUILD`, `RESUME_BUILD`, `REVIEW`, `FIX`, `MERGE`, `RUN_GATE_AUDIT`, `WAIT_FOUNDER`, `HALT`, `NONE`; each carries the build id, model, branch and a one-line plain-language reason, plus a list `waiting_on_founder`.
4. `v2/tools/loop/lock.py`: `acquire(id, action)`, `renew`, `release`, `is_stale`.
5. `v2/tools/loop/status_report.py`: the same facts as three plain sentences ("B09 is in review, round 1. Next after that: B10. Waiting on you: nothing.").
6. The status file schema: `build`, `state` (`building|needs_review|changes_requested|passed|merged|halted`), `round`, `ticks`, `head`, `halt_reason`, `halt_options`.

## Steps
1. Commit the decision table below as a parametrised test (red).
2. `ladder.py` + its validation tests.
3. `decide()` → green on the table.
4. `lock.py`, tested against a throwaway bare repository (two processes race; exactly one wins).
5. `facts.py`, `status_report.py`.
6. Dry run by hand on a toy ladder in a temp repository: start → review → merge. Paste the three `next_action` outputs into the report.

## Known answers and checks
`decide()` on the real `LADDER.yaml`, with facts as stated. `now` is fixed; a lock is fresh for 3 hours.

| # | Facts | Expected |
|---|---|---|
| 1 | No G0 report on `main` | `WAIT_FOUNDER` G0 |
| 2 | G0 done; nothing merged | `WAIT_FOUNDER` B01 (who: founder) |
| 3 | B01–B05 merged; no G1 report anywhere | `RUN_GATE_AUDIT` G1 |
| 4 | The `gate/g1` write-up pull request is open | `WAIT_FOUNDER` G1 (read and approve the write-up) |
| 4b | G1 report on `v2-build`, not on `main` | `WAIT_FOUNDER` G1 (approve the move of `main`); the action carries the instruction to open that pull request if it isn't open |
| 5 | G1 done; nothing else | `START_BUILD` B06, model opus, branch `claude/b06` |
| 6 | B06 `building`, lock 1 h old | `NONE` |
| 7 | B06 `building`, lock 4 h old, ticks 1 | `RESUME_BUILD` B06 |
| 8 | B06 `building`, lock 4 h old, ticks 3 | `HALT` B06 (overrun) |
| 9 | B06 `needs_review`, no lock | `REVIEW` B06 |
| 10 | B06 `needs_review`, a review lock 20 min old | `NONE` |
| 11 | B06 `changes_requested`, round 1 | `FIX` B06 |
| 12 | B06 `changes_requested`, round 2 | `HALT` B06 (failed review twice) |
| 13 | B06 `passed`, checks green | `MERGE` B06 |
| 14 | B06 `passed`, checks pending | `NONE` |
| 15 | B06 `passed`, checks red | `HALT` B06 |
| 16 | B06's branch says `merged`, pull request still open, checks green (a session died mid-merge) | `MERGE` B06 |
| 17 | B06 merged | `START_BUILD` B07 |
| 18 | B06 `halted`; B09 not started | `START_BUILD` B09 (a halted build blocks only what needs it) |
| 19 | B06 `halted`; nothing else runnable | `WAIT_FOUNDER` B06 |
| 20 | A `chronos-halt` issue is open; B07 runnable | `NONE` |
| 21 | Checks red on `v2-build` itself | `HALT` (global) |
| 22 | B06–B22 merged; no G2 report | `RUN_GATE_AUDIT` G2 |
| 23 | G2 done; B23 is `spec: card` | `HALT` B23 (spec not written) |
| 24 | G2 done; B23 and B24 have specs; B23 merged | `START_BUILD` B24, and `waiting_on_founder` lists B26 |
| 25 | A status file names a build not on the ladder | error exit, non-zero |
| 26 | Two active build branches (neither halted) | error exit: one active build at a time |
| 26b | B06 `halted` and B09 `building`, lock 1 h old | `NONE` (B09 is the active build; B06 is parked) |
| 27 | B14 needs B11 **and** B13; B11 merged, B13 not | B14 not chosen |
| 28 | B20's pull request touches a founder-owned path and has no approval; status `passed`, checks green except the review requirement | `WAIT_FOUNDER` B20 |

Also:
- `ladder.py` rejects: a duplicate id; a `needs` that points later in the file; `size: L`; `model: fable`; a build with neither a spec file nor `card`.
- **Blueprint and ladder agree:** for every row of the tables in `BLUEPRINT.md` Part 5, the id, size and "who" equal `LADDER.yaml`'s, in the same order.
- **Lock race:** 20 pairs of simultaneous `acquire` calls on the same id → exactly one winner each time.
- `decide()` imports nothing that does I/O (asserted by importing it with `subprocess` and `socket` patched to raise).

## Not in this build
Agents, skills, the `/tick` command (B04) · scheduling (B05).

## Halt if
- Creating a branch through the API isn't atomic in practice (the race test shows two winners).

## For the gate
`CODEBASE.md`: `v2/tools/loop/`.
