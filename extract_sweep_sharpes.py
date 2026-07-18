"""Extract per-bar Sharpe ratios for the 280-point MA-crossover sweep.

Reads records/runs.jsonl, selects "run"-type records with
5 <= trial_index <= 284 and status == COMPLETED, computes each run's
per-bar Sharpe (mean/std, ddof=1) from its own result.returns series,
and saves the 280 Sharpes to sweep_sharpes.npy.
"""

import json
from pathlib import Path

import numpy as np

RECORDS_FILE = Path(__file__).resolve().parent / "records" / "runs.jsonl"
OUT_FILE = Path(__file__).resolve().parent / "sweep_sharpes.npy"

LO, HI = 5, 284


def main() -> None:
    with open(RECORDS_FILE) as f:
        lines = [json.loads(line) for line in f]

    selected = [
        r for r in lines
        if r["type"] == "run"
        and r.get("status") == "COMPLETED"
        and LO <= r.get("trial_index", -1) <= HI
    ]

    sharpes = []
    zero_std_trials = []  # flagged, not silently dropped

    for r in selected:
        pairs = r["result"]["returns"]
        values = np.array([v for _ts, v in pairs], dtype=float)
        mean = values.mean()
        std = values.std(ddof=1)
        if std == 0:
            zero_std_trials.append(r["trial_index"])
        sharpes.append(mean / std)  # as specified: mean/std, ddof=1

    sharpes = np.array(sharpes, dtype=float)
    np.save(OUT_FILE, sharpes)

    if zero_std_trials:
        print(f"WARNING: {len(zero_std_trials)} trial(s) had std==0 "
              f"(mean/std -> nan or inf): {zero_std_trials}")

    print(f"count : {sharpes.size}")
    print(f"mean  : {sharpes.mean()}")
    print(f"var (ddof=1): {np.var(sharpes, ddof=1)}")
    print(f"saved to: {OUT_FILE}")


if __name__ == "__main__":
    main()
