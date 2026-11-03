# CLAUDE.md — Chronos (v2)

**Before doing anything, read `docs/v2/CHRONOS_V2.md`.** It is the master document: what Chronos is, what is built and not built, every decision and why, what we rejected and why, the build order, and where everything lives. If this file and the master doc ever disagree, the master doc wins.

Then, for the component you're touching, read its section in `docs/v2/BUILD_NOTES.md` (known traps) and `docs/v2/COMPONENTS.md` (where third-party and v1 code come from).

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

## At the end of every session

In the same commit as the work:
- **Update `docs/v2/CHRONOS_V2.md`:** the status board (§2) for anything whose status changed; the decisions log (§10) **only** for decisions the founder locked; open questions (§12); "Last updated".
- **Add any new trap** to `BUILD_NOTES.md`.
- **Add any adopted library** to `COMPONENTS.md`.

The founder is non-technical and works solo: keep the master doc's §1–§2 readable in two minutes, and tell the founder plainly what changed.
