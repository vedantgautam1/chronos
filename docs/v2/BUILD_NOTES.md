# BUILD NOTES — traps to avoid, by component

Companion to `docs/v2/CHRONOS_V2.md` (read that first). This file is the "things to keep in mind" list: every trap we already found, so a build session doesn't rediscover it the expensive way. **Read the section for the component you're about to build.** Add new traps as you find them (CHRONOS_V2 §14 rule 3).

Tags: [Certain — run] = we ran code and saw it · [Certain — read] = read in code or docs · [Likely] / [Guessing] = not verified. Source IDs (S1…S17) point to `claude/item-analyses*.md` in the claude.ai Project; check scripts for S10 onward are in `docs/v2/research/`.

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
  - **Exception: a repo's own test suite.** `-I` drops the working directory from the import path, so the repo's tests can't import its own package (S18: every agent-kit test module failed to import). Run its documented test command from its root, inside a throwaway venv or folder; use `-I` for our own scripts that read or call it [Certain — run, S18].
- **v2 and v1 share this repo** (V2-D29). Put v2 in its own new package folder; never edit v1 code under `src/chronos/` or `tests/`. CI (`.github/workflows/tests.yml`) currently runs only the v1 suite: add the v2 tests to CI when they exist, and retire the v1 job only with the founder's OK. Watch for import-name clashes with the v1 `chronos` package.
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
- **Raw N over-penalises correlated searches.** In a 20,000-formula noise search, the best |t| was 3.15, below the ≈4.06 expected from 20,000 *independent* tries, because formulas over the same inputs overlap [Certain — run, S10]. Estimating effective N needs stored per-trial return series (now required, V2-D33).
- **iid bootstrap on autocorrelated returns is badly overconfident:** 74% actual coverage for a nominal 95% interval (AR(1), φ = 0.5). The stationary bootstrap with automatic block length gives 92.7% [Certain — run, S10]. Use block methods.
- **Set-level tests (SPA/StepM/MCS) only see what you hand them.** Handing SPA the best 50 of 2,000 noise variants gave p = 0.028 (a false find); all 2,000 gave p = 0.56 [Certain — run, S10]. They depend on honest counting exactly like DSR.
- **The change check must allow changes that trade more.**
  - S1's gate requires drawdown ≤ and turnover ≤ baseline, and its proposer only tightens filters. That loop can only make a strategy trade less [Certain — read, S1].
  - S1's "walk_forward_2of3" is really a subperiod check: no refitting [Certain — read].
- **S1's Šidák bar is correct and reusable:** `z = Φ⁻¹(0.95^(1/trials))` with cumulative trials.
- **Count attempts across related hypotheses, not within a label (V2-D31).** S12's ledger counts per "family", a label the proposer picks. On pure noise with 12 candidates: counted together, 1% false finds; split into the book's natural families, 13%; one per family, 28% [Certain — run, S12 check]. v2 counts per hypothesis and has the same hole. The fix is v1's search-fragmentation screen (`src/chronos/moirai/stages/eligibility.py`, step (f)), reported as a warning with DSR at the union N.
  - **Known-answer test to write:** two sibling hypotheses on adjacent grids of the same strategy class → warning present, with the sibling ids and DSR at the union N. v1's `test_eligibility_fragmentation_screen_union_n` (`tests/moirai/test_free_stages.py`) and probe G6a (`tests/moirai/test_plateau.py`) are the templates.
- **Honest counting alone doesn't stop "trade less beats a losing baseline" (V2-D32).** With costs and no gross edge, net P&L is minus cost × trades, so any filter that trades less beats the baseline, repeatably. In S12's own data, 20% of best-of-12 winners cleared even the Šidák-corrected bar [Certain — run]. A paired-test-only change check at 2× costs accepted a change in 40% of no-edge worlds; requiring the candidate's own net > 0 after 2× costs cut that to 0%, at the price of about a quarter of genuine improvements (88% → 67%) [Certain — run, S12 check].
  - **Known-answer tests to write:** (1) live version with zero gross edge and a net loss at 2× costs; candidate trades half as often with zero gross edge → change check REJECTS and opens a retirement review. (2) Candidate with a real gross edge that still clears 2× costs → ACCEPT.
- **Mining "lessons" from our own history needs a minimum n per side and a correction for every group examined.** Uncorrected, a subgroup lesson appeared in 30% of no-structure worlds; with ≥ 30 trades per side and Bonferroni over the groups examined, 4.3% over 300 worlds (95% CI 2.5–7.3%) [Certain — run, S11 check]. A lesson is an association: turning it into a filter is a new, counted trial.
- **Cheap look-ahead probe (S11's `causality_ok`):** nudge a future close up and down; no earlier entry may change. Probabilistic (it only checks around sampled trades), but it caught an injected next-bar peek in 30 of 30 cases [Certain — run, S12 rerun]. Worth adding to the v2 strategy test kit beside the structural no-look-ahead tests.
- **Sealed holdouts touched once: enforce it on dates, persistently.**
  - S13's `SealedTest` is an in-memory set keyed by the dataset's file hash. Its ladder makes a fresh one on every call unless one is passed in, so calling it twice gave two looks at one dataset; and a dataset one day longer has a new hash but 100% of the same sealed days, so a second look was allowed [Certain — run, S13 check K2].
  - v1's `src/chronos/oceanus/seal.py` has the opposite gap: it logs every look with a reason but doesn't limit them [Certain — read].
  - **V2-D38:** for crypto, the seal starts **1 Apr 2026 00:00 UTC** and grows with time; research tools must refuse any query that reaches past 31 Mar 2026 for BTC/ETH. Confirm rule: ≥ 200 sealed trades, net after 2× costs > 0, adverse-funding run > 0 where funding applies; no significance bar. Recorded Kraken trades and news data start after the seal date: give each its own sealed final block before research on it starts.
  - v2 (**V2-D34, Locked**): record every sealed look in Mnemosyne keyed by **instrument + date range + hypothesis lineage** (the hypothesis plus its V2-D31 siblings). A later look whose range overlaps an earlier one for the same lineage is refused. Enforce it in the database, not in a Python object, and give screens and research tools no way to read sealed dates (the MCP server included).
  - What re-looks cost: an idea with no real effect, looked at on four overlapping windows (S15's loop: 43–56% overlap), was confirmed at least once **16%** of the time vs 5% for one look [Certain — run, K2e].
- **"Positive at 1× and 2× costs": with every cost component ≥ 0, the 1× check can never change a verdict** (net at 2× ≤ net at 1×). S13’s gate ablation showed it [Certain — arithmetic + run]. Funding and basis can be income, so doubling *all* costs can make the 2× run easier than 1×. **V2-D35 (Locked):** the 2× run doubles commission, fees, spread and slippage only; funding and basis stay at modelled values in both runs; where there is funding, an adverse-funding run must also be positive (**V2-D39:** funding against the position every hour held, at the 95th percentile of the contract's own |hourly funding| from launch to 1 Apr 2026; applied to every backtest year). Keep each cost component as a separate column so the stress can be applied per component.
- **Freeze and hash the edge-check configuration before a run; store the hash with the result.** Choosing the evaluation contract after seeing results (best of 64) raised false accepts of a useless idea from 0.24% to 12.6% and of a decoy from 1.7% to 25% [Certain — run, S13 rerun].
- **Every edge-check criterion needs a fixture it alone catches** (acceptance test, step 5), or a written note that it is deliberate defence in depth. In S13's ablation six of eight gate checks changed no decision, and two of them (net > 0 at 1×; t > 0) can't by construction [Certain — run + arithmetic].
- **Report the break-even cost multiple** (gross edge ÷ round-trip cost) for every strategy: how wrong the cost model may be before the edge is gone. In S16's worlds, true filters had a median 2.3× and the decoy 1.3× [Certain — S16 rerun].
- **Two look-ahead tests for the strategy kit, from freqtrade (S20; method only, its code is GPL-3.0):**
  1. *Slice test:* run the strategy once on the full history, then again on the history cut off just after each signal; every indicator value and signal at that bar must match. Deterministic at every signal, unlike S11's sampled nudge probe. Matters most for vectorised screening code (VectorBT), where a whole-column `.mean()` or `shift(-1)` leaks silently.
  2. *Warm-up test:* recompute indicators with different amounts of history before the same bar; values must agree within a stated tolerance. Recursive indicators (EMA, ATR) depend on how much history was loaded, so backtest and live can disagree.
  freqtrade's own tests for both pass (27/27) but use a blatant 10-bar leak [Certain — run, S20 F2]. Our fixtures should include a one-bar leak and a whole-series statistic.
- **Look-ahead is invisible to every statistical check.** In S16's ladder a one-bar peek failed the causality probe 100% of the time, the sealed look only 30%, the cost stress 14%, the gate 2% [Certain — S16 rerun]. Keep the probe (above) as a separate test.
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
- **Kraken trades endpoint:** price, volume, time, aggressor side (`b`/`s`), market/limit flag. Paged with `since`, 1,000 per call [Certain — read]. **Correction (S20, 5 Nov):** Kraken *does* publish bulk trade history: quarterly downloadable "time and sales" files per pair [Certain — freqtrade docs, citing Kraken support]. They appear to carry only timestamp, price and volume, **no aggressor side** [Likely — freqtrade parses three columns; check a real file]. So years of unsigned trades can be loaded now (volume profiles, activity/Hawkes work); the aggressor side still needs the API, which is why forward recording (V2-D26) stays.
- **Never deduplicate trades on timestamp.** One taker order filling several resting orders prints several real trades at the same time. freqtrade's Kraken CSV importer drops every trade sharing a `(timestamp, id)` with an earlier one, and its CSV rows have no id: on synthetic data it lost every same-timestamp trade (48–54% of volume in the test) [Certain — run, S20 F1]. Keep every print; if prints are merged (§8), merge them explicitly and keep a count. Store timestamps at the source's full resolution (freqtrade truncates to milliseconds).
- **FRED through OpenBB has no vintages.** OpenBB's FRED fetcher deletes FRED's `realtime_start`/`realtime_end` and returns the latest revised values [Certain — read, S19]. Backtesting on them is look-ahead (revisions weren't known at release). For S-MACRO, store each release's first value at release time ourselves; if history is needed, FRED's own vintage data (ALFRED, `realtime_*` parameters) [Likely] is the source. OpenBB's BLS calendar gives scheduled release times (ET), usable for `available_at`, but no actual values [Certain — read].
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
- **Nautilus's risk engine is a useful first line, not the last one.** It has ACTIVE / REDUCING / HALTED trading states and a per-order notional cap, but also a runtime setter for that cap and a bypass flag [Certain — Nautilus risk API docs], and it shares the bus and cache with the strategies [Likely — in-process]. That is S16's "engine in the strategy's process" case: V2-D36 uses it as layer 1 only.
- **Coinbase US perpetual-style contracts accrue funding hourly and settle it twice a day; one nano BTC contract is 0.01 BTC; they are five-year contracts** [Certain — Coinbase's explainer]. Launched around July 2025 [Likely], so their own funding history before the 1 Apr 2026 seal is short. Pull it in the spike (O-4) to compute V2-D39's level; if it can't be pulled, stop and flag it.
- **Check IBKR's broker-side order precautions during the spike.** TWS/IB Gateway have precautionary settings (size limit, total value limit, price-percentage cap) and an API setting "Bypass Order Precautions for API orders" [Certain — IBKR docs]. Whether they reject API orders for Coinbase/CME crypto futures through IB Gateway is unverified [Guessing]. They are V2-D36 layer 2; spike criterion (f) checks them.

## 6. Experiment store and registry (Mnemosyne)

- **Port the v1 SEARCH/VERIFICATION ontology:** `kind=` explicit at every run call; a sweep uses one hypothesis reused across all points; VERIFICATION runs (cost stress, null draws, walk-forward windows) don't count toward N.
- **Store every counted trial's daily net returns and trade list (V2-D33, Locked).** Without them, SPA/StepM, effective-N and CSCV/PBO can't be done after the fact. Keep them on one calendar per dataset. Size: ~32 MB per 5,000 variants × 800 days [Certain — arithmetic].
- **Ids from content, not counters** (S12 ledger, run 3 Nov):
  - version id = hash of the parameters + the code coordinate, so any edit is a new version;
  - experiment id = hash of the run spec (base, candidate, dataset hash, window, costs, seed), leaving out free text. An exact repeat is recognised and doesn't inflate N; a reworded repeat is caught too.
  - Trap: a repeat filed under a different family keeps its first family. Count across families anyway (V2-D31).
- **Code coordinate = git commit + `uv.lock` hash + engine version.** S12 hashed one engine file only, so a change to its statistics code showed up as MISMATCH, not CODE_CHANGED, and created no new version ids [Certain — read].
- **Data coordinate = snapshot hash of the exact input.** In S12's test, editing one price left every metric unchanged in 120 of 120 cases; only the data hash noticed [Certain — run].
- **Append-only in the database, not just in the app:** revoke UPDATE/DELETE (or use triggers) on result tables, store a hash per result row, and add an `audit()` that recomputes them. In S12's test the triggers blocked 8 of 8 destructive statements; without them 6 of 8 went through, and `audit()` still caught an edited number [Certain — run]. Not tamper-proof against someone with database access; a hash chain with its head stored elsewhere is the next step.
- **Comparison guard:** two results may be compared only if dataset, window, costs, seed and baseline all match (S12 `compare()`).
- **Reproduce on demand:** re-run a stored spec and report REPRODUCED / DATA_CHANGED / CODE_CHANGED / MISMATCH / NO_RESULT (S12 `reproduce()`).
- **The version registry must be persisted** (S1's `VersionStore` was in-memory only).
- **Live approvals are founder-signed registry entries** (V2-D23).
- **Promotion evidence is fetched by id, never handed in.** S16's promotion computes its checklist itself, but from objects the caller passes. A hand-built ladder record took a decoy (whose real ladder failed) to LIVE; a hand-typed monitor calibration passed; after the real audit log was tampered with, a freshly built log passed the "chain intact" item [Certain — run, S16 check K1]. In v2, edge-check, paper and monitor-calibration results are written by the code that produced them, stored append-only in Mnemosyne with a content hash, and the founder's approval command looks them up itself; the audit chain is verified against an anchor every time.
- **Every safety-state store needs the same protection as the registry.** In S16 the registry table is append-only by trigger but the halt table isn't: one INSERT or DELETE un-halted the system, orders filled again, and the audit chain still verified with no RESUME in it [Certain — run, K3c]. Same for v2's kill switch ("CLI command + config flag", V2-D23): see §11.
- **v1 legacy records** (trial_index ≤ 284) have no `kind` and old 10 bps costs. Never backfill or mix them.
- **Paper/live trade journal (at L3, not now):** record each trade with the conditions known at entry (strategy version, signal values, volatility state, session) kept apart from outcome labels. Every field used to look trades up must be computable before the outcome; reject unknown fields at the door (S11 episode schema). Feeds failure diagnosis and backtest-vs-live comparison.

## 7. LLM layer and collectors (Prometheus, S-NEWS)

- **LLMs never size, never place orders, never decide verdicts** (V2-D07). Nemesis must not be importable from research code.
- **External text is data, never instructions.** Prompt injection from news/X/web is a real risk. Check cited URLs in code.
- **LLM backtests are contaminated** by training data (Sarkar & Vafa 2024). Forward evidence only. Pin model versions, store every prompt and response with timestamps. Every prompt or model version counts as a trial.
- **`ResearchCard` look-ahead check trusts the self-reported `as_of`.** It can't detect an LLM using knowledge from after the decision date [Certain — read, S1].
- **The research MCP server is the tool broker (S14 design, run).** Deny by default; no order tools; no tool that sets or edits the attempt count; no raw SQL; no access to sealed date ranges; no role reviews its own work. In S14's test, 11 forbidden actions: 0 succeeded with broker + database rules, 3 with database rules only, 10 with neither [Certain — run].
- **Attempts come from Mnemosyne, never from the agent; the research budget is declared on the card before work starts.** S14 uses max(declared budget, ledger count): a budget declared too low leaves the earliest ideas facing a lower bar [Certain — read].
- **Diff the built rules against the card's declared change before evaluating.** Without S14's diff check, 186 ideas were accepted instead of 111; 75 carried an unrequested change and 11 credited a useless idea with a hidden change's gain [Certain — run].
- **Replication on another instrument or period is a counted VERIFICATION step, and weaker than S14's.** S14 replicates on fresh draws from the same synthetic generator (the easiest case); it cost 38% of true accepts there. Real replication sets differ in kind, so state its expected power, don't assume it.
- **Reference values used to detect tampering must live outside the agent's process** (S14's tamper detection relied on frozen values in the same process, untouched by the attack) [Certain — read].
- **"No diagnosis, no hypothesis"** for the failure-diagnosis agent: a diagnosis must pass a corrected test on development data before it may name a change. In S15's no-edge worlds this cut experiments from 12 to 0.14 per world [Certain — S15 rerun].
- **Frequency = independent sources per event, not copies.** One wire story syndicated 40 times is one source. Cluster first.
- **Grok** is valuable for live X access but can't supply honest *historical* sentiment.
- **An LLM must not pick winners from backtest results, and never on the test block.** RD-Agent's quant loop asks an LLM, every iteration, whether the new factor should "replace the best result", reading backtest metrics from its *test* segment (2017–2020 by default) [Certain — read, S22]. That is an LLM verdict (V2-D07), an uncounted search (V2-D03) and a reused test block (V2-D34) in one step. For Prometheus: agents propose and write code; Moirai's deterministic checks decide; sealed data stays sealed.
- **Paid-API clients (Grok, Claude, any data vendor): reserve the budget before the first paid call.** Pattern from S18's `skylit-agent-kit` (checked offline only): a free account/balance check first; the whole run's planned cost compared with a per-run cap before any paid request; one fixed destination host; redirects refused; response size capped; no automatic retries or budget increases; the key read from the OS keychain or an owner-only file, never from chat or a repo file. With no key, live mode refused with 0 network attempts [Certain — run, S18 C3]. Keeps collectors inside the V2-D13 budget when a loop or a bad parameter would otherwise spend all month's credits in a night.

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
- **S11–S12 (Arwaz Az, "Self-Improving AI Trading Agent" Parts 1–2) are the same author as S1–S4.** Their code is honest and reproduces to the digit (62/62 tests; every figure reruns). But the synthetic worlds are built so the tool's inputs are the planted mechanism (memory's session key is exactly the planted session effect), which flatters the tool. Ask of any synthetic demo: would it still work if you didn't know the mechanism? (S11 check: a fifth to a half of the benefit disappeared.)
- **S8a Daru Finance is one author.** Mostly pre-registered nulls, unreviewed working papers. Good model of honest reporting; one prose sentence mislabels its own percentages.
- **Published anomalies weaken after publication** (McLean & Pontiff 2016) [Likely]. Discount any edge taken from a paper.
- **Backtest rank barely predicts the next window.**
  - Daru's corpus: ≈0.02 persistence.
  - Quantopian's cohort study (Wiecki et al. 2016) [Likely]: the same.
  
  Paper trading is the real filter.
- **S13–S17 (the same series, Parts 3–7) are the same author again.** Code honest and reproducible (157/157 tests; every Part 3–7 figure reproduced (0 differences in 38,480 values)). His null worlds make every false candidate lose money, so "0 false passes" there tests only the profit requirement; his thresholds are tuned to his own planted answer. His own lists of what he did *not* test (positive drift without skill, gradual decay, real brokers) are the most useful part to read.
- **"Hedge funds use this" with no evidence, funnels (comment-for-link, courses), win rate without payoff, cost-free results, best-of-variants headlined:** red flags. Judge the claim, not the marketing.

## 11. Guard, kill switch and monitoring (Nemesis, Argus)

Mostly from S16–S17 (Arwaz Az Parts 6–7, code run 5 Nov; checks in `docs/v2/research/s13-s17-deep-pass/`). Design locked 5 Nov as **V2-D36** (Nemesis in three layers) and **V2-D37** (edge-decay alarm); the numbers were set by **V2-D40** (limits = exactly Themis's approved contracts; account ceiling 2× equity notional in paper; false-alarm budget 10% per strategy-year). Changing them is a protected change (V2-D11).

- **Put the boundary around broker access, not just around the risk check.** S16 runs its risk engine in a separate process and reports 0 of 11 attacks succeeding, but all 11 target the engine. From the strategy's process, calling the executor's broker handle directly filled a 20× order (not in the audit log; chain still verifies), and swapping the executor's risk handle for a yes-object did too [Certain — run, K3a/b]. Whatever holds the IBKR connection must be unreachable from strategy code, or a separate watcher must see the broker's own positions. V2-D36 does the second: a watchdog with its own IBKR connection.
- **Fail closed.** When S16's risk process was killed, the next order raised an exception and nothing filled [Certain — run, K3d]. Nemesis down, unreachable or slow = reject.
- **The kill switch must be latched and its state protected.** Anyone (or any automation) may set it; only a logged founder action clears it; reduce-only exits always pass. v2's kill switch is "a CLI command + config flag" (V2-D23): a flag file that any process can edit is S16's halt-table hole (one SQL statement un-halted the system, invisibly to the audit chain) [Certain — run, K3c]. Write set/clear events to the append-only audit log and have Nemesis refuse to start, or stay halted, if the flag and the log disagree.
- **Limit headroom decides which bugs you catch.** S16's order limit is 5× equity for a planned 3×, so only size bugs above 1.67× were blocked. ×1.25–×1.6 bugs went straight through: median drawdown 17% → 19–22%, the 30% kill fired in 7–16% of healthy worlds instead of 5%, and median final equity *rose* (1.96 → 2.10–2.27) because the edge was healthy, so nobody would investigate [Certain — run, K3e]. Set per-order and position limits close to Themis's approved size and check intended-vs-sent size on every order (V2-D36).
- **The V2-D36 watchdog runs under its own OS user** with its own credentials, so strategy code can't kill it or edit its config; a process on the same machine and user is only an accident barrier (S16's own caveat). It reads positions and P&L from IBKR, never from the strategy. IB Gateway accepts several API clients with different client IDs [Likely — check in spike (f)].
- **Block, don't clip** an oversize order: clipping hides the bug (S16 design).
- **Self-test before every promotion:** fire a battery of known-bad orders (NaN, negative, oversize, fat-finger, stale, unknown side, duplicate, entry after kill) at a fresh guard with the live limits; all must be refused and one good order accepted (S16 `selftest()`).
- **Calibrate the drawdown kill to healthy drawdowns, then size to it.** At 3× leverage in S16's worlds, a 10% kill ended 91% of healthy runs; 30% ended 5% [Certain — S16 rerun]. Read the healthy drawdown distribution at the approved size; set the kill above its 90th–95th percentile; if that loss is unaffordable, cut size (consistent with V2-D08: drawdown sets size).
- **An edge-decay monitor is a smoke detector, not a sprinkler.** Tuned to 5% false alarms, S16–S17's CUSUM needed a median ~370–420 days (≈ 190–230 trades) to notice a dead edge, and missed about a third within 700 days [Certain — run]. Limits protect; the monitor only says "look". State its delay in trades: a strategy that trades several times a day reaches that count much sooner [Guessing — depends on trade rate and per-trade noise].
- **V2-D37 (Locked) sets the alarm's slack this way:** break-even reference k = ½ × round-trip cost ÷ per-trade sd; paper-period reference k = ½ × (paper mean + round-trip cost) ÷ sd; h from the false-alarm budget (V2-D40: 10% per strategy-year, 5% per reference), calibrated on block-bootstrapped healthy streams of the strategy's own trades.
- **Set the CUSUM slack from the shift you want to detect** (about half of it, in standard deviations). With S17's k = 0.10 sd, a break-even monitor ("has it stopped making money?") found 30% of dead edges; with k = 0.065 (half of a 4 bps drop on a 30 bps sd) it found 56.5%, at a 4.5% false-alarm rate, close to the shadow-reference monitor's 61% [Certain — run, K4]. The book's "I did not investigate why" is this.
- **The monitor's reference mean is its weak point** (S17 says so): a lucky or unlucky paper period makes it too sensitive or blind. The break-even reference needs only the spread, not the mean.
- **Write the false-alarm budget before calibrating.** S16–S17's worked examples passed their promotion checklist with a 10% budget after the monitors had measured 8% and 6% against a 5% target; the PDFs don’t mention it (one script comment does) [Certain — read + run]. Fix the budget first, then calibrate (V2-D25 rule 2).
- **Hash-chain the audit log and anchor its head outside the system** at every promotion and at the end of every trading day (a git commit, an email to the founder). In S16's test the chain alone caught edits, deletions and changed event types but not a full rewrite or a truncated tail; the anchor caught both [Certain — run].
- **Automation may only reduce risk** (halt, flatten, roll back to a version the founder approved earlier, never to one retired as faulty); anything that adds risk needs the founder (consistent with V2-D07, V2-D11). The executor re-reads which version is live on every order, so a rollback takes effect on the next order; a config-drift check at start refuses parameters that don't match the approved version (S16 design).
- **Two code paths, one test.** If live uses a full path (registry + executor + audit) and experiments a light one, a test must show both give the same equity curve (S17).
