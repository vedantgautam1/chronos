# Pre-build audit (16 Nov 2026 UTC)

The founder asked for an in-depth audit of everything decided, documented and coded so far, before §9 step 2 (the code skeleton). This file records what was checked, what was found and what was proposed. **Nothing here is a decision.** Proposals P-12 to P-15 are in the master doc §12. **Answers so far (16 Nov):** P-13 → option (c), locked as V2-D46; P-14(b) answered (more capital available); forks 1–2 → V2-D45.

**Caveat:** Claude wrote most of the material audited here, so this audit is partly self-grading. Under V2-D25 rule 3, an audit by a separate agent that hasn't seen this work is available if the founder wants an independent pass.

## 1. What was checked

| Check | Result |
|---|---|
| Master doc read in full (§0–§14) for internal contradictions and stale text | 2 real contradictions or gaps (§3 below), 4 stale passages (§5) |
| BUILD_NOTES §3–§7, COMPONENTS §2 (v1 port list), the three specs | Port targets exist where COMPONENTS says; one spec staleness note missed the 15 Nov decisions |
| **v1 stats probe** `chronos_math_probe.py` in a fresh `uv` environment from v1's own lock file (Python 3.13) | **28/28 pass** |
| **v1 tests that step 2 ports**: `tests/statistics`, `tests/moirai`, `tests/hephaestus/test_costs.py`, `test_run.py` | **182 pass, 0 fail** (7 min) |
| v1 null benchmark's strict-`<` rank (to fix when porting) | Still at `src/chronos/moirai/stages/null_bench.py` line 125: `np.mean(nulls < candidate_net)` |
| v1 fragmentation screen (V2-D31 port) | Present: `eligibility.py` `_fragmentation_screen`, `_grid_axes` |
| NautilusTrader on PyPI | 1.231.0, Python `>=3.12,<3.15`, LGPL-3.0-or-later (compatible with an AGPL repo) |
| Coinbase nano via **IBKR Canada** | IBKR Canada's own page lists nano BTC/ETH, monthly **and perpetual-style**; needs futures permission. Margin, market-data cost and hours not stated there |
| IB Gateway unattended running | IBKR docs: daily auto-restart can be set; **weekly re-authentication needs a manual login**, cycle starting Monday |
| Cost vs typical move size, descriptive (2024 Bitstamp 5-min BTC, pre-seal; not a strategy test) | §2 below |

## 2. The biggest risk: the first track's costs vs how far BTC moves

Coinbase nano fees through IBKR are fixed in dollars (≈ USD 0.31 per contract per side, 0.62 a round trip), so in basis points they depend on the BTC price: 0.62 / (0.01 × price).

On 2024 data (pre-seal; median price ≈ USD 64k):

| Hold | Median absolute move | Mean absolute move |
|---|---|---|
| 5 min | 7.1 bps | 10.7 bps |
| 15 min | 12.7 bps | 18.6 bps |
| 1 hour | 24.4 bps | 37.0 bps |
| 4 hours | 49.8 bps | 75.4 bps |

**Fees alone, round trip:** ≈ 9.7 bps at that price (≈ 6.2 bps at USD 100k), before spread, slippage, funding and basis. The 2× run doubles them (≈ 19 bps at USD 64k).

Rough reading (a simplification: equal-sized wins and losses, no skew): a 1-hour trade earning (2p − 1) × 37 bps needs a hit rate p ≈ 63% just to pay 1× fees, and ≈ 76% for 2× fees. Holds of 15 minutes or less are close to impossible after 2× costs. Multi-hour holds are where the arithmetic starts to work.

This doesn't change any decision. It says S-INTRADAY's realistic horizon is probably "hours", not "minutes", and that the edge check's data-sufficiency step should start with this calculation. → **P-12**.

## 3. Contradictions and gaps in the design

**3a. Post-seal series can't be researched under the seal as written.** V2-D38 seals all BTC/ETH data from 1 Apr 2026, and BUILD_NOTES §2 says research tools must refuse any BTC/ETH query past 31 Mar 2026. S-NEWS collection and the Kraken trade recorder only start after the seal date. V2-D38 gives those series their own sealed block, but **studying them needs BTC prices from the same months**, which the crypto seal forbids. As written, S-NEWS (and order flow on recorded trades) can never be researched before paper. → **P-13**.

**3b. Basis before the contract existed is unspecified.** Backtests run on Kraken spot from ~2013, costs "with basis modelled", but the nano perpetual-style contract only exists from ~Jul 2025. For minutes-to-hours holds, the gap between the spot price the signal sees and the futures price actually filled is a cost of the same order as the edge. There's no stated model for years before Jul 2025, and no requirement to check candidates on the real contract's own bars for Jul 2025–Mar 2026 (the only pre-seal stretch where both exist). → **P-15**.

## 4. Things that don't fit a ~USD 2k account

- **Running costs vs capital.** The start estimate of ~$20–60/month is **12–36% of $2k a year**; the locked ceiling of $100–150/month is 60–90%. A strategy must beat that before it makes money. The master doc defers this comparison to "before going live" (O-7); it matters before step 4 starts spending. → **P-14(b)**.
- **Sizing granularity.** With an illustrative 20% annual vol target on $2k (calendar-day crypto, √365): daily cash vol target ≈ $21. One nano BTC at ~USD 100k with ~3% daily vol moves ~$30 a day. So Themis's target is usually **below one contract**, and "skip trades it can't place" could skip almost everything. The 2× notional ceiling (V2-D40) allows about 4 nano BTC at USD 100k. Rounding rule not decided. → **P-14(a)**. (Figures illustrative [Guessing on the vol levels]; the arithmetic is exact.)
- **Minimum equity.** IBKR Canada lists an account minimum of USD 0; whether a futures margin account needs a minimum equity (US accounts commonly cite USD 2,000) wasn't found [Guessing]. Check when the account is opened.

## 5. Stale or inconsistent text (fixed in this PR)

1. Master doc §1 said "decisions V2-D01–D42"; now through V2-D44.
2. Master doc §2c said "Content analysis S1–S22 … next item S23"; S1–S35 are done.
3. The sentiment spec's staleness note didn't mention the World Monitor catalog import or AGPL (15 Nov), or the seal gap in 3a.
4. Dates mix local time and UTC: the World Monitor row says 15 Nov (founder's local date), V2-D43/D44 say 16 Nov (UTC). Harmless; docs now say dates are UTC from here on.

## 6. Forks the step-2 session must settle first (CLAUDE.md rule 9)

**Answered 16 Nov:** 1 → option (a), locked as V2-D45; 2 → Python 3.14 (V2-D45); 3 → founder: "we'll change before that" (read as: strategy rules move out of the public repo before real ones exist; confirm at step 6). Package name still to propose at the start of step 2.

These are non-equivalent options, so they go to the founder at the start of step 2, not decided by the builder:

1. **Where v2 lives and what it's called.** v1's root `pyproject.toml` already defines the package `chronos` with its own `uv.lock`.
   - (a) A separate `uv` project in its own folder with its own `pyproject.toml` and lock. v1 stays byte-for-byte untouched.
   - (b) A `uv` workspace at the root. This edits v1's root `pyproject.toml`.
   
   The v2 package also needs a name other than `chronos`. V2-D42's "code coordinate" must say *which* lock file it hashes. Claude's lean: (a).
2. **Python version:** 3.12 or 3.13. NautilusTrader 1.231 needs ≥ 3.12; v1's tests pass on 3.13.
3. **Strategy rules in a public repo.** Once S-INTRADAY has real rules and parameters, the repo is public (and AGPL), so anyone can read them. Options:
   - keep strategy rule/parameter files out of the public repo (private config, or a private companion repo);
   - accept that they're public.
   
   Founder's call. AGPL only requires sharing source with people you distribute to or serve over a network; it doesn't force you to publish private configuration.

## 7. New trap (added to BUILD_NOTES §5)

IB Gateway needs a **manual weekly re-login** (IBKR docs). Consequences:
- A 24/7 strategy, its data and the V2-D36 watchdog's own connection all stop if it's missed.
- Spike criterion (c)'s "several days without manual intervention" should span a Monday re-authentication, so the cost of that login is measured, not discovered at L3.
- Each reconnect runs the V2-D44 reconciliation.

## 8. What is solid

- The statistics being ported reproduce their known answers today (28/28; 182 tests).
- The trial-counting, seal, footprint and guard decisions (V2-D03, D33, D34/D38, D36, D40–D44) hang together. Each one is backed by a run, not an opinion.
- The cost model's components are right. What's missing is the size of the numbers relative to the edge (§2).
- Engine risk is contained: the spike tests the one make-or-break point, criterion (e), before anything is built on Nautilus.

## 9. Is there a cheaper venue than IBKR? (founder question, 16 Nov)

**No usable one found. Stay with IBKR.** What was checked:

| Option | Per-side cost for 0.01 BTC of exposure | Usable? |
|---|---|---|
| IBKR, Coinbase nano (current plan) | ≈ USD 0.31 (0.20 IBKR + 0.10 exchange + 0.01 NFA) | Yes |
| IBKR fixed plan instead of tiered | Same: fixed still adds exchange and regulatory fees (IBKR's ES example: 0.85 commission, 2.24 total) [Likely] | No saving |
| IBKR, CME Micro Bitcoin (0.1 BTC) | ≈ USD 0.20 (2.0 per contract ÷ 10) — about a third cheaper per BTC | Yes, once positions are ≥ 0.1 BTC. Not 24/7, monthly rolls, no funding |
| Coinbase's own futures for Canadians | 0.02% + USD 0.11 (launch promotion): ≈ 0.24 at USD 64k, ≈ 0.31 at USD 100k | **No**: offered only to Canadians with ≥ USD 5M net financial assets or to registered firms (Cointelegraph) |
| NinjaTrader / Tradovate (accept Ontario residents; list Coinbase nano BTC) | Commission not readable on their pages; the exchange (0.10) and NFA fees are the same everywhere, so the most any broker can save is IBKR's 0.20 | Possible, but **NautilusTrader has no adapter** for them: we'd build and maintain our own order connection, and lose IBKR's FX/equities path |
| Spot venues usable from Ontario (Kraken, Coinbase spot, NDAX, Wealthsimple, IBKR spot crypto) | Typically ~0.1–0.5% (10–50 bps) a side [Likely] | No: dearer and no shorting |
| Offshore perpetual exchanges | Cheapest | Rejected (V2-D27): not legal for Ontario residents |

**Bottom line:** the exchange and regulator fees (~USD 0.11 per nano) are fixed whoever the broker is. Switching broker could save at most IBKR's USD 0.20, at the cost of building our own order connection. The two levers that actually move cost are inside the current plan:
- **MBT for larger positions:** ~35% less per BTC.
- **Longer holds:** going from 1-hour to 4-hour moves roughly halves costs as a share of the move (§2).


- IBKR, [Daily & weekly reauthentication](https://www.interactivebrokers.com/docs/third-party-integrations/tws-settings/daily-weekly-reauthentication) (read 16 Nov).
- IBKR Canada, [Coinbase Derivatives trading](https://www.interactivebrokers.ca/en/trading/coinbase-derivatives.php) (read 16 Nov).
- IBKR Canada, [Required minimums](https://www.interactivebrokers.ca/en/accounts/required_minimums.php) (read 16 Nov).
- Coinbase, [US perpetual-style futures 101](https://www-marketing.coinbase.com/learn/futures/us-perpetual-style-futures-101): 0.01 BTC, hourly funding settled twice daily, up to 10× intraday; tick size not stated.
- PyPI `nautilus_trader` JSON (1.231.0).
- IBKR Canada, [Commissions: futures](https://www.interactivebrokers.ca/en/index.php?f=49560) (read 16 Nov).
- IBKR, [CME exchange and regulatory fees](https://interactivebrokers.com/en/accounts/fees/CME.php) (read 16 Nov).
- [Cointelegraph: Coinbase launches regulated crypto derivatives in Canada](https://cointelegraph.com/news/coinbase-launches-regulated-crypto-derivatives-in-canada); [Fintech.ca, 2 Sep 2026](https://www.fintech.ca/2026/09/02/coinbase-opens-crypto-futures-to-canadian-traders/).
- [NinjaTrader: trade US futures from Canada](https://ninjatrader.com/futures/trade-us-futures-from-canada/); [Tradovate: Coinbase nano bitcoin](https://info.tradovate.com/coinbase-derivatives-nano-bitcoin).
- [NautilusTrader integrations](https://nautilustrader.io/docs/latest/integrations).
- Move-size table: `/home/claude/data/bitstamp/btc_bitstamp_5m_2023_2024.feather` (`ff137/bitstamp-btcusd-minute-data`, MIT, pre-seal), 2024 rows, last close per [start, end) bucket, absolute log returns.
