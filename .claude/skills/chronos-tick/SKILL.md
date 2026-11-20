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
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/v2" && uv run python tools/loop/next_action.py \
  --ladder "$ROOT/docs/v2/build/LADDER.yaml" --repo "$ROOT"
```

**Both paths have to be absolute, and leaving either out is worse than it
looks.** `next_action.py` resolves `--ladder` and `--repo` against the
working directory, and this has to run from `v2/`, where `uv` lives:

- no `--ladder`: the relative default finds no ladder, the script exits 1,
  and step 3 opens a `chronos-halt` issue that only the founder can close.
  Loud, and it stops the loop dead.
- no `--repo`: the default `.` is `v2/`, and `facts.gather` reads the status
  files with `git ls-tree`, whose pathspec is relative to the working
  directory inside the repository. From `v2/` it matches nothing, so
  **every** build reads as having no status file and the script answers
  confidently from an empty world — measured: `WAIT_FOUNDER G0` where the
  truth is `WAIT_FOUNDER B04`. Silent, and worse.

Put the founder's own path after `--ladder` if he gave one, and his
repository after `--repo` if it is not this one.

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
