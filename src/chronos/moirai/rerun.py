"""rerun.py — the ONE shared VERIFICATION re-run helper for the re-run gates.

Stages 4.5 (cost stress), 4.6 (capacity), 4.7 (shifted window), 4.8 (sub-period), and
4.9 (null benchmark) all do the same thing: derive a modified `RunConfig` from
`ctx.candidate`, push it through the engine exactly once as a `kind=VERIFICATION`
execution, and judge the resulting `BacktestResult`. This module is that single door,
built once so each stage only supplies the modified config; no stage re-derives the run
call, and no stage re-derives the data-supply pattern.

Stage 4.9 is the one caller that re-runs a DIFFERENT strategy (a cadence-matched null)
under a DIFFERENT hypothesis id (`<candidate>:null:<i>`) on the candidate's window, so
`rerun_candidate` takes optional `strategy=`/`hypothesis=` overrides that default to
`ctx.candidate`'s. Everything else — the timing, the VERIFICATION kind, the data-supply
pattern — is identical, which is the point of keeping ONE door.

**Data-supply pattern (verbatim with 4.1/4.2).** The candidate's data comes entirely
from its `RunConfig` — symbol, timeframe, [start, end), costs — read through the one
Oceanus door inside `run_experiment`. Neither stage 4.1 nor 4.2 passes any data
kwargs, and neither does this helper by default: there is no invented data path.
`**kwargs` are forwarded to `ctx.run` verbatim, which is purely the test seam for
injecting `data_root`/`exchange` (exactly as `tests/moirai/test_signal_null.py`
patches `ctx.run`); production callers pass none.

**Throughput instrumentation.** Every re-run is wall-clock timed. The per-engine-run
cost is otherwise only *inferred* from bar counts (STATE.md "Blocking"); these are
the first real samples, and Phase 5/6's calibration-budget decision (stage 4.9's
~200 null runs per candidate) hinges on them. Each stage stamps its per-run seconds
into evidence; the session rolls them up in SESSION_FINDINGS.md.

Kind accounting: every re-run here is `VERIFICATION` — a standalone, counted, logged
execution that never counts toward the DSR's N (I6, §4.5–4.9). SEARCH is already
frozen by stage 4.2, so a stray SEARCH would raise anyway.

NAMING: this module deliberately uses "rerun" vocabulary and never the engine's
internal run tokens, so the one-door engine-guard grep stays clean.
"""

import time
from dataclasses import dataclass

import numpy as np

from chronos.hephaestus.types import BacktestResult
from chronos.moirai import statistics as stats
from chronos.moirai.context import GauntletContext
from chronos.run import RunConfig, RunKind


def _returns_array(result: BacktestResult) -> np.ndarray:
    """The run's per-bar simple returns as a float array — the engine's own series,
    used AS-IS (never recomputed; §4.5–4.7). `returns_from_equity` already derived
    it once at run time (spec §7); every re-run gate reads the same numbers."""
    r = result.returns
    values = r.to_list() if hasattr(r, "to_list") else list(r)
    return np.asarray(values, dtype=float)


def per_bar_sharpe(result: BacktestResult) -> float:
    """Non-annualized per-bar Sharpe of the run (statistics.per_bar_sharpe on the
    returns series, native H1 frequency — CLAUDE.md rule 7). The one statistic
    4.5/4.6/4.7 compare across re-runs."""
    return stats.per_bar_sharpe(_returns_array(result))


def net_return(result: BacktestResult) -> float:
    """Total compounded net return over the run, aggregated from the per-bar returns
    AS-IS: prod(1 + r) - 1. Equal by construction to equity[-1]/equity[0] - 1 (the
    first return is 0 by convention), so this reads the engine's own P&L without
    recomputing the return series. NOT a rescale of line items — this is the whole
    point of 4.5: costs are path-dependent, so each level is a real engine re-run."""
    r = _returns_array(result)
    if r.size == 0:
        return 0.0
    return float(np.prod(1.0 + r) - 1.0)


@dataclass(frozen=True)
class Rerun:
    """One re-run's `BacktestResult` plus the wall-clock seconds the engine run took
    (throughput instrumentation). `wall_clock_s` is measured, so it is never part of
    any determinism byte-compare — it is reported, not gated on."""

    result: BacktestResult
    wall_clock_s: float


def rerun_candidate(ctx: GauntletContext, config: RunConfig, *,
                    strategy=None, hypothesis=None, **kwargs) -> Rerun:
    """Re-run through the engine at `config` as a single `kind=VERIFICATION` execution;
    return the `BacktestResult` and the measured wall-clock seconds.

    `config` is the caller's already-modified `RunConfig` (cost-stressed, cash-scaled,
    window-shifted, sub-window — the stage owns that derivation via
    `dataclasses.replace`). `strategy`/`hypothesis` default to `ctx.candidate`'s; stage
    4.9 overrides them to push a cadence-matched null (a different strategy under
    `<candidate>:null:<i>`) through the same timed door. The data comes from `config`
    through the one Oceanus door. `**kwargs` are forwarded to `ctx.run` verbatim (the
    data_root/exchange test seam only).

    Raises `ValueError` if `ctx.candidate` is None — a re-run gate cannot guess a
    candidate to run against; there is nothing to run (mirrors 4.1's and 4.2's own
    guards). This holds even for a null override: the null exists only to benchmark a
    real candidate."""
    if ctx.candidate is None:
        raise ValueError(
            "re-run gates (4.5–4.9) need ctx.candidate (strategy + base config "
            "+ hypothesis) to re-run the engine; none was provided — nothing to run."
        )
    started = time.perf_counter()
    record = ctx.run(
        kind=RunKind.VERIFICATION,
        config=config,
        strategy=strategy if strategy is not None else ctx.candidate.strategy,
        hypothesis=hypothesis if hypothesis is not None else ctx.candidate.hypothesis,
        **kwargs,
    )
    return Rerun(result=record.result, wall_clock_s=time.perf_counter() - started)
