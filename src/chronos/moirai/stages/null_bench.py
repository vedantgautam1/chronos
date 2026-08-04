"""null_bench.py — stage 4.9, Full-engine null benchmark (spec §4.9, R5-adjacent).

The expensive last wall: rank the candidate against `null_bench.n_nulls` cadence-matched
random strategies pushed through the REAL engine with REAL costs. Each null has the same
entry COUNT as the candidate and holding durations RESAMPLED from the candidate's own
realized durations, its entry bars placed uniformly at random without overlap, long-only
(spot). Each null runs `kind=VERIFICATION` (via the shared `rerun_candidate` helper, with
a null strategy/hypothesis override) under hypothesis id `<candidate>:null:<i>` — the
`:null:` id is the store-filter convention.

**Look-ahead is forbidden by construction.** `nulls.place_null_entries` receives only
the bar COUNT, the duration distribution, and `ctx.rng` — never the price series — so no
null can be placed using price information. The property is structural (there is no price
parameter) and tested. RNG is `ctx.rng` ONLY (I10): a fixed gauntlet seed gives identical
null placements.

This asks the state-aware, cost-aware question 4.1 cannot: does the rule beat luck AFTER
costs, fills, caps, and its own cadence are priced in — a rule whose only "edge" is
trading rarely (so paying little) scores well here only if random same-cadence trading
does not.

Gate: candidate net return > the `null_bench.percentile_gate`-th percentile of the null
net-return distribution. **v001 ships `null_bench.percentile_gate: 95` as an INTEGER
percentile** (spec §4.9 writes `null_bench.percentile: 0.95` as a fraction — v002
reconciliation); it is read here as a percentile (95), never as a fraction.

Kind accounting: `n_nulls` × VERIFICATION (the audit counter advances by that many per
candidate — honest and intended; the `:null:` id tags them for filtering).
"""

from dataclasses import replace

import numpy as np

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.context import GauntletContext
from chronos.moirai.nulls import NullStrategy, place_null_entries
from chronos.moirai.rerun import net_return, rerun_candidate
from chronos.moirai.round_trips import reconstruct_round_trips
from chronos.moirai.types import TestOutcome
from chronos.run import Hypothesis

MOIRA_ID = "M4.9-null-bench"

_N_NULLS_KEY = "null_bench.n_nulls"
_PERCENTILE_GATE_KEY = "null_bench.percentile_gate"  # spec: null_bench.percentile 0.95 (v002)


def _candidate_durations(result: BacktestResult, timeframe) -> list[int]:
    """The candidate's realized holding durations, in bars, from its closed round trips
    (FIFO reconstruction). Duration = (exit_time − entry_time) / one bar."""
    bar = timeframe.duration
    durations = []
    for rt in reconstruct_round_trips(result.trades):
        durations.append(int(round((rt.exit_time - rt.entry_time) / bar)))
    return [d for d in durations if d >= 1]


class NullBenchmark:
    """Stage 4.9. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.9 needs ctx.candidate (strategy + base config + hypothesis) "
                "to benchmark against cadence-matched nulls; none was provided."
            )
        base_config = ctx.candidate.base_config
        cand_hyp = ctx.candidate.hypothesis
        symbol = base_config.symbol

        durations = _candidate_durations(result, base_config.timeframe)
        n_entries = len(durations)
        n_bars = int(result.bars_processed)
        n_nulls = int(ctx.config.thresholds[_N_NULLS_KEY])
        percentile_gate = ctx.config.thresholds[_PERCENTILE_GATE_KEY]
        candidate_net = net_return(result)

        evidence: dict = {
            "candidate_net_return": candidate_net,
            "n_entries": n_entries,
            "n_bars": n_bars,
            "n_nulls": n_nulls,
            "percentile_gate": percentile_gate,
            "null_id_convention": f"{cand_hyp.id}:null:<i>",
            "look_ahead_note": (
                "null placement (nulls.place_null_entries) receives only the bar count, "
                "the duration distribution, and ctx.rng — never prices; zero look-ahead "
                "by construction (spec §4.9)."),
            "kind_accounting": f"{n_nulls} × VERIFICATION (tagged :null:, never toward N)",
        }

        if n_entries == 0:
            evidence["reason"] = "no_candidate_round_trips"
            evidence["no_trades_note"] = (
                "the candidate has no closed round trips, so there is no cadence to "
                "match; a null benchmark cannot be constructed. Unjudgeable — does not "
                "pass (breadth is 4.0's gate).")
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        null_nets: list[float] = []
        wall_clocks: list[float] = []
        for i in range(n_nulls):
            intervals = place_null_entries(n_bars, durations, n_entries, ctx.rng)
            null_strategy = NullStrategy(symbol, intervals)
            null_hyp = Hypothesis(
                id=f"{cand_hyp.id}:null:{i}",
                statement=(f"cadence-matched random null #{i} for {cand_hyp.id}: same "
                           "entry count and holding-duration distribution, entries "
                           "placed at random without look-ahead."),
                prediction="net return should sit within the luck distribution, not beat it.",
            )
            rr = rerun_candidate(ctx, base_config, strategy=null_strategy,
                                 hypothesis=null_hyp)
            wall_clocks.append(rr.wall_clock_s)
            null_nets.append(net_return(rr.result))

        nulls = np.asarray(null_nets, float)
        threshold_value = float(np.percentile(nulls, percentile_gate))
        passed = bool(candidate_net > threshold_value)
        # Candidate's own percentile within the null distribution (share strictly below).
        candidate_percentile = float(np.mean(nulls < candidate_net) * 100.0)

        evidence.update({
            "gate_threshold_net_return": threshold_value,
            "candidate_percentile_in_null_dist": candidate_percentile,
            "null_distribution": {
                "min": float(nulls.min()), "p25": float(np.percentile(nulls, 25)),
                "median": float(np.median(nulls)), "p75": float(np.percentile(nulls, 75)),
                "p95": float(np.percentile(nulls, 95)), "max": float(nulls.max()),
                "mean": float(nulls.mean()), "std": float(nulls.std(ddof=1)),
            },
            "run_wall_clock_s": wall_clocks,
        })
        if not passed:
            evidence["reason"] = "does_not_beat_null_benchmark"

        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=candidate_percentile, evidence=evidence)
