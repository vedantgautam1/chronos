"""S33 ml4t-backtest 0.2.0 checks M2.1-M2.8 (rules: PREREGISTERED.md).

Usage (venv with ml4t-backtest 0.2.0, from outside its folder):
    python -I s33_ml4tbt_checks.py /path/to/btc_bitstamp_5m_2023_2024.feather out.json
"""
import json
import sys
import time
import warnings
from datetime import datetime, timedelta

import polars as pl

warnings.simplefilter("ignore")
btc_path, out_path = sys.argv[1], sys.argv[2]

from ml4t.backtest import (AssetClass, BacktestConfig, CommissionType, ContractSpec, DataFeed, Engine,  # noqa: E402
                           OrderType, RuleChain, StopLoss, Strategy, TakeProfit)
from ml4t.backtest.controls import OrderConstraints  # noqa: E402

out = {}
T0 = datetime(2024, 1, 2)


def bars(rows, asset="X", step=timedelta(days=1)):
    ts = [T0 + i * step for i in range(len(rows))]
    o, h, lo, c = ([float(v) for v in col] for col in zip(*rows))
    return pl.DataFrame({"timestamp": ts, "asset": [asset] * len(rows), "open": o, "high": h,
                         "low": lo, "close": c, "volume": [1e9] * len(rows)}), ts


class Scripted(Strategy):
    """Runs plan[i](broker) on bar i; logs cash/position at the start of each bar."""

    def __init__(self, plan, asset="X", setup=None):
        self.plan, self.asset, self.setup, self.i, self.log, self.errors = plan, asset, setup, 0, [], []

    def on_data(self, timestamp, data, context, broker):
        if self.i == 0 and self.setup:
            self.setup(broker)
        pos = broker.get_position(self.asset)
        self.log.append({"bar": self.i, "cash": broker.get_cash(), "qty": pos.quantity if pos else 0.0})
        if self.i in self.plan:
            try:
                self.plan[self.i](broker)
            except Exception as exc:  # report, don't hide
                self.errors.append({"bar": self.i, "error": repr(exc)[:300]})
        self.i += 1


def run(rows, plan, cfg=None, setup=None, **kw):
    df, ts = bars(rows)
    s = Scripted(plan, setup=setup)
    res = Engine(DataFeed(prices_df=df), s, cfg or BacktestConfig(initial_cash=100_000), **kw).run()
    fills = res.to_fills_dataframe()
    keep = [c for c in ("timestamp", "side", "quantity", "price", "commission", "exit_reason") if c in fills.columns]
    return res, s, fills.select(keep).to_dicts(), ts


# ---------- M2.1 next-bar open ----------
rows = [(100, 101, 99, 100.5), (102, 103, 101, 102.5), (104, 105, 103, 104.5), (106, 107, 105, 106.5)]
res, s, fills, ts = run(rows, {0: lambda b: b.submit_order("X", 1)})
f = fills[0] if fills else {}
out["M2.1_next_bar_open"] = {"fill": f, "expected_ts": str(ts[1]), "expected_price": 102,
                             "pass": bool(f and str(f["timestamp"]) == str(ts[1]) and abs(f["price"] - 102) < 1e-12)}

# ---------- M2.2 fees both sides ----------
cfg = BacktestConfig(initial_cash=100_000, commission_type=CommissionType.PERCENTAGE, commission_rate=0.0005)
res, s, fills, ts = run(rows, {0: lambda b: b.submit_order("X", 10), 2: lambda b: b.submit_order("X", -10)}, cfg)
final_cash = float(res.to_equity_dataframe()["equity"][-1])
hand = 100_000 - 10 * 102 * 1.0005 + 10 * 106 * 0.9995
out["M2.2_fees"] = {"fills": fills, "final_equity": final_cash, "hand": hand,
                    "pass": bool(abs(final_cash - hand) < 1e-9)}

# ---------- M2.3 gap through stop ----------
rows3 = [(100, 100, 100, 100), (100, 100.5, 99.5, 100), (90, 99, 89, 97), (97, 98, 96, 97)]
res, s, fills, ts = run(rows3, {0: lambda b: b.submit_order("X", 1),
                                1: lambda b: b.submit_order("X", -1, order_type=OrderType.STOP, stop_price=95)})
sells = [x for x in fills if x["side"] == "sell"]
out["M2.3_gap_stop_order"] = {"fills": fills, "expected_sell_price": 90,
                              "pass": bool(sells and abs(sells[0]["price"] - 90) < 1e-12)}
# same gap with the StopLoss position rule (report)
res, s, fills, ts = run(rows3, {0: lambda b: b.submit_order("X", 1)},
                        setup=lambda b: b.set_position_rules(StopLoss(pct=0.05)))
out["M2.3b_gap_stoploss_rule_default"] = {"fills": fills}

# ---------- M2.4 stop and target in one bar ----------
rows4 = [(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 100.2, 99.8, 100), (100, 106, 94, 100),
         (100, 100, 100, 100)]
r_a = run(rows4, {0: lambda b: b.submit_order("X", 1)},
          setup=lambda b: b.set_position_rules(RuleChain([StopLoss(pct=0.05), TakeProfit(pct=0.05)])))
r_b = run(rows4, {0: lambda b: b.submit_order("X", 1)},
          setup=lambda b: b.set_position_rules(RuleChain([TakeProfit(pct=0.05), StopLoss(pct=0.05)])))
out["M2.4_both_hit"] = {"stop_listed_first": r_a[2], "target_listed_first": r_b[2],
                        "note": "which fills depends on rule order if the two differ"}

# ---------- M2.5 funding ----------
rows5 = [(100, 100, 100, 100)] * 5
df5, ts5 = bars(rows5)
fund = pl.DataFrame({"timestamp": [ts5[1], ts5[3]], "asset": ["X", "X"], "rate": [0.0001, 0.0001]})
s5 = Scripted({0: lambda b: b.submit_order("X", 1)})
try:
    eng5 = Engine(DataFeed(prices_df=df5), s5, BacktestConfig(initial_cash=100_000), funding_df=fund)
    res5 = eng5.run()
    pays = [{"ts": str(p.timestamp), "qty": p.quantity, "mark": p.mark_price, "rate": p.rate,
             "cash_delta": p.cash_delta} for p in eng5.funding_payments]
    final = float(res5.to_equity_dataframe()["equity"][-1])
    later = [p for p in pays if p["ts"] == str(ts5[3])]
    entry = [p for p in pays if p["ts"] == str(ts5[1])]
    out["M2.5_funding"] = {"payments": pays, "final_equity": final, "fill_ts": str(ts5[1]),
                           "charged_at_entry_bar_timestamp": bool(entry and abs(entry[0]["cash_delta"]) > 0),
                           "pass": bool(later and abs(later[0]["cash_delta"] - (-0.01)) < 1e-12)}
except Exception as exc:
    out["M2.5_funding"] = {"error": repr(exc)[:400], "pass": False}

# ---------- M2.6 control blocks ----------
res, s, fills, ts = run(rows, {0: lambda b: b.submit_order("X", 3)},
                        setup=lambda b: b.register_trading_control(OrderConstraints(max_order_quantity=1)))
out["M2.6_control"] = {"errors": s.errors, "fills": fills, "final_qty": s.log[-1]["qty"],
                       "pass": bool(not fills and s.log[-1]["qty"] == 0)}

# ---------- M2.7 multiplier 0.01 ----------
rows7 = [(30000, 30000, 30000, 30000), (30000, 30000, 30000, 30000), (31000, 31000, 31000, 31000),
         (31000, 31000, 31000, 31000)]
spec = {"X": ContractSpec(symbol="X", asset_class=AssetClass.FUTURE, multiplier=0.01)}
res, s, fills, ts = run(rows7, {0: lambda b: b.submit_order("X", 1), 1: lambda b: b.submit_order("X", -1)},
                        contract_specs=spec)
eq = res.to_equity_dataframe()["equity"]
out["M2.7_multiplier"] = {"fills": fills, "pnl": float(eq[-1] - 100_000), "expected": 10.0,
                          "pass": bool(abs(float(eq[-1]) - 100_010.0) < 1e-9)}

# ---------- M2.8 24/7 hourly year ----------
import pandas as pd  # noqa: E402

d5 = pd.read_feather(btc_path).set_index("date")
h = d5.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
h.index = h.index.tz_localize(None) if h.index.tz is not None else h.index
h = h.loc["2023-01-07 00:00":"2023-12-30 23:00"]
dfh = pl.from_pandas(h.reset_index().rename(columns={"date": "timestamp"})).with_columns(pl.lit("BTC").alias("asset"))


class BuyHold(Strategy):
    def __init__(self):
        self.done = False

    def on_data(self, timestamp, data, context, broker):
        if not self.done:
            broker.submit_order("BTC", 1)
            self.done = True


t0 = time.perf_counter()
try:
    r8 = Engine(DataFeed(prices_df=dfh), BuyHold(), BacktestConfig(initial_cash=100_000)).run()
    el = time.perf_counter() - t0
    e8 = r8.to_equity_dataframe()
    out["M2.8_247"] = {"input_bars": int(len(dfh)), "equity_rows": int(len(e8)), "first": str(e8["timestamp"][0]),
                       "last": str(e8["timestamp"][-1]), "seconds": round(el, 2),
                       "first_is_saturday": h.index[0].day_name(), "last_is_saturday": h.index[-1].day_name(),
                       "pass": bool(len(e8) == len(dfh))}
except Exception as exc:
    out["M2.8_247"] = {"error": repr(exc)[:400], "pass": False}

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:600])
