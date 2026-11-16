```yaml
id: B20
title: Touchstones as pre-registered fixtures (written down, not run)
size: M
model: opus
who: loop             # merges only with the founder's approval: it creates founder-owned files
needs: [B19, B06]
ticks: 3
touches:
  - v2/src/chronos2/fixtures/**
  - v2/tests/fixtures/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B20 — Touchstones as pre-registered fixtures

## Why
A touchstone is a test strategy whose right answer we know because we built the world it trades in. The validation redesign isn't "done" until the new checks give the right answer on all of them (master doc §6, V2-D08). The discipline that makes this worth anything: **the expected answers are written down now, before the checks exist**, with reasons, and can't be changed later without the founder. Nothing is executed in this build (founder, 16 Nov: option a) except T-e, which is pure arithmetic.

## Read first
- v1 `src/chronos/moirai/calibration/touchstones.py` (575 lines): the constants, the six `build_t_*`/`evaluate_t_e` functions, and every rationale comment. v1 `tests/moirai/test_touchstones.py`.
- `docs/v1-archive/SPEC_MOIRAI.md` §6. Master doc §6 "Acceptance test", §11a (gate 4.4). V2-D49 (master doc §10).

## Deliver
1. `fixtures/touchstones/*.yaml`, one per touchstone, validated by a schema (`fixtures/touchstone_schema.py`). Fields: `id`, `world` (generator function, every argument, seed, frame window), `strategy` (class name and parameters), `search` (for T-b: the grid cells and the pinned winner), `run_window`, `v1_outcome` (what v1's gauntlet did, for the record), `v2_expectation` (`verdict`, `must_fail_at` or `must_pass`, `rationale`), `pinned_on`, `source` (the v1 constant names).
2. The values, copied from v1 [Certain — read 16 Nov]:

| id | World | Strategy | v1 outcome | **v2 expectation** |
|---|---|---|---|---|
| T-a1 | regime frame, bull/bear annual Sharpe ±3.0, half-life 45 days, seed 314, hourly, 2020-01-01 → 2023-01-01 ± 3 weeks | MA 270/1080 h, fraction 0.95 | edge gates passed; failed breadth and subperiod | **To be written in this build, with reasons, before anything runs (V2-D49).** See "The T-a1 call" below |
| T-a2 | regime frame ±6.0, half-life 12 days, seed 271, same window | MA 72/288 h, fraction 0.95 | failed gate 4.4 (drawdown at 95% sizing) and subperiod | **PASS the edge check once sized by its drawdown budget** (master doc §6) |
| T-b | pure noise (target Sharpe 0), seed 20260202, 2020 → 2022 | best of an 8-cell grid, fast {10,20,30,40} × slow {80,120}; pinned winner (40, 120) | FAIL at plateau and/or DSR | **FAIL the edge check**: DSR at honest N = 8, and/or the neighbourhood test |
| T-c | noise, seed 20260303, 2020-01-01 → 2020-02-01 | MA 20/50 with the deliberate same-bar-fill leak | stopped as non-promotable before any statistics | **Caught by the look-ahead kit (B44); never reaches the edge check** (V2-D49) |
| T-d | noise, seed 20260404, 2020 → 2022 | 45 random entries (strategy seed 4040), holds of 24/48/72 h | FAIL; its own rank in v1's null between 20% and 80% | **FAIL the edge check** (not in the top 5% of the null benchmark). The rank itself is reported, not pinned to a band: a random-entry strategy's rank against a fresh random-entry null is close to uniform, so a [20, 80] band would fail a correct implementation about 4 times in 10. The same logic leaves a 1-in-20 chance that this fixed seed lands in the top 5% when it is run in B51: if it does, that is a **halt for the founder**, never a reason to pick another seed |
| T-e | no world: the committed returns of the 280-point sweep's winner | — | DSR 0.5630 as one try vs 0.0542 at N = 280 | **Same two numbers**, asserted now to 1e-12 |

3. `fixtures/touchstones/te_laundering_winner.json`: copied byte-for-byte from v1 (4,344 returns), with its SHA-256 recorded.
4. `fixtures/touchstones/MANIFEST.json`: the SHA-256 of every file in the folder. A test recomputes it.
5. Tests: schema validity; manifest; T-e.

## The T-a1 call
The master doc states v2 expectations for T-a2, T-b, T-d and T-e, not for T-a1. The builder writes T-a1's `v2_expectation` **from reasoning alone, without running anything**, choosing one of:
- `PASS` with the warnings v2 should print (v1's failures on it were breadth and subperiod, both of which are warnings in v2, so a pass with those two warnings is the natural reading); or
- `REPORT_ONLY` (no pinned verdict) if the reasoning can't support a confident prediction.

The rationale must say which, why, and what result would count as a finding. The reviewer checks that no backtest was run to reach it (no engine exists yet, which helps).

## Steps
1. Tests for schema, manifest and T-e (red). 2. Schema. 3. The six files. 4. Manifest. 5. Report (it quotes the T-a1 rationale in full).

## Known answers and checks
- **T-e, now** [Certain — computed from v1's file with v1's functions, 16 Nov]: with B06's functions on the committed returns: `T == 4344`; `per_bar_sharpe == 0.0024061391952578497`; sample skewness `0.7203182819604969`; kurtosis (not excess) `16.842229132109118`; with `V = 8.659587301602424e-05` and **the skewness and kurtosis passed in**, `dsr(N=1.0001) == 0.563048882547666` and `dsr(N=280) == 0.05423064441493044`; each to 1e-12. A second test asserts that calling `dsr` with its default skew and kurtosis gives a **different** value (0.56300 and 0.05438 to 5 places), so the test can't pass on the wrong call.
- The copied fixture's SHA-256 is `43472f4e3aff694473d5730bccfd285eb1a03736a3258acd2cfa5d834b759518` [Certain — computed on v1's file at commit `6b2b628`], typed into the test.
- Every YAML validates; every `world` argument set is one of B19's oracle cases (so the frames are already proven identical to v1's).
- `MANIFEST.json` matches the folder.
- **No verdict without a reason:** the schema rejects a `v2_expectation` with an empty `rationale`.
- **Founder-owned from the start:** `v2/src/chronos2/fixtures/touchstones/` is in `CODEOWNERS` (B02). The pull request that creates it can't merge without the founder's approval, and neither can any later edit. The loop finishes the build and the review, then waits; the founder reads the T-a1 rationale in the report and approves or sends it back.

## Not in this build
Running any touchstone except T-e (B51) · new intraday planted-edge worlds (B52) · the drawdown-budget sizing T-a2 needs (B50).

## Halt if
- A v1 constant and v1's rationale comment disagree with each other.
- Writing T-a1's expectation honestly requires a number only a run could give.

## For the gate
`COMPONENTS.md` §2 "Touchstones + regime generator" (this build edits it): definitions pre-registered in B20; executed in B51.
