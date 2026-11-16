"""C4: Qlib's experiment recorder as a trial store: can a recorded run be edited or deleted?
Run in a venv with Qlib (repo commit):  python -I c4_qlib_recorder.py results.json
Uses a throwaway MLflow file store in a temp folder."""
import json
import sys
import tempfile

import qlib
from qlib.workflow import R


def main():
    tmp = tempfile.mkdtemp(prefix="qlib_mlruns_")
    qlib.init(provider_uri={"day": tmp}, exp_manager={
        "class": "MLflowExpManager", "module_path": "qlib.workflow.expm",
        "kwargs": {"uri": f"file:{tmp}/mlruns", "default_exp_name": "s21"}})
    out = {}
    with R.start(experiment_name="s21", recorder_name="trial_A"):
        R.log_metrics(sharpe=0.40)
        rid_a = R.get_recorder().id
    with R.start(experiment_name="s21", recorder_name="trial_B"):
        R.log_metrics(sharpe=-0.10)
        rid_b = R.get_recorder().id
    out["recorded"] = [rid_a, rid_b]
    # edit: re-open the finished trial A and overwrite its metric
    try:
        with R.start(experiment_name="s21", recorder_id=rid_a, resume=True):
            R.log_metrics(sharpe=1.90)
        rec = R.get_recorder(recorder_id=rid_a, experiment_name="s21")
        out["edit_after_finish"] = {"allowed": True, "latest_sharpe": rec.list_metrics().get("sharpe")}
    except Exception as e:
        out["edit_after_finish"] = {"allowed": False, "error": f"{type(e).__name__}: {e}"}
    # delete: remove trial B entirely
    try:
        R.get_exp(experiment_name="s21").delete_recorder(recorder_id=rid_b)
        remaining = list(R.list_recorders(experiment_name="s21").keys())
        out["delete"] = {"allowed": True, "remaining": remaining}
    except Exception as e:
        out["delete"] = {"allowed": False, "error": f"{type(e).__name__}: {e}"}
    out["verdict_append_only"] = (not out["edit_after_finish"].get("allowed")) and (not out["delete"].get("allowed"))
    with open(sys.argv[1], "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
