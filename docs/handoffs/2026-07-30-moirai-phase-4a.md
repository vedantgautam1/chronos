# Closing handoff — Moirai Phase 4a (free stages 4.0/4.3/4.4, probe G8)

**Date:** 2026-07-30 · **Model:** Opus · **Protected paths touched:** `moirai/`,
`tests/moirai/`, `tests/statistics/` (full diff shown, founder-approved before
commit). **Tests: 213 → 234, all green.**

---

## What landed

The three "free" stages — zero engine runs, one shared shape (read the
`BacktestResult` and/or the store, compute, compare to a config threshold, return a
`TestOutcome`):

| moira_id (byte-matches v001 `pipeline_order`) | file | gate |
|---|---|---|
| `M4.0-eligibility` | `moirai/stages/eligibility.py` | breadth (INSUFFICIENT_BREADTH), unsafe (NON_PROMOTABLE) |
| `M4.3-dsr` | `moirai/stages/deflated_sharpe.py` | DSR@rawN ≥ `dsr.confidence` |
| `M4.4-shuffle` | `moirai/stages/trade_shuffle.py` | p95 shuffled maxDD ≤ `mc_shuffle.ruin_dd` |

Supporting:
- `moirai/round_trips.py` — FIFO round-trip reconstruction shared by 4.0 and 4.4.
- `statistics.py` — added the JPM Appendix C effective-N estimator
  (`effective_trials`, `mean_pairwise_correlation`) plus `per_bar_sharpe`,
  `sample_skewness`, `sample_kurtosis`. Pinned by `tests/statistics/
  test_effective_trials.py` (10 known-answers).
- Probe **G8** (`tests/moirai/test_free_stages.py`): unsafe → NON_PROMOTABLE, zero
  downstream even under `full_evaluation_mode`.

## The four pre-code resolutions (done in the repo, not from memory)

1. **moira_ids** — read from `configs/gauntlet/v001.json` `pipeline_order`:
   `M4.0-eligibility`, `M4.3-dsr`, `M4.4-shuffle`. Unambiguous; used byte-for-byte.
2. **BacktestResult fields** — read `hephaestus/types.py`: `returns` (pd.Series),
   `trades` (tuple[Fill]), `warnings`, `bars_processed`, `hypothesis_id`, the five
   coordinates. Used verbatim.
3. **statistics.py** — had `dsr/psr/sr_star` but **NOT** the effective-N estimator
   nor a store V-reader. Added N̂ as pure math this phase (never inside a Moira).
4. **terminal-status** — reused `types.TERMINAL_STATUS_KEY` stamped into evidence
   (Phase 3 mechanism); no field added to `TestOutcome`.

## Decisions of record (also in HANDOFF.md)

- **N when `compute_search_n == 0`.** The milestone has zero SEARCH records (its
  selecting sweep is legacy). 4.3 records `search_n_raw: 0` but floors the
  deflation N to 1 (a candidate is ≥1 trial; N=1 ⇒ SR*→0 ⇒ DSR = PSR, no
  deflation). Numeric trap fixed: `sr_star(V=0, N=1) = 0*-inf = nan` → the
  `_deflated()` helper returns `psr(sr_hat, 0)` when N<2 or V non-estimable, so the
  DSR is well-defined. Result is small/FAILING (0.349), not wrong — not a stop.
- **Kept `AlwaysPass`/`AlwaysFail`** (brief said delete) — load-bearing in ~20
  `test_pipeline.py` DAG-mechanics assertions; deleting them couples pure-DAG tests
  to stage semantics and breaks green. Kept as permanent scaffolding, flagged.
- **`mc_shuffle.luck_threshold`** (v001) vs **`mc_shuffle.luck_pct`** (spec §4.4) —
  bound to the frozen artifact's key; v002 should reconcile. Same key-drift family
  awaits 4b (`plateau.*`, `null_signal.B`).

## Checkpoint (real output, not a green line)

Milestone (trial #285) reconstructed from `records/runs.jsonl` and run through the
three stages against the real store (dev config via `context_for_config`, v001.json
untouched, `full_evaluation_mode=True`):

```
verdict.status = FAIL   cause = M4.3-dsr   authority = NO_AUTHORITY
4.0 eligibility  PASS   round_trips=42≥30, provisional_cost_constants=true
4.3 dsr          FAIL   sr_hat=-0.005895 T=4344 search_n_raw=0 n_deflation=1
                        DSR@rawN=0.349 (<0.95)  effective_n=not_estimable (M=0)
4.4 shuffle      PASS   realized_maxDD=0.1365 p95_maxDD=0.2212 (≤0.40)
                        terminal_equity=0.9044 (order-invariant)
stored gauntlet_verdict carried all coordinates (config hash, moirai/engine SHA,
data snapshot hash, seed, search_n, evaluation_window, judged_run_id).
```

Numbers appended to `SESSION_FINDINGS.md`.

4.3 evidence also carries a plain-English **`deflation_note`** (added on founder
review): it states in words — not just numbers — that `search_n_raw=0`, why (legacy
sweep excluded), that N was floored to 1, the explicit `N<2-or-V-not-estimable`
guard in `_deflated` (which returns `PSR(SR*=0)` directly, encoding "no deflation"
and avoiding the `0*-inf=nan` at N=1), and that Phase 7 re-establishes N live. The
sibling branch emits a different note (real deflation applied) that does NOT mention
Phase 7 or N-flooring.

## Next — Phase 4b

4.1 signal-only null gate (SignalCapture wrapper via `ctx.run`, stationary
bootstrap) and 4.2 parameter plateau (the only N-spending stage; calls
`ctx.freeze_search()` after). Probe G6. **When 4.2 lands, 4.3 must consume the
FROZEN N and set `n_frozen: true`** (it currently reads N live and stamps
`n_frozen: false`). Reconcile the spec-vs-v001 threshold key names in v002 (Phase 6).
