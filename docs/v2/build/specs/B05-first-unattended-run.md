```yaml
id: B05
title: The automation's own identity, GitHub rules, first unattended run
size: S
model: opus
who: founder          # needs about 30 minutes of the founder at the start
needs: [B04]
ticks: 2
touches:
  - docs/v2/build/probe/**
  - docs/v2/build/HANDBOOK.md
may_modify_tests: []
```

# B05 — Identity, GitHub rules, first unattended run

## Why
Two things happen before the loop is trusted with a real build.

**First, the automation gets its own GitHub identity.** Today every Claude session acts on GitHub as the founder, so GitHub can't tell "the founder approved this" from "the agent clicked approve". With a separate account for the automation that has ordinary write access and nothing more, GitHub's own rules become real walls: only the founder can move `main`, and only the founder can change the files that define the rules. This costs nothing but the founder's clicks.

**Second, the loop runs fake builds** with nobody at the keyboard: one that should pass, one prepared with a defect the reviewer must catch, one prepared at the point where the loop must halt. We also measure what a tick costs. If the loop misbehaves here, it costs nothing.

## Read first
- BLUEPRINT 2.3–2.6; `gates/G0-redteam.md` findings 1, 12, 13, 18; the B03 and B04 reports.
- Read fresh: Claude Code docs on cloud scheduled tasks and on GitHub authentication for cloud sessions; GitHub docs on rulesets and CODEOWNERS for public repositories on a free account.

## Deliver
1. **Identity** (founder, guided step by step):
   - a second GitHub account for the automation, added to the repository with the **Write** role (not Admin);
   - Claude's GitHub connection switched to that account, so cloud sessions push, open pull requests and merge as the automation;
   - the founder's own account stays the owner and the only code owner.
2. **Rulesets** (founder clicks, Claude reads each setting back afterwards through the API to confirm it):
   - `main`: pull request required; **one approval required**; the checks `tests`, `lint`, `v1-oracle`, `guards` required; merge method **merge commit only** (a squash here would make `main` and `v2-build` drift apart) [Likely — rulesets can restrict merge methods; confirm on the settings page]; no force-push, no deletion; no bypass for anyone.
   - `v2-build`: pull request required; **zero approvals, but review from code owners required**, so a pull request touching a founder-owned path needs the founder and any other merges on green checks; the same required checks; merge method squash; no force-push, no deletion.
3. **One cloud scheduled task**, "Chronos build loop": this repository; model **Opus** (never Fable); hourly, a few minutes past the hour; push notifications on; prompt = "Check out `v2-build`. Run the `tick` skill once. Stop." Created switched **off**.
4. **The founder's usage-credit limit** set in Claude settings (handbook §6).
5. `docs/v2/build/probe/`: a probe ladder with three fake builds and their specs.
   - **P01** (should pass, fully unattended): add `docs/v2/build/probe/hello.md` containing exactly one given sentence; known answer: the file's SHA-256.
   - **P02** (the reviewer must catch it): a branch prepared by hand in state `needs_review`. Its tests pass, but one asserts `>=` where its spec says `==`, and its report doesn't mention it.
   - **P03** (the loop must halt): a branch prepared by hand in state `changes_requested`, round 2.
6. Measurements in `LEDGER.md`: per tick, start and end time and the action; and, read by the founder from Settings → Usage before and after, the share of the five-hour allowance used.

## Steps
1. Identity, rulesets, credit limit, scheduled task (founder present). Read every setting back.
2. **Wall tests, by hand, as the automation:** try to merge a pull request into `main`; try to approve one; try to merge a `v2-build` pull request that edits `validation.yaml`. All three must be refused by GitHub. Record the refusals.
3. Probe ladder, specs and the two prepared branches. Switch the task on.
4. *(unattended)* The loop runs.
5. Collect: the pull requests, review files, the halt, the notification, `/status` at three moments, the session records.
6. Manual take-over test: with the task on, run `/tick` by hand while a build is locked; it must answer "claimed, nothing to do".
7. Clean up the probe; report; handbook.

## Known answers and checks
- **Walls:** the three attempts in step 2 are refused by GitHub itself (the error text is in the report), not by a guard script.
- **P01** ends `merged` into `v2-build` with no human action after "switch on". Its review file names the code commit reviewed, the thing the reviewer broke, and the test that caught it.
- **P02**'s first review is `CHANGES` and names the weakened assertion (file and line).
- **P03** ends `halted` on the first tick that sees it, and **one** notification reaches the founder's phone.
- With nothing runnable, the task switches itself off within one tick.
- From the session records: no unattended session used a model other than Opus; none attempted to push to `main`.
- The ledger has a measured cost for a build tick, a review tick and an idle tick.

## Not in this build
Any real build · a reviewer from another AI family (decided at G1).

## Halt if
- **Claude's cloud sessions can't act as a separate GitHub account.** Then the walls above aren't available this way. The options to put to the founder: (a) the founder merges every build himself (a real wall, less automation); (b) a reviewer and merger that runs inside GitHub's own automation with its own identity; (c) proceed with guard rails only, in writing, until one of those exists.
- A ruleset with zero approvals plus code-owner review isn't available on this account type.
- A scheduled session can't push branches, open pull requests or merge into `v2-build` as the automation.
- A tick with nothing to do uses more than a trivial share of the allowance: then the wake-up design changes (GitHub-event triggers instead of a clock), and that is the founder's call.

## For the gate
`HANDBOOK.md` §2 with the real screens, §6 with measured numbers. Status board: loop proven or not. The G1 report states plainly which protections are now walls and which are still guard rails.
