"""_noop.py — trivial test-double Moirai and deterministic fixtures.

`AlwaysPass`/`AlwaysFail` began (Phase 3) as throwaway no-ops to exercise the empty
DAG. Phase 4a landed the real stages (moirai/stages/), but these two remain as
GENERIC DAG-MECHANICS SCAFFOLDING: test_pipeline.py's probes (G1 determinism,
ordering, short-circuit, full-eval, terminal-status) arrange controllable pass/fail
moirai into ~20 assertions that the real fixed-behaviour stages cannot express.
Deleting them (as the Phase 4a brief literally said) would couple pure-DAG tests to
stage semantics and reduce coverage — so they are KEPT and this deviation is flagged
in the Phase 4a handoff. `CrashMoira` and the terminal-signal moirai back G4/G8.

This module lives under `tests/` (never in the production pipeline) and is
importable by name (`tests.moirai._noop`) so probe G1's fresh-process subprocess
can rebuild the identical fixture and config it built in-process.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from chronos.hephaestus.types import CostSummary
from chronos.hephaestus.types import BacktestResult
from decimal import Decimal

from chronos.moirai.config import GauntletConfig
from chronos.moirai.types import (
    INSUFFICIENT_BREADTH,
    NON_PROMOTABLE,
    TERMINAL_STATUS_KEY,
    TestOutcome,
)


# --- The two throwaway no-ops (DELETED IN PHASE 4a) ----------------------------

class AlwaysPass:
    """Trivial pass — generic DAG-mechanics test double (see module docstring)."""

    def __init__(self, moira_id: str = "noop-always-pass"):
        self.moira_id = moira_id

    def evaluate(self, result, ctx) -> TestOutcome:
        return TestOutcome(
            moira_id=self.moira_id, passed=True, score=1.0,
            evidence={"noop": "always-pass"},
        )


class AlwaysFail:
    """Trivial fail — generic DAG-mechanics test double (see module docstring)."""

    def __init__(self, moira_id: str = "noop-always-fail"):
        self.moira_id = moira_id

    def evaluate(self, result, ctx) -> TestOutcome:
        return TestOutcome(
            moira_id=self.moira_id, passed=False, score=0.0,
            evidence={"noop": "always-fail"},
        )


# --- Test infrastructure Moirai (not the two throwaways) ----------------------

class CrashMoira:
    """Raises mid-evaluate — for probe G4 (no unlogged judgment)."""

    def __init__(self, moira_id: str = "noop-crash"):
        self.moira_id = moira_id

    def evaluate(self, result, ctx) -> TestOutcome:
        raise RuntimeError("gauntlet probe crash")


class NonPromotableMoira:
    """Emits the NON_PROMOTABLE terminal signal (mimics Phase 4a's 4.0 unsafe path)."""

    def __init__(self, moira_id: str = "noop-nonpromotable"):
        self.moira_id = moira_id

    def evaluate(self, result, ctx) -> TestOutcome:
        return TestOutcome(
            moira_id=self.moira_id, passed=False, score=0.0,
            evidence={TERMINAL_STATUS_KEY: NON_PROMOTABLE, "reason": "unsafe flag"},
        )


class InsufficientBreadthMoira:
    """Emits the INSUFFICIENT_BREADTH terminal signal (mimics 4.0's breadth gate)."""

    def __init__(self, moira_id: str = "noop-breadth"):
        self.moira_id = moira_id

    def evaluate(self, result, ctx) -> TestOutcome:
        return TestOutcome(
            moira_id=self.moira_id, passed=False, score=0.0,
            evidence={TERMINAL_STATUS_KEY: INSUFFICIENT_BREADTH, "round_trips": 5},
        )


# --- Deterministic fixtures ---------------------------------------------------

def build_fixture_result(run_id: str = "000285-H-noop") -> BacktestResult:
    """A fully deterministic BacktestResult built by hand (no engine run needed).

    Fixed coordinates and a tiny fixed equity curve so probe G1 can reconstruct
    byte-identical inputs across processes. Zero trades/events keep it minimal —
    the Phase 3 no-op pipeline judges nothing about them."""
    start = datetime(2017, 8, 17, tzinfo=timezone.utc)
    end = datetime(2017, 8, 17, 3, tzinfo=timezone.utc)
    idx = pd.date_range(start, periods=4, freq="h", tz="UTC")
    equity = pd.Series([10000.0, 10010.0, 9990.0, 10005.0], index=idx)
    returns = pd.Series([0.0, 0.001, -0.002, 0.0015], index=idx)
    return BacktestResult(
        run_id=run_id,
        core_version="fixture-core-sha",
        config_hash="fixture-config-hash",
        data_snapshot_hash="fixture-data-hash",
        seed=0,
        bars_processed=4,
        date_range=(start, end),
        symbols=("BTC/USDT",),
        timeframe="H1",
        trades=(),
        order_events=(),
        equity_curve=equity,
        returns=returns,
        cost_summary=CostSummary(
            fees=Decimal("0"), slippage=Decimal("0"), spread=Decimal("0")
        ),
        warnings=(),
        hypothesis_id="H-noop",
        trial_index=285,
    )


def make_fill(order_id, side, qty, price, bar_time, fee="0"):
    """A Fill with zero slippage/spread (already embedded in `price` by convention)
    and a controllable fee — enough to drive round-trip reconstruction in tests."""
    from chronos.hephaestus.types import Fill, Side

    return Fill(
        order_id=order_id,
        symbol="BTC/USDT",
        side=Side.BUY if side == "BUY" else Side.SELL,
        qty_filled=Decimal(str(qty)),
        price=Decimal(str(price)),
        fee=Decimal(str(fee)),
        slippage_cost=Decimal("0"),
        spread_cost=Decimal("0"),
        bar_time=bar_time,
    )


def build_result(
    *,
    trades=(),
    warnings=(),
    returns_values=None,
    hypothesis_id="H-noop",
    run_id="000285-H-noop",
    bars_processed=None,
):
    """Flexible BacktestResult builder for the stage tests. `returns_values` sets
    the per-bar return series (and bars_processed to match unless overridden)."""
    start = datetime(2017, 8, 17, tzinfo=timezone.utc)
    if returns_values is None:
        returns_values = [0.0, 0.001, -0.002, 0.0015]
    n = len(returns_values)
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    returns = pd.Series(returns_values, index=idx)
    equity = pd.Series(
        [10000.0 * (1.0 + r) for r in returns_values], index=idx
    )
    end = idx[-1].to_pydatetime() if n else start
    return BacktestResult(
        run_id=run_id,
        core_version="fixture-core-sha",
        config_hash="fixture-config-hash",
        data_snapshot_hash="fixture-data-hash",
        seed=0,
        bars_processed=bars_processed if bars_processed is not None else n,
        date_range=(start, end),
        symbols=("BTC/USDT",),
        timeframe="H1",
        trades=tuple(trades),
        order_events=(),
        equity_curve=equity,
        returns=returns,
        cost_summary=CostSummary(
            fees=Decimal("0"), slippage=Decimal("0"), spread=Decimal("0")
        ),
        warnings=tuple(warnings),
        hypothesis_id=hypothesis_id,
        trial_index=285,
    )


def build_round_trip_fills(factors, *, qty="1", base_price="100", start=None):
    """Fills that realize exactly the given per-trip return `factors` (fee-free):
    each factor is a buy at `base_price` and a sell at base_price*factor. Returns a
    flat tuple of alternating BUY/SELL fills, one clean round trip per factor."""
    if start is None:
        start = datetime(2017, 8, 17, tzinfo=timezone.utc)
    fills = []
    oid = 1
    for i, f in enumerate(factors):
        buy_t = start + timedelta(hours=2 * i)
        sell_t = start + timedelta(hours=2 * i + 1)
        fills.append(make_fill(oid, "BUY", qty, base_price, buy_t))
        oid += 1
        fills.append(make_fill(oid, "SELL", qty,
                               str(float(base_price) * float(f)), sell_t))
        oid += 1
    return tuple(fills)


def _v001_thresholds() -> dict:
    """The real provisional thresholds from configs/gauntlet/v001.json, so tests
    exercise the stages against the same numbers the frozen judge carries."""
    import json
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    data = json.loads((repo_root / "configs" / "gauntlet" / "v001.json").read_text())
    return dict(data["thresholds"])


def build_config(
    pipeline_order: tuple[str, ...],
    *,
    full_evaluation_mode: bool = False,
    version: int = 1,
) -> GauntletConfig:
    """An in-test GauntletConfig with a custom pipeline_order but the REAL v001
    thresholds, so the free stages find their config keys and gate on the actual
    provisional defaults. Deliberately not v001's 11-stage pipeline_order — the
    caller picks which implemented stages to run."""
    return GauntletConfig(
        version=version,
        thresholds=_v001_thresholds(),
        pipeline_order=tuple(pipeline_order),
        full_evaluation_mode=full_evaluation_mode,
        cost_defaults_version="noop",
        calibration_report="",
    )
