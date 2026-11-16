# S18 Skylit — checks written before running (V2-D25 rule 2)

Written 2026-11-05 19:20 UTC, before any Skylit code was run.

## What was fetched

| Repo | Commit | Licence |
|---|---|---|
| SkylitAI/skylit-mcp | `b720b03c9ea249e5e28d61aee5d528890217576c` | MIT (code/docs only; data, server and APIs excluded by NOTICE) |
| SkylitAI/skylit-agent-kit | `0e7b06851189c81f9402d4b66951599c24c77283` | MIT |
| SkylitAI/skylit-agent-lab | `cf6e66f38f0f04f3801236c131f79024eed105c6` | MIT |

Cloned into a separate folder outside this repo. Run with `python -I`, from outside each repo's folder. No Skylit account or API key is used; nothing in this check spends credits or contacts Skylit.

## Why these checks and not others

Skylit is a paid data service for **US equity and index options** (flow, dealer positioning, volatility, dark pool). The service and its calculations are not in these repos (the MCP repo says it holds no server code). So the claims that would matter most to Chronos (is the data accurate, does it predict anything) **cannot be tested here** without a paid key. That is recorded as a gap, not checked.

What can be tested is the open code's own safety claims, which matter only if we ever borrow its patterns for our own data collectors or research MCP server (V2-D19):

## Checks and pass/fail rules

**C1 — the shipped test suites pass.**
Run each repo's documented unit-test command (`python -I -m unittest discover -s tests`), with the repo as working directory only where the suite requires it.
Pass: 0 failures and 0 errors in both agent-kit and agent-lab. Anything else is reported as found.

**C2 — "offline" modes make no network connection.**
Run each documented offline command under a wrapper that replaces `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo` with functions that record the attempt and raise.
Commands:
- agent-kit: `doctor`, `endpoints`, `endpoint heatseeker.getHeatmap`, `use-case node-tracker`, `use-case price-levels`, `use-case flow-investigator`, `use-case volatility-context`, `watchlist --dry-run`, `sample`;
- agent-lab: `experiments/journal-reviewer/run.py`, `experiments/market-brief/run.py`, `templates/experiment/run.py`.
Pass: 0 recorded network attempts across all commands. Exit status reported separately (a non-zero exit with 0 network attempts still passes C2).

**C3 — live mode without a key does not reach the network.**
With no `SKYLIT_API_KEY`, no stored key, and stdin not a terminal, run `endpoint heatseeker.getHeatmap --param symbols=SPY --param metric=gamma --live` and `watchlist --live` under the same wrapper.
Pass: 0 recorded network attempts and a non-zero exit or explicit refusal message.

## What would change the verdict

None of C1–C3 can make Skylit useful to the current crypto track. They only decide whether its client-side safety patterns are worth noting for our own collectors and MCP server. The relevance verdict rests on reading the API specs (coverage, history depth, licence), recorded in the item notes.
