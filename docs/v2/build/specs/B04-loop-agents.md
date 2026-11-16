```yaml
id: B04
title: The loop's hands — agent definitions, commands, templates
size: M
model: opus
who: founder          # changes CLAUDE.md and .claude/, which the founder owns
needs: [B03]
ticks: 3
touches:
  - .claude/agents/**
  - .claude/skills/**
  - CLAUDE.md
  - docs/v2/build/templates/**
  - docs/v2/build/HANDBOOK.md
  - v2/tests/tools/loop/test_agent_files.py
may_modify_tests: []
```

# B04 — The loop's hands

## Why
B03 decides what to do. This build defines who does it: a builder, a reviewer and an auditor, each a fresh session with its own instructions and its model fixed in its definition, plus the `/tick` command that asks B03's script for the action and hands it to the right one. Nothing here decides anything; if a rule appears here that isn't in `specs/README.md` or the blueprint, that is a defect.

## Read first
- `specs/README.md` (all), BLUEPRINT 2.2–2.8, the B03 report.
- Claude Code docs, read fresh at build time (they change): subagents (`.claude/agents/*.md` frontmatter: `name`, `description`, `tools`, `disallowedTools`, `model`, `effort`, `maxTurns`), skills, permission modes. Index: `https://code.claude.com/docs/llms.txt`. Verify each frontmatter key against the docs before using it.

## Deliver
1. `.claude/agents/chronos-builder-opus.md`, `chronos-builder-sonnet.md` (same body, different `model`), `chronos-reviewer.md` (opus; no file-editing tools beyond what writing the review and status files needs), `chronos-auditor.md` (opus). Each body: the role's rules from `specs/README.md`, the commit trailer it must use, and "read the spec from `v2-build`".
2. `.claude/skills/tick/SKILL.md`: run `v2/tools/loop/next_action.py`; if the action's model differs from the session's, print one plain sentence and stop; take the lock; dispatch to the named agent; release the lock; print `status_report`. It never chooses the action itself and never merges into `main`.
3. `.claude/skills/status`, `halt` (opens a `chronos-halt` issue), `resume` (closes it; switches the scheduled task on if it exists).
4. Templates in `docs/v2/build/templates/`: `report.md` (with the "For the gate" section), `review.md` (with "code commit reviewed"), `gate-report.md` (sections per BLUEPRINT Part 6).
5. `CLAUDE.md`: extend the "Build loop" section (added at G0) with the real command names (`/tick`, `/status`, `/halt`, `/resume`) and where the agents are defined. The three rules already in that section stay word for word.
6. `HANDBOOK.md` §1–§3: "planned" wording replaced with the real command names and outputs.
7. A test that parses every agent and skill file: required frontmatter present; each agent's `model` is `opus` or `sonnet` (never `fable`, never `inherit`); the builder bodies contain the builder trailer and not the reviewer's, and the reverse.

## Steps
1. The file test (red). 2. Agents. 3. Skills. 4. Templates. 5. `CLAUDE.md`, handbook. 6. By hand in this session, on a toy ladder in a temp repository: `/tick` three times (build, review, merge), outputs in the report.

## Known answers and checks
- The file test passes; changing one agent's model to `fable` makes it fail.
- `/tick` run on a model other than the action's prints the mismatch sentence and makes no commit.
- `/tick` with a fresh lock held by someone else prints "claimed, nothing to do" and makes no commit.
- The toy run produces: a builder commit with the builder trailer, a review file naming that commit, a reviewer commit setting `merged`, and B02's guards green on the toy pull request.
- `CLAUDE.md`'s "Build loop" section still contains its three original bullets unchanged (compared against the base branch), plus the command names.

## Not in this build
Scheduling, GitHub rulesets, the automation identity (B05).

## Halt if
- A frontmatter key the design relies on (`model`, `tools`) isn't supported as documented.
- A skill can't read the session's current model: then the model check moves into the agent dispatch, and that is a design change to flag.

## For the gate
`CODEBASE.md`: `.claude/`. Status board: loop built, not yet proven.
