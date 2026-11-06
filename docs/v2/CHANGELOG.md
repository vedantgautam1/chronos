# CHANGELOG — what was done, when

Dated work log. **Decisions** and their reasons live in `CHRONOS_V2.md` §10 (and what we won't do in §11); this file records the **work**: what changed, where, and what it was based on. Newest first. Every session adds an entry (CHRONOS_V2 §14 rule 7).

---

## 5 Nov 2026 — decisions V2-D41 and V2-D42 locked

- **Locked by the founder ("lock p9 and p10"):**
  - **V2-D41** (was P-9, from S18): budget guard for paid APIs. Plan → reserve → settle against our own spend ledger; caps $0.50/run, $3/day, $25/month for AI APIs to start; no paid retries; one fixed host; redirects refused; size cap; keys in Keychain or an owner-only file; alerts 50/80/100%, paid collectors stop at 100%. Built in step 4 before any paid collector.
  - **V2-D42** (was P-10, from S18): every trial record stores its data footprint from step 2 (latest timestamp read, data hash, code coordinate, `partial` flag); research MCP answers carry it plus the trial count.
- **Founder instructions:** step 4 loads Kraken's quarterly bulk trade files for BTC/ETH (after checking one real file); no upstream bug report to freqtrade.
- **§11b:** two Skylit rows added (no crypto coverage; vendor MCP servers for research in chat).
- **Updated:** `CHRONOS_V2.md` §1, §2, §4, §8, §9 (steps 2, 4, 8), §10, §11b, §12; `BUILD_NOTES.md` §4, §6, §7; Project docs (handoff, library, read-first). `COMPONENTS.md` and `specs/` checked: no references to change.

## 5 Nov 2026 — S19–S22 deep pass (everything tested)

- Founder asked for every repo in S19–S22 to be tested and thought through. Pre-registered in `057184b`; results in `research/s19-s22-deep/RESULTS.md`. **No switch from any locked choice** (NautilusTrader V2-D04, IBKR futures V2-D27, Mnemosyne V2-D33/D42, research MCP server V2-D19); no new proposal.
  - **OpenBB:** the parts we might use pass their tests (FRED, MCP server); some providers fail at the repo head. FRED vintages work only through an undocumented single-date pass-through. The MCP allow-list holds for our routes, but extra tools outside it can write files on the server and fetch client-chosen URLs unless switched off.
  - **freqtrade:** 4,710 tests pass (7 fail, 6 of them environment). Fill rules exact except one: a bar that opens through the stop and recovers fills at the stop, not the open. Hyperopt on pure noise: best of 200 looks good in-sample, loses out of sample, no adjustment shown. Its leak tools caught one-bar and whole-series leaks. No venue it supports is usable from Ontario with shorting at a cost near IBKR's.
  - **Qlib:** LightGBM benchmark reproduced; Linear's return didn't. BTC 24/7 hourly data loads fully, but it can't short; date-only range ends drop a day; no guard against future-data features; recorder runs can be edited and deleted.
  - **RD-Agent:** 131 offline tests pass (1 fails). Its keep-if-test-improves rule, fed 10 no-information factors per run: claimed +4.6 points of annual excess return on the test period, +0.4 held out (5 runs).
- `BUILD_NOTES.md`: full timestamps as range ends (§1); optimisers log every try (§2); deep-pass results on the leak tools and a no-future-features rule (§2); freqtrade's own Kraken sample shows the timestamp loss, FRED pass-through detail (§4); five known-answer fill tests for the spike (§5); MLflow is not a trial store (§6); OpenBB MCP lockdown, RD-Agent replay numbers (§7).

## 5 Nov 2026 — content items S19–S22 (OpenBB, freqtrade, Qlib, RD-Agent)

- **None replaces anything in build steps 2–5; no proposal, no lock.** Analysis in the Project (`claude/item-analyses-3.md`), library entries in `claude/reference-library.md`.
  - **S19 OpenBB** (now `openbq-org/OpenBB`, Apache-2.0; the move looks legitimate: the long-time maintainer still commits). A free-data platform plus an MCP server that turns any FastAPI app into MCP tools (a candidate for the step-8 research server). No Kraken, no IBKR. Its FRED fetcher strips vintages.
  - **S20 freqtrade** (GPL-3.0). A crypto bot with no IBKR, so it can't be our engine. Its Kraken trade-CSV importer loses every trade that shares a timestamp (F1 FAIL, run). Its look-ahead "slice" and warm-up tests are worth copying as methods (F2 PASS, 27/27).
  - **S21 Qlib** (MIT). An equities ML research platform; its MLflow recorder is weaker than Mnemosyne's design.
  - **S22 RD-Agent** (MIT). An LLM decides "replace best result" from test-segment backtests every loop: an LLM verdict, an uncounted search and a reused test block.
- **Correction:** Kraken does publish bulk trade history (quarterly files), apparently without the aggressor side. Master doc §2 (Kraken recorder row) and BUILD_NOTES §4 said "no bulk dump"; both fixed. V2-D26 is unaffected (the side still needs the API).
- `BUILD_NOTES.md` §2: two look-ahead tests for the strategy kit. §4: the bulk-files correction, never deduplicate trades on timestamp, FRED-via-OpenBB has no vintages. §7: an LLM must not pick winners from backtests.
- `research/s19-s22/`: pre-registered in `4ea202b`; script, raw results, `RESULTS.md`. `research/README.md` row added. Master doc counts updated to S1–S22.

## 5 Nov 2026 — content item S18 (Skylit)

- **S18: SkylitAI's three public repos** (`skylit-mcp`, `skylit-agent-kit`, `skylit-agent-lab`), analysed as one item. Skylit sells US equity and index options data: options flow, dealer positioning, volatility, dark-pool prints. No crypto, no futures. The repos are client code, setup guides and examples; the data service itself is closed and paid. **Verdict:** nothing to adopt for the crypto track; changes no decision; no proposal. One build pattern kept (budget reservation for paid-API clients, BUILD_NOTES §7). Library entries in the Project.
- Checks in `research/s18-skylit/` (pre-registered in `3e7209a`): offline modes made 0 network calls over 12 commands; live mode without a key made 0. Test suites 167 + 345 OK when run as documented; the pre-registered `-I` command could not import the repos' own packages (trap added to BUILD_NOTES §1).
- `research/README.md`: S18 row; fixed its pointer to the Project notes (S13 onward are in `item-analyses-3.md`).

## 5 Nov 2026 — decisions V2-D38–D40 locked; content analysis resumed

- **Locked by the founder (5 Nov, "lock new decisions"):**
  - **V2-D38** (O-10; amends V2-D34): crypto seal from 1 Apr 2026 00:00 UTC, growing; confirm rule ≥ 200 sealed trades, net after 2× costs > 0, adverse-funding run > 0; no significance bar; < 200 trades → same test in L3 paper. Reason for the amendment: "the last 25%" would have sealed all of Kronos's post-cutoff data.
  - **V2-D39** (O-11): adverse funding = 95th percentile of the contract's own |hourly funding| from launch to the seal date, charged every hour held.
  - **V2-D40** (O-12): limits = exactly Themis's approved contracts; account ceiling 2× equity notional in paper; false-alarm budget 10% per strategy-year.
- **Founder instruction:** content analysis resumes alongside building, repos first, judged by whether they replace something in build steps 2–5.
- **Updated:** `CHRONOS_V2.md` (§1, §2, §4, §6, §9, §10, §12), `BUILD_NOTES.md` §2, §5, §11, `specs/kronos-shadow.md`.

## 5 Nov 2026 — decisions V2-D34–D37 locked

- **Locked by the founder (5 Nov, "commit to ur suggestions"):**
  - **V2-D34** — sealed final block (~last 25% per instrument) confirmed with one look per hypothesis lineage, recorded in Mnemosyne; overlapping looks refused (was P-5, option c).
  - **V2-D35** — 2× cost stress doubles only the frictions; funding and basis at modelled values; adverse-funding run where funding exists (was P-6; protected change, approved). Funding parts conditional on O-4.
  - **V2-D36** — Nemesis in three layers: Nautilus risk engine, IBKR broker-side limits, independent watchdog with its own IBKR connection; limits from Themis's approved size; latched kill (was P-7, option a). Layer 2 conditional on new spike criterion (f).
  - **V2-D37** — edge-decay alarm in Argus: CUSUM vs break-even and vs paper mean, k set from the shift, budget written first; alarm halts new entries (was P-8).
- **Updated:** `CHRONOS_V2.md` (§1, §2, §4, §6, §9 step 3 criterion (f) and steps 5–6, §10, §12 with new O-10–O-12), `BUILD_NOTES.md` §2, §5, §11, `COMPONENTS.md` §2, `CODEBASE.md`, `specs/kronos-shadow.md` (staleness note).
- **Still open (protected numbers, set before running):** sealed-block size and confirm rule (O-10), adverse-funding level (O-11), limit headroom and false-alarm budget (O-12).

## 5 Nov 2026 — content analysis S13–S17 (Parts 3–7); content analysis paused

- **Items:** Arwaz Az, "Self-Improving AI Trading Agent" Parts 3–7 (evaluation gate, agent team, improvement loop, validation and safety layer, complete architecture). All five PDFs read; the full code pack run: 157/157 tests; every Part 3–7 figure reproduced (0 differences in 38,480 values).
- **Own checks** (rules written before running, `research/s13-s17-deep-pass/`):
  - K1: the book's promotion gate accepted forged evidence (a hand-built ladder record took a failed decoy to LIVE; a typed monitor calibration and a swapped audit log also passed).
  - K2: its "one sealed look" is per object and per file hash; consecutive loop cycles reuse 43–56% of sealed days; a null idea looked at four times is confirmed 16% of the time vs 5%.
  - K3: with the risk engine in its own process, the broker handle, a swapped risk handle and a one-line SQL un-halt still got orders through; its order-size limit misses every size bug below 1.67×. Killing the risk process failed closed, as intended.
  - K4: the book's unexplained weak break-even monitor is a slack setting: 30% → 56.5% of dead edges found at the same false-alarm rate once k is set from the shift.
- **Updated:** `CHRONOS_V2.md` (§1, §2, §6 pointer, §9 "before step 2" done, §11b three rows, §12 proposals **P-5–P-8**, §13), `BUILD_NOTES.md` (§2, §5, §6, §7, §10, new §11 Nemesis/Argus), `COMPONENTS.md` §3, `research/README.md`.
- **Added:** `research/s13-s17-deep-pass/` (pre-registration, check scripts, results JSON, `RESULTS.md`). The author's code pack is not committed (licence not stated).
- **Proposals for the founder (nothing locked):** P-5 where the edge check runs vs the searched history; P-6 per-component 2× cost stress (protected); P-7 Nemesis boundary and limit headroom (limit numbers protected); P-8 edge-decay alarm in Argus.
- **Next:** content analysis pauses; §9 step 2 (v2 code skeleton) starts.

## 5 Nov 2026 — decisions V2-D31–D33 written in; repo documented

- **Locked by the founder (3 Nov, "adopt everything"):**
  - **V2-D31** — warn-only search-fragmentation screen in the edge check, ported from v1 (was P-3).
  - **V2-D32** — the change check also requires the candidate to be net positive after 2× costs; a net-negative live version triggers a retirement review (was P-4).
  - **V2-D33** — Mnemosyne stores every counted trial's daily returns and trade list (was P-1).
  - P-2 (HAR baseline for Kronos role C) stays proposed until Kronos work.
- **Updated:** `CHRONOS_V2.md` (§0, §1, §2, §4, §6, §9, §10, §11b, §12, §13, §14), `BUILD_NOTES.md` §2, §6, §10 (new traps and the known-answer tests to write for V2-D31/D32), `COMPONENTS.md` §1–§3.
- **Added:** `CODEBASE.md` (what every file is and its v2 fate), this changelog, `research/README.md`, `research/s11-deep-pass/`, `research/s12-deep-pass/` (pre-registered rules, scripts, results).
- **Not implemented as code, on purpose:** no v2 code exists yet, and the v2 package layout is decided in the §9 step-2 build session (V2-D29). V2-D31–D33 are written as build instructions with acceptance tests, to be built in step 2 / step 5.
- **Next:** analyse Parts 3–7 of the Arwaz Az series (code packs in the founder's Drive), then stop content analysis and start §9 step 2.

## 3 Nov 2026 — evening: content analysis S11–S12

- **S11** (Arwaz Az, "Self-Improving AI Trading Agent" Part 1, memory) and **S12** (Part 2, experiment ledger). Both PDFs read; both code packs run: 62/62 tests, every Part 1 and Part 2 figure reproduced exactly.
- Own checks, rules written before running: the corrected lesson miner's false-positive rate holds (4.3% over 300 worlds); memory's benefit drops by a fifth to a half when its keys aren't the planted mechanism; splitting a search across families raises false finds from 1% to 13–28%; a change check without "candidate must make money" accepted changes in 40% of no-edge worlds (0% with it).
- Led to proposals P-3 and P-4, locked as V2-D31 and V2-D32 (above).
- The claude.ai Project's GitHub sync was found serving v1 files as current; the founder re-synced it. `claude/00-READ-FIRST.md` now explains how to read the master doc completely from a chat.

## 3 Nov 2026 — v1 frozen, v2 doc pack, V2-D29 and V2-D30

- **v1 frozen** on branch `v1-final` (commit `6b2b628`); v1 docs moved to `docs/v1-archive/` with a closing entry in its `HANDOFF.md` (PR #1).
- **v2 doc pack created:** `CHRONOS_V2.md`, `BUILD_NOTES.md`, `COMPONENTS.md`, `specs/` (PR #1).
- **V2-D29** — v2 code lives in this repo (PR #2). Trial-storage proposal renamed P-1.
- **V2-D30** — the data-collection VPS moves after the NautilusTrader spike (PR #3).
- **S10 deep pass:** arch, tick, MAPIE installed and tested; PySR tested with a stand-in. Scripts in `research/s10-deep-pass/`.

## 29 Oct 2026 — solo-founder design review

- Developer and quant unavailable; founder works solo. Review protocol **V2-D25** replaces quant review.
- **V2-D20** (neighbourhood check stays binding), **V2-D21** (random-entry null, mid-rank ties), **V2-D23** (bus, gateway, users deferred to triggers; supersedes V2-D09), **V2-D24** (one research track), **V2-D26** (record Kraken trades), **V2-D27** (crypto trades on IBKR futures), **V2-D28** (first track: S-INTRADAY).
- Content items S9 (Bullseye Order Flow indicator) and S10 (QuantFrame "4 GitHub repos").

## 27–28 Oct 2026 — v2 designed from content batches 1–2

- **Batch 1** (S1–S4, Arwaz Az: Playbook and Hidden Math PDFs with code packs, two carousels) produced the v2 design. Running the code packs found S2's cost-free audit table and its ruin-formula bug.
- **Batch 2** (S5 REA pseudo-paper, S6 QuantDinger, S7 Astral reel, S8 Daru Finance and four link lists).
- Decisions **V2-D01–D19** and **V2-D22** (no high-frequency trading).

## Jul–Aug 2026 — v1 built

- Oceanus (data), Hephaestus (engine), Mnemosyne stub, the trial ontology, and the Moirai gauntlet phases 0–4c with touchstones; ~315 tests. Its own results showed no honest should-pass strategy could clear all 11 gates, which led to the v2 redesign. Full history: `docs/v1-archive/HANDOFF.md`.
