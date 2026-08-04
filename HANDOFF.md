# HANDOFF

## PROJECT SCOPE & JESSE INTEGRATION — decisions of 2026-07-28

**2026-07-28.** Full comparative audit of `jesse-ai/jesse` (v2.4.1, MIT,
full source clone) against this repo, requested by the founder. The
complete analysis lives in `docs/JESSE_INTEGRATION_MASTER_PLAN.md`
(committed same date). Founder decisions recorded here; per STATE.md
precedence, this entry supersedes older planning language where they
conflict.

1. **Scope clarified — Chronos is the whole trading system, not a
   research project.** End state: research → backtesting → journaling
   (Mnemosyne) → live simulation → live trading → risk monitoring
   (Themis/Nemesis/Argus). This was always the Stage-2 roadmap; the
   "instrument honest enough to reject almost everything" framing
   describes Stage 0's rigor and is unchanged as a build discipline.

2. **Jesse is NOT adopted as the backtester.** Verified in source: the
   Jesse engine has no slippage model, no spread, no participation cap,
   no liquidity check — market orders fill at the touched price with a
   flat fee only. Its optimizer selects the max of hundreds of Optuna
   trials with zero selection-bias accounting (the exact N-laundering
   quantified in SESSION_FINDINGS.md). Its live plugin is closed-source
   and license-keyed. Hephaestus remains the trust core.

3. **Architecture decision: "Chronos core + rail TBD."** The Stage-2
   execution rail — build Hermes in-house vs adopt Jesse's licensed live
   plugin as the execution layer for Chronos-validated strategies — is
   deliberately DEFERRED until the gauntlet passes a deployable
   candidate. Do not re-open before then.

4. **Moirai scope decision: Moirai-lite first.** v1 gauntlet = DSR at
   honest N (`compute_search_n`) + walk-forward + cost-sensitivity +
   signal-only null gate (see item 5). The full touchstone ladder,
   seeded-realization calibration, and published power curve move to
   Moirai v2. Gate 0→1's touchstone/power-curve checklist items are
   re-cut to v2 accordingly. Rationale: founder wants a
   capital-protecting gate on the shortest honest path to Stage 2;
   the 2026-07-18 Moirai handoff remains the v2 spec source.

5. **Jesse integration plan adopted** (full detail, J1–J13 with
   verification notes, in the plan doc). Summary of what enters and when:
   - **Phase M (now, into the Moirai-lite spec, as ideas only):**
     signal-only null test (re-derived on R5's stationary bootstrap, NOT
     Jesse's i.i.d. resampling), trade-order-shuffle Monte Carlo, and
     the candle-pipeline harness pattern (as the v2 calibration
     mechanism; synthetic data enters via a marked test-fixture door,
     never a second data path — I7).
   - **Phase E1 (post-gate):** Oceanus stores 1m as ground truth; all
     higher timeframes derived by one tested aggregation function.
   - **Phase E2 (after E1):** intrabar fill resolution — broker walks 1m
     candles between decisions; strict trade-through at 1m; protective
     stops become expressible; ambiguous same-bar sequences resolve to
     the ADVERSE ordering. Protected path; hand-computed fixtures.
   - **Phase E3:** Mnemosyne hardening THEN parallel `run_experiment`
     (workers → single writer; every point `kind=SEARCH` under one
     registered hypothesis). Chosen store: SQLite (ACID, autoincrement
     trial index); `flock` locking acceptable as a quick fix. The
     current JSONL stub is single-process only — two parallel workers
     would duplicate trial indices (I6 violation) and interleave
     appends.
   - **Phase E4:** descriptive-metrics battery + vetted indicator subset
     (reporting only — nothing enters verdicts without a register
     entry); Oceanus exchange touchpoint behind a small CandleSource
     protocol.
   - **Phase L (Stage 2):** Jesse's OSS driver interfaces and
     forming-candle semantics as reference material for the rail
     decision (item 3).
   - **Rejected outright:** Jesse's global mutable store, optimizer
     fitness methodology, unlogged `research.backtest()` pattern, web
     dashboard layer, unsourced statistics in verdicts, fantasy-fill
     model. **No Jesse code import ever ships in `src/chronos/`** —
     patterns are re-derived under the invariants; licensing surface
     stays zero.

6. **Barriers assessed (plan doc §1):** MIT license — no restriction on
   patterns; compute — no barrier at any planned scale (heaviest
   workload is an overnight laptop job or ~$1–3 cloud burst); running
   costs ≈ $0 through Stage 1, VPS-scale at Stage 2. The real
   constraints: Mnemosyne single-process (item 5/E3), team bandwidth,
   and scope-creep risk — which this entry's phase gating exists to
   contain.

## HEPHAESTUS (engine) — status: BUILD COMPLETE, awaiting dev+quant review

**2026-07-08.** The developer is confirmed as operator/reviewer of this
build (brief working rule 1). All spec §13 founder decisions are resolved:

| # | Decision | Founder's choice | Notes |
|---|---|---|---|
| 1 | Spot-only for Stage 0? | **Yes — spot-only** | Founder initially chose perps+shorting (2026-07-08), which halted the build per spec §6; same day, after the scope cost was laid out, reverted to spot-only. Perps remain a possible later stage on an extended spec. `funding()` is stubbed to raise NotImplementedError. |
| 2 | Shorting allowed? | **No** | Implied by spot-only. Sell-more-than-held is a recorded rejection. |
| 3 | Unfilled remainder | **Cancel-and-record** | No order state carried between bars; strategy may re-order. |
| 4 | Numeric policy | **Decimal ledger + float series** | Cash/fees/realized PnL in Decimal (exact, to-the-cent reconciliation); price series and returns float64, matching Oceanus. |
| 5 | Initial capital | **10,000 USDT** | Arbitrary but fixed; recorded in run config. |
| 6 | Fee values | **Deferred to Phase 4** build-time verification per spec — Binance spot maker/taker bps from the published schedule, source URL + date recorded in config. | Explicitly pending, per the Phase 0 checkpoint's allowance. |
| 7 | Provisional slippage | **10 bps** (conservative end) | Provisional constant per R6 discipline: flagged in every result's warnings, stress-tested 2×/5× by the Moirai, replaced with measured values at Stage 2. |

**Phase 0 (2026-07-08):** module skeleton created (`src/chronos/hephaestus/`,
`src/chronos/run.py`, `src/chronos/mnemosyne/stub.py`, `tests/hephaestus/`);
no logic yet. Note for Phase 7: the existing Oceanus one-door guard
(`test_acceptance_5`) already scans ALL of `src/` outside `oceanus/`, so the
new hephaestus modules are covered by it automatically from day one — the
Phase 7 work is to extend it for engine-specific rules (e.g. no public
execute path), not to add basic coverage.

**Phase 1 (2026-07-08):** `types.py` (Order/Fill/Position/BacktestResult +
OrderEvent for rejections/expiries/cancellations; Decimal ledger types with
`to_decimal()` as the single float→Decimal crossing; `OrderIdSequence`
counter for deterministic ids) and `view.py` (MarketView + Feed + Strategy
protocol + Context). 19 tests.

**How the MarketView bound works (for the quant's audit — the I1 core):**
the Feed owns the full series and, at each decision time t, cuts it BY
POSITION at the number of bars whose close time (open_time + timeframe) is
≤ t, found by binary search on a precomputed close-time column. The
MarketView is constructed from that prefix slice only. Consequences:
(1) the view never *contains* a future row — a strategy that reaches into
the view's private attributes finds nothing beyond t, because nothing
beyond t was ever put in (this is tested by white-box inspection);
(2) `bars(symbol, lookback)` returns a deep copy, so strategy-side
mutation cannot corrupt engine state (tested); (3) a bar closing exactly
at t IS visible (spec: `open_time + timeframe <= t`) and one second before
its close it is NOT (both tested, boundary-exact). The Feed also refuses
unsorted/duplicated input outright — engine data must come from
`get_bars()`, which guarantees both. Indicator warm-up leaks are excluded
by construction: there is no engine-side indicator facility; strategies
compute indicators from the bounded view only.

**Phase 2 (2026-07-08):** `engine.py` — the seven-step loop per spec §4,
`_execute()` module-private, broker/portfolio injected via protocols
(real ones land in Phases 3/5; tests use clearly-labeled scaffolding).
9 tests. Checkpoint ran 720 real 1h bars (June 2026, via `get_bars()`):
do-nothing strategy → equity exactly flat at 10,000; buy-once fixture →
fill lands at bar t+1's open to the cent. Notes for reviewers:
- **Timing semantics:** the strategy decides at the CLOSE of bar t
  (view bounded there); its orders are stamped `created_at = bar t's
  open_time` (bar identity) and processed against bar t+1. Orders sit in
  `pending` for exactly one iteration — there is no code path from
  decision to same-bar execution. `unsafe_same_bar_fill` exists in config
  (so the config hash covers it) but raises NotImplementedError until the
  broker phases.
- **The engine stamps order ids and created_at itself**, overwriting
  whatever the strategy wrote (forgery test included).
- **Stage 0 simplification:** multi-symbol runs require identical bar
  timestamps across symbols; anything else is refused, not aligned.
  Cross-symbol alignment is deliberately future work.

**Phase 3 (2026-07-08):** `broker.py` — participation-capped fills
(default 5% of bar volume), cancel-and-record remainders (founder
decision), conservative limit convention (strict trade-through: a buy
limit fills iff `low < limit`; a bare touch is NOT a fill; the
optimistic touch-fill variant sits behind a flag that stamps a warning
into the run), recorded rejections (zero-volume bar, insufficient cash,
oversell/no-shorting). `costs.py` holds the CostModel protocol + a
TEMPORARY zero-parameter passthrough so the I2 call path exists from the
first fill — Phase 4 replaces the numbers, never the path. 11 tests.
Broker calls the quant should audit:
- **Rejection is whole-order** for insufficient cash and oversell — no
  partial-to-affordability fills. Simple and conservative; a strategy
  wanting partial exposure must size its orders itself.
- **Intra-bar sequencing:** orders process in creation order; an earlier
  buy consumes cash a later buy may then lack (tested). Deterministic.
- **Untriggered limit orders die at end of bar** (REMAINDER_CANCELLED,
  "not traded through") under the no-carry policy — a strategy wanting a
  standing limit must re-emit it each bar.
- **Fills never price outside the bar's range** and never against zero
  volume; sells don't check cash (proceeds only add).

**Phase 4 (2026-07-08):** `costs.py` — the real `FixedBpsCostModel`
replaces the passthrough. The passthrough CLASS is gone entirely: probe
runs use the same model with zero parameters (`ZERO_COSTS`), which is
the spec's exact intent — no zero-cost path, only zero-cost parameters.
9 tests with hand-derived Decimal-exact expectations. Reviewer notes:
- **Fees verified at build time** (rule 6): Binance spot VIP-0 = 0.100%
  maker / 0.100% taker, retrieved 2026-07-08 from binance.com/en/fee/trading
  — full record in `configs/binance_fees.md`. BNB discount NOT assumed.
- **Taker is charged on every fill including limit fills** (conservative:
  maker ≤ taker on all published tiers). Maker bps sit in config unused,
  documented for the future.
- **Cost anatomy of a fill:** exec price = base ± (slippage + half-spread)
  per unit, adverse direction always (buys pay more, sells receive less);
  fee = taker bps on executed notional. All itemized on the Fill.
- **Provisional constants (R6):** slippage 10 bps (founder), half-spread
  1 bp (my placeholder — quant should sanity-check). Both are configured
  guesses; the `provisional_cost_constants` warning is stamped through
  broker → engine → result automatically. `funding()` raises (spot-only).
- **No-bypass is enforced statically:** a test AST-parses broker.py and
  asserts Fill is constructed in exactly one place and `cost_model` has
  no default. Plus the counting-spy test: every fill calls fee, slippage,
  and spread exactly once.

**Phase 5 (2026-07-08):** `portfolio.py` — the Decimal ledger. 8 tests
incl. 3 hand-derived fixtures (derivations written longhand in
`tests/hephaestus/fixtures/test_hand_computed.py` — QUANT: re-do these on
paper) + a full-real-stack engine run with the identity checked at all 48
bars. Accounting conventions the quant must sign off on:
- **Cost-basis tracking, not average-entry.** avg_entry_price is derived
  for display only. The load-bearing property: any rounding in a partial
  sale's basis apportionment cancels between realized and unrealized, so
  the reconciliation identity holds EXACTLY (no tolerance) under Decimal.
  Selling the full holding takes the whole basis (no division residue).
- **The identity's cost term is FEES ONLY:**
  `equity == initial_cash + realized + unrealized − fees_paid`.
  Slippage and spread are embedded in execution prices, so they already
  live inside realized/unrealized PnL — adding them to the cost term
  would double-count. They remain itemized (slippage_paid/spread_paid)
  for the cost summary as attribution, not cash flows.
- **Identity checked at EVERY mark, always-on** (`check_identity=True`
  default); violation raises AccountingDriftError immediately.
- **Returns are derived once, here** (`returns_from_equity`): simple
  returns, first bar = 0.0 by convention, keeping the series aligned
  with the equity curve. The Moirai must not recompute returns their own
  way.
- Fee accounting: fees are expensed (cash out), never capitalized into
  basis — standard treatment, keeps basis = pure execution cost.

**Phase 6 (2026-07-08):** `run.py` (`run_experiment`, `Hypothesis`,
`RunConfig`, `serialize_result`) + `mnemosyne/stub.py` (append-only JSONL
store + persistent trial counter). 10 tests. Reviewer notes:
- **I8:** no Hypothesis object → TypeError before anything happens; the
  hypothesis record is appended BEFORE execution (test asserts ordering).
- **I6:** counter persisted to disk and advanced before execution;
  crashed runs count. Store's whole write surface is append+read — no
  update/delete methods exist.
- **I3:** try/finally writes a run record on every exit path; a crash
  persists an ERRORED record with the error text, then re-raises.
- **I5 coordinates** on every record: core git SHA (with an honest
  `-dirty` suffix if the tree has uncommitted changes), sha256 config
  hash over a canonical serialization, Oceanus snapshot hash, seed.
  `serialize_result()` is the canonical no-wall-clock serialization the
  Phase 7 determinism probe byte-compares.
- **Private execute:** `_execute` requires a module-private token; only
  run.py (and tests, explicitly) pass it. Direct calls raise
  PermissionError. This guards accidental bypass; Phase 7 extends the
  static guard so no other module imports _execute/_RUN_TOKEN.
- **Limitations:** deleting `records/` resets the trial counter (single
  local store; real Mnemosyne later); single-process only, no file
  locking; run_id = trial index + hypothesis id (deterministic, no uuid).

**Phase 7 (2026-07-08):** `tests/hephaestus/invariants/test_probes.py` —
the seven probes + an engine-door guard; CI workflow in
`.github/workflows/tests.yml` (dev: mark it REQUIRED via branch
protection after pushing to GitHub). `unsafe_same_bar_fill` is now
implemented (fills at the decision bar's close; stamps a NON-PROMOTABLE
warning; default path never carries it — probe 7).

**The meta-test found two real defects — read this, it matters:**
1. **Probe 1 v1 was too weak.** A deliberately planted one-bar leak in
   the view PASSED the original probe: a leaked decision at bar cut−1
   first manifests AT the cut bar, outside the strictly-before-cut
   comparison window. Fixed by comparing recorded strategy DECISIONS
   (intent) up to the cut boundary, under both pump- and collapse-
   poisoned futures. The plant is now caught; the full
   plant → red → revert → green cycle was demonstrated.
2. **The ledger's exactness had a precision cliff.** Probe 1's collapse
   scenario (cash ~1e4 against dust positions ~1e-9) drifted the
   reconciliation identity by 5E-24: the partial-sale basis
   apportionment is a non-terminating division, and its rounded tail is
   absorbed at different magnitudes in realized PnL vs basis, breaking
   the cancellation. Raising Decimal precision only moved the drift
   (1E-46 at 50 digits). Real fix: `LEDGER_QUANTUM = 1E-30` — the
   apportionment is quantized onto a fixed grid (making it exactly
   representable) + `LEDGER_PRECISION = 50` headroom so all sums stay
   exact. QUANT: verify this reasoning; it is the numeric policy's
   sharpest edge. Any future ledger value born from a division must be
   quantized the same way.

**Determinism probe nuance:** run_id and trial_index legitimately advance
between runs (I6 requires it), so the byte-compare uses
`determinism_view()` — the serialized result minus exactly those two
bookkeeping fields. Everything else must be byte-identical.

**Phase 8 (2026-07-08):** `screener.py` — vectorized MA-crossover sweep,
UNTRUSTED banner, `screen_only_never_promote()`. Shares cost parameters
as a flat per-side fraction charged on every position change; signals
shift one bar (even the crude path avoids same-bar leakage). Verdicts:
degenerate / never-trades / loses-after-costs / "MAY deserve a real
engine run — not evidence of anything." `ScreenVerdict` is type-level
quarantined (cannot pass where BacktestResult is expected; test).
Screens log as `type: "screen"` events and do NOT advance the trial
counter. 6 tests. 280-pair sweep over 720 real bars: 0.06s.
- **PENDING QUANT DECISION:** screens-as-non-trials is implemented per
  the spec's recommendation (only full evaluations feed selection). The
  conservative alternative — counting screens in the DSR trial count —
  is a one-line change (call `store.next_trial_index()` per screen).
  Quant to confirm or overrule; record the outcome here.

**Phase 9 (2026-07-08):** the end-to-end milestone.
`strategies/ma_crossover.py` (state-based long-only 20/50 crossover,
indicator math from the bounded view only, satoshi-grid order sizing) +
`scripts/run_milestone.py` (the one command). 4 tests. Live result on
six months of real BTC/USDT 1h (4,344 bars): **-15.40% net** — 84 fills,
1,588.55 USDT total itemized costs (fees 756.45 / slippage 756.45 /
spread 75.65), zero rejections, persisted as trial #4 with full
coordinates. A losing result was the registered prediction: the
milestone proves the instrument, not the idea. Note the run's
`core_version` carries `-dirty` (milestone files were uncommitted when
it ran) — the honesty mechanism working as designed; re-run after this
commit for a clean SHA.

### FOR THE QUANT — everything needed to start the Moirai

**The `BacktestResult` contract, exactly as built** (`hephaestus/types.py`):

| Field | Type | Notes |
|---|---|---|
| run_id | str | `{trial:06d}-{hypothesis_id}`, deterministic |
| core_version | str | git SHA, `-dirty` suffix if uncommitted changes |
| config_hash | str | sha256 of canonical RunConfig serialization |
| data_snapshot_hash | str | Oceanus content hash of the exact bars used |
| seed | int | the run's single RNG seed |
| bars_processed | int | |
| date_range | (datetime, datetime) | the requested [start, end), UTC |
| symbols | tuple[str, ...] | Stage 0: length 1 |
| timeframe | str | e.g. "1h" |
| trades | tuple[Fill, ...] | Fill: order_id, symbol, side, qty_filled (Decimal), price (Decimal, cost-adjusted), fee / slippage_cost / spread_cost (Decimal, itemized), bar_time (UTC) |
| order_events | tuple[OrderEvent, ...] | REJECTED / EXPIRED / REMAINDER_CANCELLED, with reasons — the full story of unexecuted intent |
| equity_curve | pd.Series float64 | indexed by bar open_time (UTC), marked at close |
| returns | pd.Series float64 | simple returns from equity, first bar = 0.0, derived ONCE (`returns_from_equity`) — do not recompute differently |
| cost_summary | CostSummary | fees / slippage / spread Decimals + `.total` |
| warnings | tuple[str, ...] | non-promotable flags, provisional-cost flag |
| hypothesis_id, trial_index | str, int | the I8 / I6 links |

`serialize_result(result)` is the canonical wall-clock-free JSON;
`determinism_view(serialized)` strips run_id/trial_index — the only two
fields that legitimately differ between runs at identical coordinates.

**Walk-forward recipe** (what spec §10 promises you): one
`run_experiment` call per window, same strategy, sub-range config.
Windows share a hypothesis; every window is a separately counted,
separately recorded trial:

```python
from dataclasses import replace
for win_start, win_end in windows:
    cfg = replace(base_config, start=win_start, end=win_end)
    record = run_experiment(strategy, cfg, hypothesis)
```

Oceanus serves sub-ranges from its disk cache after the first fetch, so
window re-runs cost no network. **Cost sensitivity** (mandatory, R6):

```python
stressed = replace(base_config, cost=CostConfig(
    taker_fee_bps=Decimal("20"), slippage_bps=Decimal("20"),
    half_spread_bps=Decimal("2")))   # 2x baseline; likewise 5x
```

**Moirai sufficiency check (spec §10):** walk-forward → cheap sub-range
re-invocation ✓; cost-sensitivity → cost params exposed in RunConfig ✓;
Deflated Sharpe → persistent trial counter + per-bar returns ✓; regime
decomposition → timestamps on every fill, event, and equity point ✓.
Anything missing: file it against this section.

**External facts verified during the build** (working rule 6):
- Binance spot fees 0.100%/0.100% (VIP-0, no BNB discount assumed) —
  binance.com/en/fee/trading, retrieved 2026-07-08
  (`configs/binance_fees.md`).
- ccxt semantics verified against installed 4.5.64 plus live calls
  (fetch_ohlcv pagination, fetch_time).
- Binance/Coinbase/OKX public endpoints probed live from this machine.

**Known limitations (consolidated):**
- Spread is a modeled 1 bp half-spread (no order book at bar
  granularity); slippage a provisional flat 10 bps (R6 — awaits real
  Stage-2 fills). Every result carries the warning until measured.
- Taker fee charged on ALL fills, including resting limits (conservative).
- Spot-only, long-only, single venue; multi-symbol runs require
  identical bar timestamps (refused otherwise, never aligned).
- No intra-bar path modeling: fills at opens (market) or limit prices
  (trade-through); a bar's internal sequence is unknowable from OHLCV.
- Participation cap 5% of bar volume by default; unfilled remainders
  cancel — no order state carries between bars.
- Equity marked at closes only; intra-bar drawdown is invisible.
- `records/` is a local stub: deleting it resets the trial counter;
  single-process, no locking. Real Mnemosyne owns durability later.
- CI workflow exists; required-check enforcement needs branch
  protection once the repo is pushed to GitHub.

**Decisions awaiting your sign-off** (detailed in the phase notes above):
the fees-only reconciliation convention; the basis-apportionment
cancellation and `LEDGER_QUANTUM = 1E-30`; the returns convention
(simple, first bar 0); screens-as-non-trials; the 1 bp half-spread
placeholder; Oceanus's 25% outlier threshold.

**2026-07-17 — SEARCH vs VERIFICATION run kind, and the N-ontology fix
it enables.** `run_experiment()` now takes a required `kind: RunKind`
argument (`SEARCH` or `VERIFICATION`), persisted on every 'run' record.
This does NOT touch the execution counter in `trial_counter.txt` — that
stays exactly as it was, still counting every execution (I6), still
conflating search points and standalone runs the same way it always
has. `kind` is a separate, narrower label read only by the new
`compute_search_n(hypothesis_id, store)`, which counts `SEARCH`-kind
records sharing a hypothesis_id — giving DSR the honest N for a
candidate pulled from a search (see `SESSION_FINDINGS.md` for the
concrete N=1-vs-N=280 case, fast=25/slow=60, that motivated this).
`register_search(hypothesis, param_grid_description)` is the companion
helper: call it once before a sweep, reuse the returned Hypothesis
across every call in that search, and the grid shape gets persisted
into every 'hypothesis' record alongside statement/prediction.

**Records 1–284 predate this distinction and carry no `kind` field at
all — do not backfill or guess one for them.** They are legacy: written
before `SEARCH`/`VERIFICATION` existed, and `compute_search_n()`
already excludes them correctly (a missing `kind` never matches
`RunKind.SEARCH.value`). Treat them as un-labeled history, not as data
to retrofit. This does not resolve the broader I6 trial-ontology
question (the execution counter itself still does not distinguish
search points from standalone runs) — that remains open, as recorded
above; `kind`/`compute_search_n()` is a narrower, additive fix scoped
to what DSR's N specifically needs.

**2026-07-17 — I5 expanded from four coordinates to five: candidate_n
joins the reproducibility tuple.** `determinism_view()` used to strip
`trial_index` and compare everything else byte-for-byte. That is no
longer sufficient now that the gauntlet exists: `trial_index` feeds
DSR (via `compute_search_n()`), and `trial_index` legitimately differs
between two runs that are otherwise identical. `determinism_view()` now
takes the `RecordStore` and adds a `candidate_n` field — the value
`compute_search_n()` reports for that result's `hypothesis_id` at the
moment the view is taken — before comparing. Two runs are the same
determinism claim iff they share (core git SHA, config hash, data
snapshot hash, seed, candidate_n). A difference in candidate_n is not
flagged as a determinism failure by this probe; it is the correct,
separate signal that the two runs were drawn from searches of
different breadth. Probe 3 (`test_probes.py`) now asserts both: same
five coordinates -> byte-identical view; a search advancing between
two SEARCH-kind runs of the same hypothesis -> differing candidate_n,
acknowledged as legitimate, not raised as a failure.

**2026-07-17 — I9 proposed: gauntlet_config_hash anchor field.**
`RunConfig` gains an optional `gauntlet_config_hash: str | None = None`,
persisted on every 'run' record alongside `config_hash`. This is
purely an anchor point, not enforcement: when the Moirai (the judge)
exists, changing a gauntlet threshold becomes a protected-path commit
requiring full CI plus human review, and it must visibly invalidate
every prior verdict stamped with the old hash — the same way
`core_version` already does for engine-code changes. Nothing in
run.py enforces that yet; this field just gives the Moirai something
to stamp and compare against once it exists. Purely additive: default
`None` means every existing `RunConfig(...)` call site is unchanged.

**2026-07-17 — Oceanus data-quality warnings now structured and
propagated into run records (I3 gap closed).** `get_bars()` gains an
optional `warnings_collector: list | None = None` parameter. When
provided, soft data-quality notices (gaps, outliers) are appended as
structured strings (`[data-quality/gap] ...`) instead of printed to
stdout. `run_experiment()` passes a collector and merges the results
into `BacktestResult.warnings` alongside the existing engine honesty
flags. Without a collector (every existing call site), behavior is
unchanged — warnings still print, preserving interactive script use.
This closes the I3 gap: a 600-run sweep now has data-quality facts on
the record, not scrolling past in a terminal nobody watches.

**2026-07-17 — Stage 0 spec amendments (HEPHAESTUS_SPEC.md).** Four
changes: (1) §1 I5 expanded to five coordinates (code SHA, config hash,
data snapshot hash, seed, candidate_n); I6 now distinguishes
SEARCH/VERIFICATION via RunKind; I9 added (judge is fixed before the
trial — gauntlet_config_hash anchor, enforcement deferred to Moirai).
(2) §10 updated: DSR needs compute_search_n(), not the global trial
counter. (3) New §15–§16 split the register into Derive-From-Source
(R1–R5, methods with primary sources) and Assumptions (R6–R7, plausible
numbers without derivations); R7 demoted not closed. (4) New Appendix A
with metric definitions resolves the annualized-vs-native Sharpe
contradiction: DSR/PSR operate on the non-annualized Sharpe at native
frequency; annualization is reporting-only, applied after the verdict,
subject to R3's Lo (2002) correction for non-i.i.d. returns.

**2026-07-17 — R6 (slippage) measured; default 10bps → 1bps.** Method:
streamed 6 months of real Binance BTC/USDT aggTrades (Jan–Jun 2026,
4,344 hourly bars) directly out of their monthly ZIPs (never extracted
to disk — `zipfile` + `pd.read_csv` on the in-memory stream), simulating
a market BUY at each hour's open against taker-side (`is_buyer_maker ==
False`) trades only. Zero bars had insufficient liquidity to fill either
a 9,000 USDT or a 90,000 USDT order — this pair is deep enough at both
sizes. Raw result: mean -0.68bps / median 0.00bps / std 1.53bps at 9k;
mean -0.94bps / median -0.08bps / std 2.70bps at 90k.

**The drift confound (why p95 was not used as the anchor):** BTC/USDT
fell ~33% over the measurement window (Jan 1 ≈ $87,648 → Jun 30 ≈
$58,625). Comparing each fill's VWAP against the hour's *first*-trade
price entangles genuine market impact with intra-hour price drift — a
larger order takes longer to fill, so it samples more of the downward
drift, which is why the 90k mean/p95 are *more negative*, not more
positive, than 9k's (backwards from what pure impact would predict).
This confound affects BOTH tails, not just the mean — p95 (0.66bps at
9k, 2.40bps at 90k) is a drift-dominated worst case, not a clean impact
ceiling, so it was rejected as the anchor for the same reason the mean
was.

**Isolating size-dependent impact (difference estimator):** per-bar
(slip_90k − slip_9k) differences out the shared drift, since both order
sizes are measured against the same hour's same first-trade price.
Result: mean -0.27bps, **median 0.0019bps**, p5 -4.19bps, p95 2.34bps,
std 2.01bps. A near-zero median difference across a 10x size change
confirms true size-dependent impact is below this measurement's
resolution at these sizes — consistent with "true impact at 9k is
plausibly ~0.1bps."

**Limitation — buy-only:** this measurement only simulates market BUYs
against taker-side trades. Sell-side slippage was not measured and may
differ (asymmetric order book depth is common, especially during a
downtrend). The 1bps default is applied uniformly to both sides pending
that measurement.

**Decision:** `CostConfig.slippage_bps` default changed 10 → 1
(`src/chronos/hephaestus/costs.py`). Justification: raw distribution is
drift-dominated (median 0.00bps, std 1.53bps at 9k) — true impact is
below measurement resolution, plausibly ~0.1bps. 1bps gives roughly a
10x margin over that plausible impact without manufacturing false
negatives the way the old 10bps (nearly half the ~42bps round-trip cost
hurdle) risked doing. `provisional_constants` stays `True` — the
measured value is still drift-confounded, not a clean impact number, so
the Moirai's 2×/5× cost-sensitivity test remains required.

**Cross-comparability boundary:** every record with `trial_index <= 284`
(trial #4 through the 280-point sweep) was produced under the OLD 10bps
value and is NOT cost-comparable with any run after this commit without
re-running. Concretely: trial #4's registered -15.40% net result used
756.45 USDT of slippage cost at 10bps; rescaling that line item linearly
to 1bps (75.65 USDT; fees and spread unchanged) gives a recomputed net
of approximately **-8.6% ("~-9%")** — still a loss, so the milestone's
registered prediction (losing result, proving the instrument not the
idea) still holds. This is a linear rescaling of the itemized cost
breakdown, not a fresh engine run — an exact re-run would be needed for
an authoritative number, since costs interact with cash-sufficiency
checks in ways linear rescaling can't fully capture. `SESSION_FINDINGS.md`
updated to record this.

**Deferred to Stage 2:** drift-neutral re-measurement (referencing each
fill's VWAP against a mid-price captured at order-entry time rather than
the hour's first trade, and measuring both book sides) would isolate
impact cleanly. Not attempted here — the difference estimator above is
a sufficient stopgap for setting the default, not a replacement for that
re-measurement.

**Evidence:** `measure_slippage.py` (repo root); raw per-bar arrays at
`data/aggtrades/measured_slippage_9k_bps.npy` and `_90k_bps.npy`
(untracked — regenerable from the aggTrades ZIPs, not committed).

---

# HANDOFF — Oceanus

Notes for the developer and quant who will review this build.
Records what was built phase by phase, every decision that was flagged
to the founder (and what they chose), every open question, and what was
deliberately left for you.

**Orientation, 30 seconds:** the whole component is
`src/chronos/oceanus/` — six small modules, read them in phase order
(`model` → `ingest` → `store` → `validate` → `clean` → `access`). The
public surface is `access.get_bars()` and `access.universe_at()`;
everything else is internal, and `tests/oceanus/test_acceptance.py` is
the contract. The git history mirrors the phases one commit each.
Built by Claude Code (an AI) pair-working with the founder, who is
non-technical: expect deliberately simple, heavily-commented code —
readability was chosen over cleverness throughout. Review skeptically;
nothing here is sacred.

## Build log

- **Phase 0 — Project setup** (2026-07-07): git repo, `uv`-managed Python
  project (lockfile: `uv.lock`), src-layout package structure, dependencies
  pinned to exactly what Oceanus needs (ccxt, pandas, numpy, pyarrow,
  matplotlib, pytest). `data/` is gitignored.
- **Phase 1 — Bar data model** (2026-07-07): `model.py` defines `Timeframe`
  (fixed enum: 1m/5m/15m/1h/4h/1d, each knowing its duration) and `Bar`, an
  immutable dataclass that validates itself at creation — tz-aware UTC
  timestamps required, positive prices, `low <= open,close <= high`,
  `volume >= 0`, and an `is_final` flag for still-forming bars. An invalid
  Bar cannot be constructed. 11 tests in `tests/oceanus/test_model.py`.
- **Phase 2 — Ingestion** (2026-07-07): `ingest.py` fetches OHLCV via ccxt
  (verified against installed ccxt 4.5.64: `fetch_ohlcv(symbol, timeframe,
  since_ms, limit, params)`; rate limiting on by default). Paginates 1000
  bars/page, retries transient network errors with exponential backoff,
  filters to a half-open `[start, end)` window, sorts, de-duplicates, and
  marks the still-forming bar `is_final=False` by comparing
  `open_time + duration` to current UTC. Tested against a fake exchange
  (8 tests) plus a live checkpoint run against real Binance data.
- **Phase 3 — Storage** (2026-07-07): `store.py` persists bars as Parquet
  under `data/bars/<symbol>/<timeframe>/vNNNN.parquet`. `get_range()` is the
  load-if-present path (fetches only missing edge ranges). `snapshot_hash()`
  is a SHA-256 over a canonical text form of the data. 8 tests, no network.
- **Phase 4 — Validation** (2026-07-07): `validate.py` — pure function,
  detects gaps, duplicates, out-of-order timestamps, OHLC violations,
  impossible values, naive timestamps, and outliers; returns a
  plain-English `ValidationReport`; never alters the data. A corrupted
  fixture (`tests/oceanus/corrupted_fixture.py`) plants one of each
  problem; a test asserts every one is caught. 7 tests. The real 168-bar
  BTC/USDT week validated clean.
- **Phase 5 — Cleaning** (2026-07-08): `clean.py` — `clean(frame, policy)`
  applies the founder's chosen policy (below) to a copy of the data and
  reports every change it makes. Gap-filling raises an error by design.
  7 tests.
- **Phase 6 — Access door** (2026-07-08): `access.py` — `get_bars()` serves
  only completed (`is_final`) bars, validated/sorted/de-duplicated/UTC;
  raises `DataIntegrityError` on corrupt ranges; optional `snapshot=`
  pins a request to an exact data hash. `universe_at()` gives the
  point-in-time symbol set. 7 tests.
- **Phase 7 — Acceptance tests** (2026-07-08):
  `tests/oceanus/test_acceptance.py` — the brief's five promises in one
  file: idempotent ingestion, validation catches every planted problem,
  the door never serves a partial bar, the snapshot hash matches a
  hard-coded pinned value (cross-machine stability), and the one-door
  guard (AST scan: no ccxt/oceanus-internal imports or data-directory
  references outside oceanus/; sole documented exemption:
  `scripts/check_setup.py`). The guard was proven live — it caught
  check_setup.py's ccxt import before the exemption was added.

## Decisions

- **Price storage: float64, not Decimal** (Phase 1, founder chose 2026-07-07).
  Rationale: standard for a research data layer, native to pandas/numpy;
  float64's ~15-16 significant digits are ample for OHLCV research data.
  Exact decimal arithmetic matters for trade accounting, which is out of
  Oceanus's scope — revisit there if/when that layer is built.
- **Exchange: Binance** (Phase 2, 2026-07-07). Probed live from the
  founder's machine: Binance, Coinbase, and OKX public endpoints all work
  without an account. Binance chosen for deepest liquid history (BTC/USDT
  back to **2017-08-17**), 1000 bars/request (vs. Coinbase's 300), and the
  best ccxt support. **Swappable**: `fetch_bars()` takes any object with a
  ccxt-compatible `fetch_ohlcv`; dev may revisit. Coinbase is the proven
  fallback (works from this location, history to 2015 for BTC/USD).
- **Range convention: half-open `[start, end)`** (Phase 2). Start included,
  end excluded, so adjacent ranges tile without overlapping bars.
- **Versioning: full-snapshot files, append-only** (Phase 3). Every write
  that changes anything produces a new `vNNNN.parquet` holding the complete
  current view; older versions are never modified or deleted. Restated
  candles: new values win in the latest version, old version preserves what
  we had. Simple and fully auditable at the cost of duplicated storage —
  dev may switch to delta-based versioning if data volume grows.
- **Only final bars are persisted** (Phase 3). A still-forming bar changes
  by the second; storing it would break idempotency. It exists only in the
  in-memory frame returned by ingestion.
- **Storage extends edges only** (Phase 3). `get_range()` fetches data
  before the first stored bar and after the last, but never tries to patch
  holes in the middle — interior gaps are validation's job to *report*
  (Phase 4), not storage's to silently fill.
  - **Known quirk (found while testing 2026-07-08):** coverage is inferred
    from the *extent of stored bars* (min/max open_time), not from what
    ranges were actually requested. So a request whose start falls in a
    sub-bar sliver before the first stored bar (e.g. mid-day start vs.
    midnight daily bars), or whose end reaches the still-forming frontier,
    will **re-fetch that edge on every run** even though nothing new gets
    stored — harmless (data stays correct/idempotent) but wasteful, and it
    means "loaded from disk, nothing re-downloaded" only prints for a
    fully-past, boundary-aligned range. A proper fix is coverage metadata
    (record requested ranges, not just data extent) — left for the dev.
- **Snapshot hash = SHA-256 of canonical text** (Phase 3), one line per bar
  (ISO timestamp + `repr()` of each float), rows sorted by time. Hashing
  the Parquet bytes instead would break across pyarrow versions; this form
  is machine- and library-independent.
- **Outlier threshold: 25% single-bar close-to-close move** (Phase 4),
  overridable per call (`outlier_threshold=`). Deliberately generous for
  crypto; both sides of a spike get flagged (the jump and the reversion).
  Outliers are flagged only, never removed — a real crash looks like an
  outlier too. Quant should revisit the threshold and may want a
  volatility-relative definition instead of a fixed percentage.
- **Cleaning policy** (Phase 5, founder chose 2026-07-08):
  - Gaps: **leave and flag** — never interpolate; `fill_gaps=True` raises.
  - Outliers: **flag only** — a real crash looks like a data error;
    `drop_outliers=True` exists but is off by default.
  - Unambiguous garbage: **drop and report** — exact duplicate timestamps
    (first copy kept) and impossible rows (high<low, open/close outside
    [low,high], non-positive prices, negative volume). Holes left by
    drops surface as honest gaps in the next validation.
  - Out-of-order rows are sorted (non-destructive, reported).
  - Naive timestamps are currently flag-only (not dropped) — dev may
    want a policy knob for this class too.
- **Access door refusal rule: hard vs. soft issues** (Phase 6, my call —
  reviewers should sanity-check). Hard integrity failures (duplicates,
  out-of-order, OHLC violations, impossible values, naive timestamps)
  make `get_bars()` raise. Gaps and outliers are honest facts about real
  markets (outages, crashes), so refusing on them would make most long
  ranges unservable — they're served with a printed notice instead.
  If the quant wants stricter behavior (e.g. refuse-on-gap for certain
  studies), add a strictness parameter rather than changing the default.
- **universe_at() v1 is a hand-maintained table** (Phase 6): symbol →
  listing date (BTC/USDT: 2017-08-17, verified by fetching Binance's
  earliest bar). Fine for a handful of symbols; a real point-in-time
  universe (delistings included!) is left for the dev/quant.

- **Post-build hardening** (2026-07-08): live self-test
  (`scripts/selftest.py`) run against real Binance surfaced a bug the
  fake-exchange unit tests missed — `get_bars()` didn't validate its own
  inputs, so a naive (tz-less) datetime crashed with a `TypeError` deep
  in storage instead of a clean `ValueError`. Fixed: the door now checks
  start/end are UTC-aware and start < end up front. Regression test added
  (`test_get_bars_rejects_naive_datetimes`). Also added `scripts/see_data.py`
  (eyeball chart) and `scripts/selftest.py` (10 live PASS/FAIL checks).
- **Sealed-range registry: invariant I4 fulfilled** (2026-07-17).
  `SealRegistry` (`oceanus/seal.py`) records holdout ranges that must not
  be queried outside one pre-registered final evaluation. `get_bars()`
  refuses any request overlapping a sealed range unless a
  `FinalEvaluationToken` is supplied, and logs sealed-data access
  (including the token's reason) when one is. `SealedDataError`
  subclasses `DataIntegrityError`. The registry defaults to
  `configs/sealed_ranges.json` (git-tracked, not `data/` which is
  gitignored and re-derivable) — losing the registry must never silently
  un-seal a holdout. `SealRegistry.seal()` is strictly additive; there is
  no remove/unseal method. Fulfills spec §4.4's promise that the sealed
  holdout (I4) is enforced by the data layer, not left to convention.

## Open questions / unverified details

- Binance occasionally **restates** old candles. Storage handles this with
  versioned snapshots (new version wins, old preserved) — but restatement
  is only *detected when we happen to re-fetch an overlapping range*.
  There is no proactive re-check of stored history. Is that acceptable,
  or should there be a periodic "re-verify last N days" job?
- **How often Binance restates, and how far back**, was not verified —
  I found no authoritative documentation of their restatement behavior.
  The versioning design assumes it's rare and shallow. **A measurement
  tool now exists**: `scripts/restatement_probe.py` records a baseline of
  a fixed historical range (fresh from the exchange, bypassing cache) and
  reports on later runs exactly which bars, if any, have been restated.
  Run it periodically to replace this assumption with data. Detection was
  verified end-to-end (baseline → no-change → simulated restatement caught
  → reset).
- Free Binance history for BTC/USDT starts 2017-08-17; other pairs start
  at their listing dates. Nothing enforces this — a request for earlier
  data simply returns fewer (or zero) bars, silently. Should an
  out-of-history request warn?
- `fetch_ohlcv` semantics were verified against the **installed** ccxt
  (4.5.64) and a live run, not against every exchange's quirks. ccxt
  abstracts exchanges imperfectly; if you swap exchanges, re-verify
  pagination behavior and the meaning of the last (possibly partial)
  candle.
- ~~The is_final calculation trusts the local clock.~~ **Resolved
  2026-07-08**: `is_final` now uses the exchange's own clock via
  `exchange.fetch_time()` (verified present for Binance), falling back to
  the local clock with a printed notice only if the exchange can't report
  its time. Two tests cover it (`test_is_final_follows_the_exchange_clock…`,
  `test_missing_exchange_clock_falls_back_to_local`).

## Known limitations / deliberately left for you

- **Single exchange, single venue.** No cross-exchange reconciliation;
  "the market" currently means "Binance spot."
- **`universe_at()` is a stub-quality v1**: one hand-entered symbol, no
  delistings, no point-in-time membership history. The *interface* is
  the deliverable; the implementation is yours.
- **Validation is loop-based, not vectorized.** Chosen for readability.
  Fine at hourly scale; will crawl on years of 1m bars across many
  symbols. Optimize when it hurts, keep the corrupted-fixture test green.
- **No CLI or scheduler** — ingestion runs via Python calls (see README).
  No automation, no cron, no monitoring.
- **Concurrency**: nothing locks the data directory; two processes
  writing the same symbol/timeframe could race on version numbering.
- **Snapshot pinning covers bars only** — `universe_at()` results are
  not hashed/versioned yet.
- Per the brief, **no backtesting, strategies, indicators, or metrics**
  exist anywhere in this repo. That is your territory.

## Failure-modes checklist (from the build brief)

- [x] Survivorship bias — `universe_at(date)` (Phase 6)
- [x] Partial trailing bar — `is_final` flag; `get_bars` excludes non-final (Phases 2, 6)
- [x] Restated candles — versioned, hashed snapshots (Phase 3)
- [x] Silent gap — `validate()` reports; `clean()` explicit policy (Phases 4, 5)
- [x] Timezone drift — tz-aware UTC mandated (Phases 1, 4)
- [x] Back-door reads — one-door guard test (Phase 7)

---

**2026-07-29 — Moirai specification approved; D-01 through D-09 decided;
build brief written.**

`docs/SPEC_MOIRAI.md` is approved as final and becomes the contract for the
gauntlet build. `MOIRAI_BUILD_BRIEF.md` sequences it in nine phases. Model
routing for the entire build: **Opus throughout** — essentially every phase
touches `moirai/`, `configs/gauntlet/`, or `tests/statistics/`, and there is
no mechanical Sonnet-safe sub-task in this component.

**D-06 reaffirmed — the lite/v2 split is REVERTED.** The full Moirai is
specified and built as one deliverable: every stage, the touchstones, the
calibration harness, and the published power curve. Rationale: a gauntlet
with unmeasured thresholds is a plausible gate, not an honest one, and
"honest" in Chronos means measured. The 2026-07-28 Moirai-lite entry is
superseded and `docs/STATE.md` is updated accordingly; any document still
describing a lite v1 is stale.

**The nine founder decisions, as approved:**

| ID | Decision | Status |
|---|---|---|
| D-01 | Verdict bindingness — no founder override of a FAIL; the only lever is changing the judge, which visibly invalidates every verdict the old judge issued | APPROVED as proposed |
| D-02 | Atropos seal — S=2.0 sizing, ~1.6 years, most-recent contiguous block | APPROVED **as amended**, see below |
| D-03 | Canonical verdict window = full history minus seal; the 6-month window is demoted to dev-only and is never verdict-grade | APPROVED as proposed |
| D-04 | Capacity (4.6) and shifted-window (4.7) adopted as gates; cross-asset trace descriptive-only; regime decomposition deferred-with-math | APPROVED as proposed |
| D-05 | Cost-stress form — absolute levels {5, 10, 25} bps, gate at 10 with margin | APPROVED as proposed |
| D-06 | Full-Moirai-in-one-go supersedes the 2026-07-28 lite decision | APPROVED as proposed |
| D-07 | Screener counting — screens are non-trials; they never promote and never count toward N. Recorded as FINAL | APPROVED as proposed |
| D-08 | R7 partial promotion via JPM Appendix C with the M < T/2 guard; **the gate stays on raw N**, N̂ is evidence only | APPROVED as proposed |
| D-09 | 1/e search discipline recorded as culture, not a hard cap | APPROVED as proposed |

**D-02 amendment — the seal is gated on the measured power curve, not merely
on Phase B completion.** The spec proposed executing the seal at the end of
the build phase. Amended: the seal executes only *after* the Mode E
calibration report exists and the founder has read the **measured
end-to-end detection floor**. Reason: the ~1.6-year / S=2.0 sizing is
derived from a floor of ≈2.3 that was measured by the statistics-only Monte
Carlo, not by the full pipeline under real costs, fills, and caps. If the
measured end-to-end floor differs materially from 2.3, the sizing must be
re-derived *before* sealing. Sealing is one-way; there is no unseal method
and there never will be. This places the seal in Phase 8, after Phase 6.

**Rationale notes on the decisions that were argued rather than
rubber-stamped:**

- **D-05.** Multipliers on the measured 1 bps base (2×/5× = 2 and 5 bps)
  stress essentially nothing given a ~0.1 bps measured median impact.
  Absolute levels anchor to scenario space instead: 10 bps ≈ the old
  conservative placeholder ≈ a thinner venue or a stressed book; 25 bps ≈
  regime-break territory. The margin criterion (per-bar Sharpe ≥ 0.005 at
  the 10 bps gate rather than merely > 0) is the softest element and is left
  for calibration to adjudicate — it is provisional, like every threshold.
- **D-04.** The capacity thresholds (30% max Sharpe degradation at 10×, 20%
  max remainder cancellation) are weakly derived and flagged as such; they
  sit alongside `mc_shuffle.ruin_dd 0.40` as the least-grounded numbers in
  the spec. Accepted anyway, because the alternative — no capacity gate —
  means promoting strategies with zero information about whether they
  survive at size. Calibration's attribution table will show whether these
  bind or are decorative.
- **D-08.** The governance risk, recorded so a future session cannot claim
  it was unforeseen: someone reads the evidence bracket, sees DSR@N̂ > 0.95,
  and argues for promotion on the effective-N figure. The gate is raw N by
  construction and stays that way. N̂ ≤ M always, so raw N is strictly
  conservative.
- **D-09.** A hard 1/e cap would create a perverse incentive to fragment
  searches across hypotheses — the exact laundering pattern 4.0's
  fragmentation screen exists to catch. The real discipline is structural:
  every trial permanently raises `SR*`, so searching more is expensive by
  construction. The 1/e rule is the name for "search less than you think you
  need to," not an enforced wall.

**One open item created by this session, recorded so it is not lost: the
Phase 6 calibration budget.** Spec §7.5 estimates Mode E's pre-registered
posture at 500 × 7 = 3,500 engine runs ≈ 3–5 laptop hours. That count
excludes stage 4.9's ~200 null runs per candidate. Under short-circuit
semantics only survivors reach 4.9, which is tolerable — but §7.4 requires
**full-evaluation mode** for the per-stage attribution table, and full-eval
runs every stage on every realization regardless of failure: 3,500 × 200 ≈
700,000 null engine runs for the pre-registered posture alone, before the
searched posture. Stages 4.5–4.8 add ~16 further verification runs per
candidate. Separately, the per-run cost is itself unmeasured — the canonical
window is ~15× the milestone's bar count, so even 30 seconds per run puts
3,500 candidate runs at ~29 hours rather than 3–5. *(The per-run figure is
an inference from bar counts, not a measurement.)*

This does not break the design. It means the ladder's parameters must be set
from measured throughput rather than the spec's estimate — setting them by
guess would yield either an infeasible overnight job or a quietly-truncated
calibration whose power curve overstates what was actually measured, which is
precisely the failure this component exists to prevent. **Resolution:** Phase
5 now includes a blocking throughput measurement (full-window run, pipeline
short-circuit, pipeline full-eval), and the founder selects a resolution at
the Phase 5 checkpoint. Recommended: option A (split modes — headline curve
short-circuit at full R, attribution from a subsample in full-eval) combined
with option B (reduced `n_nulls` during calibration, documented in the
report). Option C (shorten the synthetic window) is rejected: A and B degrade
precision in ways the report can state honestly, while C degrades validity by
measuring the instrument on a window that is not the window it judges on —
and V shrinks with T, so it biases the measurement.

---

**2026-07-29 — Phase 1 complete: statistics promoted to CI, JPM known-answers added, R1 SOURCED.**

`chronos_math_probe.py` implementations promoted to `src/chronos/moirai/statistics.py`
(pure-math: numpy + scipy.stats only; no engine/data/I-O imports). The probe's 28
known-answer checks + the four JPM (2014) worked-example assertions + the unfloored-SR*
trap test + property/determinism tests were ported to `tests/statistics/` as four
CI-required pytest modules — 34 tests total, all green (run twice in fresh processes;
deterministic). R1 register status: FORMULA-SOURCED → SOURCED (SPEC §10 row updated).
`scipy` added to `pyproject.toml` / `uv.lock` — the DSR/PSR math needs `scipy.stats.norm`
and it was not previously a declared dependency (so `uv sync --frozen` in CI would not
have had it). The original probe script remains at the repo root as a historical
artifact, unchanged (still runs 28/28 standalone). Total test count: 152 → 186.

JPM known-answer results (computed vs published): SR* 0.113172 vs 0.1132; DSR(N=100)
0.900397 vs 0.9004; DSR(N=46) 0.950502 vs 0.9505; DSR(N=88, normal) 0.950491 vs 0.9505.
All within tolerance — no implementation discrepancy found.

---

**2026-07-30 — Phase 2 complete: GauntletConfig, I9 enforcement, verify script.**

`src/chronos/moirai/config.py`: frozen GauntletConfig dataclass with canonical
serialization → sha256 (mechanism identical to `run.serialize_result`).
`configs/gauntlet/v001.json`: provisional thresholds from SPEC §14, every spec §4
key present (33 keys, 11-stage pipeline_order). `configs/gauntlet/ACTIVE` points to
v001. Activation guard: v001 returns is_calibrated=False (CAL-001.md does not
exist); verdicts stamp NO_AUTHORITY until Phase 6 calibrates. Probes G2 (fixed
judge — hash mismatch detection + no hardcoded gate literals in moirai/ gate code)
and G3 (visible invalidation — INVALIDATED(judge_changed) rendered at read time,
record bytes byte-compared untouched) passing in CI. `scripts/moirai_verify.py`
skeleton runs against the empty verdict set (exit 0, NO_AUTHORITY banner).
v001 config hash: fd65c27497d35fa17e2c2fbf441a10d2b701d64ca1f5fdea129b7528170a827d.
Total tests: 186 → 197 (+11 moirai).

Two decisions of record:
- **`_canonical` copied into config.py, not imported from `run.py`.** Importing
  `chronos.run` transitively pulls the whole engine + Oceanus + ccxt; the judge and
  the read-only verify tool must stay importable without any of that. The copy is
  byte-identical and pinned to `run._canonical` by
  `test_serialization_mechanism_matches_run` (fails CI if either drifts). config.py
  imports stdlib only — zero chronos imports.
- **Added `src/chronos/moirai/verify.py`** (beyond the brief's file list): the §5.3
  read-time validity computation as a pure, injectable function
  (`verdict_validity(record, *, active_config_hash, current_moirai_version,
  current_engine_version) → (is_valid, reasons)`), shared by `moirai_verify.py` and
  any future viewer, and directly unit-testable (G3) without subprocessing the CLI.
  The CLI computes the engine SHA locally via git rather than importing the engine,
  keeping the read-only tool light. Data-restatement staleness (needs Oceanus
  snapshot infra) is deferred, documented, and can only ever move a valid verdict to
  INVALIDATED — never the reverse.

---

## PHASE 3 — pipeline skeleton, verdict records, G1/G4 — 2026-07-30

**2026-07-30 — Phase 3 complete: pipeline skeleton, verdict records, G1/G4.**

`moirai/types.py` (`TestOutcome`, `GauntletVerdict`, `serialize_verdict`,
`verdict_determinism_view`), `moirai/context.py` (`GauntletContext`, `ctx.run`
wrapper — forces explicit `kind=`, stamps `gauntlet_config_hash` closing the I9
anchor, holds the post-4.2 SEARCH refusal flag via `freeze_search()` /
`SearchFrozenError`), `moirai/pipeline.py` (`Moira` protocol, DAG runner,
short-circuit + full-eval semantics, five statuses, try/finally on every exit
path). Un-executed stages recorded `executed=false` (unknown, not passed).
Verdicts stamped `authority=NO_AUTHORITY` until Phase 6 (propagated from Phase 2's
`load_active_config` `is_calibrated`). Probes G1 (verdict determinism,
cross-process byte-compare) and G4 (no unlogged judgment — crash persists partial
outcomes + `ERRORED` verdict, exception re-raised) passing in CI. Two throwaway
no-op Moirai (`tests/moirai/_noop.py`) exercise the DAG; deleted in Phase 4a.
Total tests: 197 → 213 (+16 moirai pipeline).

**Design decision — `verdict_determinism_view` strip-set.** Stripped as
bookkeeping/wall-clock: `verdict_id` (monotonic store id, like the engine's
`trial_index`), `judged_at` (wall-clock; `serialize_result` deliberately carries
none), and each outcome's `runtime_s` (wall-clock-derived). EVERYTHING else is
byte-compared: `status`, `cause_of_death`, every outcome's `passed`/`score`/
`evidence`/`executed`, all five judged-result coordinates, `gauntlet_config_hash`,
`moirai_code_version`, `gauntlet_seed`, `search_n`, `effective_n`,
`evaluation_window`, `authority`. This mirrors the engine's `determinism_view`
reasoning exactly (it strips `run_id`/`trial_index`, keeps everything else including
a recomputed `candidate_n`). One deliberate divergence from the engine's view: it
RECOMPUTES `candidate_n` from the store at read time because that coordinate is not
in the serialized result; the verdict instead carries `search_n` as a STORED,
byte-compared field (it is a fixed input finalized by stage 4.2), so nothing is
recomputed in the verdict view. The mirror is faithful; the judged result's
coordinates made no exception necessary.

**Design decision — terminal-status signalling mechanism.** A Moira tells the
runner "this is NON_PROMOTABLE / INSUFFICIENT_BREADTH, not a plain FAIL" by
stamping a reserved key into its outcome's `evidence`:
`evidence["terminal_status"] = "NON_PROMOTABLE"` (or `"INSUFFICIENT_BREADTH"`);
the module constant is `types.TERMINAL_STATUS_KEY`. Chosen over adding a field/enum
to `TestOutcome` because (a) it keeps `TestOutcome` at exactly the spec §2 shape,
(b) the signal rides in `evidence`, already the audited and serialized channel, so
it is on the record automatically, and (c) Phase 4a's stage 4.0 sets one dict key
rather than threading a new type through every Moira. Runner semantics: NON_PROMOTABLE
is terminal even under `full_evaluation_mode` (zero downstream execution, per spec
§3.2 "terminal at stage 4.0"); INSUFFICIENT_BREADTH is a non-passing outcome that
short-circuits in default mode and continues under full-eval like any failure, but
elevates the verdict status. Status precedence: NON_PROMOTABLE > INSUFFICIENT_BREADTH
> FAIL > PASS, computed over EXECUTED outcomes only (`executed=false` placeholders
never count toward a failure). **Phase 4a's stage 4.0 depends on this key.**

**Note — the "engine determinism probe spawns a subprocess" description is
imprecise.** The brief (Step 1/Step 6) says to copy the engine probe's subprocess
pattern; in fact `tests/hephaestus/invariants/test_probes.py::test_probe_3` re-runs
IN-PROCESS. The real cross-process pattern in the repo is
`tests/moirai/test_config.py::test_config_hash_cross_process`
(`subprocess.run([sys.executable, "-c", code])`). G1 copies THAT — a true fresh
interpreter — satisfying spec §9's "fresh process second time." No behavior change;
recorded so the next session isn't sent looking for a subprocess in probe 3.

**Note — engine-door guard is a naive substring match.** The Phase 3 helper was
first named `_not_executed`, which contains the substring `_execute` and tripped
`test_engine_door_guard_nothing_else_touches_execute` (a protected invariant probe
that greps `src/` for `_execute`/`_RUN_TOKEN`). Fixed the CAUSE, not the test:
renamed to `_skipped_outcome`. Future moirai code must avoid those two substrings.

## PHASE 4a — free stages 4.0/4.3/4.4, probe G8 — 2026-07-30

**2026-07-30 — Phase 4a complete: eligibility, deflated Sharpe, trade-shuffle.**

Three zero-engine-run stages under `moirai/stages/` (new package):
`eligibility.py` (M4.0-eligibility), `deflated_sharpe.py` (M4.3-dsr),
`trade_shuffle.py` (M4.4-shuffle) — moira_ids byte-matching v001.json
`pipeline_order`. `moirai/round_trips.py` — shared FIFO round-trip
reconstruction (buy→sell, per-unit fee, `Fill.price` already slippage/spread-
adjusted so those are not re-applied; diagnostic, proportional-sizing, not
accounting-grade — spec §4.4). All statistics from `statistics.py`; nothing
reimplemented in a Moira. Probe **G8** green (unsafe → NON_PROMOTABLE, zero
downstream even under full_evaluation_mode). Total tests: 213 → 234
(+10 statistics N̂, +11 moirai stages/G8).

**N̂ (effective-N) was ADDED this phase.** `statistics.py` had `dsr/psr/sr_star`
but no JPM Appendix C estimator and no store V-reader. Added as pure math:
`effective_trials(rho_bar, M) = rho_bar + (1-rho_bar)*M`,
`mean_pairwise_correlation`, `per_bar_sharpe`, `sample_skewness`,
`sample_kurtosis` — pinned by `tests/statistics/test_effective_trials.py`
(10 known-answers: rho=0→N̂=M, rho=1→N̂=1, rho=0.5,M=100→50.5, N̂≤M property,
identical/negated-series correlations). R7 stays evidence-only (D-08); the gate
is raw N.

**Design decision — N handling when `compute_search_n == 0` (the milestone).**
The milestone (trial #285) is a standalone `kind=VERIFICATION` run; the 280-sweep
that selected it is legacy (`kind=None`, ≤#284) and excluded by construction, so
`compute_search_n("H-003-ma-crossover-milestone")` returns **0** — there are zero
SEARCH records in the entire store. 4.3 records `search_n_raw: 0` verbatim but
floors the DEFLATION N to 1 (`max(raw_n, 1)`): a candidate is always at least one
trial (itself), and at N=1 SR* floors to 0 so DSR degenerates to a plain PSR — the
honest "no logged search breadth to deflate against" answer, and exactly the T-e
N=1 case. Evidence stamps `n_frozen: false` (no 4.2 upstream yet). A real numeric
trap was fixed here: `sr_star(V=0, N=1)` computes `sqrt(0)*norm.ppf(0) = 0*-inf =
nan`; the stage's `_deflated()` helper short-circuits N<2 (or non-estimable V) to
`psr(sr_hat, 0)` so the DSR is well-defined, never nan. Result: the milestone DSR
is small and FAILING (0.349), not wrong — so NOT the brief's stop-and-flag "wrong
rather than merely small" case. Phase 7 re-runs the sweep live under `kind=SEARCH`
to re-establish N=280.

**Design decision — kept the two no-op Moirai (deviation from the brief).** The
brief said delete `AlwaysPass`/`AlwaysFail`. They are load-bearing across ~20
assertions in `test_pipeline.py`'s generic DAG-mechanics probes (G1 determinism,
ordering, short-circuit, full-eval, terminal-status) — controllable pass/fail
doubles the real fixed-behaviour stages cannot express. Deleting them would couple
pure-DAG tests to stage semantics and cut coverage, and "every test stays green" is
a hard constraint. The brief's own logic ("keep … if pipeline tests still use
them") points the same way. KEPT as permanent scaffolding; `_noop.py` docstring
updated to say so.

**Brief/artifact imprecisions found (append-only record):**
- **`mc_shuffle.luck_pct` vs `mc_shuffle.luck_threshold`.** Spec §4.4 names the
  key `mc_shuffle.luck_pct`; the frozen `v001.json` (Phase 2) ships it as
  `mc_shuffle.luck_threshold`. v001 is hashed and must not be re-keyed (that
  changes the judge's hash), so `trade_shuffle.py` binds to the artifact's actual
  key. Phase 6's v002 should reconcile the name. (Same family of spec-vs-v001 key
  drift exists for 4b's keys: spec `plateau.max_cliff_frac`/`neighborhood_steps`
  vs v001 `plateau.max_cliff`/`plateau.steps`, and spec `null_signal.bootstrap_B`
  vs v001 `null_signal.B` — 4b's problem, noted here so it isn't a surprise.)
- **The p95 risk-band percentile** is derived as `100*(1-luck_threshold)` so both
  the risk band (95) and the luck percentile (5) tie to one config key rather than
  hardcoding 95/5 (also keeps them off the G2 gate-literal grep).

**Milestone judged end-to-end (checkpoint, real output).** Dev config via
`context_for_config()` (v001.json untouched), `pipeline_order` = the three stages,
`full_evaluation_mode=True` so all run. Verdict: **FAIL**, cause **M4.3-dsr**,
**authority=NO_AUTHORITY**. 4.0 PASS (42 round trips ≥ 30, `provisional_cost_
constants: true` stamped). 4.3 FAIL (per-bar SR −0.0059, T=4344, skew 0.287, raw
kurt 15.2, DSR@raw-N 0.349 < 0.95, N̂ not_estimable under D-08 with M=0). 4.4 PASS
(p95 shuffled maxDD 0.221 ≤ 0.40, realized 0.136, terminal equity 0.904). The
stored `gauntlet_verdict` line carried every reproducibility coordinate. Numbers →
SESSION_FINDINGS.md.

**For Phase 4b:** 4.3 reads N live and stamps `n_frozen: false`. Once 4.2 exists
and calls `ctx.freeze_search()`, 4.3 must consume the FROZEN N and flip that flag.
4.0's fragmentation screen and 4.3's union-N evidence both parse grid axes from
`param_grid_description` via `eligibility._grid_axes` — reused, kept in one place.

## PHASE 4b — signal null 4.1, plateau 4.2, N finalization, probe G6 — 2026-08-03

**2026-08-03 — Phase 4b complete: 4.1 signal-only null gate, 4.2 parameter plateau
+ N finalization, 4.3 frozen-N carryover, probe G6.** (Brief drafted 2026-07-30; the
decisions below were taken and the code written 2026-08-03.) Two new stages under
`moirai/stages/`: `signal_null.py` (M4.1-signal-null) and `plateau.py`
(M4.2-plateau), byte-matching `v001.json` `pipeline_order`. Plus: the D-R5-p block
selector in `statistics.py`, the re-run `Candidate` bundle + `search_frozen` property
on `context.py`, the grid-geometry parser in `eligibility.py`, and the frozen-N
recompute + divergence invariant in `pipeline.py`. Total tests 234 → **258**
(+7 statistics D-R5-p, +7 moirai signal-null, +10 moirai plateau/G6). Engine-door
grep clean (no `_execute`/`_RUN_TOKEN`); G2 gate-literal grep clean.

**Stage 4.1 (spec §4.1).** `SignalCapture` wraps the candidate strategy, calls its
REAL `on_bar(view, ctx)` (the spec's `inner.on_bar(view, ctx)` shorthand matches the
actual `_DecisionRecorder` pattern in `tests/hephaestus/invariants/test_probes.py` —
verified, no divergence), records the per-bar net-BUY intent `s_t ∈ {+1,0}`, and
returns `[]` so the engine executes nothing (portfolio flat throughout). It also
captures each bar's close from the same bounded view, so the market series and the
signals align by construction — no second data-door read. The capture runs through
`ctx.run(kind=VERIFICATION)` (one logged, counted execution; never toward N).
`flat_portfolio_assumption: true` is stamped (exact for the MA milestone whose
long/flat signal is state-independent; approximate otherwise — 4.9 is the state-aware
backstop). Statistic θ̂ = mean(s_i·(fr_i − fr̄)), one-sided bootstrap p-value = fraction
of null θ ≥ θ̂; gate p ≤ `null_signal.alpha`. Mandatory {p/2, 2p} bracket;
`fragile_to_block_length` when the gate call flips across it. RNG = `ctx.rng` only (I10).

**A real bug fixed during 4.1 tests (recorded because it matters).** The first
implementation pre-detrended the returns once and resampled the detrended values;
under the null this over-dispersed the bootstrap θ relative to θ̂'s true variability
(θ̂ carries a mean-subtraction constraint that shrinks its variance), so the test
turned CONSERVATIVE — empirical rejection ≈ 0.005 at α=0.05 (10× too few), not a seed
miss. Fix: detrend INSIDE the statistic, re-imposing the same mean-subtraction on
every bootstrap replicate → rejection ≈ α (measured 0.063 over 300 reps; the
CI test asserts ≈α over 200 seeded reps within ±2σ, fixed seed, no seed-shopping).
Second fix in the same pass: `np.diff(np.log(closes))` is START-indexed, so signal
`s_j` pairs DIRECTLY with `forward_returns[j]` (return over bar j→j+1), not `[j+1]`;
the off-by-one is corrected and the last signal (no following bar) is dropped.

**D-R5-p block length (`statistics.block_p_from_returns`).** Pure math consuming
`circ_autocov`: the mean block 1/p is the smallest lag L at which the sample
autocorrelations sit inside the ±1.96/√T band for 5 consecutive lags, clamped to
[1, T/50]; uncorrelated returns settle at L=1 → block 1 → p=1 (i.i.d.), the honest
default when there is no dependence to preserve; if they never settle, the cap is
used (longest block, smallest p — conservative for autocorrelated data). Pinned by
`tests/statistics/test_block_p.py` (behaviour + both clamp bounds + affine invariance
+ determinism) — this is a DOCUMENTED DECISION (Politis–Romano §5), provisional, not
a primary-source known-answer, and the tests say so.

**Stage 4.2 (spec §4.2) — the only stage that spends N.** ±1…±`plateau.steps` grid
neighbors per axis, parsed via the new `eligibility.parse_grid_geometry` (kept beside
`_grid_axes`, one place). Neighbors already in the store as `kind=SEARCH` records of
this hypothesis are read free; neighbors not yet run are executed
`ctx.run(kind=SEARCH)` — **N increases, and that is the point** (not optimized away).
Pass: median neighbor Sharpe ≥ `plateau.median_frac`×candidate AND ≤ `plateau.max_cliff`
of neighbors negative while candidate positive. `ctx.freeze_search()` fires on EVERY
exit path of `evaluate` (pass/fail/unparseable/no-grid) — 4.2 is the N-finalization
stage, so no later stage may spend SEARCH regardless of its verdict.

**No-grid 4.2 semantics — FOUNDER-APPROVED (2026-08-03).** A candidate with NO
`param_grid_description` (a genuinely pre-registered single point, e.g. the milestone)
has no neighborhood to check — DISTINCT from `grid_unparseable`. Resolution
(founder Option 1 + two conditions): (a) no countable SEARCH breadth
(`compute_search_n == 0`) and no grid-bearing fragmentation siblings → PASS, reason
`no_neighborhood_defined`, with a note that states plainly there is no search breadth
to deflate and NEVER implies the point is exempt/blessed; (b) BUT if the store shows
`kind=SEARCH` breadth under this hypothesis, or a grid-bearing fragmentation sibling →
FAIL, reason `undeclared_search_breadth` (a searched point wearing a pre-registered
label). The FAIL trigger fires ONLY on `kind=SEARCH` or grid-bearing siblings —
NEVER on legacy `kind=None` (already excluded by `compute_search_n`). **Empirically
confirmed the milestone takes branch (a):** `H-003-ma-crossover-milestone` carries
`param_grid_description: null` → 4.0's fragmentation screen skips at the candidate
check; the legacy `H-SWEEP-*` runs carry no `kind` key → `compute_search_n = 0`. So
neither FAIL trigger fires; the milestone gets the honest `no_neighborhood_defined`
PASS. `grid_unparseable` also covers a candidate whose own params are not located on
its parsed grid (an ambiguity, never guessed).

**4.3 frozen-N carryover (load-bearing).** 4.3 now stamps `n_frozen = ctx.search_frozen`
— True only when 4.2 actually froze upstream, False honestly when 4.2 is absent from
`pipeline_order` (dev subsets) or was short-circuited before. It still reads
`compute_search_n` LIVE; the value is STABLE post-4.2 because `ctx.run` refuses further
SEARCH, so no cached frozen-N field was introduced (the clean path from the brief).
The deflation-note wording is now conditional on `n_frozen` (the "un-frozen this phase"
categorical from 4a is gone); the "Phase 7" and "N floored" phrases stay only in the
degenerate branch so the real-deflation branch never mentions degenerate concepts.

**Verdict N finalization — FOUNDER-APPROVED (2026-08-03).** `run_gauntlet` now
resolves the verdict's headline `search_n` AFTER the pipeline loop (not before):
`search_n=None` (the real path) stamps the post-loop, frozen
`compute_search_n(hypothesis_id)`; an explicit `search_n=<int>` override is honored
verbatim and is used ONLY by the pure DAG-mechanics tests whose fixtures carry no
SEARCH records (so the 4a/Phase-3 probes are unchanged). Divergence invariant
(`_assert_n_coincides` → `VerdictNMismatch`): whenever stage 4.3 executed, the
verdict's N, 4.3's `search_n_raw`, and the post-loop `compute_search_n` MUST coincide,
else it raises (surfacing as an ERRORED verdict per I11, then re-raising) — a broken
freeze→4.3→verdict wiring can never publish an inconsistent verdict.

**Re-run candidate bundle.** `Moira.evaluate(result, ctx)` receives only the
`BacktestResult` (evidence), which cannot reconstruct the strategy object. The re-run
stages (4.1's capture, 4.2's neighbors, later 4.5–4.9) need the live strategy + base
`RunConfig` + hypothesis, so a `context.Candidate(strategy, base_config, hypothesis)`
bundle is carried on the (already-injected) `GauntletContext`; free stages ignore it,
a re-run stage with no candidate raises rather than guessing. `make_context` /
`context_for_config` gain an optional `candidate=`. This is the channel Phase 4c's
re-run gates consume.

**v002 key-drift reconciliation list (documented mapping — v001 is the frozen hashed
judge and was NOT re-keyed; the stages bind to v001's actual names):**

| spec name | v001 actual key | stage |
|---|---|---|
| `null_signal.bootstrap_B` | `null_signal.B` | 4.1 (known from 4a) |
| `null_signal.p_block` | `bootstrap_p.formula` (`"autocov_procedure"`) | 4.1 — **NEW this phase**; nominal only, v001 carries no numeric p — D-R5-p computes p per window |
| `plateau.max_cliff_frac` | `plateau.max_cliff` | 4.2 (known from 4a) |
| `plateau.neighborhood_steps` | `plateau.steps` | 4.2 (known from 4a) |
| `mc_shuffle.luck_pct` | `mc_shuffle.luck_threshold` | 4.4 (recorded in 4a) |

**Scoped deviation — structured `param_grid` sidecar deferred to Phase 7
(FOUNDER-APPROVED 2026-08-03).** The brief's 4.2 DO named a structured `param_grid`
sidecar for new searches; adding it means a field on the `Hypothesis`/Mnemosyne
record (a protected path beyond `moirai/`). `parse_grid_geometry` is THE single
documented grid parser for 4b and covers every grid in the repo and the tests. The
structured field lands in **Phase 7**, with the live sweep re-run — when new
`kind=SEARCH` records first make stringly-parsing a live risk rather than
hypothetical. Until then, any new search relying on grid geometry goes through the
string parser, and ambiguous geometry still returns `grid_unparseable` rather than
guessing.

**Probe G6 (CI-required).** (a) fragmentation fixture → 4.0 stamps
`possible_search_fragmentation` with the union N (the 4a mechanism, confirmed still
holds). (b) `ctx.run(kind=SEARCH)` after 4.2 → `SearchFrozenError`. (c) THE CRITICAL
ONE — a synthetic candidate with 3 of 4 neighbors pre-seeded as SEARCH (N=3): 4.2 runs
the one missing neighbor (N→4) and freezes; 4.3 reads the FROZEN N=4 (`search_n_raw`),
`n_frozen: true`; SR*(V, 4) > SR*(V, 3), so a broken freeze→4.3 wiring (which would
leave `search_n_raw=3`) fails the test — as does the `VerdictNMismatch` invariant.
Frozen N (4) ≠ pre-4.2 N (3) by construction, so the test cannot pass on stale wiring.

**Checkpoints (real output, both in SESSION_FINDINGS).** (1) 4.1 on the REAL milestone
(#285): p = **0.1045** > α=0.05 → fails the pre-cost signal gate; bracket {0.103, 0.122}
stable, not fragile; `block_p = 1.0` (verified genuine — BTC hourly acf[1..10] all
inside the ±0.030 band, hourly BTC returns are near-white in linear autocorrelation).
Unremarkable as the brief predicted, not a "looks wrong" flag. (2) Synthetic 4.2→4.3
in a temp store: N 3→4 (exactly +1 from the fast=30 neighbor run), freeze fired, 4.3
read frozen N=4 with `n_frozen: true`, SR* rose 0.457→0.564, `verdict.search_n = 4`
(invariant held). (The 4.2 flat-plateau PASSed; 4.3 DSR was 0 because the FakeExchange
monotonic ramp gives the run neighbor an inflated Sharpe ≈1.17 → large V — a
synthetic-data artifact, not a stage behaviour.)

## PHASE 4c SESSION 1 — cost stress 4.5, capacity 4.6, shifted-window 4.7 — 2026-08-03

**Model:** Opus · **Protected paths touched:** `moirai/`, `tests/moirai/`, plus ONE
read-only addition to `oceanus/access.py` (full diff shown, founder-approved before
commit). **Tests: 258 → 284, all green.** The first three re-run gates.

### What landed

| moira_id (byte-matches v001 `pipeline_order`) | file | gate |
|---|---|---|
| `M4.5-cost-stress` | `moirai/stages/cost_stress.py` | at 10 bps: net>0 AND per-bar Sharpe ≥ margin (0.005/bar, provisional-active); 5 bps must also pass (else `non_monotone_cost_response`); 25 bps reporting-only |
| `M4.6-capacity` | `moirai/stages/capacity.py` | at 10×: per-bar Sharpe degrades ≤ 0.3 of base AND remainder-cancelled notional ≤ 0.2 of intended; 100× reporting-only |
| `M4.7-shift` | `moirai/stages/shift.py` | ≥ 0.8 of the 4 offsets have per-bar Sharpe within 50% of base; forward guards refuse sealed / past-data shifts |

**The shared re-run helper (built ONCE, `moirai/rerun.py`).** `rerun_candidate(ctx,
config, **kwargs) -> Rerun(result, wall_clock_s)`: derives nothing itself — the stage
hands it an already-modified `RunConfig` (via `dataclasses.replace`) — calls
`ctx.run(kind=VERIFICATION, config=…, strategy=ctx.candidate.strategy,
hypothesis=ctx.candidate.hypothesis, **kwargs)`, wall-clock-times it, and raises if
`ctx.candidate is None`. The data-supply pattern is **verbatim with 4.1/4.2**: no data
kwargs in production (data comes from the config through the one Oceanus door);
`**kwargs` is only the data_root/exchange test seam. Also carries `net_return()` (from
returns as-is: prod(1+r)−1) and `per_bar_sharpe()`. 4.5/4.6/4.7 call ONLY this helper
to re-run; 4.8/4.9 (session 2) inherit it. Naming avoids the engine's internal run
tokens (one-door grep stays clean).

**Read-only Oceanus coverage helper (the one out-of-`moirai/` change).**
`access.available_range(symbol, timeframe) -> (first_open, last_open+1bar) | None` —
no fetch, no network, no seal bypass. 4.7's "past available data" forward guard needs
to know what is on disk, and I7 forbids the Moirai from reading `data/`, so the query
lives in Oceanus. Founder-approved as a scoped, read-only addition.

### The two founder decisions taken this phase (2026-08-03)

1. **cost_summary is never scaled (trap #6).** Every cost level is a full engine
   re-run at that absolute `CostConfig`; the stage ignores `cost_summary` for
   stressing. Verified by a CI test that spies **three real VERIFICATION `ctx.run`
   calls** with distinct config hashes and one identical data hash — structurally
   proving no line-item shortcut. Spread scaled in proportion
   (`half_spread_bps = base_half × L/base_slippage`), taker fee held; rule stamped
   into evidence.
2. **4.7 sign-agreement sub-gate built DORMANT (dropped spec gate, not a rename).**
   See the v002 list below. Reads `shift.min_sign_agree` from config; absent under
   v001 → the sub-gate reports `active:false` with a note and does NOT touch the
   verdict. No hardcoded literal (G2-clean), no v001 re-key (I9/hash untouched). v002
   activates it by adding + calibrating the one key. Founder-directed.

### v002 key-drift reconciliation — now 7 renames + 1 dropped spec gate

Two 4.5 renames added (list is now **7**):

| spec name | v001 actual key | stage |
|---|---|---|
| `cost_stress.gate_level` | `cost_stress.gate_level_bps` | 4.5 — **NEW this phase** |
| `cost_stress.margin_sharpe` | `cost_stress.margin_per_bar_sharpe` | 4.5 — **NEW this phase** |

(plus 4.7's two renames, recorded as renames: `shift.offsets_weeks`→`shift.offsets_w`;
`shift.sharpe_band`→`shift.max_sharpe_deviation_pct` + `shift.pass_fraction`.)

**DROPPED SPEC GATE (logged SEPARATELY — NOT a rename; do not collapse into the list
above).** Spec §4.7 also requires the **sign of net return** to agree with the base in
≥ `shift.min_sign_agree` of (base + shifts). v001 carries **no such key**, so under
v001 the gate is genuinely dropped. Built dormant this phase (see decision 2).
**v002 action is design + build + calibrate, NOT a rename:** add `shift.min_sign_agree`
to the config, confirm the sub-gate wiring (already present), and **calibrate its
threshold in Phase 6**. A future reader must not mistake this for "just add a key."

### Checkpoint (real output, milestone 4.0–4.7, full-evaluation mode; SESSION_FINDINGS)

- **4.5:** base net −9.08% (reproduces trial #285's scar exactly), monotone to
  −14.72% / −21.29% / −38.18% at 5/10/25 bps → **FAIL `cost_gate_fail`** (losing at
  every level). Margin active (floor 0.005/bar).
- **4.6:** base per-bar Sharpe −0.0059; 10× essentially unchanged (degradation
  ≈4.7e-08, remainder 0.0) → **PASS**; 100× Sharpe −0.00507, remainder 3.28%
  (reporting). Capacity is not the milestone's binding constraint.
- **4.7:** only **+1w** evaluable (within band, dev 0.412); **−2w/−1w/+2w REFUSED
  (past_available_data)** — the milestone's 6-month dev window sits at the cached-data
  edge (2026-01-01 → 2026-07-08). 1/4 < 0.8 → **FAIL**. Forward guard working as
  designed; sign-agreement sub-gate dormant (no v001 key), verdict unchanged.
- **Throughput (FIRST real per-engine-run samples):** 6 re-runs via the shared helper,
  **median 1.415 s/run** (~4344-bar H1 window). Implication: session 2's ~200-run 4.9
  checkpoint ≈ **4.7 min — FEASIBLE, not a blocker**. The real Phase 6 budget wall is
  calibration's nested loop (calibration.R=500 × 7 ladder points × ~200 nulls × 1.4 s
  ≈ ~11 days if run naively) — the Phase 5 budget decision should size against 1.4 s.

### For Phase 4c session 2 (next)

Stages 4.8 (sub-period stability, HAC aggregate — Newey–West consumed pre-Atropos),
4.9 (full-engine null benchmark, ~200 VERIFICATION runs — the expensive wall; the
calibration-budget open item bites here), 4.10 (descriptive, no gates). All inherit
`moirai/rerun.py`. `scripts/moirai_phase4c_checkpoint.py` extends to the full pipeline.

## PHASE 4c SESSION 2 — sub-period 4.8, null benchmark 4.9, descriptive 4.10, probe G7 — 2026-08-04

**Model:** Opus · **Protected paths touched:** `moirai/`, `tests/moirai/` (full diff
shown, founder-approved before commit). **Tests: 284 → 303, all green.** This session
COMPLETES Phase 4c and the commit `feat(moirai): cost stress, capacity, shifted-window,
sub-period, null benchmark, descriptive` — **the full eleven-stage pipeline (4.0–4.10)
now exists.**

### What landed

| moira_id (byte-matches v001 `pipeline_order`) | file | gate |
|---|---|---|
| `M4.8-subperiod` | `moirai/stages/subperiod.py` | (i) per-bar Sharpe positive in ≥ `subperiod.positive_sharpe_frac` of windows; (ii) one-sided HAC t > `subperiod.hac_t_threshold`; (iii) no window > `subperiod.max_single_window_pnl_frac` of net PnL |
| `M4.9-null-bench` | `moirai/nulls.py` + `moirai/stages/null_bench.py` | candidate net return > the `null_bench.percentile_gate`-th percentile of 200 cadence-matched null net returns |
| `M4.10-descriptive` | `moirai/stages/descriptive.py` | NONE — reporting-only (passed always True) |

**Shared helper (`rerun.py`) extended (session-1 file, re-touched).** Added keyword-only
`strategy=`/`hypothesis=` overrides so 4.9 pushes cadence-matched nulls (a different
strategy under `<candidate>:null:<i>`) through the SAME wall-clock-timed VERIFICATION
door. Additive and backward-compatible — the 4.5/4.6/4.7 call sites are unchanged; all
prior tests stayed green.

### Look-ahead forbidden by construction (4.9 — the gate's whole validity)

`nulls.place_null_entries(n_bars, durations, n_entries, rng)` takes **no price
parameter** — it literally cannot see prices, so no null can be placed on price
information. `NullStrategy` decides entries/exits off an internal bar COUNTER (bar
index), reading the current close only to size the order (present-price sizing, not
look-ahead). Property test asserts the signature carries no price data and that a fixed
`ctx.rng` seed gives identical placements (I10). Nulls are placed uniformly at random
without overlap, durations resampled with replacement from the candidate's realized
holding durations.

### Stage 4.8 gate (ii) — OPEN/UNRATIFIED METHODOLOGY DECISION (founder 2026-08-04)

Logged SEPARATELY from the key drifts because it is a statistical-form question, not a
rename. During review the founder's two answers diverged (one: switch to pooled-per-bar
HAC; the other: keep per-window-means and do NOT switch), and were resolved to:
**keep the per-window-means form as built, but treat gate (ii) as unratified.** Both
forms are flawed:

- **per-window means (as built):** HAC t on the K≈6 window mean returns (T=K,
  m=⌈K^⅓⌉). Matches the spec's literal "pooled mean of per-window mean returns," but at
  K≈6 Newey–West is near-empty — it cannot really do its job.
- **pooled per-bar returns (more powered, deliberately NOT adopted):** HAC t on the
  concatenated per-bar returns (T = full bar count). Better powered, BUT each sub-window
  is re-run fresh, so concatenation splices K−1 **warmup-reset seams** into the series —
  manufacturing autocorrelation artifacts exactly where NW reads them. For a project
  whose purpose is not fooling itself, that contamination is the worse failure, so the
  powered-but-contaminated form is not silently defaulted to.

**v002/Phase 6 action:** the quant ratifies the form AND calibrates the threshold. Until
then gate (ii) is reported but provisional; the code stamps `gate_ii_methodology_status`
in evidence. Gates (i)/(iii) and the {m/2, 2m} bracket stand as built. It was verified
the code was NOT switched to pooled-per-bar (nothing to revert); a unit test matches the
as-built HAC t directly against `statistics.newey_west` on the window means (K=6),
proving the HAC path executes and consumes the pinned implementation.

### Probe G7 (CI-required) — the seal is respected

`tests/moirai/test_seal_respect.py`: a re-run stage whose evaluation window touches a
constructed SEALED range → `SealedDataError` propagates UNCAUGHT → `run_gauntlet`
records an ERRORED verdict (I11) then re-raises. DISTINCT from 4.7's forward guard,
which gracefully REFUSES an auxiliary shifted window entering sealed/past-data ranges;
G7 is about a stage running the candidate's OWN window on sealed data, which must error,
never quietly skip. No stage (4.5/4.6/4.8/4.9/4.10) catches `SealedDataError`.

### v002 key-drift reconciliation — rename list now 12 (+ 1 dropped gate + 1 open form)

Added this session (5 renames → list is now **12**):

| spec name | v001 actual key | stage |
|---|---|---|
| `wf.window_months` | `subperiod.window_months` | 4.8 — NEW |
| `wf.min_positive_frac` | `subperiod.positive_sharpe_frac` | 4.8 — NEW |
| `wf.hac_t_min` | `subperiod.hac_t_threshold` | 4.8 — NEW |
| `wf.max_window_pnl_frac` | `subperiod.max_single_window_pnl_frac` | 4.8 — NEW |
| `null_bench.percentile` (0.95 fraction) | `null_bench.percentile_gate` (95 integer) | 4.9 — NEW; **read as a PERCENTILE, not a fraction** (a fraction read would make the gate meaningless) |

Still separate and NOT collapsed into the rename list: the **4.7 dropped spec gate**
(sign-agreement, dormant) and now the **4.8 gate (ii) open methodology form** (above).

### One descriptive limitation (4.10, non-gating — recorded)

The cross-asset ETH/USDT trace is SKIPPED-with-note: no ETH data is cached AND the
milestone `MACrossover` is symbol-bound (a faithful cross-asset trace needs a
symbol-agnostic rule or a rebound instance — a Candidate-design question, deferred). The
200d-MA regime is skipped on windows shorter than 200 days of prior history. Both are
reporting-only; neither affects any verdict.

### Full-pipeline checkpoint (real output; numbers in SESSION_FINDINGS)

Milestone through ALL eleven stages, full-evaluation mode: `status FAIL`,
`authority NO_AUTHORITY`, cause_of_death = M4.1, M4.3, M4.5, M4.7, M4.8, M4.9 — a
COMPLETE verdict with every stage's outcome present.
- **4.8:** K=1 on the 6-month dev window → `insufficient_subperiods` (needs ≥2 windows;
  honest, like 4.7's data-edge case — the HAC path is exercised by the unit test, not
  the dev checkpoint).
- **4.9:** candidate at the **88.5th percentile** of 200 nulls (null net dist: min
  −45.4%, median −24.8%, p95 −2.93%, max +4.9%) — the milestone LOSES LESS than 88.5% of
  random same-cadence trading but does not clear the 95th-percentile bar → FAIL. The
  benchmark doing its job.
- **4.10:** CAGR −17.5%, maxDD 15.1%, Sortino −0.79, profit factor 0.77, turnover 78×,
  42 round-trips; annualized Lo AR(1) −0.5507 ≈ naive √k −0.5518 (ρ≈+0.002, near-white).
- **Throughput:** 207 re-runs, **median 0.566 s/run** (4.9's 200 nulls ≈ 113 s; whole
  pipeline ≈ 2¼ min). Better than s1's 1.4 s — recomputes the Phase 6 calibration budget
  to ~4.5 days naive (STATE "Blocking").

### For Phase 5 (next)

Touchstones (§6 regression set), the calibration harness (§7 synthetic-path power curve
across `calibration.ladder_S`), and the throughput/budget decision — now sized against
0.566 s/run. The full eleven-stage gauntlet exists to calibrate.
