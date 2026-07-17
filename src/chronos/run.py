"""Phase 6 — run_experiment(): the sole public entry to the engine
(invariants I3, I6, I8).

The seam of Chronos: hypothesis in → engine executes → record persisted →
(later) the Moirai judge the result. What this door enforces:

- I8: no hypothesis, no run. The hypothesis is persisted BEFORE execution.
- I6: the trial counter advances BEFORE execution — crashed runs count.
- I3: a record is written on EVERY exit path (try/finally); a crash
  yields a persisted ERRORED record, then the exception propagates.
- I5: every record carries the full reproducibility coordinates —
  core git SHA, config hash, Oceanus data snapshot hash, seed, and
  candidate_n (the search-breadth compute_search_n() reports for this
  hypothesis_id) — five coordinates, not four.

Data enters exclusively through chronos.oceanus.access (the one door).
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field, is_dataclass, replace
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
    # Set only via register_search(): the grid shape of a parameter
    # search (e.g. "fast in range(5,55,5) x slow in range(60,200,5)").
    # None for a standalone, non-search hypothesis. Persisted verbatim
    # in every 'hypothesis' record so a reader auditing a search sees
    # the grid on the record itself, not in the script that produced it.
    param_grid_description: str | None = None

    def __post_init__(self) -> None:
        for name in ("id", "statement", "prediction"):
            if not getattr(self, name).strip():
                raise ValueError(f"hypothesis {name} must be non-empty")
        if self.param_grid_description is not None and not self.param_grid_description.strip():
            raise ValueError("param_grid_description must be non-empty or None")


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


class RunKind(str, Enum):
    """What kind of execution this is — NOT an audit count (the
    execution counter in trial_counter.txt is unchanged and unrelated).
    This is the semantic label compute_search_n() reads to determine
    DSR's N: how many executions genuinely belong to the SAME search
    over the SAME hypothesis family, versus one standalone pre-
    registered run.

    SEARCH        — one point in a parameter sweep over one hypothesis
                    family (e.g. the 280-point MA sweep). Counted by
                    compute_search_n() per hypothesis_id.
    VERIFICATION  — a standalone, pre-registered run: one hypothesis,
                    no preceding search over it (e.g. trial #4).

    See SESSION_FINDINGS.md for the concrete N=1 vs N=280 case that
    motivated this distinction, and HANDOFF.md for the open I6
    trial-ontology question this does NOT resolve (the execution
    counter still conflates every run; this is a separate, narrower
    label read only by compute_search_n()).
    """

    SEARCH = "SEARCH"
    VERIFICATION = "VERIFICATION"


@dataclass(frozen=True)
class RunRecord:
    """What run_experiment returns and what the store persists."""

    run_id: str
    trial_index: int
    status: RunStatus
    kind: RunKind
    hypothesis: Hypothesis
    result: BacktestResult | None  # None iff ERRORED
    error: str | None


def run_experiment(
    strategy: Strategy,
    config: RunConfig,
    hypothesis: Hypothesis,
    kind: RunKind,
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
        return RunRecord(run_id, trial_index, status, kind, hypothesis, result, None)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise  # the caller must see the failure — but the record persists
    finally:
        # I3: a record on every exit path, success or crash alike.
        store.append({
            "type": "run", "run_id": run_id, "trial_index": trial_index,
            "status": status.value, "kind": kind.value, "error": error,
            "hypothesis_id": hypothesis.id,
            "core_version": core_version, "config_hash": config_hash,
            "data_snapshot_hash": data_hash, "seed": config.seed,
            "config": _canonical(config),
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": None if result is None else json.loads(serialize_result(result)),
        })


def register_search(base_hypothesis: Hypothesis, param_grid_description: str) -> Hypothesis:
    """Explicit marker for a parameter search: call this ONCE before
    sweeping and reuse the returned Hypothesis across every
    run_experiment() call in that search — so the search is genuinely
    one hypothesis family on the record, not N separate beliefs.

    Returns a NEW Hypothesis with `param_grid_description` attached
    (Hypothesis is frozen, so this cannot mutate base_hypothesis in
    place — dataclasses.replace() builds the new instance). The
    description is then persisted verbatim in every 'hypothesis' record
    this Hypothesis is used with, alongside statement and prediction —
    a future reader auditing the sweep sees the grid shape on the
    record itself, not in the script that produced it.
    """
    return replace(base_hypothesis, param_grid_description=param_grid_description)


def compute_search_n(hypothesis_id: str, store: RecordStore) -> int:
    """The honest DSR search-breadth N for a candidate drawn from a
    search: the count of 'run'-type records with kind == SEARCH sharing
    this hypothesis_id. NOT a live counter — derived by re-reading the
    store, so it always reflects exactly what was actually searched.

    LEGACY NOTE: records written before this `kind` field existed
    (trials 1-284, predating this change, 2026-07-17) have no 'kind' key
    at all — record.get('kind') is None for them, which never matches
    RunKind.SEARCH.value, so they are silently and correctly excluded.
    Do NOT backfill or guess a kind for those records; they predate the
    SEARCH/VERIFICATION distinction and must be treated as legacy, not
    retrofitted into this accounting. See SESSION_FINDINGS.md and
    HANDOFF.md.
    """
    n = 0
    for record in store.read_all():
        if record.get("type") != "run":
            continue
        if record.get("kind") != RunKind.SEARCH.value:
            continue
        if record.get("hypothesis_id") != hypothesis_id:
            continue
        n += 1
    return n


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


def determinism_view(serialized_result: str, store: RecordStore) -> str:
    """The byte-compare form for the determinism probe (I5).

    I5's coordinates are FIVE, not four: core git SHA, config hash, data
    snapshot hash, seed — and candidate_n, the search-breadth
    compute_search_n() would report for this result's hypothesis_id
    right now. Two runs are the same determinism claim only if they
    share all five. A different candidate_n is not a determinism
    failure — it is an honest difference in which search a candidate
    was drawn from (see SESSION_FINDINGS.md; HANDOFF.md 2026-07-17).

    run_id and trial_index advance on every run BY DESIGN (I6: every
    trial counted) — they are bookkeeping, not result content. Everything
    else, including candidate_n, must be byte-identical across runs
    with identical coordinates."""
    payload = json.loads(serialized_result)
    payload.pop("run_id")
    payload.pop("trial_index")
    payload["candidate_n"] = compute_search_n(payload["hypothesis_id"], store)
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
