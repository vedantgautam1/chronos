# S19–S22 deep pass — results (5 Nov 2026)

Rules: `PREREGISTERED.md` (committed in `057184b` before any of this ran). Raw outputs are in the `*_results.json` files next to this one. Every deviation from the pre-registration is listed under the test it affects.

## Summary table

| Test | Rule | Result | Verdict |
|---|---|---|---|
| **A1** OpenBB offline tests | 0 failures/errors | FRED 1,316 tests, 0 failed. MCP server 593, 0 failed. Core 2,707, 2 failed. Deribit 766, 1 failed + 1 file that won't load. SEC 2,587, 24 failed/errored. CFTC 1,225, 4 failed. Federal Reserve 2,347, 13 failed | **FAIL** (see detail) |
| **A2** FRED as known on a past date | A supported parameter returns the older vintage | Documented parameters: no. An **undocumented** pass-through (`realtime_start` = `realtime_end`) does; a date range silently returns the latest vintage | **FAIL** (documented); works undocumented |
| **A3** MCP server deny-by-default | (b) admin routes unreachable with an allow-list; (c) no token → refused | (a) Default: admin routes listed and called. (b) Allow-list: admin unreachable by name, `call_tool` or `run_pipeline` (0 hits). (c) No token: refused | **PASS** (b, c) |
| A3b (exploratory) tools outside the allow-list | — | With the allow-list set, a client could still **write files on the server** (`install_skill`), **make the server fetch a URL it chose** (`openbb_dispatch`'s `server_url`), and reach **~54 KB of OpenBB commands** outside the allow-list. `default_skills_dir=""` + `enable_cli_tools=False` closes all three | Finding |
| **A4** order/broker code in OpenBB | Expected none | None (data only) | As expected |
| **B1** freqtrade full suite | 0 failures/errors | 4,710 passed, 7 failed, 20 skipped (FreqAI excluded). 6 failures are environment; 1 unexplained (scheduler test) | **FAIL** (6 environment, 1 unexplained) |
| **B2** fill rules | (a), (b), (e) exact; (c) realistic | (a) next-bar open: exact. (b) fees: exact to 1e-16. (c1) whole candle below the stop: fills at the open (realistic). **(c2) opens below the stop, then trades back above it: fills at the stop price, booking −5% for a real −10%**. (d) stop assumed before take-profit. (e) funding: exact; funding stamps at both entry and exit times are charged | **PASS** except **(c2) FAIL** |
| **B3** hyperopt on pure noise | Report | 0.1% fee: best of 200 in-sample Sharpe 0.18 → out-of-sample −1.79. Zero fee (exploratory): 2.02 → −0.62. No adjustment for the 200 tries anywhere in its output | Reported |
| **B4** look-ahead tools on small leaks | Flag (ii), (iii); clear (i); warm-up flagged for (iv) | Clean: not flagged. One bar ahead: flagged. Whole-series mean: flagged (16 of 20 entries) after a fixture fix (see below). EMA-200 warm-up: flagged; SMA: not | **PASS** |
| **B5** speed | Report | 210,528 five-minute candles (2 years): 3.6 s per backtest, 0.6 GB RAM | Reported |
| **B6** venues | Shorting **and** round trip within 2× IBKR nano | No supported venue usable from Ontario meets either condition (detail below) | **FAIL** (not worth switching) |
| **C1** Qlib benchmark | IC ±0.005 and ARR ±0.02 of the README | LightGBM: IC 0.0468 (0.0448), ARR 0.0807 (0.0901) → within. Linear: IC 0.0388 (0.0397) within; **ARR 0.0964 (0.0692) outside** | **PASS** LightGBM, **FAIL** Linear |
| **C2** BTC 24/7 + shorting | Ingest complete; short allowed | Ingest: every hourly bar (70,128) and all 158 Alpha158 features computed. Shorting: **refused** (`KeyError` with no position; `ValueError` when selling more than held) | Ingest **PASS**, shorting **FAIL** |
| **C3** future data in features | Warn or refuse | No warning. A next-bar feature raised test IC 0.032 → 0.052; a feature equal to the label → 0.997 | **FAIL** (no guard) |
| **C4** recorder append-only | Edit and delete refused | Both allowed (Sharpe 0.40 rewritten to 1.90; a run deleted) | **FAIL** |
| **D1** RD-Agent offline tests | 0 failures | 131 passed, 1 failed (an optional dependency's import) | **FAIL** (1, environment-type) |
| **D2** RD-Agent's selection rule | Held-out gain ≥ ½ claimed gain | 10 random no-information factors per run, 5 runs: the rule kept 3.8 per run. Claimed gain on the test period **+4.6 points** of annualised excess return (4.4% → ~9.0%); held-out gain **+0.4 points** (range −0.9 to +2.2). 91% of the claimed improvement did not survive | **FAIL** |
| **D3** run time | Report | ~82 s per loop (one Qlib train + backtest) on 2 CPUs, before any LLM time; ~14 min for a 10-loop run | Reported |

## Detail and deviations

### A1 — OpenBB tests
- Every package was installed from the repo commit with its own `dev` test group.
- The BLS provider could not be built from source: its build step downloads from `download.bls.gov`, which is blocked here. It was installed from PyPI (2.0.0) and isn't in A1.
- Each package's tests were run from its own folder with `-o asyncio_default_fixture_loop_scope=function`, which its pytest-asyncio version requires.
- Failures, by kind:
  - **The parts we might use pass:** FRED 0 failures; MCP server 0 failures; core 2 of 2,707. One core failure is a documentation-grouping order that depends on which extensions are installed; the other needs the network.
  - **Deribit:** its router test imports `futures.curve`, which doesn't exist in the code at this commit; one widget-contract test also fails. These are test/code mismatches at the repo head, not network [Certain — read].
  - **SEC, CFTC, Federal Reserve:** mostly the network (blocked sites), plus test/code mismatches in the Fed's regional routers (functions the tests expect but the code doesn't define).

### A2 — FRED vintages
- OpenBB's query models accept extra fields (`extra="allow"`), and the FRED fetcher forwards them into the request URL. Passing `realtime_start=realtime_end=2020-02-15` returned the first-release value (100.0) [Certain — run, fake FRED server].
- With a *range* of real-time dates, FRED returns one row per vintage. OpenBB's fetcher keeps only one row per date (dictionary overwrite), so the result silently becomes the *latest* vintage in the range [Certain — run].
- **Correction to the S19 note:** it said there was "no query parameter to ask for an older vintage". There is none *documented*; the undocumented pass-through works for single dates only.
- The fake server's behaviour imitates FRED's documented real-time parameters [Likely — not checked against the live API from here].

### A3 / A3b — MCP server
- Test app: `research/*` and `admin/*` routes, each call counted inside the app. The verdicts come from those counters, not from what the MCP layer reported.
- `call_tool`'s first attempt used the wrong argument names. It was rerun with the correct ones (`name`, `arguments`): admin refused, research reached.
- **A3b was added after A3 ran**, because A3's tool listing showed tools that sit outside the category system. With `allowed_tool_categories=["research"]`:
  - `install_skill` wrote `SKILL.md` into the server's skills folder, from where it is served back to every client as a resource or prompt. That is a way to plant instructions for future sessions.
  - `openbb_dispatch(server_url=…)` made the server request `/openapi.json` and `/` from a URL the client chose.
  - `openbb_list_commands` exposed 54 KB of OpenBB commands outside the allow-list.
- Setting `default_skills_dir=""` and `enable_cli_tools=False` removed the dispatch tools and made `install_skill` fail. `install_skill` is still *listed*, though. A startup test asserting the exact tool list is needed.

### B1 — freqtrade suite
- Environment-caused failures:
  - FreqAI extras not installed (2 tests);
  - running as root, so a no-permission test can't fail as expected (1);
  - `pip-audit` and an invalid-URL test that depend on the network (3).
- Unexplained: `test_process_scheduled_job_error` fails in isolation too. It concerns the scheduler, not backtesting.

### B2 — fills
- **(c2) is the important one.** freqtrade's stop exit returns the candle's *open* only when the whole candle is beyond the stop (`stoploss_value > high`). A candle that opens through the stop and then trades back above it exits at the stop price. A real stop order triggers at the open and fills near it [Certain — read `backtesting.py` `_get_close_rate_for_stoploss` + run].
- The pre-registration described "the next candle opens 10% below entry" without fixing the high. Both variants were run and both are reported.
- (e) Funding stamps exactly at entry and at exit are both charged (`searchsorted` left on open, right on close) [Certain — read + run]. Whether a real venue charges a position opened exactly at a funding time depends on the venue [Guessing]. Check Coinbase's rule at the spike.

### B3 — hyperopt on noise
- Data: a 4-year hourly random walk (seed 20261105), zero drift. In-sample = first half, out-of-sample = second half.
- The best parameters of 200 tries were nearly the same with and without fees (fast 25–26, slow 181).
- The pre-registered expectation ("best in-sample clearly positive") held only without fees. At 0.1% per side the best of 200 barely broke even in-sample. Costs dominate at this trade count.

### B4 — leak tools
- **Deviation:** the first whole-series-mean fixture produced 0 entry signals in freqtrade's 3-day test window, so the run was inconclusive, not a pass. The fixture was revised to trade more often, with the same leak, and rerun. Both runs are reported.
- Leak sizes are still easy: one bar, and a whole-series statistic. A 1-bar leak inside a rolling window, or a leak through a data join, wasn't tested.

### B5 — speed
3.6 s for one 2-year five-minute backtest means ~1 hour per 1,000 variants on this 2-CPU machine. That's too slow for counted screening sweeps (V2-D03), where VectorBT-style vectorised runs take milliseconds [Likely].

### B6 — "is it worth switching from IBKR?" (decision rule written before looking)
- **Exchanges freqtrade supports** (README):
  - spot: Binance, BingX, Bitget, Bybit (+EU), Gate (+EU), HTX, Hyperliquid, Kraken, OKX (+EEA), Bitvavo, Kucoin;
  - futures: Binance, Bitget, Bybit, Gate, Hyperliquid, Kraken, OKX [Certain].
  - Coinbase isn't on the list [Certain].
- **From Ontario:**
  - Kraken is a registered restricted dealer with the OSC [Certain — Kraken page footer]. Margin/shorting is unavailable to Ontario retail (founder's check, V2-D27).
  - The EU/EEA variants are EU-only [Likely].
  - Binance, Bybit and OKX withdrew from Ontario/Canada, and the rest aren't registered there [Likely].
  - Hyperliquid was rejected in V2-D27.
- **Cost:** Kraken spot, lowest tier, is **0.40% maker / 0.80% taker per side** (effective 9 Jul 2026) [Certain — Kraken support page]. That's **80–160 bps per round trip**.
  - IBKR Coinbase nano BTC: commission ~USD 0.20 per contract (master doc §3), plus an exchange fee of ~USD 0.07–0.10 per side in Coinbase Derivatives' 2022 filing [Likely — may have changed], on 0.01 BTC.
  - At an assumed BTC price of $100k [Guessing — price not checked], that's ~3 bps per side, **~6 bps per round trip** before spread.
  - So Kraken spot costs **13–27×** IBKR. **Fails both conditions** (no shorting; cost far above 2×).
- **One thing to check:** Kraken's July 2026 fee page says futures trading "does not count toward fee tiers for **Canadian accounts**" [Certain — read]. That suggests some Canadian accounts can trade Kraken futures, which would allow shorting at derivative fees. Whether an Ontario retail account can is unverified [Guessing]. A two-minute check in your Kraken account would settle it.

### C1 — Qlib benchmark
- Official dataset, which ends **25 Sep 2020** [Certain — its calendar]. The README now calls the official dataset disabled and points to a community dataset [Certain — README].
- LightGBM within tolerance on every reported metric: ICIR 0.382 (0.366), Rank IC 0.049 (0.047), IR 0.914 (1.016), MDD −0.086 (−0.104).
- **Linear's annualised return is outside tolerance** (+2.7 points); its IC matches. The first Linear run crashed while reading an empty MLflow metric file. It was rerun once, unchanged, and both logs are kept. The cause wasn't established; the disk filling up later in the session is a possible but unconfirmed link [Guessing].

### C2 / C3 — Qlib on BTC; future data
- Data: Bitstamp BTC/USD 1-minute → 1-hour, 2017-01-01 to 2024-12-31 (70,128 bars), loaded with Qlib's own `dump_bin.py` at `60min` frequency.
- **Trap found:** a query with `end_time="2024-12-31"` returned 70,105 bars. A date-only end means midnight, so the last day's 23 later hours were silently dropped. With `"2024-12-31 23:00"` it returned all 70,128 [Certain — run]. (V2 convention: full timestamps, half-open ranges.)
- Shorting is refused in Qlib's position model [Certain — run]; its exchange code carries a "TODO: make the trading shortable" comment [Certain — read].
- The test IC values come from a fixed, untuned toy model and say nothing about BTC predictability.

### C4 — recorder
MLflow underneath: a finished run was reopened and its Sharpe rewritten, and another run was deleted, both through Qlib's own API [Certain — run].

### D1 — RD-Agent tests
- Offline-marked suite: 131 passed; 1 failed, a module import that needs an optional parallel-processing package.
- The non-offline tests need LLM keys and Docker. Running them anyway gave 78 passed and 33 failed/errored (LLM calls, Docker, and the disk filling up). One of them wrote a **22 GB cache folder** (`pickle_cache/`) before the disk ran out [Certain — observed]. It was deleted.

### D2 — RD-Agent selection replay
Running (5 runs × 10 loops; ~90 s per Qlib run on 2 CPUs).
- **Deviations from the pre-registration**, all set before the full run:
  - **base features = ALPHA20**, RD-Agent's actual default, not full Alpha158 as the pre-registration said;
  - Qlib data = the community dataset (to 4 Nov 2026), because the official one stops in 2020 and leaves no held-out period;
  - LightGBM threads 20 → 2;
  - local `qrun` instead of Docker.
- **Smoke test (1 run × 1 loop):** a random factor raised test annualised excess return from 4.45% to 6.46% while test IC *fell* (0.0306 → 0.0293), so it was kept. On the held-out years the same set was +0.39 points over the baseline instead of +2.02.
- **Full run (finished 5 Nov ~18:00 local):**

| Run | Factors kept (of 10) | Claimed gain, test 2017–2020 | Held-out gain, Aug 2020 – Nov 2026 | Test IC of final set | Held-out IC |
|---|---|---|---|---|---|
| baseline (ALPHA20) | — | 4.45% ARR | 2.98% ARR | 0.0306 | 0.0115 |
| 0 | 3 | +5.6 pts | −0.6 pts | 0.036 | 0.010 |
| 1 | 4 | +4.0 pts | +2.2 pts | 0.035 | 0.014 |
| 2 | 3 | +4.3 pts | −0.9 pts | 0.033 | 0.014 |
| 3 | 6 | +4.3 pts | +0.9 pts | 0.035 | 0.014 |
| 4 | 3 | +4.6 pts | +0.4 pts | 0.040 | 0.016 |
| **mean** | **3.8** | **+4.6 pts** | **+0.4 pts** | | |

  - Rule (held-out ≥ ½ claimed): mean held-out/claimed = 0.09 → **FAIL** [Certain — run].
  - Test IC also rose for every final set (0.031 → 0.033–0.040) while held-out IC stayed at the baseline's level (0.010–0.016). Selecting on the test block inflated both measures there.
  - One candidate (run 1, loop 5) was skipped by the duplicate check (correlation > 0.99 with a kept factor), as RD-Agent's own dedup does; it still counts as one of the 10 loops.
  - **What this shows:** RD-Agent's default selection step, fed ideas with no information, reports a test-period improvement about as large as a real one would be. It does **not** show that the paper's published gains are all selection: an LLM's factors may carry real information, and the paper's protocol wasn't checked [Guessing].
  - Held-out data is the community dataset after 1 Aug 2020. Five runs is small; the held-out gains are noisy (sd ≈ 1.2 pts).

### D3 — run time
- One loop's Qlib train + backtest: median 82 s (min 79, max 87) on this 2-CPU machine; a held-out scoring run ~122 s [Certain — run].
- A real RD-Agent loop adds LLM calls (proposal, code writing, code repair, feedback) and Docker start-up. A 10-loop run on the founder's M4 would likely take tens of minutes plus API costs [Guessing].
