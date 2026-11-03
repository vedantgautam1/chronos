# Chronos

A personal systematic trading system: crypto first (BTC/ETH intraday, long and short, via IBKR futures), then forex, then equities. Honest validation decides which strategies get capital, and capital grows in steps as live evidence builds.

**Start here: [`docs/v2/CHRONOS_V2.md`](docs/v2/CHRONOS_V2.md)** — the master document. It covers what is built and what isn't, every decision and why, what was rejected and why, the build order, and where everything lives.

| Folder / file | What it is |
|---|---|
| `docs/v2/CHRONOS_V2.md` | Master document (read first) |
| `docs/v2/BUILD_NOTES.md` | Known traps, by component |
| `docs/v2/COMPONENTS.md` | Where every third-party and reused piece comes from |
| `docs/v2/specs/` | Detailed specs (Kronos shadow signal, news/sentiment strategy) |
| `docs/v1-archive/` | Frozen v1 documents (reference only) |
| `src/`, `tests/` | Frozen v1 code (tag `v1-final`); v2 ports pieces from it |
| `CLAUDE.md` | Rules for Claude Code sessions |

v1 (Jul–Aug 2026) was a validation instrument with an 11-gate gauntlet and no live path; it is frozen under the git tag `v1-final`. Its original README is at `docs/v1-archive/README-v1.md`.
