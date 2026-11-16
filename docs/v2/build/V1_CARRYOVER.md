# V1 CARRY-OVER LEDGER

What happens to every piece of v1, decided by re-reading the code on 16 Nov 2026 (founder request: "see if we can take anything more from v1"). Companion to `BLUEPRINT.md` Part 3 and to `docs/v2/CODEBASE.md`, which stays the plain map of the repo.

**The rule that doesn't move:** v1 is frozen (V2-D10, V2-D29). "Port" means copy the logic into `v2/src/chronos2/` with its tests, changing import paths and whatever the spec lists, and nothing else. v1 files are never edited. A guard in the automatic tests compares `src/`, `tests/`, the root `pyproject.toml` and `uv.lock` with branch `v1-final` on every pull request; any difference fails the build.

**Verdicts:** **Port** (copy with tests) · **Adapt** (keep the idea and the tests' shape, rewrite for v2) · **Reference** (read, don't copy) · **Retire** (not used).

Lines are counted with `wc -l` on `main` at `be93ad7`.

---

## 1. Changes from the previous plan (`CODEBASE.md`, 5 Nov)

| v1 file | Was | Now | Why |
|---|---|---|---|
| `oceanus/model.py` | Reference | **Port** (B10) | `Timeframe`, the bar columns and their checks are engine-neutral. v2 adds `instrument_id`, `source`, `asset_class`; `available_at` belongs to non-price tables |
| `oceanus/store.py` | Reference | **Port** (B10) | Versioned Parquet snapshots and `snapshot_hash` are exactly V2-D42's "data snapshot hash". One change: the hash loop is row-by-row Python, too slow for 1-minute history; v2 vectorises it and must reproduce v1's hash on a fixed frame |
| `oceanus/validate.py`, `clean.py` | Reference | **Port** (B11) | The policy is already v2's (never interpolate, flag outliers, drop only provably impossible rows and report each). 261 lines with 213 lines of tests that pass today |
| `oceanus/access.py` | Reference | **Adapt** (B12) | The single-door pattern and its acceptance tests carry over; the seal check becomes date-based (V2-D38) and every read returns a footprint (V2-D42) |
| `oceanus/seal.py` | Reference | **Adapt** (B12 seal date; B41 look ledger) | Additive-only sealing and the access log are right; it never limited looks. The limit moves into the database |
| `moirai/config.py` | Reference | **Port the hashing helper** (B01) | `_canonical` + `config_hash` are the "frozen, hashed configuration" BUILD_NOTES §2 asks for. The gauntlet config class itself is retired |
| `moirai/stages/trade_shuffle.py`, `round_trips.py` | Reference | **Port** (B45) | Drawdown by trade shuffling is valid for a path metric, and drawdown is now the sizing input (V2-D08). `test_free_stages.py` has a hand-enumerable 24-ordering fixture to port with it |
| `calibration/touchstones.py` | Port | **Port the definitions, leave the runner** (B17, B46) | The file imports the whole 11-gate pipeline. The worlds, rules, seeds and written rationales are the asset; they become data files with a schema |
| `moirai/nulls.py` | (not listed) | **Reference** (B40) | Cadence-matched random entries are close to V2-D21's null but place entries differently; the v2 recipe is written from the master doc §6 |
| `hephaestus/test_costs.py`, `test_run.py` | Keep in v1 suite | **Mine for known answers** (B08, B13) | Counting semantics and "no path around costs" tests translate |

Everything else keeps the verdict it had.

## 2. Full ledger

### `src/chronos/oceanus/` — data layer (987 lines; tests 968)

| File | Lines | Verdict | Build | Notes |
|---|---|---|---|---|
| `model.py` | 101 | Port | B10 | `Timeframe`, `Bar` |
| `store.py` | 147 | Port | B10 | Drop the import of `ingest`; vectorise the hash; parity test against v1's function |
| `validate.py` | 140 | Port | B11 | |
| `clean.py` | 121 | Port | B11 | |
| `access.py` | 188 | Adapt | B12 | `get_bars`, `available_range`; `universe_at` waits for equities |
| `seal.py` | 149 | Adapt | B12, B41 | |
| `ingest.py` | 135 | Retire | — | Binance through ccxt. The pagination/idempotency pattern is a reference for the Kraken recorder (B31) |

### `src/chronos/hephaestus/` — v1 engine (1,157 lines; tests 1,577)

| File | Lines | Verdict | Build | Notes |
|---|---|---|---|---|
| `engine.py`, `broker.py`, `portfolio.py`, `types.py`, `view.py` | 899 | Retire | — | Replaced by NautilusTrader (V2-D04). Run once more, unmodified, as the comparison in spike criterion (a) (B20) |
| `costs.py` | 140 | Reference | B13 | Fixed basis points on Binance. Keep the principle that no fill bypasses costs |
| `screener.py` | 112 | Retire | — | Built on "screens are not trials" (reversed by V2-D03) |

### `src/chronos/mnemosyne/`

| File | Lines | Verdict | Build | Notes |
|---|---|---|---|---|
| `stub.py` | 60 | Retire | — | JSONL store. The append-only principle moves into Postgres (B07). **v1 records (trial_index ≤ 284) are never imported or mixed** (BUILD_NOTES §6) |

### `src/chronos/run.py` (346 lines; tests 143)

| Part | Verdict | Build | Notes |
|---|---|---|---|
| `Hypothesis`, `RunKind`, `register_search`, `compute_search_n`, canonical config hash | Port | B08 | The honest-N ontology. `kind` stays explicit at every call |
| `run_experiment`, `RunConfig`, `RunRecord`, serialisers | Retire | — | Bound to the v1 engine. v2 records results through an engine-neutral `TrialResult` (proposal P-17) |

### `src/chronos/moirai/` — v1 validation (4,724 lines; tests 2,921)

| File | Lines | Verdict | Build | Notes |
|---|---|---|---|---|
| `statistics.py` | 270 | **Port** | B04 | 18 pure functions. `atropos_years` is renamed `years_to_significance`; `sweep_trial_variance` (a v1 measurement helper with a 42 bps default) is not ported |
| `calibration/generator.py` | 184 | Port | B16 | Depends only on the bar schema |
| `calibration/touchstones.py` + `fixtures/te_laundering_winner.json` | 575 | Port definitions | B17, B46 | T-e is pure maths on the committed fixture and can be asserted as soon as B04 exists |
| `calibration/harness.py` | 129 | Reference | B46 | The quarantine idea (synthetic data never enters the production store) is kept as a test |
| `stages/eligibility.py` | 250 | Port the fragmentation screen (~110 lines: `_grid_axes`, `parse_grid_geometry`, the sibling logic) | B15 | Breadth checks become warnings (B43) |
| `stages/deflated_sharpe.py` | 252 | Reference | B42 | The maths lives in `statistics.dsr`; the stage wrapper is gauntlet-bound. Its evidence fields (raw N, effective N, the deflation note) are the model for the edge check's report |
| `stages/plateau.py` | 309 | Reference | B43 | Neighbour enumeration and sibling matching, for the neighbourhood check (V2-D20) |
| `stages/null_bench.py` | 142 | Reference | B40 | **Strict `<` at line 125**; the v2 counter is mid-rank (B05). v1 is left as it is |
| `stages/trade_shuffle.py` | 136 | Port | B45 | |
| `round_trips.py` | 82 | Port | B45 | Needed by trade-level statistics too |
| `nulls.py` | 114 | Reference | B40 | |
| `stages/cost_stress.py`, `capacity.py`, `subperiod.py`, `descriptive.py` | 838 | Reference | B42, B43 | 2× costs becomes per-component (V2-D35); capacity and subperiod become warnings |
| `stages/signal_null.py`, `shift.py` | 428 | Retire | — | Superseded by V2-D21; shifted-window dropped |
| `config.py` | 125 | Port the hash helper | B01 | |
| `context.py`, `pipeline.py`, `types.py`, `verify.py`, `rerun.py` | 827 | Retire | — | 11-gate machinery. "A verdict is valid only for the config hash that produced it" survives as a rule in B42 |

### `src/chronos/strategies/`

| File | Lines | Verdict | Build |
|---|---|---|---|
| `ma_crossover.py` | 59 | Reference | B19 (re-implemented on Nautilus), B17 (touchstone rules) |

### Root scripts and `scripts/`

| File | Lines | Verdict | Build | Notes |
|---|---|---|---|---|
| `chronos_math_probe.py` | 340 | **Port** as tests | B05 | 28 checks |
| `measure_slippage.py` | 200 | Port the method | B14 | Binance numbers don't carry |
| `scripts/restatement_probe.py` | 132 | Reference | B32 | "Did the exchange revise old data?" is worth repeating on Kraken files |
| `scripts/run_milestone.py` | 103 | Reference | B20 | The v1 side of the spike comparison |
| the rest (`run_plateau_sweep.py`, `extract_sweep_sharpes.py`, `find_sweep_winner_dsr.py`, `compute_trial4_dsr.py`, `scripts/moirai_*`, `diag_subperiod_K.py`, `see_data.py`, `selftest.py`, `check_setup.py`) | ~1,090 | Retire | — | One-off analyses and gauntlet tools; findings are in `docs/v1-archive/SESSION_FINDINGS.md` |

### `tests/` (5,873 lines)

| Folder | Verdict | Build |
|---|---|---|
| `tests/statistics/` (407) | **Port all** | B04 |
| `tests/oceanus/test_model.py`, `test_store.py` (213) | Port | B10 |
| `tests/oceanus/test_validate.py`, `test_clean.py`, `corrupted_fixture.py` (213) | Port | B11 |
| `tests/oceanus/test_access.py`, `test_seal.py`, `test_acceptance.py` (403) | Adapt | B12 |
| `tests/oceanus/test_ingest.py` | Retire | — |
| `tests/moirai/test_calibration_generator.py` (78) | Port | B16 |
| `tests/moirai/test_touchstones.py`, `test_calibration_quarantine.py` (140) | Adapt | B17, B46 |
| `tests/moirai/test_free_stages.py::test_eligibility_fragmentation_screen_union_n`, probe G6a in `test_plateau.py` | Port | B15 |
| `tests/moirai/test_free_stages.py` trade-shuffle fixtures | Port | B45 |
| `tests/hephaestus/test_run.py` (counting cases), `test_costs.py` (no-bypass cases) | Mine | B08, B13 |
| everything else under `tests/hephaestus/`, `tests/moirai/` | Stays in the v1 suite, which keeps running in CI until the founder retires it | — |

## 3. What the numbers add up to

| | Code lines | Test lines |
|---|---|---|
| Ported or adapted into v2 (phases 1 and 4) | ~2,200 | ~1,900 |
| Read as reference while writing v2 | ~2,300 | — |
| Retired (incl. ~1,100 lines of one-off scripts) | ~4,700 | ~3,900 stay as the v1 suite |

Roughly a quarter of v1's code and a third of its tests move into v2, ported or adapted. The rest is bound to the retired engine and gauntlet, or specific to Binance. (Counts are approximate where a file is only partly ported.)

## 4. v1 commitments, not just code

| v1 commitment | v2 status | Where enforced |
|---|---|---|
| Honest trial counting; N from SEARCH-kind records only | Kept, widened (every screened variant counts, V2-D03) | B08; B38 |
| Hypothesis written before the run | Kept | B08: a trial can't be stored without a registered hypothesis |
| Known-answer tests before a statistic is trusted | Kept (hard rule 5) | Every stats build; layer 0 |
| Provenance: every threshold traceable to a reproducible path | Kept | Frozen, hashed config stored with every verdict (B01, B42) |
| No seed shopping, no verdict-fitting | Kept (hard rule 10) | Seeds are written in the spec before the build runs |
| Sealed holdout touched once | Kept, made enforceable | B12, B41 |
| Append-only records | Kept, moved into the database | B07 |
| Asymmetric findings stated asymmetrically | Kept | Reviewer checklist |
| "Nothing is decided until committed" | Kept | Specs, decisions and reports all live in the repo |
| Protected-path approvals | Narrowed to thresholds, risk limits, go-live (V2-D11) | The protected-value guard (B01) |
| Clean documented FAIL as the goal | **Retired** (master doc §11a) | — |
| 11 binding gates, gate 4.4 as a reject gate, "screens are not trials", Binance, Phase 5/6, the Atropos seal plan | **Retired** | — |
