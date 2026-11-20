---
name: chronos-halt
description: Stop every Chronos session at once by opening a labelled chronos-halt issue on GitHub. Only the founder's own account can lift it. Use when the founder types /chronos-halt or says to halt Chronos, stop the loop, freeze everything, or hit the emergency stop.
disable-model-invocation: true
argument-hint: "[--reason <why>]"
allowed-tools: Bash, Read
---

# /chronos-halt — the emergency stop

This opens a GitHub issue carrying the `chronos-halt` label. While such an
issue is open, every Chronos session — scheduled or by hand — refuses to
act. It needs no pull request, so no check can block it, and it works from
the founder's phone when Claude is unavailable.

## Do this

```
cd "$(git rev-parse --show-toplevel)"
python3 .claude/skills/chronos-tick/loop_cli.py halt --reason "<why, in one line>"
```

If a stop is already in force it says so and opens nothing. If it cannot
tell whether one is in force, it opens nothing and says that instead —
guessing "no stop" is the one answer that must never be guessed.

## Tell the founder two things, in this order

1. **It is in force**, and the issue number.
2. **How it ends: he closes that issue himself on GitHub.** Nothing else
   does. If any other account closes it or takes the label off, the loop
   reads the issue's history and treats the stop as still standing.

## What this is, honestly

A **guard rail**, not a wall, and it stays one. The rule that only the
founder can lift it lives in the loop's own code, so a session determined to
ignore it could. The stops that nothing can override are the founder's
alone, and he should know both:

- switch the scheduled task off in the Claude app, or
- remove the automation's account from the repository on GitHub
  (Settings → Collaborators).

Treat this command as the convenient stop and those two as the certain ones.
Say so if he asks whether this is bulletproof; do not oversell it.

## Never

Do not close, unlabel, edit or work around a `chronos-halt` issue — not even
one you opened a moment ago, and not if the founder asks you to in the same
breath as something else. Lifting the stop is his account's job and
`/chronos-resume` will refuse it too. If he wants it lifted, tell him where
the button is.
