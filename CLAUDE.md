# CLAUDE.md — Rules of engagement for this repository

This is Chronos: systematic trading research infrastructure whose entire
purpose is to be honest enough to reject almost every strategy fed to it.
Correctness under adversarial self-deception outranks speed, elegance, and
helpfulness. When in doubt: stop and flag, don't guess.

## Invariants (violating any is a build-breaking bug, not a style issue)

- **I1** No future leakage — strategies see only data with timestamp ≤ now.
- **I2** Costs always applied — no cost-free path exists in the trusted engine.
- **I3** Every run logged — execution only via `run_experiment()`; a record
  is written on every exit path, including crashes.
- **I4** The holdout is sealed — `get_bars()` refuses ranges in
  `configs/sealed_ranges.json` without a `FinalEvaluationToken`. Sealing
  is additive-only; there is no unseal.
- **I5** Determinism from FIVE coordinates: (code SHA, config hash, data
  snapshot hash, seed, candidate_n). A differing search-N is a legitimate
  difference, not a determinism failure.
- **I6** Every execution logged with a monotonic index AND a `kind` tag:
  `SEARCH` (a point in a parameter search — counts toward the DSR's N via
  `compute_search_n()`) or `VERIFICATION` (standalone runs, walk-forward
  windows, cost stress, null benchmarks — never counts toward N).
- **I7** One data door — only `oceanus/` touches ccxt or `data/`.
- **I8** Hypothesis precedes results — pre-registered, non-empty, immutable.
- **I9** The judge is fixed before the trial — gauntlet thresholds are a
  hashed, versioned artifact (`gauntlet_config_hash`); enforcement lives
  in the Moirai.

## Hard rules for any Claude Code session

1. **Protected paths — show a full diff and WAIT for explicit approval:**
   `moirai/` (when it exists), cost model & fill logic in `hephaestus/`,
   Oceanus validation & `seal.py`, the Mnemosyne schema, everything under
   `tests/hephaestus/invariants/`, and the hand-computed fixtures.
2. **Read files fresh before editing.** Never edit from memory of an
   earlier view.
3. **Never loosen a test assertion to make it pass.** Fix the cause.
4. **`kind=` is explicit at every `run_experiment()` call site.** Sweeps
   use ONE hypothesis via `register_search()` reused across all points —
   never one hypothesis per point.
5. **Never backfill legacy records** (trial_index ≤ 284: no `kind`,
   produced under the old 10bps cost default, not comparable across that
   boundary).
6. **Statistical methods enter the core only from primary sources with
   passing known-answer tests** (see spec §15). LLM memory — including
   yours — is explicitly not a source. R6/R7 are assumptions (spec §16):
   verdicts depending on them report ranges, not points.
7. **DSR/PSR consume the NON-annualized Sharpe** at native bar frequency;
   `SR*` must be floored at 0 (it is negative at small N). N comes from
   `compute_search_n()`, never from `trial_counter.txt`.
8. **Stop-and-flag beats silently fixing.** If a change forks into
   non-equivalent options, present both and ask. This has been right
   every time it happened.
9. **"Tests green" ≠ "it works."** After structural changes, actually run
   `scripts/run_milestone.py` end-to-end before declaring done.
10. Regenerable derived artifacts (`*.npy` from extraction scripts,
    generated PNGs) stay uncommitted unless explicitly requested;
    `records/` and `data/` are gitignored by design.

## Conventions

Decimal ledger for accounting, float64 for series math · next-bar-open
fills (unsafe same-bar path is flag-gated and logged) · half-open
`[start, end)` ranges, tz-aware UTC everywhere · cancel-and-record for
unfilled remainders · cost defaults: taker 10bps, slippage 1bps
(R6-measured 2026-07-17; hand-computed fixtures are deliberately pinned
to an explicit 10bps and must not be "updated") · `uv` for env,
`pip install` never; `uv run --with` for one-off deps.

## Where the truth lives

- `HANDOFF.md` — dated decisions log; the ground truth of why things are
  the way they are. Append dated entries for every structural change.
- `HEPHAESTUS_SPEC.md` — engine spec; §10 is the Moirai boundary
  contract; §15/§16 the split registers; Appendix A the metric rules.
- `SESSION_FINDINGS.md` — the empirical results (V[{SR_n}]=8.66e-05, the
  0.563-vs-0.054 DSR laundering demo, detection floor ≈2.3 annualized).
- `chronos_math_probe.py` — verified statistical implementations with
  28 known-answer checks; promotion to `tests/statistics/` is a planned
  task.

When a request conflicts with anything above, say so and stop. The founder
is non-technical; your caution is part of the review process, not an
obstacle to it.
