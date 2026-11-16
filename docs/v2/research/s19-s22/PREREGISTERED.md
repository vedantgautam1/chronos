# S19–S22 — checks written before running (V2-D25 rule 2)

Written 2026-11-05 20:05 UTC, after reading the code and before running anything.

| Item | Repo | Commit | Licence (file) |
|---|---|---|---|
| S19 | openbq-org/OpenBB (moved from OpenBB-finance/OpenBB) | `2a392e890f6e` | Apache-2.0 |
| S20 | freqtrade/freqtrade | `0789f5d5c3e7` | GPL-3.0 |
| S21 | microsoft/qlib | `54355232463` | MIT |
| S22 | microsoft/RD-Agent | `484776c211e4` | MIT |

The workspace can't reach Kraken, Deribit, FRED, BLS or GDELT (all refused by the network allowlist), so nothing here touches live data. Qlib and RD-Agent are judged by reading: RD-Agent needs an LLM API key, Docker and Qlib's China equity dataset, none of which a check should use; nothing in Qlib could replace a step 2–5 component (see the item notes).

## F1 — does freqtrade's Kraken trade importer keep every trade?

Why it matters: freqtrade is the obvious ready-made loader for Kraken's quarterly trade CSV files (step 4 / Oceanus). Reading `trades_df_remove_duplicates` shows it drops rows with the same `(timestamp, id)`, and the CSV importer sets `id` to an empty string for every row. Several real trades can share a timestamp (one taker order filling several resting orders; BUILD_NOTES §4).

Method: synthetic Kraken-format CSV (`timestamp,price,amount`, no header), 1,000 trades, of which a known number share a timestamp with another trade, in two variants: (a) whole-second timestamps, (b) fractional-second timestamps. Run freqtrade's own `import_kraken_trades_from_csv` (exchange object stubbed so no network is needed: only `markets` is read), then read the stored trades back with freqtrade's data handler.

Rule: PASS if the stored trade count equals the input count **and** total volume matches to 1e-9 relative, in both variants. Otherwise FAIL, reporting the share of trades and volume lost.

Expectation (not the rule): FAIL in both variants, losing every same-timestamp trade after the first.

## F2 — do freqtrade's look-ahead and recursive-indicator checks work on their own fixtures?

Why it matters: these two methods (re-run the strategy on data cut off at each signal and compare; recompute indicators with different warm-up lengths and compare) are candidates for our strategy test kit (step 5). Before borrowing the method, its own tests must pass.

Method: install freqtrade 2026.10 from PyPI in its own `uv` venv; run its test files `tests/optimize/test_lookahead_analysis.py` and `tests/optimize/test_recursive_analysis.py` from the repo root.

Rule: PASS if 0 failures and 0 errors. Skips are reported.
