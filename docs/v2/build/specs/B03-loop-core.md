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
- `BLUEPRINT.md` Part 2, `LADDER.yaml`, `specs/README.md`. `gates/G0-redteam.md`: first pass findings 12, 13, 18; second pass findings 9–11, 13, 16; third pass findings a, e, h, i, j, l.
- GitHub REST docs, read fresh: creating and updating a git reference (what `force: false` accepts), the issue timeline (who labelled, unlabelled, closed), pull-request review state.

## The rules (fixed here)
- **Done.** A build is done when `docs/v2/build/status/<id>.json` with state `merged` is on `v2-build`. A gate is done when `docs/v2/build/gates/<id>-report.md` is on **`main`**. A gate takes two pull requests, both opened by the loop, both needing the founder: the **write-up** (`gate/gN` into `v2-build`: the report and the master-doc updates; it first merges `main` into itself, so document changes the founder approved on `main` since the last gate come along) and then the **move** (`v2-build` into `main`).
- **Next** = the first ladder entry, in file order, that isn't done and whose `needs` are all done.
- **Whose build is it.** A `who: founder` build is never started, resumed, reviewed, merged or counted as active by the loop. It is listed under "waiting on you" and nothing more, however stale its lock.
- **One active loop build at a time.** A loop build is *active* when its branch exists and it is in state `building`, `needs_review` or `changes_requested`. While one is active, the loop works on that one. A build is *parked*, and blocks only the builds that need it, when it is `halted`, or when its review is finished, its checks are green and its pull request is waiting only for the founder's review (a build that touches founder-owned files). For such a build the reviewer pushes its last commit (the ledger row and status `merged`) **before** the founder is asked, because any push after his approval cancels the approval (B05); once he has approved, the merge is done without another push.
- **Locks.** Every action first takes a lock on the build or gate.
  - *Take:* create the git reference `refs/heads/lock/<id>` through the GitHub API, pointing at a new commit whose message records the session, the action and the time. Creating a reference that exists is refused by GitHub [Likely — standard API behaviour; proved in step 4], so of two sessions one wins.
  - *Renew:* on every push, the holder adds a commit on top of its own lock commit and moves the reference there **without force**.
  - *Take over a stale lock* (last commit older than `claim_hours`): add a commit on top of the stale commit and move the reference there without force. Two sessions racing to take over both build on the same stale commit; the first update wins and the second is refused because it is no longer a fast-forward [Likely; proved in step 4].
  - *Check before every push:* the holder reads the reference and stops, without pushing, if it no longer points at its own last lock commit. A slow session that lost its lock therefore stops writing. (A small window remains between the check and the push; a lock's age is read from a date the holding session wrote. Both are accepted: a session can only keep or lose its *own* lock by getting them wrong, and the overrun halt bounds the damage.)
  - *Release:* delete the reference.
- **Emergency stop.** The script reads each issue's **timeline**, not its current labels. A stop begins when the label `chronos-halt` is put on an issue by anyone. It ends only when **the repository's owner** closes that issue or removes the label. If any other account closes the issue, removes the label, or deletes the label from the repository, the stop stays in force. While a stop is in force every action is `NONE`. *This is a guard rail, not a wall:* it is enforced by this script, which the automation's own sessions run. The switches nothing can override are the founder's: turning the scheduled task off in the Claude app, and removing the automation's account from the repository.
- **When the script itself fails** (an error exit, rows 27 and 37): `/tick` (B04) opens a `chronos-halt` issue containing the error text and stops. The loop never retries past an error.
- **What the script trusts.** `round` is the number of review files on the build's branch, counted by the script. `ticks` is read from the status file, which the builder writes: an under-reported number delays an overrun halt and can do nothing else. Only branches in this repository are looked at; pull requests from forks are ignored.
- Branch names are exactly `claude/<id>` in lower case.

## Deliver
1. `v2/tools/loop/ladder.py`: load and validate a ladder file (unique ids; every `needs` exists and appears earlier; `size`, `model`, `who` from the allowed sets; `ticks` matches size; gates have no spec; a spec path exists unless it is `card`).
2. `v2/tools/loop/facts.py`: gather repository facts and nothing else: done builds and gates, build branches and their status files, review-file counts, lock references and their ages, check results on a branch head and on `v2-build`, pull requests for build and gate branches (open, merged, closed unmerged, waiting on code-owner review), `chronos-halt` issues and who closed them. `git` and `gh api` (REST only) sit behind one small function each, which tests replace.
3. `v2/tools/loop/next_action.py`: **a pure function** `decide(ladder, facts, now) -> Action` with no I/O, and a thin `main(--ladder PATH)` that prints the action as JSON (default path: `docs/v2/build/LADDER.yaml`). With `--ladder`, status files, branches and locks for ids that aren't on that ladder are **ignored** (and listed as a note in the status report), so a probe ladder can run beside the real builds' files (B05). Actions: `START_BUILD`, `RESUME_BUILD`, `REVIEW`, `FIX`, `MERGE`, `RUN_GATE_AUDIT`, `OPEN_GATE_MOVE`, `WAIT_FOUNDER`, `HALT`, `NONE`; each carries the id, model, branch and a one-line plain-language reason, plus a list `waiting_on_founder`.
4. `v2/tools/loop/lock.py`: `acquire(id, action)`, `renew`, `still_mine`, `take_over`, `release`, `is_stale`.
5. `v2/tools/loop/status_report.py`: the same facts as three plain sentences ("B09 is in review, round 1. Next after that: B10. Waiting on you: B20's pull request.").
6. The status file schema: `build`, `state` (`building|needs_review|changes_requested|passed|merged|halted`), `ticks`, `head`, `halt_reason`, `halt_options`.
7. `v2/tests/tools/loop/fixtures/ladder_a.yaml` (a frozen copy of today's `LADDER.yaml`) and `ladder_b.yaml` (the same, with B23 and B24 given spec paths). **The decision table runs on these copies, not on the live ladder**, so a later, routine change to the real ladder can't turn this build's tests red.

## Steps
0. **B02's proofs on GitHub** (they need B02's guard code on the base branch, which is true only now). **Five** scratch pull requests into `v2-build`, each from a branch named `claude/b04` cut fresh from `v2-build` (B04's spec is on the base branch and B04 hasn't started, so `scope` has something real to read), each closed without merging and its branch deleted, URLs in this build's report:
   (a) edits `src/chronos/__init__.py` → **guards** red, naming `v1_frozen`;
   (b) edits B04's spec to add `v2/src/chronos2/core/x.py` to `touches`, then adds that file → **guards** red, naming `scope` (and `protected`, for the spec);
   (c) adds `v2/conftest.py` whose hook drops one B01 test → **guards** red naming `scope`, **and earlier-tests** green with the same number of tests run as on `v2-build` (the dropped test still ran);
   (d) loosens one assertion in an existing B01 test file → **guards** red, naming `frozen_files`;
   (e) changes `v2/src/chronos2/core/` so that one existing B01 test fails against it — the **package**, not the test, since an existing test file is frozen → **earlier-tests** red: the job's conclusion is `failure`, and its log names the failing test. (`guards` goes red too, on `scope`; that is not what this proof is for.) **This is the one proof that exercises the second job end to end.** B02's `earlier-tests` job carries the same `pipefail` patch as `guards` and its runner is proven to exit non-zero in a temp repository, but on GitHub it has only ever been green, so its red path is inferred rather than observed — review `B02-r2.md` finding 9, and **O-19**: a CI gate is not reviewed until it has been seen red on GitHub. Breaking an earlier test from the test file would mean editing a frozen file, which is why this breaks the package instead.
   In each, the **guards** job log shows the guard code came from the base-commit checkout, with no bootstrap notice.
1. Commit the decision table below as a parametrised test (red).
2. `ladder.py` + its validation tests.
3. `decide()` → green on the table.
4. `lock.py`. Two proofs: (i) against a throwaway local bare repository, 20 pairs of racing `acquire` calls and 20 pairs of racing `take_over` calls → exactly one winner each time; (ii) **against GitHub itself**, on references named `lock/zz-proof-*` that are deleted afterwards: 20 racing `acquire` pairs and 20 racing `take_over` pairs, exactly one winner each time, with the count and one sample pair of API responses in the report.
5. `facts.py`, `status_report.py`.
6. Dry run by hand on a toy ladder in a temp repository: start → review → merge. Paste the three `next_action` outputs into the report.

## Known answers and checks
`decide()` on `ladder_a.yaml` unless a row says otherwise, with facts as stated. `now` is fixed; a lock is fresh for 3 hours.

| # | Facts | Expected |
|---|---|---|
| 1 | No G0 report on `main` | `WAIT_FOUNDER` G0 |
| 2 | G0 done; nothing merged | `WAIT_FOUNDER` B01 |
| 3 | B01–B05 merged; no G1 report, no `gate/g1` branch | `RUN_GATE_AUDIT` G1 |
| 4 | `gate/g1` branch exists, no pull request, lock stale | `RUN_GATE_AUDIT` G1 (resume) |
| 5 | The `gate/g1` write-up pull request is open | `WAIT_FOUNDER` G1 (read and approve the write-up) |
| 6 | The write-up pull request was closed without merging; the `gate/g1` branch still exists | `WAIT_FOUNDER` G1 (the founder sent it back). The way forward is his: in a live session he says what to change; that session deletes the `gate/g1` branch, and the next tick is row 3 again |
| 7 | G1 report on `v2-build`, not on `main`, no move pull request | `OPEN_GATE_MOVE` G1 |
| 8 | G1 report on `v2-build`, move pull request open | `WAIT_FOUNDER` G1 (approve the move) |
| 8b | G1 report on `v2-build`, a move pull request was closed without merging | `WAIT_FOUNDER` G1 (he refused the move; it is not re-opened automatically) |
| 9 | G1 done; nothing else | `START_BUILD` B06, model opus, branch `claude/b06` |
| 10 | B06 `building`, lock 1 h old | `NONE` |
| 11 | B06 `building`, lock 4 h old, ticks 1 | `RESUME_BUILD` B06 |
| 12 | B06 `building`, lock 4 h old, ticks 3 | `HALT` B06 (overrun) |
| 13 | B06 `needs_review`, no lock | `REVIEW` B06 |
| 14 | B06 `needs_review`, a review lock 20 min old | `NONE` |
| 15 | B06 `needs_review`, a review lock 4 h old | `REVIEW` B06 (takes over) |
| 16 | B06 `changes_requested`, one review file | `FIX` B06 |
| 17 | B06 `changes_requested`, two review files | `HALT` B06 (failed review twice) |
| 18 | B06 `passed`, checks green | `MERGE` B06 |
| 19 | B06 `passed`, checks pending | `NONE` |
| 20 | B06 `passed`, checks red | `HALT` B06 |
| 21 | B06's branch says `merged`, pull request still open, checks green, no review outstanding (a session died mid-merge) | `MERGE` B06 |
| 22 | B06's branch says `merged`, pull request closed without merging | `HALT` B06 |
| 23 | B06 merged | `START_BUILD` B07 |
| 24 | B06 `halted`; B09 not started | `START_BUILD` B09 (a halted build blocks only what needs it) |
| 25 | B06 `halted`; B09 `building`, lock 1 h old | `NONE` (B09 is active; B06 is parked) |
| 26 | B06 `halted`; nothing else runnable | `WAIT_FOUNDER` B06 |
| 27 | B06 and B09 both `building` | error exit: one active loop build at a time |
| 28 | B20's branch says `merged`, checks green, pull request waiting on the founder's review; B21 runnable | `START_BUILD` B21, and `waiting_on_founder` includes B20 (parked, not retried) |
| 28b | The same, and the founder has now approved | `MERGE` B20 |
| 28c | The same as 28, and nothing else is runnable | `WAIT_FOUNDER` B20 |
| 29 | A `chronos-halt` issue is open; B07 runnable | `NONE` |
| 30 | A `chronos-halt` issue was closed by the automation's account | `NONE` (still halted) |
| 30b | The label was removed from the issue by the automation's account | `NONE` (still halted) |
| 30c | The label was deleted from the repository; the issue's timeline shows it was applied and never removed or closed by the owner | `NONE` (still halted) |
| 31 | The issue was closed, or the label removed, by the repository owner | acts normally |
| 32 | Checks red on `v2-build` itself | `HALT` (global) |
| 33 | B06–B22 merged; no G2 report | `RUN_GATE_AUDIT` G2 |
| 34 | G2 done; nothing else (`ladder_a`: B23 is a card) | `WAIT_FOUNDER` B23 (its spec isn't written); `waiting_on_founder` also includes B42 |
| 35 | `ladder_b`; G2 done; B23 merged | `START_BUILD` B24; `waiting_on_founder` includes B26 and B42 |
| 36 | `ladder_b`; G2 done; B23–B29 merged; B30 (a founder build) open, its lock 3 days old; B31 waits on B30; B42 and B43 not started (B43 has no spec) | `WAIT_FOUNDER`; B30 is **not** resumed; `waiting_on_founder` includes B30, B42 and B43 |
| 37 | A status file on `v2-build` names a build that isn't on the ladder passed in | ignored for the decision; named in the status report's notes |
| 37b | A status file isn't valid against the schema | error exit, non-zero |
| 38 | B14 needs B11 **and** B13; B11 merged, B13 not | B14 not chosen |
| 39 | A pull request from a fork whose head branch is named `claude/b06` | ignored; same result as with no such pull request |

Tests that assert `waiting_on_founder` check that the named builds are **in** the list, not that the list equals them.

Also:
- `ladder.py` rejects: a duplicate id; a `needs` that points later in the file; `size: L`; `model: fable`; a build with neither a spec file nor `card`.
- **On the live files** (the only two tests that read them): `LADDER.yaml` validates; and for every row of the tables in `BLUEPRINT.md` Part 5, the id, size and "who" equal the ladder's, in the same order (the blueprint writes `loop` for `who: loop` and `you+` for `who: founder`, sometimes followed by a note in brackets, which is ignored).
- **Locks:** step 4's two proofs.
- **A session that lost its lock stops:** `still_mine` returns false after a takeover, and the push helper refuses to push.
- `decide()` imports nothing that does I/O (asserted by importing it with `subprocess` and `socket` patched to raise).

## Not in this build
Agents, skills, the `/tick` command (B04) · scheduling (B05).

## Halt if
- Any of step 0's five proofs isn't red (or, for (c), green) for the reason stated: then B02's guards don't do what B02's tests said, and that is fixed before anything else is built. For (e) specifically, a **green** `earlier-tests` job on a package change that fails an earlier test means the second job's red path does not work on GitHub, which is the same class of defect as review `B02-r1.md` finding 1 — halt and say so.
- Step 4's proof on GitHub shows two winners in either race, or GitHub accepts a non-fast-forward update with `force: false`. Then the lock design is wrong; propose the alternative (for example, a lock held as an issue assigned through the API) and stop.

## For the gate
`CODEBASE.md`: `v2/tools/loop/`.
