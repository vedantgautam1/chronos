# COMPONENTS — where every piece comes from

Companion to `docs/v2/CHRONOS_V2.md`. Lists **what we take from outside** (open-source libraries, services, data) and **what we reuse from v1**, with source, licence, version checked, and how far we tested it. Re-check version and licence before adopting anything; repos change.

Check levels: **Run** = we ran it and saw results · **Read** = read its code or docs · **Listed** = known by name only.

Things we're *not* using yet (with the trigger that would make them useful) live in the Project doc `claude/reference-library.md`. Rejected items are in CHRONOS_V2 §11.

---

## 1. Third-party: in the v2 plan

| Component | Role in v2 | Get it from | Licence | Version checked | Check | Notes / traps |
|---|---|---|---|---|---|---|
| **NautilusTrader** | Engine: backtest = paper = live; OMS; IBKR adapter | github.com/nautechsystems/nautilus_trader · PyPI `nautilus_trader` | LGPL-3.0 (fine for personal use) | 1.231.0 on PyPI (27 Oct) | Listed (spike pending) | Front-runner until the spike passes (V2-D04). Fast-moving: pin the version. BUILD_NOTES §5 |
| **Interactive Brokers** (account, IB Gateway, market-data subscriptions) | Crypto futures execution now; FX/equities later | ibkr.com | Commercial | — | Founder account; eligibility confirmed | Commission per contract: Coinbase nano ~USD 0.20, BFF 0.25, MBT 0.85 + exchange/regulatory fees (unchecked). Market-data cost unchecked (O-4) |
| **Kraken** (historical OHLCVT files + REST/WebSocket API) | Signal history; forward trade recording (V2-D26) | kraken.com (support downloads; public API) | Exchange terms | — | Read (docs) | REST OHLC returns a limited recent window: use the files for history. BUILD_NOTES §4 |
| **PostgreSQL** | Operational tables, experiment store, registry | postgresql.org | PostgreSQL licence (permissive) | — | — | On the VPS |
| **Parquet (pyarrow) + DuckDB** | Processed data store and queries | PyPI `pyarrow`, `duckdb` | Apache-2.0 / MIT | pyarrow ≥ 24 already in v1 | v1 uses pyarrow | — |
| **numpy, scipy, pandas** | Series maths | PyPI | BSD | in v1 `pyproject.toml` | v1 uses them | — |
| **arch** (Kevin Sheppard) | EWMA/GARCH vol baselines; cross-checking our Newey–West and block bootstrap; SPA/StepM/MCS over stored trial returns (V2-D33) | github.com/bashtage/arch · PyPI `arch` | NCSA (permissive) | 8.0.0 (3 Nov) | **Run** (S10) | Matched hand-computed Newey–West exactly; SPA size 4% at 5%. **Trap:** multiple-comparison classes take *losses*; passing returns silently picks the worst variant. BUILD_NOTES §2 |
| **VectorBT** | Fast counted screening sweeps | PyPI `vectorbt` | Apache-2.0 + Commons Clause (personal use fine, not for sale) | 1.2.0 (27 Oct) | Run (inside S1's pack) | Every screened variant is a trial (V2-D03) |
| **Kronos** (candle model) | Shadow signal, three roles | github.com/shiyu-coder/Kronos · Hugging Face `NeoQuasar/Kronos-small`, `-base` | MIT [Likely — model card] | — | Listed | Confirm training cutoff and API from the repo before use. Spec `specs/kronos-shadow.md` |
| **xAI Grok API** | Live X/news retrieval and scoring (S-NEWS collection) | x.ai | Commercial API | Grok 4.1 Fast listed at $0.20/$0.50 per M tokens (Jan 2026, third-party) | Listed | Pin model versions; verify search-tool fees |
| **Anthropic Claude API** | Second intensity scorer; research agents | anthropic.com | Commercial API | — | — | Pin model versions |
| **GDELT** | Free news volume + tone history and 15-min feed | gdeltproject.org | Free | — | Listed | Crude dictionary tone; a lower bound |
| **SEC EDGAR** (Form 4, XBRL company facts) | S-INSIDER, S-QUALITY (parked) | sec.gov | Public | — | Read (rules) | ≤ 10 req/s, declared User-Agent (generic project name) |
| **Official macro releases** (BLS, BEA, Fed, StatCan, BoC) | S-MACRO actuals | Agency sites | Public | — | — | Store with release timestamps |
| **Whisper** (local) | Press-conference transcription; Instagram intake on the Mac | github.com/openai/whisper | MIT | — | Used in intake | Already running in `~/chronos-intake` |
| **tick** | Hawkes fits on recorded trades (parked thesis) | github.com/X-DataInitiative/tick · PyPI `tick` | BSD-3 | 0.8.0.2 (revived Apr–May 2026; macOS arm64 wheels) | **Run** (S10) | **Must also `pip install numpydoc`** or every Hawkes learner crashes. Likelihood fit errors by default; use least squares. Seasonality trap: BUILD_NOTES §8 |

## 2. From v1 (frozen under branch `v1-final`) — port, don't extend

| v1 asset | Path | Port as | Notes |
|---|---|---|---|
| Statistics core | `src/chronos/moirai/statistics.py` | v2 stats module | Lo SE, Newey–West, stationary bootstrap, PSR/DSR (floored `SR*`), effective trials, `atropos_years` (= years-to-significance) |
| Known-answer tests | `tests/statistics/` (Lo 2002, Newey–West 1987, Politis–Romano 1994, PSR/DSR, block p, effective trials) + `chronos_math_probe.py` (28 checks) | v2 test suite | **Add** the mid-rank permutation-tie case (V2-D21) and null tests (a)–(d) |
| Trial ontology | `src/chronos/run.py` (`run_experiment`, `RunKind` SEARCH/VERIFICATION, `register_search`, `compute_search_n`) | Mnemosyne core | Keep `kind=` explicit everywhere; add per-trial daily return and trade-list storage (V2-D33) |
| Cost and slippage measurement | `src/chronos/hephaestus/costs.py`, `measure_slippage.py` | Cost-model reference | v1 numbers are Binance-specific (10 bps taker, ~1 bps slippage): **do not reuse the numbers**, only the method |
| Touchstones + regime generator | `src/chronos/moirai/calibration/touchstones.py`, `generator.py`, `fixtures/` | Acceptance test | T-b, T-d, T-e must still FAIL; T-a2 should PASS once sized by drawdown budget |
| Null benchmark | `src/chronos/moirai/stages/null_bench.py` | Reference only | **Strict `<` rank at ~line 125: replace with mid-rank.** v2 null recipe differs (CHRONOS_V2 §6) |
| Search-fragmentation screen | `src/chronos/moirai/stages/eligibility.py` step (f) (`_fragmentation_screen`, `_grid_axes`); sibling matching reused by `stages/plateau.py`; spec `docs/v1-archive/SPEC_MOIRAI.md` §4.0(f); tests `test_eligibility_fragmentation_screen_union_n` and probe G6a | Edge-check warning (V2-D31) | Warn-only; report DSR at the union N. Window from config (90 days in v1) |
| Holdout seal | `src/chronos/oceanus/seal.py` | Optional | Additive-only sealing; v2 keeps "sealed holdouts touched once" |
| Data validation/cleaning policy | `src/chronos/oceanus/validate.py`, `clean.py` | Oceanus reference | Policy: never interpolate gaps; flag outliers; drop only provably impossible rows, reporting each |
| v1 findings | `docs/v1-archive/` (SESSION_FINDINGS, SPEC_MOIRAI, handoffs) | Background | DSR laundering demo: same strategy 0.563 at N = 1 vs 0.054 at N = 280 |

## 3. Code packs from content sources (licence not stated: ask before copying verbatim)

| Pack | What's useful | Check | Notes |
|---|---|---|---|
| `mathlab` (S2) | Ruin, Kelly, streaks, years-to-significance, PSR/DSR | Run (37/37) | **Fix the ruin `× L` bug** before use (BUILD_NOTES §3) |
| `ultimate-lab` (S1) | `ResearchCard` validator, role permissions, bounded-proposal validator, Šidák bar | Run (30/30) | Remove the trade-less bias in its gate (BUILD_NOTES §2) |
| DaruFinance `Monte-Carlo-paper` | `fp_pitfall_demo.py`: floating-point tie reproducer | Run | Port as a known-answer test |
| `agentlab-lab` Parts 1–2 (S11–S12, Arwaz Az; Parts 3–7 under analysis) | Look-ahead nudge probe (`engine.causality_ok`); Bonferroni lesson miner; episode schema; ledger id scheme, database-enforced append-only, `reproduce()` / `compare()` | Run (62/62; every Part 1–2 figure reproduces) | Counts attempts per family (fixed in v2 by V2-D31); code hash covers one file only (BUILD_NOTES §6). Not committed here (licence not stated); source: the founder's Drive folder "SERIES: Self Improving AI" |

## 4. Deferred to triggers (V2-D23)

| Component | Trigger | Candidate | Reference |
|---|---|---|---|
| Event bus | A second consumer process or machine needs the live stream | Redpanda or Apache Kafka (choose then) | QuantDinger (Apache-2.0, Run): process split, leases, fencing tokens, audit worker |
| API gateway | An external client needs authenticated access | FastAPI behind a TLS reverse proxy | QuantDinger |
| User management | A second person needs access | — | QuantDinger (users, MFA, scoped tokens) |
| Monitoring dashboards | More than one live process to watch | Grafana + Prometheus (the tool) | — |
| Portfolio allocation across sleeves | Several strategies live | skfolio; Riskfolio-Lib (convex risk parity) | Equal-risk sleeves first (1/N is hard to beat) |
