"""MAPIE time-series coverage around a planted volatility break (S10 deep pass). Run: python -I -W ignore mapie_tests.py"""
import numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
from mapie.regression import TimeSeriesRegressor
from mapie.subsample import BlockBootstrap

def run(seed):
    rng = np.random.default_rng(seed)
    n = 2200
    sd = np.full(n, 0.01); sd[1700:2000] = 0.03                     # vol triples for 300 bars, then reverts
    r = rng.standard_normal(n) * sd
    lags = 5
    X = np.column_stack([r[lags - k - 1:n - k - 1] for k in range(lags)] +
                        [np.abs(r[lags - k - 1:n - k - 1]) for k in range(lags)])
    y = r[lags:]
    brk = 1700 - lags                                                # index of first high-vol target
    tr = slice(0, 1200); te = np.arange(1200, len(y))
    Xtr, ytr = X[tr], y[tr]
    cv = BlockBootstrap(n_resamplings=20, n_blocks=10, overlapping=False, random_state=seed)
    out = {}
    for name, method, gamma in [("EnbPI+update", "enbpi", None), ("ACI g=0.01", "aci", 0.01), ("ACI g=0.05", "aci", 0.05)]:
        m = TimeSeriesRegressor(LinearRegression(), method=method, cv=cv, agg_function="mean", n_jobs=1).fit(Xtr, ytr)
        lo = np.empty(len(te)); hi = np.empty(len(te))
        for j, t in enumerate(te):
            if j > 0:
                if method == "enbpi":
                    m.update(X[t - 1:t], y[t - 1:t])
                else:
                    m.adapt_conformal_inference(X[t - 1:t], y[t - 1:t], gamma=gamma)
            _, pis = m.predict(X[t:t + 1], confidence_level=0.95, ensemble=True, allow_infinite_bounds=True)
            lo[j], hi[j] = pis[0, 0, 0], pis[0, 1, 0]
        out[name] = (y[te] >= lo) & (y[te] <= hi)
    # trivial baseline: EWMA vol (lambda 0.94), +-1.96 sigma around 0
    var = np.empty(len(y)); var[0] = 1e-4
    for t in range(1, len(y)):
        var[t] = 0.94 * var[t - 1] + 0.06 * y[t - 1] ** 2
    out["EWMA +-1.96s"] = np.abs(y[te]) <= 1.96 * np.sqrt(var[te])
    rel = te - brk
    rows = {}
    for k, c in out.items():
        rows[k] = dict(calm_before=c[(rel >= -400) & (rel < 0)].mean(),
                       first_10=c[(rel >= 0) & (rel < 10)].mean(),
                       first_50=c[(rel >= 0) & (rel < 50)].mean(),
                       whole_300=c[(rel >= 0) & (rel < 300)].mean(),
                       after_revert_50=c[(rel >= 300) & (rel < 350)].mean())
    return pd.DataFrame(rows).T

res = [run(s) for s in range(20)]
avg = sum(res) / len(res)
print("Coverage of nominal 95% intervals, averaged over 20 seeds (vol x3 from bar 0 to 299):")
print(avg.round(3).to_string())
