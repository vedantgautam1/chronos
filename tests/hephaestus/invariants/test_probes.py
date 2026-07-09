"""Phase 7 — THE INVARIANT PROBES (spec §9). CI-required.

These are the engine's definition of "cannot lie." Each probe attacks one
way a backtester deceives its owner, and fails loudly if the attack works.
Probes exercise the REAL stack (engine + broker + cost model + portfolio);
where they enter below run_experiment they pass the private token
explicitly — that is what the token is for.
"""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest

from chronos.hephaestus.broker import Broker, BrokerConfig
from chronos.hephaestus.costs import ZERO_COSTS, CostConfig, FixedBpsCostModel
from chronos.hephaestus.engine import EngineConfig, _RUN_TOKEN, _execute
from chronos.hephaestus.portfolio import Portfolio
from chronos.hephaestus.types import Order, OrderType, Side
from chronos.mnemosyne.stub import RecordStore
from chronos.oceanus.model import BAR_COLUMNS, Timeframe
from chronos.run import (
    Hypothesis,
    RunConfig,
    determinism_view,
    run_experiment,
    serialize_result,
)
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class ToyMomentum:
    """Data-REACTIVE test strategy: buys after an up bar, sells all after
    a down bar. Not a real strategy — its only job is to make engine
    output depend on the data, so leaks and cost changes become visible."""

    def on_bar(self, view, ctx):
        bars = view.bars("BTC/USDT", 2)
        if len(bars) < 2:
            return []
        held = ctx.portfolio["positions"].get("BTC/USDT", {}).get("qty", Decimal("0"))
        if bars["close"].iloc[-1] > bars["close"].iloc[-2]:
            return [Order(id=0, symbol="BTC/USDT", side=Side.BUY, type=OrderType.MARKET,
                          qty=Decimal("0.2"), created_at=view.now)]
        if bars["close"].iloc[-1] < bars["close"].iloc[-2] and held > 0:
            return [Order(id=0, symbol="BTC/USDT", side=Side.SELL, type=OrderType.MARKET,
                          qty=held, created_at=view.now)]
        return []


def wiggly_frame(n: int) -> pd.DataFrame:
    """Deterministic up-and-down prices so ToyMomentum actually trades."""
    rows = []
    for i in range(n):
        price = 100.0 + 10.0 * math.sin(i / 3.0) + 0.05 * i
        rows.append({"open_time": pd.Timestamp(START + timedelta(hours=i)),
                     "open": round(price, 2), "high": round(price + 2, 2),
                     "low": round(price - 2, 2), "close": round(price + 1, 2),
                     "volume": 1000.0, "is_final": True})
    return pd.DataFrame(rows, columns=BAR_COLUMNS)


def run_engine(bars, seed=7, cost=None, unsafe=False):
    portfolio = Portfolio(Decimal("10000"))
    broker = Broker(FixedBpsCostModel(cost or CostConfig()), portfolio, BrokerConfig())
    config = EngineConfig(initial_cash=Decimal("10000"), seed=seed,
                          unsafe_same_bar_fill=unsafe)
    out = _execute({"BTC/USDT": bars}, Timeframe.H1, ToyMomentum(),
                   broker, portfolio, config, _token=_RUN_TOKEN)
    return out, portfolio


# ---------------------------------------------------------------- probe 1
def _poison(frame: pd.DataFrame, cut: int, direction: str) -> pd.DataFrame:
    """Replace everything from `cut` on with absurd garbage, either a
    massive pump or a total collapse. Valid-looking rows, insane values."""
    poisoned = frame.copy(deep=True)
    price = 1000000.0 if direction == "up" else 0.0001
    poisoned.loc[cut:, ["open", "high", "low", "close"]] = [
        price, price * 1.01, price * 0.99, price]
    poisoned.loc[cut:, "volume"] = 0.001
    return poisoned


class _DecisionRecorder:
    """Wraps a strategy and records its raw DECISIONS (time, side, qty)
    before execution touches them. The probe compares these directly —
    intent is the leak-sensitive quantity; execution outcomes at the cut
    bar legitimately depend on post-cut data (prices, caps, rejections).

    Meta-test history (2026-07-08), kept as a warning to future editors:
    v1 of this probe compared only strictly-before-cut fills/equity and
    MISSED a deliberately planted one-bar leak (a leaked decision at bar
    cut−1 first manifests AT the cut, outside v1's window). Recording
    decisions directly is the correct surface: intent is what leaks;
    execution outcomes at the cut legitimately depend on post-cut data.
    Bonus find: running this probe's collapse scenario exposed a REAL
    ledger defect — reconciliation drifted 5E-24 because Decimal's
    default 28-digit context couldn't span cash (~1e4) and dust
    (~1e-9×1e-4) in one sum; fixed via LEDGER_PRECISION=50 in types.py.
    """

    def __init__(self, inner):
        self.inner = inner
        self.decisions: list[tuple] = []

    def on_bar(self, view, ctx):
        orders = self.inner.on_bar(view, ctx)
        for o in orders:
            self.decisions.append((view.now, o.side, str(o.qty)))
        return orders


def test_probe_1_poisoned_future_changes_no_decision_made_before_the_cut():
    """I1 — no future leakage. Three datasets identical up to bar 80; two
    have their tails garbage-poisoned (a pump and a collapse — both
    directions, so a leak can't hide behind a coincidentally-identical
    decision). Every decision whose time is <= the cut boundary was made
    from pre-cut data only, so it must be identical across all three."""
    n, cut = 120, 80
    clean = wiggly_frame(n)
    cut_time = START + timedelta(hours=cut)  # decision at bar cut-1 has now == cut_time

    def decisions_and_prefix(frame):
        recorder = _DecisionRecorder(ToyMomentum())
        portfolio = Portfolio(Decimal("10000"))
        broker = Broker(FixedBpsCostModel(), portfolio, BrokerConfig())
        out = _execute({"BTC/USDT": frame}, Timeframe.H1, recorder, broker,
                       portfolio, EngineConfig(initial_cash=Decimal("10000"), seed=7),
                       _token=_RUN_TOKEN)
        return (
            [d for d in recorder.decisions if d[0] <= cut_time],  # pre-cut intents
            [f for f in out.fills if f.bar_time < cut_time],  # their executions
            list(out.equity_curve[out.equity_curve.index < cut_time]),
        )

    baseline = decisions_and_prefix(clean)
    assert baseline[0], "probe needs pre-cut decisions to mean anything"
    for direction in ("up", "down"):
        poisoned_state = decisions_and_prefix(_poison(clean, cut, direction))
        assert poisoned_state == baseline, (
            f"a decision made before the cut changed under {direction}-poisoned "
            f"future data: the strategy saw the future (I1 violated)"
        )


# ---------------------------------------------------------------- probe 2
def test_probe_2_no_cost_path_costs_always_bite():
    """I2 — zero-parameter vs realistic costs MUST differ (same data, same
    strategy). If they match, some path skipped the cost model."""
    bars = wiggly_frame(100)
    out_free, p_free = run_engine(bars, cost=ZERO_COSTS)
    out_real, p_real = run_engine(bars, cost=CostConfig())
    assert len(out_real.fills) > 0, "probe needs trades to mean anything"
    assert p_real.fees_paid > 0
    assert p_free.fees_paid == 0
    assert out_free.equity_curve.iloc[-1] != out_real.equity_curve.iloc[-1]


# ---------------------------------------------------------------- probe 3
def test_probe_3_determinism_byte_identical_results(tmp_path):
    """I5 — identical (code, config, data snapshot, seed) -> byte-identical
    serialized results, modulo the trial bookkeeping that I6 requires to
    advance. Run through the FULL public door, twice."""
    def one_run():
        store = RecordStore(tmp_path / "records")
        fake = FakeExchange(int(START.timestamp() * 1000), n_bars=100)
        cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                        start=START, end=START + timedelta(hours=100), seed=13)
        record = run_experiment(ToyMomentum(), cfg,
                                Hypothesis(id="H-det", statement="s", prediction="p"),
                                store=store, data_root=tmp_path / "data", exchange=fake)
        return serialize_result(record.result)

    first, second = one_run(), one_run()
    assert determinism_view(first) == determinism_view(second)  # byte-equal
    assert first != second  # ONLY because trial bookkeeping advanced (I6)


# ---------------------------------------------------------------- probe 4
def test_probe_4_logging_no_unlogged_execution(tmp_path):
    """I3 — the private door raises; a mid-run crash still persists an
    ERRORED record before the exception reaches the caller."""
    with pytest.raises(PermissionError, match="run_experiment"):
        _execute({}, Timeframe.H1, ToyMomentum(), None, None, None)

    class Crasher:
        def on_bar(self, view, ctx):
            raise RuntimeError("probe crash")

    store = RecordStore(tmp_path / "records")
    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=50)
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=START, end=START + timedelta(hours=50))
    with pytest.raises(RuntimeError, match="probe crash"):
        run_experiment(Crasher(), cfg,
                       Hypothesis(id="H-log", statement="s", prediction="p"),
                       store=store, data_root=tmp_path / "data", exchange=fake)
    runs = [r for r in store.read_all() if r["type"] == "run"]
    assert runs and runs[0]["status"] == "ERRORED"


# ---------------------------------------------------------------- probe 5
def test_probe_5_every_trial_counted(tmp_path):
    """I6 — N attempts advance the counter by exactly N, crashes included.
    An understated trial count is how selection bias re-enters."""
    store = RecordStore(tmp_path / "records")
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=START, end=START + timedelta(hours=50))

    def attempt(strategy):
        fake = FakeExchange(int(START.timestamp() * 1000), n_bars=50)
        return run_experiment(strategy, cfg,
                              Hypothesis(id="H-count", statement="s", prediction="p"),
                              store=store, data_root=tmp_path / "data", exchange=fake)

    attempt(ToyMomentum())
    attempt(ToyMomentum())

    class Crasher:
        def on_bar(self, view, ctx):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        attempt(Crasher())
    assert store.trial_count == 3


# ---------------------------------------------------------------- probe 6
def test_probe_6_reconciliation_identity_holds_under_heavy_trading():
    """§7 identity — the Portfolio verifies it at EVERY mark (always-on),
    so completing a 300-bar run with dozens of round trips IS the proof;
    any drift would have raised AccountingDriftError mid-run."""
    bars = wiggly_frame(300)
    out, portfolio = run_engine(bars)
    assert len(out.fills) > 20  # heavy traffic: fees, slips, partial state
    assert out.bars_processed == 300  # identity checked 300 times
    final_close = Decimal(str(bars["close"].iloc[-1]))
    lhs = Decimal(str(out.equity_curve.iloc[-1]))
    rhs = (portfolio.initial_cash + portfolio.realized_pnl
           + portfolio.unrealized_pnl({"BTC/USDT": final_close})
           - portfolio.fees_paid)
    assert lhs == Decimal(str(float(rhs)))  # explicit final restatement


# ---------------------------------------------------------------- probe 7
def test_probe_7_unsafe_flag_stamps_warning_default_never_does():
    """§4 — the same-bar research mode is loudly marked; the default path
    NEVER carries the mark (a clean result can be trusted to be clean)."""
    bars = wiggly_frame(60)
    out_default, _ = run_engine(bars)
    out_unsafe, _ = run_engine(bars, unsafe=True)

    assert not any("unsafe" in w.lower() for w in out_default.warnings)
    assert any("NON-PROMOTABLE" in w for w in out_unsafe.warnings)
    # And the flattery is real and measurable — that's why the mode exists:
    assert not out_unsafe.equity_curve.equals(out_default.equity_curve)


# ------------------------------------------------------- engine-door guard
def test_engine_door_guard_nothing_else_touches_execute():
    """One-door, engine edition: no module under src/ besides engine.py
    itself and run.py may reference _execute or _RUN_TOKEN."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "src" / "chronos"
    allowed = {src / "hephaestus" / "engine.py", src / "run.py"}
    offenders = []
    for path in src.rglob("*.py"):
        if path in allowed:
            continue
        text = path.read_text()
        if "_execute" in text or "_RUN_TOKEN" in text:
            offenders.append(str(path))
    assert not offenders, f"engine door bypassed by: {offenders}"
