# CHANGELOG — what was done, when

Dated work log. **Decisions** and their reasons live in `CHRONOS_V2.md` §10 (and what we won't do in §11); this file records the **work**: what changed, where, and what it was based on. Newest first. Every session adds an entry (CHRONOS_V2 §14 rule 7).

---

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
