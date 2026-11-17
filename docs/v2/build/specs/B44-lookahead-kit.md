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

All three tests take a strategy, one parameter point and a bar frame, and return a report with `passed` and, when it fails, the bars and values that gave it away. The frame used is recorded in the report (its snapshot hash and window). **A report counts for a candidate only if its frame is the candidate trial's research window and snapshot, and the strategy made at least 30 entries in it**; fewer → `inconclusive`, never `passed` (red team F4: a frame with no trades passes vacuously).

**1. Slice test** (deterministic). Compute all signals on the full history: long and short entries, long and short exits, and the stop. Then, for every bar `i` where any of them fires, recompute on the history cut just after it (`bars[: i + 1]`) and compare: every signal column must have the same value at `i`, and every indicator column the strategy exposes must agree at `i` to 1e-12 relative. One mismatch fails the strategy. *(The first draft checked entries only and called that enough; the red team showed an exit that reads tomorrow passed all three tests (F2). Exits are where a peek makes money, and BUILD_NOTES asks for "every indicator value and signal".)*

**2. Warm-up test.** For each indicator column, at the last bar, compute it with `h` bars of history before that bar for **every** `h` from `warmup_bars` to all available. The largest relative difference from the "all available" value must be at most **1e-6**. A failure doesn't mean the strategy cheats; it means the backtest and live trading will compute different values unless live trading loads the same history. The report states the **history needed**: the smallest `h` such that every longer history is within 1e-6 (checked bar by bar, because the difference doesn't shrink steadily: for the EMA-200 fixture, 500 bars is within it and 1,000 isn't, red team F3). The strategy must declare at least that as its `warmup_bars` to pass.

**3. Nudge probe** (random, seeded). Pick 30 entries at random, **with replacement** (seed from the call; with replacement so a strategy with fewer than 30 entries still gets 30 picks). For each, multiply the close of the bar **after** the entry by 1.05, recompute, then by 0.95, recompute. If **any signal column** (entries, exits, stop) changes at any bar **at or before** the original entry, the strategy fails. Picking the bar right after an entry is the point: a strategy that reads one bar ahead decides that bar's signals from exactly the nudged bar.

**Order and result.** `check_strategy(...)` runs the static check below first, then slice, warm-up and nudge; all always run, and the report lists every failure. It returns pass only if all pass. Reports are stored in `mnemosyne.lookahead_report` (migration `0004`; append-only, hashed and journaled like every B09 table), keyed by strategy name, parameter point, a hash of the strategy's source file, the lock-file hash, and the frame's snapshot hash and window (not the git commit: an unrelated commit must not invalidate every report, red team F19); `has_passing_report(...)` answers yes or no. The edge check (B47) refuses a candidate without one.

**Parse-time rule.** `ScreeningStrategy` code may not call `.shift()` with a negative number, `.iloc` with a negative step past the current row, or `.mean()`/`.std()`/`.max()`/`.min()` on a whole column outside a rolling or expanding window. A static check (Python's `ast`) refuses these when a strategy is registered. It is a quick first filter; the three tests above are the real ones.

## Deliver
1. `lookahead/slice.py`, `warmup.py`, `nudge.py`, `check.py` (`check_strategy` and the stored report), `static.py` (the parse-time rule).
2. Fixture strategies in `v2/tests/lookahead/fixtures.py`: `clean` (enter long when the close is above its 20-bar average, exit when below), `peek` (close tomorrow above close today), `whole_mean` (close above the mean of the entire series), `exit_peek` (clean entries; exit long when tomorrow's close is below today's), `ema200` and `sma200` (the indicator only, for the warm-up test; `ema200` declares `warmup_bars = 250`).
3. Tests.

## Steps
1. Fixtures and tests (red). 2. Slice. 3. Warm-up. 4. Nudge. 5. Static check. 6. `check_strategy`, stored reports, `has_passing_report`. 7. Report.

## Known answers and checks
Bars: 3,000 closes, `100 × exp(cumulative sum of 0.01 × standard normals)` from `numpy.random.default_rng(44001)`. Entries are the first bar of each run of `True`. Figures in brackets are what a prototype written for this spec gave [Certain — run, 16 Nov]; the builder's code must reproduce the pass/fail, and the counts where stated.

| Fixture | Slice test | Warm-up test | Nudge probe (seed 44003) |
|---|---|---|---|
| `clean` | pass (0 mismatches at 384 signal bars) | — | pass (0 of 30) |
| `exit_peek` | **fail** (747 of 838) | — | **fail** (30 of 30) |
| `peek` | **fail** (747 of 747) | — | **fail** (30 of 30) |
| `whole_mean` | **fail** (19 of 25) | — | **fail** (27 of 30) |
| `ema200` (span 200, no adjustment) | — | **fail** (relative difference ≈ 1.0e-4 at 250 bars of history; history needed **1,070**) | — |
| `sma200` | — | pass (0.0) | — |

- `peek` and `whole_mean` each fail the slice test **and** the nudge probe: two independent tests catch them, which is intended.
- `ema200` passes once it declares enough warm-up: the report's history needed is exactly **1,070** bars [Certain — run, 17 Nov], and with `warmup_bars = 1070` the test passes; with 1,069 it fails.
- `peek`, `whole_mean` and `exit_peek` are the counts in the table with every signal column compared; `peek` and `whole_mean` have no exit rule, so their counts are the entries-only counts.
- A frame of 500 bars on which `clean` enters 12 times → `inconclusive`.
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
