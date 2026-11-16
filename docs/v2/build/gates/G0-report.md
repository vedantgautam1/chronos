# Gate G0 — the build blueprint

**Verdict asked of the founder: adopt this blueprint as the way Chronos v2 gets built.** Merging the pull request that contains this file is the approval. Date: 16 Nov 2026 (UTC).

## 1. What exists now that didn't before

A plan, not code. `docs/v2/build/` holds: diagrams of the whole system; a build loop that replaces the chat-to-paste-to-Claude-Code relay; 54 builds and 6 gates to the end of the acceptance test, of which the first 22 have full written instructions with their pass/fail checks decided in advance; a handbook for you; a file-by-file account of what is kept from v1.

## 2. The weakest parts, first

1. **Nothing here has run.** The loop is a design until builds B01–B05 build it, and B05 is where it is proved on GitHub or isn't.
2. **The first draft was rejected by the red team** (3 blockers, 16 major, 6 minor). All 25 findings are answered (`G0-redteam.md`), but **the answers were written by the same author and have not had a second independent pass.**
3. **Build sizes are estimates.** Past plans of 5 sessions took 12–13. This plan's count already moved from 49 to 54 before a line of code. The ledger measures it from B01; G1 and G2 re-size.
4. **Until B05, the protections are instructions, not walls.** Every Claude session acts on GitHub as you. That is why B01–B05 are done with you present.
5. **Every checker is an AI.** The only checks that aren't are yours at each gate, and a human reviewer if you choose to pay for one at G5 (blueprint 2.9).

## 3. What the red team broke

See `G0-redteam.md`. Short version: a builder could have approved itself; the checks could have been edited by the code they judged; any build could have rewritten the master document; four test answers were wrong or flaky. All redesigned or corrected, with the numbers re-run against v1.

## 4. Decisions

**Already yours, recorded in the master doc §10 (16 Nov):** V2-D47–V2-D51 (were P-16–P-20).

**What merging this pull request also approves** (rule files, shown in the diff):
- `CLAUDE.md`: a new "Build loop" section. A build writes a report and a changelog entry; it never edits the master doc; the master doc is updated at gates in a write-up you approve.
- Master doc §14 rule 3: the same exception. Consequence: between gates, the status board can lag the working branch by up to one phase. `LEDGER.md` shows the live state.
- Protected values are **not** changed by this pull request. The seal dates and stress settings are written into their protected file in build B02, with you present, with exactly the values already locked (V2-D35, V2-D38, V2-D39, V2-D31).

**Waiting for you, not needed today:**
- **P-21:** rent the server at G2 instead of after the spike. My view: a small gain; take it only if the spike slips.
- **O-14:** does a chain of sibling hypotheses share one sealed look? Needed before B46 is specified.
- **Claude Max** for the build months (blueprint 2.9, row 1). My recommendation: yes, from B01.
- P-12, P-14(a) and P-15 from the pre-build audit are still open.

## 5. Numbers

22 full specs · 32 cards · 54 builds · 6 gates · 0 lines of v2 code · 0 builds measured.

## 6. Three things you can check yourself (no terminal)

1. Open `docs/v2/build/LADDER.yaml` on GitHub. The last build is **B54** and the line for **G5** says `needs: [B42, B54]`.
2. Open `docs/v2/build/specs/B02-guards.md`. Find `seal:`. Both dates say **2026-04-01T00:00:00Z**, the date locked in V2-D38.
3. Open this pull request's "Files changed" tab and type `src/` in the file filter. **Nothing under `src/` or `tests/` appears**: v1 is untouched.

## 7. What happens when you approve

Nothing runs by itself. The next step is build B01, by hand, with you: open a Claude Code session on the repository and say *"Do build B01 from docs/v2/build/specs. Follow specs/README.md, builder rules."* (HANDBOOK §2.)
