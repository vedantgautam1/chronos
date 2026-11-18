# CHANGELOG — what was done, when

Dated work log. **Decisions** and their reasons live in `CHRONOS_V2.md` §10 (and what we won't do in §11); this file records the **work**: what changed, where, and what it was based on. Newest first. Every session adds an entry (CHRONOS_V2 §14 rule 7).

---

## 18 Nov 2026 — review findings get a severity; the reviewer attaches the patch and fixes the record (P-25, awaiting "lock it")

- **Why.** B01 and B01A cost three review rounds between them. **One** found a real defect (the non-deterministic fingerprint). The other two were test strictness (`match=` missing) and prose (an inaccurate report). Under the old rules the reviewer had two buttons, `PASS` and `CHANGES`, and no way to say "the code is fine, the write-up isn't" — so a one-sentence correction blocked a build and, per reviewer rule 6, came one round short of a halt.
- **Changed in `docs/v2/build/specs/README.md`** (reviewer rules 6–7 and a new "Severity" block): every finding is **blocking** (the code or the tests are wrong) or **non-blocking** (the record or the polish is wrong). Only a blocking finding produces `CHANGES` and counts toward the second-round halt. For each blocking finding the reviewer now writes the **exact patch** — file, line, text as it is, text as it should be — so the builder round is mechanical. For non-blocking findings the reviewer **corrects the report and the CHANGELOG itself**, marked in place and disclosed in the review under "Role deviation". Code and tests stay untouchable: a reviewer that edits them is reviewing its own work.
- **One deliberate exception.** A report or changelog asserting a founder decision, approval, review or measurement that **did not happen** is blocking however small it looks. The gate audit and `LEDGER.md` are built on these documents, and `specs/README.md` already says the role checks cannot catch a session that labels its own work falsely. Inaccurate is non-blocking; untrue is not. This is what B01A round 2 blocked on.
- **Also learned, and not yet fixed anywhere:** a review session without push access cannot commit its review. B01A's round-1 review file was lost that way and had to be reconstructed in round 2 (`reviews/B01A-r1.md`, marked as a reconstruction). Any reviewer needs write access to the repository.
- **Status: proposal P-25 (§12), not yet locked.** The rule text is in this change; §10 gets **V2-D51** when the founder says "lock it". Drafted by Opus in the B01A round-2 session on the founder's instruction.

---

## 18 Nov 2026 — B01A built: dict keys validated like values; the fingerprint made deterministic

- **Fixed the merged B01 defect** in `v2/src/chronos2/core/canonical.py`: `_canonical` passed dict **values** through validation but **keys** through a bare `str()`. Now a dict key must be a `str`; any other key type raises `TypeError` (naming the type). One rule closes all three leaks at once — an unknown-type key no longer reaches a hash with its memory address (non-deterministic across processes), naive-`datetime` and NaN keys no longer reach a hash instead of raising, and two keys can no longer collide after conversion because no conversion happens.
- **One other line changed, with no change in behaviour** *(corrected 18 Nov by the round-2 reviewer on the founder's instruction; this bullet previously read "Nothing else changed… sorted keys … untouched", which contradicted the report's own declared deviation)*. The dict sort expression was simplified from `sorted(obj.items(), key=lambda kv: str(kv[0]))` to `sorted(obj.items())`. Output is byte-for-byte identical, and in fact that sort has no effect on output at all: `canonical_json` already passes `sort_keys=True` to `json.dumps`, so removing the sort entirely leaves all 31 tests green [Certain — run, r2]. Founder's decision 18 Nov: keep the simplified form. `Decimal`/`datetime`/float/`tuple`/`Enum` handling and the value-side raises are untouched; B01's 22 tests pass **unmodified** (every canonical test uses string keys).
- **Known answers written first** (`v2/tests/core/test_canonical_keys.py`, a new file — B01's test file is frozen): six `TypeError` key cases (object, naive `datetime`, NaN, `int`, `int`-vs-`str` collision, nested) red before the code, plus three string-key guards — a canonical-JSON pin, a hand-checkable SHA-256 **stability pin** (`825348ea…`, `printf '%s' '{"a":["1.0","0.10"],"b":1}' | sha256sum`), and a determinism check across two fresh subprocesses with `PYTHONHASHSEED` unset. Full suite **31 passed**, ruff clean.
- **Model:** built on **DeepSeek V4 Pro** per the spec header (founder's 18 Nov choice, O-16); review is on Opus, separate session. First clean **P-24** data point after B01's misfired merge.
- Full detail in `docs/v2/build/reports/B01A.md`. Master-doc and `LEDGER.md` updates are the reviewer's and the gate's, from the report's "For the gate" section.

---

## 18 Nov 2026 — B01 reviewed `CHANGES`, merged by mistake; fix build B01A specified; record reconciled

- **B01's review (`build/reviews/B01-r1.md`, Opus, fresh session).** Verdict **`CHANGES`**, one blocking finding. Independently re-run, not taken from the build report: 22 tests pass, ruff clean, lockfile installs frozen on Python 3.14.6, all three CI jobs green, red-at-step-2 confirmed for the right reason, and **no assertion was weakened between red and green**. Four deliberate mutations (half-open boundary, key sorting, float `repr`, non-UTC offset) were each caught by the matching known-answer test — B01's tests bite.
- **The finding.** `canonical.py` passes dict **keys** through a bare `str()` while values go through `_canonical`. So an unknown-type key is stamped into the hash with its memory address and **the same input hashes differently in every process**; naive-`datetime` and NaN keys reach a hash instead of raising, against B01's own spec; and two keys colliding under `str()` silently lose one [Certain — run]. Narrow in practice (config dicts are string-keyed) but it sits under every fingerprint B09–B11 will store.
- **The merge was a misfire.** Pull request #18 was merged into `v2-build` at `78298f3` on the `CHANGES` verdict, before any fix. **`main` was not touched** — gate discipline held, and the blast radius is one working branch. `v2-build` carries the defect until B01A lands. Recorded, not tidied away: `LEDGER.md` footnote †, and B01's "1 review round" must not be read as a clean pass.
- **New build B01A** (`specs/B01A-canonical-keys.md`, size S, 2 ticks, by hand): a dict key must be a `str`; anything else raises `TypeError`. One rule closes all three leaks. Known answers written first, including a **hand-checkable** stability pin — `printf '%s' '{"a":["1.0","0.10"],"b":1}' | sha256sum` → `825348ea…` — and a determinism test across two fresh subprocesses, because no single-process test can see this class of bug. B01's existing test file is **not** touched (`may_modify_tests: []`); the new tests go in a new file.
- **Ladder:** B01A inserted after B01, and **B02 now needs B01A**, so nothing stacks on the defective helper. `BLUEPRINT.md` Part 5 updated to match (B03 tests that the two agree).
- **Status/record:** `status/B01.json` → `merged` (it is merged; leaving it `changes_requested` would make the B03 loop try to "fix" a finished build). `LEDGER.md` B01 row filled with the real numbers — 1 tick, 1 round, 131 code / 263 test lines — plus the † footnote explaining the override.
- **P-24 (cheap builder, Opus reviewer) has no usable measurement.** B01 ran on DeepSeek V4 Pro and the Opus review caught the defect, which is the system working — but a `CHANGES`-then-merged round measures nothing about cost or rounds. First clean number will be B01A or B02. §12's P-24 row updated to say so.
- **Open questions added:** **O-15** — floats, `Decimal`s and strings share a fingerprint (follows B01's spec as written; a design call, and it must be settled before B09 or never). **O-16** — which model builds B01A; the header says Opus, the founder may switch it to DeepSeek to restart the P-24 measurement, and the header should change *before* the build, not be deviated from during it.
- **New traps** in `BUILD_NOTES.md` §1: canonicalise keys, not just values; test fingerprints across two processes; and pin a fingerprint's wire format with a hand-checkable digest.
- **Housekeeping:** §12's "Next proposal ID" counter read `P-22` while P-23 and P-24 were already in use — corrected to `P-25`, with the next open-question ID recorded too, so the next proposal doesn't collide.
- **For B05:** require the status file to read `passed` before a pull request can merge into `v2-build`. That rule would have stopped this, and it is free to add while B05's GitHub rules are being written. Noted in B01A's spec under "For the gate".

---

## 18 Nov 2026 — B01 built: v2 project scaffold, core helpers, automatic tests (first build, hand-run)

- **First build of the loop's phase 0, run by hand** (the loop doesn't exist until B05). Work is on branch `claude/b01` (PR #18 into the new working branch `v2-build`, which this build also creates from `main`).
- **New v2 project** in `v2/`: `pyproject.toml` (`chronos2`, Python 3.14, src layout) + committed `uv.lock`; deps `numpy`, `scipy`, `pandas`, `pyarrow` (runtime) and `pytest`, `ruff`, `pyyaml` (dev).
- **`src/chronos2/core/`:** `timeutil.py` (`require_utc`, `assert_process_utc`, `HalfOpen`) and `canonical.py` (`canonical_json`, `content_hash` — the v1 `_canonical` idea, tightened: floats by `repr`, raises on NaN/inf/naive datetimes/sets/unknown types).
- **Tests:** known-answer tests for both helpers, the environment test (Python 3.14, `chronos2` importable, v1 `chronos` not importable), the workflow-file test (read-only permissions, no secrets), and a `SELECT 1` Postgres connectivity test (stdlib-only client; psycopg arrives in B09). 22 tests, red-then-green.
- **`.github/workflows/v2.yml`:** three jobs on `pull_request` and pushes to `v2-build`/`main`, read-only token — `tests` (with a `postgres:16` service and `CHRONOS2_TEST_DSN`), `lint`, `v1-oracle` (v1 environment, no dump scripts yet). All three green on PR #18.
- **Housekeeping:** `scratch/.gitkeep`, `docs/drafts/.gitkeep`, `v2/tools/v1_oracle/README.md`, `v2/README.md`.
- **Local Postgres:** installed `postgresql@16` (Homebrew) and created the `postgres` superuser, per handbook §5, so the `SELECT 1` test passes locally too.
- **Model:** built on **DeepSeek V4 Pro** (founder's 17 Nov instruction, P-24 first step); review is on Opus. Cost to be logged by the founder for P-24.
- Full detail in `docs/v2/build/reports/B01.md`. Master-doc, `CODEBASE.md` and `COMPONENTS.md` updates are deferred to the gate, from the report's "For the gate" section.

---

## 16 Nov 2026 — build blueprint v0.4 (after three red-team passes), specs B01–B22, founder handbook; V2-D47–D50 locked (awaiting gate G0)

- **Founder asked for** a build skeleton with line diagrams, session-sized builds, automated build-and-check loops in place of the chat → paste → Claude Code relay, a handbook, and a re-audit of v1. Nothing here is adopted until the founder approves gate G0.
- **New folder `docs/v2/build/`:**
  - `BLUEPRINT.md`: eight diagrams (the whole machine top to bottom, the evidence ladder, the order path, the seal, where things run, the build loop, branches, the build ladder); the build system (roles, ticks, five layers of checking, walls vs tripwires vs guard rails, brakes, size classes, model routing, money); when each outside component enters; **54 builds and 6 gates planned to the end of the acceptance test**.
  - `specs/B01`–`B22` (full) with `specs/README.md` (rules for every builder and reviewer); `BUILD_CARDS.md` for B23–B54; `LADDER.yaml`; `LEDGER.md`; `V1_CARRYOVER.md`; `HANDBOOK.md`; `gates/G0-redteam.md`, `gates/G0-report.md`.
- **Red team** (founder: yes; each pass a separate agent on a different model that had not seen the plan being written). Everything is in `gates/G0-redteam.md`.
  - **Pass 1, on v0.1: do not adopt.** 25 findings (3 blockers, 16 major, 6 minor).
    - *The builder could approve and merge its own work; the checks ran from the pull request's own code; any build could edit the master doc.* Redesigned.
    - *Four known answers were wrong or would fail a correct build by chance* (the laundering pair without skew and kurtosis; the generator's planted-Sharpe check; the bootstrap band at 5,000 resamples; a [20, 80] band on a uniform rank). Corrected against v1 by running it.
    - *Design errors in the trial store* (a status that could never change in an append-only table; lineage wider than V2-D34 allows; a duplicate check that couldn't work). Redesigned: trials are registered at start with an append-only event log; lineage is the hypothesis plus direct siblings; a `trial_key` identifies the same try across hypotheses.
    - *Two builds were too big and three jobs had no build.* Phase 0 is now five builds (was three); added file loaders (B15), a sabotage tool (B22), and the full Kraken history load (B42). Builds renumbered: 49 → 54.
  - **Pass 2, on v0.2: do not adopt, for the loop's enforcement only.** 18 findings (1 blocker, 14 major, 3 minor). Every number it re-ran matched. The blocker: the redesigned checks used a GitHub event that would never have run them (designed from memory; confirmed wrong on GitHub's changelog). Redesigned as v0.3: checks on the ordinary pull-request event with code and spec from the base commit; the automation's own GitHub account at B05; GitHub's rules attacked before they are trusted; "wall" claimed only where an attack test exists.
  - **Pass 3, on v0.3, builds B02–B05 only: adopt with fixes.** Two blockers (an approval on the working line survived later pushes; the first move of `main` could never pass its own check) and several major findings, all corrections to the text of four specs. Applied as v0.4. **Its report text was not kept across an interruption; the record of it is reconstructed from the changes made.**
  - **Not done:** the v0.4 fixes have not been attacked. The next real test is on GitHub: B03's first step and B05's twelve attack tests.
- **Locked by the founder (16 Nov, "it's a go"):** V2-D47 (data layer in step 2), V2-D48 (one standard input for the edge check), V2-D49 (T-a1 and T-c expectations pre-registered), V2-D50 (engine-independent step-5 builds may start early). P-16–P-19 closed. **Not locked:** P-20 (second reviewer from another AI family): the founder left the call to Claude; Claude's call is a trial from G1, which the founder confirms at G1 before any money is spent.
- **Founder facts and instructions (16 Nov):** the Mac is 16 GB memory, 256 GB storage (master doc §3 said 512 GB; O-6 closed). The US$100 month-one cap is not hard: Claude says where more spend buys something clearly better (blueprint 2.9, handbook §6). On Claude's first such recommendation (Claude Max from B01) the founder said: not now, maybe in a couple of months; the plan runs on Pro and G1 revisits it with measurements.
- **New for the founder:** proposal **P-21** (server and free collectors from G2 instead of after the spike; amends V2-D30; Claude's view: small gain); open question **O-14** (does a chain of sibling hypotheses share one sealed look?).
- **Rule files changed, for the founder's approval at G0:** `CLAUDE.md` gets a "Build loop" section (a build writes its report and changelog entry; the master doc is updated at gates). Master doc §14 rule 3 gets the same exception. §9 step 2's strict-rank sentence is restored to its original wording with a clarifying note.
- **v1 re-audit** (all of `src/`, `tests/`, root scripts): the data layer (schema, store, snapshot hash, validate, clean) moves from "reference" to "port" (V2-D47); touchstone *definitions* are separated from their gauntlet-bound runner; trade-shuffle drawdown and round-trip code are ported into sizing. `main` equals `v1-final` on every v1 path [run].
- **Checked by running:**
  - Python 3.14 with numpy, scipy, pandas, pyarrow, duckdb, arch, quantstats, vectorbt, psycopg and NautilusTrader 1.231.0 installs with no conflicts (Linux).
  - Cloud sessions have PostgreSQL 16 and the Claude Code CLI, so database tests and the loop can run there.
  - The mid-rank tie demonstration for build B07: with `numpy.sum`, strict ranking gives a mean rank of 38.9 on identical sums and mid-rank 50.2. **New trap:** Python's built-in `sum()` is compensated since 3.12 and hides the artefact; numpy and running totals don't.
  - The laundering pair with skew and kurtosis passed in: 0.563048882547666 and 0.05423064441493044 (v1's functions on v1's fixture). Without them: 0.56300 and 0.05438.
  - The slippage tape values (exact decimals) and the sabotage toy (11 mutations by hand: 7 caught, 4 survive, 2 of them equivalent).
  - All diagrams render (mermaid-cli).
- **Corrections:**
  - `BUILD_NOTES.md` §4: a true Sharpe of 0.5 needs about **25** years to show, not 18 (v1's own function: 24.73).
  - Master doc §12: the second "O-12" (AGPL) renumbered O-13; §13: content analysis is S1–S35 with `item-analyses-4.md`.
- **Master doc:** header, §1 next step, §2a new row, §3 hardware, §9 step 2, §10 (four founder-instruction rows, V2-D47–D50), §12 (P-16–P-20 closed, P-21, O-6 closed, O-14), §13, §14 rule 3. Next IDs: V2-D52, P-22.
- **Not done:** no v2 code; no loop yet (builds B01–B05); full specs for B23–B54 are written when each phase opens.

---

## 16 Nov 2026 — V2-D46 locked; cheaper-venue check

- **V2-D46 (locked, founder "go with C"):** series that start after the crypto seal (news, recorded trades) get a research window plus their own sealed block. Inside the window, same-date prices are read only through code joined to the series, with footprints. P-13 resolved.
  - Swept: master doc §6, §10 (V2-D38 status), §12; BUILD_NOTES §2; sentiment spec; order-flow dossier.
- **Founder's Mac is on macOS 26:** Nautilus wheels install (BUILD_NOTES §5, COMPONENTS).
- **Venue check** (audit §9): no cheaper Ontario-usable venue. Findings:
  - IBKR's fixed plan still adds exchange fees;
  - Coinbase's Canadian futures are for ≥ USD 5M investors only;
  - NinjaTrader/Tradovate have no Nautilus adapter;
  - spot venues are dearer and can't short.
  - Corrected the "fixed plan includes fees" claim (master doc §3, BUILD_NOTES §5).
  - Added CME exchange fees: MBT is ~⅓ cheaper per BTC than nano once positions reach 0.1 BTC.

---

## 16 Nov 2026 — founder answers to the audit; V2-D45 locked

- **V2-D45 (locked):** v2 is its own `uv` project in its own folder, with its own `pyproject.toml` and lock file; v1's files stay untouched; Python 3.14. Checked on PyPI that Nautilus and every dependency in view (numpy, pandas, scipy, numba, pyarrow, duckdb, psycopg, torch, tick, arch) publish 3.14 wheels. Swept: V2-D29 status, CODEBASE (root `pyproject.toml` row, planned v2 folder), COMPONENTS (Nautilus row), audit §6.
- **New trap (BUILD_NOTES §5):** Nautilus's macOS wheels need macOS 26+ on Apple Silicon.
- **P-14(b) answered:** the founder has more capital available when required. P-14(a) (rounding below one contract) stays open.
- **P-12 note:** founder plans no holds under 15 minutes and 3:1 stops. The answer on why stops don't remove the cost hurdle is recorded in the P-12 row.
- **Strategy rules in a public repo:** founder will change this before real rules exist.

---

## 16 Nov 2026 — pre-build audit

Founder asked for an in-depth audit before §9 step 2. Full report: `docs/v2/research/pre-build-audit.md`.

- **Ran:** v1's stats probe in a fresh `uv` environment from v1's own lock file (Python 3.13): **28/28**. The v1 tests step 2 ports (`tests/statistics`, `tests/moirai`, `test_costs.py`, `test_run.py`): **182 pass**. Port targets confirmed (strict `<` still at `null_bench.py:125`; fragmentation screen in `eligibility.py`).
- **Looked up:**
  - IBKR Canada lists Coinbase nano BTC/ETH including perpetual-style;
  - IB Gateway needs a manual weekly re-login;
  - NautilusTrader 1.231.0 needs Python ≥ 3.12, LGPL.
- **Computed (descriptive, pre-seal 2024 data):** round-trip nano fees ≈ 9.7 bps vs median absolute BTC moves of 12.7 bps (15 min) and 24.4 bps (1 h).
- **Proposals added (§12):**
  - P-12: cost-feasibility check and minimum hold horizon before S-INTRADAY cards;
  - P-13: the crypto seal blocks research on post-seal series (S-NEWS, recorded trades), with three options;
  - P-14: small-capital sizing rounding and the running-cost vs capital check before step 4;
  - P-15: basis check on real nano bars, Jul 2025–Mar 2026.
- **Fixed stale text:**
  - master doc §1 (decisions through V2-D44) and §2c (S1–S35);
  - sentiment spec staleness note (World Monitor, AGPL, P-13);
  - "dates are UTC" added to the header.
- **BUILD_NOTES §5:** IB Gateway weekly re-login trap; nano fees in bps vary with price.
- **Step-2 forks listed for the founder** (audit §6): v2 project layout and package name, Python version, whether strategy rules live in the public repo.

---

## 16 Nov 2026 — news sources: founder decisions

- **S-NEWS sources.** The founder chose to start the source list by **importing World Monitor's news catalog** (757 feeds, tiers, types), observing it, and refining later. Recorded in the master doc §10 (dash row).
  - Its licence is AGPL-3.0. The founder chose to **keep the repo public and accept AGPL-3.0** (O-12 resolved). At import: add the AGPL licence file and keep World Monitor's notices.
  - No files imported yet; that happens with step 4's collectors.
- **Early news recorder declined:** the skeleton (§9 step 2) comes first.

---

## 16 Nov 2026 — V2-D43 and V2-D44 locked; four open questions looked up

- Founder said "yes both" to P-11:
  - **V2-D43:** the spike's five fill tests also run on ml4t-backtest, and every difference is explained (spike criterion (a) amended);
  - **V2-D44:** a startup or reconciliation position mismatch halts trading until the founder clears it (Nemesis and Aletheia rows).
- Looked up instead of deferring (sources in the session; facts tagged in the docs):
  1. **IBKR costs for Coinbase nano:** USD 0.20 commission + 0.10 exchange + 0.01 NFA ≈ 0.31 per contract per side on tiered pricing. O-4 is partly answered; CME's own fees and IBKR's market-data cost are still open.
  2. **Kraken's bulk trade files carry a buy/sell field** (7 columns incl. `type` b/s and `trade_id`). This corrects the 5 Nov "apparently no side". Updated: master doc §2, BUILD_NOTES §4, COMPONENTS, order-flow dossier.
  3. **Kraken Derivatives isn't available in Canada** (Kraken support). This closes the founder's open check: Kraken stays data-only.
  4. **Nautilus's IBKR adapter** parses futures generically but its venue list has no Coinbase Derivatives entry, and its docs never mention Coinbase. Spike criterion (e) remains a live test (BUILD_NOTES §5).
- Sweep: master doc (§2 rows, §9 step 3, Nemesis, Aletheia, decisions log, §12, IDs); BUILD_NOTES §4, §5, §11; COMPONENTS (IBKR, Kraken, ml4t-backtest); `specs/orderflow-parked.md`; Project handoff and library.

---

## 16 Nov 2026 — order-flow dossier; pre-build sweep

- Founder (15 Nov): keep order flow on the side for now, wanted later; record everything found. New `specs/orderflow-parked.md` gathers it:
  - the data being collected and not collected;
  - the three theses with priors and falsifiers;
  - every tested data rule and trap;
  - the tools (kept and rejected);
  - open checks before unparking;
  - where the evidence lives.
  
  Linked from the master doc (S-ORDERFLOW row, §13), BUILD_NOTES §8 and CODEBASE.
- Pre-build sweep of the S23–S35 findings against the docs:
  - `COMPONENTS.md` gains **quantstats** (adopted in Part 1 but never added there: my omission), and **ml4t-backtest** and **ml4t-diagnostic** as test oracles only.
  - **P-11** proposed (master doc §12): (a) the spike's fill tests also run on ml4t-backtest; (b) a startup position mismatch with the broker halts trading. Not locked; the founder decides.

---

## 16 Nov 2026 — last repo batch S23–S35, Part 4 (order-flow tools) and synthesis

- Pre-registered in `f1ae09f`; results in `research/s23-s35/part4/RESULTS.md`; batch synthesis in `research/s23-s35/SYNTHESIS.md`. **No switch, no proposal, no lock.**
  - **OrderflowChart (S26)** kept as a future viewer: footprint, delta and imbalance from a trade tape with aggressor side are exact, and fast.
  - **flowsurface (S23)**: reference only. Its footprints are exact, but it's GPL, has none of our venues, and its app build needs ALSA.
  - **Rejected:**
    - order-book-heatmap (S24): applies a book with missing updates silently; rounds sizes to the price tick; 13 npm vulnerabilities;
    - NT8 OrderFlowKit (S25): NinjaTrader only, no licence, its quote rule drops inside-spread trades;
    - OrderFlowMap (S27): live side guessed by the tick rule, 78.7% right per trade and 52.6% at 5-trade snapshots; needs a CDN.
- Deviations: Rust 1.97 instead of the pinned 1.95 (not downloadable); ALSA installed for the app build; npm installed with `--ignore-scripts`.
- `BUILD_NOTES.md`:
  - §4: recorders detect gaps; sizes stored at their own precision;
  - §8: write and test the price-bin tie rule; inferred side is not aggressor data; OrderflowChart as the viewer.
- `CHRONOS_V2.md` §1: content analysis 35 items done, batch finished.

---

## 16 Nov 2026 — last repo batch S23–S35, Part 3: ML for Trading (S33), FinRL (S34), gs-quant (S35)

- Pre-registered in `cb70a0a`; results in `research/s23-s35/part3/RESULTS.md`. **No engine or venue switch; no proposal, no lock.**
- **ML for Trading (3rd ed.) and its libraries:**
  - **ml4t-backtest 0.2.0:** 3,162 tests pass. Every fill check passed (next-bar open, fees, gap-through stop at the open, funding to the cent, 0.01 multiplier, 24/7 year, blocking controls). It's the best third opinion for the spike's fill tests.
  - **ml4t-live 0.1.3:** builds only US-stock contracts through IBKR; by default it keeps trading through a startup reconciliation mismatch.
  - **ml4t-diagnostic 0.2.1:** 9,047 tests pass.
    - Its DSR is the 2025 form: it ignores skew/kurtosis against 0, and its rescaling table stops at N = 100. Within size under the null: 2.6% vs v1's 0.0%.
    - RAS used as documented: 100% false finds on noise; 0% standardised.
    - White's Reality Check and purged walk-forward pass.
  - **The book's own crypto case study:** best of 2,807 candidates, validation Sharpe 1.67, deflated Sharpe negative, holdout −44.8% a year.
- **FinRL:**
  - the stock env fills at the observed close;
  - cleaning drops a ticker from all history for a gap at the end;
  - a frame-wide `bfill` copies one ticker's warm-up values to the others;
  - the crypto env is long-only, whole units, no funding;
  - PPO on noise (5 seeds) lost in- and out-of-sample.
- **gs-quant:**
  - the offline backtest's clock guard returns today's date-keyed close at 10:00;
  - the offline engine ignores per-unit transaction cost;
  - TWAP uses (start, end];
  - daily vol is annualised with 252;
  - its MCP server is read-only and needs GS credentials;
  - 2 tests fail only under a New York/Toronto time zone.
- Deviations recorded in RESULTS (timestamp, two harness fixes, test-only installs).
- `BUILD_NOTES.md`:
  - §1: `TZ=UTC` everywhere;
  - §2: DSR variants, RAS units, outside p-value tie rules;
  - §4: no fills across a stacked frame, point-in-time universes, timestamp-level availability guards;
  - §5: ml4t-backtest as third opinion;
  - §11: a reconciliation mismatch must halt.
- `CHRONOS_V2.md` §1 count (30 items) and "Last updated".

---

## 6 Nov 2026 — last repo batch S23–S35, Part 2: pysystemtrade (S30), Zipline (S28), RQAlpha (S29)

- Pre-registered in `bc851d8`; results in `research/s23-s35/part2/RESULTS.md`. **No engine switch; none is a Nautilus fallback; no proposal, no lock.**
  - **pysystemtrade** (GPL-3.0): 103 tests pass + 17 slow examples. Its sizing formula, per-trade cost formula and BTC back-adjustment (74 rolls) reproduce exactly. But:
    - it is daily-only (24/7 data folded into Friday);
    - it has no funding concept and no Coinbase contract;
    - its default cost accounting is smoothed (+6.1% on a BTC run; exact with two defaults off);
    - its trade and position limits clip.
    
    A reference for Themis and roll arithmetic only.
  - **Zipline:** the original no longer installs. zipline-reloaded passes 3,313 tests and every fill, cost, volume-cap, short and no-peeking check. Its 24/7 BTC run crashed at the year end and needed three workarounds. It is equity-first, with no IBKR futures path.
  - **RQAlpha:**
    - non-commercial licence;
    - every test failure traces to its data bundle, which downloads over plain HTTP with no checksum and is unpacked without a filter;
    - its validators reject by default, but a backtest-only option fills part of an order instead.
- Deviations recorded:
  - pre-registration header time (05:45 written, 05:35 committed);
  - Z0 on Python 3.8;
  - two Z6 harness fixes;
  - RQAlpha test dependencies added.
- `BUILD_NOTES.md`:
  - §1: HTTPS or checksum for downloads; unpack archives with a filter;
  - §3: Carver's sizing as a Themis known-answer test, and the /16 annualisation trap;
  - §4: business-day resampling stamps weekend prices with Friday's date;
  - §5: pysystemtrade's cost defaults; 24/7 edge-of-run tests for the spike;
  - §11: two systems that clip.
- `CHRONOS_V2.md` §1 content-analysis count (27 items) and "Last updated". `COMPONENTS.md` unchanged (nothing adopted).

## 5 Nov 2026 — decisions V2-D41 and V2-D42 locked

- **Locked by the founder ("lock p9 and p10"):**
  - **V2-D41** (was P-9, from S18): budget guard for paid APIs. Plan → reserve → settle against our own spend ledger; caps $0.50/run, $3/day, $25/month for AI APIs to start; no paid retries; one fixed host; redirects refused; size cap; keys in Keychain or an owner-only file; alerts 50/80/100%, paid collectors stop at 100%. Built in step 4 before any paid collector.
  - **V2-D42** (was P-10, from S18): every trial record stores its data footprint from step 2 (latest timestamp read, data hash, code coordinate, `partial` flag); research MCP answers carry it plus the trial count.
- **Founder instructions:** step 4 loads Kraken's quarterly bulk trade files for BTC/ETH (after checking one real file); no upstream bug report to freqtrade.
- **§11b:** two Skylit rows added (no crypto coverage; vendor MCP servers for research in chat).
- **Updated:** `CHRONOS_V2.md` §1, §2, §4, §8, §9 (steps 2, 4, 8), §10, §11b, §12; `BUILD_NOTES.md` §4, §6, §7; Project docs (handoff, library, read-first). `COMPONENTS.md` and `specs/` checked: no references to change.

## 5–6 Nov 2026 — last repo batch S23–S35, Part 1: vectorbt (S32) and quantstats (S31)

- Founder's last batch before building: 13 repos in four parts (Alpaca, Qlib and OpenAlice dropped). Part 1 pre-registered in `acde253`; results in `research/s23-s35/part1/RESULTS.md`.
- **vectorbt:** maths exact; fast enough for counted sweeps (1,000 variants on 2 years of hourly BTC in ~3–11 s). Five optimistic defaults (same-bar fills, close-only stops, stop exits without slippage, no funding, silent missing Sharpe without `freq`) → a screening wrapper (BUILD_NOTES §2). Stays Leaning; COMPONENTS row updated.
- **quantstats:** formulas exact, offline HTML report works; 252-day default is a trap for crypto (BUILD_NOTES §2). Candidate for Argus reports and for known-answer cross-checks.
- Two harness errors of mine (an expected value, a unit mismatch) were found after the first run, corrected and recorded; no library result changed.

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
