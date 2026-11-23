# B05 — what a cloud session can and cannot do on GitHub

Measured 2026-11-20, build round 1, in a **cloud** Claude Code session on Opus,
acting as GitHub user `vedantgautam1` (the founder's own account — the identity
switch of Deliver 2 had not happened yet). Repo `vedantgautam1/chronos`.

This file exists because B05 halted at step 0 on what is in it. It is kept
under `docs/v2/build/probe/**` (this build's `touches`) so the measurements are
not lost between rounds, and so the next session does not re-run them blind.

Every line below is **[Certain — run]** unless it says otherwise. Each was
executed in this session and the response text is quoted as it came back.

## 1. Which identity a cloud session uses

```
gh api user  ->  {"id":148167806,"login":"vedantgautam1","type":"User"}
```

A cloud session acts as **the founder's own account**. This is the fact
Deliver 2 exists to change, and it is confirmed rather than assumed.

`gh auth status` reports `The token in GH_TOKEN is invalid` while `gh api`
works — the known trap, confirmed, not chased.

## 2. The two refusal texts, and who is refusing

Two different refusals come back, both from **Anthropic's session proxy**, not
from GitHub. Both carry `documentation_url:
https://docs.anthropic.com/en/docs/claude-code/github-actions`:

- reads: `403 "Access to this GitHub API path is not permitted through this proxy."`
- writes: `403 "Write access to this GitHub API path is not permitted through this proxy."`

The distinction matters for every attack test: a refusal whose text names *the
proxy* is not GitHub refusing, so it cannot prove a GitHub protection.

## 3. Route-by-route result

| Route / operation | Result | Needed by |
|---|---|---|
| `GET /git/ref/heads/<name>` | **allowed** | lock read |
| `POST /git/commits` | **BLOCKED** (write) | lock take, lock renew |
| `POST /git/refs` | **BLOCKED** (write) | lock take |
| `PATCH /git/refs/heads/<name>` | **BLOCKED** (write) | lock renew |
| `DELETE /git/refs/heads/<name>` | **BLOCKED** (write) | lock release, A5, B98/B99 cleanup |
| `git push <sha>:refs/heads/<new>` | **allowed** (branch created) | builder push |
| `git push --force` | **allowed** (branch overwritten) | A5 |
| `git push --delete` / `:ref` / zero-sha | **BLOCKED** `RPC failed; HTTP 403` | A5, B98/B99 cleanup |
| `POST /repos/.../pulls` | **allowed** | open PR |
| `PUT /pulls/{n}/merge` | **allowed** | merge, A1–A3, A7–A10 |
| `POST /pulls/{n}/reviews` | **allowed** | approve, A1–A3 |
| `POST /pulls/{n}/ccr/ready_for_review` | **allowed** | mark ready |
| `POST /statuses/{sha}` | **BLOCKED** (write) | **A4** |
| `POST /repos/.../issues` | **allowed** | `/chronos-halt` |
| `PATCH /issues/{n}` | **allowed** | A11 (close) |
| `DELETE /labels/{name}` | **allowed** | A11 (delete label) |
| `POST /repos/.../rulesets` | **BLOCKED** (write) | **A6** |
| `GET /repos/.../rulesets` | **allowed** (returns `[]` today) | Deliver 3 read-back |
| `GET /repos/.../collaborators` | **BLOCKED** (read) | **A12** |
| `GET /repos/.../actions/permissions` | **BLOCKED** (read) | Deliver 2 read-back |
| GraphQL (`gh api graphql`) | **BLOCKED** | `gh pr ready`, `gh pr review` |

Write routes were probed against deliberately non-existent targets (PR/issue
`99999`, label `__nope__`, empty required fields) so that an *allowed* route
answers `404 Not Found` or `422 Validation Failed` instead of changing
anything. A route is recorded as allowed only where GitHub's own error came
back; `BLOCKED` is the proxy text above and nothing else.

## 4. The lock, run rather than read

`v2/tools/loop/lock.py` states its design rests on two REST properties, both
proved against GitHub on 19 Nov by B03. Those properties are untouched. What
is measured here is that a cloud session cannot reach the routes that use them.

Driven through `Lock` + `GitHubRefs` directly, throwaway id `b05proxyprobe`:

| Operation | Measured behaviour |
|---|---|
| `read()` on a missing ref | returns `None` — correct |
| `acquire()` | **raises** `LockError: could not write a lock commit: {... not permitted through this proxy ...}` |
| `release()` on a ref that does not exist | **returns normally** |
| `release()` on `refs/heads/lock/proxytest`, which existed before and still existed after | **returns normally** |

Two consequences, and they point in opposite directions:

1. **`acquire()` fails loudly.** The raise comes from `GitHubRefs.commit`, and
   in `loop_cli.tick` the `try/except LockError` wraps only `is_stale`, not the
   `lock.acquire(...)` call on the line above it — so an unattended tick ends
   with an uncaught `LockError` before it dispatches any agent. Nothing is
   silently claimed. This is the safe direction.
2. **`release()` fails silently, and reports success.**
   `GitHubRefs.delete` calls `self._run("-X", "DELETE", ...)` and discards the
   return code, so `release()` cannot fail. `loop_cli.finish` therefore prints
   `Lock on <id> released.` on a lock that is still held. That is exactly the
   state B05's spec names as worse than having no lock: *"the status report will
   say it has one."* Proved above against a ref demonstrably still present
   afterwards.

`v2/tools/loop/lock.py` is **outside this build's `touches`**, so this build
cannot fix either one (builder rule 4).

## 5. Branch deletion is blocked in every namespace

Tested in two namespaces to tell "lock refs are special" from "deletes are
blocked", because B98 and B99 both require a branch to be deleted:

- `lock/proxytest` — `git push --delete`, `:ref`, zero-sha, `DELETE /git/refs`: all refused
- `doc/b05-deltest` — the same four routes: all refused

So it is universal: **a cloud session can create and force-push a branch and
cannot delete one.**

### Two branches this session must ask the founder to delete

Created by the tests above and not removable from here:

- `lock/proxytest` — left pointing at `v2-build`'s head `b9c4f5d` (harmless;
  it was force-pushed to `v1-final`'s head during test 5 and then put back)
- `doc/b05-deltest` — pointing at `v2-build`'s head `b9c4f5d`

Neither is on the ladder and neither affects any guard. They are recorded here
rather than quietly left behind.

## 6. Three stale claims in the record, corrected

| Claim | Where | Correction |
|---|---|---|
| The `chronos-halt` label does not exist | `reports/B03.md`, `reviews/B04-r1.md` | **It exists.** Ten labels: the nine GitHub defaults plus `chronos-halt`. A11 has what it needs |
| Writes to `/git/refs` are refused | B04 builder, `B04-r1`, `B04-r2` | True, and **incomplete**: `POST /git/commits` is refused as well, and the lock reaches it *first*, so the take fails one call earlier than recorded |
| "In any Claude Code session (cloud, desktop app or the Mac terminal) the same commands work … a session takes a lock by creating a branch named `lock/<build>`" | `BLUEPRINT.md` §2.3 | Not true of cloud sessions. The *concept* survives — `git push` can create `lock/<id>` — but `lock.py` creates it through the REST API, which cloud sessions cannot reach, and no route releases it |

## 7. The open question this build cannot answer from here

Whether a Claude Code session **on the founder's Mac** is behind the same
proxy. [Guessing] — not tested, and not testable from a cloud session.

It decides between a cheap outcome and an expensive one, so it is the first
thing the next round should establish. One command answers it and also clears
one of the two stray branches in §5:

```
gh api -X DELETE repos/vedantgautam1/chronos/git/refs/heads/lock/proxytest
```

- no output, branch gone → the Mac is **not** proxied. B05 proceeds there
  largely as written: the lock works, A4/A5/A6/A12 become runnable, and only
  Deliver 5's *cloud* scheduled task stays in question.
- `403 "... not permitted through this proxy."` → the restriction is the
  platform's, not the environment's, and the halt options in
  `status/B05.json` are the decision.

## 7a. Re-measured 23 Nov, and made reproducible

Everything in §3 and §4 was re-run in a cloud session on **23 Nov** after a
three-day pause, and came back **identical** — same routes allowed, same
routes blocked, same two refusal texts. Nothing drifted.

`measure-env.sh`, beside this file, is the whole of §3 plus a real lock
take/renew/release cycle in one script, so the next session measures rather
than inherits. It must be run **inside a Claude Code session**, because that is
the environment the loop runs in; a plain Terminal with the founder's own `gh`
login answers a different question.

Its first draft carried the defect this build is halted over: when the lock
take was refused, it checked whether `lock/mactest` existed, found it absent,
and printed *"full take/release cycle worked"* — a false success, from the same
confusion between "the call did not happen" and "the call succeeded" that
makes `release()` lie in §4. It now asks GitHub whether the ref came into
existence, reports `lock ref actually created? no`, and declines to interpret
renew or release at all when the take failed.

### Status of the two stray branches from §5

- `lock/proxytest` — **deleted by the founder on 23 Nov.** Confirmed gone from
  here (`GET /git/ref/...` → 404). Which route or environment performed the
  delete is **not established**: a cloud session cannot delete a branch, so it
  was not this one, but nothing visible from here distinguishes a Claude Code
  session on the Mac from the GitHub web interface. `measure-env.sh` settles
  that question properly rather than inferring it from one success.
- `doc/b05-deltest` — **still present** at `b9c4f5d`. `measure-env.sh` deletes
  it wherever a delete route works.

## 7b. The Mac, measured 23 Nov — and what it does not settle

`measure-env.sh` run in a Claude Code session **on the founder's Mac**,
23 Nov ~14:47 UTC. Result: **every route in §3 allowed, nothing blocked.**

- reads: `/git/ref`, `/collaborators` (A12), `/actions/permissions`, `/rulesets`
  — all returned. GraphQL works.
- writes probed against non-existent targets: all reached GitHub and were
  refused by *GitHub* as `404`/`422`, which is the point.
- **the lock: full cycle works.** `lock/mactest` was created; a second create
  was refused *because it already existed* — the 422 the design rests on;
  renew and release both worked; the ref is gone.
- `doc/b05-deltest` deleted. No stray branches remain.

So the proxy of §2 is a **cloud-session** restriction, not a platform one.
GraphQL working on the Mac while being refused in cloud is the cleanest proof:
that refusal is a proxy rule, and on the Mac there is no proxy in the path.

**What this unblocks:** Deliver 1–4 — identity, repository settings, both
rulesets, and all twelve attacks including A4, A5, A6 and A12 — become
runnable, from the Mac.

**What it does not unblock: Deliver 5 and 6.** The three probes run through a
**cloud** scheduled task, and §3/§4 were re-run in cloud on 23 Nov and came
back identical. A scheduled cloud session still cannot take the lock, so B97
cannot run unattended. The Mac result narrows the halt; it does not lift it.

### The new question, and it is load-bearing for every attack

The Mac session reported `login=vedantgautam1`. **Today that is ambiguous**:
`vedantgautam1` is both the founder's own `gh auth login` keychain *and* the
account Claude's GitHub connection currently uses, so the two are
indistinguishable. They diverge the moment Deliver 2 switches Claude's
connection to the automation.

It matters because **an attack run under the founder's own token proves
nothing about the automation.** A1–A3 turn on which account acts; A4, A5, A6,
A11 and A12 turn on which *permissions* it has, and a personal access token
and a GitHub App installation token for the same account need not carry the
same permissions. [Likely — reasoned from how the two credential types work,
not measured here.]

`measure-env.sh` now prints `gh api user`, whether `GH_TOKEN` and
`GITHUB_TOKEN` are set (length only — **never the value**, since this output
gets pasted around) and `gh auth status`, so one re-run after the switch
settles it instead of leaving it to inference.

### A permanent side effect this build caused, recorded rather than buried

The first version of `measure-env.sh` aimed its A4 probe at `origin/v2-build`'s
**real** tip. In cloud that route is blocked and nothing happened. On the Mac it
is allowed, so it **wrote**: a `success` commit status named `__b05probe__` on
`b9c4f5d`, by `vedantgautam1`, at 14:47:47Z. GitHub does not allow a status to
be deleted, so it is permanent. The script now aims at
`deadbeef…deadbeef`, which answers `422 No commit found for SHA`.

Audited for anything else: no ruleset was created (`/rulesets` → `[]`), no
issue, labels still ten, no stray pull request, no stray branch. That status is
the only unintended write.

Two consequences, neither severe:

1. `__b05probe__` will appear in GitHub's **required-status-checks picker**
   when Deliver 3's rulesets are built. It must not be selected: nothing ever
   posts it, so requiring it would block every pull request.
2. It does **not** weaken A4. PR merges evaluate the *head* commit, and PR
   #37's head carries no statuses (`state: pending, total_count: 0`). The
   status was also posted by the founder's account, not the automation's, so it
   gives the automation nothing.

## 7c. The identity switch worked, and it worked mid-session

Measured 23 Nov, after the founder switched Claude's GitHub connection to the
automation account `vedant420420` (id 360309407):

- **A cloud session now acts as `vedant420420`.** `gh api user` returns it. The
  switch took effect **without restarting the session** — this same session had
  been acting as `vedantgautam1` an hour earlier. [Certain — run]
- Which routes are allowed did **not** change. Same allowed set, same blocked
  set, same two refusal texts. So the proxy filters by **path, not by account**,
  which is what §8 of round 1 called [Likely] and is now measured.

So the spec's `Halt if` bullet *"Claude's cloud sessions can't act as a separate
GitHub account"* does **not** fire: they can.

**Where each attack therefore runs.** A1, A2, A3, A7, A8, A9, A10 and A11 use
only routes cloud allows, and a cloud session is now the automation, so those
eight run from here with no workaround. A4, A5, A6 and A12 need routes only a
Mac session reaches, and whether a Mac session also follows Claude's connection
is still unmeasured — the re-run there is outstanding.

## 7d. The spec names two required checks that do not exist

Deliver 3 asks for required checks `tests`, `lint`, `v1-oracle`, `guards` and
`earlier-tests`. Read from the check runs GitHub actually reported on
`685ac56` and `deb346a` — not from the workflow files — the real names are:

| Spec says | GitHub actually reports | Source |
|---|---|---|
| `tests` | `tests` | `v2.yml` |
| `lint` | `lint` | `v2.yml` |
| `v1-oracle` | `v1-oracle` | `v2.yml` |
| `guards` | `guards (from the base commit's copy)` | `v2-guards.yml` |
| `earlier-tests` | `earlier-tests (the base's tests, this branch's package)` | `v2-guards.yml` |

The last two carry a `name:` override (`v2-guards.yml` lines 35 and 83) that
GitHub uses as the check-run name. **Requiring the bare names `guards` and
`earlier-tests` would wait for checks that never appear and block every pull
request permanently.**

Both overrides are **static strings** — the 13 `${{ }}` expressions in that file
are all in steps, none in a `name:` — so the long names are stable and safe to
require. [Certain — read, and confirmed against two commits' actual check runs.]

There is also a near-miss to avoid: `tests.yml` is a **v1** workflow whose own
job is named **`test`** (singular), and it reports twice per pull request
because it triggers on both `push` and `pull_request`. `test` is not one of the
five and must not be selected in its place.

**What B05 does about it:** requires the real names. That is a deviation from
the spec's wording and is recorded as one; it is not a fork, because requiring
a check that never runs cannot be what the spec intended. **What B05 must not
do:** change the `name:` lines to make the spec's wording true —
`.github/workflows/**` is outside this build's `touches` (builder rule 4).
Making the names plain, or correcting the spec to quote the real ones, is worth
its own small spec, and is the more durable of the two: a later build that
edits a `name:` line would silently stop satisfying the ruleset.

## 7e. PR #37 was merged into `v2-build` unreviewed

On 23 Nov at 10:23 ET the founder merged pull request #37 (`claude/b05` →
`v2-build`, merge commit `6f0ded6`) while `status/B05.json` still read
`building`. No review file exists and B05 has not been reviewed.

Recorded because the reviewer will see it and should see it flagged rather than
find it. What it does and does not mean:

- **Materially harmless.** The merge carried this measurements file, the
  `measure-env.sh` script and `status/B05.json` — 417 added lines of
  documentation, no code and no tests. All five checks were green on `685ac56`.
- **It did complete Deliver 1.** There are now zero open pull requests, so the
  repository is quiet for the attack tests.
- **Nothing stopped it, which is the point of this build.** `GET /rulesets`
  returned `[]` at the time. This is the gap Deliver 3 closes.
- `claude/b05` was fast-forwarded onto `6f0ded6` and B05's remaining work
  continues on it under a new pull request.

## 8. What this does **not** show

- Nothing here was run as the automation account; it does not exist yet. The
  refusals above are path-based and carry Anthropic's `documentation_url`, so
  changing which GitHub account the token represents is **[Likely]** not going
  to change them — but that is a read of the error text, not a measurement.
- No ruleset existed during these tests (`GET /rulesets` → `[]`), so nothing
  here says anything about whether GitHub's rules hold. That is Deliver 3 and 4,
  and none of it has been attempted.
- No attack test A1–A12 has been run. The table in §3 says which of them are
  *runnable* from a cloud session, not which pass.
