# CHRONOS BUILD HANDBOOK — for the founder

**Status: v0.6, 20 Nov 2026 (UTC). The plan was approved at gate G0 on 16 Nov.** Section **1A** is what you do *now*, for builds 1–5. **The four commands in §2 exist as of build B04** and §1–§3 describe what really happens on screen rather than what was planned; the scheduled task that runs them without you is build B05, so until that lands you type them yourself.

You don't need to read code to run this. You need to know five things: where to look, how to start and stop the loop, what to do when it stops, how to approve a gate, and what to do when usage runs out.

Facts are tagged: [Certain] = verified · [Likely] · [Guessing]. Sources are at the end.

---

## 0. The one-page version

**What the loop does without you:** picks the next build from the ladder, writes it, has a separate session review it, runs the automatic tests, merges it into the working branch, and moves on. When it hits something that is yours to decide, it stops, tells you once, and waits. It never waits on a clock, and it never needs you at a fixed time.

**What only you do:**

| You | How often | How long |
|---|---|---|
| Be present for the **first five builds** (B01–B05), which build the loop and its walls | Once | Five to eight short sessions; B05 needs about 45 minutes of clicking in GitHub and Claude settings |
| Approve a **gate** (end of each phase) | 6 times to the end of the acceptance test | 2–15 minutes each, two clicks on GitHub |
| Approve a **rule change** (a corrected spec, a new library, the touchstones, a protected value) | Occasionally | One click after reading a short summary |
| Answer a **halt** (a fork, a protected value, a build that needs splitting) | Sometimes | Usually one sentence |
| The **engine spike** (your broker account, your Mac) | Once, about a week of calendar time | A few short sessions |
| Rent the **server**, hold the **API keys** | Once | 30 minutes |

**The three rules that keep you safe:**
1. Nothing reaches `main` without your approval, from your own GitHub account: code only at gates, documents when you approve them. Everything else happens on a working branch you can throw away.
2. The session that writes code never grades it.
3. If the loop is unsure, it stops. A stopped loop costs nothing. A loop that guessed costs weeks.

**What you should not assume.** Between gates, the automatic checks catch mistakes and shortcuts; they would not stop an AI session that set out to deceive. Three red-team passes made that plain. What you are guaranteed is narrower and firmer: nothing reaches `main` without you, every phase is re-checked from clean at its gate, and the worst case is redoing part of one phase. If you want more than that, G1 offers two ways (BLUEPRINT 2.5, last paragraph).

---

## 1A. Right now: running builds 1–5 by hand

"B01" means build 1. Each build is one Claude Code chat's worth of work, with its own instruction file in `docs/v2/build/specs/`. Build 1 is the code skeleton.

**Where to run it.** Two ways.
- **On Opus (your Pro allowance):** Claude Code on the web or in the phone app, on the `chronos` repo. Runs in the cloud: start one before work, close your laptop, check at lunch [Likely].
- **On DeepSeek (cheaper, proposal P-24; recommended to try on build 1):** Claude Code in the Mac's Terminal, pointed at DeepSeek. Doesn't touch your Claude allowance; costs cents to a few dollars per build [Guessing — build 1 measures it]. Setup below.

Reviews are always on Opus, in a new chat on the web or app.

**For each build (1, then 2, 3, 4, 5):**

1. **Start it.** New chat, Opus, paste:
   > Do build B01 from docs/v2/build/specs. Follow specs/README.md, builder rules.

   Then leave it. It saves (commits and pushes) after every step.
2. **If it gets cut off by the usage limit,** you don't have to do anything if the resume watcher is on (below). By hand, open a new chat and paste:
   > Resume build B01 from the last commit on branch claude/b01. Follow specs/README.md, builder rules.
3. **When it says it's finished,** open a **new** chat on Opus (never the chat that wrote the code) and paste:
   > Review build B01 per specs/README.md, reviewer rules. Don't merge; tell me the verdict in plain words.
4. **If the verdict is PASS:** on GitHub, open the pull request, read the first paragraph of the report, click **Merge**. For builds 1–5 you merge, not the reviewer: until build 5 nothing on GitHub stops a wrong merge, so you are the check.
5. **If the verdict is CHANGES:** new chat, paste:
   > Fix what the latest review of B01 found. Follow specs/README.md, builder rules.

   Then review again (step 3). Two failed reviews in a row means the instructions are wrong: tell Claude "show me both reviews in plain words".

Build 5 needs about 45 minutes of you clicking in GitHub and Claude settings; the build guides you.

**Building on DeepSeek, step by step (Mac):**
1. At platform.deepseek.com: sign up, add $10 of credit (prepaid, so it can't overspend), create an API key.
2. One-time Mac setup with Claude's help (§5): the `chronos` repo in `~/chronos`, `uv`, the GitHub command-line tool signed in.
3. In Terminal, **in a separate window you use only for this**, run (paste your key in place of `sk-…`):
   ```
   cd ~/chronos
   ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic ANTHROPIC_AUTH_TOKEN=sk-… ANTHROPIC_MODEL='deepseek-v4-pro[1m]' claude
   ```
   These are DeepSeek's documented settings [Certain — DeepSeek's Claude Code guide]. Putting them on the one command line means only that window uses DeepSeek; **never** put them in `~/.zshrc`, or every Claude Code session becomes DeepSeek.
4. Paste the same build prompt as above. When it's done, review on Opus in the cloud as usual.
5. Write down what it cost (DeepSeek's usage page) and how many review rounds it needed. That's the number that decides P-24.

**The resume watcher** (set up 17 Nov, **switched off**). A scheduled task, "Chronos resume watcher", that wakes every two hours in the cloud. If a build was cut off and nobody is working on it, it carries on from the last save. If a build is finished and has no review yet, it reviews it in a fresh session. It never merges builds 1–5, never touches `main`, and stops at once when there's nothing to do. **Switch it on when you start build 1** (Claude app → Scheduled tasks → Chronos resume watcher), and off when you're between builds: each wake-up uses a little of your allowance even when idle [Guessing on how much; build 5 measures it]. While your usage is used up, its wake-ups are refused; the first one after the reset picks the work up.

**Your time, efficiently:**
- Start a build first thing, or before bed. Check once. You don't need to watch.
- One build per chat. Long chats get slow and forget.
- Don't chat with Claude about other things on a day you want a build to finish: chats and builds share one allowance on Pro [Certain].
- When a build halts with a question, answer in one sentence in a new chat ("For B03: take option b"). That is the whole job.

---

## 1. Where to look

| You want to know | Look at |
|---|---|
| What is it doing right now? | Type `/chronos-status` in any Claude Code session. Three plain sentences |
| What got built? | GitHub → Pull requests → Closed. Each has a report whose first paragraph is written for you |
| Is it waiting on me? | Your phone: one notification per gate or halt. Or `/chronos-status`. Or GitHub → Pull requests → "Review requested" |
| Is the plan slipping? | `docs/v2/build/LEDGER.md`: estimate vs actual for every build |
| What was decided, ever? | `docs/v2/CHRONOS_V2.md` §10. Nothing else is a decision |
| The plan itself | `docs/v2/build/BLUEPRINT.md` (diagrams first) |

The GitHub mobile app shows pull requests, reports and the diagrams. You never need a terminal to follow along.

---

## 2. Starting, stopping, taking over

**The four commands.** They all start `chronos-`, so typing `/chronos-` in any Claude Code session shows you exactly these four and nothing else:

| Type this | And it |
|---|---|
| `/chronos-tick` | Does the next thing, once, then stops |
| `/chronos-status` | Tells you where things stand, in three sentences |
| `/chronos-halt` | Stops everything until you say otherwise |
| `/chronos-resume` | Turns the loop back on |

*Why the prefix:* `/status` and `/resume` are already Claude Code's own commands, and a command of ours cannot take a name one of its own already uses. That is also why `/status` still does what §7 says — shows you which model this session is on — and has nothing to do with Chronos.

> **Where this stands today (B05, 23 Nov 2026).** The scheduled task now
> exists — "Chronos build loop", hourly at :07, Opus, push notifications on —
> and it is **switched off on purpose. Do not switch it on yet.**
>
> A session running in Anthropic's cloud cannot take the lock: the GitHub
> routes it needs are blocked there, so every firing would stop with an error
> before doing anything, and with notifications on that is an hourly buzz on
> your phone. Worse, *releasing* a lock silently does nothing while reporting
> success, so a status report would tell you the sign came down when it is
> still hanging.
>
> Both live in `v2/tools/loop/lock.py` and both need a small build of their
> own. **Until that is done, run builds by hand from the Mac** (§1A), where
> every route works and the lock behaves. B05's report has the measurements.
>
> **But know what a Mac session is.** Claude Code on your Mac uses your Mac's
> own GitHub login, which is **you**: `vedantgautam1`, the owner, the admin and
> the only code owner. Every wall B05 built is a wall against the *automation*
> account and lets *you* through, so a Mac session gets through as well. It
> can approve a pull request as you, merge your own files on `v2-build`, and
> its approval plus the automation's push is everything `main` asks for. B05
> measured this; it is not a guess. So **a build run on the Mac is protected
> only by guard rails** (our own scripts and the session's instructions), not
> by GitHub. The G1 gate has to choose one of two things: log the Mac's Claude
> Code in as the automation account, or accept in writing that Mac-run builds
> are guard rails only.

**Stop the loop:** in the Claude app, open Scheduled tasks → "Chronos build loop" → switch it off. Or say to Claude: "pause the Chronos loop." Nothing is lost; the state lives in the repo.

*Also in your scheduled tasks, and not part of the loop:* "Chronos review watcher", created 17 Nov and currently off. It reviews finished builds every two hours and writes statuses directly, without taking a lock. If both it and the build loop were on, they would collide. Decide which one you want before switching anything on.

**Start it:** switch it on, or type `/chronos-resume`, which checks nothing is halted and then tells you which switch to flip. It cannot flip that switch for you, and it will say so rather than pretending.

**Emergency stop for everything:** type `/chronos-halt` (or say "halt Chronos" to Claude), **or** do it yourself from the GitHub app on your phone: Issues → New issue → any title → add the label `chronos-halt`. While such an issue is open, every session, scheduled or manual, refuses to act. **Only you closing it releases it**: if any other account closes it or removes the label, the loop treats it as still in force. This works even if Claude is unavailable.

*This was tested properly in B05, not just believed.* The automation tried all three ways out — closing the issue, stripping the label off it, and deleting the label from the repository altogether. GitHub permitted all three, and the loop still answered "an emergency stop is in force" every time. One thing to know for when you do want to lift it: because the loop reads each issue's **history** rather than its current labels, an issue that the automation closed is still a stop. You have to reopen it and close it yourself, or remove the label yourself. Your action is the one that counts, and it has to actually happen.

`/chronos-resume` will **not** lift a stop, and that is deliberate: an automation that can switch off its own emergency stop does not have one. It will tell you to close the issue yourself. If you ask it again, it will say the same thing.

**The last resort, which nothing can override:** switch the scheduled task off in the Claude app, or remove the automation's account from the repository (GitHub → Settings → Collaborators). The labelled issue is the convenient stop; these two are the certain ones.

**Take over by hand** (when you have time and want it faster, or usage is short and you want to choose what gets done):
1. Open a Claude Code session on the repo (cloud, desktop app, or `claude` in the Mac terminal inside `~/chronos`).
2. Type `/chronos-tick`. It does the next thing, exactly as the loop would, and then stops. One command, one action.
3. It will tell you first if you are on the wrong model — "This build wants opus; you are on sonnet. Nothing was claimed and nothing was committed." — and stop until you switch with `/model`. You don't have to remember which model.
4. Repeat `/chronos-tick` as often as you like. The loop and you can't collide: whoever acts first takes a lock on that build, and the other is told "claimed, nothing to do." **On the Mac. See the caveat below — this is not true in a cloud session today.**
5. When it finishes it prints the same three sentences as `/chronos-status`, so you can see what it did and what is next without typing anything else.

*One honest caveat on step 3:* the wrong-model warning works by the session comparing the model it is running as against the one the build asks for. There is no way for a command to look that up for itself, so this is a courtesy, not a lock. What actually pins the model is each agent's own definition in `.claude/agents/`: a build routed to the Opus builder runs on Opus whatever session dispatched it.

*A second caveat, on step 4, measured in B05 and true until `lock.py` is fixed:* **do your by-hand ticks on the Mac, not in a cloud session.** A cloud session cannot take the lock at all — `/chronos-tick` stops with an error before it dispatches anything. That failure is loud, which is the safe direction. The quiet one is the other way round: if a cloud session ever does hold a lock, releasing it does nothing while still printing "Lock released." So the rule for now is simply that the Mac is where ticks happen, and the collision protection in step 4 is real there and absent in the cloud. The price, from the box above: on the Mac, Claude acts as you, so GitHub's walls do not apply to that session.

**While the loop doesn't exist yet (builds 1–5),** see §1A.

---

## 3. When it halts

A halt is the system working. You get one notification with the reason and the options. At any point `/chronos-status` tells you what is halted and what is waiting on you, in three sentences; the reason and the options are written into the build's own status file, so nothing is lost if you come back days later.

| It says | It means | You do |
|---|---|---|
| "B20 is waiting for your review" | The build is finished and reviewed, but it creates or changes something that is yours (the touchstones, a protected value, a rule). GitHub won't merge it without you | Open the pull request, read the first paragraph of the report, approve if it says what you expect |
| "A spec correction is waiting for your review" | A build halted because its instructions were wrong; the fix to the instructions needs you | Read the two-line summary of what changed and why; approve, or ask |
| "B09 failed review twice" | The spec or the approach is wrong, not the typing | "Show me both reviews in plain words," then usually "correct the spec as you propose" |
| "B14 overran its budget" | My size estimate was wrong | "Split it as proposed." The ladder is renumbered and the ledger records it |
| "B07: two options that give different results" | A real fork | Read the two options and the recommendation; pick one. If you can't tell, say "explain the trade-off like I'm new" |
| "Checks are red on the working branch" | Something merged that shouldn't have | "Roll back to the last green commit and tell me what happened" |
| "v1 guard tripped" | Something tried to edit frozen v1 code | "Revert it." Always |
| "B23 has no spec" | A new phase is starting; its cards need turning into specs | Start the phase's spec-writing session (§4) |

**What you should never say** to make a halt go away: "just make it pass," "loosen the test," "skip the review," "use a different seed." Those are the four ways a system like this gets corrupted. If Claude ever proposes one, that is a bug in Claude: say no.

---

## 4. Gates

At the end of each phase the loop writes `docs/v2/build/gates/Gn-report.md` and stops.

**Read, in this order** (two minutes): the verdict line; "what the audit tried to break, and what broke"; "decisions waiting for you."

**Check three things yourself.** Every report ends with three checks you can do without reading code and without a terminal: "open this file on GitHub and confirm line 3 says 2026-04-01", or "open this pull request's checks page and confirm it shows 0.5630 and 0.0542". Do at least one. It takes a minute and it is the only check in the whole system that doesn't depend on an AI.

**Approve — two clicks, on two pull requests the loop opens for you:**
1. **"Gate Gn: write-up"** holds the report and the updates to the master document. This is the one to read. Approve and merge it.
2. **"Gate Gn: move main"** appears right after. Approve and merge it (choose "Create a merge commit" if GitHub asks).

Once B05 is done, telling Claude "approve G2" in a chat is not enough, on purpose: the approval must come from your own GitHub account. If something is pushed to a pull request after you approved it, GitHub discards your approval and asks again; that is deliberate, so read what changed. When the second pull request is merged, the loop carries on at its next wake-up.

**Don't approve if:** the sabotage section lists survivors that aren't explained; a number re-derived blind doesn't match; the report can't tell you plainly what was built.

**Opening a new phase.** Phases 2, 3 and 4 have cards, not full specs (see `BUILD_CARDS.md` for why). After the gate, start one planning session on the strongest model you have available and say: "Write the specs for phase N from BUILD_CARDS.md, using what the earlier phases found. Follow the format of specs B01–B22." Its specs arrive as a pull request for your review (specs are yours). Read its summary, approve, then let the loop run.

| Gate | What you are really approving |
|---|---|
| G0 | This plan |
| G1 | That the loop works, that GitHub refused each of the attacks B05 ran against it (for the reason named), and what a tick costs. Which Claude plan to stay on. Whether builds keep merging on their own between gates, or you want a reviewer with its own identity, or to merge each build yourself |
| G2 | The foundations (statistics, trial store, data, costs) are correct and match v1 |
| G3 | The engine choice |
| G4 | The server's monthly cost and that collection is running clean |
| G5 | The validation thresholds. After this, results can be believed |

---

## 5. Your Mac

**What it is:** MacBook Air 15-inch, M4, **16 GB memory, 256 GB storage** [Certain — founder, 16 Nov]. The folders `~/chronos` and `~/chronos-intake` exist [Certain — seen 16 Nov].

**What that means:**
- **Storage is the tight one.** Years of one-minute data, trade files and the engine spike's working files add up to tens of gigabytes [Guessing]. Keep market data on the external SSD the master doc says you have; if it has less than about 500 GB free, buy a 1 TB one before phase 2. It is also your backup.
- **16 GB memory is fine for building and testing**, and too small for the big calibration run in phase 4 to be quick. That run can be rented by the hour when the time comes (BLUEPRINT 2.9).
- **16 GB can't run an AI model good enough to write this code** (§7, option B, says what it can do).

**What the Mac is for:** the engine spike (IB Gateway must run where your broker login is), a local Postgres for running tests yourself, and later long backtests. **The loop itself runs in the cloud**, so the Mac can be shut [Certain].

**If you want things to run on the Mac while you're out:**
- Claude's own scheduled tasks on the Mac fire only while the Claude app is open and the Mac is awake; a closed lid still sleeps it; turn on Settings → This computer → System → **Keep computer awake** [Certain].
- An agent running unattended on your Mac can touch everything your user account can. The cloud sandbox can't [Likely]. So unattended work goes to the cloud unless it truly needs the Mac.

**One-time setup** *(do it with Claude in a session; each line is one request)*: confirm `~/chronos` is the repo and up to date · install `uv` · install Postgres (the Postgres app, or Homebrew) · install the GitHub command line tool and sign in · run the v2 tests once and see them pass.

---

## 6. Models and money

### Which model, when
You don't choose; the spec does (BLUEPRINT 2.8). For the record:

| Work | Model |
|---|---|
| Writing builds | DeepSeek V4 Pro by default if you accept P-24 (BLUEPRINT 2.8); Opus otherwise, and for any build that failed review twice |
| Every review; every gate audit | Opus |
| Planning, architecture, writing specs, red-teaming a plan | Opus on Pro (Fable is billed extra on Pro since the launch offer ended, [Likely]); Fable if you're on Max |
| The loop | **Never Fable on Pro** (billed extra). Cheap models only with a prepaid, capped balance |

### What the plans are
- Your plan is **Pro, $20**. Chat and Claude Code share one allowance, limited per five hours and per week [Certain].
- **Max is $100** and gives five times Pro on both limits; **Ultra is $200** [Likely — third-party summaries of Anthropic's help pages].
- **Fable on Pro is not in the allowance: it bills pay-as-you-go usage credits** [Certain]. A launch offer included it for a while; one write-up dates the end of that offer for Pro to 16 Nov 2026, 11:59 pm Pacific [Likely — single source]. After that, a long Fable session on Pro costs real money. On Max, Fable is inside the plan up to half of the weekly allowance [Certain — Anthropic help page, read 16 Nov].
- A scheduled cloud run uses the same allowance as you do. When the allowance is gone, runs are rejected until it resets, unless usage credits are on [Certain].

### Do this once, today — **done, 23 Nov 2026**
Claude → Settings → Usage: **set a monthly limit on usage credits** (suggest $0–20). Then nothing unattended can spend beyond it. If you use Fable for planning on Pro after the offer ends, this limit is your brake.

Set on 23 Nov: **a $20 monthly cap on usage credits.** That is the ceiling on what anything unattended can cost you in real money, separate from the Pro allowance, which is time-based and resets on its own. If a scheduled run ever misbehaves, this is the number that bounds the damage.

### What a tick costs — **not measured, and the reason matters**
B05 was meant to produce this: a measured cost for a build tick, a review tick and an idle tick, read from Settings → Usage before and after the three probe builds.

**There is no figure, because the probes never ran.** A cloud scheduled session cannot take the lock, so B97, B98 and B99 could not be attempted at all. This is not a number that was skipped or estimated — the thing it would have measured did not happen.

Nothing downstream should quote a per-tick cost until it is measured for real. In particular, §6's rule for revisiting Max — *"B05 measures what a build and a review cost. The G1 report states how many builds a week that allows on Pro"* — has no input yet. It moves to whichever build first runs the loop unattended.

### Where more money helps (you said the $100 cap is soft)
The full table with the weak point of each is in BLUEPRINT 2.9. In order:

| # | Spend | Cost | Why |
|---|---|---|---|
| 1 | **Claude Max for the build months** | $100/month | About five times the allowance, and Fable for planning inside the plan. On Pro, one planning session plus one review emptied a five-hour window on 16 Nov. **You said on 16 Nov: not now, maybe in a couple of months.** The plan runs on Pro, slower; G1 brings this back with a measured cost per build |
| 2 | **A few hours of an independent human reviewer** at G5 and before real money | a few hundred dollars, twice [Guessing] | Every checker in this system is an AI. Where the thresholds get set, one human who has seen none of it is a different kind of check |
| 3 | **A second reviewer from a different AI family**, acting through its own GitHub identity | $20/month from G1 (you confirm then) | Different blind spots, on every build; and it is the one thing that would make "a build can't approve itself" a wall. Kept only if G2 shows it caught something |
| 4 | **The server from G2, not after the spike** (proposal P-21, needs your yes) | $10–30/month [Guessing] | A few more weeks of headline history. A small gain; I'd take it only if the spike slips |
| 5 | **Storage** | $0 if your external SSD has 500 GB free; else $80–120 once [Guessing] | 256 GB won't hold the data comfortably |
| 6 | Rented compute for the phase-4 calibration run | tens of dollars, once [Guessing] | Hours instead of days |
| 7 | Paid history (futures quotes; a timestamped news archive) | unknown; priced when needed | Real spreads and an S-NEWS past sooner |

**Not worth money** [Likely]: hardware for local AI models · a new Mac · pay-per-use credits as the loop's main fuel · the top Claude plan before the middle one has been measured.

**While you are on Pro:** build and review on Opus (Fable costs extra on Pro once the launch offer ends [Likely]); remember the allowance is shared with your ordinary chats; and expect sessions to be cut off by the limit now and then. That is harmless: every build saves its work step by step and the next session picks up where it stopped. **The rule for revisiting, written now:** a build and a review get measured for what they cost, and the G1 report states how many builds a week that allows on Pro and how long 54 builds would take. That number decides whether Max is worth it, not a feeling. **B05 was to have taken that measurement and did not** — its probes never ran, for the lock reason above — so the measurement moves to whichever build first runs the loop unattended. The rule stands; its input is still missing.

---

## 7. When Claude usage runs out

First: **nothing breaks.** Builds commit after every step; the loop simply resumes at the next reset. The cheapest answer is often to wait.

If you want to keep working anyway, these are the options, best first.

### Option A — a second AI with its own allowance (ChatGPT Plus → Codex), $20
You don't have this subscription today. ChatGPT Plus includes OpenAI's coding agent, with its own five-hour and weekly limits, separate from Claude's [Likely]. It can also review every GitHub pull request automatically [Likely]. This is the strongest fallback, because it is a frontier-class model, not a small one.
**Allowed for:** second-opinion reviews; anything in the side lane below. **Not for:** writing builds marked Opus.

### Option B — a small model running on your Mac, $0
Yes, this works, and here is exactly how. But know what you're getting.

**What a USB drive does and doesn't do.** A model is a large file (4–10 GB for the ones that fit you). A USB drive or external SSD can *hold* that file, which is useful if your internal storage is 256 GB. It can't *run* it: the model runs in the Mac's memory and on its chip. So the limit is memory, not the USB. On a 16 GB Mac a model gets roughly 10–11 GB at most; real agent-style coding at that size is slow and unreliable, and a fanless Air slows a further 15–20% after about ten minutes of sustained work [Likely — hands-on write-ups]. Use an external **SSD**, not a thumb drive: loading a 5 GB file from a slow stick takes minutes.

**What it is good for** (work that needs patience, not brains): explaining a file or a report to you in plain words · summarising a long log · drafting documentation text · small throwaway scripts (rename files, check a CSV) · practice questions about the code base.
**What it is not for:** anything under `v2/src/` or `v2/tests/`, any review, any statistics, any number that feeds a decision.

**Setup, once (ask Claude to walk you through it; about 20 minutes):**
1. Install **Ollama** (a free app that runs models locally).
2. If storage is tight: point it at your external SSD by setting `OLLAMA_MODELS` to a folder on that drive [Likely].
3. Download one small coding model. Start with something around 4–5 GB; guides for 16 GB Macs currently suggest models of that size, and a 9 GB one leaves the rest of the Mac starved [Likely — third-party guides, they disagree on the best pick and it changes monthly]. Ask Claude to look up the current best fit when you do this.
4. Run Claude Code against it. Recent Ollama versions speak the same protocol Claude Code uses, and have a launcher that sets everything up for one session [Likely]: `ollama launch claude`. The manual form is: `ANTHROPIC_BASE_URL=http://localhost:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model <the model>`.

**Two traps that would hurt you:**
- **Never put those settings in your shell profile** (`~/.zshrc`) or in Claude's settings file. If you do, *every* Claude Code session, including real builds, silently runs on the small model. Use them only on the one command line, in a separate terminal window. If a session ever seems oddly weak, type `/status` and check the model.
- **Never set `ANTHROPIC_API_KEY` in your profile either.** With it set, Claude Code bills that key instead of using your subscription [Certain].

**A ten-minute test before you rely on it:** give it one fixed chore ("summarise docs/v2/build/LEDGER.md in five bullets") and time it. If it takes more than a couple of minutes or gets facts wrong, this lane isn't worth your time on this Mac, and that is a fine conclusion.

### Option C — a hosted open-weight model, pay per use
The strongest open models are far too large for any laptop [Likely], but companies host them and charge per use, often cheaply. Claude Code can be pointed at such a service the same way as at Ollama. It costs money per use and it sends your prompts to another company. Not recommended in month one: Option A is stronger for a flat price, and Option B is free.

### Option D — cheap hosted models (DeepSeek, Qwen) running chores on their own (proposal P-23, not built)
DeepSeek and Alibaba's Qwen both offer endpoints that Claude Code can talk to directly, by changing its address and key [Certain — DeepSeek's and Alibaba Cloud's own docs]. They cost cents to low dollars per million words processed, against tens of dollars for Opus [Likely — published prices vary by source and change often]. So they can run around the clock for very little. The question is what they should do.

**They may write code** (your instruction of 17 Nov; see P-24 and "Building on DeepSeek" in §1A). **They never decide whether a build passes** or anything that trades money: hard rule 1 applies to every AI, Claude included.

**What they could do well, cheaply:**
- **A second-opinion review on every build's pull request**, posted as a comment, never an approval. This is proposal P-20's "reviewer from another AI family" at pennies instead of a $20 ChatGPT subscription.
- Summaries of build reports and logs for you, in plain words.
- Drafts of documentation, into `docs/drafts/` only.
- Checks on data files you download (row counts, gaps, odd values), with the result as a note.

**How it would run (the design; a build would make it real):**
1. **A chore list**, `docs/v2/build/CHORES.yaml`. Opus sessions (builders, reviewers, planning chats) add chores as they notice them, each marked `tier: cheap` or `tier: opus`. Only chore types on a fixed allowed list can be `cheap`. That is the "Claude decides who gets which chore" part: Claude labels the work, and a plain script enforces the list, so a mislabelled chore still can't reach code.
2. **A GitHub Actions job** (free on a public repository [Likely]) wakes every hour, takes the oldest open cheap chore, runs Claude Code pointed at DeepSeek or Qwen, and pushes the result to a `lane/` branch. The guards already refuse a `lane/` branch that touches anything outside `scratch/` and `docs/drafts/`.
3. **Money:** a prepaid balance at the provider (for example $10), so it can't overspend; the key is stored as a GitHub secret.

**Weakest parts, honestly:**
- Chores alone don't speed up the build; the big saving is the cheap builder (P-24).
- **API keys and account details must never be in a prompt** (privacy of the code itself isn't a concern, your call of 17 Nov).
- It is one more moving part to maintain.

**Recommendation:** start with the cheap builder on build 1 (§1A), by hand. The automatic chore list and the GitHub Actions job are one small build after G1.

### The side lane — the rule that makes B, C and D safe
Anything written by a tool other than the loop's own builder goes on a branch named `lane/<something>` and may only touch `scratch/` and `docs/drafts/`. The automatic guards refuse a `lane/` branch that touches anything else. Nothing from the lane becomes part of Chronos unless a proper build picks it up and it passes the same tests and the same Opus review as everything else.

---

## 8. Your list

**Done:** gate G0 approved (16 Nov).

**Now:**
1. Set the usage-credit limit (§6), so nothing unattended can spend money.
2. Start build 1 (§1A) and switch the resume watcher on.

**Before build 5 (15 minutes, any time):**
3. Create a second, free GitHub account for the automation (for example `<yourname>-chronos-bot`) with its own email address. Build 5 walks you through adding it as a collaborator and connecting it. It is never the owner.

**When convenient:**
4. Read pull request #16 (instructions for builds 43–50) and the choices listed in proposal P-22. Not urgent: they matter before build 43.
5. Download Kraken's BTC/USD 1-minute OHLCVT history to a folder on the Mac (build 21 uses one file; build 42 loads all of it).
6. Answer proposal P-21 (the server from G2) and the sibling-chain question (O-14).
7. Check how much free space your external SSD has (§5).

---

## 9. Glossary

**Build** one session-sized piece of work, one pull request · **Tick** one wake-up of the loop · **Gate** a checkpoint that waits for you · **Halt** the loop stopping itself · **Spec** the written instructions and pass/fail checks for one build · **Known answer** a result we know is right before the code exists, used as a test · **Pull request** a proposed change, with its tests and review attached · **Working branch (`v2-build`)** where builds land · **`main`** the approved line; moves only at gates · **Sabotage run** deliberately breaking the code to prove the tests notice · **Blind re-derivation** a separate session recomputing a result from the spec without seeing the original · **Protected value** a validation threshold, risk limit, seal date or go-live decision; always yours · **Wall** a protection enforced by GitHub or the database whatever an agent intends, and that has been attacked and held · **Tripwire** an automatic check that catches mistakes and shortcuts but that a session set on cheating could get around · **Guard rail** a protection that depends on a session following its instructions · **Code owner** the account GitHub requires a review from before certain files can change (you) · **Lock** a marker a session takes before acting on a build, so two sessions can't work on the same thing · **Seal** the date (1 Apr 2026) after which research can't read price data · **Footprint** the record of what data a result actually read.

---

## Sources

- Claude Code docs: [cloud scheduled tasks](https://code.claude.com/docs/en/web-scheduled-tasks), [desktop scheduled tasks](https://code.claude.com/docs/en/desktop-scheduled-tasks) (read 16 Nov 2026)
- Anthropic support: [Claude Code with Pro, Max or Ultra](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan), [Fable models on your plan](https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan)
- Plan prices and the Fable 5.2 offer dates (third-party): [danilchenko.dev](https://www.danilchenko.dev/posts/claude-code-max-vs-pro/), [wmedia.es](https://wmedia.es/en/tips/claude-code-fable-5-2-usage-credits-pro)
- Codex with ChatGPT Plus (third-party): [developersdigest.tech](https://www.developersdigest.tech/blog/codex-usage-limits-pricing-2026)
- Local models on a 16 GB Mac (third-party): [towardsai](https://pub.towardsai.net/is-a-16gb-mac-mini-enough-for-local-llms-m6-2026-efd2a80ca3d1), [bestllmfor.com](https://bestllmfor.com/guides/best-llm-macbook-air-m4/)
- Claude Code with Ollama (third-party): [morphllm.com](https://www.morphllm.com/ollama-claude-code), [kdnuggets.com](https://kdnuggets.com/pairing-claude-code-with-local-models)
- Open-weight model sizes (third-party): [opulon.org](https://opulon.org/blog/best-ai-for-coding/)
