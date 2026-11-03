"""Known-answer tests for arch (S10 deep pass). Run: python -I arch_tests.py"""
import numpy as np
from arch.bootstrap import StationaryBootstrap, IIDBootstrap, SPA, StepM, optimal_block_length
from arch.covariance.kernel import Bartlett

rng = np.random.default_rng(20261029)

def ar1(n, phi, rng):
    e = rng.standard_normal(n)
    x = np.empty(n); x[0] = e[0] / np.sqrt(1 - phi**2)
    for t in range(1, n):
        x[t] = phi * x[t-1] + e[t]
    return x

# ---------- A. Newey-West (Bartlett) long-run variance vs hand formula ----------
x = ar1(2000, 0.5, rng)
bw = 10
lrv_arch = float(np.squeeze(Bartlett(x, bandwidth=bw).cov.long_run))
xc = x - x.mean(); n = len(x)
g = lambda k: (xc[k:] * xc[:n-k]).sum() / n
lrv_hand = g(0) + 2 * sum((1 - k / (bw + 1)) * g(k) for k in range(1, bw + 1))
print(f"A. Bartlett LRV arch={lrv_arch:.6f} hand={lrv_hand:.6f} (Bartlett weights 1-k/(bw+1))")

# ---------- B. Bootstrap CI coverage for the mean of an AR(1) (true mean 0) ----------
def coverage(boot_cls, reps=300, n=500, phi=0.5, **kw):
    hit = 0; blocks = []
    for i in range(reps):
        r = np.random.default_rng(1000 + i)
        y = ar1(n, phi, r)
        if boot_cls is StationaryBootstrap:
            b = optimal_block_length(y)["stationary"].iloc[0]; blocks.append(b)
            bs = StationaryBootstrap(b, y, seed=i)
        else:
            bs = IIDBootstrap(y, seed=i)
        lo, hi = bs.conf_int(np.mean, reps=500, method="percentile").ravel()
        hit += lo <= 0 <= hi
    return hit / reps, (np.mean(blocks) if blocks else None)

cov_sb, blk = coverage(StationaryBootstrap)
cov_iid, _ = coverage(IIDBootstrap)
print(f"B. 95% CI coverage, AR(1) phi=0.5, n=500, 300 reps: stationary={cov_sb:.3f} (mean auto block {blk:.1f}), iid={cov_iid:.3f}")
# theory: iid CI too narrow by sqrt(LRV/var) = sqrt((1+phi)/(1-phi)) = sqrt(3) -> coverage ~ 2*Phi(1.96/sqrt3)-1
from scipy.stats import norm
print(f"   theory for iid coverage: {2*norm.cdf(1.96/np.sqrt(3))-1:.3f}")

# ---------- C. SPA / StepM sign convention and planted edge ----------
T, K = 1000, 50
def make(edge, seed):
    r = np.random.default_rng(seed)
    rets = r.standard_normal((T, K)) * 0.01            # 50 zero-mean variants, 1% daily vol
    if edge:
        rets[:, 7] += 0.001                             # variant 7: +0.1%/day (~Sharpe 1.6 annualised)
    bench = np.zeros(T)                                 # benchmark = flat (cash)
    return rets, bench

rets, bench = make(True, 1)
spa = SPA(bench, -rets, reps=2000, seed=1)              # correct: losses = -returns
spa.compute()
spa_wrong = SPA(bench, rets, reps=2000, seed=1)         # wrong: returns passed as losses
spa_wrong.compute()
print(f"C1. planted edge: SPA p (consistent) correct sign={spa.pvalues['consistent']:.4f}, "
      f"WRONG sign={spa_wrong.pvalues['consistent']:.4f}")
sm = StepM(bench, -rets, size=0.05, reps=2000, seed=1); sm.compute()
print(f"C2. StepM superior models (should be [7]): {list(sm.superior_models)}")
sm_w = StepM(bench, rets, size=0.05, reps=2000, seed=1); sm_w.compute()
print(f"    StepM with wrong sign: {list(sm_w.superior_models)[:10]} (count {len(sm_w.superior_models)})")

# C3. size under the null: all 50 variants noise -> how often SPA rejects at 5%
rej = 0; ps = []
for s in range(200):
    rr, bb = make(False, 5000 + s)
    sp = SPA(bb, -rr, reps=500, seed=s); sp.compute()
    p = sp.pvalues["consistent"]; ps.append(p); rej += p < 0.05
print(f"C3. null (50 noise variants), 200 seeds: SPA reject rate at 5% = {rej/200:.3f}; "
      f"p-value quartiles {np.percentile(ps,[25,50,75]).round(3)}")

# C4. what SPA can't see: best-of-2000 searched, only best 50 handed over
r = np.random.default_rng(77)
big = r.standard_normal((T, 2000)) * 0.01
top = np.argsort(big.mean(0))[-50:]
sp = SPA(np.zeros(T), -big[:, top], reps=2000, seed=3); sp.compute()
sp_all = SPA(np.zeros(T), -big, reps=2000, seed=3); sp_all.compute()
print(f"C4. pure noise, 2000 searched: SPA p given only the top 50 = {sp.pvalues['consistent']:.4f}; "
      f"given all 2000 = {sp_all.pvalues['consistent']:.4f}")
