# CHRONOS BUILD HANDBOOK — for the founder

**Status: DRAFT v0.1, 16 Nov 2026 (UTC).** Sections marked *(planned)* describe commands that exist only after builds B02 and B03; those builds replace the wording with what really happens on screen.

You don't need to read code to run this. You need to know five things: where to look, how to start and stop the loop, what to do when it stops, how to approve a gate, and what to do when usage runs out.

Facts are tagged: [Certain] = verified · [Likely] · [Guessing]. Sources are at the end.

---

## 0. The one-page version

**What the loop does without you:** picks the next build from the ladder, writes it, has a separate session review it, runs the automatic tests, merges it into the working branch, and moves on. When it hits something that is yours to decide, it stops, tells you once, and waits. It never waits on a clock, and it never needs you at a fixed time.

**What only you do:**

| You | How often | How long |
|---|---|---|
| Approve a **gate** (end of each phase) | 6 times to the end of the acceptance test | 2–15 minutes each |
| Answer a **halt** (a fork, a protected value, a build that needs splitting) | Sometimes | Usually one sentence |
| The **engine spike** (your broker account, your Mac) | Once, about a week of calendar time | A few short sessions |
| Rent the **server**, hold the **API keys** | Once | 30 minutes |

**The three rules that keep you safe:**
1. `main` moves only when you approve a gate. Everything else happens on a working branch you can throw away.
2. The session that writes code never grades it.
3. If the loop is unsure, it stops. A stopped loop costs nothing. A loop that guessed costs weeks.

---

## 1. Where to look

| You want to know | Look at |
|---|---|
| What is it doing right now? | Type `/status` in any Claude session *(planned, B02)*. Three plain sentences |
| What got built? | GitHub → Pull requests → Closed. Each has a report whose first paragraph is written for you |
| Is it waiting on me? | Your phone: one notification per gate or halt. Or `/status` |
| Is the plan slipping? | `docs/v2/build/LEDGER.md`: estimate vs actual for every build |
| What was decided, ever? | `docs/v2/CHRONOS_V2.md` §10. Nothing else is a decision |
| The plan itself | `docs/v2/build/BLUEPRINT.md` (diagrams first) |

The GitHub mobile app shows pull requests, reports and the diagrams. You never need a terminal to follow along.

---

## 2. Starting, stopping, taking over *(planned, B02–B03)*

**Stop the loop:** in the Claude app, open Scheduled tasks → "Chronos build loop" → switch it off. Or say to Claude: "pause the Chronos loop." Nothing is lost; the state lives in the repo.

**Start it:** switch it on, or say "resume the Chronos loop."

**Emergency stop for everything:** say "halt Chronos." That writes a HALT file; every session, scheduled or manual, refuses to act until you say "clear the halt."

**Take over by hand** (when you have time and want it faster, or usage is short and you want to choose what gets done):
1. Open a Claude Code session on the repo (cloud, desktop app, or `claude` in the Mac terminal inside `~/chronos`).
2. Type `/tick`. It does the next thing, exactly as the loop would.
3. It will tell you first if you are on the wrong model ("this build wants Opus; you are on Sonnet") and stop until you switch. You don't have to remember which model.
4. Repeat `/tick` as often as you like. The loop and you can't collide: whoever starts a build claims it for three hours.

**While the loop doesn't exist yet (builds B01–B03),** you start each by hand: open a session and say "Do build B01 from docs/v2/build/specs. Follow specs/README.md." For the review, open a **new** session (new chat, so it has no memory of the build) and say "Review build B01 per specs/README.md, reviewer rules."

---

## 3. When it halts

A halt is the system working. You get one notification with the reason and the options.

| It says | It means | You say |
|---|---|---|
| "B09 needs founder approval: protected value" | The build must create or change a validation threshold, a risk limit or a seal date. The diff is shown | "Approved" if the numbers are the ones already in the master doc; otherwise ask why they differ |
| "B07 failed review twice" | The spec or the approach is wrong, not the typing | "Show me both reviews in plain words," then usually "rewrite the spec as you propose" |
| "B12 overran its budget" | My size estimate was wrong | "Split it as proposed." The ladder is renumbered and the ledger records it |
| "B05: two options that give different results" | A real fork | Read the two options and the recommendation; pick one. If you can't tell, say "explain the trade-off like I'm new" |
| "Tests are red on the working branch" | Something merged that shouldn't have | "Roll back to the last green commit and tell me what happened" |
| "v1 guard tripped" | Something tried to edit frozen v1 code | "Revert it." Always |
| "B19 has no spec" | A new phase is starting; its cards need turning into specs | Start the phase's spec-writing session (§5) |

**What you should never say** to make a halt go away: "just make it pass," "loosen the test," "skip the review," "use a different seed." Those are the four ways a system like this gets corrupted. If Claude ever proposes one, that is a bug in Claude: say no.

---

## 4. Gates

At the end of each phase the loop writes `docs/v2/build/gates/Gn-report.md` and stops.

**Read, in this order** (two minutes): the verdict line; "what the audit tried to break, and what broke"; "decisions waiting for you."

**Check three things yourself.** Every report ends with three checks you can do without reading code, for example: "run this one command and confirm it prints 0.5630 and 0.0542" or "open this file and confirm line 3 says 2026-04-01." Do at least one. It takes a minute and it is the only check in the whole system that doesn't depend on an AI.

**Approve:** merge the gate's pull request in GitHub, or tell Claude in a live chat "approve gate G2." That moves `main`, tags the known-good point, and switches the loop back on.

**Don't approve if:** the sabotage section lists survivors that aren't explained; a number re-derived blind doesn't match; the report can't tell you plainly what was built.

**Opening a new phase.** Phases 2, 3 and 4 have cards, not full specs (see `BUILD_CARDS.md` for why). After the gate, start one planning session on the strongest model you have available and say: "Write the specs for phase N from BUILD_CARDS.md, using what the earlier phases found. Follow the format of specs B01–B18." Read its summary, then let the loop run.

| Gate | What you are really approving |
|---|---|
| G0 | This plan |
| G1 | That the loop works and what a tick costs. Whether to add a second-opinion reviewer |
| G2 | The foundations (statistics, trial store, data, costs) are correct and match v1 |
| G3 | The engine choice |
| G4 | The server's monthly cost and that collection is running clean |
| G5 | The validation thresholds. After this, results can be believed |

---

## 5. Your Mac

What I could see from here on 16 Nov: the folders `~/chronos` and `~/chronos-intake` exist [Certain]. I could not see memory, storage or what is installed.

**Two things to read off the screen once** (Apple menu → About This Mac → More Info): **Memory** (16, 24 or 32 GB) and **Storage** (256 or 512 GB). The master doc says 512 GB; you think 256. Tell Claude what it says and both documents get corrected. It matters for local models (§7) and for how much market data fits.

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
- **Fable on Pro is not in the allowance: it bills pay-as-you-go usage credits** [Certain]. A launch offer includes it for a while; one write-up dates the end of that offer for Pro to 16 Nov 2026, 11:59 pm Pacific [Likely — single source]. After that, a long Fable session on Pro costs real money.
- A scheduled cloud run uses the same allowance as you do. When the allowance is gone, runs are rejected until it resets, unless usage credits are on [Certain].

### Do this once, today
Claude → Settings → Usage: **set a monthly limit on usage credits** (suggest $0–20). Then nothing unattended can spend beyond it. If you use Fable for planning after the offer ends, this limit is your brake.

### Your cap: $100 for month one

| Choice | Monthly | When to choose it |
|---|---|---|
| Stay on Pro | $20 | Default. The loop uses the five-hour windows you weren't using anyway |
| + ChatGPT Plus as a second-opinion reviewer at gates | +$20 | Decide at G1; judge at G2 by what it caught that Claude's reviewer missed (proposal P-20) |
| Max instead of Pro | $100 | Only on measured need (rule below). It would be the whole cap by itself |

**The rule for Max, written now so it isn't decided in a bad week:** B03 measures what a build tick and a review tick cost as a share of a five-hour window. If the measured cost means fewer than **three builds a week** get through on Pro while you'd want more, switch to Max for the heavy months (phases 1 and 4) and back to Pro for the slow ones (the spike, collection). If Pro manages three or more, stay. [The threshold is my suggestion; change it at G1.]

---

## 7. When Claude usage runs out

First: **nothing breaks.** Builds commit after every step; the loop simply resumes at the next reset. The cheapest answer is often to wait.

If you want to keep working anyway, these are the options, best first.

### Option A — a second AI with its own allowance (ChatGPT Plus → Codex), $20
ChatGPT Plus includes OpenAI's coding agent, with its own five-hour and weekly limits, separate from Claude's [Likely]. It can also review every GitHub pull request automatically [Likely]. This is the strongest fallback, because it is a frontier-class model, not a small one.
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
The strongest open models are far too large for any laptop [Likely], but companies host them and charge per use, often cheaply. Claude Code can be pointed at such a service the same way as at Ollama. It counts toward your $100 and it sends your prompts to another company. Not recommended in month one: Option A is stronger for a flat price, and Option B is free.

### The side lane — the rule that makes B and C safe
Anything written by a tool other than the loop's own builder goes on a branch named `lane/<something>` and may only touch `scratch/` and `docs/drafts/`. The automatic guards refuse a `lane/` branch that touches anything else. Nothing from the lane becomes part of Chronos unless a proper build picks it up and it passes the same tests and the same Opus review as everything else.

---

## 8. Things to do before G0 (your list)

1. Look at `BLUEPRINT.md` Part 1 (diagrams) and Part 5 (the ladder). Ask about anything that doesn't match your picture of Chronos.
2. Answer the five proposals in Part 8 (P-16 to P-20). One line each is enough.
3. Read the red-team findings (`gates/G0-redteam.md`) and what was done about each.
4. Set the usage-credit limit (§6).
5. Read Memory and Storage off About This Mac (§5).
6. When convenient, not urgent: download one Kraken BTC/USD 1-minute OHLCVT file to a folder on the Mac. Build B18 uses it.

---

## 9. Glossary

**Build** one session-sized piece of work, one pull request · **Tick** one wake-up of the loop · **Gate** a checkpoint that waits for you · **Halt** the loop stopping itself · **Spec** the written instructions and pass/fail checks for one build · **Known answer** a result we know is right before the code exists, used as a test · **Pull request** a proposed change, with its tests and review attached · **Working branch (`v2-build`)** where builds land · **`main`** the approved line; moves only at gates · **Sabotage run** deliberately breaking the code to prove the tests notice · **Blind re-derivation** a separate session recomputing a result from the spec without seeing the original · **Protected value** a validation threshold, risk limit, seal date or go-live decision; always yours · **Seal** the date (1 Apr 2026) after which research can't read price data · **Footprint** the record of what data a result actually read.

---

## Sources

- Claude Code docs: [cloud scheduled tasks](https://code.claude.com/docs/en/web-scheduled-tasks), [desktop scheduled tasks](https://code.claude.com/docs/en/desktop-scheduled-tasks) (read 16 Nov 2026)
- Anthropic support: [Claude Code with Pro, Max or Ultra](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan), [Fable models on your plan](https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan)
- Plan prices and the Fable 5.2 offer dates (third-party): [danilchenko.dev](https://www.danilchenko.dev/posts/claude-code-max-vs-pro/), [wmedia.es](https://wmedia.es/en/tips/claude-code-fable-5-2-usage-credits-pro)
- Codex with ChatGPT Plus (third-party): [developersdigest.tech](https://www.developersdigest.tech/blog/codex-usage-limits-pricing-2026)
- Local models on a 16 GB Mac (third-party): [towardsai](https://pub.towardsai.net/is-a-16gb-mac-mini-enough-for-local-llms-m6-2026-efd2a80ca3d1), [bestllmfor.com](https://bestllmfor.com/guides/best-llm-macbook-air-m4/)
- Claude Code with Ollama (third-party): [morphllm.com](https://www.morphllm.com/ollama-claude-code), [kdnuggets.com](https://kdnuggets.com/pairing-claude-code-with-local-models)
- Open-weight model sizes (third-party): [opulon.org](https://opulon.org/blog/best-ai-for-coding/)
