"""S26 OrderflowChart checks C2-C4 (rules: PREREGISTERED.md).

Usage (venv with orderflowchart installed, from outside its folder):  python -I s26_orderflowchart_checks.py out.json
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from OrderFlow import OrderFlowChart
from OrderFlow._data import footprint_from_trades

out = {}
T = pd.Timestamp("2024-01-02 00:00:00")
m = pd.Timedelta(minutes=1)
# ---------- C2 hand tape: two 5-minute candles ----------
rows = [  # time, price, size, side
    (T + 0 * m, 100.00, 1.0, "buy"),
    (T + 1 * m, 100.20, 2.0, "sell"),
    (T + 1 * m, 100.30, 3.0, "buy"),      # same timestamp as the previous trade
    (T + 2 * m, 100.25, 4.0, "sell"),     # exact half tick -> tie rule
    (T + 3 * m, 100.75, 5.0, "buy"),      # exact half tick -> tie rule
    (T + 4 * m + pd.Timedelta(seconds=59.999), 99.90, 6.0, "sell"),
    (T + 5 * m, 101.00, 7.0, "buy"),      # exactly on the boundary -> second candle
    (T + 6 * m, 100.60, 8.0, "sell"),
    (T + 6 * m, 100.60, 9.0, "sell"),     # duplicate time AND price: must both count
]
tape = pd.DataFrame(rows, columns=["time", "price", "size", "side"]).set_index("time")
of, ohlc = footprint_from_trades(tape, "5min", tick_size=0.5)
c = OrderFlowChart.from_trades(tape, timeframe="5min", tick_size=0.5)
c._ensure_processed()
stats = c._stats

# hand values
lvl = lambda p: float(np.round(p / 0.5) * 0.5)  # what the code states (np.round: ties to even)
hand = {}
for t, p, s, sd in rows:
    k = (str(T if t < T + 5 * m else T + 5 * m), lvl(p))
    b, a = hand.get(k, (0.0, 0.0))
    hand[k] = (b + (s if sd == "sell" else 0.0), a + (s if sd == "buy" else 0.0))
got = {(str(i), float(r.price)): (float(r.bid_size), float(r.ask_size)) for i, r in of.iterrows()}
bar0 = [r for r in rows if r[0] < T + 5 * m]
bar1 = [r for r in rows if r[0] >= T + 5 * m]
hand_ohlc = [[lvl(bar0[0][1]), max(lvl(r[1]) for r in bar0), min(lvl(r[1]) for r in bar0), lvl(bar0[-1][1])],
             [lvl(bar1[0][1]), max(lvl(r[1]) for r in bar1), min(lvl(r[1]) for r in bar1), lvl(bar1[-1][1])]]
got_ohlc = ohlc[["open", "high", "low", "close"]].values.tolist()
d0 = sum(r[2] if r[3] == "buy" else -r[2] for r in bar0)
d1 = sum(r[2] if r[3] == "buy" else -r[2] for r in bar1)
out["C2_from_trades"] = {
    "levels_got": {f"{k[0]} @ {k[1]}": v for k, v in got.items()},
    "levels_hand": {f"{k[0]} @ {k[1]}": v for k, v in hand.items()},
    "tie_100.25_went_to": [k[1] for k in got if k[1] in (100.0, 100.5) and got[k][0] == 4.0],
    "tie_100.75_went_to": [k[1] for k in got if k[1] in (100.5, 101.0) and got[k][1] == 5.0 and k[0] == str(T)],
    "ohlc_got": got_ohlc, "ohlc_hand": hand_ohlc,
    "boundary_trade_in_second_candle": bool(got.get((str(T + 5 * m), 101.0), (0, 0))[1] == 7.0),
    "delta_got": stats["delta"].tolist(), "delta_hand": [d0, d1],
    "cum_delta_got": stats["cum_delta"].tolist(), "cum_delta_hand": [d0, d0 + d1],
    "volume_total_got": float(of.bid_size.sum() + of.ask_size.sum()), "volume_total_hand": float(sum(r[2] for r in rows)),
    "pass": bool(got == hand and got_ohlc == hand_ohlc and stats["delta"].tolist() == [d0, d1]
                 and stats["cum_delta"].tolist() == [d0, d0 + d1]),
}

# ---------- C3 diagonal imbalance on a hand-built candle ----------
fp = c._footprint
c0 = fp[fp["bar"] == fp["bar"].min()].set_index("price")
res = {}
for p in c0.index:
    bid_p = float(c0.loc[p, "bid_size"])
    ask_above = float(c0.loc[p + 0.5, "ask_size"]) if (p + 0.5) in c0.index else 0.0
    den = bid_p + ask_above
    hand_imb = (bid_p - ask_above) / den if den > 0 else 0.0
    res[str(p)] = {"got": float(c0.loc[p, "imbalance"]), "hand": hand_imb}
out["C3_diagonal_imbalance"] = {"rows": res,
                                "pass": bool(all(abs(v["got"] - v["hand"]) < 1e-12 for v in res.values()))}

# ---------- C4 scale ----------
rng = np.random.default_rng(26)
n = 86_400
idx = pd.date_range("2024-01-03", periods=n, freq="1s")
px = 42_000 + np.cumsum(rng.normal(0, 2.0, n))
big = pd.DataFrame({"price": px, "size": rng.exponential(0.05, n),
                    "side": np.where(rng.random(n) < 0.5, "buy", "sell")}, index=idx)
t0 = time.perf_counter()
cb = OrderFlowChart.from_trades(big, timeframe="5min", tick_size=5.0)
cb._ensure_processed()
t1 = time.perf_counter()
fig = cb.plot(return_figure=True)
t2 = time.perf_counter()
out["C4_scale"] = {"trades": n, "candles": int(len(cb._bars)), "footprint_rows": int(len(cb._footprint)),
                   "build_s": round(t1 - t0, 2), "figure_s": round(t2 - t1, 2), "traces": len(fig.data)}

with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:900])
