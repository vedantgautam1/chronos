"""S11 deep-pass checks (see PREREGISTERED.md). Run: python -I s11_checks.py <path-to-agentlab-lab>"""
import sys, json, math, time
import numpy as np
from scipy.stats import spearmanr
sys.path.insert(0, sys.argv[1])
from agentlab import world, engine as E, memory as M

T0 = time.time()
OUT = {}

# ---------------- A. false-lesson rate under the null, 300 worlds, the book's own miner
hits = []; n_lessons = []
for s in range(5000, 5300):
    b = world.make_bars(s, edge=0.0)
    tr = E.run(b, E.BASE).select(0, 1000)
    mem = M.TradeMemory(); mem.add_many(M.episodes_from_trades(b, tr, "v0"))
    out, tests = mem.mine_lessons(min_n=30)
    hits.append(len(out) > 0); n_lessons.append(len(out))
k = int(np.sum(hits)); n = len(hits)
from agentlab.stats import wilson
OUT["A"] = dict(worlds=n, worlds_with_lesson=k, rate=k / n, wilson95=wilson(k, n), total_lessons=int(np.sum(n_lessons)))
print("A", OUT["A"], f"{time.time()-T0:.0f}s", flush=True)

# ---------------- B/C. vectorised retrieval + recommend, replicating memory.retrieve / recommend exactly
W0 = dict(regime=3.0, vol_bucket=2.0, session=1.0, trend_up=1.0, vol_ratio=2.0, junk=2.0)

def world_features(seed, edge):
    b = world.make_bars(seed, edge=edge); tr = E.run(b, E.BASE); eps = M.episodes_from_trades(b, tr, "v0")
    rng = np.random.default_rng(seed + 77)
    f = dict(day=np.array([e["ts_day"] for e in eps]), net=np.array([e["net_bps"] for e in eps]),
             regime=np.array([e["regime"] == "high_vol" for e in eps], int),
             vol_bucket=np.array([{"low": 0, "mid": 1, "high": 2}[e["vol_bucket"]] for e in eps]),
             bod=np.array([e["ts_bar"] for e in eps]), trend_up=np.array([e["trend_up"] for e in eps]),
             vr=np.array([e["vol_ratio"] for e in eps]), junk=rng.integers(0, 3, size=(len(eps), 4)))
    split = int(np.searchsorted(tr.entry_day, 1000))
    return f, split, tr.entry_day.copy()

def run_variant(f, split, entry_day, variant):
    n_all = len(f["net"]); idx = np.arange(n_all)
    sess = None
    if variant in ("published", "junk_plus", "sess2", "sess8"):
        cut = {"published": 4, "junk_plus": 4, "sess2": 2, "sess8": 8}[variant]; sess = (f["bod"] < cut).astype(int)
    use_core = variant != "junk_only"; use_junk = variant in ("junk_plus", "junk_only")
    pred = []; real = []; flag = []
    for j in range(split, n_all):
        m = (idx < j) & (f["day"] < entry_day[j] - 1)
        c = idx[m]; s = np.zeros(len(c))
        if use_core:
            s += W0["regime"] * (f["regime"][c] == f["regime"][j]) + W0["vol_bucket"] * (f["vol_bucket"][c] == f["vol_bucket"][j])
            s += W0["vol_ratio"] * np.exp(-np.abs(f["vr"][j] - f["vr"][c]) / 0.5)
        if sess is not None: s += W0["session"] * (sess[c] == sess[j])
        s += W0["trend_up"] * (f["trend_up"][c] == f["trend_up"][j])
        if use_junk: s += W0["junk"] * (f["junk"][c] == f["junk"][j]).sum(1)
        order = np.lexsort((c, -f["day"][c], -s))[:25]                    # best score, then newest, then insertion order (stable sort in the book)
        x = f["net"][c[order]]; nn = len(x)
        if nn < 15: pred.append(np.nan); flag.append("INSUFFICIENT"); real.append(f["net"][j]); continue
        mu = x.mean(); sd = x.std(ddof=1); t = mu / (sd / math.sqrt(nn)) if sd > 0 else 0.0
        pred.append(mu); flag.append("FAV" if t > 2 else "UNFAV" if t < -2 else "UNCLEAR"); real.append(f["net"][j])
    pred = np.array(pred); real = np.array(real); flag = np.array(flag); ok = ~np.isnan(pred)
    u = flag == "UNFAV"
    return dict(spearman=spearmanr(pred[ok], real[ok])[0], flagged=u.mean(), gain=real[~u].mean() - real.mean())

variants = ["published", "sess2", "sess8", "no_session", "junk_plus", "junk_only"]
res = {v: [] for v in variants}
for w in range(20):
    f, split, ed = world_features(900 + w, 1.0)
    for v in variants: res[v].append(run_variant(f, split, ed, v))
OUT["C_planted"] = {v: dict(spearman=float(np.mean([r["spearman"] for r in res[v]])), spearman_sd=float(np.std([r["spearman"] for r in res[v]])),
                            flagged=float(np.mean([r["flagged"] for r in res[v]])), skip_gain=float(np.mean([r["gain"] for r in res[v]])),
                            skip_gain_pos=float(np.mean([r["gain"] > 0 for r in res[v]]))) for v in variants}
for v in variants: print("C", v, OUT["C_planted"][v], flush=True)
ctrl = []
for w in range(20):
    f, split, ed = world_features(920 + w, 0.0); ctrl.append(run_variant(f, split, ed, "junk_plus"))
OUT["C_noise_junk_plus"] = dict(spearman=float(np.mean([r["spearman"] for r in ctrl])), skip_gain=float(np.mean([r["gain"] for r in ctrl])), flagged=float(np.mean([r["flagged"] for r in ctrl])))
print("C noise junk_plus", OUT["C_noise_junk_plus"], f"{time.time()-T0:.0f}s", flush=True)
json.dump(OUT, open(sys.argv[2], "w"), indent=1, default=float)
