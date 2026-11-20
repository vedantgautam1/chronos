---
name: chronos-tick
description: Do whatever the Chronos build loop says is next -- one action, then stop. Ask the loop's script what to do, refuse if the session is on the wrong model, take the lock, dispatch the named agent, release the lock and report. Use when the founder types /chronos-tick or asks to run the loop, do the next build, review or merge.
disable-model-invocation: true
argument-hint: "[finish --build <id>] [--ladder <path>]"
allowed-tools: Bash, Read
---

# /chronos-tick — do the next thing, once

**You never choose the action.** An ordinary script does, by reading the
ladder, the branches, the status files and GitHub. You run it, obey it, and
stop. If you find yourself reasoning about which build ought to be next,
that is the bug: ask the script again.

**You never merge into `main`.** `main` moves only at a gate, on the
founder's own approval. Nothing in this command merges anything.

## 1. Fetch first, then ask

```
cd "$(git rev-parse --show-toplevel)"
git fetch --no-tags --prune origin
```

Do this **before** anything else, every time. `facts.gather` discovers
branches with `git ls-remote` — the remote — but reads them as
`refs/remotes/origin/<name>` — the local clone. On a stale clone four facts
read empty at once: the lock's age, the build's status, its review count and
its head commit. Measured on B03 with real git: a build that is in fact
`changes_requested` with two review files reads as `state=None, rounds=0`,
and the loop returns `RESUME_BUILD` where row 17 says `HALT`. **A
twice-failed build gets resumed.** This line is the whole fix, and it is why
it comes first.

## 2. Ask the script

```
cd v2 && uv run python tools/loop/next_action.py
```

Add `--ladder <path>` if the founder gave one, and `--repo <path>` for a
repository that is not the current one.

**Never run it with `python -I`.** `CLAUDE.md`'s conventions say to use `-I`
for third-party or downloaded code; this is neither. `-I` strips the
script's own directory from `sys.path`, and the loop's modules are siblings
in that folder, so `import ladder` fails immediately.

## 3. Run the command, which does steps 2 to 5 for you

```
cd "$(git rev-parse --show-toplevel)"
python3 .claude/skills/chronos-tick/loop_cli.py claim --session-model <the model you are running as>
```

Pass the model **you** are running as. You are told it in your own context;
read it there and pass it. There is no reliable way for a command to read it
for itself: `ANTHROPIC_MODEL` is read at start-up and goes stale the moment
anyone switches with `/model`, and no documented variable carries the live
model into a shell. So this check is a guard rail that depends on you being
honest about your own model, and the structural half is elsewhere — every
agent file pins its own `model`, so dispatching `chronos-builder-opus` gets
Opus whatever this session is.

What it prints, and what each one means:

| It says | You do |
|---|---|
| `WAIT_FOUNDER`, `NONE`, `HALT` or `OPEN_GATE_MOVE` | Nothing. Show the reason and stop. These are the founder's to move. |
| `This build wants opus; you are on sonnet` | Stop. Tell the founder to switch with `/model`, and do not dispatch. No lock was taken and nothing was committed. |
| `claimed, nothing to do` | Stop. Another session holds the lock. Do not push anything. |
| opened a `chronos-halt` issue | Stop. The script itself failed; the issue carries the error text. Do not try to work around it. |
| `Lock taken. Now dispatch…` | Go to step 4. |

## 4. Dispatch — a tool call, not a shell command

The line it printed names an agent. Invoke it **through the Task/Agent
tool**, with `subagent_type` set to that name. Running `claude <agent-name>`
in a shell does not work and never has; a subagent is only reachable through
that tool.

```
Task(subagent_type: "<the agent it named>",
     prompt: "<the prompt it printed>")
```

Pass the prompt as printed. Do not add instructions of your own, do not tell
the agent what you think the answer is, and do not do the work yourself —
the whole point is that a fresh session with its own instructions does it.

## 5. Release the lock and report

```
python3 .claude/skills/chronos-tick/loop_cli.py finish --build <id>
```

It releases the lock and prints the status report. Show that to the founder
as your last word, and stop. One tick is one action.

## If anything is ambiguous

Stop and say so. Do not improvise, do not re-run the script hoping for a
different answer, and do not take an action the script did not name. A
stopped loop costs nothing; a loop that guessed costs weeks.
