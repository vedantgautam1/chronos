# CLAUDE.md — Chronos (v2)

**Before doing anything, read `docs/v2/CHRONOS_V2.md`.** It is the master document: what Chronos is, what is built and not built, every decision and why, what we rejected and why, the build order, and where everything lives. If this file and the master doc ever disagree, the master doc wins.

Then, for the component you're touching, read its section in `docs/v2/BUILD_NOTES.md` (known traps) and `docs/v2/COMPONENTS.md` (where third-party and v1 code come from). `docs/v2/CODEBASE.md` says what every file in the repo is and whether v2 ports, references or retires it.

## v1 is frozen — do not follow it

Everything in `docs/v1-archive/`, the code under `src/` and `tests/`, and branch `v1-final` is **v1: reference only**. Its rules no longer apply:
- the 11-gate gauntlet;
- gate 4.4 as a reject gate;
- "screens are not trials" (D-07);
- Binance and its 10 bps taker / 1 bps slippage defaults;
- Phase 5/6;
- the Atropos seal plan;
- protected paths everywhere.

Don't extend v1 code. Port pieces into v2 as `COMPONENTS.md` §2 describes. If a request seems to follow v1 rules, say so and ask.

## Hard rules (v2)

1. **LLMs never size positions, never place orders, never decide validation verdicts** (V2-D07). Nothing an LLM produces reaches an order without deterministic sizing and the Nemesis guard. Research code may not import Nemesis.
2. **Every screened variant counts as a trial** (V2-D03). Record runs with an explicit `kind` (SEARCH / VERIFICATION); one hypothesis per sweep, reused across its points.
3. **Costs are always the real venue's full costs.** For crypto: IBKR futures commission + exchange fees + spread + slippage + funding + futures–spot basis. No cost-free path.
4. **No look-ahead.** Strategies see only data with timestamp ≤ now. Non-price data carries `available_at`. LLM outputs are evidence only forward of the model's training cutoff.
5. **Statistical methods enter only with passing known-answer tests;** pass/fail rules are committed before a test runs (V2-D25). LLM memory, yours included, is not a source. Every rank or p-value counter uses mid-rank ties (V2-D21).
6. **No high-frequency trading** (V2-D22): no sub-minute holds, order-book/queue strategies, market making or latency-dependent edges.
7. **Protected changes — show the diff and wait for the founder's approval:** validation thresholds, risk limits, promotion of any strategy to live (V2-D11). Everything else moves normally.
8. **Read files fresh before editing. Never loosen a test to make it pass.** "Tests green" ≠ "it works": run the end-to-end path after structural changes.
9. **Stop and flag** when a change forks into non-equivalent options, or when a request conflicts with the master doc. Present the options; the founder decides. Only the founder locks decisions.
10. **No seed shopping, no verdict-fitting.** State asymmetric findings asymmetrically.

## Conventions

tz-aware UTC everywhere · half-open `[start, end)` ranges · Decimal for the money ledger, float64 for series maths · every money amount is configuration (capital-agnostic) · `uv` for the environment · run third-party or downloaded code with `python -I` from outside its folder.

## Build loop (from gate G0)

Builds follow `docs/v2/build/`: the build's spec (`specs/Bnn-*.md`) and the rules in `specs/README.md`. If a spec and the master doc disagree, the master doc wins and the build halts.

- **In a build or review session, the end-of-session list below is replaced** by the build report (`docs/v2/build/reports/`) and one `CHANGELOG.md` entry. A build never edits the master doc, a spec or the ladder. It edits this file, `.claude/`, the guards, a workflow, `v2/pyproject.toml` or a protected value only if its own spec lists that path (a few builds do, and their pull requests need the founder's review). The master doc is updated at gates, from the reports, in a pull request the founder approves.
- **Unattended sessions never merge into `main`, never approve a pull request, and never change a founder-owned file.** A scheduled prompt is not the founder's approval.
- Builder and reviewer are different sessions. The session that wrote the code doesn't review it.
- Never create a `CLAUDE.md`, `AGENTS.md` or `.claude` folder below the repository root.

### The commands, and who runs the work (built in B04)

Four commands, all prefixed `chronos-`. **`/status` and `/resume` are built-in Claude Code commands and a skill cannot take a name a built-in already uses**, so every Chronos command carries the prefix — one rule to remember, and it stays safe if a later version adds a built-in `/tick` or `/halt`. Typing `/chronos-` filters the menu to exactly these four.

| Command | What it does |
|---|---|
| `/chronos-tick` | One action, then stop: fetch, ask `v2/tools/loop/next_action.py` what is next, refuse if this session is on the wrong model, take the lock, dispatch the named agent, release the lock, print the status report. It never chooses the action itself and **never merges into `main`**. |
| `/chronos-status` | Where things stand, in three plain sentences. Reads only. |
| `/chronos-halt` | Opens a `chronos-halt` issue: every session, scheduled or by hand, then refuses to act. |
| `/chronos-resume` | Turns the loop back on — and **never closes a `chronos-halt` issue**. Only the founder's own account lifts a stop. |

The commands are `.claude/skills/chronos-*/SKILL.md`, over one shared helper, `.claude/skills/chronos-tick/loop_cli.py`. **The agents are defined in `.claude/agents/`**: `chronos-builder-opus.md` and `chronos-builder-sonnet.md` (same body, different `model`), `chronos-reviewer.md` and `chronos-auditor.md`, both Opus. Each pins its own `model` — never `fable`, never `inherit`, never omitted — so the model an action runs on comes from the agent definition rather than from whatever the calling session happens to be. Dispatch is a Task-tool call with `subagent_type`; running `claude <agent-name>` in a shell does not work.

Templates for the documents each role writes are in `docs/v2/build/templates/`.

## At the end of every session

*(Sessions outside the build loop: planning, research, content analysis, gate write-ups.)* In the same commit as the work:
- **Update `docs/v2/CHRONOS_V2.md`:** the status board (§2) for anything whose status changed; the decisions log (§10) **only** for decisions the founder locked; open questions (§12); "Last updated".
- **Add any new trap** to `BUILD_NOTES.md`.
- **Add any adopted library** to `COMPONENTS.md`.
- **Add a dated entry to `docs/v2/CHANGELOG.md`** saying what was done; update `docs/v2/CODEBASE.md` if files were added, moved or retired.

The founder is non-technical and works solo: keep the master doc's §1–§2 readable in two minutes, and tell the founder plainly what changed.
