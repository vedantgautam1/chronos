# S23–S35, Part 4 — results: the five order-flow tools (S23–S27)

Run 16 Nov 2026 against `PREREGISTERED.md` (commit `f1ae09f`, 00:49 UTC, pushed before any test ran). All data synthetic (seeds in the scripts). Machine: 2 CPUs; Python 3.12; Node 22; Rust 1.97 stable (see deviations).

## Summary

| Test | Result | One line |
|---|---|---|
| **W1** flowsurface library tests | **PASS** | 85 pass, 0 fail, 2 ignored: 16 in `data`, 69 in the indicator engine, 0 in `exchange`. **None of them tests footprint or profile aggregation.** |
| **W2** app build | report | First attempt failed after 345 s: the audio dependency needs the ALSA system library (`libasound2-dev`). With it installed, the release build finished in 4 min 7 s (48 MB binary). The GUI wasn't run (no display here). |
| **W3** footprint known answer | **PASS** | Bins = nearest 0.5 step, **ties away from zero** (100.25 → 100.5, 99.75 → 100.0), as its code says. Buy/sell sums exact (fixed-point integers). Candle time buckets [start, end). |
| **W4** data sources (read) | report | Live: Binance, Bybit, Hyperliquid, OKX, MEXC. **No Kraken, Coinbase or IBKR.** Historical trades: Binance only, or its separate `flowsurface-server` collector. The indicator catalog downloads code from api.flowsurface.com and compiles it locally (checksum-verified). |
| **H1** order-book-heatmap deps | report | `npm audit`: **13 vulnerabilities: 1 critical (webpack), 9 high** (axios, ws, d3, follow-redirects…), 3 moderate. Installed with `--ignore-scripts`. No tests ("only unlucky people need tests"). |
| **H2** price string → tick | **PASS** | 0 mismatches in 10,000 at tick 0.01 and 10,000 at 0.00001. |
| **H3** missed book update | **FAIL** (predicted) | Diffs 110–115 applied after 101–105 with 106–109 missing: **no error, no flag, no resync**. |
| **K1** NT8 kit build | report | Can't be built or run here: needs NinjaTrader 8's proprietary Windows assemblies. |
| **K2** NT8 aggressor rule (read) | report | Quote rule at trade time (`AddOns/SE.cs`): price ≥ ask → buy, ≤ bid → sell. **Trades inside the spread count in total but in neither side**, so bid + ask ≠ total and delta ignores them. |
| **K3** licence | report | None stated. Nothing copied; logic described only. |
| **C1** OrderflowChart suite | **PASS** | 17 of 17. |
| **C2** `from_trades` | **PASS** | All exact: [start, end) candles (a trade at exactly 00:05:00 opened the second candle); per-level bid/ask; delta −3/−10; cumulative −3/−13; OHLC; 45 of 45 volume kept, including two identical same-time trades. Price levels: nearest tick via NumPy, so **ties go to the even level** (100.25 → 100.0, 100.75 → 101.0). Candle OHLC are tick-rounded, not raw (candle 1's close shows 100.0 for a 99.90 print). |
| **C3** diagonal imbalance | **PASS** | Matches its documented (bid[P] − ask[P+tick]) / (bid[P] + ask[P+tick]) on every row. |
| **C4** scale | report | 86,400 one-second trades → 288 five-minute candles, 3,343 footprint rows; build 0.04 s, figure 0.24 s. |
| **O1** OrderFlowMap offline | **FAIL** (predicted) | With the network blocked: "LightweightCharts is not defined". The "zero-dependency" page loads its chart library from cdn.jsdelivr.net. |
| **O2** live-mode side inference | **FAIL** (predicted) | 5,000 synthetic trades with true sides. **Snapshot after every trade: 78.7% of volume signed correctly; CVD −3,452 vs true +790. Every 5 trades: 52.6% (a coin flip); CVD −9,608 vs +902.** Its side comes from the tick rule on last-price changes, and all volume between snapshots becomes one trade. |
| **O3** simulate-mode CVD | **PASS** | 350 simulated trades over 300 ticks: CVD 2,837 = sum of its own signed trades. |

## Deviations

1. **Rust toolchain.** The repo pins 1.95.0; rustup couldn't download it (static.rust-lang.org isn't reachable from here). W1–W3 ran on the installed stable 1.97.0.
2. **W2:** after the ALSA failure, `libasound2-dev` was installed with apt and the build rerun (result at the end).
3. **H1** used `npm ci --ignore-scripts`, so no install scripts from 2021-era packages ran.
4. **H4** (exploratory, below) was added after reading the code and is labelled in the script and JSON.
5. **O2/O3** served the CDN file locally. `lightweight-charts@5.0.9`, the exact pinned version, was fetched from npm. The page logged "Value is null" twice during O2/O3 (chart updates while paused); results were read from its own variables, not the drawing.

## Exploratory (after the results; not pre-registered)

**H4: order-book-heatmap rounds sizes to the price tick.**
- A 0.004 BTC trade is stored as size **0**.
- A 0.003 depth update is stored as **0** (the level vanishes).
- So with tick 0.01, every size under half a cent of BTC disappears.
- Its price aggregation is also broken: with aggregate 10, `parseStep("100.27")` returns 100.27, not 100.3, and `getAggregate()` returns the tick size.

## What this means

None replaces anything in §9 steps 2–5. Order-flow research stays parked (S-ORDERFLOW). The question was which tool could show our Kraken trades correctly when it's unparked.

- **OrderflowChart (S26):** the only fit.
  - Python, Apache-2.0.
  - It takes a trade tape **with the aggressor side**, which is exactly what our Kraken recorder stores (V2-D26).
  - Its footprint, delta and imbalance are exact.
  - Handles a day of 1-second trades in under 0.3 s.
  - Watch-outs: ties go to the even level, and candle OHLC are rounded to the tick.
- **flowsurface (S23):** a correct, well-built desktop app (exact fixed-point footprints), but:
  - GPL;
  - none of our venues;
  - its desktop build pulls system audio libraries;
  - it doesn't read a file of our trades without its own server.
  
  Reference only.
- **order-book-heatmap (S24):** reject.
  - 2021, Binance only, 13 known vulnerabilities, no tests;
  - silently applies a book with missing updates (H3);
  - zeroes small sizes (H4).
- **NT8 OrderFlowKit (S25):** reject.
  - NinjaTrader/Windows only, no licence.
  - Its quote rule drops inside-spread trades from delta.
- **OrderFlowMap (S27):** reject.
  - Indian exchanges via OpenAlgo; needs a CDN.
  - Its "order flow" in live mode is a tick-rule guess on snapshots: ~79% right at best, a coin flip at a 5-trade cadence. Same lesson as S9: only trust delta built from aggressor-side trades.

**Cross-tool trap:** the same 100.25 print lands in the 100.5 row in flowsurface and the 100.0 row in OrderflowChart. When we build profiles, write the tie rule down and test it.

## Files

- `PREREGISTERED.md`.
- S23: `s23_footprint_check/` (Rust crate source + `Cargo.toml.template`; it depends on the clone, nothing copied), `s23_results.json`.
- S24: `s24_obheatmap_checks.mjs`, `s24_results.json`, `s24_npm_audit_summary.json`.
- S26: `s26_orderflowchart_checks.py`, `s26_results.json`.
- S27: `s27_orderflowmap_checks.py`, `s27_results.json`.
- `test_suites.json`.
