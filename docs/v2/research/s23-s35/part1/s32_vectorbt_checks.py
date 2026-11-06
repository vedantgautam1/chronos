"""S32 vectorbt checks V2-V8 (rules: PREREGISTERED.md).

Usage (venv with vectorbt + quantstats installed, from outside their folders):
    python -I s32_vectorbt_checks.py /path/to/btc_bitstamp_5m_2023_2024.feather out.json
"""
import json
import resource
import sys
import time
import warnings

import numpy as np
import pandas as pd
import vectorbt as vbt

warnings.simplefilter("ignore")
REL = 1e-9
out = {}


def close_enough(a, b, rel=REL):
    return bool(abs(a - b) <= rel * max(1.0, abs(b)))


def candles(rows):
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="1h", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    return df


# ---------------- V2 fill timing ----------------
df = candles([(100, 101, 99, 100), (102, 104, 101, 103), (103, 106, 102, 105), (105, 107, 104, 106)])
ent = pd.Series([True, False, False, False], index=df.index)
ext = pd.Series([False, False, True, False], index=df.index)
pf = vbt.Portfolio.from_signals(df["close"], ent, ext, init_cash=10_000, freq="1h")
t = pf.trades.records_readable
out["V2a_default_fill"] = {"entry_price": float(t["Avg Entry Price"].iloc[0]), "entry_time": str(t["Entry Timestamp"].iloc[0]),
                           "close_of_signal_bar": 100.0, "note": "default fills at the signal bar's close"}
pf = vbt.Portfolio.from_signals(df["close"], ent.vbt.fshift(1, fill_value=False), ext.vbt.fshift(1, fill_value=False),
                                price=df["open"], open=df["open"], high=df["high"], low=df["low"],
                                init_cash=10_000, freq="1h")
t = pf.trades.records_readable
out["V2b_next_open"] = {"entry_price": float(t["Avg Entry Price"].iloc[0]), "expected": 102.0,
                        "exit_price": float(t["Avg Exit Price"].iloc[0]), "expected_exit": 105.0,
                        "note": "expected_exit corrected 106 -> 105 after first run: 106 was bar 3 close, the rule is bar 3 open (fixture error)",
                        "pass": close_enough(t["Avg Entry Price"].iloc[0], 102.0) and close_enough(t["Avg Exit Price"].iloc[0], 105.0)}

# ---------------- V3 costs ----------------
size = 1.0
pf = vbt.Portfolio.from_signals(df["close"], ent, ext, size=size, fees=0.001, init_cash=10_000, freq="1h")
hand = (105 - 100) * size - 0.001 * 100 * size - 0.001 * 105 * size
out["V3a_prop_fee"] = {"pnl": float(pf.trades.pnl.sum()), "hand": hand, "pass": close_enough(pf.trades.pnl.sum(), hand)}
pf = vbt.Portfolio.from_signals(df["close"], ent, ext, size=size, fixed_fees=0.27, init_cash=10_000, freq="1h")
hand = (105 - 100) * size - 0.27 * 2
out["V3b_fixed_fee"] = {"pnl": float(pf.trades.pnl.sum()), "hand": hand, "pass": close_enough(pf.trades.pnl.sum(), hand)}
pf = vbt.Portfolio.from_signals(df["close"], ent, ext, size=size, fees=0.001, fixed_fees=0.27, direction="shortonly",
                                init_cash=10_000, freq="1h")
hand = (100 - 105) * size - 0.001 * 100 - 0.001 * 105 - 0.27 * 2
out["V3c_short"] = {"pnl": float(pf.trades.pnl.sum()), "hand": hand, "pass": close_enough(pf.trades.pnl.sum(), hand)}
import inspect
params = set(inspect.signature(vbt.Portfolio.from_signals).parameters)
fund_like = sorted(p for p in params if any(k in p for k in ("fund", "earn", "divid", "carry", "interest", "cash_flow")))
out["V3d_funding_native"] = {"funding_like_params": fund_like, "native_funding": bool(fund_like)}

# ---------------- V4 stops ----------------
df4 = candles([(100, 100.5, 99.5, 100), (90, 97, 88, 96), (96, 97, 95, 96)])
e4 = pd.Series([True, False, False], index=df4.index)
x4 = pd.Series([False, False, False], index=df4.index)
pf = vbt.Portfolio.from_signals(df4["close"], e4, x4, open=df4["open"], high=df4["high"], low=df4["low"],
                                sl_stop=0.05, size=1, init_cash=10_000, freq="1h")
t = pf.trades.records_readable
out["V4a_gap_with_ohlc"] = {"exit_price": float(t["Avg Exit Price"].iloc[0]), "realistic": 90.0,
                            "exit_time": str(t["Exit Timestamp"].iloc[0]),
                            "pass": float(t["Avg Exit Price"].iloc[0]) <= 90.0 + 1e-9}
pf = vbt.Portfolio.from_signals(df4["close"], e4, x4, sl_stop=0.05, size=1, init_cash=10_000, freq="1h")
t = pf.trades.records_readable
out["V4b_close_only"] = {"exit_price": float(t["Avg Exit Price"].iloc[0]) if len(t) else None,
                         "exit_time": str(t["Exit Timestamp"].iloc[0]) if len(t) else None,
                         "status": str(t["Status"].iloc[0]) if len(t) else None}
df4b = candles([(100, 100.5, 99.5, 100), (99, 99.5, 93, 97), (97, 98, 96, 97)])  # stop hit intrabar, no gap
pf = vbt.Portfolio.from_signals(df4b["close"], e4, x4, open=df4b["open"], high=df4b["high"], low=df4b["low"],
                                sl_stop=0.05, size=1, slippage=0.001, init_cash=10_000, freq="1h")
t = pf.trades.records_readable
out["V4c_stop_slippage_default"] = {"exit_price": float(t["Avg Exit Price"].iloc[0]), "stop_price": 95.0,
                                    "with_slippage_would_be": 95.0 * 0.999,
                                    "slippage_applied": not close_enough(t["Avg Exit Price"].iloc[0], 95.0)}

# ---------------- V5 stats ----------------
rng = np.random.default_rng(20261105)
px = 100 * np.exp(np.cumsum(rng.normal(0.0001, 0.004, 500)))
idx = pd.date_range("2025-01-01", periods=500, freq="1h", tz="UTC")
cl = pd.Series(px, index=idx)
pf = vbt.Portfolio.from_holding(cl, init_cash=10_000, freq="1h")
r = pf.returns()
st = pf.stats()
sh_hand = r.mean() / r.std(ddof=1) * np.sqrt(8760)
val = pf.value()
mdd_hand = (val / val.cummax() - 1).min() * 100
out["V5_stats"] = {"sharpe_vbt": float(st["Sharpe Ratio"]), "sharpe_hand": float(sh_hand),
                   "mdd_vbt_pct": float(st["Max Drawdown [%]"]), "mdd_hand_pct": float(-mdd_hand),
                   "pass": close_enough(st["Sharpe Ratio"], sh_hand) and close_enough(st["Max Drawdown [%]"], -mdd_hand)}
cl_nofreq = pd.Series(px)  # integer index, no freq
try:
    pf2 = vbt.Portfolio.from_holding(cl_nofreq, init_cash=10_000)
    s2 = pf2.stats()
    out["V5_no_freq"] = {"sharpe_present": "Sharpe Ratio" in s2.index, "keys": [k for k in s2.index if "Sharpe" in k or "Ann" in k]}
except Exception as exc:
    out["V5_no_freq"] = {"error": repr(exc)[:300]}

# ---------------- V8 vs quantstats ----------------
import quantstats as qs
qs_sh = qs.stats.sharpe(r, periods=8760)
out["V8_vs_quantstats"] = {"vbt": float(st["Sharpe Ratio"]), "quantstats": float(qs_sh),
                           "pass": close_enough(st["Sharpe Ratio"], qs_sh)}

# ---------------- V6 speed + V7 look-ahead on real data ----------------
d5 = pd.read_feather(sys.argv[1]).set_index("date")
h = d5.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
h = h.loc["2023-01-01":"2024-12-31 23:00"]
close, opn = h["close"], h["open"]
fast = np.arange(5, 85, 2)    # 40 values
slow = np.arange(100, 350, 10)  # 25 values -> 1,000 pairs, all fast < slow
t0 = time.perf_counter()
wins = np.unique(np.r_[fast, slow])
ma = vbt.MA.run(close, window=wins).ma  # one column per window
ma.columns = wins
pf_fast = np.repeat(fast, len(slow))
pf_slow = np.tile(slow, len(fast))
cols = pd.MultiIndex.from_arrays([pf_fast, pf_slow], names=["fast", "slow"])
fm = pd.DataFrame(ma[pf_fast].values, index=close.index, columns=cols)
sm = pd.DataFrame(ma[pf_slow].values, index=close.index, columns=cols)
keep = np.ones(len(cols), dtype=bool)
entries = fm.vbt.crossed_above(sm).vbt.fshift(1, fill_value=False)
exits = fm.vbt.crossed_below(sm).vbt.fshift(1, fill_value=False)
pf = vbt.Portfolio.from_signals(close, entries, exits, price=opn, fees=0.001, init_cash=10_000, freq="1h")
tr = pf.total_return()
elapsed = time.perf_counter() - t0
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
out["V6_speed"] = {"bars": int(len(close)), "variants": int(keep.sum()), "seconds_incl_numba_compile": round(elapsed, 2),
                   "peak_rss_mb": round(rss, 1), "pass": bool(elapsed <= 60 and keep.sum() == 1000),
                   "note": "toy grid; returns not evidence"}
# second run (compiled)
t0 = time.perf_counter()
pf = vbt.Portfolio.from_signals(close, entries, exits, price=opn, fees=0.001, init_cash=10_000, freq="1h")
tr = pf.total_return()
out["V6_speed"]["portfolio_only_second_run_s"] = round(time.perf_counter() - t0, 2)

rng = np.random.default_rng(7)
cuts = np.sort(rng.choice(np.arange(400, len(h) - 1), size=200, replace=False))
ind = {
    "MA20": lambda d: vbt.MA.run(d["close"], 20).ma,
    "EMA50": lambda d: vbt.MA.run(d["close"], 50, ewm=True).ma,
    "MSTD20": lambda d: vbt.MSTD.run(d["close"], 20).mstd,
    "BB_upper20": lambda d: vbt.BBANDS.run(d["close"], 20).upper,
    "RSI14": lambda d: vbt.RSI.run(d["close"], 14).rsi,
    "ATR14": lambda d: vbt.ATR.run(d["high"], d["low"], d["close"], 14).atr,
}
v7 = {}
for name, f in ind.items():
    full = f(h)
    bad = 0
    worst = 0.0
    for c in cuts:
        part = f(h.iloc[: c + 1])
        a, b = float(full.iloc[c]), float(part.iloc[-1])
        if np.isnan(a) and np.isnan(b):
            continue
        rel = abs(a - b) / max(1e-12, abs(a))
        worst = max(worst, rel)
        if rel > REL:
            bad += 1
    v7[name] = {"mismatches": bad, "of": len(cuts), "worst_rel": worst}
bar = len(h) - 1
e_long = float(vbt.MA.run(h["close"].iloc[bar - 5000: bar + 1], 200, ewm=True).ma.iloc[-1])
e_short = float(vbt.MA.run(h["close"].iloc[bar - 500: bar + 1], 200, ewm=True).ma.iloc[-1])
v7["EMA200_warmup_500_vs_5000"] = {"rel_diff": abs(e_long - e_short) / e_long}
v7["pass"] = all(v["mismatches"] == 0 for k, v in v7.items() if isinstance(v, dict) and "mismatches" in v)
out["V7_lookahead"] = v7

with open(sys.argv[2], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:400])
