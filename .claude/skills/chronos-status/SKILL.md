---
name: chronos-status
description: Say where the Chronos build loop stands, in three plain sentences -- what is running, what is next, and what is waiting on the founder. Reads only; changes nothing. Use when the founder types /chronos-status or asks what the loop is doing, where things stand, or whether anything needs him.
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /chronos-status — where things stand

Read-only. This command takes no lock, dispatches nothing and writes
nothing.

> **Not `/status`.** That is a built-in Claude Code command that opens the
> settings panel and shows this session's version, model and account, and a
> skill cannot take a name a built-in already uses. The handbook tells the
> founder to type `/status` to check which model he is on, and that still
> works and still means that. This command is the Chronos one.

## Do this

```
cd "$(git rev-parse --show-toplevel)"
git fetch --no-tags --prune origin
python3 .claude/skills/chronos-tick/loop_cli.py status
```

The fetch comes first for the same reason it does in `/chronos-tick`: the
facts are read from the local clone, so a stale clone reports a build's
status, review count and lock age as empty and the answer is quietly wrong.

Add `--ladder <path>` if the founder gave one.

## Then

Show the three sentences as they are printed. They are written for the
founder and need no translation — *"B09 is waiting to be reviewed, round 1.
Next after that: B10. Nothing is waiting on you."*

If he asks for more than that, answer from the repository rather than from
memory: `docs/v2/build/LEDGER.md` for estimate against actual, the build
reports in `docs/v2/build/reports/` for what each build did, and the pull
requests on GitHub for what is open. Say which one you read.

If the script fails, say so plainly and show the error. Do not reconstruct
the answer by reading the status files yourself and guessing — a status
report that is assembled by hand is an opinion, and the point of this
command is that it is not one.
