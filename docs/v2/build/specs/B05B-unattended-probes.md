```yaml
id: B05B
title: "The first unattended runs: B05's probes and the measured cost of a tick"
size: M
model: opus
who: founder          # about 20 minutes of the founder at the start and 15 near the end
needs: [B05A]
ticks: 3
touches:
  - docs/v2/build/probe/**
  - docs/v2/build/HANDBOOK.md
may_modify_tests: []
adds_dependencies: []
```

# B05B — the first unattended runs

## Why

B05 built the automation's identity and GitHub's walls and proved them by attack. It could not do the last third of its spec: **the loop has never run by itself**, and nobody knows what a tick costs. A cloud session could not take the lock (`reports/B05.md` deviation 1). The founder accepted that on 23 Nov and split the lock fix into its own build. B05A fixes the lock. This build runs what B05 could not, **exactly as B05's spec writes it**, so the G1 gate has the evidence its title asks for: "the loop is proven".

The measured cost matters as much as the probes. Whether the founder's Pro plan can carry the 50-odd builds ahead, or whether Max is needed, has had no input since B05 (HANDBOOK §6, "What a tick costs — not measured").

**Built under the founder's 27 Nov choices** (G1 writes them into the master doc §10): builder and reviewer stay on **one** GitHub account for now (B05 "Halt if" option (c)), so B97's review is a separate *session*, not a separate identity. That is the guard rail BLUEPRINT 2.5 describes, and this build's report says so rather than calling it a wall.

## Read first

- `specs/B05-first-unattended-run.md` on `v2-build`: **Deliver 5, Deliver 6, steps 3–7, and every known answer about B97, B98, B99, the task, the session records, the costs and the cleanup.** Those are this build's Deliver items and known answers, word for word, except where this spec changes them below.
- `reports/B05.md` (what was done and what was left), `reviews/B05-r2.md` findings 3 and 5, HANDBOOK §1–§3 and §6.
- `reports/B05A.md`: how the lock now works, and that a released lock leaves a marker branch behind.

## Deliver

1. **B05's Deliver 6 and its measurements, unchanged:** the `spec/probes` pull request (founder-approved) adding B97, B98 and B99 and `probe/LADDER.probe.yaml`. B97 runs to `merged` with the task on and no human action. B98, then B99, run one after the other. Then the manual take-over test, and the `spec/probes-cleanup` pull request (founder-approved) removing what B05's spec lists.
2. **B05's Deliver 5, finished.** The founder, at the start, with Claude guiding:
   - Deletes the **"Chronos review watcher"** scheduled task. It writes statuses without taking a lock, and its prompt checks the current `chronos-halt` label, which the automation can defeat (`reports/B05.md`, open question 3).
   - Removes **every connector** from "Chronos build loop" (Gmail and Google Drive among them; it needs none). Leaves its approval setting so its runs go ahead unattended, and says in the report what that setting is.
   - Points the task's prompt at the probe ladder for the probes, and back afterwards, as B05 Deliver 6 says.
   - Revokes the automation's **classic personal access token** used for B05's Mac run, if it still exists, and says so in the report.
3. **The cost of a tick, measured.** For every tick in the probes: start and end time (UTC) and the action. The founder reads the five-hour allowance from Settings → Usage before and after (a) B97's build ticks, (b) its review tick, (c) one idle tick. From those, this build's report states **how many build-plus-review cycles one five-hour window allows on Pro**, as a range, with the arithmetic shown. HANDBOOK §6's "What a tick costs" section gets the measured numbers.

## Steps

B05's steps 3–7, in that order, with step 2 above first (founder present, about 20 minutes). Steps 4 (B97, unattended) and 5 (B98, B99 and the take-over test, founder back for about 15 minutes) are B05's.

## Known answers and checks

**B05's, all of them**, with "B05" read as "B05B" where it names the open build:

- **B97** ends `merged` into `v2-build` with no human action after "switch on". Its review file names the code commit reviewed, the thing the reviewer broke, and how it was caught. The commits of its build and of its review carry **different session links**.
- **B98**'s review is `CHANGES` and names the one-word difference and the SHA mismatch.
- **B99** ends `halted` on the first tick that sees it, and **one** notification reaches the founder's phone.
- With nothing runnable on the probe ladder, the task switches itself off within one tick.
- From the session records: no unattended session used a model other than Opus; none attempted to push to `main`.
- The report has a measured cost for a build tick, a review tick and an idle tick.
- After cleanup, `next_action` on the real ladder says "waiting on you: B05B", and none of the files the cleanup lists remains on `v2-build`.
- Manual take-over: while B97's or B98's lock is held, `/chronos-tick` by hand answers "claimed, nothing to do".

**And, new here:**

- **Every lock the probes took was released.** After the probes, every `lock/b97`, `lock/b98`, `lock/b99` branch's tip is a release marker, or the branch was never created. Read with `git ls-remote` and the tip messages, and paste them into the report.
- **The "review watcher" task no longer exists** and **"Chronos build loop" has no connectors**, both read back through the scheduling tools and pasted.

## Not in this build

- A reviewer with its own identity (founder, 27 Nov: not now; revisit when a second subscription is affordable).
- Logging the Mac's Claude Code in as the automation: the founder does it when he next runs a Mac session; HANDBOOK §2 says how. Not needed here, because this build runs in the cloud.
- Pruning old `lock/*` and attack branches (the founder, from the Mac, whenever he likes).
- Any real build. B06 starts after G1.

## Halt if

B05's "Halt if" list applies as written. Especially: **a tick with nothing to do uses more than a trivial share of the allowance** (then the wake-up design changes, the founder's call), and **a scheduled session can't push branches, open pull requests or merge into `v2-build` as the automation**. And additionally:

- Any lock is left held after its tick finished (the B05A fix is not doing its job on the shipped path).
- B97 needs a human action to reach `merged`.

## For the gate

The G1 report carries: the probes' outcome; the measured tick costs and the "cycles per five-hour window" range, which decide **Pro or Max**; that builder–reviewer separation is still a guard rail by the founder's choice; and the re-sized ladder from B01–B05B's actuals.
