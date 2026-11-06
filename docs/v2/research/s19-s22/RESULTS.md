# S19–S22 — results (5 Nov 2026)

Rules: `PREREGISTERED.md` (committed in `4ea202b` before anything ran). Environment: Python 3.13, freqtrade installed from the repo at commit `0789f5d` (reports itself as `2026.11-dev`) into its own `uv` venv with its core, hyperopt, plot and test requirements. Deviation: the pre-registration said "freqtrade 2026.10 from PyPI"; I installed the cloned commit instead so the test files match the code they test. The full dev requirements (FreqAI, reinforcement learning, docs) were not installed: the install timed out and nothing checked here needs them.

| Check | Rule | Result | Verdict |
|---|---|---|---|
| **F1** freqtrade's Kraken trade-CSV importer keeps every trade | Stored count = input count and volume equal, in both variants | (a) whole-second timestamps: 519 of 1,000 trades and 53.8% of volume lost. (b) fractional (µs) timestamps: 482 of 1,000 trades and 48.7% of volume lost | **FAIL** |
| **F2** freqtrade's look-ahead and recursive-indicator tests pass | 0 failures, 0 errors | 27 passed | **PASS** |

## F1 in detail

Every trade lost was a trade that shared its exact timestamp with an earlier one; no other trade was lost [Certain — run]. The cause is in freqtrade's code [Certain — read]:
- the CSV importer sets every trade's `id` to an empty string (Kraken's files have no id column);
- `trades_df_remove_duplicates` drops rows with the same `(timestamp, id)`, both when importing and again when loading;
- timestamps are stored as integer milliseconds, so trades less than 1 ms apart also collide (exploratory variant (c), not part of the rule: 519 of 1,000 lost, identical to (a)).

How much this loses on real Kraken data depends on how often real trades share a timestamp at the file's resolution, which this workspace can't check (Kraken is unreachable from here) [Guessing]. One taker order filling several resting orders prints several trades at one timestamp (BUILD_NOTES §4), so the loss is concentrated in the biggest, most aggressive orders: exactly the ones order-flow and volume work care about. If Kraken's files carry whole-second timestamps, every BTC trade after the first in each second would be dropped.

The synthetic share of same-timestamp trades (~50%) was set by my generator, not measured; it shows the mechanism, not the real loss rate.

## F2 in detail

The look-ahead test fixture is a strategy whose entries use `close.shift(-10)` (ten candles into the future) against a clean `shift(10)` version; the analysis flags the first and clears the second [Certain — read + run]. That's a deliberately blatant leak: it shows the method works, not how small a leak it can find.

## Not tested, and why

- **OpenBB:** every data source it wraps is outside the network allowlist. Its relevant behaviour was confirmed by reading the code (item notes).
- **Qlib:** nothing in it is a candidate for build steps 2–5.
- **RD-Agent:** needs an LLM API key, Docker and Qlib's China equity data. Its decision step was read in the code.
