```yaml
id: B07
title: Trial store I — Postgres harness, migrations, append-only, audit
size: M
model: opus
who: loop
needs: [G1]
ticks: 3
touches:
  - v2/pyproject.toml
  - v2/uv.lock
  - v2/migrations/**
  - v2/src/chronos2/mnemosyne/**
  - v2/tests/mnemosyne/**
  - v2/tests/conftest.py
  - .github/workflows/v2.yml
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B07 — Trial store I

## Why
Mnemosyne is the memory that keeps Chronos honest: every try is recorded and none can be quietly changed or removed. "Can't be changed" has to be true in the database itself, not just in our Python, because a rule that lives only in application code is one bug away from not existing. In a tested example, database rules blocked 8 of 8 destructive statements; without them 6 of 8 went through [Certain — run, S12].

Postgres is used from this build on (founder, 16 Nov). No server is needed: tests use a local Postgres on whatever machine runs them.

## Read first
- `BUILD_NOTES.md` §6 (all). Master doc §4 row "Mnemosyne".
- v1 `src/chronos/mnemosyne/stub.py` (60 lines) for the append-only idea only.

## Deliver
1. Dependency `psycopg[binary]` (v3). No ORM.
2. **Test harness** in `v2/tests/conftest.py`: reads `CHRONOS2_TEST_DSN` (default `postgresql://postgres@localhost:5432/postgres`); creates a database `chronos2_test_<random>` per test session, applies all migrations, yields connections, drops it at the end. If Postgres isn't reachable the database tests **fail** with a one-line instruction; they never skip. (How to start it: CI has a `postgres:16` service; a cloud session runs `pg_ctlcluster 16 main start`; on the Mac, the handbook §6.)
3. **Migration runner** `mnemosyne/migrate.py`: applies `v2/migrations/NNNN_name.sql` in order, each in a transaction, recording name and SHA-256 in `mnemosyne.schema_migrations`. Refuses to run if an already-applied file's hash changed.
4. `0001_foundation.sql`:
   - schema `mnemosyne`; roles `chronos_owner` (owns objects) and `chronos_app` (what code connects as: `INSERT` and `SELECT` only, no `UPDATE`, `DELETE`, `TRUNCATE`, no DDL);
   - function `mnemosyne.make_append_only(regclass)`: installs row triggers that raise on `UPDATE` and `DELETE` and a statement trigger that raises on `TRUNCATE`, for **every** role including the owner;
   - table `mnemosyne.journal` (`seq bigserial`, `at timestamptz`, `kind text`, `subject text`, `payload jsonb`, `row_hash text`), made append-only. Every later table writes one journal line per insert; the journal is the audit trail.
5. `mnemosyne/db.py`: `connect(dsn, role)`; `insert_journal(conn, kind, subject, payload)` computing `row_hash = content_hash({at, kind, subject, payload})` with `core.canonical` (B01).
6. `mnemosyne/audit.py`: `audit(conn) -> list[Finding]` recomputes every `row_hash` in every append-only table and reports mismatches and gaps in `seq`.

## Steps
1. Harness + a trivial "can connect, can create and drop the test database" test. Commit.
2. Commit the attack tests below (red).
3. Migration runner, `0001`.
4. `db.py`, `audit.py` → green.
5. CI: the **tests** job waits for the Postgres service and exports the DSN.
6. Docs, report.

## Known answers and checks
**The attack list.** Connected as `chronos_app`, after inserting three journal rows, each of these must raise, and afterwards the table must hold the same three rows with the same hashes:
1. `UPDATE mnemosyne.journal SET payload = '{}'`
2. `UPDATE mnemosyne.journal SET row_hash = 'x' WHERE seq = 1`
3. `DELETE FROM mnemosyne.journal WHERE seq = 2`
4. `DELETE FROM mnemosyne.journal`
5. `TRUNCATE mnemosyne.journal`
6. `DROP TABLE mnemosyne.journal`
7. `ALTER TABLE mnemosyne.journal DISABLE TRIGGER ALL`
8. `INSERT … ON CONFLICT (seq) DO UPDATE SET payload = '{}'`

Result required: **8 of 8 refused.** Then statements 1–5 again as `chronos_owner`: also refused (the triggers, not just the permissions).

**Audit catches what gets through anyway.** As a superuser, disable the triggers, change one payload, re-enable. `audit()` returns exactly one finding, naming that `seq`. Delete one row the same way: `audit()` reports the gap.

**Migrations.** Applying twice is a no-op. Editing an applied file's content makes the runner refuse, naming the file.

**Hash.** `row_hash` for the fixed row `{at: 2026-01-01T00:00:00Z, kind: "test", subject: "s", payload: {"a": 1}}` equals the value the test computes with `content_hash`, and is stable across runs.

**No skips:** `pytest -q -rs` shows zero skipped tests.

## Not in this build
Hypotheses and trials (B08) · a hash chain with its head stored elsewhere (phase 6, with the guard stack; noted in `BUILD_NOTES.md` §6 as the next step) · backups.

## Halt if
- The owner role can't be stopped by triggers without also stopping migrations. (Then append-only for the owner needs a different mechanism, and that is a design fork.)
- Postgres 16 in CI and the version in a cloud session behave differently on any attack.

## Doc rows to update
`COMPONENTS.md` §1 PostgreSQL row: version, "used from B07; tests need a local Postgres". Master doc §2a Mnemosyne row → In progress.
