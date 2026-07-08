# Chronos

A systematic trading research system, built in components. This repository
currently contains **Oceanus**, the data layer.

## What Oceanus is

Oceanus produces clean, trustworthy, point-in-time-correct crypto market
data behind **one access function**. Every other part of Chronos will get
its data through that single door — never from raw files or the exchange
directly. Data errors here are inherited silently by everything downstream,
so this layer is treated as part of the trusted core.

## Project layout

```
src/chronos/oceanus/   the Oceanus code
  model.py             the Bar schema (Phase 1)
  ingest.py            fetch data from the exchange (Phase 2)
  store.py             save/load Parquet + snapshot hashes (Phase 3)
  validate.py          detect data problems, never fix them (Phase 4)
  clean.py             explicit, documented cleaning policy (Phase 5)
  access.py            the one data door: get_bars, universe_at (Phase 6)
tests/oceanus/         tests for each phase
data/                  stored market data (not in git)
configs/               configuration files
HANDOFF.md             decisions and open questions for the reviewers
```

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync            # create the virtual environment from the lockfile
uv run python scripts/check_setup.py   # should print "Oceanus setup OK"
```

## Running tests

```sh
uv run pytest
```

*(Ingestion/validation usage instructions will be added as those phases are built.)*
