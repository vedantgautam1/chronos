"""B2: freqtrade backtest fill rules against known answers (see PREREGISTERED.md, B2).

This file is copied at run time into freqtrade's own tests folder
(tests/optimize/test_s19deep_fills.py) so it can use freqtrade's fixtures
(patched exchange, default config) and its synthetic-candle helper, then run with
    python -m pytest -q tests/optimize/test_s19deep_fills.py -s
It prints one RESULT line per case; the asserts are kept loose on purpose so every
case reports its numbers instead of stopping at the first surprise.
Candle rows: [offset, open, high, low, close, volume, enter_long, exit_long].
"""
import json
import logging
from datetime import timedelta

import pandas as pd

from freqtrade.data.history import get_timerange
from freqtrade.enums import TradingMode
from freqtrade.exchange import Exchange
from freqtrade.optimize.backtesting import Backtesting
from tests.conftest import EXMS, patch_exchange
from tests.optimize import _build_backtest_dataframe

RESULTS = {}


def run_case(default_conf, mocker, data, stoploss, roi, fee=0.0, use_exit_signal=False):
    default_conf["stoploss"] = stoploss
    default_conf["minimal_roi"] = roi
    default_conf["timeframe"] = "1h"
    default_conf["use_exit_signal"] = use_exit_signal
    default_conf["max_open_trades"] = 10
    default_conf["trailing_stop"] = False
    patch_exchange(mocker)
    mocker.patch(f"{EXMS}.get_fee", return_value=fee)
    mocker.patch(f"{EXMS}.get_min_pair_stake_amount", return_value=0.00001)
    mocker.patch(f"{EXMS}.get_max_pair_stake_amount", return_value=float("inf"))
    mocker.patch(f"{EXMS}.get_max_leverage", return_value=100)
    mocker.patch(f"{EXMS}.calculate_funding_fees", return_value=0)
    frame = _build_backtest_dataframe(data)
    bt = Backtesting(default_conf)
    bt.trading_mode = TradingMode.SPOT
    bt._set_strategy(bt.strategylist[0])
    bt.required_startup = 0
    bt.strategy.advise_entry = lambda a, m: frame
    bt.strategy.advise_exit = lambda a, m: frame
    pair = "UNITTEST/BTC"
    mn, mx = get_timerange({pair: frame})
    res = bt.backtest(processed={pair: frame.copy()}, start_date=mn, end_date=mx)["results"]
    return res


def record(name, res, expected):
    row = res.iloc[0] if len(res) else None
    out = {
        "trades": int(len(res)),
        "open_rate": float(row["open_rate"]) if row is not None else None,
        "close_rate": float(row["close_rate"]) if row is not None else None,
        "profit_ratio": float(row["profit_ratio"]) if row is not None else None,
        "exit_reason": str(row["exit_reason"]) if row is not None else None,
        "open_date": str(row["open_date"]) if row is not None else None,
        "expected": expected,
    }
    RESULTS[name] = out
    print("RESULT", name, json.dumps(out))


def test_a_entry_next_open(default_conf, mocker):
    # signal on candle 0 (close 101); candle 1 opens at 102 -> entry should be 102 at candle 1.
    data = [
        [0, 100, 102, 99, 101, 1, 1, 0],
        [1, 102, 103, 101, 102, 1, 0, 0],
        [2, 102, 104, 101, 103, 1, 0, 1],
        [3, 110, 111, 109, 110, 1, 0, 0],
        [4, 110, 111, 109, 110, 1, 0, 0],
    ]
    res = run_case(default_conf, mocker, data, stoploss=-0.5, roi={"0": 10}, use_exit_signal=True)
    record("a_entry_next_open", res, {"open_rate": 102, "close_rate": 110})


def test_b_fees(default_conf, mocker):
    data = [
        [0, 100, 102, 99, 101, 1, 1, 0],
        [1, 100, 103, 99, 102, 1, 0, 1],
        [2, 110, 111, 109, 110, 1, 0, 0],
        [3, 110, 111, 109, 110, 1, 0, 0],
    ]
    fee = 0.001
    res = run_case(default_conf, mocker, data, stoploss=-0.5, roi={"0": 10}, fee=fee, use_exit_signal=True)
    hand = (110 * (1 - fee)) / (100 * (1 + fee)) - 1  # bought at 100 paying fee, sold at 110 paying fee
    record("b_fees", res, {"profit_ratio_hand": hand})


def test_c1_gap_whole_candle_below_stop(default_conf, mocker):
    # entry 100 at candle 1 open; stop 5% -> 95; candle 2 opens 90 and never trades above 95.
    data = [
        [0, 100, 101, 99, 100, 1, 1, 0],
        [1, 100, 101, 99, 100, 1, 0, 0],
        [2, 90, 93, 88, 91, 1, 0, 0],
        [3, 91, 92, 90, 91, 1, 0, 0],
    ]
    res = run_case(default_conf, mocker, data, stoploss=-0.05, roi={"0": 10})
    record("c1_gap_whole_candle_below_stop", res, {"realistic_close_rate": 90})


def test_c2_gap_open_below_stop_then_rally(default_conf, mocker):
    # same, but candle 2 opens at 90, rallies to 97 (above the 95 stop), low 88.
    # A real stop order is triggered at the open, so it fills near 90, not at 95.
    data = [
        [0, 100, 101, 99, 100, 1, 1, 0],
        [1, 100, 101, 99, 100, 1, 0, 0],
        [2, 90, 97, 88, 96, 1, 0, 0],
        [3, 96, 97, 95.5, 96, 1, 0, 0],
    ]
    res = run_case(default_conf, mocker, data, stoploss=-0.05, roi={"0": 10})
    record("c2_gap_open_below_stop_then_rally", res, {"realistic_close_rate": 90})


def test_d_stop_and_roi_same_candle(default_conf, mocker):
    # candle 2 hits both the 5% stop (low 94) and a 5% ROI target (high 106).
    data = [
        [0, 100, 101, 99, 100, 1, 1, 0],
        [1, 100, 101, 99, 100, 1, 0, 0],
        [2, 100, 106, 94, 100, 1, 0, 0],
        [3, 100, 101, 99, 100, 1, 0, 0],
    ]
    res = run_case(default_conf, mocker, data, stoploss=-0.05, roi={"0": 0.05})
    record("d_stop_and_roi_same_candle", res, {"report_only": True})


def test_e_funding_short_constant_rate():
    # Short 1 unit, mark price 100, funding +0.01% every 8h (00, 08, 16 UTC),
    # opened 2024-01-01 00:30, closed 2024-01-02 23:30 -> funding times inside:
    # 01-01 08, 16; 01-02 00, 08, 16 = 5 payments; short RECEIVES 5 * 0.0001 * 100 = 0.05.
    dates = pd.date_range("2024-01-01 00:00", "2024-01-03 00:00", freq="8h", tz="UTC")
    funding = pd.DataFrame({"date": dates, "funding_rate": 0.0001})
    mark = pd.DataFrame({"date": dates, "open": 100.0})
    df = Exchange.combine_funding_and_mark(funding, mark)
    open_d = pd.Timestamp("2024-01-01 00:30", tz="UTC").to_pydatetime()
    close_d = pd.Timestamp("2024-01-02 23:30", tz="UTC").to_pydatetime()
    got = Exchange.calculate_funding_fees(None, df, 1.0, True, open_d, close_d)
    # boundary case: open exactly at a funding time and close exactly at another
    got_edge = Exchange.calculate_funding_fees(
        None, df, 1.0, True, pd.Timestamp("2024-01-01 08:00", tz="UTC").to_pydatetime(),
        pd.Timestamp("2024-01-01 16:00", tz="UTC").to_pydatetime())
    out = {"short_funding": got, "expected": 0.05, "edge_open_at_08_close_at_16": got_edge,
           "edge_note": "a position opened at 08:00 and closed at 16:00: both timestamps are counted (2 payments) if inclusive on both ends"}
    RESULTS["e_funding"] = out
    print("RESULT e_funding", json.dumps(out))
