# Closing handoff — Moirai Phase 4c session 1 (cost stress 4.5, capacity 4.6, shifted-window 4.7 + the shared re-run helper)

**Date:** 2026-08-03 · **Model:** Opus · **Protected paths touched:** `moirai/`,
`tests/moirai/`, plus ONE read-only addition to `oceanus/access.py` (full diff shown,
founder-approved before commit). **Tests: 258 → 284, all green.**

---

## What landed — the first three re-run gates, one shared door

| moira_id (byte-matches v001 `pipeline_order`) | file | gate |
|---|---|---|
| `M4.5-cost-stress` | `moirai/stages/cost_stress.py` | at 10 bps: net>0 AND per-bar Sharpe ≥ margin (0.005/bar, provisional-active); the dominated 5 bps must also pass (else `non_monotone_cost_response`); 25 bps reporting-only |
| `M4.6-capacity` | `moirai/stages/capacity.py` | at 10×: per-bar Sharpe degrades ≤ 0.3 of base AND remainder-cancelled notional ≤ 0.2 of intended; 100× reporting-only |
| `M4.7-shift` | `moirai/stages/shift.py` | ≥ 0.8 of the 4 offsets have per-bar Sharpe within 50% of base; forward guards refuse sealed / past-data shifts |

**`moirai/rerun.py` — the shared VERIFICATION re-run helper, built ONCE.**
`rerun_candidate(ctx, config, **kwargs) -> Rerun(result, wall_clock_s)`. The stage owns
the config derivation (`dataclasses.replace`); the helper only runs it:
`ctx.run(kind=VERIFICATION, config=…, strategy=ctx.candidate.strategy,
hypothesis=ctx.candidate.hypothesis, **kwargs)`, wall-clock-timed, raising if
`ctx.candidate is None`. Data-supply is **verbatim with 4.1/4.2** — no data kwargs in
production (data comes from the config through the one Oceanus door); `**kwargs` is only
the data_root/exchange test seam. Also exports `net_return` (prod(1+r)−1, from the
returns series as-is) and `per_bar_sharpe`. 4.5/4.6/4.7 call ONLY this to re-run; 4.8/4.9
inherit it. Named to avoid the engine's internal run tokens (one-door grep stays clean).

**`oceanus.access.available_range` — the one out-of-`moirai/` change.**
`(symbol, timeframe) -> (first_open, last_open + 1 bar) | None`, read-only (no fetch, no
network, no seal bypass). 4.7's "past available data" forward guard needs the stored
coverage, and I7 forbids the Moirai from reading `data/`, so the query lives in Oceanus.
Founder-approved as a scoped, read-only addition.

## Pre-code ground truth (confirmed in the repo, not from memory)

- `RunConfig` fields (run.py) and `CostConfig` fields (`slippage_bps`,
  `half_spread_bps`, `taker_fee_bps`, `provisional_constants` — costs.py) confirmed
  before writing; all frozen dataclasses, modified via `dataclasses.replace`.
- **4.1's data-supply pattern passes ZERO data kwargs** — the data lives in
  `base_config`, read through `get_bars`. The helper copies that verbatim; there was
  nothing to invent, so no STOP-AND-FLAG on data-supply.
- `OrderEvent` carries `qty` (a quantity, NOT notional). A participation-cap
  `REMAINDER_CANCELLED` (broker.py:158) shares its `order_id` with the fill of the same
  bar (broker.py:144) at the same exec price → remainder notional = `qty × that fill's
  price`. The extraction handles the limit-not-through remainder (no matching fill,
  never produced by the market-only milestone) by excluding + counting it.
- `BacktestResult.returns` used as-is (never recomputed); per-bar Sharpe via
  `statistics.per_bar_sharpe`.

## The two founder decisions taken this phase (2026-08-03)

1. **cost_summary is never scaled (trap #6).** Every level is a full engine re-run at
   that absolute `CostConfig`; the stage ignores `cost_summary` for stressing. A CI
   test spies **three real VERIFICATION `ctx.run` calls** with distinct config hashes
   and one identical data hash — structurally proving no line-item shortcut. Spread
   scaled in proportion (`half_spread = base_half × L/base_slippage`), taker held; the
   rule is stamped into evidence.
2. **4.7 sign-agreement sub-gate built DORMANT (a DROPPED SPEC GATE, not a rename).**
   Spec §4.7 also requires the sign of net return to agree with the base in
   ≥ `shift.min_sign_agree` of (base + shifts). v001 carries no such key. Building it
   live would force either a hardcoded literal (trips G2) or a v001 re-key (I9/hash
   change, out of scope) — so it is built dormant: it reads `shift.min_sign_agree` from
   config, and absent under v001 it reports `active:false` with a note and does NOT
   touch the verdict. v002 activates it by adding + **calibrating** the one key. This is
   the founder's synthesis of the two review answers (build the logic now, dormant; it
   correctly does not act under v001; log it separately from the renames).

## v002 reconciliation — now 7 renames + 1 dropped spec gate

Two 4.5 renames added → the rename list stands at **7**:
`cost_stress.gate_level` → `cost_stress.gate_level_bps`;
`cost_stress.margin_sharpe` → `cost_stress.margin_per_bar_sharpe`. (4.7's
`offsets_weeks`→`offsets_w` and `sharpe_band`→`max_sharpe_deviation_pct`/`pass_fraction`
are also renames.) **Logged SEPARATELY** in HANDOFF.md: the §4.7 net-return
sign-agreement gate is a **dropped spec gate** whose v002 action is **design + build +
calibrate** (`shift.min_sign_agree`), NOT a rename — do not collapse it into the list.

## Checkpoint (real output, milestone 4.0–4.7, full-eval; numbers in SESSION_FINDINGS)

- **4.5:** base net −9.08% (reproduces trial #285), monotone to −14.72% / −21.29% /
  −38.18% at 5/10/25 bps → **FAIL `cost_gate_fail`**.
- **4.6:** 10× Sharpe unchanged (degradation ≈4.7e-08, remainder 0.0) → **PASS**; 100×
  remainder 3.28% (reporting). Capacity is not the milestone's binding constraint.
- **4.7:** +1w within band; −2w/−1w/+2w REFUSED (past_available_data — the 6-month dev
  window sits at the stored-data edge 2026-01-01→2026-07-08) → 1/4 < 0.8 → **FAIL**.
  Forward guard working; sign-agreement sub-gate dormant.
- **Throughput (first real samples):** 6 re-runs, **median 1.415 s/run**. Session 2's
  ~200-run 4.9 ≈ 4.7 min (feasible); the Phase 6 calibration nest is the real budget
  wall — size against 1.4 s.

## Tests added (26 → 284 total)

`test_rerun.py` (candidate guard, real run + positive wall-clock, metrics-as-is),
`test_cost_stress.py` (monotone PASS, non-monotone FAIL, gate-fail, margin boundary
active/inactive, candidate guard, **3-real-VERIFICATION-runs spy**), `test_capacity.py`
(remainder extraction incl. unpriced/non-remainder/empty, degradation boundary, 100×
reporting-only, Decimal scaling, candidate guard), `test_shift.py` (4→4 runs +
determinism, sealed-range refusal, past-data refusal, pass-fraction boundary, candidate
guard, sign-agreement sub-gate dormant-under-v001 + activates-with-v002-key).

## STOP-AND-FLAG items checked (none forced a halt)

- 4.1 data-supply reused cleanly (zero kwargs). ✅
- 4.5 buildable without a `cost_summary` shortcut (3 real runs, spied). ✅
- Throughput NOT large enough to make session 2's 4.9 infeasible (1.4 s → 4.7 min). ✅
- Spec-vs-v001 drift beyond the two named turned up (4.7 sign-agreement) → surfaced to
  the founder, resolved (dormant build + separate v002 entry), not pushed through. ✅

## For session 2

4.8 sub-period stability (K year-long windows + one-sided HAC t via Newey–West — the
first pre-Atropos NW consumer; N-laundering warning binding), 4.9 full-engine null
benchmark (~200 cadence-matched VERIFICATION nulls — the expensive wall), 4.10
descriptive (no gates). All inherit `moirai/rerun.py`.
`scripts/moirai_phase4c_checkpoint.py` extends to the full pipeline.
