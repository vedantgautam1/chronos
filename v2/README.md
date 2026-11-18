# chronos2

Chronos v2 lives here, separate from the frozen v1 `chronos` package.

## Run the tests

    cd v2
    uv sync --all-groups
    TZ=UTC uv run pytest -q

Lint: `uv run ruff check .`

One test needs Postgres (the `SELECT 1` connectivity check); it reads
`CHRONOS2_TEST_DSN` (default `postgresql://postgres@localhost:5432/postgres`).
