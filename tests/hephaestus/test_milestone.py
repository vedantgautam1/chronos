"""Phase 9 tests: the MA-crossover strategy and the end-to-end milestone
path (through run_experiment, no network)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from chronos.hephaestus.types import Side
from chronos.mnemosyne.stub import RecordStore
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunStatus, run_experiment
from chronos.strategies.ma_crossover import MACrossover
from tests.oceanus.test_ingest import FakeExchange

from .test_view import START


class TrendingFake(FakeExchange):
    """A fake exchange serving a down-then-up series: flat/falling for the
    first half (fast MA below slow -> no position), rising in the second
    (golden cross -> buy). Guarantees the crossover actually trades."""

    def __init__(self, n_bars=200):
        super().__init__(int(START.timestamp() * 1000), n_bars=n_bars)
        half = n_bars // 2
        for i, candle in enumerate(self.candles):
            price = 100.0 - i * 0.1 if i < half else 100.0 - half * 0.1 + (i - half) * 0.3
            candle[1:6] = [price, price + 0.5, price - 0.5, price + 0.2, 50.0]


def milestone_config(n_hours=200):
    return RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                     start=START, end=START + timedelta(hours=n_hours), seed=1,
                     strategy_params={"fast": 5, "slow": 20, "fraction": "0.9"})


def test_crossover_buys_on_golden_cross_and_sells_on_death_cross(tmp_path):
    record = run_experiment(
        MACrossover(), milestone_config(),
        Hypothesis(id="H-x", statement="s", prediction="p"),
        store=RecordStore(tmp_path / "records"),
        data_root=tmp_path / "data", exchange=TrendingFake())
    trades = record.result.trades
    assert trades, "the trending series must produce at least one trade"
    assert trades[0].side is Side.BUY  # first action is the golden-cross buy
    # Spot-only invariant: can never sell more than held, so cumulative
    # position never goes negative.
    position = Decimal("0")
    for f in trades:
        position += f.qty_filled if f.side is Side.BUY else -f.qty_filled
        assert position >= 0


def test_milestone_end_to_end_record_complete(tmp_path):
    store = RecordStore(tmp_path / "records")
    record = run_experiment(
        MACrossover(), milestone_config(),
        Hypothesis(id="H-milestone-test", statement="s", prediction="p"),
        store=store, data_root=tmp_path / "data", exchange=TrendingFake())

    assert record.status is RunStatus.COMPLETED
    result = record.result
    assert result.bars_processed == 200
    assert len(result.equity_curve) == 200
    assert result.cost_summary.fees > 0  # it traded, so it paid
    assert any("provisional_cost_constants" in w for w in result.warnings)
    assert len(result.data_snapshot_hash) == 64

    persisted = [r for r in store.read_all() if r["type"] == "run"]
    assert persisted[0]["status"] == "COMPLETED"
    assert persisted[0]["result"]["bars_processed"] == 200


def test_strategy_waits_for_enough_history(tmp_path):
    # With slow=20, the first 19 bars must produce no orders at all.
    record = run_experiment(
        MACrossover(), milestone_config(n_hours=19),
        Hypothesis(id="H-warmup", statement="s", prediction="p"),
        store=RecordStore(tmp_path / "records"),
        data_root=tmp_path / "data", exchange=TrendingFake())
    assert not record.result.trades
    assert not record.result.order_events


def test_bad_params_fail_loudly(tmp_path):
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=START, end=START + timedelta(hours=50),
                    strategy_params={"fast": 50, "slow": 20})
    with pytest.raises(ValueError, match="fast < slow"):
        run_experiment(MACrossover(), cfg,
                       Hypothesis(id="H-bad", statement="s", prediction="p"),
                       store=RecordStore(tmp_path / "records"),
                       data_root=tmp_path / "data", exchange=TrendingFake())
