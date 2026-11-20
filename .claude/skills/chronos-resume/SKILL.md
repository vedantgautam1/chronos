---
name: chronos-resume
description: Turn the Chronos loop back on after a pause -- and refuse, every time, to lift an emergency stop. Use when the founder types /chronos-resume or says to resume the loop, start it again, carry on, or unpause Chronos.
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /chronos-resume — turn the loop back on

> **Not `/resume`.** That is a built-in Claude Code command that reopens a
> previous conversation, and a skill cannot take a name a built-in already
> uses. This command is the Chronos one.

## Do this first, always

```
cd "$(git rev-parse --show-toplevel)"
python3 .claude/skills/chronos-tick/loop_cli.py resume
```

## If a stop is in force

It will refuse, and it names the issue. Pass that on as it is written:

> close the issue yourself on GitHub; only your account releases the stop

**There is no code path in this command that closes an issue.** That is
deliberate, and it is the answer to a red-team finding: an automation able
to close its own emergency stop has no emergency stop. So do not close it,
do not remove the label, do not open a replacement issue, and do not offer
to "clear it" by another route. If he insists, tell him again where the
button is — Issues → the open `chronos-halt` issue → Close — and that it has
to be his account that clicks it.

If the command cannot tell whether a stop is in force, it treats that as a
stop and resumes nothing. That is the right way round.

## If no stop is in force

Then there is nothing here to lift, and what actually restarts the loop is a
switch only the founder can reach: **the Claude app → Scheduled tasks →
"Chronos build loop" → on.** Tell him that. This command cannot switch a
scheduled task on for him, and should not pretend to.

If he wants work done right now instead of waiting for the next wake-up, the
answer is `/chronos-tick`, which does one action and stops.

## Never

Nothing in this command merges anything, and it never merges into `main`.
`main` moves only at a gate, on his own approval.
