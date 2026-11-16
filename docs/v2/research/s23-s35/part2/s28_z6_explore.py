"""Exploratory (after Z6 failed as pre-registered): what does a 24/7 BTC daily run on zipline-reloaded need?
Usage: python -I s28_z6_explore.py /path/btc_5m.feather workdir out.json
Reuses the bundle ingested by s28_zipline_checks.py in the same workdir (ZIPLINE_ROOT)."""
import json, os, sys, time, traceback, warnings
import pandas as pd
warnings.simplefilter("ignore")
os.environ["ZIPLINE_ROOT"] = os.path.join(sys.argv[2], "zroot")
from zipline import run_algorithm
from zipline.api import order, set_benchmark, symbol
from zipline.data import bundles
from zipline.data.bundles.csvdir import csvdir_equities
from zipline.utils.calendar_utils import get_calendar
bundles.register("s28btc", csvdir_equities(["daily"], os.path.join(sys.argv[2], "s28btc")), calendar_name="24/7")
res = {}
for end, own_bench in [("2023-12-31", False), ("2023-12-30", False), ("2023-12-31", True)]:
    def init(ctx, own_bench=own_bench):
        ctx.btc = symbol("BTC"); ctx.done = False
        if not own_bench: set_benchmark(ctx.btc)
    def handle(ctx, data):
        if not ctx.done:
            order(ctx.btc, 2); ctx.done = True
    t0 = time.perf_counter()
    try:
        perf = run_algorithm(start=pd.Timestamp("2023-01-03"), end=pd.Timestamp(end), initialize=init, handle_data=handle,
                             capital_base=100_000, bundle="s28btc", data_frequency="daily", trading_calendar=get_calendar("24/7"),
                             **({"benchmark_returns": pd.Series(0.0, index=pd.date_range("2023-01-01", end, tz="UTC"))} if own_bench else {}))
        idx = pd.DatetimeIndex(perf.index)
        res[end + (" own benchmark" if own_bench else "")] = {"ok": True, "rows": len(perf), "calendar_days": len(pd.date_range("2023-01-03", end)),
                    "day_names": sorted(set(idx.day_name())), "seconds": round(time.perf_counter() - t0, 2),
                    "final_value": float(perf["portfolio_value"].iloc[-1])}
    except Exception:
        res[end + (" own benchmark" if own_bench else "")] = {"ok": False, "trace_tail": traceback.format_exc().splitlines()[-6:]}
json.dump(res, open(sys.argv[3], "w"), indent=2, default=str)
print(json.dumps(res, default=str)[:1500])
