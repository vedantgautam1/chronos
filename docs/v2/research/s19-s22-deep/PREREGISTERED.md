# S19–S22 deep pass — tests written before running (V2-D25 rule 2)

Written 2026-11-05 20:40 UTC, before any test below was run. The founder asked for every repo to be tested and fully thought through, in parts. Same repo commits as `../s19-s22/PREREGISTERED.md`.

## Environment limits (found 5 Nov, before writing this)

- **Reachable:** PyPI, npm, GitHub (repos, raw files, release downloads).
- **Blocked:** Kraken, Deribit, FRED, BLS, GDELT, Binance, Hugging Face, Docker Hub (no Docker daemon either).
- **Consequences:**
  - No live data from any provider. OpenBB is tested offline (its recorded responses, mocked HTTP).
  - Real BTC history comes from `ff137/bitstamp-btcusd-minute-data` (MIT, Bitstamp BTC/USD 1-minute, 1 Jan 2012 to 7 Jan 2025, sha256 `1be15206…a20`), entirely before our 1 Apr 2026 seal. The repo's daily-update file, which runs past the seal, is **not** downloaded or read.
  - Qlib's China datasets download from GitHub releases.
  - RD-Agent's LLM steps can't run: there is no API key here, and keys never go through a chat (V2-D41). Its non-LLM parts run; its decision rule is replayed with a scripted stand-in (D2).
- **Not research:** engine tests on real BTC data use fixed toy strategies written before running. Their profits are not evidence about any strategy and aren't trials of any Chronos hypothesis. Nothing from them may seed a research card.

## Part A — OpenBB

- **A1 — its offline tests pass.** Install `openbb-core`, the BLS, FRED, Federal Reserve, Deribit, SEC and CFTC providers and `openbb-mcp-server` (repo commit) into a `uv` venv. Run each provider's and the MCP server's unit tests. *PASS:* 0 failures and 0 errors (tests that need the network are reported as skipped or errored separately, not counted as failures of the code).
- **A2 — can OpenBB return a FRED series as it was known on a past date?** Feed the FRED series fetcher a FRED-format response containing two vintages (mocked HTTP, no network), and try every route it offers for a vintage or real-time date. *PASS:* some supported parameter returns the value as of the earlier vintage. *Expected:* FAIL.
- **A3 — OpenBB's MCP server as the wrapper for our research server (V2-D19).** Build a small FastAPI app with routes in two groups, `research/*` and `admin/*`, where every call increments a counter in the app. Serve it with `openbb-mcp --app`, connect an MCP client and test:
  - (a) default settings: are `admin/*` tools listed and callable? *Expected:* yes, by default.
  - (b) allowed categories = research only: `admin/*` must be neither listed nor callable, by direct name, `call_tool` or any pipeline/chaining tool. *PASS:* the admin counter stays at 0.
  - (c) server auth set: a client without the token must get no tool listing or call. *PASS:* refused.
- **A4 — does OpenBB place orders or touch a broker?** Search the code for order/broker/execution routes. *Expected:* none (data only).

## Part B — freqtrade

- **B1 — its full test suite passes** at the repo commit, with the core, hyperopt and plot extras installed. FreqAI/RL tests are skipped if their extras aren't installed; that's reported. *PASS:* 0 failures and 0 errors.
- **B2 — backtest fill rules, against known answers on synthetic candles** (1 pair, 1-hour candles, fee 0.1% per side, no slippage setting):
  - (a) an entry signal on candle *t* fills at the open of *t+1*. *PASS:* exact.
  - (b) fees are charged on entry and exit. *PASS:* the trade's net profit equals the hand calculation to 1e-9.
  - (c) **gap through the stop:** a long with a 5% stop where the next candle opens 10% below entry. *Realistic:* exit at that candle's open (−10%). *PASS* (realistic) if the exit is at or below the open; *FAIL* (optimistic) if at the stop price. freqtrade's docs say stop exits "happen exactly at stoploss price, even if low was lower".
  - (d) a candle that hits both stop and take-profit: which is assumed first. Reported, not pass/fail (the docs say low first).
  - (e) futures with funding: a short held across funding times with a constant positive funding rate. *PASS:* funding received matches the hand calculation to 1e-6 relative.
- **B3 — hyperopt on pure noise.** A random-walk price series (no edge), a fixed toy strategy (two MA lengths and a stop as parameters), 200 hyperopt epochs on the first half, then the best parameters on the second half. Report best in-sample vs out-of-sample profit and Sharpe, and whether freqtrade reports any adjustment for the 200 tries. *Expected:* best in-sample clearly positive, out-of-sample about zero, no adjustment shown. Reported, not pass/fail: it measures how big the uncounted-search problem is.
- **B4 — do the look-ahead tools catch small leaks?** Synthetic random walk; four toy strategies:
  - (i) clean;
  - (ii) uses `close.shift(-1)` (one bar ahead);
  - (iii) compares close with the whole-series mean (`.mean()` over all rows);
  - (iv) an EMA whose value depends on how much history was loaded (warm-up).

  *PASS:* `lookahead-analysis` flags (ii) and (iii) and clears (i); `recursive-analysis` reports a warm-up difference for (iv) and not for (i).
- **B5 — speed** (decides whether it could even serve as a screening engine): one toy MA strategy on 2 years of real BTC 5-minute candles (from the Bitstamp minute data). Wall time and memory reported; not pass/fail.
- **B6 — venues: "is it worth switching from IBKR?"** Not a code test. From each venue's official fee pages (searched; uncertainty tagged): fees and Ontario availability for every venue freqtrade supports that an Ontario resident could use, compared with IBKR's Coinbase nano futures. Decision rule written now: a venue is worth considering only if it allows **shorting** and its round-trip cost for a ~US$1,000 BTC position is **within 2× of IBKR nano futures**.

## Part C — Qlib

- **C1 — reproduce its published benchmark.** China CSI300, Alpha158 features, LightGBM (and Linear), the repo's own benchmark configs, 2017-01-01 → 2020-08-01 test period. *PASS:* IC within ±0.005 and annualised return within ±0.02 of the README table (LightGBM: IC 0.0448, ARR 0.0901; Linear: IC 0.0397, ARR 0.0692). Data version is "latest", so small differences are possible; anything outside tolerance is reported as FAIL with the numbers.
- **C2 — can it carry our market?** Load the Bitstamp BTC 1-minute data (resampled to 1-hour) into Qlib's format with a 24/7 calendar. Then compute Alpha158-style features, train LightGBM on one period and score another.
  - *PASS for ingest:* every hourly bar present and features computed without errors.
  - *PASS for shorting:* Qlib's backtest can hold a short BTC position and account for its P&L.

  *Expected:* ingest works; shorting doesn't (its exchange model is cash equities).
- **C3 — does Qlib stop a feature from using future data?** Add the feature `Ref($close, -1)/$close` (next bar's price) to an otherwise normal feature set and train. *PASS (guarded):* Qlib warns or refuses. *Expected:* no warning, and the leaked model's IC jumps.
- **C4 — the experiment recorder as a trial store.** Record two runs, then try deleting one and editing a logged metric through the recorder API. *PASS (append-only):* both refused. *Expected:* both allowed.

## Part D — RD-Agent

- **D1 — its offline tests pass.** Install `rdagent` (repo commit) in a `uv` venv; run its test suite. Tests needing an LLM key, Docker or network are reported as skipped/errored separately. *PASS:* 0 failures among the rest.
- **D2 — what its decision rule does with ideas that carry no information.** Replay the open-source default quant loop's selection step with a scripted stand-in for the LLM:
  - Each loop adds one candidate factor to the current best set (Alpha158 baseline + accepted factors).
  - The candidate is a **random expression with no real information**, built from Qlib operators on price and volume at random lags. It is a stand-in for an idea with no edge, not for an LLM's typical idea.
  - The set is retrained with RD-Agent's own combined-factor LightGBM config (train 2008–2014, valid 2015–2016, test 2017-01-01 → 2020-08-01). The candidate is kept if its **test-period** annualised excess return beats the current best's. That is the metric RD-Agent's feedback prompt is given; an LLM reading it is assumed to follow it.
  - 10 loops (its default `evolving_n`), 5 independent runs.
  - Then the final set is scored on **2020-08-01 → the end of the data**, which the loop never saw.

  *Measure:* the gain over the baseline claimed on the test period vs the gain held out. *PASS (for RD-Agent's procedure):* the held-out gain is at least half the claimed gain, on average over the 5 runs. *Expected:* FAIL. The claimed gain is positive by selection; the held-out gain is about zero or negative.
- **D3 — run time.** Report wall time per loop on this 2-CPU machine, so the founder knows what a real run costs on the Mac.

## What would change the conclusions

- B2(c) or B4 passing would make freqtrade's backtester more trustworthy than its docs suggest, but it still couldn't trade our venue.
- C1 failing would make Qlib's benchmark numbers suspect.
- D2 passing would mean RD-Agent's test-period selection does little harm at its default loop count. It would still be an LLM verdict (V2-D07).
