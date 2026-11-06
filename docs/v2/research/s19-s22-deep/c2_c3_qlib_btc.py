"""C2 + C3: can Qlib carry BTC hourly (24/7), can its backtest short, and does it stop a
feature from reading the future?

Run in a venv with Qlib (repo commit) + lightgbm, from outside the Qlib repo:
    python -I c2_c3_qlib_btc.py /path/to/qlib_btc_dir results.json
The Qlib-format BTC data (Bitstamp 1-minute -> 1-hour, 2017-01-01..2024-12-31, all
before the 1 Apr 2026 seal) is built by dump_bin.py; see RESULTS.md. Fixed toy model,
not research: features are Qlib's own Alpha158 expressions, untuned.
"""
import json
import sys
import warnings

import numpy as np
import pandas as pd
import qlib
from qlib.constant import REG_CN
from qlib.contrib.data.loader import Alpha158DL
from qlib.data import D


def ic(pred, label):
    df = pd.concat([pred, label], axis=1).dropna()
    return float(df.iloc[:, 0].corr(df.iloc[:, 1])), float(df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman")), int(len(df))


def fit_and_score(feats, names, label_expr, inst, freq):
    import lightgbm as lgb
    raw = D.features(inst, feats + [label_expr], start_time="2017-01-01", end_time="2024-12-31", freq=freq)
    raw.columns = names + ["label"]
    raw = raw.droplevel(0)
    raw = raw.replace([np.inf, -np.inf], np.nan)
    tr, va, te = raw.loc[:"2021-12-31"], raw.loc["2022-01-01":"2022-12-31"], raw.loc["2023-01-01":]
    tr = tr.dropna(subset=["label"]); va = va.dropna(subset=["label"]); te = te.dropna(subset=["label"])
    m = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=31, subsample=0.8, colsample_bytree=0.8,
                          random_state=7, verbose=-1)
    m.fit(tr[names], tr["label"], eval_set=[(va[names], va["label"])])
    p = pd.Series(m.predict(te[names]), index=te.index)
    return ic(p, te["label"]), raw


def main():
    qdir, out_path = sys.argv[1], sys.argv[2]
    res = {}
    qlib.init(provider_uri={"60min": qdir, "day": qdir}, region=REG_CN)
    inst = ["BTCUSD"]
    cal = D.calendar(start_time="2017-01-01", end_time="2024-12-31", freq="60min")
    res["calendar_bars"] = len(cal)
    res["calendar_expected_hours"] = int((pd.Timestamp("2024-12-31 23:00") - pd.Timestamp("2017-01-01")).total_seconds() // 3600 + 1)
    res["has_weekend_bars"] = bool(any(pd.Timestamp(t).dayofweek >= 5 for t in cal[:200]))
    feats, names = Alpha158DL.get_feature_config()
    res["alpha158_features"] = len(feats)
    label = "Ref($close, -2)/Ref($close, -1) - 1"
    with warnings.catch_warnings(record=True) as w_clean:
        warnings.simplefilter("always")
        (ic_p, ic_s, n), raw = fit_and_score(feats, names, label, inst, "60min")
    res["C2_ingest"] = {"rows": int(len(raw)), "feature_nan_share": float(raw[names].isna().mean().mean()),
                        "test_ic_pearson": ic_p, "test_ic_spearman": ic_s, "test_rows": n}
    # C3: add a leaked feature (next bar's close over this bar's close)
    leak = "Ref($close, -1)/$close"
    with warnings.catch_warnings(record=True) as w_leak:
        warnings.simplefilter("always")
        (ic_p2, ic_s2, n2), _ = fit_and_score(feats + [leak], names + ["LEAK_next_close"], label, inst, "60min")
    res["C3_leak"] = {"test_ic_pearson": ic_p2, "test_ic_spearman": ic_s2,
                      "warnings_about_future_refs": [str(x.message)[:160] for x in w_leak
                                                     if "future" in str(x.message).lower() or "ref" in str(x.message).lower()]}
    # same leak, but aligned with the label (the next bar's return itself): IC should jump
    leak2 = "Ref($close, -2)/Ref($close, -1) - 1"
    (ic_p3, ic_s3, _), _ = fit_and_score(feats + [leak2], names + ["LEAK_label_itself"], label, inst, "60min")
    res["C3_leak_label_aligned"] = {"test_ic_pearson": ic_p3, "test_ic_spearman": ic_s3}
    # C2 shorting: Qlib's Position model with no BTC held, then sell 1 unit
    from qlib.backtest.position import Position
    pos = Position(cash=100000.0)
    try:
        pos._sell_stock("BTCUSD", trade_val=30000.0, cost=0.0, trade_price=30000.0)
        res["C2_short"] = {"short_opened": True, "amount": pos.get_stock_amount("BTCUSD")}
    except Exception as e:
        res["C2_short"] = {"short_opened": False, "error": f"{type(e).__name__}: {e}"}
    pos.update_order = None
    pos2 = Position(cash=100000.0)
    pos2._buy_stock("BTCUSD", trade_val=30000.0, cost=0.0, trade_price=30000.0)
    try:
        pos2._sell_stock("BTCUSD", trade_val=60000.0, cost=0.0, trade_price=30000.0)
        res["C2_short_flip"] = {"went_negative": True, "amount": pos2.get_stock_amount("BTCUSD")}
    except Exception as e:
        res["C2_short_flip"] = {"went_negative": False, "error": f"{type(e).__name__}: {e}"}
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2, default=str)
    print(json.dumps(res, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
