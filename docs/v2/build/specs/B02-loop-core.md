```yaml
id: B02
title: The loop — ladder reader, next-action script, agents, commands
size: M
model: opus
who: founder          # run by hand: this build creates the loop
needs: [B01]
ticks: 3
touches:
  - v2/tools/loop/**
  - v2/tools/guards/**
  - v2/tests/tools/**
  - .claude/agents/**
  - .claude/skills/**
  - CLAUDE.md
  - docs/v2/build/templates/**
  - docs/v2/build/HANDBOOK.md
may_modify_tests: []
```

# B02 — The loop

## Why
This replaces the founder as the message bus. The important design choice: **an ordinary script decides what happens next, not an AI.** The AI sessions only do the work the script names. That makes "what is the loop doing?" a question with one checkable answer.

## Read first
- `BLUEPRINT.md` Part 2 (all), `LADDER.yaml`, `specs/README.md`.
- Claude Code docs, read fresh at build time (they change): subagents (`.claude/agents/*.md` frontmatter: `name`, `description`, `tools`, `disallowedTools`, `model`, `effort`, `maxTurns`), skills, scheduled tasks. Index: `https://code.claude.com/docs/llms.txt`. Verify each frontmatter key against the docs before using it.

## Deliver
1. `v2/tools/loop/ladder.py`: load and validate `LADDER.yaml` (unique ids; every `needs` exists and appears earlier; sizes, models and `who` from the allowed sets; `ticks` matches size; gates have no spec).
2. `v2/tools/loop/facts.py`: gather the repository facts and nothing else: which builds are merged (a status file with state `merged` on `v2-build`), which gate tags exist, which `claude/bNN-*` branches exist, each open build's status file, whether automatic tests are green on a branch head (`gh api`, REST only), whether `docs/v2/build/HALT` exists on `v2-build`.
3. `v2/tools/loop/next_action.py`: **a pure function** `decide(ladder, facts, now) -> Action` with no I/O, and a thin `main()` that prints the action as JSON. Actions: `START_BUILD`, `RESUME_BUILD`, `REVIEW`, `FIX`, `MERGE`, `RUN_GATE_AUDIT`, `WAIT_FOUNDER`, `HALT`, `NONE`; each carries the build id, model, branch and a one-line plain-language reason.
4. `v2/tools/loop/status_report.py`: the same facts as three plain sentences ("B07 is in review, round 1. Next after that: B08. Waiting on you: nothing.").
5. Status file schema (`docs/v2/build/status/<id>.json`): `build`, `state` (`building|needs_review|changes_requested|passed|merged|halted`), `round`, `ticks`, `claimed_by`, `claimed_at`, `head`, `halt_reason`, `halt_options`.
6. A CI check `v2/tools/guards/roles.py` (added to `run_all.py`): a commit whose message carries the trailer `Chronos-Role: reviewer` may touch only `docs/v2/build/reviews/`, `status/` and `LEDGER.md`; the reviewer agent's instructions require the trailer on every commit it makes.
7. Agent definitions: `.claude/agents/chronos-builder-opus.md`, `chronos-builder-sonnet.md` (same body, different `model`), `chronos-reviewer.md` (opus), `chronos-auditor.md` (opus). Bodies restate the role rules from `specs/README.md` and BLUEPRINT 2.2; they don't add rules.
8. Skills: `.claude/skills/tick/SKILL.md` (run `next_action.py`; check the session's model against the action's and stop with a plain message if they differ; dispatch to the named agent; never decide the action itself), `status`, `halt` (write the global HALT file), `resume`.
9. Templates in `docs/v2/build/templates/`: `report.md`, `review.md`, `gate-report.md` (sections per BLUEPRINT Part 6).
10. `CLAUDE.md`: a new short section "Build loop" pointing to the blueprint and stating three rules: never merge into `main`; never edit a spec whose build has started; the reviewer never edits code.

## Steps
1. Commit the decision table below as a parametrised test (red).
2. `ladder.py` + its validation tests.
3. `decide()` → green on the table.
4. `facts.py`, tested against throwaway git repositories; `gh` calls behind one small function that tests replace.
5. `status_report.py`, templates.
6. Agents, skills, `CLAUDE.md` section.
7. Dry run by hand in this session on a toy ladder in a temp repository: start → review → merge. Paste the three `next_action` outputs into the report.

## Known answers and checks
`decide()` on the real `LADDER.yaml`, with facts as stated. `now` is fixed; a claim is fresh for 3 hours.

| # | Facts | Expected |
|---|---|---|
| 1 | No gate tags | `WAIT_FOUNDER` G0 |
| 2 | G0 tagged; nothing merged | `WAIT_FOUNDER` B01 (who: founder) |
| 3 | B01–B03 merged; no G1 report | `RUN_GATE_AUDIT` G1 |
| 4 | …G1 report exists; no tag | `WAIT_FOUNDER` G1 |
| 5 | G1 tagged; nothing else | `START_BUILD` B04, model opus |
| 6 | B04 `building`, claimed 1 h ago | `NONE` |
| 7 | B04 `building`, claimed 4 h ago, ticks 1 | `RESUME_BUILD` B04 |
| 8 | B04 `building`, claimed 4 h ago, ticks 3 | `HALT` B04 (overrun) |
| 9 | B04 `needs_review` | `REVIEW` B04 |
| 10 | B04 `changes_requested`, round 1 | `FIX` B04 |
| 11 | B04 `changes_requested`, round 2 | `HALT` B04 (failed review twice) |
| 12 | B04 `passed`, tests green | `MERGE` B04 |
| 13 | B04 `passed`, tests pending | `NONE` |
| 14 | B04 `passed`, tests red | `HALT` B04 |
| 15 | B04 merged | `START_BUILD` B05 |
| 16 | B04 `halted`; B07 not started | `START_BUILD` B07 (a halted build blocks only what needs it) |
| 17 | B04 `halted`; B07, B10, B13 chains all blocked or done; nothing runnable | `WAIT_FOUNDER` B04 |
| 18 | Global `HALT` file present, B05 runnable | `NONE` |
| 19 | B04–B18 merged; no G2 report | `RUN_GATE_AUDIT` G2 |
| 20 | G2 tagged; B19 has `spec: card` | `HALT` B19 (spec not written) |
| 21 | G2 tagged; B19 spec written; B22 (founder) and B38 (loop) both runnable after B19 merges | `START_BUILD` B20 (file order), and B22 listed as waiting on the founder |
| 22 | A status file names a build not on the ladder | error exit, non-zero |
| 23 | B05 and B07 both `building` (two claims) | error exit: one build at a time |
| 24 | B12 runnable only when B09 **and** B11 merged; B09 merged, B11 not | B12 not chosen |
| 25 | B04's branch says `merged`, its pull request is still open, tests green (a session died mid-merge) | `MERGE` B04 |
| 26 | Same, tests red | `HALT` B04 |

Also:
- `ladder.py` rejects: a duplicate id; a `needs` that points later in the file; `size: L`; `model: fable`.
- **Blueprint and ladder agree:** the build and gate ids in `BLUEPRINT.md` Part 5 tables equal `LADDER.yaml`'s, in order.
- `decide()` imports nothing that does I/O (asserted by importing it with `subprocess` and `socket` patched to raise).

## Not in this build
Scheduling anything (B03) · any change to how GitHub branches are protected (B03).

## Halt if
- A frontmatter key the design relies on (`model`, `tools`) isn't supported as documented.
- A skill can't check the session's current model: then the model check moves into the agent dispatch, and that is a design change to flag.

## Doc rows to update
`HANDBOOK.md` §2–§4: replace "planned" wording with the real command names and outputs. `CODEBASE.md`: `.claude/`, `v2/tools/loop/`.
