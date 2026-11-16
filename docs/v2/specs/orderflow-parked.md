# S-ORDERFLOW — parked thesis dossier

**Status: parked** (founder, 15 Nov 2026: "keep order flow on the side for now", wanted later). This file gathers everything found so far so the work can restart without re-research. It is **not** a spec and nothing here is a decision. When this is unparked:
- the theses below go through the normal path (research card → pre-registered rules → counted screen → edge check);
- every variant counts as a trial (V2-D03).

Last updated 16 Nov 2026.

## 1. What is being collected now, and what isn't

| Data | Status | Notes |
|---|---|---|
| **Kraken BTC/USD and ETH/USD trades, forward**: price, size, time, **aggressor side**, market/limit | Locked (V2-D26), built at §9 step 4 (after the spike, V2-D30) | The only true aggressor-side source we'll have. Kraken's public `Trades` endpoint: 1,000 per call, page forward with `since`. |
| **Kraken quarterly bulk trade files** (history) | Planned at step 4 (founder, 5 Nov) | **Carry a buy/sell field** (corrected 16 Nov from Kraken's support page): timestamp, price, volume, type b/s, order_type, misc, trade_id. So years of signed history may be available, which is a big help for this thesis. Confirm `type` is the taker side against recorder data on overlapping days, and check the timestamp resolution. |
| Kraken trades backfilled through the API (with side) | Optional | Possible but slow (1,000 trades per call). |
| Order book (L2/L3) | **Not collected** | Book-based strategies are out of scope (V2-D22). |
| Coinbase nano / CME futures trades | Not collected | We trade these through IBKR. Whether IBKR gives trade-level data with side is unchecked. |

## 2. The three theses (from the reference library §6)

1. **Aggressor-side delta as an S-INTRADAY input (S9, reframed for V2-D28).** For example, confirm entries in the S-TREND regime direction.
   - **Prior:** order-flow imbalance moves price mostly *at the same time*, not later (Cont, Kukanov & Stoikov 2014) [Likely], so prediction at minutes-to-hours horizons is doubtful.
   - **Falsifier:** no lift over the same S-INTRADAY rules without it, after futures costs, counted as trials.
2. **Hawkes / trade clustering (S10).**
   - Candidate features:
     - (a) branching ratio as an activity/volatility filter;
     - (b) buy-vs-sell intensity imbalance as a directional input.
   - **Prior:** Hawkes models forecast activity and volatility well; direction is the weak part [Likely].
   - **Falsifiers:** (a) no gain over an EWMA/HAR volatility baseline; (b) no lift after costs vs the random-entry null.
   - **Trigger:** a few months of recordings.
3. **Market profile (S9).**
   - Dalton value-area behaviour: re-entry into the prior value area → traverse; point of control as a magnet. Testable at hours (allowed by V2-D22).
   - Needs a measured volume profile from trades.
   - **Falsifier:** no edge over the random-entry null after costs.

**Cross-venue caveat for all three:**
- flow is measured on Kraken spot, but we trade Coinbase/CME futures;
- Kraken is a minority of BTC volume [Likely].

So any signal is a partial view. Measure how Kraken flow relates to the nano contract's price before trusting it.

## 3. Rules for the data (all tested; details in `BUILD_NOTES.md` §4 and §8)

- **Only trust delta built from aggressor-side trades.**
  - Candle-shape "delta" (close-location × volume) is a function of OHLC only (S9).
  - Tick-rule guessing signed 78.7% of volume correctly per trade and 52.6% at 5-trade snapshots on a synthetic tape (S27).
  - Quote rules drop inside-spread trades (S25).
- **The recorder detects gaps and records them;** it never stitches over them (S24 applied a book across missing updates silently).
- **Sizes are stored at their own precision** (S24 rounded 0.004 BTC to 0 at a 0.01 price tick).
- **Never deduplicate on timestamp:** one taker order prints several trades at the same time (S20: freqtrade's Kraken importer drops them). For Hawkes fits, *merge* same-order prints deliberately and record that you did.
- **Write down and test the price-bin tie rule** for footprints and profiles. flowsurface rounds ties away from zero; OrderflowChart rounds them to even (S23, S26). Floor to the bin's lower edge is simplest.
- **Candle and profile buckets are [start, end)**, UTC.
- **Hawkes fits** (S10, `tick` library):
  - use a time-of-day baseline (seasonality alone fit as branching 0.25–0.92);
  - choose the decay by likelihood (a wrong decay moved branching from 0.55 to 0.15 or 0.75);
  - install `numpydoc` (undeclared dependency);
  - use least squares (its likelihood fit errors by default).
- **Stay above one minute** (V2-D22). Predicting the next seconds of flow is HFT.
- **Maker fills get picked off.** Back-of-queue crypto maker fills lost more to 10-second moves than the spread earned (S8a). No maker-fee savings without measured markout.

## 4. Tools

| Tool | Use | Status | Notes |
|---|---|---|---|
| **OrderflowChart** (murtazayusuf, Apache-2.0, 0.2.0) | Viewer: footprint, delta, cumulative delta, diagonal imbalance, POC from a trade tape with aggressor side | **Tested 16 Nov (S26): exact; 86,400 trades in 0.3 s** | Ties to even; candle OHLC tick-rounded |
| **tick** (BSD-3, 0.8.0.2) | Hawkes simulation and fitting | **Tested 29 Oct (S10)** | Traps above |
| **flowsurface** (GPL-3.0, Rust desktop) | Reference for exact fixed-point footprints and profiles | **Tested 16 Nov (S23)** | None of our venues; GPL: methods only |
| **Bullseye Order Flow** profile engine (Pine, MPL-2.0) | Reference for session-profile construction and a footprint diagonal-imbalance scanner | Read (S9) | Its default "order flow" is candle shape; fix its BTC row-size bug |
| hftbacktest | Order-book/queue backtester | Listed only | Only if V2-D22 ever changes |

**Rejected** (don't re-evaluate from scratch; reasons in the reference library §8):
- order-book-heatmap (S24);
- CSharp-NT8-OrderFlowKit (S25; no licence);
- OrderFlowMap (S27);
- Bullseye Order Flow as a signal source (S9).

## 5. Before unparking: open checks

1. A few months of V2-D26 recordings exist and the gap log is clean enough to use.
2. One real Kraken bulk file opened: timestamp resolution; `type` matches the recorder's aggressor side on overlapping days.
3. Kraken's share of BTC volume, and how Kraken flow relates to Coinbase nano price moves at the horizons we trade.
4. Whether IBKR offers trade-level data for the nano contracts, and at what cost.
5. A research card per thesis, with falsifiers and the trial count written before any screen.

## 6. Where the evidence lives

| Source | Where |
|---|---|
| S9 Bullseye Order Flow | `claude/item-analyses.md` (Project) |
| S10 tick / Hawkes deep pass | `claude/item-analyses-2.md`; repo `docs/v2/research/s10-deep-pass/` |
| S8a maker-markout study | `claude/item-analyses.md` |
| S20 Kraken bulk files, freqtrade importer | `claude/item-analyses-3.md`; repo `docs/v2/research/s19-s22/`, `s19-s22-deep/` |
| S23–S27 order-flow tools | `claude/item-analyses-4.md`; repo `docs/v2/research/s23-s35/part4/` |
| Traps | `BUILD_NOTES.md` §4, §8 |
| Library entries | `claude/reference-library.md` §1, §2, §6, §8 |
