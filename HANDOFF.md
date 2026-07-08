# HANDOFF — Oceanus

Notes for the developer and quant who will review this build.
Updated at every phase. Records what was built, every decision that was
flagged to the founder (and what they chose), and every open question.

## Build log

- **Phase 0 — Project setup** (2026-07-07): git repo, `uv`-managed Python
  project (lockfile: `uv.lock`), src-layout package structure, dependencies
  pinned to exactly what Oceanus needs (ccxt, pandas, numpy, pyarrow,
  matplotlib, pytest). `data/` is gitignored.

## Decisions

*(none yet — first flagged decision comes in Phase 1: float64 vs. decimal prices)*

## Open questions / unverified details

*(none yet)*

## Failure-modes checklist (from the build brief)

- [ ] Survivorship bias — `universe_at(date)` (Phase 6)
- [ ] Partial trailing bar — `is_final` flag; `get_bars` excludes non-final (Phases 2, 6)
- [ ] Restated candles — versioned, hashed snapshots (Phase 3)
- [ ] Silent gap — `validate()` reports; `clean()` explicit policy (Phases 4, 5)
- [ ] Timezone drift — tz-aware UTC mandated (Phases 1, 4)
- [ ] Back-door reads — one-door guard test (Phase 7)
