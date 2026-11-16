# CHRONOS BUILD HANDBOOK — for the founder

**Status: DRAFT v0.3, 16 Nov 2026 (UTC), revised after two red-team passes.** Sections marked *(planned)* describe commands that exist only after builds B04 and B05; those builds replace the wording with what really happens on screen.

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
1. `main` moves only when you approve a gate, from your own GitHub account. Everything else happens on a working branch you can throw away.
2. The session that writes code never grades it, and the checks that judge a build are read from the approved copy, not from the build's own.
3. If the loop is unsure, it stops. A stopped loop costs nothing. A loop that guessed costs weeks.

**What you should not assume.** Between gates, the automatic checks catch mistakes and shortcuts; they would not stop an AI session that set out to deceive. Two red-team passes made that plain. What you are guaranteed is narrower and firmer: nothing reaches `main` without you, every phase is re-checked from clean at its gate, and the worst case is redoing part of one phase. If you want more than that, G1 offers two ways (BLUEPRINT 2.5, last paragraph).

---

## 1. Where to look

| You want to know | Look at |
|---|---|
| What is it doing right now? | Type `/status` in any Claude session *(planned, B04)*. Three plain sentences |
| What got built? | GitHub → Pull requests → Closed. Each has a report whose first paragraph is written for you |
| Is it waiting on me? | Your phone: one notification per gate or halt. Or `/status`. Or GitHub → Pull requests → "Review requested" |
| Is the plan slipping? | `docs/v2/build/LEDGER.md`: estimate vs actual for every build |
| What was decided, ever? | `docs/v2/CHRONOS_V2.md` §10. Nothing else is a decision |
| The plan itself | `docs/v2/build/BLUEPRINT.md` (diagrams first) |

The GitHub mobile app shows pull requests, reports and the diagrams. You never need a terminal to follow along.

---

## 2. Starting, stopping, taking over *(planned, B04–B05)*

**Stop the loop:** in the Claude app, open Scheduled tasks → "Chronos build loop" → switch it off. Or say to Claude: "pause the Chronos loop." Nothing is lost; the state lives in the repo.

**Start it:** switch it on, or say "resume the Chronos loop."

**Emergency stop for everything:** say "halt Chronos" to Claude, **or** do it yourself from the GitHub app on your phone: Issues → New issue → any title → add the label `chronos-halt`. While such an issue is open, every session, scheduled or manual, refuses to act. **Only you closing it releases it**: if any other account closes it, the loop treats it as still open. This works even if Claude is unavailable.

**Take over by hand** (when you have time and want it faster, or usage is short and you want to choose what gets done):
1. Open a Claude Code session on the repo (cloud, desktop app, or `claude` in the Mac terminal inside `~/chronos`).
2. Type `/tick`. It does the next thing, exactly as the loop would.
3. It will tell you first if you are on the wrong model ("this build wants Opus; you are on Sonnet") and stop until you switch. You don't have to remember which model.
4. Repeat `/tick` as often as you like. The loop and you can't collide: whoever acts first takes a lock on that build, and the other is told "claimed, nothing to do."

**While the loop doesn't exist yet (builds B01–B05),** you start each by hand: open a session and say "Do build B01 from docs/v2/build/specs. Follow specs/README.md, builder rules." For the review, open a **new** session (new chat, so it has no memory of the build) and say "Review build B01 per specs/README.md, reviewer rules." Then you merge the pull request yourself on GitHub. These five builds are the only ones where you are the wall.

---

## 3. When it halts

A halt is the system working. You get one notification with the reason and the options.

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
| G1 | That the loop works, that GitHub refused each of the eleven attacks B05 ran against it, and what a tick costs. Which Claude plan to stay on. Whether builds keep merging on their own between gates, or you want a reviewer with its own identity, or to merge each build yourself |
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
| Any build touching code or tests; every review; every gate audit | Opus |
| Docs-only and wiring builds | Sonnet (reviewed by Opus) |
| Planning, architecture, writing specs, red-teaming a plan | The strongest you have: Fable while your allowance lasts, else Opus |
| The loop | **Never Fable.** Never a local or third-party model |

### What the plans are
- Your plan is **Pro, $20**. Chat and Claude Code share one allowance, limited per five hours and per week [Certain].
- **Max is $100** and gives five times Pro on both limits; **Ultra is $200** [Likely — third-party summaries of Anthropic's help pages].
- **Fable on Pro is not in the allowance: it bills pay-as-you-go usage credits** [Certain]. A launch offer included it for a while; one write-up dates the end of that offer for Pro to 16 Nov 2026, 11:59 pm Pacific [Likely — single source]. After that, a long Fable session on Pro costs real money. On Max, Fable is inside the plan up to half of the weekly allowance [Certain — Anthropic help page, read 16 Nov].
- A scheduled cloud run uses the same allowance as you do. When the allowance is gone, runs are rejected until it resets, unless usage credits are on [Certain].

### Do this once, today
Claude → Settings → Usage: **set a monthly limit on usage credits** (suggest $0–20). Then nothing unattended can spend beyond it. If you use Fable for planning on Pro after the offer ends, this limit is your brake.

### Where more money helps (you said the $100 cap is soft)
The full table with the weak point of each is in BLUEPRINT 2.9. In order:

| # | Spend | Cost | Why |
|---|---|---|---|
| 1 | **Claude Max for the build months** | $100/month | About five times the allowance, and Fable for planning inside the plan. On Pro, one planning session plus one review emptied a five-hour window on 16 Nov. **My recommendation: switch when B01 starts** |
| 2 | **A few hours of an independent human reviewer** at G5 and before real money | a few hundred dollars, twice [Guessing] | Every checker in this system is an AI. Where the thresholds get set, one human who has seen none of it is a different kind of check |
| 3 | **A second reviewer from a different AI family**, acting through its own GitHub identity | $20/month from G1 (you confirm then) | Different blind spots, on every build; and it is the one thing that would make "a build can't approve itself" a wall. Kept only if G2 shows it caught something |
| 4 | **The server from G2, not after the spike** (proposal P-21, needs your yes) | $10–30/month [Guessing] | A few more weeks of headline history. A small gain; I'd take it only if the spike slips |
| 5 | **Storage** | $0 if your external SSD has 500 GB free; else $80–120 once [Guessing] | 256 GB won't hold the data comfortably |
| 6 | Rented compute for the phase-4 calibration run | tens of dollars, once [Guessing] | Hours instead of days |
| 7 | Paid history (futures quotes; a timestamped news archive) | unknown; priced when needed | Real spreads and an S-NEWS past sooner |

**Not worth money** [Likely]: hardware for local AI models · a new Mac · pay-per-use credits as the loop's main fuel · the top Claude plan before the middle one has been measured.

**The rule for stepping back down, written now:** B05 measures what a build tick and a review tick cost. At G1, if a week of the loop used less than a fifth of Max's weekly allowance, go back to Pro for the slow phases (the spike, collection) and return to Max for the heavy ones (phases 1 and 4). [The one-fifth threshold is my suggestion; change it at G1.]

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

### The side lane — the rule that makes B and C safe
Anything written by a tool other than the loop's own builder goes on a branch named `lane/<something>` and may only touch `scratch/` and `docs/drafts/`. The automatic guards refuse a `lane/` branch that touches anything else. Nothing from the lane becomes part of Chronos unless a proper build picks it up and it passes the same tests and the same Opus review as everything else.

---

## 8. Your list

**Before approving G0:**
1. Look at `BLUEPRINT.md` Part 1 (diagrams) and Part 5 (the ladder). Ask about anything that doesn't match your picture of Chronos.
2. Read `gates/G0-report.md` (one page) and skim `gates/G0-redteam.md`: what the red team found and what was done.
3. Approve G0 by merging the blueprint's pull request on GitHub.

**Before B01 starts:**
4. Set the usage-credit limit (§6).
5. Decide on Claude Max (§6, row 1).

**Before B05 (15 minutes, any time):**
6. Create a second, free GitHub account for the automation (for example `<yourname>-chronos-bot`) with its own email address. B05 walks you through adding it as a collaborator and connecting it. It is never the owner.

**When convenient:**
7. Download Kraken's BTC/USD 1-minute OHLCVT history to a folder on the Mac (B21 uses one file; B42 loads all of it).
8. Answer proposal P-21 (the server from G2) and the sibling-chain question in BLUEPRINT Part 8.
9. Check how much free space your external SSD has (§5).

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
