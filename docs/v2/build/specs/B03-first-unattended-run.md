```yaml
id: B03
title: First unattended run, schedule, notifications
size: S
model: opus
who: founder          # needs about 10 minutes of the founder at the start
needs: [B02]
ticks: 2
touches:
  - docs/v2/build/probe/**
  - docs/v2/build/HANDBOOK.md
  - v2/tests/tools/**
may_modify_tests: []
```

# B03 — First unattended run

## Why
Before the loop is trusted with real builds, it runs two fake ones: one that should pass and one built to fail. We watch it build, review, merge, halt and notify with nobody at the keyboard, and we measure what a tick costs. If the loop misbehaves here, it costs nothing.

## Read first
- `BLUEPRINT.md` 2.3–2.6; the B02 report.
- Claude Code docs, read fresh: cloud scheduled tasks (triggers, permissions, branches, usage and limits).

## Deliver
1. **GitHub settings** (founder clicks, or Claude through `gh api` with the founder watching): on `main` and `v2-build`, require a pull request and the `tests`, `guards` and `lint` checks; block force-pushes and deletion.
2. **One cloud scheduled task**, "Chronos build loop": this repository; model **Opus** (never Fable: on the Pro plan Fable bills usage credits); hourly, a few minutes past the hour; push notifications on; prompt = "Check out `v2-build`. Run the `tick` skill once. Stop." Created switched **off**.
3. **A usage-credit cap** set in Claude settings by the founder (handbook §7), so an unattended run can't spend money.
4. `docs/v2/build/probe/LADDER.probe.yaml` with two fake builds, and their specs:
   - **P01** (should pass): add `docs/v2/build/probe/hello.md` containing exactly one given sentence; known answer: the file's SHA-256.
   - **P02** (must halt): its spec demands a file whose SHA-256 equals a hash that no content the spec allows can produce.
5. The loop is pointed at the probe ladder, switched on, and left alone until both builds end. Then switched off and pointed back at the real ladder.
6. Measurements written to `LEDGER.md`: for each tick, start and end time, the action taken, and (read by the founder from Settings → Usage, before and after) the share of the five-hour allowance used.

## Steps
1. Settings, cap, task (founder present).
2. Probe ladder and specs. Switch on.
3. *(unattended)* The loop runs.
4. Collect: the pull requests, the review files, the halt file, the notification screenshots, `/status` output at three moments.
5. Manual take-over test: with the task on, run `/tick` by hand while a build is claimed; it must answer "claimed, nothing to do".
6. Clean up the probe; report; handbook.

## Known answers and checks
- P01 ends `merged` into `v2-build` with **no human action** between "switch on" and the merge. Its review file names the mutation the reviewer made and the check that caught it.
- P02 ends `halted` after exactly two review rounds, with a reason file, and **one** notification arrives on the founder's phone.
- With nothing runnable, the task switches itself off within one tick.
- No unattended session pushed to `main`, added the `founder-approved` label, or used a model other than Opus (read from the session records).
- The ledger has a measured cost per tick for: a build tick, a review tick, an idle tick.

## Not in this build
Any real build · a second-opinion reviewer (decided at G1).

## Halt if
- A scheduled session can't push branches, open pull requests or merge into `v2-build` with the permissions it gets.
- A tick with nothing to do uses more than a trivial share of the allowance: then the wake-up design changes (for example GitHub-event triggers instead of a clock), and that is the founder's call.
- The task can't switch itself off.

## Doc rows to update
`HANDBOOK.md` §3 (switching on and off, with the real screens), §7 (measured numbers replace estimates).
