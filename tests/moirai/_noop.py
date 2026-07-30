"""_noop.py — throwaway no-op Moirai and deterministic fixtures for Phase 3.

These exist ONLY to exercise the empty pipeline before any real Moira exists.
`AlwaysPass` and `AlwaysFail` are the two throwaway no-ops the brief calls for and
are DELETED IN PHASE 4a. The rest (`CrashMoira`, the terminal-signal moirai, and
the fixture builders) are test infrastructure the probes lean on.

This module lives under `tests/` (never in the production pipeline) and is
importable by name (`tests.moirai._noop`) so probe G1's fresh-process subprocess
can rebuild the identical fixture and config it built in-process.
"""

from datetime import datetime, timezone

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
    """Trivial pass. DELETED IN PHASE 4a."""

    def __init__(self, moira_id: str = "noop-always-pass"):
        self.moira_id = moira_id

    def evaluate(self, result, ctx) -> TestOutcome:
        return TestOutcome(
            moira_id=self.moira_id, passed=True, score=1.0,
            evidence={"noop": "always-pass"},
        )


class AlwaysFail:
    """Trivial fail. DELETED IN PHASE 4a."""

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


def build_config(
    pipeline_order: tuple[str, ...],
    *,
    full_evaluation_mode: bool = False,
    version: int = 1,
) -> GauntletConfig:
    """A minimal in-test GauntletConfig with a custom pipeline_order of no-op
    moira_ids. Deliberately NOT the production v001 config — Phase 3 has no real
    Moirai to run under v001's 11-stage order."""
    return GauntletConfig(
        version=version,
        thresholds={"noop.threshold": 0},
        pipeline_order=tuple(pipeline_order),
        full_evaluation_mode=full_evaluation_mode,
        cost_defaults_version="noop",
        calibration_report="",
    )
