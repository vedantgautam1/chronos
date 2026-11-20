```yaml
id: B43
title: Screening wrapper — fast sweeps through VectorBT with five fixes, every variant a counted trial
size: M
model: opus
who: loop             # merges only with the founder's approval: it adds a library (dependency files are founder-owned)
needs: [G2]
ticks: 3
adds_dependencies: [vectorbt]
touches:
  - v2/pyproject.toml
  - v2/uv.lock
  - v2/src/chronos2/screen/**
  - v2/tests/screen/**
  - docs/v2/COMPONENTS.md
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B43 — Screening wrapper

## Why
Researching an idea means trying many versions of it (a fast average of 5, 10 or 20 bars; a stop at 2% or 4%). VectorBT tries a thousand versions in seconds and its maths is exact. Out of the box, though, it does five things that flatter a strategy: it fills a signal at the price that produced it, checks stops only at the close, charges no slippage on stops, charges no funding, and silently drops the Sharpe ratio when the bar size isn't stated (S32, run). This build is the one door to VectorBT, with those five things fixed, and it writes **every version tried** into the trial store before anyone sees a result. That last part is what keeps the trial count honest; the rest keeps each number honest.

## Read first
- `BUILD_NOTES.md` §2 "VectorBT screening goes through one wrapper", "Optimisers report the best try as if it were the only one". `COMPONENTS.md` §1 "VectorBT".
- Master doc §10 V2-D03, V2-D33, V2-D42, V2-D48.
- Specs B10 (`start_trial`, `finish_trial`), B11 (`TrialResult`, `Trade`, `Footprint`), B14 (`get_bars`), B16 (`price_trade`).
- VectorBT's docs for `Portfolio.from_signals`, read fresh for the version the lock resolves: `price`, `open/high/low/close`, `sl_stop`, `stop_exit_price`, `freq`, `year_freq`.

## The rules (fixed here)

**VectorBT decides when positions open and close. It never prices costs.** Every run uses `fees=0`, `slippage=0`. Each trade it reports is then re-priced by B16's `price_trade` into a `Trade` (B11) with all seven cost components. So fixes 3 and 4 below come from our pricer, the same one the null benchmark (B45) and the engine path use, and the screen can never disagree with the edge check about what a trade cost.

**The five fixes:**
1. Signals are shifted one bar; entries and exits fill at the **next bar's open** (`price=open`).
2. `open`, `high`, `low`, `close` are always passed, so a stop is checked against the whole bar.
3. Every exit, stop exits included, carries spread and slippage as cost components (VectorBT's default leaves stop exits without slippage).
4. Funding is charged per trade from its own records: hours held × notional × the hourly rate path (and, in the adverse run, B16's adverse level).
5. `freq` and `year_freq` are always set; a run without them is refused.

**A strategy for screening** is a pure function `signals(bars, params) -> Signals` (long entries, long exits, short entries, short exits as boolean columns; optional stop as a fraction) plus `warmup_bars(params)` and an optional `trading_hours` (UTC hours in which it may open a trade; absent = all). It sees only the bars it is given. The look-ahead kit (B44) tests exactly this function; the null benchmark (B45) uses `warmup_bars` and `trading_hours` to know where a random trade could have started.

**Only our numbers leave the wrapper.** With fees and slippage at zero, every VectorBT statistic is gross of costs. So `run_grid` and `run_point` return trial ids and nothing else; the `Portfolio` object and its `stats()` never leave `screen/`. Every number stored is computed from the repriced net returns (red team F23: anything else is a cost-free path, hard rule 3). Fix 5 stays, as a guard on VectorBT's internal annualisation.

**Kinds are not a free choice.** `run_grid` files every point as SEARCH. `run_point` files SEARCH by default; it files VERIFICATION only for a point that already exists as a SEARCH trial of the same hypothesis (same strategy class and parameters) and on that trial's window, as a re-run or cost stress. A new parameter point or a new window as VERIFICATION is refused (red team F6: filing new tries as VERIFICATION would never raise N). B48 adds the database trigger that makes this a wall. `run_point` has no `purpose` argument: it always reads for research. The one sealed run goes through `run_sealed(look_id, trial_id, ...)`, which only works for the look's bound reader (the door checks, B46).

**Every version is a trial.** For a grid run: the hypothesis must exist; one SEARCH trial is **started** for every grid point (B10) before the first VectorBT call; each is finished with its stored `TrialResult` (returns, trades, footprint) or as `errored`. Nothing is returned to the caller until every point has a terminal event. Grids over 200 points are run in chunks (memory: 1,000 × 17,544 hourly bars used 1.5 GB in S32).

**Returns are additive, not compounding:** each bar's net return is that bar's mark-to-market P&L net of costs, divided by the configured capital. Entry-side costs are booked on the entry bar; exit-side costs and funding on the exit bar. Then `Σ net_returns × capital = Σ trade nets`, which can be tested.

**Data only through the door** (B14). The footprint of each trial is the door's footprint for the bars read, warm-up included.

**Sizes in screening** are a fixed notional per trade from configuration; contract counts may be fractional here and say so in the trial record. Whole-contract sizing is B50's job.

**First thing in the build:** re-run S32's five findings on the VectorBT version the lock resolves (S32 tested 1.2.0). If any of the five no longer holds, halt: the fix for it may be wrong.

## Deliver
1. `vectorbt` added (the version the lock resolves; recorded in `COMPONENTS.md`).
2. `screen/strategy.py` (`ScreeningStrategy`, `Signals`), `screen/run.py` (`run_grid(hypothesis_id, strategy, grid, window, venue, cost_inputs, capital, freq) -> list[trial_id]`; `run_point(...)` for single points, used by B48 for neighbours; `run_sealed(...)` for the one sealed run; none returns anything but trial ids), `screen/reprice.py` (VectorBT trade records → B11 `Trade`s), `screen/returns.py` (additive net returns).
3. Two example strategies used by tests and later builds: a moving-average cross (long/short, grid `fast`, `slow`) and a breakout with a stop.
4. Tests.

## Steps
1. Re-check the S32 findings on the resolved version; record in the report. 2. The five fix tests (red). 3. `reprice.py`, `returns.py`. 4. `run.py` with trial registration → green. 5. The count and identity tests. 6. Report with timings.

## Known answers and checks

**The five fixes**, each a test that fails when the same bars go through raw `Portfolio.from_signals` with its defaults and passes through the wrapper:

| # | Bars and signal | Wrapper | Raw VectorBT |
|---|---|---|---|
| 1 | Long signal on bar 3 (close 100); bar 4 opens at 105 | entry price 105 | entry price 100 |
| 2 | Long from 100 with a 5% stop; next bar O 90, H 99, L 88, C 99 | exits on that bar | still open after it (the close never touched 95) |
| 3 | Same as 2, with half-spread 0.02% and slippage 0.05% per side | the exit `Trade` has non-zero `spread` and `slippage` | — (raw with `slippage=0.0005` and default `stoplimit`: the stop exit pays no slippage) |
| 4 | Long, 10,000 USD notional, held 10 hourly bars, hourly funding 0.001% | `funding == 1.00` USD | no funding |
| 5 | Any run with `freq` missing | refused | `stats()` has no Sharpe ratio |

For row 2 the exit price used for repricing must be **at most the bar's open, 90** (for a long; the mirror for a short): a stop the price gapped through can't fill at the stop. If VectorBT reports 95, the wrapper corrects it to the open and the report says so.

**Every version counted.** A hypothesis with N = 0. A 1,000-point grid (`fast` × `slow` × `stop`, 10 × 10 × 10) on two years of synthetic hourly bars → `search_n == 1000` afterwards; every one of the 1,000 trials has a terminal event and, if `completed`, stored returns, trades and a footprint. A run interrupted after the first chunk (simulated by raising inside chunk 2) leaves `search_n == 1000` anyway (all were started before any ran) and the unfinished ones without a `completed` event.

**Open at the end.** A position still open at the window's last bar is closed at that bar's open and priced with its costs, so every P&L belongs to a closed trade.

**Gross numbers stay inside.** For a grid point with costs, the stored per-bar Sharpe equals `per_bar_sharpe(net_returns)` and **differs** from VectorBT's own `stats()` Sharpe on the same run. `run_grid`'s return value is a list of trial ids (type asserted).

**Kinds.** `run_point(kind=VERIFICATION)` with parameters that aren't a SEARCH trial of the hypothesis → refused; with a different window → refused; on an existing SEARCH point and its window → accepted, and `search_n` doesn't change. `run_point` has no `purpose` parameter (signature inspected).

**Identity.** For every stored trial: `Σ net_returns × capital` equals `Σ trade nets` to 1e-9 relative; `trade net = gross − all seven components` (B11's own check).

**Repricing.** A trade VectorBT reports from 100 to 110, one contract equivalent, priced by B16 by hand (use B16's worked example values) gives exactly B16's components.

**Door and seal.** A grid whose window ends after `2026-04-01T00:00Z` with `purpose="research"` is refused before any trial is started (so N doesn't rise for a run that never happened). The footprints' `max_timestamp_read` equals the open time of the last bar read.

**Look-ahead hook.** `signals` receives a frame whose last row is the last bar of the window plus nothing else; a strategy that reads `bars.shift(-1)` produces a column that is entirely missing at the last bar, and the wrapper refuses signals containing missing values. (B44 does the real hunting; this only refuses the crudest case.)

**Speed.** 1,000 points × 17,544 hourly bars in chunks of 200: time and peak memory recorded in the report. No pass mark: it is the baseline the next phases plan with.

## Not in this build
Look-ahead tests (B44) · the null (B45) · whole-contract sizing (B50) · VectorBT's own optimisers and its paid version · the real engine (after G3).

## Halt if
- Any of S32's five findings no longer holds on the resolved version.
- `vectorbt` or its `numba` doesn't install on the locked Python (3.14, V2-D45).
- VectorBT's trade records lack something repricing needs (entry and exit bar, side, size).
- The additive-return identity can't hold to 1e-9 because of how VectorBT reports positions: say why; don't widen the tolerance.

## For the gate
`COMPONENTS.md` §1 "VectorBT" (this build edits it): version, "used only through `screen/` (B43)". `BUILD_NOTES.md` §2: the re-check of S32 on the new version.
