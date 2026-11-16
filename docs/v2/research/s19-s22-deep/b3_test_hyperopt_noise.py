"""B3: hyperopt on a pure random walk (no edge): best in-sample vs out-of-sample.
Copied to freqtrade/tests/optimize/test_s19deep_hyperopt.py; uses freqtrade fixtures."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from unittest.mock import PropertyMock

from freqtrade.data.history import get_datahandler
from freqtrade.enums import CandleType, RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.optimize.hyperopt import Hyperopt
from tests.conftest import EXMS, patch_exchange

STRATS = str(Path(__file__).parent.parent / "strategy/strats/s19deep")
SEED = 20261105


def make_walk(datadir: Path):
    rng = np.random.default_rng(SEED)
    n = 4 * 365 * 24  # 4 years of hourly candles
    dates = pd.date_range("2019-01-01", periods=n, freq="1h", tz="UTC")
    r = rng.normal(0, 0.006, n)  # ~0.6% hourly vol, zero drift
    close = 10000 * np.exp(np.cumsum(r))
    openp = np.concatenate([[10000], close[:-1]])
    hi = np.maximum(openp, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
    lo = np.minimum(openp, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
    df = pd.DataFrame({"date": dates, "open": openp, "high": hi, "low": lo, "close": close, "volume": 100.0})
    get_datahandler(datadir, "feather").ohlcv_store("ETH/BTC", "1h", df, CandleType.SPOT)
    return df


def sharpe(trades: pd.DataFrame, days: float):
    if len(trades) == 0:
        return 0.0, 0.0, 0
    daily = trades.set_index(pd.to_datetime(trades["close_date"]))["profit_ratio"].resample("1D").sum()
    idx = pd.date_range(daily.index.min().normalize(), periods=int(days), freq="1D", tz="UTC")
    daily = daily.reindex(idx, fill_value=0.0)
    s = daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else 0.0
    return float(s), float(trades["profit_ratio"].sum()), int(len(trades))


def test_hyperopt_on_noise(mocker, hyperopt_conf, tmp_path):
    patch_exchange(mocker)
    mocker.patch(f"{EXMS}.get_fee", return_value=0.001)
    mocker.patch("freqtrade.plugins.pairlistmanager.PairListManager.whitelist", PropertyMock(return_value=["ETH/BTC"]))
    datadir = tmp_path / "data"
    datadir.mkdir()
    make_walk(datadir)
    (tmp_path / "hyperopt_results").mkdir(parents=True)
    hyperopt_conf.update({
        "strategy": "s19deep_hyper", "strategy_path": STRATS, "user_data_dir": tmp_path,
        "datadir": datadir, "timeframe": "1h", "pairs": ["ETH/BTC"],
        "exchange": {**hyperopt_conf["exchange"], "pair_whitelist": ["ETH/BTC"]},
        "timerange": "20190110-20210101", "epochs": 200, "spaces": ["buy"],
        "hyperopt_loss": "SharpeHyperOptLoss", "hyperopt_random_state": SEED,
        "hyperopt_min_trades": 20, "max_open_trades": 1, "stake_amount": "unlimited",
        "dry_run_wallet": 1000, "disableparamexport": True,
    })
    ho = Hyperopt(hyperopt_conf)
    ho.start()
    best = ho.current_best_epoch
    params = best["params_dict"]
    ins = best["results_metrics"]
    # out of sample: same strategy, best params, second half
    bt_conf = dict(hyperopt_conf)
    bt_conf.update({"timerange": "20210101-20221231", "runmode": RunMode.BACKTEST})
    mocker.patch("freqtrade.strategy.hyper.HyperStrategyMixin.load_params_from_file",
                 return_value={"params": {"buy": params}})
    bt = Backtesting(bt_conf)
    bt._set_strategy(bt.strategylist[0])
    data, timerange = bt.load_bt_data()
    min_d, max_d = None, None
    preprocessed = bt.strategy.advise_all_indicators(data)
    from freqtrade.data.history import get_timerange
    min_d, max_d = get_timerange(preprocessed)
    oos = bt.backtest(processed=preprocessed, start_date=min_d, end_date=max_d)["results"]
    # in-sample with same helper for a like-for-like Sharpe
    bt_conf2 = dict(bt_conf); bt_conf2["timerange"] = "20190110-20210101"
    bt2 = Backtesting(bt_conf2)
    bt2._set_strategy(bt2.strategylist[0])
    d2, _ = bt2.load_bt_data(); p2 = bt2.strategy.advise_all_indicators(d2)
    mn2, mx2 = get_timerange(p2)
    ins_tr = bt2.backtest(processed=p2, start_date=mn2, end_date=mx2)["results"]
    s_in, p_in, n_in = sharpe(ins_tr, 722)
    s_out, p_out, n_out = sharpe(oos, 729)
    out = {
        "epochs": ho.total_epochs, "best_params": params,
        "in_sample": {"sharpe_daily_annualised": s_in, "sum_profit_ratio": p_in, "trades": n_in,
                      "freqtrade_reported_sharpe": ins.get("sharpe"), "freqtrade_reported_profit_total": ins.get("profit_total")},
        "out_of_sample": {"sharpe_daily_annualised": s_out, "sum_profit_ratio": p_out, "trades": n_out},
        "result_keys_mentioning_trials_or_deflation": [k for k in ins.keys() if any(w in k.lower() for w in ("deflat", "trial", "epoch", "dsr", "pbo"))],
    }
    print("RESULT b3", json.dumps(out, default=str))
