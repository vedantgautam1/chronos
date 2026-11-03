# Chronos

A systematic trading research system, built in components. This repository
contains **Oceanus** (the data layer) and **Hephaestus** (the event-driven
backtesting engine), both complete as review-ready first drafts. See
[HANDOFF.md](HANDOFF.md) for decisions, open questions, and known
limitations; [docs/SPEC_HEPHAESTUS.md](docs/SPEC_HEPHAESTUS.md) is the
engine's contract.

## Hephaestus in one paragraph

An event-driven simulator that walks historical bars in time order,
exposes strategies only to information available at decision time (the
bounded `MarketView` — look-ahead is structurally impossible), fills
orders through a simulated broker with participation caps and a
never-skippable cost model, keeps an exact Decimal ledger with a
reconciliation identity checked at every bar, and records every run —
including crashes — through the sole entry point:

```python
from chronos.run import Hypothesis, RunConfig, run_experiment

record = run_experiment(strategy, config, hypothesis)  # the only door
```

No hypothesis, no run. Every run is counted and persisted to
`records/runs.jsonl` with full reproducibility coordinates (code SHA,
config hash, data snapshot hash, seed). The invariant probes in
`tests/hephaestus/invariants/` are the engine's definition of "cannot
lie." Run the end-to-end milestone:

```sh
uv run python scripts/run_milestone.py
```

## What Oceanus is

Oceanus produces clean, trustworthy, point-in-time-correct crypto market
data behind **one access function**. Every other part of Chronos gets its
data through that single door — never from raw files or the exchange
directly (a test enforces this). Its four rules:

1. **No future leakage** — the still-forming bar is never served.
2. **Reproducibility** — data is content-hashed; a result can be pinned to
   an exact snapshot.
3. **One data door** — all reads go through `get_bars()`.
4. **Honest validation** — problems are reported, never silently fixed.

## Project layout

```
src/chronos/oceanus/   the Oceanus code (read in this order)
  model.py             the Bar schema and Timeframe enum
  ingest.py            fetch OHLCV from Binance via ccxt (paginated, idempotent)
  store.py             Parquet storage, versioned snapshots, content hashing
  validate.py          detect data problems — never fixes anything
  clean.py             the explicit cleaning policy — every change reported
  access.py            the one door: get_bars() and universe_at()
tests/oceanus/         tests, incl. test_acceptance.py (the contract)
data/                  stored market data (not in git)
scripts/check_setup.py environment sanity check
HANDOFF.md             notes for the reviewing developer and quant
```

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync                                 # environment from the lockfile
uv run python scripts/check_setup.py    # prints "Oceanus setup OK"
```

## Getting data (the one door)

```python
from datetime import datetime, timezone
from chronos.oceanus.access import get_bars, universe_at
from chronos.oceanus.model import Timeframe

bars = get_bars(
    "BTC/USDT",
    Timeframe.H1,
    datetime(2026, 6, 1, tzinfo=timezone.utc),   # timestamps must be UTC-aware
    datetime(2026, 7, 1, tzinfo=timezone.utc),   # end is excluded: [start, end)
)
```

First call fetches from Binance (no account needed) and stores Parquet under
`data/`; later calls serve from disk. Only completed bars come back. If the
range contains corrupt data, `get_bars` raises `DataIntegrityError` instead
of returning it.

To pin a result to an exact data snapshot:

```python
from chronos.oceanus.store import snapshot_hash
pin = snapshot_hash(bars)                        # record this with results
bars = get_bars(..., snapshot=pin)               # raises if data changed since
```

`universe_at(date)` returns the symbols tradeable as of that date.

## Validating and cleaning

```python
from chronos.oceanus.validate import validate
from chronos.oceanus.clean import clean

report = validate(bars, Timeframe.H1)   # detects; changes nothing
print(report)

result = clean(bars)                    # applies the documented policy
print(result)                           # ...and lists every change it made
```

The policy (chosen deliberately, recorded in HANDOFF.md): gaps are left and
flagged — never interpolated; outliers are flagged, not removed; only
provably impossible rows (duplicates, high < low, negative volume) are
dropped, each drop reported.

## Tests

```sh
uv run pytest -v        # 67 tests; test_acceptance.py is the contract
```

## Diagnostic tools

```sh
uv run python scripts/selftest.py           # 10 live PASS/FAIL checks vs Binance
uv run python scripts/see_data.py           # fetch + chart real data (oceanus_preview.png)
uv run python scripts/restatement_probe.py  # detect if the exchange revised old candles
```

The restatement probe records a baseline of a fixed historical range on its
first run, then reports on later runs whether any old bars have changed.
Re-baseline (accept current data) with `--update`.
