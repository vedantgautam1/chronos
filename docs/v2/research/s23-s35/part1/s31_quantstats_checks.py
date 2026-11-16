"""S31 quantstats checks Q2-Q6 (rules: PREREGISTERED.md).

Usage (venv with quantstats installed, from outside its folder):
    python -I s31_quantstats_checks.py out.json workdir
"""
import json
import os
import socket
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sps

warnings.simplefilter("ignore")
REL = 1e-9
out_path, workdir = sys.argv[1], sys.argv[2]
net = []


def _blocked(*a, **k):
    net.append(repr(a)[:120])
    raise OSError("S31 guard: network blocked")


socket.socket.connect = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked

import quantstats as qs  # noqa: E402  (imported after the guard)


def ok(a, b, rel=REL):
    return bool(abs(a - b) <= rel * max(1.0, abs(b)))


out = {}
rng = np.random.default_rng(20261105)
n, P = 1000, 365
raw = rng.standard_t(4, n)
r = pd.Series(raw / raw.std() * 0.02 + 0.0005, index=pd.date_range("2022-01-01", periods=n, freq="D"))

# ---------- Q2 textbook formulas ----------
hand = {}
hand["sharpe"] = r.mean() / r.std(ddof=1) * np.sqrt(P)
hand["sortino"] = r.mean() / np.sqrt((np.minimum(r, 0) ** 2).sum() / n) * np.sqrt(P)
hand["volatility"] = r.std(ddof=1) * np.sqrt(P)
hand["cagr"] = (1 + r).prod() ** (P / n) - 1
w = np.r_[1.0, (1 + r).cumprod().values]
hand["max_drawdown"] = (w / np.maximum.accumulate(w) - 1).min()
hand["calmar"] = hand["cagr"] / abs(hand["max_drawdown"])
got = {
    "sharpe": qs.stats.sharpe(r, periods=P),
    "sortino": qs.stats.sortino(r, periods=P),
    "volatility": qs.stats.volatility(r, periods=P),
    "cagr": qs.stats.cagr(r, periods=P),
    "max_drawdown": qs.stats.max_drawdown(r),
    "calmar": qs.stats.calmar(r, periods=P),
}
q2 = {k: {"quantstats": float(got[k]), "hand": float(hand[k]), "pass": ok(got[k], hand[k])} for k in hand}
q2["pass"] = all(v["pass"] for v in q2.values() if isinstance(v, dict))
default_cagr = qs.stats.cagr(r)
q2["note_defaults"] = {"cagr_with_default_periods_252": float(default_cagr), "cagr_with_365": float(got["cagr"]),
                       "sharpe_with_default_252": float(qs.stats.sharpe(r))}
out["Q2_formulas"] = q2

# ---------- Q3 does periods_per_year reach every metric ----------
m = qs.reports.metrics(r, periods_per_year=P, mode="full", display=False, compounded=True)
col = m.columns[0]
table = m[col]


def num(x):
    try:
        s = str(x).replace("%", "").replace(",", "").strip()
        return float(s)
    except Exception:
        return None


direct = {
    "Sharpe": qs.stats.sharpe(r, periods=P),
    "Sortino": qs.stats.sortino(r, periods=P),
    "Smart Sharpe": qs.stats.smart_sharpe(r, periods=P),
    "Smart Sortino": qs.stats.smart_sortino(r, periods=P),
    "Calmar": qs.stats.calmar(r, periods=P),
    "Prob. Sharpe Ratio": qs.stats.probabilistic_sharpe_ratio(r, periods=P),  # report gives fractions when display=False (corrected after first run)
}
pct = {"CAGR﹪": qs.stats.cagr(r, periods=P), "Volatility (ann.)": qs.stats.volatility(r, periods=P)}  # fractions, see above
q3 = {}
for label, val in list(direct.items()) + list(pct.items()):
    key = next((k for k in table.index if k.strip().startswith(label.replace("﹪", "").strip())), None)
    if key is None:
        q3[label] = {"in_report": False}
        continue
    rep = num(table[key])
    tol = 0.006 if label in pct or label == "Prob. Sharpe Ratio" else 0.006
    q3[label] = {"report": rep, "direct_365": round(float(val), 4), "match": rep is not None and abs(rep - val) <= tol}
q3["pass"] = all(v.get("match", False) for v in q3.values() if isinstance(v, dict) and v.get("in_report", True))
q3["report_rows_annualised_like"] = [k for k in table.index if any(s in k for s in ("Sharpe", "Sortino", "CAGR", "Volatility", "Calmar", "Omega"))]
out["Q3_periods_propagation"] = q3

# ---------- Q4 PSR ----------
sr = qs.stats.sharpe(r, periods=P, annualize=False)
g3 = qs.stats.skew(r)
g4 = qs.stats.kurtosis(r) + 3
psr_hand = sps.norm.cdf(sr / np.sqrt((1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) / (n - 1)))
psr_qs = qs.stats.probabilistic_sharpe_ratio(r, periods=P)
g3p = sps.skew(r, bias=True)
g4p = sps.kurtosis(r, fisher=False, bias=True)
psr_pop = sps.norm.cdf(sr / np.sqrt((1 - g3p * sr + (g4p - 1) / 4 * sr ** 2) / (n - 1)))
out["Q4_psr"] = {"quantstats": float(psr_qs), "formula_same_estimators": float(psr_hand), "pass": ok(psr_qs, psr_hand),
                 "formula_population_moments": float(psr_pop), "abs_diff_vs_population": float(abs(psr_qs - psr_pop)),
                 "benchmark_sharpe": "0 (tests SR > 0; no deflation for number of trials)"}

# ---------- Q5 offline HTML ----------
html = os.path.join(workdir, "tearsheet.html")
try:
    qs.reports.html(r, output=html, periods_per_year=P, title="S31 offline test")
    out["Q5_html_offline"] = {"written": os.path.exists(html), "bytes": os.path.getsize(html) if os.path.exists(html) else 0,
                              "network_attempts": len(net), "pass": os.path.exists(html) and len(net) == 0}
except Exception as exc:
    out["Q5_html_offline"] = {"error": repr(exc)[:300], "network_attempts": len(net), "pass": False}

# ---------- Q6 hourly ----------
rh = pd.Series(rng.normal(0.00002, 0.004, 2 * 8760), index=pd.date_range("2023-01-01", periods=2 * 8760, freq="h"))
mh = qs.reports.metrics(rh, periods_per_year=8760, mode="full", display=False)
th = mh[mh.columns[0]]
sh_key = next(k for k in th.index if k.strip() == "Sharpe")
direct_h = rh.mean() / rh.std(ddof=1) * np.sqrt(8760)
daily = (1 + rh).resample("D").prod() - 1
direct_daily_365 = daily.mean() / daily.std(ddof=1) * np.sqrt(365)
start_end = [k for k in th.index if "Start" in k or "End" in k or "Period" in k]
out["Q6_hourly"] = {"report_sharpe": num(th[sh_key]), "hourly_sqrt8760": round(float(direct_h), 4),
                    "daily_resampled_sqrt365": round(float(direct_daily_365), 4),
                    "uses_hourly_returns_as_given": abs(num(th[sh_key]) - direct_h) < 0.006,
                    "period_rows": {k: str(th[k]) for k in start_end}}
out["network_attempts_total"] = len(net)

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:600])
