# BUILD CARDS — phases 2, 3 and 4

One card per build that doesn't have a full spec yet. A card fixes **what the build must prove** (taken from locked decisions, so it won't move) and leaves **how** to the spec written when the phase opens. A card can't be built from: the loop halts on `spec: card` (LADDER.yaml).

**Why cards and not full specs today.** The engine spike can change the engine. Fee, funding and data-format facts get confirmed in phases 2–3. A full spec written now for B47 would be precise about things we don't know yet. Each phase opens with a **spec-writing session** (planning-grade model) that turns that phase's cards into specs, using what the earlier phases actually found. The specs arrive as a pull request the founder approves: specs are founder-owned files.

`who`: **loop** = unattended · **you+** = needs the founder (your accounts, your Mac, your money, or your approval).

---

## Phase 2 — The engine spike (master doc §9 step 3)

**What the phase must answer:** is NautilusTrader the engine (V2-D04), yes or no, on the six criteria (a)–(f). A week or more of calendar time, because criterion (c) is "several days unattended" and must span a Monday.

**Before it starts (founder):** an IBKR paper account with futures permission and the Coinbase Derivatives and CME crypto market-data subscriptions; IB Gateway installed on the Mac; one Kraken BTC/USD 1-minute OHLCVT file in a connected folder.

### B23 — Spike prep · M · loop
- **Prove:** a pinned NautilusTrader (version recorded in a separate `v2/spike/` uv project so the spike can't leak into `chronos2`) installs on Python 3.14 on Linux and on the Mac; the Kraken file loads into Nautilus's data catalog; v1's MA-crossover is re-implemented as a Nautilus strategy.
- **Checks:** bar counts in the catalog equal the door's for the same range; a run that starts and ends on a weekend completes (the 24/7 edge trap, BUILD_NOTES §5).
- **Traps:** macOS wheels need macOS 26 on Apple Silicon; pin the version.

### B24 — Criterion (a): parity and fills · M · loop
- **Prove:** (1) the MA strategy on Kraken BTC data gives results on Nautilus that match v1's Hephaestus "within explainable differences", every difference listed and explained; (2) the five known-answer fill tests (BUILD_NOTES §5) give the same fills on Nautilus and on `ml4t-backtest` 0.2.0, or every difference is explained (V2-D43).
- **Checks (the five, pre-registered there):** next-bar-open entry; fees both sides to the cent; a bar that opens through the stop fills at the open; a bar touching stop and target resolves stop-first (or by 1-minute bars); funding stamps at entry/exit follow the venue's rule.
- **Output:** a table, one row per test per engine.

### B25 — Criterion (b): our cost model in the engine · S · loop
- **Prove:** `chronos2.costs` (B16) prices every Nautilus fill; no fill escapes it.
- **Checks:** B16's hand-worked trade reproduced through the engine to the cent; a deliberately unpriced fill path fails a test.

### B26 — IBKR paper hookup; find the contract · S · you+
- **Prove:** IB Gateway on the Mac logs into the paper account; the nano BTC perpetual-style contract and one monthly nano are found by contract search; their exchange code, tick size, multiplier, trading hours and margin are written into `v2/config/venues/`.
- **This is criterion (e), first half.** Nautilus's IBKR adapter lists no Coinbase venue [Certain — read 16 Nov]; if the contract can't be reached through it even with a raw contract spec, **stop and raise it as an engine-choice problem** (master doc §9).

### B27 — Criterion (e): trade it, read funding and fees · M · you+
- **Prove:** paper orders long and short on nano BTC fill; the statement shows commission, exchange and regulatory fees matching B16's venue file (or the file is corrected, with the statement as source); funding cash adjustments are read and matched to the hours held.
- **Also:** pull the contract's hourly funding history from launch to 31 Mar 2026 and compute the 95th percentile of its absolute value (V2-D39). Store the number, its source and hash; setting it in `protected/validation.yaml` is a protected change for the founder. If the history can't be obtained: stop and flag (V2-D39 says so).
- **Also:** download the nano BTC contract's own bars from its launch to 31 Mar 2026 (pre-seal) through the door, as its own series. Proposal P-15's basis check (B47) needs them, and so does any honest statement of the futures–spot basis.
- **Answers O-4.**

### B28 — Criterion (f): broker precautions and the second connection · S · you+
- **Prove:** an oversize API order on the nano contract is rejected by IBKR's order precautions; a second API connection with its own client id, while the strategy node is connected, can read positions and orders and cancel/flatten.
- **If precautions don't apply to API orders:** record it; V2-D36 layer 2 is re-argued at G3.

### B29 — Criterion (d): two strategies, two venues, one node · S · you+
- **Prove:** one Nautilus node runs two strategies on two venues at once (nano on Coinbase Derivatives and MBT on CME, or nano and Kraken spot data) without interfering.

### B30 — Criterion (c): several days unattended · S · you+ (calendar time)
- **Prove:** paper trading nano BTC long and short for several days with no manual intervention **except** the Monday re-login, whose cost is measured (minutes of downtime, what reconnect did, whether reconciliation ran).
- **Needs:** the Mac plugged in and awake for those days, or the server rented early (founder's choice; master doc §9 allows either).

### B31 — Spike report · S · loop
- **Output:** `docs/v2/research/spike/REPORT.md`: each criterion pass/fail with evidence; every explained difference; the fee, funding, margin and hours facts found; open risks; a recommendation.

### G3 — Engine decision · gate
The founder decides: NautilusTrader final (V2-D04 unconditional), or re-argue. The gate report includes the blind re-check of B24's fill table by a session that hasn't seen the spike.

---

## Phase 3 — Always-on collection (master doc §9 step 4, V2-D30)

**What the phase must deliver:** a server that records, without attention, the things that can't be recovered later (news and sentiment as seen at the time; live futures spreads), plus Kraken trades, inside a spend limit that fails closed.

**Before it starts (founder):** rent the server (2 vCPU / 4–8 GB to start [Guessing — check prices]); API keys for Grok and Claude; decide whether B30 already rented it.

### B32 — Server up · M · you+
- **Prove:** hardened Linux box (SSH keys only, firewall, automatic security updates, separate OS users for collectors and, later, the watchdog), `TZ=UTC` asserted at start-up, Postgres with the v2 migrations applied, nightly backups restored once as a test.
- **Check:** a restore of last night's backup onto a scratch database passes `audit()` (B09).

### B33 — Budget guard (V2-D41) · M · loop
- **Prove:** one shared client for every paid call: plan the run's maximum cost → reserve it in a Postgres spend ledger → settle with the usage the API reports; unsettled reservations count as spent. Caps to start: $0.50 per run, $3 per day, $25 per month.
- **Checks (locked in V2-D41):** over-budget plan → 0 calls; redirect → refused; oversize response → cut; no key → 0 network attempts. Alerts at 50/80/100%; at 100% paid collectors stop, free ones continue.

### B34 — Collector frame · M · loop
- **Prove:** a small scheduler; every collector writes raw immutable files with SHA-256 first, then parsed rows with `available_at`; a missed run or a break in a feed is stored as a **gap row** with its time range; simple alerts (feed down, collector silent, disk above 70%) reach the founder's phone or email.
- **Check:** kill a collector mid-run → a gap row and an alert, never a silent hole.

### B35 — Kraken trade recorder (V2-D26) · M · loop
- **Prove:** every BTC/USD and ETH/USD trade recorded forward with price, size, time, aggressor side, market/limit flag; each page continues from the last stored trade id; sizes at their own precision; nothing deduplicated on timestamp.
- **Check:** replaying a recorded day from the API reproduces the stored rows exactly; a simulated missing page produces a gap row.
- **Note:** this series starts after the seal. Its research window and its own seal date X are written into Mnemosyne before anyone researches it (V2-D46; B46).

### B36 — Kraken bulk trade files · M · you+ (one real file from you)
- **Prove:** one real quarterly file's columns and timestamp resolution are checked first (founder, 5 Nov); published checksums verified; BTC and ETH history loaded with the buy/sell field; on days where recorder and file overlap, the sides agree (this settles whether `type` is the taker side).
- **Seal:** file rows from 1 Apr 2026 onward are stored but sealed like any other BTC/ETH data.

### B37 — News catalog and headline recorder · M · loop
- **Prove:** World Monitor's catalog (757 feeds, tiers, types) imported as-is; **the AGPL-3.0 licence file added to the repo and World Monitor's notices kept** (founder, 15 Nov); headlines recorded with `first_seen_utc`; external text stored as data, never executed or followed.
- **Check:** one wire story syndicated across many feeds is stored once per feed (clustering into events is later; frequency = independent sources, BUILD_NOTES §7).

### B38 — GDELT collector · S · loop
- **Prove:** the 15-minute feed recorded with arrival times; history loaded as a labelled crude proxy.

### B39 — Grok/X collector · M · you+ (keys)
- **Prove:** every call goes through B33; model versions pinned; every prompt and response stored with timestamps; both scorers (Grok and Claude) score each event and the disagreement is logged (the Leaning "choose at rule-freeze" item).
- **Check:** with the monthly cap set to $0 in a test, zero network attempts.

### B40 — Macro actuals · S · loop
- **Prove:** official releases stored with their release timestamps, first value as released (never a later revision).

### B41 — IBKR spread snapshots · M · you+
- **Prove:** IB Gateway on the server; quotes for the nano and micro contracts sampled on a schedule and stored; the weekly re-login has a runbook and an alert if it hasn't happened.
- **This is unrecoverable data** (master doc §1): the reason phase 3 exists.

### G4 — Collection audit · gate
A week of unattended collection: gap report per collector, spend report against the caps, backup restored, disk and memory headroom. The founder approves the monthly running cost.

---

## Phase 4 — The validation acceptance test (master doc §9 step 5)

**What the phase must answer:** do v2's checks give the right answer on worlds where we know the answer? Until G5, no S-INTRADAY or S-TREND result is trusted (V2-D08).

B42–B50 are engine-independent and may run while phases 2–3 wait on the founder (V2-D50). B51–B54 need G3.

### B42 — Load the full Kraken 1-minute history · S · you+ (you download the files)
- **Prove:** Kraken's BTC/USD and ETH/USD 1-minute OHLCVT history, every year available, is loaded through B15's loader into the store on the external drive; each file's SHA-256 is recorded; the loader's real-file evidence file exists (so `VERIFIED_AGAINST_REAL_FILE` may be set true); the validation report (B13) lists every gap, and nothing is filled.
- **Checks:** bar counts per year against the file's own row counts; the first and last timestamps; reading anything from 1 Apr 2026 onward through the door for research is refused; a second load of the same files changes nothing.
- **Why it is its own build:** the first draft had no build that loaded the data every real result depends on (G0 red team, finding 23). The files can't be fetched from a cloud session, so the founder downloads them.

### B43 — Screening wrapper · M · loop
- **Prove:** one wrapper around VectorBT that fixes the five defaults found in S32 (BUILD_NOTES §2): signals shifted one bar and filled at the next open; OHLC always passed so stops see the whole bar; stop exits as market orders so slippage applies; funding added per trade from the trade records; `freq` and `year_freq` always set. Costs come from B16. **Every column of every sweep is registered as a SEARCH trial** (B10) with its returns, trades and footprint (B11), before any result is shown.
- **Checks:** five tests, one per fix, each failing on raw VectorBT and passing through the wrapper; 1,000 variants → `search_n` rises by exactly 1,000; data comes only through the door (B14).
- **First:** re-check the S32 findings on the version the lock file resolves (1.2.1 vs the 1.2.0 that was tested).

### B44 — Look-ahead test kit · M · loop
- **Prove:** three tests any strategy must pass before the edge check: the **slice test** (rerun on history cut just after each signal; every value at that bar must match), the **warm-up test** (indicators agree within a stated tolerance across different amounts of prior history), the **nudge probe** (change a future close; no earlier entry may change).
- **Checks:** fixtures with a one-bar-ahead feature and a whole-series mean are flagged; the clean version passes; an EMA-200 is flagged by the warm-up test and an SMA isn't (BUILD_NOTES §2, S20 B4). Negative lags are rejected at parse time.

### B45 — Null benchmark (V2-D21) · M · loop
- **Prove:** random entries with matched exposure on the real price path: each draw keeps the strategy's trade count, holding-time distribution, long/short mix, sizing rule and costs; positions don't overlap; entries only where the strategy could have traded; at least 1,000 draws; ranks through `stats/ranks.py` (B07) only.
- **Checks (the four, locked):** (a) the floating-point tie case; (b) a random-entry strategy gives roughly uniform p-values; (c) a planted timing edge gives low p-values; (d) constant exposure on a trending series does **not** pass.

### B46 — Sealed-look ledger · M · loop
- **Prove:** every sealed look is a row keyed by instrument + date range + lineage (B18); a look that overlaps an earlier one for the same lineage is refused **by the database** (an exclusion constraint), not by Python; the door's `sealed_look` purpose (B14) works only with a ledger row; post-seal series get a research window `[start, X)` and their own seal from X, with X stored before research (V2-D46), and prices inside that window are readable only through a join to the series.
- **Checks:** the V2-D34 fixture (an overlapping second look is refused); a dataset one day longer is still refused (the S13 trap); a look for a sibling hypothesis counts as the lineage's look.
- **Question for the founder before this spec is written:** a lineage is a hypothesis plus its direct siblings (V2-D34). A chain of siblings (A–B, B–C, not A–C) is then three lineages and three looks. One look for the whole chain, or three? (B18 reports chains; it decides nothing.)

### B47 — Edge check I · M · loop
- **Prove:** the edge check's first half on the standard result shape (B11; V2-D48): configuration frozen and hashed before the run and stored with the verdict; data-sufficiency first (years to significance); DSR at honest N (and at the lineage's union N as a warning, B18); net after costs at 1× and at 2× frictions; the adverse-funding run where funding applies (V2-D35).
- **Checks:** T-e's two numbers through the full path; the V2-D35 fixture fails at 2×; a verdict can't be produced under a config whose hash wasn't stored first.
- **Basis check (proposal P-15, still the founder's to accept):** the edge check can rerun a candidate on the real nano contract's own bars (from B27) as a VERIFICATION trial and print the difference from the spot-signal result, and it states which basis model was used for the years before the contract existed. If P-15 is declined, this bullet is dropped when the spec is written.

### B48 — Edge check II · M · loop
- **Prove:** the second half: beats the null (B45); the neighbourhood test with a **pluggable rule** (the rule itself is chosen in B53, V2-D20); a lone spike also opens a look-ahead review (B44); the sealed-look confirm (≥ 200 sealed trades, net after 2× > 0, adverse funding > 0; else deferred to paper, V2-D38); the warnings (subperiod, minimum trades, capacity, fragmentation); the break-even cost multiple reported.
- **Checks:** **one fixture per criterion that only that criterion catches**, or a written note that it is deliberate defence in depth (BUILD_NOTES §2, S13).

### B49 — Change check · M · loop
- **Prove:** paired daily-difference test against the live version; Šidák bar over cumulative trials; 2× frictions; no bias toward trading less; the candidate must be net positive on its own after 2× costs; a live version that is itself net negative opens a retirement review (V2-D32).
- **Checks (locked):** zero-edge live version losing at 2×, candidate trades half as often with zero edge → REJECT and retirement review; a candidate with a real edge that clears 2× → ACCEPT.

### B50 — Sizing v0 · M · loop
- **Prove:** accepted ruin probability → cushion → risk per trade, with the ruin formula fixed (`exp(−θ·D)`, not `exp(−θ·D·L)`); verified by block bootstrap because the formula assumes independent trades; never above ¼ Kelly; rounds to whole contracts and skips what it can't place; every money amount is configuration.
- **Checks:** the ruin bug's known pair (5.0% wrong vs 10.0% right at 0.30R cost, BUILD_NOTES §3); Carver's volatility-target sizing reproduced with √365, not 16; v1's hand-enumerable 24-ordering drawdown fixture (ported with `trade_shuffle`).
- **Open (P-14a):** what to do when the target is below one contract. Founder decides before L3; v0 implements "skip" and reports how often it skipped.

### B51 — Run the touchstones · M · loop · needs G3
- **Prove:** each touchstone (B20) gives its pre-registered v2 verdict: T-b, T-d, T-e FAIL the edge check; T-a2 PASSES once sized by its drawdown budget; T-c is caught by the look-ahead kit; T-a1 as written in B20.
- **A mismatch is a finding, never a cue to re-seed.** The loop halts and the founder sees it.
- **Also:** a sample of touchstones re-run on the real engine gives the same verdicts as on the screening wrapper (V2-D48: two code paths, one answer).

### B52 — Planted-edge calibration: write the criteria · S · you+ (you approve the criteria)
- **Prove nothing yet; write down:** the worlds (noise; a smooth planted edge; a narrow real edge; **intraday-style** planted edges, because S-INTRADAY is the first family, V2-D28; and drift-without-skill); the candidate neighbourhood rules; and **the criteria for choosing between them** (maximum false-pass rate, maximum false-rejection rate, measured for DSR alone vs DSR + neighbourhood), all before a single world is generated.
- **The founder approves the criteria** (they are validation thresholds: protected).

### B53 — Planted-edge calibration: run and choose · M · loop (long compute)
- **Prove:** the rule picked is the one B52's criteria pick, from the measured rates. No other consideration enters.
- **Compute:** thousands of worlds; sized and split in its spec so it fits the tick budget (checkpointed batches, results appended to Mnemosyne as VERIFICATION runs).

### B54 — Acceptance report · S · loop
- **Output:** `docs/v2/research/acceptance/REPORT.md`: every known-answer test and fixture with its result; the calibration tables; the rule chosen and why; what the checks still can't catch.

### G5 — Acceptance test passed · gate (protected)
V2-D08 stops being conditional. Requires a blind re-derivation of the calibration result by a session that has seen none of phase 4 (V2-D25 rule 3), the sabotage run on `moirai/`, and the founder's approval of the chosen thresholds.
