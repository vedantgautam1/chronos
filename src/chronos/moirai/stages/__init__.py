"""stages/ — the Moirai test roster (spec §4).

The free stages (zero engine runs) landed in Phase 4a: 4.0 eligibility, 4.3 deflated
Sharpe, 4.4 trade-shuffle. Phase 4b adds the first re-run stages: 4.1 signal-only
null gate (a capture pass) and 4.2 parameter plateau (0–K SEARCH neighbor runs; the
only stage that finalizes N). Phase 4c adds the six re-run gates, all sharing the one
`moirai/rerun.py` VERIFICATION re-run helper: session 1 landed 4.5 cost stress, 4.6
capacity, 4.7 shifted-window stability; session 2 completes the roster with 4.8
sub-period stability (HAC aggregate), 4.9 full-engine null benchmark, and 4.10
descriptive reporting (no gates). Each reads the BacktestResult and/or the store,
computes, compares to a config threshold, and returns a TestOutcome. With this the
full eleven-stage pipeline (4.0–4.10) exists.

Every gate threshold is read from `ctx.config.thresholds` (I9); no numeric gate
literal appears in this package (probe G2 greps for exactly that).
"""

from chronos.moirai.stages.eligibility import Eligibility
from chronos.moirai.stages.signal_null import SignalNull
from chronos.moirai.stages.plateau import Plateau
from chronos.moirai.stages.deflated_sharpe import DeflatedSharpe
from chronos.moirai.stages.trade_shuffle import TradeShuffle
from chronos.moirai.stages.cost_stress import CostStress
from chronos.moirai.stages.capacity import Capacity
from chronos.moirai.stages.shift import ShiftedWindow
from chronos.moirai.stages.subperiod import SubPeriod
from chronos.moirai.stages.null_bench import NullBenchmark
from chronos.moirai.stages.descriptive import Descriptive

__all__ = [
    "Eligibility", "SignalNull", "Plateau", "DeflatedSharpe", "TradeShuffle",
    "CostStress", "Capacity", "ShiftedWindow", "SubPeriod", "NullBenchmark",
    "Descriptive",
]
