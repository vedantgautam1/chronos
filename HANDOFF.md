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
