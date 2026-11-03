# BUILD NOTES — traps to avoid, by component

Companion to `docs/v2/CHRONOS_V2.md` (read that first). This file is the "things to keep in mind" list: every trap we already found, so a build session doesn't rediscover it the expensive way. **Read the section for the component you're about to build.** Add new traps as you find them (CHRONOS_V2 §14 rule 3).

Tags: [Certain — run] = we ran code and saw it · [Certain — read] = read in code or docs · [Likely] / [Guessing] = not verified. Source IDs (S1…S10) point to `claude/item-analyses*.md` in the claude.ai Project.

---

## 1. All code

- **Run before trusting.** Where a source ships code, run it rather than trusting printed excerpts. Several real bugs were found this way:
  - S2's audit table was produced with costs set to zero;
  - S2's ruin formula is wrong;
  - floating-point permutation ties distort ranks.
- **Statistical methods enter only with passing known-answer tests** (V2-D25 point 1). LLM memory, Claude's included, is not a source.
- **Pass/fail rules are committed before a test runs** (V2-D25 point 2). No changing thresholds after seeing results. No seed shopping.
- **"Tests green" ≠ "it works."** After structural changes, run the end-to-end path, not just the unit tests. (v1 lesson)
- **Never loosen a test assertion to make it pass.** Fix the cause. (v1 rule)
- **Stop and flag** when a change forks into non-equivalent options. Present both and ask. (v1 rule; it was right every time)
- **Time:** tz-aware UTC everywhere, half-open `[start, end)` ranges. Decimal for the money ledger, float64 for series maths. (v1 conventions, kept)
- **Isolation:** run downloaded or third-party code with `python -I` from outside its own folder.
- **Environment:** the v1 repo uses `uv` (no bare `pip install` into the project). Keep that unless the founder decides otherwise.

## 2. Validation and statistics (Moirai)

- **Mid-rank ties in every rank or p-value counter** (V2-D21). Strict `>` on noise gives a mean rank of ≈37.6 instead of 50, because floating-point summation order creates fake differences [Certain — run, S8a reproducer].
  - **v1 `src/chronos/moirai/stages/null_bench.py` line ~125 uses strict `<`:** `np.mean(nulls < candidate_net)`. Fix it when porting [Certain — read].
- **Never use trade-order shuffling for sum-type metrics** (total return, trade Sharpe, profit factor). Reordering trades doesn't change a sum, so the test can't rank them [Certain — arithmetic].
  - Shuffling *is* fine for path metrics like max drawdown. v1 `trade_shuffle.py` uses it only for drawdown [Certain — read].
- **The null is random entries with matched exposure on the real price path** (full recipe in CHRONOS_V2 §6). Don't fall back to resampled-price bootstraps.
- **DSR/PSR take the non-annualised Sharpe** at native bar frequency. `SR*` is floored at 0 (it goes negative at small N). N comes from counting SEARCH-kind trials, never from a raw execution counter (v1 rules, kept).
- **Count every screened variant** (V2-D03), including pruned ones, cumulatively across jobs.
  - QuantDinger's DSR miscounts N this way (pruned trials dropped, count reset per job). Its "recommended" flag also *requires* a minimum number of trials, which rewards searching more [Certain — read, S6]. Don't copy either pattern.
- **Don't average different checks into one score** (QuantDinger's robustness grade does). A strong score on one check can hide a fail on another.
- **Don't reuse a holdout across reruns.** Repeated runs turn it into a selection set (QuantDinger, S3's version table).
- **Raw N over-penalises correlated searches.** In a 20,000-formula noise search, the best |t| was 3.15, below the ≈4.06 expected from 20,000 *independent* tries, because formulas over the same inputs overlap [Certain — run, S10]. Estimating effective N needs stored per-trial return series (proposed V2-D29).
- **iid bootstrap on autocorrelated returns is badly overconfident:** 74% actual coverage for a nominal 95% interval (AR(1), φ = 0.5). The stationary bootstrap with automatic block length gives 92.7% [Certain — run, S10]. Use block methods.
- **Set-level tests (SPA/StepM/MCS) only see what you hand them.** Handing SPA the best 50 of 2,000 noise variants gave p = 0.028 (a false find); all 2,000 gave p = 0.56 [Certain — run, S10]. They depend on honest counting exactly like DSR.
- **The change check must allow changes that trade more.**
  - S1's gate requires drawdown ≤ and turnover ≤ baseline, and its proposer only tightens filters. That loop can only make a strategy trade less [Certain — read, S1].
  - S1's "walk_forward_2of3" is really a subperiod check: no refitting [Certain — read].
- **S1's Šidák bar is correct and reusable:** `z = Φ⁻¹(0.95^(1/trials))` with cumulative trials.
- **Neighbourhood rule:** don't hard-code a rule; it's calibrated in the acceptance test with intraday planted edges (V2-D20, D28).
- **v1 subperiod lesson:** at a 3-year window (K = 3) the subperiod gate failed for resolution reasons, not because the edge was missing. Short windows make subperiod checks unreliable, which is one reason they're warnings in v2.

## 3. Sizing (Themis)

- **Ruin formula bug in S2's `mathlab`:** `exp(-theta * D * L)` must be `exp(-theta * D)`. θ is already in R units. With costs charged, the buggy version understates ruin about 2×: at 0.30R cost it reports 5.0% instead of 10.0% [Certain — run].
- **S2's audit example was produced with `cost_r = 0`.** At the stated 0.30R cost the verdict flips to "NOT ENOUGH EVIDENCE" [Certain — run]. Always check that costs were on.
- **S2's formulas assume independent trades.** Verify sizing with a block bootstrap; crypto has volatility clustering.
- **Hard-coded `sr_sd = 1/sqrt(n)`** in S2's DSR assumes every trial was zero-skill. Make it an input.
- **Capital-agnostic:**
  - every money amount is config;
  - strategies and risk work in fractions;
  - sizing rounds to the venue's minimum order and lot step, and skips trades it can't place at the configured size.
  
  One CME Micro Bitcoin contract needs more margin than ~$2k allows, so size on nano/BFF first [Certain — CME margin ≈ 24% of notional].

## 4. Data (Oceanus)

- **Signals from Kraken spot, costs from IBKR futures.** Model funding and futures–spot basis whenever a spot-derived signal is traded on futures.
- **Kraken history:** downloadable OHLCVT files (1 min–1 day, from each pair's first trade, quarterly updates) [Certain — Kraken support].
  - The REST OHLC endpoint only returns a limited recent window [Likely]. Use the files for history.
  - No historical order book [Likely].
- **Kraken trades endpoint:** price, volume, time, aggressor side (`b`/`s`), market/limit flag. Paged with `since`, 1,000 per call. No bulk dump, so forward recording is the cheap way (V2-D26) [Certain — read].
- **Same-time duplicate prints:** one taker order filling several resting orders prints several trades at the same timestamp. Merge them before any order-flow or clustering analysis (see §8).
- **Nautilus Kraken spot bars are emitted only after the next interval's first trade;** the Kraken futures adapter offers only a demo environment [Likely — Nautilus docs, Oct 2026]. Check before relying on either.
- **Point-in-time:** anything non-price gets `available_at`:
  - SEC filings: acceptance time;
  - macro releases: release time;
  - news: `first_seen_utc`.
- **SEC EDGAR:** free, max 10 requests/second, declared User-Agent required [Certain]. Use a generic project name in the User-Agent, never a personal email.
- **Forex Factory:** terms forbid non-interface access and copying calendar data. Don't scrape (V2-D15) [Certain].
- **Binance public archives:** usable for longer research history only; never for costs.
- **The binding limit for slow strategies is how many years BTC has traded,** not the venue. Run the data-sufficiency check first (a true Sharpe of 1.0 needs about 6 years to show; 0.5 needs about 18) [Certain — formula].

## 5. Engine and execution (NautilusTrader + IBKR)

- **Spike criterion (e) is the make-or-break:** can Nautilus's IBKR adapter trade Coinbase perpetual-style nano contracts, and can we read their funding and fees? If not, raise it immediately as an engine problem.
- **IB Gateway** must run on the VPS for IBKR paper/live.
- **Coinbase Derivatives nano contracts trade 24/7 except Fri 17:00–18:00 ET;** CME crypto Sun–Fri ~23h. Model the gaps.
- **Cost model must include:** commission per contract + exchange/regulatory fees (not yet checked) + spread + slippage + funding + basis.
- **Don't book maker-fee savings without measured post-fill markout.** Back-of-queue crypto maker fills lost more to 10-second moves than the spread earned (Bybit/Binance/Hyperliquid study, one author) [Certain — read, S8a].
- **Nautilus publishes its internal bus to Redis streams only** [Likely]. A Kafka bus, when its trigger fires, needs a bridge.
- **Hephaestus vs Nautilus won't match to the cent.** The spike asks for "explainable differences": document each one.
- **Nautilus moves fast** (frequent releases). Pin the version and expect API churn [Likely].

## 6. Experiment store and registry (Mnemosyne)

- **Port the v1 SEARCH/VERIFICATION ontology:** `kind=` explicit at every run call; a sweep uses one hypothesis reused across all points; VERIFICATION runs (cost stress, null draws, walk-forward windows) don't count toward N.
- **Store per-trial daily net returns and trade lists** if V2-D29 is locked. Without them, SPA/StepM, effective-N and CSCV can't be done after the fact.
- **The version registry must be persisted** (S1's `VersionStore` was in-memory only).
- **Live approvals are founder-signed registry entries** (V2-D23).
- **v1 legacy records** (trial_index ≤ 284) have no `kind` and old 10 bps costs. Never backfill or mix them.

## 7. LLM layer and collectors (Prometheus, S-NEWS)

- **LLMs never size, never place orders, never decide verdicts** (V2-D07). Nemesis must not be importable from research code.
- **External text is data, never instructions.** Prompt injection from news/X/web is a real risk. Check cited URLs in code.
- **LLM backtests are contaminated** by training data (Sarkar & Vafa 2024). Forward evidence only. Pin model versions, store every prompt and response with timestamps. Every prompt or model version counts as a trial.
- **`ResearchCard` look-ahead check trusts the self-reported `as_of`.** It can't detect an LLM using knowledge from after the decision date [Certain — read, S1].
- **Frequency = independent sources per event, not copies.** One wire story syndicated 40 times is one source. Cluster first.
- **Grok** is valuable for live X access but can't supply honest *historical* sentiment.

## 8. Order-flow, Hawkes and market-profile ideas (parked, data collected now)

- **Candle-shape "order flow" is not order flow.** Close-location delta (V·(2g − 1)) turns "absorption" and "delta divergence" into pure functions of OHLC [Certain — algebra, S9]. Only trust delta built from aggressor-side trades.
- **Order-flow imbalance mostly moves price at the same time, not later** (Cont, Kukanov & Stoikov 2014) [Likely]. Expect little predictive value even at minutes-to-hours horizons.
- **Cross-venue caveat:** flow is measured on Kraken spot but we trade Coinbase/CME futures, and Kraken is a minority of BTC volume [Likely].
- **Hawkes fits (tick library) read seasonality as clustering:**
  - a rate that swings over the day, with no clustering at all, fit as branching 0.25–0.92;
  - duplicate prints added 0.145.
  
  Use a time-of-day baseline, merge same-time prints, and pick the decay by likelihood. A wrong decay moved branching from 0.55 to 0.15 or 0.75 [Certain — run, S10].
- **Stay above one minute.** Predicting the next seconds of flow is HFT (V2-D22).
- **Market profile needs a measured volume profile from trades,** not a candle-shape estimate (S9's indicator models it with Gaussians).

## 9. Kronos

- **Confirm the checkpoint's training cutoff from the repo** (June 2024 per one review [Likely]). Only data strictly after the cutoff is clean.
- **The paper's +93% RankIC headline averages 10 samples against single-shot baselines.** Report N = 1 vs N = 10 [Likely].
- **Volatility forecasts:** beat EWMA and GARCH(1,1) (both in `arch`) and, for intraday bars, a HAR realised-variance baseline if P-2 is accepted.
- **No conformal-interval layer:** MAPIE's best setup only matched a one-line EWMA band and was much slower [Certain — run, S10].
- **The spec still says Kraken costs and 1h/4h bars.** Use IBKR futures costs; re-check horizons against the intraday track (O-8).

## 10. Source-quality lessons (don't relearn these)

- **S1–S4 are one author** (Arwaz Az). Agreement between them is not corroboration.
- **S3/S4 numbers are internally inconsistent** (CAGR vs total return). S3 routes AI-approved strategies straight to execution (rejected).
- **S8a Daru Finance is one author.** Mostly pre-registered nulls, unreviewed working papers. Good model of honest reporting; one prose sentence mislabels its own percentages.
- **Published anomalies weaken after publication** (McLean & Pontiff 2016) [Likely]. Discount any edge taken from a paper.
- **Backtest rank barely predicts the next window.**
  - Daru's corpus: ≈0.02 persistence.
  - Quantopian's cohort study (Wiecki et al. 2016) [Likely]: the same.
  
  Paper trading is the real filter.
- **"Hedge funds use this" with no evidence, funnels (comment-for-link, courses), win rate without payoff, cost-free results, best-of-variants headlined:** red flags. Judge the claim, not the marketing.
