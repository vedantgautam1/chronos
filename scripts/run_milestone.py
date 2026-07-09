"""The Stage 0 milestone: one command, the whole pipeline, on the record.

Run:  uv run python scripts/run_milestone.py

Oceanus data -> run_experiment -> engine + broker + full costs ->
BacktestResult -> persisted record -> equity chart. The expected outcome
is an unremarkable or LOSING result — that is success. This proves the
instrument tells the truth; it does not try to make money.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from chronos.oceanus.model import Timeframe
from chronos.run import DEFAULT_RECORDS_DIR, Hypothesis, RunConfig, run_experiment
from chronos.strategies.ma_crossover import MACrossover

HYPOTHESIS = Hypothesis(
    id="H-003-ma-crossover-milestone",
    statement=(
        "A 20/50 MA crossover on hourly BTC/USDT captures enough trend to "
        "survive real trading costs over H1 2026. (Registered belief: it "
        "probably does NOT — this run exists to prove the instrument.)"
    ),
    prediction=(
        "Unremarkable or negative net return after fees, spread, and "
        "slippage; every trade itemized; the record reproducible from its "
        "coordinates. A losing result confirms the instrument, not the idea."
    ),
)

CONFIG = RunConfig(
    symbol="BTC/USDT",
    timeframe=Timeframe.H1,
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end=datetime(2026, 7, 1, tzinfo=timezone.utc),  # six months
    seed=42,
    strategy_params={"fast": 20, "slow": 50, "fraction": "0.95"},
)


def main() -> None:
    print("=" * 72)
    print("STAGE 0 MILESTONE — MA(20/50) crossover, BTC/USDT 1h, H1 2026")
    print("=" * 72)
    print(f"\nHypothesis {HYPOTHESIS.id} registered BEFORE execution:")
    print(f"  {HYPOTHESIS.prediction}\n")

    record = run_experiment(MACrossover(), CONFIG, HYPOTHESIS)
    result = record.result

    initial = float(CONFIG.initial_cash)
    final = float(result.equity_curve.iloc[-1])
    buys = sum(1 for f in result.trades if f.side.value == "BUY")
    sells = len(result.trades) - buys

    print(f"\nRUN {record.run_id}: {record.status.value}  (trial #{record.trial_index})")
    print(f"  bars processed : {result.bars_processed}")
    print(f"  trades         : {len(result.trades)} fills ({buys} buys, {sells} sells)")
    print(f"  other events   : {len(result.order_events)} (expiries/cancels/rejections)")
    print(f"  costs, itemized: fees {result.cost_summary.fees:.2f}  "
          f"slippage {result.cost_summary.slippage:.2f}  "
          f"spread {result.cost_summary.spread:.2f}  "
          f"(total {result.cost_summary.total:.2f} USDT)")
    print(f"  equity         : {initial:,.2f} -> {final:,.2f}  "
          f"({(final / initial - 1):+.2%} net of all costs)")
    print(f"  warnings       : {len(result.warnings)}")
    for w in result.warnings:
        print(f"    ! {w[:100]}")
    print("\n  reproducibility coordinates:")
    print(f"    core    {result.core_version}")
    print(f"    config  {result.config_hash}")
    print(f"    data    {result.data_snapshot_hash}")
    print(f"    seed    {result.seed}")
    print(f"\n  record persisted to {DEFAULT_RECORDS_DIR / 'runs.jsonl'}")

    out = REPO / "milestone_equity.png"
    fig, ax = plt.subplots(figsize=(12, 5))
    result.equity_curve.plot(ax=ax, linewidth=1.2)
    ax.axhline(initial, linestyle="--", linewidth=0.8, alpha=0.6, label="initial capital")
    ax.set_title(f"Milestone: MA(20/50) BTC/USDT 1h — net {(final / initial - 1):+.2%} "
                 f"after {result.cost_summary.total:.0f} USDT costs")
    ax.set_ylabel("equity (USDT)")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f"  equity curve rendered to {out}")
    print("\nAn unremarkable result here is the instrument working. Judging")
    print("whether any strategy is actually good is the Moirai's job — next stage.")


if __name__ == "__main__":
    main()
