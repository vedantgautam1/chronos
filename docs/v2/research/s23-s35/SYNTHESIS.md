# S23–S35 — synthesis of the last repo batch before building

Thirteen items (fourteen repos with both Zipline versions, plus ML4T's libraries), tested in four parts, 5–16 Nov 2026. Each part's rules were committed before it ran:
- Part 1: `part1/PREREGISTERED.md`, results in `part1/RESULTS.md`;
- Part 2: `part2/PREREGISTERED.md`, results in `part2/RESULTS.md`;
- Part 3: `part3/PREREGISTERED.md`, results in `part3/RESULTS.md`;
- Part 4: `part4/PREREGISTERED.md`, results in `part4/RESULTS.md`.

**Bottom line:**
- Nothing in this batch replaces anything in master doc §9 steps 2–5 or contradicts a locked decision.
- No engine, venue or data-source switch.
- No new proposal.
- What it changes is **how we build and test**: the notes below are already in `BUILD_NOTES.md`.

## Verdicts

| Item | Verdict | Why, in one line |
|---|---|---|
| S32 VectorBT | **Keep** as the screening engine (Leaning, now tested) | Exact maths and fast enough for counted sweeps; five optimistic defaults fixed by one wrapper |
| S31 quantstats | **Adopt** for reports and cross-checks | Exact formulas; always pass `periods` (252-day default) |
| S30 pysystemtrade | **Reference** | Sizing and back-adjustment exact → Themis known-answer tests; daily-only, no funding, limits clip, GPL |
| S28 Zipline / zipline-reloaded | **Reference** | Original dead; reloaded correct on fills but 24/7 needs three workarounds; no live path |
| S29 RQAlpha | **Reject** | Non-commercial licence; Chinese data over plain HTTP; backtest-only partial fills |
| S33 ML for Trading (book + libraries) | **Reference / test oracle** | ml4t-backtest passes every fill check (funding, multiplier, gap stops, 24/7) → third opinion for the spike; ml4t-live trades only US stocks via IBKR; ml4t-diagnostic useful with caveats; the book's own crypto case study lost 44.8%/yr on its holdout |
| S34 FinRL | **Reject** | Same-bar fills, survivorship in cleaning, cross-ticker fills; RL out of scope |
| S35 gs-quant | **Reject** as a tool | Needs a GS account; date-level look-ahead hole; costs ignored offline |
| S26 OrderflowChart | **Library** (viewer for when S-ORDERFLOW unparks) | Exact footprints from aggressor-side trades, fast |
| S23 flowsurface | **Reference** | Correct fixed-point footprints, but GPL, none of our venues |
| S24 order-book-heatmap | **Reject** | Silent gaps in the book; sizes zeroed; 13 known vulnerabilities |
| S25 NT8 OrderFlowKit | **Reject** | NinjaTrader/Windows, no licence; quote rule drops inside-spread trades |
| S27 OrderFlowMap | **Reject** | Live "order flow" is a tick-rule guess (79% at best, coin flip at 5-trade snapshots); needs a CDN |

## What changes for the build

**Step 2 (skeleton + stats port):**
- Carver's sizing formula becomes a Themis known-answer test, with the annualisation trap: /16 is for business days only.
- ml4t-diagnostic and quantstats become second opinions in the known-answer tests. Label the DSR form. Use RAS only on standardised returns.
- Outside p-values get our mid-rank and +1 rules.
- `TZ=UTC` everywhere.

**Step 3 (Nautilus spike):**
- Run the five fill tests on Nautilus **and** on ml4t-backtest as a third opinion. List the stop before the target.
- Test runs that start and end on a weekend, and across Coinbase's Friday pause.

**Step 4 (collection):**
- The Kraken recorder detects and logs gaps.
- Sizes are stored at their own precision.
- Availability is checked at timestamp level, never date level.
- Never forward- or back-fill a stacked multi-asset frame.
- HTTPS or checksums for downloads; archives unpacked with a filter.

**Step 5 (acceptance test):**
- The VectorBT wrapper's five fixes.
- No business-day resampling of 24/7 data.
- Point-in-time universes.

**Nemesis:**
- Block, don't clip (pysystemtrade and RQAlpha both clip).
- A startup reconciliation mismatch halts.
- Limits from config, never library defaults.

## Evidence worth quoting

The ML for Trading 3rd edition crypto-perps case study:
- best of 2,807 candidates, validation Sharpe 1.67, naive PSR p = 0.005;
- deflated Sharpe at honest K negative;
- holdout Sharpe −0.83, CAGR −44.8%, drawdown −82%.

It's an independent author's pipeline. It supports V2-D03 (count every trial) and V2-D34/V2-D38 (sealed block) better than any of our own planted-answer tests can.

## Weakest parts of this batch

- **No real Kraken trade or Coinbase funding data was available here.** Every order-flow and funding check used synthetic data, so the O2 accuracy numbers describe my simulator, not a market.
- **The pre-registration timestamps were wrong twice by a few minutes.** Each was still committed before its tests.
- **Several harness errors were found and fixed after first runs.** Each is recorded with its first-run output.
- **The RL test (F6) only covered a short training budget.**
- **Nautilus itself hasn't been tested yet.** This batch only tells us what to compare it against.
