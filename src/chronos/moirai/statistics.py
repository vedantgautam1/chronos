"""statistics.py — the Moirai's pure-math statistical core.

Promoted from the standalone `chronos_math_probe.py` (repo root, retained as a
historical artifact). This is the module every Moira calls for anything
statistical. It is deliberately pure math:

  * No engine imports (nothing from `chronos.hephaestus`, `chronos.run`,
    `chronos.mnemosyne`).
  * No data imports (nothing from `chronos.oceanus`).
  * No I/O (no file reads, no prints, no network).
  * Only `numpy` and `scipy.stats` as dependencies.

Every function is derived from a primary source and pinned by a known-answer
test in `tests/statistics/`. The implementations are byte-identical in logic to
the probe's; if a known-answer test disagrees, the implementation is wrong until
proven otherwise against the primary paper — the numbers do not change.

SOURCES
  Lo (2002)  "The Statistics of Sharpe Ratios", FAJ 58(4)   -> Eq 9, Eq 22, Tables 1 & 2
  Newey & West (1987), Econometrica 55(3)                   -> Eq 5, Theorem 1
  Politis & Romano (1994), JASA 89(428)                     -> Sec 2, Lemma 1 Eq 5
  Bailey & López de Prado (2014), JPM 40(5)                 -> PSR, DSR (SR*) — R1 PRIMARY
        The DSR/PSR forms below match AFML (2018) §14.7; R1's four JPM
        known-answer assertions (§4.3 of the spec) pin them to the published
        worked example. R1 register status: SOURCED.
"""

import numpy as np
from scipy.stats import norm

EULER = 0.5772156649015329
HOURS_PER_YEAR = 8760.0


# =====================================================================
# METHOD IMPLEMENTATIONS  (each derived from the cited equation)
# =====================================================================

def lo_se_sharpe(sr, T):
    """Lo (2002) Eq 9.  IID standard error of the Sharpe estimator."""
    return np.sqrt((1.0 + 0.5 * sr ** 2) / T)


def lo_eta(q, rho):
    """Lo (2002) Eq 22.  Time-aggregation scale factor under AR(1) returns."""
    if abs(rho) < 1e-15:
        return np.sqrt(q)
    inner = q + 2.0 * rho / (1.0 - rho) * (q - (1.0 - rho ** q) / (1.0 - rho))
    return q / np.sqrt(inner)


def newey_west(h, m):
    """Newey & West (1987) Eq 5, scalar case.
    S_hat = Om_0 + sum_{j=1..m} w(j,m) * (Om_j + Om_j')  with w = 1 - j/(m+1).
    """
    h = np.asarray(h, float)
    h = h - h.mean()
    T = len(h)
    S = np.dot(h, h) / T                      # Omega_0
    for j in range(1, m + 1):
        w = 1.0 - j / (m + 1.0)               # modified Bartlett weight
        om = np.dot(h[j:], h[:-j]) / T        # Omega_j
        S += 2.0 * w * om                     # + Omega_j + Omega_j'
    return S


def nw_weights(m):
    return np.array([1.0 - j / (m + 1.0) for j in range(1, m + 1)])


def circ_autocov(x):
    """C_N(i), the circular autocovariances used in Politis-Romano Lemma 1."""
    x = np.asarray(x, float)
    N = len(x)
    d = x - x.mean()
    dd = np.concatenate([d, d])               # wrap the series around a circle
    return np.array([np.dot(d, dd[i:i + N]) / N for i in range(N)])


def pr_lemma1_variance(x, p):
    """Politis & Romano (1994) Lemma 1, Eq 5.
    Closed form for var(sqrt(N) * Xbar*) under the stationary bootstrap.
    Requires NO resampling -- which is what makes it a known-answer test.
    """
    N = len(x)
    C = circ_autocov(x)
    s = C[0]
    for i in range(1, N):
        s += 2.0 * (1.0 - i / N) * ((1.0 - p) ** i) * C[i]
    return s


def stationary_bootstrap_indices(N, p, rng):
    """Politis & Romano (1994) Sec 2.
    Start uniform. Each step: continue to the next observation w.p. 1-p
    (wrapping X_1 after X_N); otherwise jump to a fresh uniform draw.
    Block lengths are therefore geometric with mean 1/p.
    """
    new = rng.random(N) < p
    new[0] = True
    jump = rng.integers(0, N, N)
    seg = np.maximum.accumulate(np.where(new, np.arange(N), 0))
    return (jump[seg] + (np.arange(N) - seg)) % N


def sr_star(V, N):
    """AFML s.14.7.3.  Expected max Sharpe across N trials under H0: SR = 0.
    V is the CROSS-TRIAL VARIANCE of the estimated Sharpes, in the
    ORIGINAL (non-annualized) sampling frequency.
    """
    return np.sqrt(V) * ((1 - EULER) * norm.ppf(1 - 1.0 / N)
                         + EULER * norm.ppf(1 - 1.0 / (N * np.e)))


def psr(sr_hat, sr_bench, T, skew=0.0, kurt=3.0):
    """AFML s.14.7.2.  P(true SR > sr_bench).  sr_hat non-annualized."""
    den = np.sqrt(1.0 - skew * sr_hat + (kurt - 1.0) / 4.0 * sr_hat ** 2)
    return norm.cdf((sr_hat - sr_bench) * np.sqrt(T - 1.0) / den)


def dsr(sr_hat, T, V, N, skew=0.0, kurt=3.0, floor_at_zero=True):
    """DSR = PSR evaluated at the estimated SR*.  See the negative-SR* probe."""
    b = sr_star(V, N)
    if floor_at_zero:
        b = max(b, 0.0)
    return psr(sr_hat, b, T, skew, kurt)


# =====================================================================
# CALIBRATION SUPPORT  (used by the Phase 5 calibration harness)
# =====================================================================

def atropos_years(sr_annual, alpha=0.05, power=0.80):
    """Years of SEALED data needed to detect a true annual Sharpe with `power`.
    Derived from Lo Eq 9. The sampling frequency cancels: z ~= sqrt(years)*SR_ann.
    """
    z = norm.ppf(1 - alpha) + norm.ppf(power)
    return z ** 2 / sr_annual ** 2


def sweep_trial_variance(n_bars, cost_bps=42.0, seed=1, ann_vol=0.60):
    """Simulate the 280-point MA sweep on a ZERO-EDGE path and return
    V[{SR_n}] -- the cross-trial variance of per-bar Sharpes. This is the
    quantity the DSR actually consumes, and nothing in Chronos computes it yet.
    """
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, ann_vol / np.sqrt(HOURS_PER_YEAR), n_bars)
    px = np.exp(np.cumsum(r))
    cs = np.cumsum(np.insert(px, 0, 0.0))
    sma = lambda w: np.concatenate([np.full(w - 1, np.nan), (cs[w:] - cs[:-w]) / w])
    fasts, slows = np.arange(5, 55, 5), np.arange(60, 200, 5)   # 10 x 28 = 280
    cache = {w: sma(w) for w in set(fasts) | set(slows)}
    out = []
    for f in fasts:
        for s in slows:
            pos = np.roll(np.nan_to_num((cache[f] > cache[s]).astype(float)), 1)
            pos[0] = 0.0
            turn = np.abs(np.diff(np.insert(pos, 0, 0.0)))
            ret = pos * r - turn * (cost_bps / 1e4)
            sd = ret.std(ddof=1)
            out.append(ret.mean() / sd if sd > 0 else 0.0)
    return float(np.var(out, ddof=1))
