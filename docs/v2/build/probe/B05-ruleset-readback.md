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
