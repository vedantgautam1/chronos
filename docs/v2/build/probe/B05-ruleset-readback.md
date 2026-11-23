# B05 Deliver 3 — rulesets, read back through the API

Deliver 3 says the founder clicks and Claude reads every setting back through
the API. This file is that read-back, verbatim, round by round. `GET /rulesets`
is one of the few write-adjacent routes a cloud session may use, so this was
done from here as the automation account `vedant420420`.

The authority for "is this branch actually protected" is
`GET /repos/{o}/{r}/rules/branches/{branch}`, which reports the rules GitHub
would really apply. Reading the ruleset's own configuration is **not**
sufficient, as round 1 below shows.

---

## Round 1 — 23 Nov 14:29 ET — BOTH RULESETS PROTECTED NOTHING

Two rulesets existed, both `enforcement: active`, both looking correct in the
list view:

```
id=27924823  name=MAIN      target=branch  enforcement=active
id=27930220  name=v2-build  target=branch  enforcement=active
```

And yet:

```
GET /rules/branches/main      -> []   NO RULES APPLY
GET /rules/branches/v2-build  -> []   NO RULES APPLY
GET /rules/branches/MAIN      -> 7 rules from both rulesets
GET /git/ref/heads/MAIN       -> 404 Not Found
```

### Defect 1 — both rulesets targeted a branch that does not exist

Both carried `conditions.ref_name.include: ["refs/heads/MAIN"]`. Git ref names
are case-sensitive, the repository's branch is `main`, and no branch named
`MAIN` exists. So `main` and `v2-build` were **completely unprotected** while
the settings page showed two active rulesets.

This is the "false wall" the build exists to prevent, and it would have
survived any check short of this one. The ruleset list looked right. Each
ruleset's own configuration looked right. Had the attack tests been run in this
state, A1–A11 would each have "succeeded", and the honest-looking conclusion
would have been *the protections do not work* — when the truth was that they
were pointed at a phantom. Reading configuration is not measurement.

### Defect 2 — the `v2-build` ruleset had no required status checks at all

Ruleset 27930220's `rules` array contained `deletion`, `non_fast_forward` and
`pull_request`. There was **no `required_status_checks` entry**. The five checks
were never added to it.

### What was correct in round 1

Worth recording, because these did not need redoing:

| Setting | `MAIN` (27924823) | `v2-build` (27930220) | Spec wants |
|---|---|---|---|
| `enforcement` | `active` | `active` | active |
| `current_user_can_bypass` | `never` | `never` | bypass list empty ✓ |
| `deletion` rule | present | present | no deletion ✓ |
| `non_fast_forward` rule | present | present | no force-push ✓ |
| `required_approving_review_count` | `1` | `0` | 1 / 0 ✓ |
| `dismiss_stale_reviews_on_push` | `true` | `true` | true ✓ |
| `require_code_owner_review` | `true` | `true` | true ✓ |
| `require_last_push_approval` | `true` | `false` | true / off pending A10 ✓ |
| `allowed_merge_methods` | `["merge"]` | `["squash"]` | merge / squash ✓ |
| `required_status_checks` | 5, all `integration_id: 15368` | **absent** | 5, pinned to Actions |

`integration_id: 15368` is GitHub Actions, so the five checks on 27924823 are
pinned to the right source, and the two long check names went in correctly:

```
tests
lint
v1-oracle
guards (from the base commit's copy)
earlier-tests (the base's tests, this branch's package)
```

### One setting the spec does not mention

`require_extra_approval_for_unattributed_changes` came back `true` on
`MAIN` and `false` on `v2-build`. The spec names neither. It appears to be a
GitHub default applied at creation rather than anything the founder chose.
[Guessing — not verified against GitHub's documentation.] It is recorded here
rather than silently normalised, and it should be read fresh and either
adopted or turned off deliberately before the gate.

### Fixes asked of the founder

1. Ruleset 27924823: target `main`, not `MAIN`. Rename it to `main` too, so
   the record is not confusing.
2. Ruleset 27930220: target `v2-build`, not `MAIN`.
3. Ruleset 27930220: add **Require status checks to pass** with the same five
   checks, each pinned to GitHub Actions.

Neither can be fixed from here: `POST /rulesets` is refused by the proxy, and
the automation is a collaborator rather than the owner, so GitHub would refuse
it as well. That second refusal is what A6 tests.

### No attack test was run in this state

A1–A12 were not attempted against an unprotected repository. An attack that
"succeeds" because nothing was protecting the branch measures nothing, and
recording it as a result would be worse than not running it.

---

## Round 2 — 23 Nov 14:48 ET — both branches protected, every setting matches

The founder fixed all three defects. The authority first:

```
GET /rules/branches/main      -> deletion, non_fast_forward, pull_request, required_status_checks  (ruleset 27924823)
GET /rules/branches/v2-build  -> deletion, non_fast_forward, pull_request, required_status_checks  (ruleset 27930220)
GET /rules/branches/MAIN      -> []   the phantom is gone
GET /rules/branches/claude/b05-> []   build branches are unprotected, as intended
```

`main`'s ruleset now targets **`~DEFAULT_BRANCH`** rather than a literal name,
which is the more durable of the two options: renaming the default branch
cannot silently unprotect it. `v2-build`'s targets `refs/heads/v2-build`.

### Every setting, read back

| Setting | `main` (27924823) | `v2-build` (27930220) | Spec | ✓ |
|---|---|---|---|---|
| `enforcement` | `active` | `active` | active | ✓ |
| `current_user_can_bypass` | `never` | `never` | bypass list empty | ✓ |
| targets | `~DEFAULT_BRANCH` | `refs/heads/v2-build` | main / v2-build | ✓ |
| `conditions.ref_name.exclude` | `[]` | `[]` | — | ✓ |
| `deletion` | present | present | no deletion | ✓ |
| `non_fast_forward` | present | present | no force-push | ✓ |
| `required_approving_review_count` | `1` | `0` | 1 / 0 | ✓ |
| `dismiss_stale_reviews_on_push` | `true` | `true` | true | ✓ |
| `require_code_owner_review` | `true` | `true` | true | ✓ |
| `require_last_push_approval` | `true` | `false` | true / off pending A10 | ✓ |
| `required_review_thread_resolution` | `false` | `false` | not specified | — |
| `allowed_merge_methods` | `["merge"]` | `["squash"]` | merge / squash | ✓ |
| `strict_required_status_checks_policy` | `false` | `false` | not specified | — |
| `do_not_enforce_on_create` | `false` | `false` | not specified | — |
| required checks | 5 | 5 | 5 | ✓ |

All ten required-check entries (five on each ruleset) carry
`integration_id: 15368`, which is GitHub Actions, so every check is pinned to
its source as Deliver 3 requires. The contexts, verbatim on both:

```
tests
lint
v1-oracle
guards (from the base commit's copy)
earlier-tests (the base's tests, this branch's package)
```

### Still unresolved, carried to the gate

`require_extra_approval_for_unattributed_changes` remains `true` on `main` and
`false` on `v2-build`. The spec names it nowhere and the founder did not set it
deliberately; it appears to be a GitHub default that differs by how each
ruleset was created. [Guessing — not verified against GitHub's documentation,
and this build did not read that documentation fresh.] Left as found rather
than normalised, and flagged for a deliberate decision.

### First evidence the rulesets bite

PR #38 (`claude/b05` → `v2-build`, opened by the automation) went from
`mergeable_state: clean` to **`mergeable_state: blocked`** the moment ruleset
27930220 began targeting `v2-build`. B05's own pull request is now subject to
the rules B05 installed, which is the cheapest possible confirmation that they
apply to something real.

### What this round does **not** establish

That any protection is a **wall**. Settings reading back correctly is what
round 1 proved is not enough. Only Deliver 4's attacks, each refused by GitHub
for the reason named in the spec's table, can make that claim — and none has
been run yet.

---

## Where each attack can run, measured rather than assumed

From the route map in `B05-environment-measurements.md` §3 and §7c, with the
cloud session now acting as the automation:

| Attack | Runnable from cloud as the automation? | Why |
|---|---|---|
| A1 | **yes** | git push, `POST /pulls`, `PUT /merge` all allowed |
| A2 | partly | the founder must open the `doc/a2` pull request |
| A3 | partly | the founder must approve before the second push |
| A4 | **no** | `POST /statuses` refused by the proxy — needs the Mac |
| A5 | partly | push and force-push yes; **delete and rename** need the Mac |
| A6 | **no** | `POST /rulesets` refused by the proxy — needs the Mac |
| A7 | **yes** | ordinary pull request and merge attempt |
| A8 | partly | the founder must approve before the second push |
| A9 | **yes** | five pull requests that must each be refused |
| A10 | **yes** | control; `lane/…` into `v2-build` is a guard-recognised kind and `/scratch/` has no code owner |
| A11 | **yes** | corrected from round 1: `_agent_for` returns `None` for `WAIT_FOUNDER`, so `tick` returns **before** `Lock(...)` is constructed. A halted loop never reaches the lock, so the cloud lock defect does not block A11 |
| A12 | **no** | `GET /collaborators` refused by the proxy; the installed-Apps half needs the founder's own screen either way |

One correction to round 1's pessimism: A5 is **mostly** runnable from cloud,
not wholly blocked. Pushing directly and force-pushing are the two sub-tests
the ruleset is supposed to refuse, and both use `git push`, which is allowed.

### Cleanup debt the attacks will create

A1–A10 need roughly eleven branches (`doc/a1`–`doc/a4`, `spec/a7`, five for
A9, `lane/a10`). A cloud session cannot delete a branch by any route, so they
will accumulate and need deleting from the Mac in one batch at the end. Noted
in advance rather than discovered afterwards.
