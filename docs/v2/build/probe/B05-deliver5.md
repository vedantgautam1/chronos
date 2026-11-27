# B05 Deliver 5 — the scheduled task and the spending limit

## The task, created 23 Nov 21:46 UTC and switched off

| Spec asks for | What was created | ✓ |
|---|---|---|
| one cloud scheduled task | `trig_01BLsY181hgG64m66VhDnQCf` | ✓ |
| named "Chronos build loop" | `Chronos build loop` | ✓ |
| this repository | cloud environment of this session, which is this repository's | ✓ |
| model **Opus** | `model: claude-opus-5` | ✓ |
| hourly, a few minutes past the hour | `7 * * * *` | ✓ |
| push notifications on | `notifications.channel: {push: true, email: false}` | ✓ |
| prompt | ``Check out `v2-build`. Run the `tick` skill once. Stop.`` | ✓ |
| created switched **off** | `enabled: false` | ✓ |

**It could not be created switched off in one step.** The creation API has no
disabled option, so it came into being `enabled: true` with `next_run_at`
22:07 UTC, and was disabled 18 seconds later. Verified afterwards with
`list_triggers`: `enabled: false`. No firing occurred in the gap, and at 21:46
the next one was 21 minutes away — but the window was real and is recorded
rather than glossed. Anyone repeating this should expect it and disable
immediately.

## Two things about it the spec does not mention

**1. Its runs are set to act without asking for approvals.**
`derived_state.permission_mode: auto`. The server chose this; it was not
requested. For an unattended loop it is arguably what you want — a run that
stops to ask has nobody to ask — but it means a firing session acts on this
repository with no human gate, and it should be a deliberate choice rather
than a default nobody noticed. Changeable from the task's own settings.

**2. DO NOT ENABLE IT until `lock.py` is fixed.**
A cloud session cannot take the lock (`B05-environment-measurements.md` §4).
Every firing would raise `LockError` before dispatching anything, and with push
notifications on, that is an hourly failure notification. The task is correct
as configured and useless until the lock is.

## A second scheduled task already exists, and the two overlap

`list_triggers` shows another one, which this build did not create:

```
trig_01BRQchiJzEja42PEFYEhVvD   "Chronos review watcher"
  enabled: false     created 17 Nov     model: claude-opus-5-5
  cron: CRON_TZ=America/Toronto 17 */2 * * *     push notifications on
  permission_mode: auto
```

Its prompt has it review finished builds every two hours — reading
`status/<id>.json` on each `claude/b*` branch, writing review files and setting
statuses — on the premise (its words) that builds are written by DeepSeek on
the founder's Mac under "proposal P-24". It carries its own instruction not to
merge B01–B05.

It is **off**, so nothing is wrong today. But the spec for Deliver 5 says *one*
cloud scheduled task, and there are now two that both write to this repository.
If both were enabled they would race: the review watcher sets statuses directly
without taking the lock, while the loop's whole design is that one session
holds the lock and dispatches. Recorded as a thing for the founder to decide
before either is switched on — delete it, or keep it and reconcile it with the
loop. Not something this build should quietly remove.

## The spending limit — **not done**

Deliver 5's second half is the founder's usage-credit limit, set in Claude
settings. It is a founder-only action on a page no session can read, so it is
outstanding and recorded as outstanding.

The same applies to the allowance figures the report is supposed to carry:
*"the allowance figures the founder reads from Settings → Usage before and
after"*. There were no probe runs to measure, so there is no before-and-after
to read. That measurement is not deferred — it is **void for this build**,
because the thing it measures did not happen.
