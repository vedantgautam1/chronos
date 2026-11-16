"""S35 gs-quant checks G2-G6 (rules: PREREGISTERED.md).

Usage (venv with gs-quant installed, from outside its folder):
    python -I s35_gsquant_checks.py /path/to/btc_bitstamp_5m_2023_2024.feather out.json
"""
import datetime as dt
import json
import math
import subprocess
import sys
import warnings
import zoneinfo

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
btc_path, out_path = sys.argv[1], sys.argv[2]
out = {}

from gs_quant.timeseries import econometrics as ec  # noqa: E402
from gs_quant.timeseries import statistics as st  # noqa: E402

# ---------- G2 annualisation ----------
d5 = pd.read_feather(btc_path).set_index("date")
d5.index = d5.index.tz_localize(None) if d5.index.tz is not None else d5.index
daily = d5["close"].resample("1D").last().loc["2023-01-01":"2023-12-31"].dropna()
vol = ec.volatility(daily)
r = daily.pct_change().dropna()
hand_unann = r.std(ddof=1) * 100
got = float(vol.iloc[-1])
factor = (got / hand_unann) ** 2
out["G2_daily"] = {
    "n_days": int(len(daily)),
    "gs_vol_pct": got,
    "hand_252": hand_unann * math.sqrt(252),
    "hand_365": hand_unann * math.sqrt(365),
    "implied_factor": factor,
    "pass": bool(abs(got - hand_unann * math.sqrt(round(factor))) < 1e-9),
}
vol365 = float(ec.volatility(daily, annualization_factor=365).iloc[-1])
out["G2_daily_with_factor_365"] = {"gs_vol_pct": vol365, "hand_365": hand_unann * math.sqrt(365),
                                   "match": bool(abs(vol365 - hand_unann * math.sqrt(365)) < 1e-9)}
hourly = d5["close"].resample("1h").last().loc["2023-01-01":"2023-01-31"].dropna()
try:
    hv = ec.volatility(hourly)
    out["G2_hourly"] = {"error": None, "value": float(hv.iloc[-1])}
except Exception as exc:  # report, don't hide
    out["G2_hourly"] = {"error": repr(exc)[:300]}

# ---------- G3 mid-rank ties ----------
idx = pd.date_range("2024-01-01", periods=5, freq="D")
x = pd.Series([1.0, 2.0, 2.0, 2.0, 3.0], index=idx)
# Harness fix after the first run: with y = one point, the window defaults to len(y) = 1, so the first
# run compared 2 against [3] only (gave 0.0). Use a y on the same index so the window is all 5 values.
y = pd.Series([2.0] * 5, index=idx)
p = st.percentiles(x, y)
out["G3_percentiles_ties"] = {"value": float(p.iloc[-1]), "expected_midrank": 50.0,
                              "pass": bool(abs(float(p.iloc[-1]) - 50.0) < 1e-12)}

# ---------- G4 look-ahead clock ----------
from gs_quant.backtests.actions import AddTradeAction  # noqa: E402
from gs_quant.backtests.backtest_objects import ConstantTransactionModel  # noqa: E402
from gs_quant.backtests.core import ValuationFixingType  # noqa: E402
from gs_quant.backtests.data_sources import DataManager  # noqa: E402
from gs_quant.backtests.order import OrderTWAP, TimeWindow  # noqa: E402
from gs_quant.backtests.predefined_asset_engine import PredefinedAssetEngine  # noqa: E402
from gs_quant.backtests.strategy import Strategy  # noqa: E402
from gs_quant.backtests.triggers import (  # noqa: E402
    DateTrigger, DateTriggerRequirements, OrdersGeneratorTrigger)
from gs_quant.data.core import DataFrequency  # noqa: E402
from gs_quant.instrument import IRBondFuture  # noqa: E402

tz = zoneinfo.ZoneInfo("UTC")
inst = IRBondFuture(currency="USD", name="SYNTH")
day1, day2 = dt.date(2024, 3, 4), dt.date(2024, 3, 5)
minutes = []
for d in (day1, day2):
    minutes += list(pd.date_range(dt.datetime.combine(d, dt.time(9, 0)), dt.datetime.combine(d, dt.time(17, 0)),
                                  freq="1min"))
rt = pd.Series(np.arange(len(minutes), dtype=float) + 100.0, index=minutes)
eod = pd.Series({day1: 1111.0, day2: 2222.0})  # date-keyed end-of-day values
probe = {}


class Probe(OrdersGeneratorTrigger):
    def get_trigger_times(self):
        return [dt.time(10, 0)]

    def generate_orders(self, state, backtest=None):
        if state.date() != day2 or probe:
            return []
        dh = backtest.data_handler
        for name, key in (("same_day_11am", dt.datetime.combine(day2, dt.time(11, 0))), ("same_day_eod_date", day2)):
            try:
                probe[name] = {"returned": float(dh.get_data(key, inst, ValuationFixingType.PRICE))}
            except Exception as exc:
                probe[name] = {"refused": repr(exc)[:200]}
        return []


dm = DataManager()
dm.add_data_source(rt, DataFrequency.REAL_TIME, inst, ValuationFixingType.PRICE)
dm.add_data_source(eod, DataFrequency.DAILY, inst, ValuationFixingType.PRICE)
states = [dt.datetime.combine(d, t) for d in (day1, day2) for t in (dt.time(10, 0), dt.time(17, 0))]
eng = PredefinedAssetEngine(data_mgr=dm, tz=tz)
try:
    eng.run_backtest(Strategy(None, triggers=[Probe()]), start=states[0], end=states[-1], states=states)
except Exception as exc:
    probe["run_error"] = repr(exc)[:300]
out["G4_clock"] = {"probe": probe,
                   "pass": bool("refused" in probe.get("same_day_11am", {})
                                and "refused" in probe.get("same_day_eod_date", {}))}

# ---------- G5 TWAP + transaction cost ----------
twap_fill = {}


class Twap(OrdersGeneratorTrigger):
    def get_trigger_times(self):
        return [dt.time(9, 30)]

    def generate_orders(self, state, backtest=None):
        if state.date() != day2:
            return []
        w = TimeWindow(start=dt.datetime.combine(day2, dt.time(10, 0)), end=dt.datetime.combine(day2, dt.time(10, 30)))
        return [OrderTWAP(instrument=inst, quantity=1, generation_time=state, window=w, source="t")]


states2 = [dt.datetime.combine(d, t) for d in (day1, day2) for t in (dt.time(9, 30), dt.time(10, 30), dt.time(17, 0))]
eng2 = PredefinedAssetEngine(data_mgr=dm, tz=tz)
bt2 = eng2.run_backtest(Strategy(None, triggers=[Twap()]), start=states2[0], end=states2[-1], states=states2)
orders = [o for o in bt2.orders if isinstance(o, OrderTWAP)]
fill = float(orders[0].executed_price) if orders and orders[0].executed_price is not None else None
win = rt.loc[dt.datetime.combine(day2, dt.time(10, 0)):dt.datetime.combine(day2, dt.time(10, 30))]
incl = float(win.mean())
half_open = float(win.iloc[:-1].mean())
left_open = float(win.iloc[1:].mean())  # (start, end]: added after the first run showed neither of the above
twap_fill.update({"fill": fill, "mean_inclusive_both_ends": incl, "mean_half_open": half_open,
                  "mean_left_open_(start,end]": left_open,
                  "bounds": "inclusive" if fill is not None and abs(fill - incl) < 1e-9 else
                  ("half-open [start,end)" if fill is not None and abs(fill - half_open) < 1e-9 else
                   ("(start,end]" if fill is not None and abs(fill - left_open) < 1e-9 else "other"))})

# transaction cost through AddTradeAction on a DateTrigger
act = AddTradeAction(inst, transaction_cost=ConstantTransactionModel(5.0))
trig = DateTrigger(DateTriggerRequirements(dates=[dt.datetime.combine(day2, dt.time(10, 0))]), actions=[act])
states3 = [dt.datetime.combine(d, t) for d in (day1, day2) for t in (dt.time(10, 0), dt.time(17, 0))]
eng3 = PredefinedAssetEngine(data_mgr=dm, tz=tz)
cost_info = {}
try:
    bt3 = eng3.run_backtest(Strategy(None, triggers=[trig]), start=states3[0], end=states3[-1], states=states3)
    costs = bt3.get_costs()
    cost_info = {"booked_costs_total": float(costs.sum()) if len(costs) else 0.0, "expected": 5.0,
                 "n_orders": len(bt3.orders),
                 "order_types": sorted({type(o).__name__ for o in bt3.orders})}
except Exception as exc:
    cost_info = {"error": repr(exc)[:300]}
out["G5_twap_and_cost"] = {"twap": twap_fill, "cost": cost_info,
                           "pass": bool(twap_fill["bounds"] != "other"
                                        and cost_info.get("booked_costs_total") == 5.0)}

# ---------- G6 MCP tools (offline discovery) ----------
try:
    res = subprocess.run([sys.executable, "-m", "gs_quant.mcp", "discover-tools"], capture_output=True, text=True,
                         timeout=120)
    out["G6_mcp_discover"] = {"rc": res.returncode, "stdout": res.stdout[-4000:], "stderr": res.stderr[-1500:]}
except Exception as exc:
    out["G6_mcp_discover"] = {"error": repr(exc)[:300]}

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:700])
