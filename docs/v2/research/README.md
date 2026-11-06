# Research check scripts (content analysis)

Scripts used to test claims made by the content we analysed (items S10 onward). Each folder holds the code that produced the numbers quoted in the Project notes (`claude/item-analyses-2.md` for S10–S12, `claude/item-analyses-3.md` for S13 onward), so anyone can rerun them instead of trusting the summary.

**These are not v2 code.** Nothing here is imported by Chronos. They are synthetic-data experiments.

Rules followed (V2-D25): pass/fail rules written down **before** running (`PREREGISTERED.md` where present), no seed shopping, results reported whichever way they fell.

| Folder | Item | What it tests | Needs |
|---|---|---|---|
| `s10-deep-pass/` | S10: QuantFrame "4 GitHub repos" (arch, tick, MAPIE, PySR) | arch's Newey–West, bootstrap coverage, SPA/StepM size, power and blind spot; tick's Hawkes recovery and seasonality trap; MAPIE coverage after a volatility break; a formula-search stand-in for PySR | `pip install arch tick numpydoc mapie scikit-learn` (each in its own environment) |
| `s11-deep-pass/` | S11: Arwaz Az, "Self-Improving AI Trading Agent" Part 1 (memory) | (A) false-lesson rate of the corrected lesson miner over 300 no-structure worlds; (C) how much of the memory's benefit survives when its lookup keys are mis-specified or diluted | The author's `agentlab-lab` code pack (Part 1 or later) |
| `s12-deep-pass/` | S12: same series, Part 2 (experiment ledger) | (P-3 → V2-D31) false finds when a search is split across families; (P-4 → V2-D32) a change check with and without "the candidate must make money" | The author's `agentlab-lab` code pack (Part 2 or later) |
| `s13-s17-deep-pass/` | S13–S17: same series, Parts 3–7 (evaluation gate, agent team, loop, safety layer, full system) | (K0) every author figure reproduced; (K1) forged promotion evidence; (K2) sealed-look enforcement and re-look cost; (K3) risk-engine bypass and size-bug headroom; (K4) why the break-even monitor detected less | The full `agentlab-lab` pack (`agentlab-code.zip`, Part 7 folder) |
| `s18-skylit/` | S18: SkylitAI's three public repos (`skylit-mcp`, `skylit-agent-kit`, `skylit-agent-lab`) | (C1) their test suites pass; (C2) the offline modes make no network call; (C3) live mode without a key stays off the network. The service itself (data, scores) was not tested: it needs a paid key | Clones of the three repos (MIT; commits in `PREREGISTERED.md`); standard library only |
| `s19-s22/` | S19 OpenBB, S20 freqtrade, S21 Qlib, S22 RD-Agent | (F1) freqtrade's Kraken trade-CSV importer drops every trade sharing a timestamp; (F2) freqtrade's look-ahead and warm-up tests pass on its own fixtures. OpenBB, Qlib and RD-Agent judged by reading (their data and LLM back-ends are unreachable from here) | A `uv` venv with freqtrade (repo commit in `PREREGISTERED.md`) and its core + test requirements |
| `s19-s22-deep/` | Deep pass on S19–S22 (founder asked for everything tested): A OpenBB (tests, FRED vintages, MCP server lockdown), B freqtrade (suite, fill rules, hyperopt on noise, leak tools, speed, venues), C Qlib (benchmark reproduction, BTC 24/7 + shorting, future-data guard, recorder), D RD-Agent (tests, selection-rule replay, run time) | Separate `uv` venvs per repo (commits in `../s19-s22/PREREGISTERED.md`); Bitstamp BTC/USD minute data (`ff137/bitstamp-btcusd-minute-data`, MIT, to 7 Jan 2025, before the seal); Qlib's official and community China datasets. Full detail and deviations in `RESULTS.md` |

## How to rerun S11/S12 (S13–S17: see the end)

The author's code pack is **not committed here** (its licence isn't stated). It is in the founder's Google Drive folder "SERIES: Self Improving AI". Then:

```
uv venv venv && . venv/bin/activate && uv pip install numpy scipy numba pytest
unzip agentlab-lab-part2.zip -d /some/separate/folder
python -I s11_checks.py /some/separate/folder/agentlab-lab s11_results.json
python -I s12_checks.py /some/separate/folder/agentlab-lab s12_results.json
```

Run from outside the unpacked folder, with `python -I`, so nothing in it is imported by accident. Runtimes: S11 ~30 s, S12 ~45 s (numba compiles on first run). Results are deterministic (fixed seeds); a rerun should match the committed `*_results.json` exactly on the same library versions (checked with Python 3.13, numpy 2.5.4, scipy 1.18.1, numba 0.68.1).

## How to rerun S13–S17

Needs the full pack (`agentlab-code.zip` in the Part 7 folder of the same Drive folder), same environment as above.

```
unzip agentlab-code.zip -d /some/separate/folder
python -I s13_checks.py /some/separate/folder/agentlab-lab s13_results.json            # K1-K4, ~3 min
python -I compare_k0.py author_results_pN.json rerun_results_pN.json                    # K0, after rerunning the author's scripts
```

K0 means: copy the pack's shipped `figs/results_p3.json` … `results_p7.json` aside first (the author's scripts overwrite them), rerun `scripts/p3_experiments.py` … `p7_experiments.py` at the author's settings (Part 3 `W=60`, `p3_decoy.py` `N=200`; Part 4 `W=150`; Part 5 `W=150`; Part 6 `W=100`; Part 7 `STAGES=cal,life,loc,example W=300 NCAL=500`, then `STAGES=gates`), then compare file by file. `PREREGISTERED.md` was written before K1–K4 ran.

## How to rerun S18

```
git clone https://github.com/SkylitAI/skylit-agent-kit /some/folder/skylit-agent-kit
git clone https://github.com/SkylitAI/skylit-agent-lab /some/folder/skylit-agent-lab
python -I s18_checks.py /some/folder s18_results.json      # C1-C3, ~15 s, no key, no network
```

Check out the commits listed in `PREREGISTERED.md` first. C1 as pre-registered uses `-I`, which can't import a repo's own package; `RESULTS.md` gives the documented rerun (167 + 345 tests OK).

## How to rerun S19–S22

```
git clone https://github.com/freqtrade/freqtrade /some/folder/freqtrade   # commit in PREREGISTERED.md
uv venv venv && . venv/bin/activate
uv pip install -r /some/folder/freqtrade/requirements.txt -r /some/folder/freqtrade/requirements-hyperopt.txt -r /some/folder/freqtrade/requirements-plot.txt pytest pytest-asyncio pytest-mock pytest-xdist pytest-cov pytest-random-order pytest-timeout time-machine
uv pip install --no-deps -e /some/folder/freqtrade
python -I s20_kraken_csv_check.py s20_results.json                        # F1, a few seconds, no network
(cd /some/folder/freqtrade && python -m pytest -q tests/optimize/test_lookahead_analysis.py tests/optimize/test_recursive_analysis.py)   # F2
```
