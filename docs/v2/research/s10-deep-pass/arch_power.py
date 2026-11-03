import numpy as np
from arch.bootstrap import SPA, StepM
T,K=1000,50
r=np.random.default_rng(1); rets=r.standard_normal((T,K))*0.01; rets[:,7]+=0.001
t=rets.mean(0)/rets.std(0,ddof=1)*np.sqrt(T)
print("seed1: t of planted variant 7 =",round(t[7],2),"| best noise t =",round(np.delete(t,7).max(),2),"| worst t =",round(t.min(),2), "argmin",t.argmin())
# power across seeds, single-strategy t-test vs SPA vs StepM
hits_spa=hits_stepm=hits_t=0; N=100
for s in range(N):
    r=np.random.default_rng(9000+s); x=r.standard_normal((T,K))*0.01; x[:,7]+=0.001
    sp=SPA(np.zeros(T),-x,reps=500,seed=s); sp.compute(); hits_spa+=sp.pvalues['consistent']<0.05
    sm=StepM(np.zeros(T),-x,size=0.05,reps=500,seed=s); sm.compute(); hits_stepm+= 7 in list(sm.superior_models)
    tt=x[:,7].mean()/x[:,7].std(ddof=1)*np.sqrt(T); hits_t+= tt>1.645
print(f"power over {N} seeds: one pre-registered strategy t-test={hits_t/N:.2f}, SPA over 50={hits_spa/N:.2f}, StepM flags variant 7={hits_stepm/N:.2f}")
