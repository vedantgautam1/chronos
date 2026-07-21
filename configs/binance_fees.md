# Binance spot fee verification record

Per docs/SPEC_HEPHAESTUS §6 / build brief rule 6: fee values must be verified
against the exchange's current published schedule at build time, with the
source and retrieval date recorded. This file is that record.

| Item | Value | Where used |
|---|---|---|
| Spot maker fee, regular/VIP-0 | **0.100% (10 bps)** | `CostConfig.maker_fee_bps` |
| Spot taker fee, regular/VIP-0 | **0.100% (10 bps)** | `CostConfig.taker_fee_bps` — charged on ALL fills (conservative) |
| BNB-payment discount (0.075%) | **NOT assumed** | — |

- **Source:** https://www.binance.com/en/fee/trading
- **Retrieved:** 2026-07-08
- **Notes:** VIP tiers reduce fees with volume; Stage 0 assumes the worst
  (regular tier, no BNB discount). Re-verify when this matters or when
  Binance announces schedule changes.

Non-fee constants (NOT from any schedule — provisional, R6 discipline):

| Item | Value | Status |
|---|---|---|
| Modeled half-spread | 1 bp per side | Provisional; bar data has no order book |
| Slippage | 1 bp (R6-measured 2026-07-17) | Provisional; measured from 6mo Binance aggTrades, 90k−9k difference estimator median 0.002bps size-impact — defaulted to 1bps as a conservative margin, not a clean impact number |

Every result produced with provisional constants carries the
`provisional_cost_constants` warning automatically.
