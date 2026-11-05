# Research check scripts (content analysis)

Scripts used to test claims made by the content we analysed (items S10 onward). Each folder holds the code that produced the numbers quoted in the Project notes `claude/item-analyses-2.md`, so anyone can rerun them instead of trusting the summary.

**These are not v2 code.** Nothing here is imported by Chronos. They are synthetic-data experiments.

Rules followed (V2-D25): pass/fail rules written down **before** running (`PREREGISTERED.md` where present), no seed shopping, results reported whichever way they fell.

| Folder | Item | What it tests | Needs |
|---|---|---|---|
| `s10-deep-pass/` | S10: QuantFrame "4 GitHub repos" (arch, tick, MAPIE, PySR) | arch's Newey–West, bootstrap coverage, SPA/StepM size, power and blind spot; tick's Hawkes recovery and seasonality trap; MAPIE coverage after a volatility break; a formula-search stand-in for PySR | `pip install arch tick numpydoc mapie scikit-learn` (each in its own environment) |
| `s11-deep-pass/` | S11: Arwaz Az, "Self-Improving AI Trading Agent" Part 1 (memory) | (A) false-lesson rate of the corrected lesson miner over 300 no-structure worlds; (C) how much of the memory's benefit survives when its lookup keys are mis-specified or diluted | The author's `agentlab-lab` code pack (Part 1 or later) |
| `s12-deep-pass/` | S12: same series, Part 2 (experiment ledger) | (P-3 → V2-D31) false finds when a search is split across families; (P-4 → V2-D32) a change check with and without "the candidate must make money" | The author's `agentlab-lab` code pack (Part 2 or later) |

## How to rerun S11/S12

The author's code pack is **not committed here** (its licence isn't stated). It is in the founder's Google Drive folder "SERIES: Self Improving AI". Then:

```
uv venv venv && . venv/bin/activate && uv pip install numpy scipy numba pytest
unzip agentlab-lab-part2.zip -d /some/separate/folder
python -I s11_checks.py /some/separate/folder/agentlab-lab s11_results.json
python -I s12_checks.py /some/separate/folder/agentlab-lab s12_results.json
```

Run from outside the unpacked folder, with `python -I`, so nothing in it is imported by accident. Runtimes: S11 ~30 s, S12 ~45 s (numba compiles on first run). Results are deterministic (fixed seeds); a rerun should match the committed `*_results.json` exactly on the same library versions (checked with Python 3.13, numpy 2.5.4, scipy 1.18.1, numba 0.68.1).
