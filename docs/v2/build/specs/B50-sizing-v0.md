```yaml
id: B50
title: Sizing v0 — from an accepted chance of ruin to contracts per trade, checked by bootstrap, capped at ¼ Kelly
size: M
model: opus
who: loop             # merges only with the founder's approval: it creates a protected file of risk limits
needs: [G2]
ticks: 3
touches:
  - v2/src/chronos2/themis/**
  - v2/src/chronos2/core/protected.py
  - v2/config/protected/risk.yaml
  - v2/tests/themis/**
  - docs/v2/COMPONENTS.md
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B50 — Sizing v0

## Why
v1 threw strategies away for drawing down too far. That judged the bet size, not the edge: the same strategy at a smaller size passes. In v2 the drawdown you can live with **sets** the size instead (V2-D08). You choose two things, how deep a fall you'd accept (the cushion) and how small a chance of ever hitting it (the accepted ruin probability); the maths turns those into how much to risk per trade. The textbook formula has a bug in the one popular implementation we checked (it understates ruin about 2× once costs are charged), and it assumes trades are independent, which crypto's calm-then-wild stretches break. So the formula is fixed, then checked by resampling the strategy's own trades in blocks, and never allowed above a quarter of the Kelly bet.

## Read first
- Master doc §6 "Drawdown is a sizing input"; the Themis rows of §2 and §3 (≤ ¼ Kelly). `BUILD_NOTES.md` §3 (all of it).
- v1 `tests/moirai/test_free_stages.py` around line 211 (the 24-ordering drawdown fixture) and v1's `trade_shuffle`.
- Spec B06 (`stationary_bootstrap` and block length helpers), B16 (venue contract specs).

## The rules (fixed here)

**Units.** A trade's result in R: its net P&L ÷ the amount it risked (entry to stop, plus costs). `r` = the fraction of capital risked per trade. The cushion `cushion` is a fraction of capital (0.20 = a 20% fall). In R units the cushion is `D = cushion ÷ r`.

**The formula** (S2, corrected). For a trade distribution with positive mean, θ is the positive root of `E[exp(−θ·X)] = 1`, X the result in R. The chance of ever falling D R below the start is about `exp(−θ·D)`. **Not** `exp(−θ·D·L)`: θ is already in R units, and the extra L is the bug [Certain — run, S2 audit]. So the largest risk whose ruin chance is at most ε is
`r_formula = θ · cushion ÷ ln(1/ε)`.

**The bootstrap check.** The strategy's own sequence of R results is resampled with a stationary block bootstrap (B06; mean block length from B06's block-length rule, with a floor of 5), into 20,000 paths of `horizon` trades. `ruin_boot(r)` = the share of paths whose running sum falls to `−cushion ÷ r` R. `r_boot` = the largest r with `ruin_boot(r) <= ε`, found by bisection to 1e-6, **using the same 20,000 resampled paths for every r** (drawn once; only the ruin line moves), so the ruin share can only fall as r falls and the bisection can't wander. Seeds come from the call.

**The Kelly cap.** `f_kelly` maximises `E[ln(1 + f·X)]`; `r_kelly_cap = f_kelly ÷ 4`.

**The size.** `r = min(r_formula, r_boot, r_kelly_cap)`; the report names which one bound. A strategy with non-positive mean R has no θ and no size: refused.

**To contracts.** `contracts = floor(r × capital ÷ risk_per_contract)`, where `risk_per_contract` = stop distance × contract multiplier + round-trip costs per contract (B16). Zero contracts → the trade is **skipped**, and skips are counted (proposal P-14(a) is still open; "skip" is v0's answer and is reported, not hidden). Above the venue's maximum order → refused.

**Volatility targeting** (Carver's method, ported as a known-answer test, V2 principle "vol targeting"): `contracts = forecast ÷ 10 × daily_cash_vol_target ÷ contract_daily_value_vol`, `daily_cash_vol_target = capital × annual_vol_target ÷ sqrt(periods per year)`. **Divide by the square root of the number of bars per year:** `sqrt(365)` for daily crypto bars, `sqrt(8,760)` for hourly ones (and then the target and the contract's volatility are both per hour, not per day), never Carver's 16, which is right only for business days.

**Protected risk limits.** `v2/config/protected/risk.yaml` holds `accepted_ruin_probability`, `cushion`, `horizon_trades`, `annual_vol_target`, all `null`. These are risk limits: only the founder sets them (hard rule 7). While any is `null`, real sizing refuses (`RiskLimitNotSet`); tests pass their own values. Every money amount (capital, per-contract values) comes from configuration.

## Deliver
1. `themis/ruin.py` (`theta`, `ruin_formula`, `r_formula`), `themis/kelly.py`, `themis/bootstrap_check.py` (`ruin_boot`, `r_boot`), `themis/size.py` (`size_strategy` → the chosen `r` and its binding limit; `contracts_for`), `themis/voltarget.py`, `themis/shuffle.py` (`trade_shuffle` and `max_drawdown`, ported from v1).
2. `risk.yaml` with the four `null` keys; `load_risk()` in `core/protected.py`.
3. Tests.

## Steps
1. Tests (red). 2. θ, ruin, Kelly. 3. Shuffle and drawdown (v1 port). 4. Bootstrap check. 5. `size_strategy`, contracts, skips. 6. Vol targeting. 7. Protected file. 8. Report.

## Known answers and checks
All [Certain — run, 16–17 Nov], to 1e-9 unless stated.

**θ and ruin.**
- S2's Strategy A (win 40% at +3R, lose at −1R): `θ = 0.36901653217091435`; ruin of 10R `= 0.024967873969457224`.
- A fair coin tilted to 55% (±1R): `θ = ln(0.55/0.45) = 0.20067069546215124`; ruin of 20R `= (0.45/0.55)^20 = 0.018071595021380355`. (A closed form, so this one checks the root-finder.)
- **The bug, as a pair** (S2's audit example: wins 43% at +3R, losses at −1R, with costs of c R taken off every trade, so +3−c and −1−c):

| Cost c | θ | Correct ruin of 10R `exp(−10θ)` | Buggy `exp(−10θ·(1+c))` |
|---|---|---|---|
| 0 | 0.44016408853161243 | 0.012257210715660948 | the same |
| 0.30 | 0.23070305941865846 | **0.09955643654217909** | 0.04982991500236381 |
| 0.60 | 0.06206370297888409 | **0.5376018600908079** | 0.3704565008830563 |

The tests assert the correct column **and** that the result differs from the buggy column (so a copy of the bug can't pass).

**Kelly.** (40%, +3, −1) → `0.2` (1e-12); (43%, +2.7, −1.3) → `0.11965811965811964`; (55%, ±1) → `0.1`.

**The size, worked.** Trades at 43% of +2.7R, else −1.3R; `ε = 0.05`, `cushion = 0.20`: `r_formula = 0.015402114631890226`; `r_kelly_cap = 0.02991452991452991`; given an `r_boot` of 1.0 (a stub, to test the minimum), the size is `0.015402…` and the binding limit is `formula`; given an `r_boot` of 0.01, the size is 0.01 and the binding limit is `bootstrap`. With `ε = 0.01`: `r_formula = 0.01001930656637214`.

**The bootstrap catches clustering** (seeds pinned; prototype values in brackets):
- *Independent:* 1,100 wins and 900 losses of 1R in a random order (shuffled with `numpy.random.default_rng(50001)`). `ruin_boot` for a 20R fall over 2,000 trades, mean block 10, 20,000 paths, seed 50002: in **[0.009, 0.036]**, within a factor of 2 of the formula's 0.0181 [0.01555].
- *Clustered:* the same 2,000 results arranged as 11 wins then 9 losses, repeated 100 times. Same settings, seed 50003: at least **0.054**, three times the formula's value [0.1052]. The formula sees no difference between the two; the bootstrap does. That difference is why both exist.

**Contracts.** Capital 2,000; `r = 0.0154` → 30.80 at risk. Risk per contract 25 → 1 contract. Risk per contract 40 → 0 contracts: the trade is skipped and the skip counter goes up by one. Capital and per-contract values come from configuration; a test asserts no number in `themis/` source is a money amount.

**Volatility targeting** (Carver). Capital 100,000; annual vol target 20%; daily bars: `daily_cash_vol_target = 1046.8478451804274`; contract daily value vol 300; forecast 10 → `3.4894928172680912` contracts. With 16 in place of √365: 1250.0 and 4.1667, i.e. **19.4% too big** (`sqrt(365)/16 − 1 = 0.19406082340892494`): asserted as the trap. Hourly bars use √8,760.

**v1's drawdown fixture** (ported unchanged). Trade factors 1.10, 0.90, 1.05, 0.80: terminal equity `0.8316` for all 24 orderings; the 24 maximum drawdowns are exactly `{0.20: 4, 0.208: 4, 0.244: 4, 0.28: 12}`; every value `trade_shuffle` produces is one of them.

**Fail closed.** With the real `risk.yaml` (all `null`), `size_strategy` raises `RiskLimitNotSet`. A strategy whose mean R is ≤ 0 → refused, with the reason.

## Not in this build
Setting the risk limits (the founder, before paper trading) · the guard stack and Nemesis (orders never come from here: this module returns numbers; hard rule 1) · portfolio-level sizing across strategies · P-14(a).

## Halt if
- B06's bootstrap can't produce paths of a given length from a shorter series.
- A band is missed by code that passes the closed-form tests: report the numbers; seeds and bands don't change.

## For the gate
`COMPONENTS.md` §2 (this build edits it): "Sizing v0 — built in B50". `BUILD_NOTES.md` §3 (this build edits it): "fixed formula, bootstrap check and ¼ Kelly cap in `themis/` (B50); the risk limits are protected and still unset". For the founder: four risk limits to set before paper trading.
