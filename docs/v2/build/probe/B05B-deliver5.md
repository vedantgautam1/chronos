# B05B — Deliver 2 (B05's Deliver 5, finished): the scheduled tasks, read back

**Recorded by:** the B05B builder session `session_01PidDBuPusdPMu4NRHHT4Gd`, 27 Nov 2026, acting on GitHub as the automation (`vedant420420`).
**Sources:** what the founder reported in this session's opening message (marked *founder*), and the scheduling tool's own read-back, taken by this session at about 22:42 UTC (marked *read back*). The founder did all of step 2 before this session began, so none of it was redone here.

## The four items

| Deliver 2 item | Outcome | Source |
|---|---|---|
| Delete the "Chronos review watcher" task | **Done.** Deleted by the founder. The read-back lists one task only, "Chronos build loop" | *founder*; *read back* |
| Remove **every connector** from "Chronos build loop" | **Not done. Could not be done.** The app's task editor shows no control for connectors, and the scheduling tool cannot change them. All seven remain: `Claude_Docs`, `Google_Sheets`, `Google_Drive`, `Higgsfield`, `Canva`, `Gmail`, `Claude_Code_Remote`. Recorded as a deviation (report, deviation 1); the B05B known answer "'Chronos build loop' has no connectors" is **not met** | *founder*; *read back* |
| Approval setting: leave it so runs go ahead unattended; say what it is | **`permission_mode: auto`**, unchanged | *founder*; *read back* |
| Point the prompt at the probe ladder for the probes, and back afterwards | **Not yet.** Done at step 3. Separately, the prompt was corrected at 22:03 UTC (below) | *founder*; *read back* |
| Revoke the automation's classic token from B05's Mac run, if it still exists | **Unverified.** The founder believes it was revoked; nobody has checked. No session can check it: a token's existence shows only on the founder's own GitHub settings screen | *founder* |

## The prompt and model correction, 22:03 UTC

The task's prompt used to say "Run the `tick` skill once". No skill called `tick` exists: B04 named it `chronos-tick`, because a skill cannot take a name a built-in command already uses (CLAUDE.md, "The commands"). At 22:03 UTC (the read-back's `updated_at` is `2026-11-27T22:03:12Z`) the prompt became:

> Check out the v2-build branch of vedantgautam1/chronos. Then run /chronos-tick once, exactly as .claude/skills/chronos-tick/SKILL.md on that branch says. Stop after one action.

and the model became `claude-opus-5-5`.

## One idle tick, fired by hand

| | |
|---|---|
| Fired | 22:29:29 UTC (`fired_at 2026-11-27T22:29:29.202042Z`) |
| Finished | 22:31:03 UTC (`finished_at 2026-11-27T22:31:03.806144Z`); run status `SUCCEEDED` |
| Session | `cse_01PidDButsQoYwzZeQ8kMoAt` |
| Answer | `WAIT_FOUNDER B05A`. B05A's status still read `passed`: its merge was recorded afterwards, in pull request #61, merged at 22:42:15 UTC |
| Lock, commits | none taken, none made (*founder*) |
| Five-hour allowance | **0% → 3%** (*founder*, from Settings → Usage) |

That is Deliver 3's "(c) one idle tick". A reading at whole-percent resolution: 3% could be anything from about 2.5% to 3.5% [Likely: the screen rounds], and nothing records whether anything else drew on the allowance between the two readings.

## The read-back, pasted

`list_triggers` (scheduling tool), `include_completed: true`, trimmed to the fields that matter here. `has_more: false`.

```
id                 trig_01BLsY181hgG64m66VhDnQCf
name               Chronos build loop
cron_expression    7 * * * *
enabled            false
created_at         2026-11-23T21:46:36Z
updated_at         2026-11-27T22:03:12Z
mcp_connections    Claude_Docs, Google_Sheets, Google_Drive, Higgsfield, Canva, Gmail, Claude_Code_Remote
notifications      push: true, email: false
permission_mode    auto
model              claude-opus-5-5
prompt             Check out the v2-build branch of vedantgautam1/chronos. Then run /chronos-tick
                   once, exactly as .claude/skills/chronos-tick/SKILL.md on that branch says.
                   Stop after one action.
last_run           SUCCEEDED, fired 2026-11-27T22:29:29.202042Z, finished 2026-11-27T22:31:03.806144Z,
                   session cse_01PidDButsQoYwzZeQ8kMoAt
```

No other task is listed, so the "Chronos review watcher" no longer exists.
