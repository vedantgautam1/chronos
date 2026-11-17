```yaml
id: B49
title: Change check — is a change to a live strategy really better, and still profitable on its own (V2-D32)
size: M
model: opus
who: loop
needs: [B47]
ticks: 3
touches:
  - v2/migrations/0008_change_check.sql
  - v2/src/chronos2/moirai/change/**
  - v2/tests/moirai/change/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B49 — Change check

## Why
Once a strategy trades, people want to improve it. The danger is quiet: against a version that is losing money, **any change that simply trades less looks better**, every time, because it pays fewer costs. In S12's test (no edge anywhere, 2× costs, 12 tries) the paired comparison alone accepted a change in 40% of worlds; adding "the change must make money on its own" brought that to 0% [Certain — S12 run]. The prototype for this spec shows the same trap more starkly: 95% accepted on the comparison alone, 0% with the rule. This build is the change check with that rule built in, and with the opposite bias removed too: S1's version only accepted changes that traded less and drew down less, so it could never accept a better change that trades more.

## Read first
- Master doc §6 "Change check"; §10 V2-D32, V2-D35, V2-D39. `BUILD_NOTES.md` §2 on S1's paired test (its autocorrelation check) and the Šidák bar.
- Specs B06 (`newey_west`), B10 (hypotheses, SEARCH trials, `search_n`), B47 (C3 cost runs, `freeze`, protected file).

## The rules (fixed here)

**What is compared.** The live version and the candidate are run on **the same window and the same data**, both at **2× frictions** (V2-D35), producing daily net P&L series `L` and `C`, aligned by date. Days on which neither trades count as zero for both.
- **The window**, for now: the candidate trial's own research window, read with `purpose="research"`, so never past the seal. *Open question for the founder (proposal P-22 (g)):* once a strategy is live in 2027, comparing changes only on pre-seal data gets stale, and reading post-seal data needs a rule V2-D38 and V2-D46 don't give yet. A change check asked for a window past the seal halts.
- **No look-ahead report, no comparison:** the candidate version must have a passing B44 report (`has_passing_report`), checked before anything is read (red team F16: a look-ahead bug is the classic way an "improvement" beats the live version).
- **One check per candidate:** a unique constraint on the candidate trial refuses a second `change_config` for it, and the window is the candidate trial's, so windows can't be shopped.

**Every candidate is counted.** Each proposed change to a live strategy is a SEARCH trial under one hypothesis per live strategy, "changes to <strategy>", registered when the live version goes live. `k` = that hypothesis's `search_n`, counting every change ever tried, accepted or not.

**The test.** `d = C − L`; `t = mean(d) ÷ sqrt(S ÷ T)`, with `S = newey_west(d, m)`, `m = ceil(T^(1/3))` (v1's lag rule) [Certain — read]. The bar is Šidák over the cumulative count: `z(k) = Φ⁻¹(c^(1/k))`, where `c` is `change_check.confidence` (0.95) read from the protected file B47 created. The comparison passes if `t > z(k)`.

**The decision**, in this order:
1. The live version's net at 2× over the window is ≤ 0 → **`RETIREMENT_REVIEW`**. No change is accepted. *(Design choice, for the founder: the locked text says "open a retirement review instead of accepting a less-bad change". This spec reads it strictly: while the live version loses, no change is accepted, however good; a replacement that is really profitable goes through the full edge check as a new strategy, which is the stronger test. The looser reading, "accept a candidate that passes everything else on its own", is a one-line change; the founder's call.)*
2. The candidate's net at 2× ≤ 0 → `REJECT` (V2-D32).
3. Where funding applies, the candidate's adverse-funding run ≤ 0 → `REJECT`.
4. The comparison fails → `REJECT`.
5. Anything needed is unavailable (e.g. the adverse funding level isn't set) → `INCOMPLETE`. Every fail is checked before any gap, as in B47 (red team F16).
6. Otherwise → `ACCEPT`.

**What is never a condition:** that the candidate trades less, holds less, or draws down less than the live version. A test asserts that no field of turnover or drawdown is read by `decide`.

The configuration (both versions' trial ids, the window, `k`, the protected values' hash) is frozen and hashed before the run, as in B47, and stored with the verdict.

## Deliver
1. Reads `change_check.confidence` through B47's `load_edge()`; this build changes no protected file.
2. `0008_change_check.sql`: `mnemosyne.change_config`, `mnemosyne.change_verdict` (append-only, hashed, journaled).
3. `moirai/change/`: `paired_series(live_trial, cand_trial)`, `hac_t(d)`, `sidak_bar(k, confidence)`, `decide(...)` (pure), `run_change_check(config_hash)`.
4. Tests.

## Steps
1. Tests (red). 2. `hac_t`, `sidak_bar`. 4. `decide`. 5. Migration, freeze and run. 6. The simulated worlds. 7. Report.

## Known answers and checks

**Šidák bar** (1e-12) [Certain — run, 16 Nov]: `z(1) = 1.6448536269514722`, `z(2) = 1.9545083272139914`, `z(12) = 2.630312646175007`, `z(100) = 3.2834075352738954`.

**HAC t** [Certain — run, 17 Nov]. On `d = [1, −1] repeated 50 times, plus 0.1` (T = 100): `m = 5`, `newey_west(d, 5) = 0.01` and `t = 10.0` (both to 1e-9), while the plain t is `0.99499` (5 places). The alternating series has strong negative autocorrelation, so the long-run variance is far smaller than the daily one. A second test on a series with strong positive autocorrelation shows the reverse: the HAC t is smaller than the plain t.

**The decision table** (`decide`, pure):

| # | Live net 2× | Candidate net 2× | Adverse run | t vs z(k) | Verdict |
|---|---|---|---|---|---|
| 1 | +50 | +80 | n/a | 3.0 > 2.63 | `ACCEPT` |
| 2 | +50 | +80 | n/a | 2.0 < 2.63 | `REJECT` |
| 3 | −10 | +80 | n/a | 3.0 | `RETIREMENT_REVIEW` |
| 4 | −10 | −2 | n/a | 5.0 | `RETIREMENT_REVIEW` (the trap: less bad, still losing) |
| 5 | +50 | −1 | n/a | 5.0 | `REJECT` (V2-D32) |
| 6 | +50 | +80 | −3 | 3.0 | `REJECT` (adverse funding) |
| 7 | +50 | +80 | not set | 3.0 | `INCOMPLETE` |
| 7b | +50 | +80 | not set | 2.0 < 2.63 | `REJECT` (a fail outranks a gap) |
| 8 | 0 exactly | +80 | n/a | 3.0 | `RETIREMENT_REVIEW` |
| 9 | +50 | +80, trading 3× as often as live | n/a | 3.0 | `ACCEPT` (trading more is no obstacle) |

**The count.** A hypothesis "changes to X" with 11 earlier candidates: the 12th is judged at `z(12)`; a 13th registered afterwards raises the bar for itself to `z(13)` and never lowers an earlier one's.

**More refusals.** A candidate without a passing B44 report → refused before reading. A second `change_config` for the same candidate trial → refused (`23505`). A window that ends after the seal → halt-level refusal with the reason.

**Simulated worlds**, generated exactly like this (daily series, T = 500): one market path `m` of standard normals per world, **shared** by live and candidates; live's daily P&L = `side × m + e_L − 0.30`, with `side` ±1 at random each day; candidate j's = on a random half of days `side × m + e_C − 0.30`, else 0, with its own random sides; `e_L`, `e_C` per world below; 12 candidates per world, the j-th judged at `z(j)`. Figures in brackets are the prototype's [Certain — run, 17 Nov]; the red team's independent re-implementation gave 0.952 / 0, 0.860 and 0.003.
- *No edge anywhere* (`e_L = e_C = 0`, seed 49001, 500 worlds). Note: here the full rule's 0 comes from rule 1 alone (the live version always loses), so this world shows the trap, and decision-table row 5 is what tests rule 2. The comparison alone accepts at least one candidate in **at least 75%** of worlds [0.952]; the full rule accepts in **0** [0]. Asserting both shows the trap is real in the fixture and the rule closes it. These are the locked V2-D32 fixtures: a zero-edge live version losing at 2×, a candidate trading half as often → never `ACCEPT`, and `RETIREMENT_REVIEW` whenever live is net negative.
- *A real improvement* (`e_L = 0.35`, `e_C = 0.90`; seed 49003, 300 worlds). Accepted in **at least 75%** of worlds [0.857]. The rest are mostly worlds where noise put the live version below zero, which the strict reading sends to retirement review.
- *Same edge, trades less* (`e_L = e_C = 0.35`; seed 49004, 300 worlds). Accepted in **at most 5%** [0.000].

## Not in this build
Running the paired versions (the caller provides both trials, from B43 now, the real engine later) · the edge-decay alarm on live strategies (V2-D37, a later build) · what happens in a retirement review (the founder decides).

## Halt if
- B06's `newey_west` doesn't match v1's for the HAC case above.
- `change_check.confidence` isn't in B47's protected file.
- A band is missed by code that passes the decision table: report the numbers; don't change seeds or bands.

## For the gate
`COMPONENTS.md` §2 (this build edits it): "Change check — built in B49 with V2-D32". Open question for the founder: the strict or the loose reading of rule 1 (see "The decision").
