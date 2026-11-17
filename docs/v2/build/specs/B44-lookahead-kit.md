```yaml
id: B44
title: Look-ahead test kit — slice test, warm-up test, nudge probe
size: M
model: opus
who: loop
needs: [B43]
ticks: 3
touches:
  - v2/migrations/0004_lookahead_reports.sql
  - v2/src/chronos2/lookahead/**
  - v2/tests/lookahead/**
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B44 — Look-ahead test kit

## Why
A strategy that peeks at tomorrow looks brilliant in a backtest and loses money live. **No statistical check catches it:** in S16's ladder a one-bar peek passed the main statistical gate 98% of the time, and even the sealed look caught it only 30% of the time [Certain — S16 rerun]. Only tests built for it do. This build is three such tests. Every strategy must pass all three before the edge check will look at it, and a "lone spike" (B48) sends a strategy back here.

## Read first
- `BUILD_NOTES.md` §2: "Cheap look-ahead probe", "Two look-ahead tests for the strategy kit, from freqtrade" (method only: freqtrade is GPL-3.0, so none of its code is copied), "Look-ahead is invisible to every statistical check".
- Spec B43 (`ScreeningStrategy`: `signals(bars, params)`, `warmup_bars(params)`).

## The rules (fixed here)

All three tests take a strategy, one parameter point and a bar frame, and return a report with `passed` and, when it fails, the bars and values that gave it away.

**1. Slice test** (deterministic). Compute entries on the full history. Then, for every entry bar `i`, recompute on the history cut just after it (`bars[: i + 1]`) and compare: the entry at `i` must still be there, and every indicator column the strategy exposes must agree at `i` to 1e-12 relative. One mismatch fails the strategy. *(Entries only, not exits: the founder can widen it later. Exits are where the money is made, but an exit leak can only change P&L, not whether the strategy trades; the nudge probe watches P&L.)*

**2. Warm-up test.** For each indicator column, at the last bar, compute it with `h` bars of history before that bar for `h` in {`warmup_bars`, 2 × `warmup_bars`, 4 × `warmup_bars`, all available}. The largest relative difference from the "all available" value must be at most **1e-6**. A failure doesn't mean the strategy cheats; it means the backtest and live trading will compute different values unless live trading loads the same history. The report states the history needed for the difference to fall under 1e-6, and the strategy must declare at least that as its `warmup_bars` to pass.

**3. Nudge probe** (random, seeded). Pick 30 entries at random (seed from the call). For each, multiply the close of the bar **after** the entry by 1.05, recompute, then by 0.95, recompute. If any entry **at or before** the original entry changes in either case, the strategy fails. Picking the bar right after an entry is the point: a strategy that reads one bar ahead decides that entry from exactly that bar.

**Order and result.** Slice, then warm-up, then nudge; all three always run, and the report lists every failure. `check_strategy(...)` returns pass only if all three pass. Reports are stored in `mnemosyne.lookahead_report` (migration `0004`; append-only, hashed and journaled like every B09 table), keyed by strategy name, parameter point and code coordinate; `has_passing_report(...)` answers yes or no. The edge check (B47) refuses a candidate without one.

**Parse-time rule.** `ScreeningStrategy` code may not call `.shift()` with a negative number, `.iloc` with a negative step past the current row, or `.mean()`/`.std()`/`.max()`/`.min()` on a whole column outside a rolling or expanding window. A static check (Python's `ast`) refuses these when a strategy is registered. It is a quick first filter; the three tests above are the real ones.

## Deliver
1. `lookahead/slice.py`, `warmup.py`, `nudge.py`, `check.py` (`check_strategy` and the stored report), `static.py` (the parse-time rule).
2. Fixture strategies in `v2/tests/lookahead/fixtures.py`: `clean` (close above its 20-bar average), `peek` (close tomorrow above close today), `whole_mean` (close above the mean of the entire series), `ema200` and `sma200` (the indicator only, for the warm-up test).
3. Tests.

## Steps
1. Fixtures and tests (red). 2. Slice. 3. Warm-up. 4. Nudge. 5. Static check. 6. `check_strategy`, stored reports, `has_passing_report`. 7. Report.

## Known answers and checks
Bars: 3,000 closes, `100 × exp(cumulative sum of 0.01 × standard normals)` from `numpy.random.default_rng(44001)`. Entries are the first bar of each run of `True`. Figures in brackets are what a prototype written for this spec gave [Certain — run, 16 Nov]; the builder's code must reproduce the pass/fail, and the counts where stated.

| Fixture | Slice test | Warm-up test | Nudge probe (seed 44003) |
|---|---|---|---|
| `clean` | pass (0 mismatches of 192 entries) | — | pass (0 of 30) |
| `peek` | **fail** (747 of 747) | — | **fail** (30 of 30) |
| `whole_mean` | **fail** (19 of 25) | — | **fail** (27 of 30) |
| `ema200` (span 200, no adjustment) | — | **fail** (largest relative difference ≈ 1.0e-4 with 250 bars of history) | — |
| `sma200` | — | pass (0.0) | — |

- `peek` and `whole_mean` each fail the slice test **and** the nudge probe: two independent tests catch them, which is intended.
- `ema200` passes once it declares enough warm-up: the report's "history needed" is between 1,500 and 3,000 bars, and with `warmup_bars` set to it, the test passes.
- A nudge on the bar **before** an entry is not what the probe does: a test asserts every nudged bar is an entry bar plus one.
- The probe with a different seed picks different entries; with the same seed, the same ones.

**Static check.** Refused: `c.shift(-1)`; `c.mean()` on a whole column; `c.iloc[i + 1]`. Accepted: `c.shift(1)`; `c.rolling(20).mean()`; `c.expanding().max()`.

**Stored reports.** `has_passing_report` is false for a failing or missing report, and false again after the strategy's code changes (new code coordinate) until a new report passes. (The fixtures are run through the three tests directly, not registered, so the static check doesn't stop them first.)

## Not in this build
Look-ahead in non-price data (`available_at` is checked by the door, B14, and by later data builds) · look-ahead inside the real engine (after G3) · LLM-sourced ideas, whose models have seen the future (they only count from paper trading, V2-D34).

## Halt if
- `warmup_bars` can't be read from a strategy without running it.
- A fixture's pass/fail differs from the table: report it; the fixtures and seeds don't change.

## For the gate
`BUILD_NOTES.md` §2 (this build edits it): "look-ahead kit built in B44; the nudge probe perturbs the bar after each sampled entry (a random bar caught a one-bar peek only 16 of 30 times in the prototype; the bar after an entry, 30 of 30)".
