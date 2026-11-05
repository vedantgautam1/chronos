# CODEBASE — what every part of this repo is

Companion to `docs/v2/CHRONOS_V2.md`. One line per file or folder: what it is, whether it is v1 (frozen) or v2, and what happens to it in v2. **As of 5 Nov 2026 no v2 code exists:** every `.py` file in the repo is either v1 or a research check script. Update this file when v2 code lands (CHRONOS_V2 §14).

**v2 fate, in one word:**
- **Port** — copy the logic into the new v2 package, with its known-answer tests (see `COMPONENTS.md` §2).
- **Reference** — read it for ideas or methods; don't copy it.
- **Retire** — not used by v2 (the reason is given).
- **Keep** — stays as it is.

v1 is frozen on branch `v1-final` (commit `6b2b628`). Never edit v1 code (V2-D29).

---

## Top level

| Path | What it is | Era | v2 fate |
|---|---|---|---|
| `CLAUDE.md` | Rules for Claude Code sessions | v2 | Keep |
| `README.md` | Front page; points to the master doc | v2 | Keep |
| `pyproject.toml`, `uv.lock` | Python environment (managed with `uv`) | v1 | Keep; v2 extends it in its own package (V2-D29) |
| `.github/workflows/tests.yml` | CI: runs the v1 test suite on every push | v1 | Keep; add the v2 suite when it exists; retire the v1 job only with the founder's OK |
| `.gitignore` | Ignores `data/`, caches, `.venv/`, `*.png` | v1 | Keep |
| `chronos_math_probe.py` | 28 known-answer checks for the statistics (DSR, Lo, Newey–West…) | v1 | **Port** into the v2 test suite |
| `measure_slippage.py` | Measured Binance market-buy slippage (R6) | v1 | Reference (method only; Binance numbers don't apply) |
| `run_plateau_sweep.py`, `extract_sweep_sharpes.py`, `find_sweep_winner_dsr.py`, `compute_trial4_dsr.py` | One-off analysis of the 280-point MA-crossover sweep (the DSR "laundering" demo: 0.563 at N = 1 vs 0.054 at N = 280) | v1 | Retire (the finding is recorded in `docs/v1-archive/SESSION_FINDINGS.md`) |
| `milestone_equity.png` | Equity chart from the v1 milestone run | v1 | Retire (artifact) |
| `configs/binance_fees.md` | Binance fee notes | v1 | Retire (Binance not used, V2-D27) |
| `configs/gauntlet/v001.json`, `ACTIVE` | The 11-gate gauntlet's hashed threshold file | v1 | Retire (gauntlet replaced by the edge check, V2-D08). The idea of versioned, hashed config stays (V2-D11) |
| `data/` | Local market-data folder (git-ignored) | v1 | Keep the convention |
| `docs/calibration/`, `docs/promotions/` | Empty v1 placeholders | v1 | Retire |

## `docs/`

| Path | What it is |
|---|---|
| `docs/v2/CHRONOS_V2.md` | **Master document.** Read first |
| `docs/v2/BUILD_NOTES.md` | Traps to avoid, by component |
| `docs/v2/COMPONENTS.md` | Where every third-party and v1 piece comes from |
| `docs/v2/CODEBASE.md` | This file |
| `docs/v2/CHANGELOG.md` | Dated work log |
| `docs/v2/specs/` | Kronos shadow-signal spec; news/sentiment strategy spec (each with a staleness note) |
| `docs/v2/research/` | Check scripts behind the content-analysis findings (README inside) |
| `docs/STATE.md` | Pointer: "moved, read the master doc" |
| `docs/v1-archive/` | Frozen v1 documents: `SPEC_MOIRAI.md`, `SPEC_HEPHAESTUS.md`, `HANDOFF.md` (the v1 decisions log, closed 3 Nov), `SESSION_FINDINGS.md` (measured numbers), build briefs, dated handoffs |

## `src/chronos/` — v1 code (frozen)

### `oceanus/` — data layer
| File | What it does | v2 fate |
|---|---|---|
| `model.py` | The `Bar` schema | Reference (v2 schema adds `instrument_id`, `source`, `asset_class`, `available_at`) |
| `ingest.py` | Fetches OHLCV from Binance via ccxt | Retire (Binance); the pagination/idempotency pattern is a reference for Kraken |
| `store.py` | Versioned Parquet snapshots + snapshot hash | Reference (the snapshot hash is the v2 "data coordinate", BUILD_NOTES §6) |
| `validate.py`, `clean.py` | Detects data problems; applies an explicit cleaning policy | Reference (policy: never interpolate gaps; flag outliers; drop only impossible rows, reporting each) |
| `access.py` | The single data door `get_bars()` | Reference (pattern) |
| `seal.py` | Holdout seal (additive only) | Optional port ("sealed holdouts touched once" stays) |

### `hephaestus/` — v1 backtest engine
| File | What it does | v2 fate |
|---|---|---|
| `engine.py`, `broker.py`, `portfolio.py`, `types.py`, `view.py` | Event loop, simulated fills, Decimal ledger, order/fill types, time-bounded market view | Retire (replaced by NautilusTrader, V2-D04). Used once more as the comparison in spike criterion (a) |
| `costs.py` | Fee/spread/slippage model | Reference (method; v2 costs come from IBKR futures) |
| `screener.py` | Quarantined fast screener ("screens are not trials") | Retire (V2-D03: every screened variant counts) |

### `mnemosyne/`
| File | What it does | v2 fate |
|---|---|---|
| `stub.py` | Append-only JSONL store + persistent trial counter | Retire (replaced by the Postgres store); append-only principle stays |

### `run.py`
`run_experiment()`, `RunKind` (SEARCH / VERIFICATION), `register_search()`, `compute_search_n()`: the honest trial-counting ontology. **Port** into Mnemosyne, adding per-trial daily return and trade-list storage (V2-D33).

### `moirai/` — v1 validation gauntlet
| File | What it does | v2 fate |
|---|---|---|
| `statistics.py` | Lo SE, Newey–West, stationary bootstrap, PSR/DSR, block p, effective trials | **Port** |
| `calibration/generator.py`, `touchstones.py`, `harness.py`, `fixtures/` | Synthetic-candle generator, touchstone strategies T-a…T-e, calibration quarantine | **Port** (acceptance test, §9 step 5) |
| `stages/eligibility.py` | Breadth check + **search-fragmentation screen** | **Port** the screen as an edge-check warning (V2-D31); breadth becomes a warning |
| `stages/deflated_sharpe.py` | DSR at honest N | **Port** the logic |
| `stages/plateau.py` | Parameter plateau; freezes N | Reference for the neighbourhood check (V2-D20) and sibling matching |
| `stages/null_bench.py` | Full-engine null benchmark | Reference only; **strict `<` rank bug at ~line 125** (BUILD_NOTES §2); v2 null differs (V2-D21) |
| `stages/signal_null.py` | Signal-only bootstrap null | Retire (v2 null = random entries with matched exposure, V2-D21) |
| `stages/trade_shuffle.py` | Drawdown via trade shuffling | Reference (fine for drawdown, which is a path metric; drawdown is now a sizing input) |
| `stages/cost_stress.py`, `capacity.py`, `subperiod.py`, `descriptive.py` | Cost stress, capacity, subperiod stability, reporting | Reference (2× costs is an edge-check gate; capacity and subperiod are warnings) |
| `stages/shift.py` | Shifted-window stability | Retire |
| `config.py`, `context.py`, `pipeline.py`, `types.py`, `verify.py`, `rerun.py`, `nulls.py`, `round_trips.py` | The 11-gate pipeline machinery: hashed judge, run context, DAG runner, verdict records, re-run helper | Reference (the gauntlet is retired, V2-D08; hashed-config and read-time-validity ideas stay) |

### `strategies/`
| File | What it does | v2 fate |
|---|---|---|
| `ma_crossover.py` | The v1 milestone strategy | Reference (re-implemented in Nautilus for spike criterion (a)) |

## `tests/` — v1 tests (CI runs them)

| Folder | What it covers | v2 fate |
|---|---|---|
| `tests/statistics/` | Known-answer tests (Lo 2002, Newey–West 1987, Politis–Romano 1994, PSR/DSR, block p, effective trials) | **Port** with `statistics.py`; add the mid-rank tie case (V2-D21) |
| `tests/moirai/` | Gauntlet stages, touchstones, probes G1–G8 | Port `test_touchstones.py`, the fragmentation test (`test_free_stages.py::test_eligibility_fragmentation_screen_union_n`) and probe G6a; the rest is reference |
| `tests/hephaestus/` | Engine tests and invariant probes | Keep in the v1 suite; retire with the engine |
| `tests/oceanus/` | Data-layer tests | Keep in the v1 suite; reference for the v2 data layer |

## `scripts/` — v1 tools

| File | What it does | v2 fate |
|---|---|---|
| `run_milestone.py` | End-to-end v1 milestone run | Reference (spike criterion (a) comparison) |
| `moirai_verify.py`, `moirai_phase4c_checkpoint.py`, `diag_subperiod_K.py` | Gauntlet verification and diagnostics | Retire |
| `restatement_probe.py` | Checks whether Binance revised old candles | Retire (idea worth repeating for Kraken data) |
| `see_data.py`, `selftest.py`, `check_setup.py` | Data and environment checks | Retire |

## What v2 will add (not created yet)

- A new v2 package folder (name and layout set in the §9 step-2 build session, V2-D29), with its own tests added to CI.
- First contents (§9 step 2): ported statistics + known-answer tests, the trial ontology with per-trial return storage (V2-D33), the search-fragmentation screen (V2-D31), cost/slippage measurement, touchstones.
