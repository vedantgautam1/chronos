> **Staleness note (3 Nov 2026) — read before using this spec.** Written 27 Oct, before V2-D24/D27.
> - **Collection only for now** (V2-D24): build the collectors, freeze no trading rules.
> - Crypto is traded via **IBKR crypto futures**, not Kraken (V2-D27). Wherever this spec says "crypto (Kraken)" or "Kraken sub-account", read IBKR futures; sleeves are tracked in the version registry and Nemesis per-sleeve budgets.
> - Insider filings moved to their own parked equity strategy, S-INSIDER (V2-D14).
> - "Matrix refs" point to `claude/comparison-matrix.md` in the claude.ai Project.
> - Where this spec and `docs/v2/CHRONOS_V2.md` disagree, CHRONOS_V2 wins.

# Spec — News & sentiment strategy (v0.1 draft, 27 Oct 2026)

**Status:** Locked V2-D06 (27–28 Oct 2026). Founder decision: pure sentiment trading runs as **its own strategy with a small, capped capital sleeve**, forward-tested, scaled only on evidence. Sources requested: Grok/X, Insider, Forex Factory, live presidential press conferences. Signal idea: sentiment from **how often the same news arrives (frequency)** and **how strong it is (intensity)**. Matrix refs: §8, §19 (L2 sleeve), §20.

## The idea, stated so it can fail
> When the same market-relevant story is reported by a rising number of **independent** sources, with high intensity, the affected asset moves in the story's direction over the next H hours, by more than costs.

**Falsifier:** the frequency × intensity index does not lead returns (it moves with or after price), or the after-cost expectancy is not positive over the pre-registered sample.

## Two strategies, not one
| | S-MACRO (scheduled data surprises) | S-NEWS (unscheduled news + sentiment) |
|---|---|---|
| Inputs | Economic releases: actual vs consensus forecast | Grok/X, news headlines, press-conference transcripts |
| Backtestable? | **Yes** — history of actuals and consensus exists | **No** for Grok/LLM scoring (forward only); **partly** via GDELT history (below) |
| Markets | FX (IBKR), crypto (IBKR futures) | Crypto first, FX second |

S-MACRO can be tested on history before any money is at risk. Keep it separate so its evidence isn't diluted by the forward-only part.

## Source review
| Source | Status | Plan |
|---|---|---|
| **Grok (xAI API)** | Live X posts; pinned model version required | Scheduled queries per asset; store raw answer + cited URLs + model version + timestamp. Treated as data, never instructions |
| **Insider = corporate insider filings (SEC Form 4)** (V2-D14) | Free from SEC EDGAR (10 req/s, declared User-Agent) [Certain] | **Moved to its own backtestable equity strategy, S-INSIDER.** Not part of the S-NEWS index. General news headlines come via RSS / licensed APIs, never full-text scraping |
| **Forex Factory** | Terms: no access except via the interface; calendar data copying prohibited without written consent [Certain] | **Do not scrape (Locked V2-D15).** Actuals from official sources (BLS, BEA, Fed, StatCan, BoC — free); consensus from a licensed vendor. FMP economic calendar (estimate/actual/previous, 10 yrs) listed at $100/month [Likely] — budget problem, vendor Open |
| **Presidential press conferences / speeches** | Official live streams; speeches by federal officials generally not copyrighted [Likely] | Live audio → local Whisper in short chunks → LLM classification. Truth Social posts reach X quickly and are covered via Grok [Likely] |
| **GDELT** | Free global news monitoring, 15-minute updates, article volume + tone [Likely]; raw history back years [Likely] | **Backtest proxy for frequency × tone** before risking money. Crude dictionary tone, so treat as a lower bound |

## Pipeline
1. **Collect** (24/7 on the VPS — a laptop sleeps): every item stored with `first_seen_utc`, `source`, `source_type`, `url`, `headline`, `text_hash`, `raw_payload`. Immutable.
2. **Cluster into events.** Embed headlines and group items about the same underlying event within a time window. **Frequency = number of independent sources per event, not number of copies.** One wire story syndicated 40 times is one source.
3. **Score intensity** per event with a pinned LLM (Grok and Claude, logging disagreement — see below): affected assets, direction, magnitude 0–3, novelty/surprise vs what was already known, confidence. Output is a strict JSON schema validated by code.
4. **Index** per asset per hour: e.g. Σ over active events of direction × magnitude × f(independent-source count, velocity), with exponential decay. The exact formula is frozen before forward testing begins; each variant tried counts as a trial.
5. **Strategy rules** (frozen): entry threshold on the index, holding horizon H, exit rules, max trades per day.
6. **Execution:** deterministic code sizes from the sleeve's risk budget and runs the order through the hard risk guard. The LLM never sets size and never places orders.

## Speed, honestly
Markets react to headlines within seconds; automated news feeds and algos act first [Likely]. A pipeline of audio → transcription → LLM → order will take tens of seconds or more [Guessing]. **Do not compete on being first.** Target the slower part: the build-up of independent coverage and drift over minutes to days. Pre-register H (e.g. 1h, 4h, 24h — each a trial).

## Capital sleeve and scaling rules (decided now)
- Fixed sleeve with a written maximum loss; when hit, the strategy stops and goes back to paper.
- **Evidence needed to scale** (S2 maths, corrected): trades needed n ≈ ((1.645 + 0.84) × σ / E)². With per-trade σ = 1.5R: E = 0.3R needs ~155 independent trades; E = 0.2R needs ~348 [Certain — arithmetic; inputs illustrative]. At a few trades a week that is a year or more. Scale only when the after-cost expectancy interval excludes zero at the honest trial count.
- Count independent events, not trades: several trades on the same event are one bet.

## Order of work
1. **Start collection now** (forward evidence only accumulates with time): Grok queries, headlines, GDELT, press-conference transcripts → store. No trading.
2. **S-MACRO backtest** once a licensed consensus source is chosen.
3. **GDELT backtest** of the frequency × tone index on crypto and FX.
4. Freeze S-NEWS rules → paper → tiny live sleeve.

## Intensity scorer (Leaning, 28 Oct)
During collection, score every clustered event with **both** Grok and Claude (pinned model versions), store both, and log their disagreement. At this volume the cost is a few dollars a month [Likely]. Two scorers on the same events show how noisy the scoring is, and their disagreement may itself be a useful input. At rule-freeze, keep whichever scorer's index actually leads returns, or a frozen local model if it does as well.

## Sleeve and maximum loss — what these mean
- **Sleeve:** the slice of trading capital this strategy may use, held apart from the others. The strategy can never touch more than this.
- **Written maximum loss:** a number fixed **before** trading starts. If the sleeve loses that much, the strategy stops and goes back to paper. No discretion in the moment.
- **Suggested starting shape (Leaning):** sleeve ≤ 10% of total trading capital; maximum loss = 20% of the sleeve; per-event risk sized by the drawdown-budget rule. All in percentages, so they scale with capital.

## Open items (settle while building / before live)
1. Sleeve % and maximum-loss % are configuration; set before going live.
2. Consensus vendor for S-MACRO.
