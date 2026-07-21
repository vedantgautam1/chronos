# CHRONOS — Hephaestus Build Brief

**For:** Claude Code, operated by the developer (with the quant reviewing).
**Prerequisite:** `docs/SPEC_HEPHAESTUS.md` is the contract. Read it fully
before Phase 0. Where this brief and the spec disagree, the spec wins.
**Prerequisite:** Oceanus exists, is tested, and is the ONLY data source
(via `get_bars()`).

> **STATUS NOTE (updated 2026-07-08, see HANDOFF.md):** build in progress,
> spot-only per the founder's (reverted, then final) decision. Developer is
> operator/reviewer. Decisions table lives in HANDOFF.md.

## 0. READ THIS FIRST — working rules

1. This component is built by the developer, not the founder solo. The founder
   drafted Oceanus; the engine is where bugs go invisible (a look-ahead leak
   doesn't error — it produces a beautiful, false equity curve). If the
   founder is operating this brief without the developer, STOP and say so.
2. One phase at a time. Complete a phase, stop at its checkpoint, get
   confirmation, commit, then proceed. Never run ahead.
3. The spec's invariants are build-breaking. I1 (no future leakage), I2
   (costs always applied), I3 (every run logged), I5 (determinism), I6
   (every trial counted), I8 (hypothesis first). If an implementation choice
   conflicts with an invariant, the invariant wins.
4. Simple and auditable beats clever. The quant must be able to read the fill
   logic and the accounting in one sitting. No premature abstraction.
5. Tests alongside code, not after. Each phase lands with its tests. The
   invariant probes (Phase 7) are the component's definition of trustworthy.
6. Verify externals at build time. Exchange fee values come from the
   exchange's current published schedule (record source + date in config).
   Do not hardcode remembered numbers.
7. Flag decisions; don't silently choose. The spec §13 lists the founder
   decisions. If any are unresolved when needed, stop and ask. Record all of
   them in `HANDOFF.md` as they're made.
8. Scope wall. Do NOT build: validation statistics (Sharpe/DSR/walk-forward —
   those are the Moirai, the quant's domain), strategies beyond the test
   fixtures and the Phase 9 milestone, live trading, perps/funding (spot-only
   unless the founder has explicitly decided otherwise), or the full
   Mnemosyne (only its stub, Phase 6).
9. Data discipline. The engine imports from `chronos.oceanus.access` only.
   Importing `ccxt`, reading `data/` directly, or fetching anything from the
   network inside the engine is a violation (the one-door guard test must
   extend to cover the new module).

## PHASE 0 — Orientation and scaffolding
Goal: the engine's home exists; nothing is built yet.

Do:
* Read `docs/SPEC_HEPHAESTUS.md` end to end. Read Oceanus's `access.py`,
  `model.py`, and `HANDOFF.md` (its decisions — e.g. the numeric policy —
  bind here).
* Create the module skeleton:

```
src/chronos/hephaestus/
  __init__.py
  types.py        # Phase 1: Order, Fill, Position, BacktestResult
  view.py         # Phase 1: MarketView + Feed
  engine.py       # Phase 2: the event loop (execute is PRIVATE)
  broker.py       # Phase 3: fill logic
  costs.py        # Phase 4: CostModel
  portfolio.py    # Phase 5: accounting
  screener.py     # Phase 8: vectorized, UNTRUSTED
src/chronos/run.py        # Phase 6: run_experiment() — sole entry point
src/chronos/mnemosyne/
  stub.py         # Phase 6: append-only record store + trial counter
tests/hephaestus/
  fixtures/       # hand-computed accounting scenarios live here
  invariants/     # the probes (CI-required)
```

* Confirm founder decisions from spec §13 are answered (spot-only?,
  shorting?, remainder policy, numeric policy, initial capital, fee values,
  provisional slippage bps). List them in `HANDOFF.md`. Any unanswered →
  ask now.

CHECKPOINT: skeleton committed; decisions table in `HANDOFF.md` filled or
explicitly flagged as pending.
Commit: `chore(hephaestus): module skeleton and decisions record`

## PHASE 1 — Core types and the bounded view
Goal: the vocabulary of the engine, and the structural I1 guarantee.

Do:
* Implement `types.py` per spec §2: Order, Fill, Position, BacktestResult.
  Order IDs are deterministic (a per-run counter — never wall-clock or uuid4).
* Implement `MarketView` + `Feed` per spec §3: the view exposes `now` and
  `bars(symbol, lookback)` returning only bars whose close (open_time +
  timeframe) is ≤ now. The strategy receives a protected copy — it cannot
  reach the full series or mutate shared state.
* Define the `Strategy` Protocol and `Context` (injected seeded RNG,
  read-only portfolio snapshot, params).

Tests:
* A view constructed at time t refuses to serve the bar that closes after t
  (the still-open bar case is already excluded by Oceanus, but the view must
  also bound historical slices correctly at every t).
* Mutating the returned frame does not affect the engine's copy.

CHECKPOINT: tests green; a short plain-English note in `HANDOFF.md` on how
the view achieves the bound (the quant will audit this first).
Commit: `feat(hephaestus): core types and time-bounded MarketView`

## PHASE 2 — The event loop
Goal: the spine: bars in, strict per-bar sequence, orders out.

Do: implement `engine.py` exactly per spec §4's seven-step sequence: advance
clock → broker processes t−1 orders against bar t → portfolio applies fills →
feed builds view at t → strategy emits orders (stamped t) → mark to market at
close(t) → next bar. The execute function is module-private (name-mangled or
underscore + enforced by the Phase 6/7 logging probe). End-of-data: last-bar
orders expire and are recorded.

Use a trivial hardcoded do-nothing strategy and a buy-once strategy as
loop-exercising fixtures (not real strategies — test scaffolding).

Tests:
* Order created at t never fills before t+1.
* Expired last-bar order appears in the result as expired, not dropped.
* The loop processes an Oceanus-served range end to end without error.

CHECKPOINT: the loop runs over a real month of BTC/USDT 1h data from
`get_bars()` with the do-nothing strategy; equity curve equals flat initial
capital (no trades, no costs — this also pre-validates Phase 5's identity).
Commit: `feat(hephaestus): event loop with next-bar execution`

## PHASE 3 — The simulated broker
Goal: honest fills.

Do: implement `broker.py` per spec §5:
* Market orders: fill at open(t+1) (price adjustment deferred to Phase 4 —
  broker calls the cost model even now; wire a temporary passthrough
  CostModel so the I2 path exists from the first fill).
* Participation cap (config; conservative default) → partial fills;
  remainder per the founder's decided policy (cancel-and-record recommended).
* Limit orders: conservative trade-through convention (buy fills iff
  low(t+1) < limit, at limit). Touch ≠ fill. Optimistic mode only behind an
  explicit flag that lands in `warnings`.
* Rejections (insufficient cash; selling more than held under spot-only;
  zero-volume bar) are recorded events.

Tests: each convention above has a direct test, including: partial fill math
against the cap; buy-limit at exactly `low == limit` does NOT fill; rejection
events recorded with reasons.

CHECKPOINT: a scripted scenario (crafted small dataset) where the person
running can see: one full fill, one partial fill with recorded remainder, one
limit that correctly does not fill on a touch, one rejection.
Commit: `feat(hephaestus): broker with participation-capped fills and conservative limits`

## PHASE 4 — The cost model (I2 becomes real)
Goal: no fill without cost.

Do: implement `costs.py` per spec §6:
* `fee(side, notional)` from configured maker/taker bps (taker default for
  market orders). Fee values verified from the exchange's current published
  schedule; source URL + retrieval date recorded in the config file.
* `spread(bar)` as configured half-spread bps per side (documented as an
  approximation).
* `slippage(order, bar, participation)` — fixed-bps first, interface ready
  for a size-aware model. Stamp `provisional_cost_constants=True` into every
  result's warnings while defaults are in use (spec R6 discipline).
* Spot-only: `funding()` raises NotImplementedError with a clear message
  (unless the founder decided otherwise — then stop, the spec must be
  extended first).
* Replace Phase 3's passthrough: the broker now cannot construct a Fill
  without the model's outputs; there is no bypass parameter.

Tests: fee/spread/slippage each verified against hand-computed values on a
known notional; a grep/import-level test that `broker.py` has no fill path
that skips `CostModel`.

CHECKPOINT: the same Phase 3 scenario re-run now shows itemized costs on
every fill, and the zero-vs-nonzero cost runs visibly differ.
Commit: `feat(hephaestus): cost model wired into every fill (I2)`

## PHASE 5 — Portfolio, accounting, and the hand-computed fixtures
Goal: accounting that reconciles exactly.

Do: implement `portfolio.py` per spec §7 under the decided numeric policy
(recommended: Decimal ledger, float series):
* cash / positions / realized PnL / itemized cumulative costs;
* equity[t] = cash + Σ qty × close(t) at every bar close;
* per-bar returns derived once, here;
* the reconciliation identity checked (in debug/test mode) at every bar.

The fixtures (the heart of this phase): at least three micro-scenarios
computed by hand, with the full derivation written in the test file as
comments (the quant reviews the derivations, not just the asserts):
1. Single buy, hold, mark over 3 bars — exact cash/equity at each bar.
2. Buy then sell with fees + slippage — exact realized PnL and cost totals.
3. Partial fill scenario — exact position and remainder accounting.

Tests: the fixtures pass exactly under the numeric policy; the reconciliation
identity holds on every fixture at every bar.

CHECKPOINT: the founder can follow fixture 1's hand-derivation and see the
engine produce the same numbers to the cent.
Commit: `feat(hephaestus): exact accounting with hand-computed fixtures`

## PHASE 6 — run_experiment() and the Mnemosyne stub (I3, I6, I8)
Goal: the seam to the rest of Chronos; no unlogged runs, ever.

Do:
* `mnemosyne/stub.py`: an append-only record store (JSONL or Parquet) + a
  monotonic trial counter persisted across runs. Records are immutable — no
  update path exists. (Full Mnemosyne schema arrives later as its own
  component; the invariants are NOT deferred.)
* `run.py`: `run_experiment(strategy, config, hypothesis) -> RunRecord`:
   * refuses to run without a hypothesis object (I8) — the hypothesis is
     persisted before execution;
   * increments the trial counter before execution (I6) — errored runs count;
   * executes inside try/finally — a record is written on every exit path,
     with status COMPLETED or ERRORED (I3);
   * stamps core git SHA, config hash, Oceanus snapshot hash, and seed into
     the record (I5 coordinates);
   * the engine's execute is unreachable publicly — this is the only door.

Tests: run-without-hypothesis raises; an exception mid-run still yields a
persisted ERRORED record; N runs advance the counter by exactly N; records
resist mutation.

CHECKPOINT: two real runs appear in the store with full coordinates; a
deliberately-crashed run appears as ERRORED; the counter reads correctly.
Commit: `feat: run_experiment sole entry with append-only records and trial counting`

## PHASE 7 — The invariant probes (the trust suite)
Goal: the engine proves it can't lie. CI-required from here on.

Do: implement spec §9's probes as tests under `tests/hephaestus/invariants/`:
1. Poisoned-future (I1) — poison beyond a cut, run to the cut, byte-compare.
2. No-cost-path (I2).
3. Determinism (I5) — byte-identical serialized results on identical
   coordinates; run it twice in CI to catch machine-dependence.
4. Logging (I3) and 5. Trial-count (I6) — extend Phase 6's tests into probes.
6. Reconciliation — the identity across all fixtures.
7. Unsafe-flag — `unsafe_same_bar_fill` stamps warnings; default never does.

Wire CI so these + the Oceanus one-door guard (extended to cover hephaestus
imports) are required checks on the engine's protected paths.

CHECKPOINT: full suite green in CI; a deliberately-introduced future leak
(temporarily added, then reverted, as a meta-test) is caught by probe 1 —
demonstrating the probe actually detects what it claims to.
Commit: `test(hephaestus): invariant probe suite, CI-required`

## PHASE 8 — The vectorized screener (separate and untrusted)
Goal: fast idea-killing, clearly quarantined.

Do: `screener.py` per spec §11 — whole-series array computation, shares cost
parameters, banner comment UNTRUSTED at the top, API named so misuse is
awkward (e.g. `screen_only_never_promote()`), results logged as screen
events, not trials (or as trials if the quant so decided — the decision must
be in `HANDOFF.md` by now).

Tests: the screener's output type cannot be passed where a `BacktestResult`
is expected (type-level separation).

CHECKPOINT: screener runs a parameter sweep over the milestone strategy in
seconds and rejects the obviously-dead region.
Commit: `feat(hephaestus): quarantined vectorized screener`

## PHASE 9 — The end-to-end milestone
Goal: the Stage 0 definition-of-done run.

Do: a moving-average-crossover strategy (as a real Strategy implementation),
a pre-registered hypothesis for it, and one command that runs it end to end:
Oceanus data → run_experiment → full costs → BacktestResult → persisted
record. The expected outcome is an unremarkable or losing result — that is
success. The point is a truthful instrument, not a profitable crossover.

CHECKPOINT: the command runs; the record persists with all coordinates; the
equity curve renders; costs are itemized; the founder can narrate what
happened at each stage.
Commit: `feat: end-to-end MA-crossover milestone through run_experiment`

## PHASE 10 — Handoff to the quant
Goal: the quant can start the Moirai against a stable contract.

Do: update `HANDOFF.md` with: every decision and its rationale; the exact
`BacktestResult` contract as built (fields, types); how to re-invoke runs
over sub-ranges (what walk-forward will need); every open question and every
place external facts were verified (fee schedule source/date); known
limitations (spread approximation, provisional slippage constants and their
values, spot-only scope).

CHECKPOINT: the quant reads `HANDOFF.md` + spec §10 and confirms the result
object is sufficient for the planned gauntlet, or files what's missing.
Commit: `docs(hephaestus): handoff for Moirai construction`

## Definition of done (whole component)

* [ ] All seven invariant probes green and CI-required.
* [ ] Hand-computed accounting fixtures pass exactly; derivations reviewed by
      the quant.
* [ ] No public path to execution except `run_experiment()`.
* [ ] Every result carries coordinates (SHA, config hash, snapshot hash,
      seed) and honest warnings.
* [ ] One-door guard extended: nothing in hephaestus imports ccxt or touches
      `data/`.
* [ ] Milestone run persisted end to end.
* [ ] `HANDOFF.md` complete; founder decisions all recorded.

Start at Phase 0. Stop at every checkpoint.
