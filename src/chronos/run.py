"""Phase 6 — run_experiment(): the sole public entry to the engine
(invariants I3, I6, I8).

The seam of Chronos: hypothesis in → engine executes → record persisted →
(later) the Moirai judge the result. What this door enforces:

- I8: no hypothesis, no run. The hypothesis is persisted BEFORE execution.
- I6: the trial counter advances BEFORE execution — crashed runs count.
- I3: a record is written on EVERY exit path (try/finally); a crash
  yields a persisted ERRORED record, then the exception propagates.
- I5: every record carries the full reproducibility coordinates —
  core git SHA, config hash, Oceanus data snapshot hash, seed.

Data enters exclusively through chronos.oceanus.access (the one door).
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Mapping

from chronos.oceanus.access import get_bars, snapshot_hash
from chronos.oceanus.model import Timeframe
from chronos.hephaestus.broker import Broker, BrokerConfig
from chronos.hephaestus.costs import CostConfig, FixedBpsCostModel
from chronos.hephaestus.engine import EngineConfig, _RUN_TOKEN, _execute
from chronos.hephaestus.portfolio import Portfolio, returns_from_equity
from chronos.hephaestus.types import BacktestResult, CostSummary
from chronos.hephaestus.view import Strategy
from chronos.mnemosyne.stub import RecordStore

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS_DIR = _REPO_ROOT / "records"


@dataclass(frozen=True)
class Hypothesis:
    """What you believe BEFORE running, on the record (I8).

    Results without a pre-registered hypothesis are how "look what I
    found!" data-mining gets laundered into strategy claims."""

    id: str  # e.g. "H-001-ma-crossover"
    statement: str  # what you believe and why it might be true
    prediction: str  # what result would support it — stated in advance

    def __post_init__(self) -> None:
        for name in ("id", "statement", "prediction"):
            if not getattr(self, name).strip():
                raise ValueError(f"hypothesis {name} must be non-empty")


@dataclass(frozen=True)
class RunConfig:
    """Everything that (with the code SHA, data hash, and seed) fully
    determines a run. Hashed canonically into config_hash."""

    symbol: str
    timeframe: Timeframe
    start: datetime
    end: datetime
    initial_cash: Decimal = Decimal("10000")  # founder decision
    seed: int = 0
    strategy_params: Mapping = field(default_factory=dict)
    participation_rate: Decimal = Decimal("0.05")
    optimistic_touch_fills: bool = False
    unsafe_same_bar_fill: bool = False
    cost: CostConfig = field(default_factory=CostConfig)


class RunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    ERRORED = "ERRORED"


@dataclass(frozen=True)
class RunRecord:
    """What run_experiment returns and what the store persists."""

    run_id: str
    trial_index: int
    status: RunStatus
    hypothesis: Hypothesis
    result: BacktestResult | None  # None iff ERRORED
    error: str | None


def run_experiment(
    strategy: Strategy,
    config: RunConfig,
    hypothesis: Hypothesis,
    store: RecordStore | None = None,
    data_root=None,  # internal: overridden only by tests
    exchange=None,  # internal: overridden only by tests
) -> RunRecord:
    """THE way to run a backtest. There is no other."""
    if not isinstance(hypothesis, Hypothesis):
        raise TypeError(
            "run_experiment requires a pre-registered Hypothesis (I8): "
            "results cannot exist without a stated expectation to judge "
            "them against."
        )
    store = store or RecordStore(DEFAULT_RECORDS_DIR)

    core_version = _core_version()
    config_hash = _config_hash(config)

    # I6: counted before execution. I8: hypothesis persisted before execution.
    trial_index = store.next_trial_index()
    run_id = f"{trial_index:06d}-{hypothesis.id}"
    started_at = datetime.now(timezone.utc)
    store.append({
        "type": "hypothesis", "run_id": run_id, "trial_index": trial_index,
        "hypothesis": asdict(hypothesis), "registered_at": started_at.isoformat(),
    })

    status, error, result, data_hash = RunStatus.ERRORED, None, None, None
    try:
        bars = get_bars(config.symbol, config.timeframe, config.start, config.end,
                        root=data_root, exchange=exchange)
        data_hash = snapshot_hash(bars)

        portfolio = Portfolio(config.initial_cash)
        broker = Broker(
            FixedBpsCostModel(config.cost), portfolio,
            BrokerConfig(participation_rate=config.participation_rate,
                         optimistic_touch_fills=config.optimistic_touch_fills),
        )
        engine_config = EngineConfig(
            initial_cash=config.initial_cash, seed=config.seed,
            strategy_params=config.strategy_params,
            unsafe_same_bar_fill=config.unsafe_same_bar_fill,
        )
        out = _execute({config.symbol: bars}, config.timeframe, strategy,
                       broker, portfolio, engine_config, _token=_RUN_TOKEN)

        result = BacktestResult(
            run_id=run_id, core_version=core_version, config_hash=config_hash,
            data_snapshot_hash=data_hash, seed=config.seed,
            bars_processed=out.bars_processed,
            date_range=(config.start, config.end),
            symbols=(config.symbol,), timeframe=config.timeframe.value,
            trades=out.fills, order_events=out.order_events,
            equity_curve=out.equity_curve,
            returns=returns_from_equity(out.equity_curve),
            cost_summary=CostSummary(fees=portfolio.fees_paid,
                                     slippage=portfolio.slippage_paid,
                                     spread=portfolio.spread_paid),
            warnings=out.warnings,
            hypothesis_id=hypothesis.id, trial_index=trial_index,
        )
        status = RunStatus.COMPLETED
        return RunRecord(run_id, trial_index, status, hypothesis, result, None)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise  # the caller must see the failure — but the record persists
    finally:
        # I3: a record on every exit path, success or crash alike.
        store.append({
            "type": "run", "run_id": run_id, "trial_index": trial_index,
            "status": status.value, "error": error,
            "hypothesis_id": hypothesis.id,
            "core_version": core_version, "config_hash": config_hash,
            "data_snapshot_hash": data_hash, "seed": config.seed,
            "config": _canonical(config),
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": None if result is None else json.loads(serialize_result(result)),
        })


def serialize_result(result: BacktestResult) -> str:
    """Canonical, deterministic serialization of a BacktestResult.

    The determinism probe (I5) byte-compares this string across runs:
    sorted keys, no whitespace, Decimals as strings, datetimes as ISO.
    Deliberately contains NO wall-clock fields."""
    payload = {
        "run_id": result.run_id, "core_version": result.core_version,
        "config_hash": result.config_hash,
        "data_snapshot_hash": result.data_snapshot_hash, "seed": result.seed,
        "bars_processed": result.bars_processed,
        "date_range": [t.isoformat() for t in result.date_range],
        "symbols": list(result.symbols), "timeframe": result.timeframe,
        "trades": [_canonical(f) for f in result.trades],
        "order_events": [_canonical(e) for e in result.order_events],
        "equity_curve": [[t.isoformat(), v] for t, v in result.equity_curve.items()],
        "returns": [[t.isoformat(), v] for t, v in result.returns.items()],
        "cost_summary": _canonical(result.cost_summary),
        "warnings": list(result.warnings),
        "hypothesis_id": result.hypothesis_id, "trial_index": result.trial_index,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _canonical(obj):
    """Recursively convert to JSON-safe, deterministic primitives."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return _canonical(asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    return obj


def _config_hash(config: RunConfig) -> str:
    blob = json.dumps(_canonical(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _core_version() -> str:
    """Git SHA of the engine code, with an honest '-dirty' suffix if the
    working tree has uncommitted changes."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=_REPO_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"  # recorded honestly rather than failing the run
