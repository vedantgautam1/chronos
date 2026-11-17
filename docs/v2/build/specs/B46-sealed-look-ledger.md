```yaml
id: B46
title: Sealed-look ledger — one look at the unseen data per lineage, refused by the database
size: M
model: opus
who: loop
needs: [G2]
ticks: 3
touches:
  - v2/migrations/0005_sealed_looks.sql
  - v2/src/chronos2/mnemosyne/looks.py
  - v2/src/chronos2/oceanus/door.py
  - v2/src/chronos2/oceanus/series_join.py
  - v2/tests/mnemosyne/test_looks.py
  - v2/tests/oceanus/test_sealed_look_door.py
  - v2/tests/oceanus/test_series_join.py
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B46 — Sealed-look ledger

## Why
Everything from 1 April 2026 onward is data nobody is allowed to look at while researching. It is the last honest test: a strategy gets **one** look at it, at the very end. In other people's code that "one look" was a promise kept in memory, and it broke two ways: asking twice gave two looks, and a data file one day longer counted as new data. Re-looking four times let a useless idea through 16% of the time instead of 5%. So here the promise is kept by the database: a second look for the same idea, or for its close relatives, is refused by a rule the code calling it can't switch off.

## Read first
- Master doc §6 "Sealed final block"; §10 V2-D34, V2-D38, V2-D46. `BUILD_NOTES.md` §2 "Sealed holdouts touched once".
- Specs B09 (append-only machinery, error codes), B14 (the door, `purpose`), B18 (`lineage`, siblings, chains).
- PostgreSQL docs, read fresh: exclusion constraints on range types; the `btree_gist` extension and who may create it.

## The rules (fixed here)

**A look** is a row: which asset (`BTC`, `ETH`), which date range, which hypothesis asked, when. Its range is always `[the seal date, the moment of the look)` (V2-D38), so any two looks at the same asset overlap.

**A look is spent for a whole lineage at once.** When hypothesis H takes a look, one member row is written for H **and for each of its direct siblings** (B18), in the same transaction. The database refuses two member rows for the same asset and hypothesis whose ranges overlap. So:
- H asking again is refused (its own row is there);
- a sibling of H asking is refused (it was covered by H's look);
- a hypothesis with a sibling that was covered is refused too, because its own look would have to write a row for that sibling.

*(Open question O-14, the founder's: this follows the locked wording, "the hypothesis plus its siblings". A long chain of relatives, A–B–C–D–E, therefore gets roughly one look per two or three links, not one for the whole chain. Making a whole chain share one look is a change to one function, `members_for`, and is the stricter choice. Until the founder says otherwise, the locked wording stands.)*

**What the database enforces, and what it can't.**
- Wall: no second overlapping look for a hypothesis that has a member row. A look's range must start at the anchor stored for that asset. The requester must be among the members. Rows can't be changed or deleted.
- Not a wall: that the member list given is the complete lineage. It is computed in Python (B18). `audit_looks()` recomputes every look's lineage from registration times and reports any look that left out a sibling registered before it. The gate audit runs it.

**The anchor.** The first look at an asset stores the seal date for it in `mnemosyne.seal_anchor` (one row per asset and series, never changed), read from the protected file. Every later look must start there. `audit_looks()` also compares the anchors with the protected file.

**Reading sealed data.** The door (B14) gains `purpose="sealed_look"`, which needs a `look_id`: the read is allowed only if that look exists, is for that asset, and the requested range lies inside the look's range. The footprint carries the look id. `purpose="research"` is unchanged: it never reads past the seal.

**Data series that begin after the seal** (recorded trades, news; V2-D46). Before any research on such a series, its window is registered: `series_key`, the asset, `research_start`, and `X`, the date its own sealed block starts. Once registered it can't be changed. Inside `[seal date, X)`, prices of that asset may be read **only** through `join_prices_to_series`, which returns price moves around the series' own events and never a raw run of bars; its footprint is tagged with the series. Sealed looks at the series' own block `[X, …)` use the same ledger with `series_key` set.

## Deliver
1. `0005_sealed_looks.sql`: extension `btree_gist`; tables `mnemosyne.seal_anchor`, `mnemosyne.sealed_look`, `mnemosyne.sealed_look_member` with `EXCLUDE USING gist (asset WITH =, series_key WITH =, hypothesis_id WITH =, look_range WITH &&)`, and `mnemosyne.series_window`; triggers for the anchor and requester rules; all append-only, hashed, journaled (B09).
2. `mnemosyne/looks.py`: `take_look(hypothesis_id, asset, look_end, *, series_key="", edge_config_hash=None) -> Look` (one transaction; raises `LookRefused` carrying the database's reason), `members_for(hypothesis_id)`, `looks_for(...)`, `register_series_window(...)`, `audit_looks(validation) -> list`.
3. `oceanus/door.py`: the `sealed_look` purpose. `oceanus/series_join.py`: `join_prices_to_series(series_key, event_times, horizon_bars) -> frame of returns from each event's next bar open over the horizon`.
4. Tests.

## Steps
1. Tests (red). 2. Migration. 3. `looks.py`. 4. The door. 5. Series windows and the join. 6. Report.

## Known answers and checks
Seal date for `BTC` and `ETH`: `2026-04-01T00:00:00Z`. Hypotheses H1 and H2 are siblings; H3 is unrelated. Error codes: `23P01` exclusion violation, `P0001` raised by our trigger, `42501` permission denied.

| # | Action | Result |
|---|---|---|
| 1 | H1 takes a look at BTC, ending `2026-11-01T00:00:00Z` | stored; two member rows (H1, H2) |
| 2 | H1 again, ending `2026-12-01` | refused, `23P01` |
| 3 | H1 again, ending `2026-11-02` (one day more: the S13 trap) | refused, `23P01` |
| 4 | H2 (the sibling) asks | refused, `23P01` |
| 5 | H3 asks | stored |
| 6 | H1 asks for ETH | stored (another asset) |
| 7 | A look whose range starts `2026-07-01` | refused, `P0001` (must start at the anchor) |
| 8 | Member rows written without the requester among them | refused, `P0001` |
| 9 | After any refusal | no row of the refused look exists (all or nothing) |
| 10 | Chain: A–B siblings, B–C siblings, A–C not. A looks; then C asks | A stored; C refused, `23P01` (its look would cover B again) |
| 11 | Same chain extended C–D, D–E. D asks | stored, covering C, D, E (this is the gap O-14 describes; the test pins today's behaviour) |
| 12 | The 8 attacks of B09 on each of the four tables | refused with B09's codes |
| 13 | Two sessions take the same look at once (20 trials) | exactly one succeeds each time |

**Door.**
- `sealed_look` without a `look_id` → refused. With look #1: bars in `[2026-04-01, 2026-11-01)` are returned and the footprint names the look. Asking to `2026-11-01T01:00Z` → refused. Asking for ETH with a BTC look → refused.
- `research` for `[2026-03-01, 2026-04-01T00:00Z)` still works; one bar later is still refused, with or without a look.

**Audit.** A look stored with members {H1} although H2 was registered as its sibling before the look → `audit_looks` returns it. A sibling registered **after** the look is not reported. An anchor that differs from the protected file is reported.

**Series windows.**
- Register `kraken-trades` on BTC, research from `2026-06-01`, X `= 2027-01-01`. Registering it again with another X → refused.
- `join_prices_to_series` for events inside `[2026-06-01, 2027-01-01)` returns one row of returns per event and a footprint tagged `kraken-trades`. An event outside the window → refused. No function in `series_join.py` returns a frame of consecutive bars (asserted on the return shape: one row per event).
- `research` reads of BTC bars after the seal are still refused, series or no series.
- A look by H3 at the `kraken-trades` block and a look by H3 at plain BTC don't block each other: both are stored (different `series_key`).

## Not in this build
Deciding when to look (B47's verdict state) · running the candidate on the sealed block (B48) · recording which sealed dates other families' research has read on a confirm record (B48 reads the footprints) · O-14.

## Halt if
- `btree_gist` can't be created by the database owner in CI or on the Mac's Postgres.
- An exclusion constraint can't be made append-only-safe with B09's triggers.
- The size budget won't hold: move series windows and the join to their own build, and say so.

## For the gate
`BUILD_NOTES.md` §2 (this build edits it): "V2-D34 is enforced by an exclusion constraint on member rows (B46); the member list is audited, not walled". Open question O-14 with test #11 as its concrete example.
