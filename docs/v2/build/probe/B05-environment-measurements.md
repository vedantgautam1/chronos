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
