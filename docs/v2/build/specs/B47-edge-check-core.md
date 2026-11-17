```yaml
id: B47
title: Edge check I — frozen configuration, the decision table for all six criteria, evidence for criteria 1–3
size: M
model: opus
who: loop             # merges only with the founder's approval: it creates a protected file
needs: [B44, B46]
ticks: 3
touches:
  - v2/migrations/0006_edge_check.sql
  - v2/src/chronos2/moirai/edge/**
  - v2/src/chronos2/core/protected.py
  - v2/config/protected/edge_check.yaml
  - v2/tests/moirai/edge/**
  - v2/tests/core/test_protected_edge.py
  - v2/tests/mnemosyne/test_looks_with_configs.py
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B47 — Edge check I: the decision core

## Why
The edge check is the centre of Chronos: the one place that says "this strategy has shown an edge" or "it hasn't". Three things make such a verdict worth something, and this build is those three. **The rules are frozen before the result is seen** (choosing the test after the result raised false passes of a useless idea from 0.24% to 12.6%, BUILD_NOTES §2). **The decision is a plain table that code applies**, never a judgement (hard rule 1). **Every number the table needs is gathered by code that can be checked on its own.** This build writes the whole decision table, for all six criteria, and gathers the evidence for the first three. B48 gathers the other three.

## Read first
- Master doc §6 (all of it); §10 V2-D03, V2-D08, V2-D25, V2-D34, V2-D35, V2-D38, V2-D39, V2-D48.
- `BUILD_NOTES.md` §2: "Freeze and hash the edge-check configuration", "Positive at 1× and 2× costs", "Every edge-check criterion needs a fixture it alone catches", "DSR/PSR take the non-annualised Sharpe".
- Spec B44 (`has_passing_report`). Specs B06 (`dsr`, `per_bar_sharpe`, `sample_skewness`, `sample_kurtosis`, `years_to_significance`), B10 (`search_n`, trial kinds), B11 (`TrialResult`, `Trade`), B16 (`stress`), B18 (`fragmentation_warning`).

## The rules (fixed here)

**The six criteria** are the master doc's (§6), in its order: C1 data sufficiency · C2 DSR at honest N · C3 positive after costs · C4 beats the random-entry null · C5 neighbourhood is not a lone spike · C6 confirmed by one look at the sealed block.

**Pass marks.** Numbers the master doc uses but never wrote down, written into a new protected file, `v2/config/protected/edge_check.yaml`. They are validation thresholds: **the founder approves them by approving this spec (proposal P-22) and, again, this build's pull request.** Every key the later builds need is in it from the start, so the file doesn't change after B47 (a change would make every frozen config unrunnable, red team F11).

| Key | Value | Where it comes from |
|---|---|---|
| `dsr_pass_mark` | `0.95` | v1 `configs/gauntlet/v001.json`, `thresholds.dsr.confidence` [Certain — read] |
| `dsr_min_returns_share` | `0.90` | new: the share of the hypothesis's SEARCH trials that must have complete stored returns before V is trusted (red team F8) [Guessing — a starting value for the founder] |
| `null_alpha` | `0.05` | v1 `null_bench.percentile_gate: 95`, restated as a p-value [Certain — read] |
| `null_min_draws` | `1000` | V2-D21 ("at least 1,000 draws") |
| `data_sufficiency.alpha`, `.power` | `0.05`, `0.80` | the defaults of v1's `atropos_years` [Certain — read] |
| `neighbourhood_rule` | `null` | chosen at gate G5 (V2-D20). While it is `null`, C5 is unavailable and no strategy can pass |
| `lone_spike.frac`, `.min_neighbours` | `0.25`, `3` | new: when a candidate counts as a lone spike (B48), which fails C5 (red team F25) [Guessing — a starting value for the founder] |
| `change_check.confidence` | `0.95` | the Šidák level for the change check (B49), shipped here so the file never changes later |

`sealed_confirm_min_trades: 200` already lives in `validation.yaml` (B02, V2-D38).

**C1, data sufficiency.** The idea states, before any of its trials starts, the smallest net annual Sharpe at which it would be worth trading: `target_sharpe_annual`, written once into `mnemosyne.hypothesis_target` (a trigger refuses it if the hypothesis already has a trial, and it can't be changed). The config reads it from there; nobody types it at freeze time (red team F9). `years_needed = years_to_significance(target_sharpe_annual, alpha, power)`; `years_available = n × step ÷ 365.25 days`, from the candidate's own return calendar. If `years_available < years_needed`, the verdict is `INSUFFICIENT_DATA` and nothing else is judged. It is not a fail: the history is too short to answer, either way. *(Design choice, for the founder: the alternative is to use the Sharpe the backtest produced. That is circular, because it lets the result decide whether the test was fair. Overstating the target to get past C1 gains nothing: C2 is still judged on the real returns.)*

**C2, DSR.** On the candidate's net returns at 1× costs, at their own bar frequency, not annualised: `sr_hat = per_bar_sharpe`, `T = n`, sample skewness and kurtosis from the same series. `N = search_n(hypothesis)` (every SEARCH trial, whatever became of it).
- **N = 1:** C2 is PSR against zero, `dsr(sr_hat, T, V, N=1, skew, kurt)` with any positive V (it doesn't depend on V when N = 1); V is not computed. *(Red team F1: B06's `dsr` returns NaN for V = 0, which would silently fail every single pre-registered idea.)*
- **N > 1:** `V` = the sample variance (`ddof=1`) of `per_bar_sharpe` over the hypothesis's SEARCH trials that have complete stored returns, the candidate included. If fewer than `dsr_min_returns_share × N` trials have complete returns, C2 is **unavailable** (red team F8: a variance taken from two near-identical trials makes the penalty for N vanish).
- Pass: `dsr >= dsr_pass_mark`. The same number at the lineage's union N (B18) is reported and never decides.

**C3, costs** (V2-D35), on the candidate's trades, in Decimal:
- `net_x1 = Σ (gross_pnl − commission − exchange_fee − regulatory_fee − spread − slippage − funding − basis)`
- `net_x2` = the same with B16's `stress(…, "x2_frictions")` applied to each trade: frictions multiplied by the protected `stress_friction_multiplier` (2.0), funding and basis unchanged. One source for the multiplier.
- `net_adverse`, only where the venue's contract has funding: frictions at 1×, and funding replaced by B16's `stress(…, "adverse_funding")`. If the adverse level isn't set yet, it is unavailable.
- Pass: all of those that apply are `> 0`. (`net_x1 > 0` can never fail on its own when frictions are non-negative. It is kept because the master doc states it, and noted here as deliberate redundancy.)

**C4, C5, C6** take their numbers from B48 (the null's p-value and draw count; the neighbourhood rule's result; the sealed block's trade count and net results). Their pass rules are fixed here: C4 `null_p <= null_alpha` with `null_draws >= null_min_draws` · C5: if `neighbourhood_rule` is `null`, C5 is **unavailable**, whatever the grid (this is checked first, red team F24); otherwise the active rule says pass, and a lone spike (as defined by the protected `lone_spike` keys) is a fail **and** opens a look-ahead review · C6 at least `sealed_confirm_min_trades` trades in the sealed block, `net_x2 > 0` there, and `net_adverse > 0` there where funding applies.

**The verdict**, decided in this order:
1. C1 fails → `INSUFFICIENT_DATA`.
2. Any of C2–C5 fails → `FAIL`, even if another is unavailable.
3. Any of C2–C5 unavailable → `INCOMPLETE` (it names what is missing).
4. C2–C5 all pass and no look has been taken → `PENDING_SEALED_LOOK`. **This is the only state in which a sealed look may be requested.** A look is never spent on a candidate that has already failed.
5. The look was refused because the lineage already used it (B46) → `LOOK_SPENT`.
6. The sealed run errored → `INCOMPLETE` (reason `sealed_run_errored`). The look stays spent; nothing retries by itself; the founder decides.
7. Fewer sealed trades than the minimum → `DEFERRED_TO_PAPER` (V2-D38).
8. C6 passes → `PASS`; otherwise `FAIL`.

**One final verdict per config.** A unique index allows one `final` row per config. Running a config that already has a final verdict returns that verdict and writes nothing (red team F10).

Warnings (subperiods, trade count, capacity, fragmentation) are carried in the verdict record and can never change it.

**Frozen configuration.** An `EdgeConfig` holds: hypothesis id, candidate trial id, the research window (**equal to the candidate trial's window**: nothing else is accepted), `target_sharpe_annual` (from `hypothesis_target`), the venue, the null's draw count, the null's seed (**derived** from the hash of all the other fields, never chosen), `look_end` (the end of the sealed look this candidate would get; at most the moment of freezing and after the seal date), the code coordinate, and the content hash of both protected files. `freeze()` stores it in an append-only table and returns its hash.
- **One config per candidate:** a unique constraint on (hypothesis id, candidate trial id) refuses a second freeze for the same candidate (red team F9: otherwise seeds, windows and targets could be shopped).
- `run_edge_check(config_hash)` is the only way to run, and it takes nothing but the hash. A verdict row has a foreign key to its config row. If the protected files' hash at run time differs from the frozen one, the run is refused.
- **The look belongs to the config:** this build's migration adds the foreign key from B46's `sealed_look.edge_config_hash` to `edge_config`, and a trigger that refuses a look unless that config has a `pre_look` verdict of `PENDING_SEALED_LOOK` (red team F5).

## Deliver
1. `v2/config/protected/edge_check.yaml` with exactly the keys in the table, and `load_edge()` in `core/protected.py` (frozen object + content hash; an unknown key raises).
2. `0006_edge_check.sql`: `mnemosyne.hypothesis_target`; `mnemosyne.edge_config` (`config_hash` primary key, `hypothesis_id`, `candidate_trial_id` unique together, `payload jsonb`, `created_at`) and `mnemosyne.edge_verdict` (`config_hash` foreign key, `stage` in `pre_look|final`, `verdict`, `criteria jsonb`, `evidence jsonb`, `warnings jsonb`, `created_at`); both append-only, hashed and journaled with B09's machinery.
3. `moirai/edge/config.py` (`EdgeConfig`, `freeze`, `load_frozen`), `evidence.py` (`Evidence`: a frozen record of plain numbers, one group per criterion, each group optional), `criteria.py` (one pure function per criterion returning `pass | fail | unavailable` and a one-line reason), `decide.py` (`decide(evidence, edge, validation) -> Verdict`, pure, no I/O).
4. `moirai/edge/gather.py`: `gather_c1`, `gather_c2`, `gather_c3` from the store and the cost model. `moirai/edge/run.py`: `run_edge_check(config_hash)`, which gathers C1–C3, leaves C4–C6 empty (so every real run ends `INCOMPLETE` until B48), decides, and stores the verdict.
5. Tests.

## Steps
1. The decision table and the known answers below, as tests (red). 2. Protected file and loader. 3. Migration; `config.py`. 4. `criteria.py`, `decide.py` → the table is green. 5. `gather.py`, `run.py`. 6. Report.

## Known answers and checks

**The decision table** (`decide`, pure). Unless a row says otherwise: years 8.0 available, 6.18 needed; `dsr 0.97`; `net_x1 +7`, `net_x2 +3`, no funding; `null_p 0.01` with 1,000 draws; rule `test_rule` passes, no lone spike; sealed: 250 trades, `net_x2 +2`.

| # | What differs | Verdict |
|---|---|---|
| 1 | nothing | `PASS` |
| 2 | 6.0 years available | `INSUFFICIENT_DATA` |
| 3 | row 2, and `dsr 0.10`, `net_x2 −5` | `INSUFFICIENT_DATA` (nothing else is judged) |
| 4 | `dsr 0.949999` | `FAIL` (only C2) |
| 5 | `dsr 0.95` exactly | `PASS` |
| 6 | `net_x2 −1` (with `net_x1 +7`) | `FAIL` (only C3) |
| 7 | funding applies; `net_adverse −1` | `FAIL` (only C3, adverse run) |
| 8 | funding applies; adverse level not set | `INCOMPLETE` |
| 9 | `null_p 0.0501` | `FAIL` (only C4) |
| 10 | `null_p 0.05` exactly | `PASS` |
| 11 | `null_p 0.01` with 999 draws | `INCOMPLETE` |
| 12 | rule says fail, no lone spike | `FAIL` (only C5); `lookahead_review_required` false |
| 13 | lone spike | `FAIL`; `lookahead_review_required` true |
| 14 | `neighbourhood_rule` is `null` | `INCOMPLETE` |
| 14b | `neighbourhood_rule` is `null`, single pre-registered point (N = 1, no grid) | `INCOMPLETE` (the null rule is checked before the grid) |
| 15 | row 14, and `dsr 0.10` | `FAIL` (a fail outranks a gap) |
| 16 | no sealed evidence yet | `PENDING_SEALED_LOOK`; `sealed_look_allowed` true |
| 17 | row 4, no sealed evidence | `FAIL`; `sealed_look_allowed` false |
| 18 | look refused | `LOOK_SPENT` |
| 19 | sealed: 199 trades | `DEFERRED_TO_PAPER` |
| 20 | sealed: 200 trades, `net_x2 −0.01` | `FAIL` (only C6) |
| 21 | funding applies everywhere; sealed `net_adverse −1`, all else positive | `FAIL` (only C6) |
| 22 | `N > 1` and `V` unavailable | `INCOMPLETE` |
| 22b | sealed run errored | `INCOMPLETE`, reason `sealed_run_errored` |
| 23 | row 1, with all four warnings raised | `PASS` (warnings never decide) |

Rows 4, 6, 7, 9, 12, 20 and 21 are the "one fixture that only this criterion catches" the master doc asks for.

**C1 numbers.** `years_needed` for targets 0.5, 1.0, 1.5, 2.0: `24.730228928079065`, `6.182557232019766`, `2.7478032142310074`, `1.5456393080049415` (1e-12) [Certain — run on v1's function, 16 Nov]. A daily calendar of 2,922 bars is `8.0` years; 2,191 bars is `5.9986…` years and is insufficient for a target of 1.0.

**C2 numbers** [Certain — run on v1's functions and v1's committed fixture, 16 Nov]. With `sr_hat = 0.0024061391952578497`, `T = 4344`, `skew = 0.7203182819604969`, `kurt = 16.842229132109118`, `V = 8.659587301602424e-05`: `dsr` at `N = 280` is `0.05423064441493044`; at `N = 1` it is `0.563048882547666`; both to 1e-12. Both are below 0.95: the laundering pair fails either way, and the honest count is what makes it fail badly.
- **N = 1:** with N = 1, `dsr(...)` gives `0.563048882547666` (PSR against zero) whatever positive V is passed; the code never passes V = 0. A test asserts that calling B06's `dsr` with V = 0 and N = 1 gives NaN, so nobody "simplifies" back to it.
- **`V` from the store:** a hypothesis with five trials: three SEARCH with complete returns, one SEARCH stored as partial, one VERIFICATION. `N == 4`, and only 3 of 4 have returns (75% < 90%) → C2 **unavailable**. Add a fourth complete SEARCH trial (N = 5, 4 of 5 = 80%) → still unavailable. With 9 of 10 complete → available, and `V` equals `numpy.var` (`ddof=1`) of the nine complete SEARCH trials' Sharpes; the test also asserts it differs from the `ddof=0` value and from the value with the VERIFICATION trial included.
- **Honest N end to end, the laundering pair** [Certain — run, 17 Nov]. A hypothesis with a 280-point grid. The candidate is T-e's returns (B20). The other 279 trials are built so their Sharpes are known exactly: `u` = 279 standard normals from `numpy.random.default_rng(47001)`; trial i's Sharpe is `a × u_i` with `a = 0.00993506709770173` (the positive root that makes the variance of all 280 Sharpes equal T-e's V); its returns are `a × u_i + z`, where `z` is 4,344 standard normals from `default_rng(47002)` rescaled to mean 0 and standard deviation 1 (`ddof=1`), so its `per_bar_sharpe` is `a × u_i` to 1e-15. Then: `N == 280`, `V == 8.659587301602424e-05` (relative 1e-12), C2's DSR `== 0.05423064441493044` (1e-12), C2 **fails**, and the stored verdict (C4–C6 still empty in this build) is `FAIL`.

**C3 numbers**, by hand:
- Trade A: gross `+10`; commission 2, exchange fee 1, regulatory fee 0, spread 3, slippage 2; funding `−5` (income); basis 0. `net_x1 = +7`. `net_x2 = 10 − 16 + 5 = −1`. Doubling everything would give `10 − 16 + 10 = +4`: the test asserts the result is `−1` **and is not** `+4` (the V2-D35 fixture).
- Trade B: gross `+20`, the same frictions, funding `−5`. `net_x1 = +17`, `net_x2 = +9`. With an adverse funding charge of 13: `net_adverse = 20 − 8 − 13 = −1`. Fails only on the adverse run.

**Frozen configuration.**
- Inserting a verdict whose `config_hash` isn't in `edge_config` is refused by the database (`23503`).
- `run_edge_check` has exactly one parameter. A test inspects its signature.
- Freeze a config, change one value in a copy of the protected file, run → refused (`ProtectedChanged`); nothing is stored.
- The same config frozen twice gives the same hash and one row. A **different** config for the same candidate (another window, another `look_end`) → refused (`23505`). A config whose window differs from the candidate trial's → refused before storing. The seed in two configs that differ only in `look_end` differs, and nobody passes a seed (no such parameter).
- `hypothesis_target` for a hypothesis that already has a trial → refused (`P0001`); a second target for the same hypothesis → refused.
- A second `run_edge_check` on a config with a final verdict writes nothing and returns the stored verdict. Inserting a second `final` row directly → refused (`23505`).
- **Looks need a pending verdict** (in `test_looks_with_configs.py`): B46's rows 1–4 re-run through real configs; a look for a config whose `pre_look` verdict is `FAIL` → refused (`P0001`); a look for a config with no verdict → refused.
- The 8 attacks (B09) are refused on both tables with B09's error codes.
- `decide` imports nothing that does I/O (same test as B03's).
- **No look-ahead report, no run:** a candidate whose strategy has no passing B44 report for its code coordinate is refused by `run_edge_check` before anything is read or stored.

## Not in this build
Evidence for C4–C6, the warnings, end-to-end worlds (B48) · the basis check (proposal P-15, not yet accepted by the founder) · choosing the neighbourhood rule (B52, B53).

## Halt if
- The protected file would need a key not in the table above.
- B46's `sealed_look` table can't take the foreign key and trigger without changing B46's migration (then the design needs the founder).
- The size budget won't hold (propose: `gather.py` and `run.py` move to a follow-up build).

## For the gate
`COMPONENTS.md` §2 (this build edits it): new row "Edge check — decision core built in B47". Status board: Moirai edge check → in progress. For the founder: the three pass marks above are now in a protected file.
