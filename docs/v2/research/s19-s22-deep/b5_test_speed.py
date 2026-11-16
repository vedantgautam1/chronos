"""B5: freqtrade backtest speed on 2 years of real BTC 5-minute candles (Bitstamp, 2023-2024).
Copied to freqtrade/tests/optimize/test_s19deep_speed.py. A fixed toy strategy (MA 20/100 cross);
the result is not research evidence."""
import json
import os
import resource
import time
from pathlib import Path
from unittest.mock import PropertyMock

import pandas as pd

from freqtrade.data.history import get_datahandler, get_timerange
from freqtrade.enums import CandleType, RunMode
from freqtrade.optimize.backtesting import Backtesting
from tests.conftest import EXMS, patch_exchange

STRATS = str(Path(__file__).parent.parent / "strategy/strats/s19deep")
SRC = os.environ.get("S19_BTC5M", "/home/claude/data/bitstamp/btc_bitstamp_5m_2023_2024.feather")


def test_speed(default_conf, mocker, tmp_path):
    patch_exchange(mocker)
    mocker.patch(f"{EXMS}.get_fee", return_value=0.001)
    mocker.patch("freqtrade.plugins.pairlistmanager.PairListManager.whitelist", PropertyMock(return_value=["ETH/BTC"]))
    mocker.patch("freqtrade.strategy.hyper.HyperStrategyMixin.load_params_from_file",
                 return_value={"params": {"buy": {"fast": 20, "slow": 100}}})
    df = pd.read_feather(SRC)
    dd = tmp_path / "data"; dd.mkdir()
    get_datahandler(dd, "feather").ohlcv_store("ETH/BTC", "5m", df, CandleType.SPOT)
    default_conf.update({"strategy": "s19deep_hyper", "strategy_path": STRATS, "datadir": dd,
                         "timeframe": "5m", "timerange": "20230102-20241231", "max_open_trades": 1,
                         "stake_amount": "unlimited", "dry_run_wallet": 1000, "runmode": RunMode.BACKTEST,
                         "user_data_dir": tmp_path})
    t0 = time.perf_counter()
    bt = Backtesting(default_conf)
    bt._set_strategy(bt.strategylist[0])
    bt.strategy.timeframe = "5m"
    data, _ = bt.load_bt_data()
    t1 = time.perf_counter()
    pre = bt.strategy.advise_all_indicators(data)
    t2 = time.perf_counter()
    mn, mx = get_timerange(pre)
    res = bt.backtest(processed=pre, start_date=mn, end_date=mx)["results"]
    t3 = time.perf_counter()
    out = {"candles": int(len(df)), "load_s": round(t1 - t0, 2), "indicators_s": round(t2 - t1, 2),
           "backtest_s": round(t3 - t2, 2), "trades": int(len(res)),
           "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    print("RESULT b5", json.dumps(out))
