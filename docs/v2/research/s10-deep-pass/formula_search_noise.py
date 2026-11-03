"""Stand-in for PySR (Julia backend not installable here): random symbolic-formula search on pure-noise returns.
Shows what any formula search finds on noise, and what honest trial counting does to it."""
import numpy as np
from scipy.stats import norm
rng = np.random.default_rng(42)
n_tr, n_te = 3000, 3000                                  # ~ 3000 bars in-sample, 3000 out-of-sample
r = rng.standard_normal(n_tr + n_te + 10) * 0.01         # pure noise: no formula can have real skill
L = {f"r{k}": np.roll(r, k) for k in range(1, 6)}        # lagged returns as inputs
unary = {"abs": np.abs, "sign": np.sign, "sq": np.square, "tanh": lambda x: np.tanh(100 * x), "id": lambda x: x}
binary = {"+": np.add, "-": np.subtract, "*": np.multiply, "max": np.maximum, "min": np.minimum}

def rand_expr(depth=0):
    if depth >= 2 or rng.random() < 0.3:
        k = rng.choice(list(L)); return k, L[k]
    if rng.random() < 0.4:
        u = rng.choice(list(unary)); s, v = rand_expr(depth + 1); return f"{u}({s})", unary[u](v)
    b = rng.choice(list(binary)); s1, v1 = rand_expr(depth + 1); s2, v2 = rand_expr(depth + 1)
    return f"({s1} {b} {s2})", binary[b](v1, v2)

y = r                                                    # target: return of bar t; inputs use only lags >= 1
tr = slice(10, 10 + n_tr); te = slice(10 + n_tr, 10 + n_tr + n_te)
def ic(f, sl):
    a, b = f[sl], y[sl]
    if a.std() == 0: return 0.0
    return np.corrcoef(a, b)[0, 1]

N = 20_000
best = (0.0, None, None)
ics = []
for _ in range(N):
    s, f = rand_expr()
    c = ic(f, tr); ics.append(c)
    if abs(c) > abs(best[0]): best = (c, s, f)
c_tr, s, f = best
c_te = ic(f, te)
t_tr = c_tr * np.sqrt(n_tr)
print(f"formulas evaluated: {N}")
print(f"best formula in-sample: {s}")
print(f"  in-sample IC = {c_tr:+.4f} (t = {t_tr:+.2f}, naive one-test p = {2*(1-norm.cdf(abs(t_tr))):.5f})")
print(f"  out-of-sample IC = {c_te:+.4f} (t = {c_te*np.sqrt(n_te):+.2f})")
# expected max |t| of N independent noise tests ~ the bar honest counting sets
emax = norm.ppf(1 - 0.5 / N)
print(f"  expected best |t| from {N} noise trials ~ {emax:.2f}; Bonferroni 5% bar = {norm.ppf(1-0.025/N):.2f}")
print(f"  share of formulas with naive |t|>1.96 in-sample: {np.mean(np.abs(np.array(ics))*np.sqrt(n_tr) > 1.96):.3f}")
