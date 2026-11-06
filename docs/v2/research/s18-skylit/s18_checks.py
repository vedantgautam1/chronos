"""S18 Skylit checks C1-C3 (see PREREGISTERED.md).

Usage (from outside the Skylit folders):
    python -I s18_checks.py /path/to/skylit-root results.json
where /path/to/skylit-root contains skylit-agent-kit/ and skylit-agent-lab/.

Each command runs in a child process: `python -I -c <guard>` with the repo as
working directory. The guard replaces socket connect / create_connection /
getaddrinfo with recorders that raise, then runs the command with runpy.
No Skylit key is set; HOME points at an empty temp dir so no stored key is found.
"""
import json
import os
import subprocess
import sys
import tempfile

GUARD = r'''
import json, os, runpy, socket, sys
LOG = os.environ["S18_NETLOG"]
def _rec(kind, args):
    with open(LOG, "a") as f:
        f.write(json.dumps({"kind": kind, "args": repr(args)[:200]}) + "\n")
def _connect(self, *a, **k):
    _rec("connect", a); raise OSError("S18 guard: network blocked")
def _cc(*a, **k):
    _rec("create_connection", a); raise OSError("S18 guard: network blocked")
def _gai(*a, **k):
    _rec("getaddrinfo", a); raise socket.gaierror("S18 guard: network blocked")
socket.socket.connect = _connect
socket.socket.connect_ex = _connect
socket.create_connection = _cc
socket.getaddrinfo = _gai
sys.path.insert(0, os.getcwd())
mode, target, *rest = json.loads(os.environ["S18_CMD"])
sys.argv = [target] + rest
if mode == "module":
    runpy.run_module(target, run_name="__main__", alter_sys=True)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
    runpy.run_path(target, run_name="__main__")
'''


def run_guarded(cwd, cmd, home, stdin_text=""):
    log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "S18_NETLOG": log,
        "S18_CMD": json.dumps(cmd),
        "LANG": "C.UTF-8",
        "PYTHONUTF8": "1",
    }
    p = subprocess.run(
        [sys.executable, "-I", "-B", "-c", GUARD],
        cwd=cwd, env=env, input=stdin_text, capture_output=True, text=True, timeout=300,
    )
    with open(log) as f:
        attempts = [json.loads(line) for line in f if line.strip()]
    os.unlink(log)
    return {
        "cmd": cmd,
        "exit": p.returncode,
        "net_attempts": attempts,
        "stdout_tail": p.stdout[-600:],
        "stderr_tail": p.stderr[-600:],
    }


def run_tests(cwd, home):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "LANG": "C.UTF-8", "PYTHONUTF8": "1"}
    p = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "unittest", "discover", "-s", "tests"],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=900,
    )
    tail = p.stderr.strip().splitlines()[-4:]
    return {"exit": p.returncode, "summary": tail}


def main():
    root, out = sys.argv[1], sys.argv[2]
    kit = os.path.join(root, "skylit-agent-kit")
    lab = os.path.join(root, "skylit-agent-lab")
    home = tempfile.mkdtemp(prefix="s18home_")
    res = {"C1": {}, "C2": [], "C3": []}

    res["C1"]["agent-kit"] = run_tests(kit, home)
    res["C1"]["agent-lab"] = run_tests(lab, home)

    m = "skylit_agent_kit"
    outdir = tempfile.mkdtemp(prefix="s18out_")
    kit_offline = [
        ["module", m, "doctor"],
        ["module", m, "endpoints"],
        ["module", m, "endpoint", "heatseeker.getHeatmap"],
        ["module", m, "use-case", "node-tracker"],
        ["module", m, "use-case", "price-levels"],
        ["module", m, "use-case", "flow-investigator"],
        ["module", m, "use-case", "volatility-context"],
        ["module", m, "watchlist", "--dry-run"],
        ["module", m, "sample"],
    ]
    for c in kit_offline:
        res["C2"].append({"repo": "agent-kit", **run_guarded(kit, c, home)})
    lab_offline = [
        ["path", "experiments/journal-reviewer/run.py", "--output", os.path.join(outdir, "j.md")],
        ["path", "experiments/market-brief/run.py", "--output", os.path.join(outdir, "m.md")],
        ["path", "templates/experiment/run.py"],
    ]
    for c in lab_offline:
        res["C2"].append({"repo": "agent-lab", **run_guarded(lab, c, home)})

    kit_live = [
        ["module", m, "endpoint", "heatseeker.getHeatmap", "--param", "symbols=SPY",
         "--param", "metric=gamma", "--live"],
        ["module", m, "watchlist", "--live"],
    ]
    for c in kit_live:
        res["C3"].append({"repo": "agent-kit", **run_guarded(kit, c, home)})

    c1_pass = all(v["exit"] == 0 for v in res["C1"].values())
    c2_pass = all(len(r["net_attempts"]) == 0 for r in res["C2"])
    c3_pass = all(len(r["net_attempts"]) == 0 and r["exit"] != 0 for r in res["C3"])
    res["verdict"] = {"C1": c1_pass, "C2": c2_pass, "C3": c3_pass}
    with open(out, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res["verdict"]))
    for k in ("C2", "C3"):
        for r in res[k]:
            print(k, r["repo"], " ".join(r["cmd"][1:3]), "exit", r["exit"], "net", len(r["net_attempts"]))
    for k, v in res["C1"].items():
        print("C1", k, v)


if __name__ == "__main__":
    main()
