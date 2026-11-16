"""B4: do freqtrade's look-ahead and recursive-analysis tools catch small leaks?
Copied at run time to freqtrade/tests/optimize/test_s19deep_leaks.py; uses freqtrade's
fixtures and its bundled UNITTEST/BTC 5m test data (same set-up as its own tests)."""
import json
from pathlib import Path
from unittest.mock import PropertyMock

import pytest

from freqtrade.data.history import get_timerange
from freqtrade.optimize.analysis.lookahead import LookaheadAnalysis
from freqtrade.optimize.analysis.recursive import RecursiveAnalysis
from freqtrade.util.progress_tracker import get_progress_tracker
from tests.conftest import EXMS, patch_exchange

STRATS = str(Path(__file__).parent.parent / "strategy/strats/s19deep")


def _conf(default_conf_usdt, tmp_path, scenario, mocker):
    patch_exchange(mocker)
    mocker.patch(f"{EXMS}.get_fee", return_value=0.0)
    mocker.patch(f"{EXMS}.get_min_pair_stake_amount", return_value=0.00001)
    mocker.patch(f"{EXMS}.get_max_pair_stake_amount", return_value=float("inf"))
    mocker.patch("freqtrade.data.history.get_timerange", get_timerange)
    mocker.patch("freqtrade.plugins.pairlistmanager.PairListManager.whitelist",
                 PropertyMock(return_value=["UNITTEST/BTC"]))
    mocker.patch("freqtrade.strategy.hyper.HyperStrategyMixin.load_params_from_file",
                 return_value={"params": {"buy": {"scenario": scenario}}})
    c = default_conf_usdt
    c["user_data_dir"] = tmp_path
    c["strategy_path"] = STRATS
    c["strategy"] = "s19deep_leaks"
    c["pairs"] = ["UNITTEST/BTC"]
    c["timeframe"] = "5m"
    c["timerange"] = "20180119-20180122"
    c["minimum_trade_amount"] = 10
    c["targeted_trade_amount"] = 20
    c["max_open_trades"] = 1
    c["dry_run_wallet"] = 1000000000
    return c


@pytest.mark.parametrize("scenario", ["clean", "lead1", "fullmean", "fullmean2"])
def test_lookahead(default_conf_usdt, tmp_path, mocker, scenario):
    c = _conf(default_conf_usdt, tmp_path, scenario, mocker)
    inst = LookaheadAnalysis(c, {"name": "s19deep_leaks"})
    inst.start(get_progress_tracker())
    a = inst.current_analysis
    out = {"has_bias": bool(a.has_bias), "total_signals": a.total_signals,
           "false_entry_signals": a.false_entry_signals, "false_exit_signals": a.false_exit_signals,
           "false_indicators": list(a.false_indicators), "failed_bias_check": bool(inst.failed_bias_check)}
    print("RESULT lookahead", scenario, json.dumps(out))


@pytest.mark.parametrize("scenario", ["sma_clean", "ema_warmup"])
def test_recursive(default_conf_usdt, tmp_path, mocker, scenario):
    c = _conf(default_conf_usdt, tmp_path, scenario, mocker)
    c["startup_candle"] = [30, 100, 200]
    inst = RecursiveAnalysis(c, {"name": "s19deep_leaks"})
    inst.start(get_progress_tracker())
    out = {"dict_recursive": {k: {str(kk): str(vv) for kk, vv in v.items()} for k, v in inst.dict_recursive.items()}}
    print("RESULT recursive", scenario, json.dumps(out))
