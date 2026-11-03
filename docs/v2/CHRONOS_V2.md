# CHRONOS v2 — the master document

**Read this first. Every Claude chat, every Claude Code session, every time.**
Last updated: **3 Nov 2026**. Owner: the founder (Big Dawg / Vedant). Kept current by whoever changes anything (rules in §14).

This one file answers: what Chronos is, what is built, what is not built, what we decided and why, what we rejected and why, what to watch out for when building, and where everything else lives. If anything else disagrees with this file, **this file wins** (see §0 for the order).

---

## 0. How to use this document

**Precedence when documents disagree (highest first):**
1. The founder's latest explicit instruction in the current conversation.
2. **This file** (`docs/v2/CHRONOS_V2.md`) — especially the decisions log in §10.
3. The other files in `docs/v2/`: `BUILD_NOTES.md` (traps to avoid while building), `COMPONENTS.md` (third-party code and v1 code to reuse), `specs/` (detailed specs, with the staleness notes at their top).
4. Research notes in the claude.ai Project (`claude/item-analyses*.md`, `claude/comparison-matrix.md`, `claude/reference-library.md`). Background and reasoning; they never override this file.
5. **Frozen v1 material** (`docs/v1-archive/` including the closed v1 log `docs/v1-archive/HANDOFF.md`, the code under `src/` and `tests/`, branch `v1-final`). Reference only. Its rules (11-gate gauntlet, Binance, 10 bps taker fee, Phase 5/6, Atropos seal plan, "screens are not trials") **do not apply to v2**.
6. Memory notes about Chronos. Background only.

**If you find a contradiction:** say so, point to both places, and follow the higher one. Never silently follow the lower one, and never "fix" a Locked decision yourself. Only the founder unlocks.

**Status words used everywhere:** **Locked** = founder said "lock it" (recorded in §10). **Leaning** = current draft, open to challenge. **Open** = needs a founder answer or evidence. **Proposed** = Claude's suggestion awaiting the founder. **Deferred** = will be built only when a named trigger happens. **Parked** = not now; unparks at a named milestone. **Rejected** = not doing it, with the reason in §11.

**Reading guide by job:**
- *Building something (Code session):* §1, §2, §9, the section for the component, then `BUILD_NOTES.md` for that component and `COMPONENTS.md` for any library. Then build.
- *Analysing new content (chat):* §1, §2, §3, §5, §10, §11, §12. Judge each item against v2 (does it beat something, fill a gap, or contradict a Locked decision?).
- *Founder catching up:* §1 and §2 are the whole picture on one screen each.

---

## 1. One-screen summary

**What Chronos is.** A personal trading system meant to **make money**, starting with crypto, then forex, then equities, running several strategies at once. Honest validation stays because it stops money being lost on strategies that only work in backtests. **Capital follows evidence:** a strategy gets more money in steps as live evidence builds.

**What changed.** v1 (Jul–Aug 2026) was a research instrument built to produce a clean, documented FAIL, with an 11-gate validation gauntlet and no way to trade. Its own results showed no honest should-pass test strategy could clear all 11 gates. v2 (designed 27 Oct–3 Nov 2026) keeps v1's honest statistics, replaces the rest with open-source parts (NautilusTrader as the engine), and adds a path to live trading.

**Where we are today (3 Nov 2026).**
- **Design: done** (decisions V2-D01–D28, §10).
- **v2 code: none written yet.**
- **v1: frozen** (branch `v1-final`).
- **Data collection: not started.** Price candles and Kraken trades can be downloaded or backfilled later; what can't be recovered is news/X sentiment as it looked at the time (needed for S-NEWS) and our own snapshots of IBKR futures spreads.
- **Content analysis:** 10 items done (S1–S10). It feeds the design but does not replace building.

**First trading target.** BTC (then ETH) **intraday, long and short**, several trades a day with holds of minutes to hours. Traded through **IBKR crypto futures** (Coinbase nano BTC/ETH first, CME micro and Bitcoin Friday second). Signal history comes from Kraken spot data.

**Next step (§9):** stand up the slim VPS and start data collection. Then the v2 code skeleton (in this repo, V2-D29) with ported statistics, the one-week NautilusTrader spike, and the validation acceptance test.

**Hard rules that never bend:** LLMs never size positions, never place orders and never decide validation verdicts. Every variant tried counts as a trial. Costs are always the real venue's full costs. No high-frequency trading.

---

## 2. Status board — everything, built or not

### 2a. v2 components

| Component | What it is | Status | Why / decision |
|---|---|---|---|
| **This doc pack** (`docs/v2/`) | Single source of truth | **Done** 3 Nov | Founder request: one doc every session reads |
| **v1 freeze** | Branch `v1-final`, v1 docs to `docs/v1-archive/` | **Done** 3 Nov | V2-D10 |
| **Slim VPS + Postgres + collectors + alerts** | Always-on Linux box collecting data 24/7 | **Not started — next** | V2-D23, V2-D26. Only news/sentiment snapshots and live spread records are truly unrecoverable; prices and trades can be backfilled (see O-9) |
| **Kraken trade recorder** | Every BTC/USD + ETH/USD trade with aggressor side, recorded forward | **Not started** | V2-D26. Kraken has no bulk dump |
| **Collectors: S-NEWS (Grok/X, headlines, GDELT), S-MACRO actuals** | Forward collection, no trading | **Not started** | V2-D06, V2-D24 |
| **v2 code skeleton + ported statistics** | Stats probe, known-answer tests, trial ontology, cost code, touchstones | **Not started** | V2-D10, V2-D29: in this repo, in a new package folder; v1 code untouched |
| **NautilusTrader spike** (1 week) | Prove the engine before committing | **Not started** | V2-D04. Pass criteria in §9 step 4 |
| **Oceanus — data layer** | Kraken history + IBKR futures data, Parquet + DuckDB + Postgres | Not started (v1 version is Binance-only) | §4 |
| **Moirai — validation** (edge check + change check) | Is a strategy real? Is a change better? | **Locked design, not built** | V2-D08, D20, D21. Not trusted until the acceptance test passes |
| **Validation acceptance test** | Touchstones + null known-answer tests + planted-edge calibration | Not started | V2-D08, D20, D21, D25 |
| **Themis — sizing** | Drawdown budget → size, vol targeting, ≤ ¼ Kelly | Locked principle, not built | §6 |
| **Nemesis — hard guard + kill switch** | Limits outside strategy code | Leaning list, not built | §4 |
| **Execution** (Nautilus OMS + IBKR adapter) | Orders to IBKR futures | Not started | V2-D27 |
| **Aletheia — daily reconciliation** | Positions/balances vs the broker | Not started | §4 |
| **Mnemosyne — experiment store + version registry** | Every trial and every strategy version recorded | Not started (v1 ontology to port) | §4. Proposal P-1 adds per-trial return storage |
| **Argus — monitoring** | Alerts to phone/email | Not started | §4 |
| **Prometheus — LLM research layer** | Research cards → registry → code → checks | Leaning design, not built | §4, V2-D07 |
| **Research MCP server** | Our research tools inside any Claude chat; no order tools | Locked, sequenced after spike + acceptance test | V2-D19 |
| **S-INTRADAY** | First strategy family | **Active research track**, no rules chosen yet | V2-D28 |
| **S-TREND** | Slow trend; regime filter + benchmark for S-INTRADAY | Active (as filter/benchmark) | V2-D28 |
| **Kronos shadow signal** | Open-source candle model as an input, no order authority | Locked spec, after a baseline exists | V2-D05 |
| **AI entry veto** | AI may block, never create, entries; fail-closed | Locked as a candidate to forward-test | V2-D18 |
| **S-MACRO / S-NEWS** | News and data-surprise strategies | Collection only | V2-D06, V2-D24 |
| **S-ORDERFLOW, Hawkes, market profile** | Order-flow ideas as S-INTRADAY inputs | Parked theses; data collected from now | §5 |
| **S-INSIDER, S-QUALITY** (equities) | Form 4 insider buying; quality screens | Parked until crypto reaches paper (L3) | V2-D24 |
| **FX** | Via IBKR | Parked until crypto reaches paper | V2-D24, V2-D12 |
| **Event bus (Kafka/Redpanda), API gateway, user management** | Platform infrastructure | **Deferred to triggers** | V2-D23 |

### 2b. Built in v1 (frozen; reuse by porting, see `COMPONENTS.md` §2)

Statistics with known-answer tests (Lo 2002, Newey–West, Politis–Romano stationary bootstrap, PSR/DSR, block p-value, effective trials; `chronos_math_probe.py` 28 checks) · SEARCH/VERIFICATION trial ontology (`src/chronos/run.py`) · cost and slippage code · touchstone strategies T-a1…T-e and the regime generator · holdout seal (`src/chronos/oceanus/seal.py`) · Binance data layer (not reused for trading; Binance is not usable from Ontario).

### 2c. Outside the repo

- **Content-intake pipeline** on the founder's Mac (`~/chronos-intake`): downloads, transcribes and OCRs Instagram posts for analysis.
- **Content analysis S1–S10:** reasoning in the claude.ai Project (`claude/item-analyses.md`, `claude/item-analyses-2.md`).

---

## 3. Constraints

| Item | Value | Status |
|---|---|---|
| Running-cost budget | ~$100–150/month to start, ~$300–500/month once live. **Running costs only** (VPS, data, APIs, subscriptions). Trading capital is separate | Locked (V2-D13) |
| Trading capital | Configuration, never architecture. ~$2k start indicated, growing toward ~$8–10k. Every money amount is config; strategies and risk work in fractions; sizing rounds to the venue's minimum order and skips trades it can't place | Set before live |
| Crypto execution | **IBKR crypto futures, long and short.** Primary: Coinbase Derivatives nano BTC (0.01 BTC) and nano ETH (0.1 ETH), perpetual-style and monthly, 24/7 except Fri 17:00–18:00 ET. Secondary: CME Micro Bitcoin (0.1 BTC), Bitcoin Friday (1/50 BTC, weekly), Sun–Fri ~23h. IBKR commission per contract: Coinbase ~USD 0.20, BFF 0.25, MBT 0.85, plus exchange/regulatory fees (not yet checked). CME margin ≈ 24% of notional, so one MBT is too big for ~$2k; nano/BFF first. Founder confirmed Ontario eligibility | Locked (V2-D27) |
| Crypto data | **Kraken** spot: OHLCVT candles 1 min–1 day from each pair's first trade (quarterly downloadable files), trades with aggressor side via API. Kraken spot fees ~0.40% maker / 0.80% taker at the lowest tier [Likely], too high for active trading; optional long-only spot sleeve only | Locked (V2-D26, D27) |
| FX + equities | Interactive Brokers. No MT5, no Windows | Locked (V2-D02) |
| No high-frequency trading | Several trades a day, holds of minutes to hours: allowed. Sub-minute holds, queue or order-book strategies, market making, latency-dependent edges: not allowed | Locked (V2-D22, D28) |
| Hardware | M4 MacBook Air 512 GB (+ external SSD available) for research; one always-on Linux VPS for collection and later paper/live. No Windows, no new laptop, no GPU purchase, never the work laptop | Locked |
| Employer | AGF approval given verbally (manager + head of trading, 29 Oct). Compliance is the founder's responsibility; Chronos does not gate on it | Closed (V2-D16) |
| Team | **Founder works solo.** Developer and quant unavailable for the foreseeable future. Claude makes the statistical calls under the review protocol V2-D25 | Locked (V2-D25) |
| Binance, offshore perp exchanges (Bybit, OKX, Hyperliquid) | Not for trading. Binance public archives may be used for research history only | Locked (V2-D02, D27) |

---

## 4. Architecture (layers)

Built on **NautilusTrader** (event-driven; the same strategy code runs in backtest, sandbox and live; LGPL-3.0). Final once the one-week spike passes (§9 step 4). Greek names are kept only for layers we build ourselves; open-source parts go by their real names. **Chronos** = the platform. **Kronos** = the open-source candle model. Don't mix them up (V2-D01).

| Layer | v2 design | Status |
|---|---|---|
| **Oceanus — data** | Raw immutable files → processed Parquet + DuckDB; Postgres for operational tables. Unified schema: `instrument_id`, `timestamp_utc`, `source`, `asset_class`, plus `available_at` for anything non-price (point-in-time). **Signal history from Kraken spot; costs, fills and basis from the IBKR futures actually traded.** Sources: Kraken OHLCVT files + API, Kraken trade recorder (V2-D26), IBKR futures quotes/bars (paid market data, check cost), SEC EDGAR (free, 10 req/s, declared User-Agent), GDELT, news RSS, Grok API, official macro releases, licensed consensus vendor (Open) | Leaning |
| **Event backbone** | **Deferred (V2-D23).** Now: collectors write to Postgres/Parquet on a schedule; Nautilus uses its internal bus. **Trigger:** a second consumer process or machine needs the live event stream → Kafka-compatible bus (Redpanda vs Kafka chosen then) | Locked (deferred) |
| **API gateway + users** | **Deferred (V2-D23).** Now: founder-only access over SSH; kill switch = CLI command + config flag read by Nemesis; live approval = founder-signed registry entry. **Triggers:** a second person needs access, or an external client (dashboard, phone) needs authenticated access → FastAPI behind TLS | Locked (deferred) |
| **Prometheus — LLM research layer** | Sources → role agents (analyst, researcher, skeptic) → `ResearchCard` (claim, source URL, `as_of`, kind, assumptions, uncertainty, data needed) → deterministic card validator → hypothesis registry (each test a counted trial) → Claude Code writes exact rules + tests → look-ahead review → edge check. Scheduled briefs. Failure-diagnosis agent for live strategies. **Research MCP server (V2-D19):** data queries, backtests, trial registry, Kronos forecasts inside any Claude chat; server logs every backtest as a counted trial; no order tools | Leaning (design); MCP Locked |
| **Kronos — candle model** | Shadow signal, no order authority. Three roles tested separately: direction, filter, volatility-for-sizing. `NeoQuasar/Kronos-small` / `-base`, MIT | Locked (V2-D05); spec `specs/kronos-shadow.md` |
| **Screening** | Fast vectorised sweeps; **every screened variant counts as a trial** | Locked (counting, V2-D03) / Leaning (VectorBT) |
| **Engine** | Backtest, paper and live on one code path | NautilusTrader, Locked pending spike (V2-D04) |
| **Moirai — validation** | Edge check (new strategies) + change check (changes to live ones), §6 | Locked, conditional on the acceptance test (V2-D08) |
| **Themis — sizing + limits** | Drawdown sets size (ruin cushion), vol targeting, ≤ ¼ Kelly cap, per-strategy capital sleeves | Locked principle / Leaning parameters |
| **Nemesis — hard guard + kill switch** | Outside strategy code. Minimum checks: kill switch, duplicate order, stale data, daily loss, max position, max exposure, per-sleeve budget, price band (fat-finger), order comes from an approved version, rate limit, founder approval for live. Research code may not import it. Use Nautilus's risk engine where it covers these | Leaning (list) |
| **Execution** | Nautilus OMS + IBKR adapter (crypto futures, later FX/equities); Kraken adapter only if a spot sleeve is used. **Cost model:** commission + exchange/regulatory fees + spread + slippage + perpetual-style funding + futures–spot basis (signals come from spot data). No maker-fee savings booked without measured post-fill markout | Leaning |
| **Aletheia — reconciliation** | Daily positions and balances vs the broker | Leaning |
| **Mnemosyne — experiment store + registry** | v1 SEARCH/VERIFICATION ontology for honest trial counts + version registry (baseline, candidate, paper, live, rolled back), in Postgres | Leaning |
| **Argus — monitoring** | Alerts: drawdown breach, unusual slippage, order rejection, data feed down, strategy silent, system error, daily report. To phone/email. Grafana later | Leaning |
| Hephaestus, Hermes | Retired; replaced by NautilusTrader | Locked |
| Zeus | Dormant | — |

---

## 5. Strategies and research scope

**Scope (V2-D24 as amended by V2-D28, Locked).** One active research track: **S-INTRADAY** with S-TREND as its regime filter and benchmark, then Kronos. Plus early collection for S-NEWS, S-MACRO and Kraken trades. FX and equities research is parked until crypto reaches paper trading (L3). The architecture stays multi-market. **Live rollout order: crypto → FX → equities** (V2-D12). Each market needs its own data, cost model, legal check and trial budget.

| ID | Strategy | Markets | Evidence type | Track |
|---|---|---|---|---|
| **S-INTRADAY** | BTC (then ETH) intraday, long and short, several trades a day, holds of minutes to hours. Rule sets come from research cards; none chosen yet. Uses S-TREND's regime (lean long in uptrends, short in downtrends) | IBKR crypto futures | Backtest on Kraken 1-min spot history with futures costs, funding and basis modelled → paper on IBKR → live | **Active — first** |
| S-TREND | Slow trend/momentum with calm-vol filter, vol-scaled sizing, pre-set stop; long and short via futures | Crypto futures; FX later | Backtest (post-cost, honest N) → paper → live | Active as filter/benchmark; maybe its own sleeve |
| Kronos roles | Direction / filter / volatility for sizing | BTC | Backtest only on data **after the checkpoint's training cutoff** (June 2024 per one review [Likely]; confirm from the repo) | Active after a baseline exists. Spec's 1h/4h bars to be re-checked against the intraday horizon |
| S-MACRO | Trade economic-release surprises (actual vs consensus) | FX, crypto | Backtestable once a consensus source is licensed | Collection only (official actuals with release timestamps) |
| S-NEWS | Frequency × intensity of independent news per clustered event (Grok/X, headlines, GDELT, live press conferences via Whisper) | Crypto first, then FX | **Forward-only**; GDELT history as a crude proxy | Collection only. Spec `specs/sentiment-strategy.md` |
| S-ORDERFLOW (thesis) | Aggressor-side delta, Hawkes trade clustering, market-profile value areas as S-INTRADAY inputs | Crypto | Needs recorded trades (V2-D26) | Parked; data collected from now. Traps in `BUILD_NOTES.md` §8 |
| S-INSIDER | Corporate insider buying (SEC Form 4); `available_at` = filing acceptance time | US equities | Backtestable from EDGAR (free) | Parked until crypto reaches L3 |
| S-QUALITY | Quality/value screens; point-in-time fundamentals from SEC XBRL company facts (free) | US equities | Backtestable | Parked until crypto reaches L3 |

**Every strategy idea, whatever its source, enters as an L0 research card** with a hypothesis, the data needed and a falsifier, and is tested through the ladder in §6. Every variant tried counts toward the trial total.

---

## 6. Validation and the evidence ladder

- **Ladder:** L0 idea card → L1 counted screen → L2 edge check → L3 paper on live data → L4 tiny live with a pre-committed maximum loss → L5 size up by risk budget as live evidence accumulates.
- **Edge check (new strategies).** All of these must pass:
  1. **Data-sufficiency check first:** can the available history answer the question at all (years-to-significance)?
  2. **DSR with honest N:** every screened variant counted.
  3. **Positive after costs at 1× and 2×**, using the real venue's full costs: IBKR commission + exchange fees + spread + slippage + funding + basis.
  4. **Beats the random-entry null.**
  5. **Parameter neighbourhood is not a lone spike.**
  
  Reported as **warnings, not gates:** subperiod stability, minimum trade count, capacity.
- **Null benchmark (V2-D21, Locked):** random entries with matched exposure on the **real** price path.
  - Each draw keeps the strategy's number of trades, holding-time distribution (sampled from the real trades), long/short mix, sizing rule and costs.
  - Positions don't overlap. Entries only on bars where the real strategy could have traded. At least 1,000 draws.
  - **Every rank or p-value counter uses mid-rank ties.**
  - Trade-order shuffling is never used for sum-type metrics. The resampled-price bootstrap is not the null.
  - Known-answer tests:
    - (a) floating-point permutation case: strict `>` gives ≈37.6 on noise; mid-rank ≈50.
    - (b) a strategy with random entries gives roughly uniform p-values.
    - (c) a planted timing edge gives low p-values.
    - (d) constant exposure on a trending series does **not** pass.
- **Neighbourhood check (V2-D20, Locked):** binding.
  - A lone spike also triggers a mandatory bug/look-ahead review.
  - The exact rule (neighbourhood size, allowed degradation) is calibrated in the acceptance test, which must include **intraday-style planted edges** because S-INTRADAY is the first family (V2-D28).
  - Re-argue the rule before applying it to any family expected to be naturally narrow.
- **Change check (live strategies):**
  - Paired daily-difference test vs the known-good version.
  - Šidák bar over cumulative trials. 2× costs.
  - **Without** S1's built-in bias (drawdown ≤ and turnover ≤ baseline), so improvements that trade more can pass.
- **Drawdown is a sizing input, not a reject gate.**
  - Choose the accepted ruin probability → cushion → risk per trade. Verify with block bootstrap, because the formula assumes independent trades.
  - Use S2's formulas **with the ruin bug fixed**: `exp(-θ·D)`, not `exp(-θ·D·L)`.
- **Acceptance test (before the redesign counts as done):**
  - Port the v1 touchstones. T-b, T-d and T-e must still **FAIL** the edge check. T-a2 should **PASS** once sized by its drawdown budget.
  - Include the null known-answer tests.
  - Include the planted-edge calibration of the neighbourhood rule: noise worlds, a smooth planted edge, a narrow real edge. Measure false passes and false rejections for DSR alone vs DSR + neighbourhood. Pick the rule by criteria written before running.
  - Reviewed under V2-D25.
- **Review protocol (V2-D25, Locked), replacing the quant:**
  1. Every statistical tool reproduces known answers before it is trusted.
  2. Pass/fail rules are committed before a test runs.
  3. On high-stakes work, and on founder request, a separate agent that hasn't seen the work re-derives the result from the spec.
  4. The founder challenges Claude's calls.
- **Kept from v1:** honest trial counting, DSR, Lo / Newey–West / block bootstrap (dependence-aware) statistics, provenance discipline (every threshold traceable to a reproducible path), no seed shopping, sealed holdouts touched once, state asymmetric findings asymmetrically.

---

## 7. AI rules

- **Levels:**
  - **L0:** research only.
  - **L1:** model output is an input to a deterministic strategy (Kronos, sentiment scores).
  - **L2:** an LLM proposes a structured trade intent; deterministic code sizes it, runs the guard and executes it inside a capped sleeve (S-NEWS).
  - **L3:** an LLM places orders with tools. **Rejected.**
- **Locked (V2-D07):** LLMs never set position size, never place orders, never decide validation verdicts.
- **LLM look-ahead:** LLM signals can't be honestly backtested on data their training already covers (Sarkar & Vafa 2024).
  - Forward evidence only, from timestamped stored outputs with pinned model versions.
  - Every prompt or model version counts as a trial.
- **Text and sources:** external text (X, news, web) is data, never instructions. Cited URLs are checked by code.
- **AI entry veto (V2-D18, candidate):**
  - Deterministic risk checks run first. Then an AI may **block** a new entry, never create one.
  - Exits, stops and emergency actions never wait on AI.
  - **Fail-closed:** AI down means no new entries.
  - No third-party decision service. Pinned model, every decision stored.
  - Tested forward only, with/without comparison.
- **Intensity scorer (Leaning):** during collection, score every event with both Grok and Claude (pinned versions) and log disagreement. Choose at rule-freeze.
- **Local models:** a local embedding model for clustering news into events (Leaning). A frozen local LLM scorer considered at S-NEWS rule-freeze.

---

## 8. Infrastructure and budget

- **Mac:** research, backtests, Kronos backfill, development.
- **VPS (needed now, slim, V2-D23).** An always-on Linux box running:
  - Postgres and the scheduled collectors: Kraken trade recorder, Grok, headlines, GDELT, official macro actuals; press-conference transcription later.
  - Simple alerts.
  - Later, Nautilus paper/live with **IB Gateway**.
  - Probably 2 vCPU / 4–8 GB at first [Guessing], about US$10–30/month [Guessing — check prices].
- **Rough start budget (running costs only), ≈ $20–60/month, inside $100–150:**
  - VPS $10–30.
  - LLM APIs ~$5–20.
  - GDELT and Kraken data $0.
  - IBKR market data for CME and Coinbase Derivatives: a few dollars a month, possibly waived above a commission threshold [Guessing — check].
- **Budget problem:** the S-MACRO consensus vendor. FMP's economic calendar is listed at ~$100/month [Likely]. Open; only needed when S-MACRO leaves collection-only.
- **Upgrade triggers:**
  - Bigger VPS or a transcription API when live press-conference transcription starts.
  - Hourly cloud GPU only if Kronos fine-tuning is ever pre-registered.
  - External SSD when the disk passes ~70%.
  - Optional home research box only if overnight jobs keep tying up the Air.
- **Before going live:** compare monthly running cost with expected after-cost returns at the actual capital.

---

## 9. Build order (what happens next, in order)

1. ~~**Freeze v1**~~ — **done 3 Nov 2026** (branch `v1-final`, docs to `docs/v1-archive/`, closing entry in `docs/v1-archive/HANDOFF.md`).
2. **Create the v2 code skeleton in this repo (V2-D29) and port:**
   - the stats probe + known-answer tests (DSR, Lo, Newey–West, block bootstrap, **plus the mid-rank permutation-tie case**);
   - the trial run-kind ontology;
   - the cost/slippage measurement code;
   - the touchstones as acceptance tests.
   
   Fix the strict-`<` rank in v1 `src/chronos/moirai/stages/null_bench.py` when porting (`BUILD_NOTES.md` §2).
3. **Stand up the slim VPS and start collection:** Postgres + scheduled collectors + simple alerts (§8). Can run in parallel with step 2. Urgent only for the parts that can't be recovered later (news/X sentiment for S-NEWS, live IBKR spread snapshots); price candles and Kraken trades can be downloaded or backfilled (O-9).
4. **NautilusTrader spike (one week).** Pass criteria:
   - (a) one MA strategy on Kraken BTC data matches v1 Hephaestus within explainable differences;
   - (b) our cost/slippage model plugs in;
   - (c) several days of sandbox paper on an **IBKR paper account trading nano BTC futures**, long and short, with no manual intervention;
   - (d) two strategies on two venues in one node;
   - (e) Nautilus's IBKR adapter can trade **Coinbase perpetual-style nano contracts**, and we can read their funding and fees. If it can't, raise it immediately as an engine-choice problem.
5. **Validation acceptance test** (§6). Must pass **before** any S-INTRADAY or S-TREND result is trusted.
6. **S-INTRADAY on BTC futures**, with S-TREND as regime filter and benchmark: research cards → pre-registered rules → counted screen → edge check → paper on IBKR (L3).
7. **Kronos:** backfill forecasts over the clean window; evaluate per spec on top of the S-INTRADAY/S-TREND baseline.
8. **Research MCP server** (V2-D19), once steps 4–5 exist to wrap.
9. **Unpark FX and equities** when crypto reaches paper (L3).

---

## 10. Decisions log (canonical from 3 Nov 2026)

Format: ID · date · decision · status. Appended only when the founder says "lock it". Earlier copies of this log in the claude.ai Project (`claude/chronos-v2-changes.md`) are frozen as of 3 Nov; this table is the live one.

| ID | Date | Decision | Status |
|---|---|---|---|
| V2-D01 | 28 Oct | Naming: Chronos = platform; Kronos = candlestick model component; Greek names only for layers we build | Locked |
| V2-D02 | 28 Oct | Venues: Kraken for crypto; IBKR for FX and equities; no MT5, no Windows | Locked (crypto execution amended by V2-D27) |
| V2-D03 | 27–28 Oct | Reverse v1 D-07: **every screened variant counts as a trial** | Locked |
| V2-D04 | 27–28 Oct | NautilusTrader is the engine front-runner; final after the one-week spike passes its criteria (§9 step 4) | Locked |
| V2-D05 | 27–28 Oct | Implement Kronos as a shadow signal per `specs/kronos-shadow.md` | Locked |
| V2-D06 | 27–28 Oct | News/sentiment is its own strategy with a small capped sleeve, forward-tested, scaled only on evidence; split into S-MACRO and S-NEWS | Locked |
| V2-D07 | 28 Oct | LLMs never size, never place orders, never decide validation verdicts; L1 + L2 allowed; L3 rejected | Locked |
| V2-D08 | 28 Oct | Validation redesign: edge check + change check; drawdown → sizing; subperiod/breadth/capacity → warnings. **Counts as done only after the acceptance test passes** (reviewed under V2-D25) | Locked (conditional) |
| V2-D09 | 28 Oct | Build the event bus, API gateway and user management now | **Superseded by V2-D23** |
| V2-D10 | 28 Oct | Freeze the v1 repo; v2 starts fresh; port stats probe + tests, trial ontology, cost/slippage code, touchstones. *(Freeze done 3 Nov. "New v2 repo" amended by V2-D29: v2 lives in this repo)* | Locked (amended by V2-D29) |
| V2-D11 | 28 Oct | Process: append-only logs, versioned configs, commit rule; protected approvals **only** for validation thresholds, risk limits, promotion to live | Locked |
| V2-D12 | 28 Oct | Live rollout crypto → FX → equities (research scope now V2-D24/D28) | Locked (rollout order) |
| V2-D13 | 28 Oct | Budget ~$100–150/month to start, ~$300–500 once live; running costs only; trading capital separate | Locked |
| V2-D14 | 28 Oct | "Insider" = corporate insider filings (SEC Form 4) → S-INSIDER | Locked |
| V2-D15 | 28 Oct | Replace Forex Factory (terms forbid scraping) with official actuals + a licensed consensus vendor | Locked (vendor Open) |
| V2-D16 | 28–29 Oct | AGF approval given verbally; employer compliance is the founder's responsibility; no approval gate in Chronos | Closed |
| V2-D17 | 28 Oct | Two QuantDinger days in the engine spike | **Dropped** with V2-D23 |
| V2-D18 | 28 Oct | AI entry veto as a candidate to test: blocks entries only, exits bypass AI, fail-closed, no third party, forward-tested with/without | Locked (as candidate) |
| V2-D19 | 28 Oct | Build our own research MCP server: read-only research + backtests, every backtest logged as a counted trial server-side, no order tools. Hosted MCP trading services rejected | Locked |
| V2-D20 | 28–29 Oct | Neighbourhood check stays **binding**; a lone spike triggers a bug/look-ahead review; exact rule calibrated by the planted-edge test in the acceptance test; re-argue before applying to naturally narrow families | Locked |
| V2-D21 | 28–29 Oct | Null = random entries with matched exposure on the real price path (details §6); mid-rank ties everywhere; known-answer tests (a)–(d); no trade-order shuffling for sum-type metrics; resampled-price bootstrap dropped as the null | Locked |
| V2-D22 | 28–29 Oct | No high-frequency trading (definition in §3) | Locked |
| V2-D23 | 29 Oct | Supersedes D09. Build now only: slim VPS, Postgres, scheduled collectors, simple alerts. Bus, gateway and users deferred to triggers (§4). Meanwhile SSH-only, CLI kill switch, founder-signed live approvals | Locked |
| V2-D24 | 29 Oct | Research scope: one active track + collection only for S-NEWS/S-MACRO; equities and FX research parked until crypto reaches paper (L3) | Locked (first track amended by V2-D28) |
| V2-D25 | 29 Oct | Review protocol while solo: known-answer tests, pre-committed pass/fail rules, blind second-agent re-derivation on high-stakes work, founder challenge | Locked |
| V2-D26 | 29 Oct | Record Kraken BTC/USD and ETH/USD trades (price, size, time, aggressor side, market/limit) forward from now on the VPS | Locked |
| V2-D27 | 29 Oct | Active crypto trading on **IBKR crypto futures**, long and short (Coinbase nano BTC/ETH primary; CME Micro Bitcoin and Bitcoin Friday secondary). Kraken for data, trade recording and an optional long-only sleeve. Full cost model incl. funding and basis. Offshore perpetual exchanges rejected | Locked |
| V2-D28 | 29 Oct | First active track is **S-INTRADAY** (BTC then ETH, long/short, minutes-to-hours holds) on IBKR futures; S-TREND becomes its regime filter and benchmark; neighbourhood rule for intraday families set by intraday planted-edge worlds | Locked |
| V2-D29 | 3 Nov | Amends V2-D10: **v2 code lives in this same repo** (`vedantgautam1/chronos`), which the claude.ai Project already syncs. v1 stays frozen on branch `v1-final` and in `docs/v1-archive/`; v1 code under `src/chronos/` and `tests/` is not modified; v2 code goes in its own new package folder (layout set in the step-2 build session) | Locked |
| — | 28 Oct | Intensity scorer: Grok + Claude both during collection, choose at rule-freeze | Leaning |
| — | 28 Oct | Point-in-time fundamentals from SEC XBRL company facts (free) | Leaning |
| — | 3 Nov | v2 doc pack: `docs/v2/CHRONOS_V2.md` is the single master doc; repo is canonical; v1 frozen under branch `v1-final` | Done (founder instruction 3 Nov) |

**Next decision ID: V2-D30.**

---

## 11. What we are NOT doing — and why

### 11a. Retired from v1
| Item | Why |
|---|---|
| Goal "clean documented FAIL = success" | Founder reframe: the goal is to make money; validation protects money, it isn't the product |
| 11-gate binding gauntlet with no override | No honest should-pass test strategy could clear all 11; replaced by edge check + change check (V2-D08) |
| Gate 4.4 (`ruin_dd`) as a reject gate | It judged the sizing choice, not the edge (T-a2 sized at 95% failed at 0.535 vs 0.40); drawdown is now a sizing input |
| D-07 "screens are not trials" | Uncounted screening inflates the winner (V2-D03) |
| Hephaestus engine, Hermes execution design | Replaced by NautilusTrader (backtest = paper = live) |
| Phase 5/6 work (Mode S, GATE C, ruin_dd calibration, v002 reconciliation list, the Atropos seal plan) | Belongs to the retired gauntlet |
| Binance as a venue; 10 bps taker / 1 bps slippage defaults | Not usable from Ontario; v2 costs come from IBKR futures |
| Protected-path ceremony everywhere | Slowed a one-person build; now only thresholds, risk limits, live promotion (V2-D11) |
| Building bus/gateway/users up front (V2-D09); QuantDinger spike days (V2-D17) | Build time is the scarcest resource; triggers instead (V2-D23) |
| Resampled-price bootstrap as the null | Chunk-length dilemma (V2-D21) |

### 11b. Rejected options (don't re-evaluate from scratch)
| Item | Why rejected | Source |
|---|---|---|
| LLM placing orders (L3); AI orchestrator approving strategies straight to execution | Safety: V2-D07 | S3 |
| Astral (heyastral.ai) and other hosted MCP trading services | Closed, uncounted trials, LLM in the order path, funnel | S7 |
| QuantDinger as the platform | No Ontario-usable crypto venue; validation flaws (pruned trials uncounted, recommendation ignores DSR/PBO); 262k lines to own. Kept as a blueprint for when the bus/gateway triggers fire | S6 |
| MT5 / Windows | Windows-only Python package; IBKR covers FX | S3 |
| Binance, Bybit, OKX, Hyperliquid for trading | Not available to Ontario residents or legally grey; counterparty risk; IBKR covers shorting and 24/7 | V2-D27 |
| Kraken margin/shorting | Not available to Ontario retail | V2-D27 |
| Forex Factory scraping | Terms forbid it | V2-D15 |
| High-frequency trading, market making, queue strategies | Fees, latency, adverse selection at our size | V2-D22 |
| Trade-order shuffling as a null for return/Sharpe/PF | Mathematically uninformative (sum is unchanged by reordering) | V2-D21 |
| REA / reverse-engineering trading software | Nothing legitimate to point it at; never on AGF systems | S5 |
| Bullseye Order Flow as a signal source | Its default "order flow" is candle shape + volume; its location filter is dead code | S9 |
| PySR (symbolic regression) for signal discovery | Searches enormous numbers of formulas; any find is undeflatable or overfit | S10 |
| MAPIE for volatility intervals | Best setup only matched a one-line EWMA band, much slower | S10 |
| VectorBT + Backtrader dual engine | Engines disagree; Backtrader unmaintained | S1 |
| "Edge is in the Process" selection claim (Daru) | Compares profit factors across portfolio sizes; pooled result still loses | S8a |

Full list with links: Project doc `claude/reference-library.md` §8.

---

## 12. Open questions and pending proposals

| ID | Question / proposal | Status | Needed by |
|---|---|---|---|
| ~~O-1~~ | Where v2 code lives | **Resolved 3 Nov → V2-D29: this repo** | — |
| **P-1** | Mnemosyne stores each counted trial's daily net return series and trade list, so set-level tests (SPA/StepM/MCS), effective-N estimation and CSCV stay possible later. ~32 MB per 5,000 variants × 800 days | **Proposed (S10)** | Before the experiment store is built |
| P-2 | Add a HAR realised-variance baseline (5-min returns) to Kronos role C when the spec is re-checked for intraday bars | Proposed (S10) | Before Kronos work |
| O-3 | Exact neighbourhood rule (size, allowed degradation) | Open → acceptance test | Step 5 |
| O-4 | IBKR futures cost model: exchange/regulatory fees for Coinbase nano and CME contracts; perpetual-style funding mechanics; IBKR market-data cost | Open → spike | Step 4 |
| O-5 | Consensus-forecast vendor for S-MACRO | Open | When S-MACRO leaves collection |
| O-6 | Mac RAM (only matters for local model sizes) | Open | Before local models |
| O-7 | Before live: actual capital, sleeve %, max losses, running cost vs expected returns | Open | Before L4 |
| O-9 | V2-D26's stated reason ("Kraken has no bulk dump, so forward recording is the only cheap way") is overstated: Kraken's trades endpoint can be paged back through full history, just slowly [Likely — Kraken docs, not timed]; paid vendors also sell historical trades [Likely]. Forward recording is still cheap; the question is whether it should block the build order | Open — founder | Before step 3 |
| O-8 | Kronos spec horizons (1h/4h bars) vs the intraday track | Open | Before Kronos work |

---

## 13. Where everything lives

| What | Where | Notes |
|---|---|---|
| **This master doc** | `docs/v2/CHRONOS_V2.md` (repo) | Canonical |
| Build traps per component | `docs/v2/BUILD_NOTES.md` | Read before building that component |
| Third-party code + v1 code to reuse | `docs/v2/COMPONENTS.md` | Source, licence, version, test status |
| Detailed specs | `docs/v2/specs/` | Kronos shadow; sentiment strategy (each with a staleness note at the top) |
| Content-analysis results (reasoning per source S1–S10+) | claude.ai Project: `claude/item-analyses.md`, `claude/item-analyses-2.md` | Background; this doc wins |
| Every option considered | Project: `claude/comparison-matrix.md` | Record of options |
| Kept-for-later library (repos, data sources, findings, rejected) | Project: `claude/reference-library.md` | Check before re-researching anything |
| How to run content analysis | Project: `claude/content-analysis-handoff.md` | Points back here |
| S10 test scripts | `docs/v2/research/s10-deep-pass/` | Rerun with `python -I` |
| v1 frozen docs | `docs/v1-archive/` (incl. `HANDOFF.md`, the v1 log, closed 3 Nov) | Reference only |
| v1 frozen code | `src/`, `tests/`, branch `v1-final` | Port from it; don't extend it |
| Content intake pipeline | Founder's Mac `~/chronos-intake` | Not in the repo |

---

## 14. Keeping this current (rules for every session)

1. **Start of any session:** read §1–§2 and the sections for your task. If the request conflicts with this file, say so before doing anything.
2. **Locks:** only the founder locks ("lock it"). On a lock, in the same turn:
   - append the decision to §10;
   - update every section it touches (status board §2, constraints, architecture, open questions);
   - bump "Last updated";
   - **sweep `BUILD_NOTES.md`, `COMPONENTS.md`, `specs/` and the Project docs** for references to what changed, and fix or annotate each one. A spec still saying "Kraken execution" after V2-D27 is the failure this rule exists for.
3. **Building:** when a component changes status (not started → in progress → built), update its row in §2 in the same commit. When you hit a trap worth remembering, add it to `BUILD_NOTES.md`. When you adopt a library, add it to `COMPONENTS.md` with version and licence.
4. **Content analysis:** new items are judged against this file. Findings go to the Project research docs. Anything that changes the design becomes a proposal in §12, and only enters §10 when locked.
   - Sessions that can write to both the repo and the Project (Claude Code with the Project attached) update both.
   - A claude.ai chat that can't write to the repo lists the change at the top of `claude/content-analysis-handoff.md` under "Pending repo updates", and the next repo-capable session applies it.
5. **Never** mark something Locked, Done or Built that isn't. Asymmetric findings are stated asymmetrically.
6. **Keep §1 and §2 short enough to read in two minutes.** Move history and detail elsewhere; never delete a decision.
