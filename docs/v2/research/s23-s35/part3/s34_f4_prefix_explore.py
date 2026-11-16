"""S34 FinRL F4 follow-up (EXPLORATORY, written after the F4 result; not pre-registered).

F4 (cut at day 600, compared on days <= 600) passed, but it can't see a leak *inside* the cut window:
FeatureEngineer.preprocess_data ends with df.ffill().bfill() on a frame sorted by (date, tic).
This prefix test computes features on data up to day t only and compares row t with the full-data row t,
for several early and late t. Any difference means row t used data from after t.

Usage: python -I s34_f4_prefix_explore.py out.json
"""
import contextlib
import io
import json
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
from finrl import config  # noqa: E402
from finrl.meta.preprocessor.preprocessors import FeatureEngineer  # noqa: E402

rng = np.random.default_rng(20261116)  # same data as s34_finrl_checks.py F4
days = pd.bdate_range("2020-01-01", periods=800).strftime("%Y-%m-%d")
rows = []
for tic, p0 in (("AAA", 100.0), ("BBB", 50.0), ("CCC", 80.0)):
    c = p0 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
    h = c * (1 + rng.uniform(0, 0.02, len(days)))
    lo = c * (1 - rng.uniform(0, 0.02, len(days)))
    o = c * (1 + rng.normal(0, 0.005, len(days)))
    rows.append(pd.DataFrame({"date": days, "tic": tic, "open": o, "high": h, "low": lo, "close": c,
                              "volume": rng.uniform(1e5, 1e6, len(days))}))
raw = pd.concat(rows).sort_values(["date", "tic"]).reset_index(drop=True)
fe = FeatureEngineer(use_technical_indicator=True, tech_indicator_list=config.INDICATORS, use_vix=False,
                     use_turbulence=True, user_defined_feature=True)
with contextlib.redirect_stdout(io.StringIO()):
    full = fe.preprocess_data(raw.copy())
cols = config.INDICATORS + ["turbulence", "daily_return"]
full_i = full.set_index(["date", "tic"])[cols]
res = {}
for t in (0, 1, 5, 13, 29, 30, 59, 60, 100, 251, 252, 253, 254, 255, 300, 599):
    # turbulence needs > 252 days of history, so earlier prefixes are computed without it (its column skipped)
    use_t = t > 252
    fe_t = fe if use_t else FeatureEngineer(use_technical_indicator=True, tech_indicator_list=config.INDICATORS,
                                            use_vix=False, use_turbulence=False, user_defined_feature=True)
    cols_t = cols if use_t else [c for c in cols if c != "turbulence"]
    with contextlib.redirect_stdout(io.StringIO()):
        pre = fe_t.preprocess_data(raw[raw.date <= days[t]].copy())
    last = pre[pre.date == days[t]].set_index(["date", "tic"])[cols_t]
    ref = full_i.loc[last.index, cols_t]
    d = (last - ref).abs()
    # NaN-aware: a value that is NaN on one side only also counts as a difference (first version missed this)
    nan_mismatch = last.isna() ^ ref.isna()
    bad = {}
    for c in cols_t:
        if (d[c] > 1e-9).any() or nan_mismatch[c].any():
            bad[c] = {"max_abs_diff": float(d[c].max()) if d[c].notna().any() else None,
                      "prefix_values": [None if pd.isna(v) else float(v) for v in last[c]],
                      "full_values": [None if pd.isna(v) else float(v) for v in ref[c]]}
    res[int(t)] = bad
# cross-ticker fill: on day 0, does any indicator of one ticker equal another ticker's value?
d0 = full[full.date == days[0]].set_index("tic")[cols]
cross = {}
for c in cols:
    vals = d0[c].to_dict()
    cross[c] = vals
out = {"prefix_rows_differing_from_full": res,
       "n_t_checked": len(res), "n_t_with_any_difference": sum(1 for v in res.values() if v),
       "day0_values_by_ticker": cross}
with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "day0_values_by_ticker"}, default=str)[:2500])
print(json.dumps(cross, default=str)[:1500])
