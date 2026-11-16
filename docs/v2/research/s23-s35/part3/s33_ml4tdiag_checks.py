"""S33 ml4t-diagnostic 0.2.1 checks M3a-M3d, M4, M5, M6 (rules: PREREGISTERED.md).

v1's DSR (src/chronos/moirai/statistics.py, our own code) is reproduced below line for line so this script
needs no Chronos import. Usage (venv with ml4t-diagnostic 0.2.1, from outside its folder):
    python -I s33_ml4tdiag_checks.py out.json
"""
import json
import sys
import time
import warnings

import numpy as np
import pandas as pd
from scipy.stats import kurtosis as sp_kurt
from scipy.stats import norm
from scipy.stats import skew as sp_skew

warnings.simplefilter("ignore")
out_path = sys.argv[1]
out = {}

from ml4t.diagnostic.evaluation.stats.deflated_sharpe_ratio import (  # noqa: E402
    deflated_sharpe_ratio, deflated_sharpe_ratio_from_statistics)
from ml4t.diagnostic.evaluation.stats.rademacher_adjustment import (  # noqa: E402
    rademacher_complexity, ras_sharpe_adjustment)
from ml4t.diagnostic.evaluation.stats.reality_check import whites_reality_check  # noqa: E402
from ml4t.diagnostic.evaluation.stats.sharpe_inference import get_variance_rescaling_factor  # noqa: E402
from ml4t.diagnostic.splitters.walk_forward import WalkForwardCV  # noqa: E402

EULER = 0.5772156649015329


# ---- v1 (copied from src/chronos/moirai/statistics.py) ----
def v1_sr_star(V, N):
    return np.sqrt(V) * ((1 - EULER) * norm.ppf(1 - 1.0 / N) + EULER * norm.ppf(1 - 1.0 / (N * np.e)))


def v1_psr(sr_hat, sr_bench, T, skew=0.0, kurt=3.0):
    den = np.sqrt(1.0 - skew * sr_hat + (kurt - 1.0) / 4.0 * sr_hat ** 2)
    return norm.cdf((sr_hat - sr_bench) * np.sqrt(T - 1.0) / den)


def v1_dsr(sr_hat, T, V, N, skew=0.0, kurt=3.0, floor_at_zero=True):
    b = v1_sr_star(V, N)
    if floor_at_zero:
        b = max(b, 0.0)
    return v1_psr(sr_hat, b, T, skew, kurt)


# ---------- M3a: N = 1 ----------
grid = [(sr, T, sk, ku) for sr in (0.02, 0.05, 0.1) for T in (250, 1000) for sk in (0.0, -0.5) for ku in (3.0, 6.0)]
rows = []
for sr, T, sk, ku in grid:
    ml = deflated_sharpe_ratio_from_statistics(observed_sharpe=sr, n_samples=T, n_trials=1, skewness=sk,
                                               excess_kurtosis=ku - 3.0).probability
    v1 = float(v1_psr(sr, 0.0, T, sk, ku))
    hand_T = float(norm.cdf(sr * np.sqrt(T) / np.sqrt(1 - sk * sr + (ku - 1) / 4 * sr**2)))   # 2014 form, T
    hand_null_var = float(norm.cdf(sr * np.sqrt(T)))   # variance evaluated at SR0 = 0 (its docstring: sharpe=threshold)
    rows.append({"sr": sr, "T": T, "skew": sk, "kurt": ku, "ml4t": ml, "v1_T_minus_1": v1, "hand_2014_T": hand_T,
                 "hand_var_at_null": hand_null_var})
out["M3a_N1"] = {"rows": rows,
                 "max_abs_ml4t_minus_hand_2014_T": max(abs(r["ml4t"] - r["hand_2014_T"]) for r in rows),
                 "max_abs_ml4t_minus_hand_var_at_null": max(abs(r["ml4t"] - r["hand_var_at_null"]) for r in rows),
                 "pass": bool(max(abs(r["ml4t"] - r["hand_2014_T"]) for r in rows) < 1e-12)}

# ---------- M3b: N > 1 ----------
rows = []
for N in (10, 100, 1000):
    for sr in (0.06, 0.1):
        V, T = 0.0004, 1000
        ml = deflated_sharpe_ratio_from_statistics(observed_sharpe=sr, n_samples=T, n_trials=N, variance_trials=V).probability
        v1 = float(v1_dsr(sr, T, V, N))
        rows.append({"N": N, "sr": sr, "V": V, "T": T, "ml4t": ml, "v1": v1,
                     "rescale_factor_used": get_variance_rescaling_factor(N)})
out["M3b_Ngt1"] = rows

# ---------- M3c: rescaling table vs Monte Carlo ----------
rng = np.random.default_rng(20261116)
mc = {}
for K in (2, 5, 10, 100, 1000):
    draws, chunk, maxes = 1_000_000, max(1, 20_000_000 // K), []
    done = 0
    while done < draws:
        m = min(chunk, draws - done)
        maxes.append(rng.standard_normal((m, K)).max(axis=1))
        done += m
    sd = float(np.concatenate(maxes).std(ddof=1))
    tab = get_variance_rescaling_factor(K)
    mc[K] = {"table": tab, "mc_sqrt_var_max": sd, "rel_err": abs(tab - sd) / sd, "ok": abs(tab - sd) / sd <= 0.005}
out["M3c_rescaling"] = {"by_K": mc, "pass": bool(all(v["ok"] for v in mc.values()))}

# ---------- M3d: size under the exact null ----------
t0 = time.perf_counter()
rng = np.random.default_rng(424242)
W, K, T = 2000, 20, 500
rej_v1 = rej_ml = rej_ml_raw = 0
for w in range(W):
    R = rng.normal(0.0, 0.01, (T, K))
    srs = R.mean(axis=0) / R.std(axis=0, ddof=1)
    b = int(np.argmax(srs))
    V = float(srs.var(ddof=1))
    rb = R[:, b]
    sk, ku = float(sp_skew(rb, bias=True)), float(sp_kurt(rb, fisher=False, bias=True))
    if v1_dsr(srs[b], T, V, K, sk, ku) > 0.95:
        rej_v1 += 1
    if deflated_sharpe_ratio_from_statistics(observed_sharpe=float(srs[b]), n_samples=T, n_trials=K,
                                             variance_trials=V, skewness=sk, excess_kurtosis=ku - 3.0).probability > 0.95:
        rej_ml += 1
    if w < 500:  # the raw-returns API is slower; first 500 worlds (reported separately, not a registered rule)
        if deflated_sharpe_ratio([R[:, j] for j in range(K)]).probability > 0.95:
            rej_ml_raw += 1
lim = 0.05 + 2 * np.sqrt(0.05 * 0.95 / W)
out["M3d_size"] = {"worlds": W, "K": K, "T": T, "limit": lim,
                   "rate_v1_2014": rej_v1 / W, "rate_ml4t_from_statistics": rej_ml / W,
                   "rate_ml4t_raw_returns_api_first_500": rej_ml_raw / 500,
                   "pass_v1": bool(rej_v1 / W <= lim), "pass_ml4t": bool(rej_ml / W <= lim),
                   "seconds": round(time.perf_counter() - t0, 1)}

# ---------- M4: RAS false positives ----------
t0 = time.perf_counter()
rng = np.random.default_rng(777)
W, N, T, delta = 500, 100, 252, 0.05
fp_doc = fp_std = 0
for w in range(W):
    R = rng.normal(0.0, 0.01, (T, N))
    # (a) as its docstring example: complexity on raw returns, annualised Sharpe
    sr_ann = R.mean(axis=0) / R.std(axis=0) * np.sqrt(252)
    c_raw = rademacher_complexity(R, random_state=w)
    if (ras_sharpe_adjustment(sr_ann, c_raw, T, N, delta=delta) > 0).any():
        fp_doc += 1
    # (b) standardised: returns / column sd, per-period Sharpe
    Z = R / R.std(axis=0)
    sr_pp = Z.mean(axis=0)
    c_std = rademacher_complexity(Z, random_state=w)
    if (ras_sharpe_adjustment(sr_pp, c_std, T, N, delta=delta) > 0).any():
        fp_std += 1
lim = delta + 2 * np.sqrt(delta * (1 - delta) / W)
out["M4_ras"] = {"worlds": W, "N": N, "T": T, "delta": delta, "limit": lim,
                 "rate_docstring_usage": fp_doc / W, "rate_standardised_usage": fp_std / W,
                 "pass_docstring_usage": bool(fp_doc / W <= lim), "pass_standardised_usage": bool(fp_std / W <= lim),
                 "seconds": round(time.perf_counter() - t0, 1)}

# ---------- M5: White's Reality Check size ----------
t0 = time.perf_counter()
rng = np.random.default_rng(99)
W, K, T, B = 500, 20, 500, 500
rej = 0
for w in range(W):
    R = rng.normal(0.0, 0.01, (T, K))
    res = whites_reality_check(np.zeros(T), R, bootstrap_samples=B, random_state=w)
    if res["p_value"] < 0.05:
        rej += 1
lim = 0.05 + 2 * np.sqrt(0.05 * 0.95 / W)
out["M5_reality_check"] = {"worlds": W, "rate": rej / W, "limit": lim, "pass": bool(rej / W <= lim),
                           "tie_rule": "p = mean(null >= statistic), no +1 (read: reality_check.py)",
                           "seconds": round(time.perf_counter() - t0, 1)}

# ---------- M6: purged walk-forward ----------
X = pd.DataFrame({"f": np.arange(1000.0)})
h = 5
viol, folds = 0, []
cv = WalkForwardCV(n_splits=5, label_horizon=h, calendar=None)
for tr, te in cv.split(X):
    tmin, tmax = int(te.min()), int(te.max())
    bad = [int(i) for i in tr if i < tmin and i + h > tmin] + [int(i) for i in tr if tmin <= i <= tmax]
    viol += len(bad)
    folds.append({"train": [int(tr.min()), int(tr.max()), int(len(tr))], "test": [tmin, tmax], "violations": len(bad)})
out["M6_purged_wf"] = {"folds": folds, "violations": viol, "pass": bool(viol == 0)}

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:900])
