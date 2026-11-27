```yaml
id: B05A
title: "The lock, made to work from the cloud: taken and released by git push, every refusal reported"
size: M
model: opus
who: founder          # run by hand: the loop cannot run until this build lands
needs: [B05]
ticks: 3
touches:
  - v2/tools/loop/lock.py
  - v2/tools/loop/facts.py
  - v2/tools/loop/prove_lock_by_push.py
  - .claude/skills/chronos-tick/loop_cli.py
  - v2/tests/tools/loop/test_lock_by_push.py
  - v2/tests/tools/loop/test_lock_release_marker.py
may_modify_tests:
  - v2/tests/tools/loop/test_lock.py  # amended 27 Nov: two tests only, see "Known answers" -> "And:"
adds_dependencies: []
```

# B05A — the lock, made to work from the cloud

## Why

The loop runs as a scheduled task, and a scheduled task runs in Anthropic's cloud. **A cloud session cannot take the lock**, so the loop cannot run a single tick unattended. B05 measured this and the founder accepted it on 23 Nov, deciding to fix the lock in its own build (`reports/B05.md` deviation 1; `probe/B05-environment-measurements.md` §4 and §7c) [Certain — run]:

- `lock.py`'s only backend, `GitHubRefs`, writes through the GitHub REST API: `POST /git/commits`, `POST /git/refs`, `PATCH` and `DELETE /git/refs/…`. The cloud session's proxy refuses every one of those.
- **`GitHubRefs.delete` discards GitHub's answer** (`lock.py`, the last method), so `release()` reports success on a lock that is still held. A silent false success is worse than a refusal.
- A cloud session **can** push branches with `git`, including force-pushes, and **cannot delete a branch by any route** (B05 trap 1).

**What was measured on 27 Nov, from a cloud session, before this spec was written** [Certain — run, on `refs/heads/lock/b05a-probe`; that branch is left behind because a cloud session cannot delete it]:

| Push | Result | Exit code |
|---|---|---|
| a root commit to an absent ref, `--force-with-lease=<ref>:` (lease "must not exist") | created | 0 |
| a second, different root commit, same lease | refused, `(stale info)` | 1 |
| the same rival root, plain push | refused, `(non-fast-forward)` | 1 |
| a child of the current tip, plain push | accepted (fast-forward) | 0 |
| a child of an *older* tip, plain push (a take-over race's loser) | refused, `(non-fast-forward)` | 1 |
| **10 racing pairs**, two children of the same tip pushed at once | **exactly one winner in all 10**; every loser exit 1; the tip always the winner's commit | — |

So `git push` gives the lock the two properties its design rests on (`lock.py` docstring): a create is refused if the ref exists, and an update is refused unless it is a fast-forward. And it works where the REST API is refused. This build adds a second backend that uses it, makes "release" something a cloud session can do, and makes every refusal loud.

**The founder's choices this build is built under** (27 Nov, in a chat; G1 writes them into the master doc §10): builder and reviewer stay on **one** GitHub account for now (B05 "Halt if" option (c): guard rails, with the gate audit as the control), and the Mac's Claude Code will be logged in as the automation account. Neither changes this build's code. The second means this build is run **in a cloud session**, which acts as the automation, not on the Mac.

## Read first

- `v2/tools/loop/lock.py` (all of it: the `Lock` protocol and the `GitHubRefs` backend).
- `v2/tools/loop/facts.py` `_locks` (how the loop reads locks: **any** `lock/<id>` branch counts as held, aged by its last commit time).
- `.claude/skills/chronos-tick/loop_cli.py` `claim`, `finish` and `main` (where the backend is built).
- `v2/tests/tools/loop/test_lock.py`, `test_agent_files.py` (`FakeRefs`, the two `finish` tests), `test_facts_collectors.py`. These are frozen. They must pass unmodified.
- `specs/B03-loop-core.md` "Locks" and step 4 (the race proofs this build repeats on the new backend).
- `reports/B05.md` "For the gate" traps 1–3 and 8; `BUILD_NOTES.md` on CI identity (the `IDENTITY` comment in `test_lock.py`).

## Deliver

1. **`GitPushRefs`**, a new backend class in `lock.py` with the same duck type as `GitHubRefs` (`read`, `message`, `commit`, `create`, `update`, `delete`), working on a local clone through `git` subprocesses. `GitHubRefs` stays in the module.
   - `__init__(repo_dir, remote="origin", runner=None)`. `runner` is injectable like `GitHubRefs`'s, so tests need no network.
   - `commit(message, parent)`: `git commit-tree` on the **empty tree** (`4b825dc642cb6eb9a060e54bf8d69288fbee4904`), with `-p parent` when given. Author and committer identity are set **in the subprocess environment** (a fixed loop identity such as `Chronos Loop <loop@chronos.invalid>`), so it works on a machine with no git identity at all. `test_lock.py` records how this exact trap first went green locally and red in CI.
   - `create(ref, sha)`: if the remote ref is absent, push `sha:ref` with `--force-with-lease=<ref>:` (must not exist). If the remote tip is a **release marker** (item 2), push `+sha:ref` with `--force-with-lease=<ref>:<marker sha>`, replacing the marker only if it is still the tip. If the tip is a held lock, return False without pushing.
   - `update(ref, sha, expect)`: plain push `sha:ref`, never `+` and never `--force`, so only a fast-forward is accepted.
   - `read(ref)`: the remote tip from `git ls-remote <remote> <ref>`, fetched if not present locally. Returns **`None` if the ref is absent or its tip is a release marker**, otherwise the sha.
   - `message(sha)`: the commit message, read locally after fetch.
   - `delete(ref)`, the release: if the remote tip is absent or already a marker, do nothing. Otherwise push a **release-marker commit** whose parent is the current tip, as a plain fast-forward push.
   - **Every push uses `--porcelain`, and its outcome is decided from that output and the exit code, never assumed.** A ref line flagged `!` (rejected: `stale info`, `non-fast-forward`, `fetch first`, `already exists`) makes `create`/`update` return **False**: another session won. **Any other non-zero exit** (network, proxy, authentication, HTTP 429) raises **`LockError`**, carrying git's stderr. That is a fault, not "someone else holds it". `delete` raises `LockError` on **any** failure, rejections included. A release that did not happen must never look like one that did.
   - `read` raises `LockError` when `ls-remote` or the fetch fails. An unreadable lock is never reported as free (the rule `is_stale` already follows).
2. **The release marker.** A commit whose message carries a trailer line `Chronos-Lock-Released: <ISO-8601 UTC time>` and **no** `Chronos-Lock-At:` line. Define the trailer as a constant beside `STAMP`, and a helper `is_release_marker(message) -> bool`.
3. **`GitHubRefs.delete` stops discarding the answer.** On a non-zero return code it raises `LockError` with GitHub's text. Nothing else in `GitHubRefs` changes.
4. **`facts._locks` skips released locks.** A `lock/<id>` branch whose tip message is a release marker is **not** reported as a lock, so `next_action` treats the build as unlocked. Every other branch is read exactly as today (time from `%cI`, message as today).
5. **`loop_cli.py` builds `GitPushRefs`.** A small factory, `production_refs(repo_root, github_repo)`, returns `GitPushRefs(repo_root)`. `main()` uses it for `claim` and `finish` in place of `GitHubRefs(...)`. `claim`'s and `finish`'s behaviour is unchanged: `finish` already reports a failed release in words (`test_finish_reports_a_lock_it_could_not_release_instead_of_assuming`), and that path is now reachable for real.
6. **`prove_lock_by_push.py`**, a harness beside `prove_lock_on_github.py`, run by hand from a **cloud** session against this repository, on the one ref `refs/heads/lock/zz-proof-b05a`. It runs, through the real `Lock` and `GitPushRefs`:
   - 20 racing `acquire` pairs: two threads, distinct session ids, on an absent or released ref. Count the winners, and have the winner release.
   - 20 racing `take_over` pairs: on a lock written with a stamp 4 hours old, two threads take over at "now". Count the winners, and have the winner release.
   - one `acquire` → `renew` → `release` cycle, then `facts._locks` on a fresh fetch, which must not report the ref.

   A pair in which either racer hit a transport error (a `LockError`, not a rejection) is recorded **and re-run**, not counted. The harness prints the counts, the number of re-runs and why, and one sample pair's porcelain lines. It leaves the ref in the released state; the cloud cannot delete it.

## Steps

1. Commit the known-answer tests below, in the two new test files. Run them: they fail because `GitPushRefs`, `is_release_marker` and `production_refs` don't exist and `facts._locks` reports markers. Paste the failing summary line into the report.
2. `GitPushRefs`, the marker, and `GitHubRefs.delete` (Deliver 1–3). The lock tests go green; every existing test still passes.
3. `facts._locks` and `loop_cli.production_refs` (Deliver 4–5). Green.
4. `prove_lock_by_push.py`, run from a cloud session against GitHub (Deliver 6). Paste its output into the report.
5. **End to end, from a cloud session:** run `loop_cli.py finish --build ZZ-PROOF-B05A` against the real repository after an `acquire` on that id. It must print "Lock on ZZ-PROOF-B05A released.", and `next_action.py` must run cleanly afterwards. Then the report, CHANGELOG and status, in the same commit as the last code change (builder rule 7).

## Known answers and checks

All tests in step 1 run against a **throwaway local bare repository reached as a `file://` remote from a real local clone**, through the real `GitPushRefs` code and real `git push`, not an emulation. That is the difference from `test_lock.py`'s `BareRepoRefs`, and it is the point: these test the production backend.

**`v2/tests/tools/loop/test_lock_by_push.py`**

| # | Setup | Required |
|---|---|---|
| 1 | ref absent; `create` | returns `True`; the bare repo's ref equals the sha |
| 2 | ref held; `create` with a different root commit | returns `False`; ref unchanged |
| 3 | ref held; `update` with a child of the tip | `True`; ref moved |
| 4 | ref held; `update` with a child of an older commit (a sibling of the tip) | `False`; ref unchanged |
| 5 | ref held; `delete` | ref **still exists** in the bare repo; its tip's message satisfies `is_release_marker`; its parent is the previous tip; `read(ref)` is `None` |
| 6 | ref released; `create` with a new root | `True`; tip is the new commit |
| 7 | ref absent; `delete` | no error; the ref still does not exist |
| 8 | ref released; `delete` again | no error; the tip is unchanged (no second marker) |
| 9 | remote URL points at a path that does not exist; `create`, `update`, `read`, `delete` | each raises `LockError` whose text includes git's stderr. **None returns `False` or `None`** |
| 10 | 20 racing `Lock.acquire` pairs (two threads, distinct session ids) on an absent ref, the winner releasing after each pair | exactly one `True` in every one of the 20 |
| 11 | 20 racing `Lock.take_over` pairs on a lock whose stamp is 4 h old | exactly one `True` in every one of the 20 |
| 12 | `commit` run with `HOME` set to an empty temp dir and `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` | succeeds (the identity comes from the backend, not the machine) |
| 13 | `Lock.acquire` → `release` → second session `acquire`, all through `GitPushRefs` | the second acquire is `True`. A released lock is free |
| 14 | `GitHubRefs` with a fake runner returning `(1, "HTTP 403 not permitted")` for the `DELETE`; `delete` | raises `LockError` containing `403` |
| 15 | every push `GitPushRefs` makes (capture the runner's argv) | carries `--porcelain`; **none** carries `--force` or `-f`; the only `+` refspec appears together with a `--force-with-lease=<ref>:<sha>` naming a release marker |

**`v2/tests/tools/loop/test_lock_release_marker.py`**

| # | Setup | Required |
|---|---|---|
| 16 | `is_release_marker` on a marker message; on a `message_for(...)` lock message; on `""` | `True`, `False`, `False` |
| 17 | `facts._locks` with an injected `git` function: `lock/b06` tip is a marker, `lock/b09` tip is an ordinary lock message | result has `B09` with its time and message, and **no `B06`** |
| 18 | `loop_cli.production_refs(repo_root, "owner/repo")` | returns a `GitPushRefs` whose `repo_dir` is `repo_root` |
| 19 | `loop_cli.finish` with a `GitPushRefs` over a local bare repo where the lock was acquired | prints "released"; the bare ref's tip is a marker |

**And:** every test that exists on `v2-build` today passes **unmodified**, `test_lock.py`, `test_agent_files.py` and `test_facts_collectors.py` included, with **one exception**, below.

**Amendment, 27 Nov (the founder's choice (a) after the builder halted at step 2; `status/B05A.json` on `claude/b05a` at `52e3d13`).** As first written, this spec could not be met: Deliver 3 and known answer 14 make `GitHubRefs.delete` raise on a non-zero answer, and two frozen tests in `test_lock.py` call `delete` through `FakeGh()`, whose default answer to every call is `(1, "{}")`. With Deliver 3 in place they went red [Certain — run: 4 failed, 400 passed]. So `test_lock.py` is now in `may_modify_tests`, under these limits:

- Only **`test_the_backend_deletes_the_reference_from_the_plural_refs_route`** and **`test_every_write_route_the_backend_uses_starts_with_git_refs`** may change. Every other line of the file stays byte-for-byte as on `v2-build`, `FakeGh` included.
- The only permitted change is to give the `DELETE` call a **success answer** (for example, constructing `FakeGh` with an answer of `(0, "")` for the delete), so that `delete` does not raise.
- Every existing assertion in both tests stays, unweakened: the route (`repos/owner/repo/git/refs/heads/lock/b06`), the `("-X", "DELETE")` verb, and "every write route starts with `git/refs`". Nothing is removed, skipped or wrapped in `pytest.raises`.
- The report lists the diff to `test_lock.py` under its deviations, and the reviewer checks it against these limits.

`test_agent_files.py` and `test_facts_collectors.py` remain frozen.

**On GitHub (step 4, in the report, not a test):** 20 of 20 acquire pairs and 20 of 20 take-over pairs with exactly one winner, from a cloud session, with the re-run count. Then a clean acquire → renew → release, after which `facts._locks` does not report `lock/zz-proof-b05a`. **Any pair with two winners is a halt.**

## Not in this build

- **Deleting lock branches.** The cloud cannot, so released locks stay as marker branches. The founder can prune `lock/*` from the Mac whenever he likes; nothing depends on their absence. Two exist already: `lock/b05a-probe` (this spec's measurement) and `lock/zz-proof-b05a` (step 4).
- **Checking that a release is by the holder.** `Lock.release` calls `refs.delete` without checking `still_mine`, as today, because `finish` runs in a later process that does not know `mine`, and the frozen test `test_finish_releases_the_lock_and_prints_the_status_report` releases a lock its `Lock` object did not take. A session that lost a stale lock and then finishes would release the winner's lock, exactly as with today's backend. For the gate, not here.
- The B05 probes (B97–B99) and the per-tick cost: **B05B**.
- Logging the Mac's Claude Code in as the automation (the founder, by hand; HANDBOOK §2).
- `next_action.py`, the decision table, `prove_lock_on_github.py`, and anything about how actions are chosen.

## Halt if

- GitHub, through the cloud proxy, accepts a push that is not a fast-forward without `+`, or accepts a lease whose expected value is wrong. The design is then unsound: stop and say so.
- Any racing pair on GitHub has two winners, or a pair keeps failing on transport errors so that 20 clean pairs cannot be reached in one tick.
- The proxy refuses `git push` to `refs/heads/lock/*` (it did not on 27 Nov).
- Making a known answer pass needs a change outside `touches`, or a change to a frozen test.
- `--porcelain` output cannot separate a rejection from a transport failure on this git version. Name the version and what it printed.

## For the gate

- **New traps for `BUILD_NOTES.md`:** a lock released by a marker leaves its branch behind, so anything that reads `lock/*` must read the tip, not just test that the branch exists. `git push --porcelain` and the exit code are the only trustworthy outcome of a push.
- **The release-by-a-non-holder gap** above: decide at G1 whether `finish` should carry the session id and refuse to release a lock that names another session (that needs `test_agent_files.py` in `may_modify_tests`, so it is the founder's call).
- **`LEDGER.md`:** B05A's ticks and rounds.
