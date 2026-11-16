"""S28 zipline-reloaded checks Z2-Z7 (rules: PREREGISTERED.md).

Usage (venv with zipline-reloaded installed, from outside its folder):
    python -I s28_zipline_checks.py /path/to/btc_bitstamp_5m_2023_2024.feather workdir out.json
"""
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
btc_path, work, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["ZIPLINE_ROOT"] = os.path.join(work, "zroot")

from zipline import run_algorithm  # noqa: E402
from zipline.api import order, set_benchmark, symbol  # noqa: E402
from zipline.data import bundles  # noqa: E402
from zipline.data.bundles.csvdir import csvdir_equities  # noqa: E402
from zipline.utils.calendar_utils import get_calendar  # noqa: E402

out = {}


def make_bundle(name, cal_name, frames):
    d = os.path.join(work, name, "daily")
    os.makedirs(d, exist_ok=True)
    for sym, df in frames.items():
        df.to_csv(os.path.join(d, f"{sym}.csv"), index_label="date")
    bundles.register(name, csvdir_equities(["daily"], os.path.join(work, name)), calendar_name=cal_name)
    bundles.ingest(name, show_progress=False)


def frame(sessions, close, volume):
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                         "volume": volume, "dividend": 0.0, "split": 1.0}, index=sessions)


# ---------- synthetic NYSE stocks ----------
nyse = get_calendar("XNYS")
sess = nyse.sessions_in_range(pd.Timestamp("2023-01-03"), pd.Timestamp("2023-06-30"))
rng = np.random.default_rng(20261106)
close_a = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(sess)))), index=sess).round(2)
close_b = pd.Series(50 * np.exp(np.cumsum(rng.normal(0, 0.01, len(sess)))), index=sess).round(2)
close_c = pd.Series(80 * np.exp(np.cumsum(rng.normal(0, 0.01, len(sess)))), index=sess).round(2)
make_bundle("s28eq", "XNYS", {
    "AAA": frame(sess, close_a, 1_000_000),
    "BBB": frame(sess, close_b, 20_000),
    "CCC": frame(sess, close_c, 1_000_000),
})
start, end = sess[5], sess[64]
seen = []


def init(ctx):
    ctx.a, ctx.b, ctx.c = symbol("AAA"), symbol("BBB"), symbol("CCC")
    set_benchmark(ctx.a)
    ctx.i = 0


def handle(ctx, data):
    dt = data.current_session if hasattr(data, "current_session") else data.current_dt.normalize()
    h = data.history(ctx.a, "close", 2, "1d")
    seen.append((str(pd.Timestamp(dt).date()), float(h.iloc[-1]), float(data.current(ctx.a, "close"))))
    if ctx.i == 0:
        order(ctx.a, 100)        # Z2
        order(ctx.b, 10_000)     # Z3
        order(ctx.c, -100)       # Z4 open short
    if ctx.i == 3:
        order(ctx.c, 100)        # Z4 cover
    ctx.i += 1


perf = run_algorithm(start=start, end=end, initialize=init, handle_data=handle, capital_base=1_000_000,
                     bundle="s28eq", data_frequency="daily")
tx = [t for day in perf["transactions"] for t in day]
txdf = pd.DataFrame(tx)
txdf["sym"] = txdf["sid"].map(lambda s: s.symbol)
txdf["day"] = pd.to_datetime(txdf["dt"]).dt.tz_localize(None).dt.normalize()
orders = [o for day in perf["orders"] for o in day]
comm = {}
for o in orders:
    comm[o["id"]] = o["commission"]
# Z2
a = txdf[txdf.sym == "AAA"].iloc[0]
t1 = sess[sess.get_loc(start) + 1]
z2_price_hand = float(close_a.loc[t1]) * 1.0005
a_comm = sum(o["commission"] for o in orders if o["sid"].symbol == "AAA")
out["Z2_fill_and_costs"] = {"fill_day": str(a.day.date()), "expected_day": str(t1.date()), "fill_price": float(a.price),
                            "hand_price": z2_price_hand, "commission": float(a_comm), "hand_commission": 0.10,
                            "pass": bool(a.day == t1 and abs(a.price - z2_price_hand) < 1e-6 and abs(a_comm - 0.10) < 1e-9)}
# Z3
b = txdf[txdf.sym == "BBB"].groupby("day")["amount"].sum()
out["Z3_volume_cap"] = {"fills_per_day": {str(k.date()): int(v) for k, v in b.items()}, "total": int(b.sum())}
# Z4
c = txdf[txdf.sym == "CCC"].sort_values("dt")
sell, buy = c.iloc[0], c.iloc[1]
c_comm = sum(o["commission"] for o in orders if o["sid"].symbol == "CCC")
s_day, b_day = sell.day, buy.day
hand_sell = float(close_c.loc[s_day]) * (1 - 0.0005)
hand_buy = float(close_c.loc[b_day]) * (1 + 0.0005)
hand_pnl = 100 * (hand_sell - hand_buy) - 0.20
got_pnl = 100 * (sell.price * -1 * -1 - buy.price) - c_comm if sell.amount < 0 else None
out["Z4_short"] = {"short_fill": [str(s_day.date()), float(sell.price), int(sell.amount)],
                   "cover_fill": [str(b_day.date()), float(buy.price), int(buy.amount)],
                   "zipline_pnl_from_fills": float(100 * (sell.price - buy.price) - c_comm), "hand_pnl": hand_pnl,
                   "commission": float(c_comm),
                   "pass": bool(abs(100 * (sell.price - buy.price) - c_comm - hand_pnl) < 1e-6
                                and abs(sell.price - hand_sell) < 1e-6 and abs(buy.price - hand_buy) < 1e-6)}
# Z5
bad = [(d, h, cur, float(close_a.loc[pd.Timestamp(d)])) for d, h, cur in seen
       if not (abs(h - close_a.loc[pd.Timestamp(d)]) < 1e-9 and abs(cur - close_a.loc[pd.Timestamp(d)]) < 1e-9)]
out["Z5_no_peeking"] = {"days": len(seen), "mismatches": len(bad), "examples": bad[:3], "pass": len(bad) == 0}

# ---------- Z6/Z7 24/7 BTC ----------
d5 = pd.read_feather(btc_path).set_index("date")
day = d5.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
day = day.loc["2023-01-01":"2023-12-31"]
day.index = day.index.tz_localize(None) if day.index.tz is not None else day.index
day["dividend"], day["split"] = 0.0, 1.0
try:
    make_bundle("s28btc", "24/7", {"BTC": day})
    t0 = time.perf_counter()

    def init2(ctx):
        ctx.btc = symbol("BTC")
        set_benchmark(ctx.btc)
        ctx.done = False

    def handle2(ctx, data):
        if not ctx.done:
            order(ctx.btc, 2)
            ctx.done = True

    perf2 = run_algorithm(start=pd.Timestamp("2023-01-03"), end=pd.Timestamp("2023-12-31"), initialize=init2,
                          handle_data=handle2, capital_base=100_000, bundle="s28btc", data_frequency="daily",
                          trading_calendar=get_calendar("24/7"))  # added after first run: calendar must also be passed to the run
    el = time.perf_counter() - t0
    days = pd.to_datetime(perf2.index).tz_localize(None).normalize() if perf2.index.tz is not None else perf2.index
    weekdays = sorted(set(pd.DatetimeIndex(days).day_name()))
    out["Z6_247"] = {"rows": int(len(perf2)), "expected_rows": int(len(pd.date_range("2023-01-03", "2023-12-31"))),
                     "weekday_names": weekdays, "final_portfolio_value": float(perf2["portfolio_value"].iloc[-1]),
                     "pass": bool(len(perf2) == len(pd.date_range("2023-01-03", "2023-12-31")))}  # start moved 2 Jan -> 3 Jan after first run (needs a prior session)
    out["Z7_speed"] = {"seconds_one_year_daily": round(el, 2)}
except Exception as exc:  # report, don't hide
    out["Z6_247"] = {"error": repr(exc)[:500], "pass": False}

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:600])
