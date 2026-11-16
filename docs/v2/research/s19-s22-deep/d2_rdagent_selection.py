"""D2: replay RD-Agent's quant-loop selection step with a scripted stand-in for the LLM.

Usage (Qlib venv; from outside both repos):
    python -I d2_rdagent_selection.py RDAGENT_REPO PROVIDER_URI WORKDIR RESULTS.json [runs] [loops]

What is RD-Agent's, used as-is: its Qlib config templates (factor_template/conf_baseline.yaml
and conf_combined_factors.yaml), its default base features (ALPHA20, rdagent/utils/qlib.py),
its default segments (train 2008-2014, valid 2015-2016, test 2017-01-01..2020-08-01), its
"SOTA factors + new factor" combination with the >0.99-correlation dedup, and the metric its
feedback prompt is given (1day.excess_return_with_cost.annualized_return on the test segment).

What is scripted (the LLM's two jobs): proposing a factor (here: a random Qlib expression on
price/volume at random lags) and deciding "Replace Best Result" (here: yes iff the test-segment
annualised excess return with cost beats the current best's).

Deviations from RD-Agent, all recorded in RESULTS.md: Qlib data = the community dataset the
Qlib README points to (official data stops 2020-09-25); LightGBM num_threads 20 -> 2 (this
machine has 2 CPUs); qrun runs locally instead of in Docker.
After the loops, each run's final set (and the baseline) is scored once on 2020-08-01 ->
end of data, which no loop saw.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RD, PROVIDER, WORK, OUT = (Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))
RUNS = int(sys.argv[5]) if len(sys.argv) > 5 else 5
LOOPS = int(sys.argv[6]) if len(sys.argv) > 6 else 10
TEMPLATES = RD / "rdagent/scenarios/qlib/experiment/factor_template"
TEST = ("2017-01-01", "2020-08-01")
HELD = ("2020-08-01", None)  # None -> end of data
ARR = "1day.excess_return_with_cost.annualized_return"
KEYS = ["IC", "ICIR", "Rank IC", ARR, "1day.excess_return_with_cost.max_drawdown",
        "1day.excess_return_with_cost.information_ratio"]

def _load_alpha20():
    """RD-Agent's default base features, read from its source (rdagent/utils/qlib.py) without importing rdagent."""
    import ast
    tree = ast.parse((RD / "rdagent/utils/qlib.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ALPHA20" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("ALPHA20 not found")


ALPHA20 = _load_alpha20()


def render(template: str, test_start: str, test_end: str | None) -> str:
    import jinja2
    txt = (TEMPLATES / template).read_text()
    env = {"train_start": "2008-01-01", "train_end": "2014-12-31", "valid_start": "2015-01-01",
           "valid_end": "2016-12-31", "test_start": test_start, "test_end": test_end,
           "feature_names": str(list(ALPHA20.keys())), "feature_expressions": str(list(ALPHA20.values()))}
    out = jinja2.Template(txt).render(**env)
    out = out.replace('"~/.qlib/qlib_data/cn_data"', f'"{PROVIDER}"')
    out = re.sub(r"num_threads: \d+", "num_threads: 2", out)
    return out


def qrun(name: str, template: str, factors: pd.DataFrame | None, test_start, test_end):
    ws = WORK / name
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    (ws / "conf.yaml").write_text(render(template, test_start, test_end))
    if factors is not None:
        f = factors.sort_index().copy()
        f.columns = pd.MultiIndex.from_product([["feature"], f.columns])
        f.to_parquet(ws / "combined_factors_df.parquet", engine="pyarrow")
    t0 = time.time()
    p = subprocess.run([sys.executable, "-m", "qlib.cli.run", "conf.yaml"], cwd=ws, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ws)})
    dt = time.time() - t0
    (ws / "qrun.log").write_text(p.stdout[-20000:] + "\n" + p.stderr[-20000:])
    from mlflow.tracking import MlflowClient
    c = MlflowClient(tracking_uri=f"file:{ws}/mlruns")
    runs = [r for e in c.search_experiments() for r in c.search_runs([e.experiment_id])]
    if not runs:
        return {"error": f"no run (exit {p.returncode})", "seconds": dt}
    m = max(runs, key=lambda r: r.info.start_time).data.metrics
    res = {k: m.get(k) for k in KEYS}
    res["seconds"] = round(dt, 1)
    return res


FIELDS = ["$close", "$open", "$high", "$low", "$vwap", "$volume"]


def random_expr(rng) -> str:
    """A random price/volume expression, scale-free, using only past data (lags >= 0)."""
    w = int(rng.choice([3, 5, 10, 20, 30, 60]))
    k = int(rng.choice([1, 2, 3, 5, 10, 20]))
    a, b = rng.choice(FIELDS[:5], 2, replace=False)
    choices = [
        f"Mean({a}, {w})/{b}",
        f"Std({a}/Ref({a}, {k}) - 1, {w})",
        f"Corr({a}, Log($volume+1), {w})",
        f"Ref({a}, {k})/{b} - 1",
        f"(Max({a}, {w}) - {b})/({b}+1e-12)",
        f"(Min({a}, {w}) - {b})/({b}+1e-12)",
        f"Slope({a}, {w})/{b}",
        f"Rsquare({a}/{b}, {w})",
        f"Mean($volume, {w})/(Ref($volume, {k})+1e-12)",
        f"Corr({a}/Ref({a}, 1), {b}/Ref({b}, {k}), {w})",
        f"Resi({a}, {w})/{b}",
        f"Sum(If({a}>Ref({a}, 1), $volume, 0), {w})/(Sum($volume, {w})+1e-12)",
    ]
    return str(rng.choice(choices))


def compute_factor(expr: str, name: str, end: str) -> pd.DataFrame:
    from qlib.data import D
    df = D.features(D.instruments("csi300"), [expr], start_time="2008-01-01", end_time=end, freq="day")
    df.columns = [name]
    df = df.swaplevel().sort_index()
    df.index.names = ["datetime", "instrument"]
    return df.replace([np.inf, -np.inf], np.nan)


def too_similar(kept: pd.DataFrame | None, new: pd.DataFrame) -> bool:
    """RD-Agent's dedup: mean daily cross-sectional correlation > 0.99 with any kept factor."""
    if kept is None or kept.empty:
        return False
    j = kept.join(new, how="inner")
    mx = 0.0
    for c in kept.columns:
        s = j.groupby(level="datetime").apply(lambda x: x[c].corr(x[new.columns[0]])).mean()
        mx = max(mx, abs(s) if pd.notna(s) else 0.0)
    return mx > 0.99


def main():
    import qlib
    qlib.init(provider_uri=PROVIDER, region="cn")
    from qlib.data import D
    data_end = str(D.calendar(freq="day")[-1].date())
    WORK.mkdir(parents=True, exist_ok=True)
    state = json.loads(OUT.read_text()) if OUT.exists() else {"runs": {}}
    state["data_end"] = data_end
    if "baseline_test" not in state:
        state["baseline_test"] = qrun("baseline_test", "conf_baseline.yaml", None, *TEST)
        OUT.write_text(json.dumps(state, indent=2, default=str))
    if "baseline_heldout" not in state:
        state["baseline_heldout"] = qrun("baseline_heldout", "conf_baseline.yaml", None, HELD[0], data_end)
        OUT.write_text(json.dumps(state, indent=2, default=str))
    base_arr = state["baseline_test"][ARR]
    for r in range(RUNS):
        key = f"run{r}"
        if state["runs"].get(key, {}).get("done"):
            continue
        rng = np.random.default_rng(20261105 + r)
        run = {"loops": [], "kept": []}
        best = base_arr
        kept_df = None
        for i in range(LOOPS):
            expr = random_expr(rng)
            name = f"f_r{r}_l{i}"
            new = compute_factor(expr, name, data_end)
            if too_similar(kept_df, new):
                run["loops"].append({"loop": i, "expr": expr, "skipped": "dedup>0.99"})
                continue
            cand = new if kept_df is None else kept_df.join(new, how="outer")
            res = qrun(f"{key}_loop{i}", "conf_combined_factors.yaml", cand.loc[:TEST[1]], *TEST)
            arr = res.get(ARR)
            replace = arr is not None and best is not None and arr > best
            run["loops"].append({"loop": i, "expr": expr, "test": res, "replace_best": replace, "best_before": best})
            if replace:
                kept_df, best = cand, arr
                run["kept"].append(expr)
            state["runs"][key] = run
            OUT.write_text(json.dumps(state, indent=2, default=str))
        run["claimed_test_arr"] = best
        run["claimed_gain"] = best - base_arr
        if kept_df is None:
            run["heldout"] = state["baseline_heldout"]
        else:
            run["heldout"] = qrun(f"{key}_heldout", "conf_combined_factors.yaml", kept_df, HELD[0], data_end)
        run["heldout_gain"] = run["heldout"][ARR] - state["baseline_heldout"][ARR]
        run["done"] = True
        state["runs"][key] = run
        OUT.write_text(json.dumps(state, indent=2, default=str))
    done = [v for v in state["runs"].values() if v.get("done")]
    if done:
        cg = float(np.mean([v["claimed_gain"] for v in done]))
        hg = float(np.mean([v["heldout_gain"] for v in done]))
        state["summary"] = {"runs_done": len(done), "mean_claimed_gain": cg, "mean_heldout_gain": hg,
                            "rule_pass_heldout_ge_half_claimed": hg >= 0.5 * cg if cg > 0 else None}
    OUT.write_text(json.dumps(state, indent=2, default=str))
    print(json.dumps(state.get("summary", {}), indent=1))


if __name__ == "__main__":
    main()
