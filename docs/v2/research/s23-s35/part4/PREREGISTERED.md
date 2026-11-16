# S23–S35, Part 4 — pre-registered tests: the five order-flow tools (S23–S27)

Written 2026-11-16 around 00:50 UTC; the commit time is the record. Committed and pushed **before any test below runs**.

## What was done before this file (setup only)

- Shallow clones.
- Reading code to decide what to test. Predictions from reading are marked **(read)**; they still have to run.
- No installs and no builds yet.

## Pinned versions

| Item | Repo | Commit | Licence | What it is |
|---|---|---|---|---|
| S23 | flowsurface-rs/flowsurface | `9a7497d` (15 Nov 2026) | GPL-3.0 | Rust desktop charting app (iced). Live feeds from Binance, Bybit, Hyperliquid, OKX, MEXC. |
| S24 | Elenchev/order-book-heatmap | `cc26b5a` (9 Mar 2021) | BSD-2 | Browser order-book heatmap (JS, d3) on Binance WebSockets. |
| S25 | gbzenobi/CSharp-NT8-OrderFlowKit | `3be4556` (1 Mar 2022) | **none stated** | NinjaTrader 8 indicators (C#, Windows). |
| S26 | murtazayusuf/OrderflowChart | `9f54638` (1 Nov 2026) | Apache-2.0 | Python/Plotly footprint charts; `from_trades()` builds them from a trade tape. |
| S27 | Azhagesan-dev/OrderFlowMap | `69adb15` (17 Apr 2026) | MIT | Single-file browser Bookmap-style tool. Simulated NIFTY data, or live Indian-exchange data via OpenAlgo. |

**Context:**
- Order-flow ideas are parked (S-ORDERFLOW thesis, BUILD_NOTES §8). The only thing we collect now is Kraken trades with the aggressor side (V2-D26).
- Order-book and sub-minute strategies are out of scope (V2-D22).

So the question for each tool is whether it can **correctly** turn trades into footprints, profiles and delta for research and review, and what we must not copy.

**Data:** all synthetic, with seeds in the scripts. Kraken and Binance aren't reachable from here.

**Licences:**
- S25 has no licence: nothing from it is copied, and its logic is described, not ported.
- S23 is GPL: methods only.

## S23 — flowsurface

| Id | Test | Pass rule |
|---|---|---|
| **W1** | `cargo test` on the workspace library crates (data, exchange, indicator-engine). The repo pins Rust 1.95.0; if that toolchain can't be downloaded here, the installed stable is used and that is recorded. | PASS if all pass. |
| **W2** | `cargo build --release` of the app (no GUI run) | Report: builds or not, time, missing system libraries. |
| **W3** | Footprint known answer. A small test crate calls its `data`/`exchange` types with synthetic trades: bin edges, both sides, a trade exactly on a candle boundary. | PASS if (a) price bins follow its stated rule (nearest step, ties away from zero), (b) buy/sell sums are exact, (c) time buckets are [start, end). If the types aren't constructible from outside the crate, report "not run" with the reason. |
| **W4** | Data sources (read) | Report whether any venue is Kraken, Coinbase or IBKR, and what historical backfill needs. |

## S24 — order-book-heatmap

| Id | Test | Pass rule |
|---|---|---|
| **H1** | `npm ci` and `npm audit` | Report vulnerability counts by severity. `npm test` is `echo "Error: only unlucky people need tests" && exit 1` **(read)**: no tests. |
| **H2** | `Tick.js` string→tick conversion on 10,000 random prices at tick sizes 0.01 and 0.00001 | PASS if every round trip is exact. |
| **H3** | Book sync with a **missed** diff update. Snapshot `lastUpdateId` = 100; diffs U..u = 101–105, then 110–115 (106–109 missing), through a mock feed (no network). | PASS if it detects the gap (resync, error or flag). FAIL if it applies 110–115 silently. |

## S25 — CSharp-NT8-OrderFlowKit

| Id | Test | Pass rule |
|---|---|---|
| **K1** | Build or run | Report. **(read)** It can't be built or run here: it needs NinjaTrader 8's proprietary Windows assemblies. |
| **K2** | Aggressor rule (read, `AddOns/SE.cs`) | Report the rule. **(read)** Quote rule at the trade's time: price ≥ ask → buy, ≤ bid → sell; trades strictly inside the spread count in total volume but in neither side, so bid + ask ≠ total and delta ignores them. |
| **K3** | Licence | None stated → nothing may be copied (repo rule). |

## S26 — OrderflowChart

| Id | Test | Pass rule |
|---|---|---|
| **C1** | `pytest tests` from the repo root | PASS if all pass. |
| **C2** | `OrderFlowChart.from_trades` on a synthetic tape with known sides, 5-minute candles, tick 0.5 | PASS if all of these are exact: (a) a trade exactly at a candle boundary goes to the **new** candle ([start, end)); (b) each trade lands in the price level the docs/code state (rule recorded: floor or nearest); (c) per-level bid/ask sums, candle delta = ask − bid, cumulative delta; (d) candle OHLC = first/max/min/last trade, same-timestamp trades kept in input order; (e) trade count preserved (no same-timestamp dedup, S20's trap). |
| **C3** | Diagonal imbalance on a hand-built candle | PASS if it equals the formula in its docs/code. |
| **C4** | Scale: 86,400 one-second trades | Report the build and figure times. |

## S27 — OrderFlowMap

| Id | Test | Pass rule |
|---|---|---|
| **O1** | Load `index.html` in headless Chromium with all network blocked | PASS if the chart renders. **(read)** Prediction: FAIL. Despite "zero-dependency", it loads `lightweight-charts@5.0.9` from cdn.jsdelivr.net. For O2/O3 the same pinned version is served locally from npm. |
| **O2** | Live-mode trade inference. Call its own `processLiveData()` in the page with snapshots built from a synthetic tape of 5,000 trades with true sides (buys at the ask, sells at the bid, random walk mid). Two snapshot cadences: after every trade, and after every 5 trades. | PASS if ≥ 95% of volume is signed correctly at the every-trade cadence (good enough to stand in for aggressor data). Also report the every-5 result and the CVD error. **(read)** Prediction: FAIL. It infers side by the tick rule from last-price changes and lumps all volume between snapshots into one trade. Caveat: the accuracy depends on my synthetic tape and isn't an estimate for real markets. |
| **O3** | Simulate mode: its CVD vs the sum of its own signed simulated trades | PASS if exact. |

## What would change the conclusions

- If any tool computes footprint/delta/profile **exactly** from aggressor-side trades (C2, W3), it's a candidate viewer for our Kraken trades when S-ORDERFLOW is unparked. Library entry only: no build-order change while it's parked.
- A tool that infers side (O2) or needs order-book data (S24, S27 heatmaps) doesn't fit our data and is rejected, with its traps recorded.
