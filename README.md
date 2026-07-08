# Chronos

A systematic trading research system, built in components. This repository
currently contains **Oceanus**, the data layer — complete as a reviewed-ready
first draft. See [HANDOFF.md](HANDOFF.md) for decisions, open questions, and
known limitations.

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
uv run pytest -v        # 53 tests; test_acceptance.py is the contract
```
