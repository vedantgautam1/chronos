# HANDOFF

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
