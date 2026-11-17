*Kept as written by the red team (an agent on Opus, read-only), 17 Nov 2026. Every finding below was fixed in the specs the same day (commit after this file); the fixes have not been attacked again. Where the fix took a choice that belongs to the founder, it is in proposal P-22 (d2), (f), (g) in the master doc.*

# Red team — Phase 4a specs B43–B50 (branch spec/phase4a)

Independent review. Read-only on the repo. Findings appended as found; summary + verdict at the end.

## Findings (running log)

### F1 [major] B47 C2 — the spec's own N=1 rule makes DSR NaN; the build is certain to halt (or, worse, silently FAIL every N=1 candidate)
- Where: B47 "C2, DSR" ("With N = 1, V = 0") + Halt-if ("B06's dsr doesn't accept N = 1 and V = 0").
- Evidence (v1 `dsr`, which B06 ports with "same maths"): `dsr(V=0, N=1, ...)` = **nan** (sqrt(0) * norm.ppf(0) = 0 * -inf = nan; `max(nan, 0.0)` returns nan). With V=8.66e-5, N=1 gives 0.563048882547666 = PSR(sr_hat, 0) because -inf is floored to 0. So the spec's known answer "at N = 1 it is 0.563…" uses V != 0, contradicting its own rule that V = 0 at N = 1.
- Risk: a builder who doesn't halt gets `nan >= 0.95 == False`, i.e. every honest single pre-registered strategy FAILs C2.
- Fix: state "N = 1: C2 uses PSR(sr_hat, 0); V is not computed" and add a known answer with V = 0, N = 1 -> 0.563048882547666. Drop the halt line (it is now certain to trigger).

### F2 [major] B44 — exit look-ahead is caught by none of the three tests; the stated justification is false
- Where: B44 rule 1 (slice test "entries only ... the nudge probe watches P&L") and rule 3 (nudge probe: fails only "if any entry at or before the original entry changes").
- The nudge probe as written compares entries, not P&L or exits. So a strategy with clean entries and an exit of `close.shift(-1) < close` (sell before the drop) passes slice (entries unchanged), warm-up, and nudge (entries unchanged). The static check only catches the literal `.shift(-1)` / `.iloc[i+1]` spellings (`np.roll(c,-1)`, `c.values[1:]`, `c.diff().shift(-1)` via a variable, etc. go through). An exit leak is the cheapest way to inflate P&L, and nothing downstream (DSR, null, sealed look: S16 says 30%) catches it reliably.
- Also ambiguous: whether "entries" includes short entries (Signals has four columns).
- Fix: slice test over all four signal columns (long/short entries and exits) and the stop column; nudge probe fails if any signal (any column) at or before the nudged bar's predecessor changes. Add an `exit_peek` fixture that must fail both. If exits are deliberately deferred, it must be a founder-approved deviation, not a "can widen later".

### F3 [major] B44 — the ema200 known answer is method-dependent; a precise implementation lands outside the band
- Where: B44 known answers, "the report's 'history needed' is between 1,500 and 3,000 bars, and with warmup_bars set to it, the test passes".
- Evidence (my reimplementation, rng 44001, `ewm(span=200, adjust=False)`; slice/nudge counts reproduced exactly: clean 0/192 and 0/30, peek 747/747 and 30/30, whole_mean 19/25 and 27/30; ema h=250 -> 1.03e-4 OK): the relative difference is **not monotone in h** (h=500: 5.8e-7 passes; h=1000: 1.7e-6 fails). Smallest h below 1e-6: 940. Smallest h such that every larger h also passes: **1,070**. A doubling search from 200 gives 1,600 (in band); a doubling search from 250 gives 500, and then the test with warmup 500 checks h=1000 and **fails**, contradicting "with warmup_bars set to it, the test passes".
- Fix: define "history needed" = smallest h such that every h' in [h, all available] (bar by bar) is within 1e-6; recompute the band (about 1,070 here) or pin the method. Also state the ema200 fixture's declared warmup_bars (the 250 in the table is only reachable if it is 250).
- Also minor: whole_mean has only 25 entries but the probe "picks 30" — the 27/30 reproduces only with sampling **with replacement**; say so (or sample min(30, n) without replacement and restate the count).

### F4 [major] B44 — a strategy can pass on a frame where it never trades
- Where: B44 "All three tests take a strategy, one parameter point and a bar frame"; B47 checks only `has_passing_report(strategy, point, code coordinate)`.
- The caller chooses the frame. A frame with 0 entries passes slice (0 mismatches) and nudge (nothing to pick) vacuously; a short frame passes warm-up because 4 x warmup >= available. Nothing ties the report to the bars the candidate trial actually used.
- Fix: the report records the frame's snapshot hash/window; `has_passing_report` (or B47) requires the frame to be the candidate trial's research window (its footprint) and at least 30 entries (else `inconclusive`, not pass).

### F5 [blocker] B43/B46/B47/B48 — once any look exists, sealed data can be read by anyone, any number of times; and a look can be taken outside the edge check
- Where: B46 "Reading sealed data" (door allows `purpose="sealed_look"` if the look exists, is for that asset and the range is inside it); B46 `take_look(..., edge_config_hash=None)` (optional); B43 `run_point(...)` "with kind and purpose passed explicitly"; B47 verdict step 4 "the only state in which a sealed look may be requested" (enforced nowhere).
- What breaks: (1) the door does not bind a sealed read to the look's hypothesis, to a VERIFICATION trial, or to a single run. Any research code holding a `look_id` (look ids are readable by `looks_for`) can screen unlimited strategies on the sealed block through `run_point(purpose="sealed_look", look_id=...)`. BUILD_NOTES §2 (V2-D34 note): "give screens and research tools **no way** to read sealed dates". (2) `take_look` can be called directly by research code with no edge config and no `PENDING_SEALED_LOOK` verdict, which both spends a lineage's look on a candidate that was never checked and opens the door. "A look is never spent on a candidate that has already failed" is a convention in `run.py`, not a wall. (3) Nothing records which trial consumed the look, so the audit can't spot a second reader.
- Fix: (a) `sealed_look` row stores `edge_config_hash` (NOT NULL) and, when B47 lands, a trigger (or B47 migration 0006 adding it) requires a `pre_look` verdict `PENDING_SEALED_LOOK` for that config; B47's `touches` must then list the B46 migration/looks.py or add a 0006 trigger. (b) The door's `sealed_look` read requires `(look_id, trial_id)` where the trial is a VERIFICATION trial of that config's candidate (same strategy and params), and a unique constraint allows one such trial per look. (c) `run_point` does not take `purpose` from callers; B48's `gather_c6` is the only caller allowed to pass a look, via a private path. (d) `audit_looks` also scans footprints: any footprint carrying a look id that isn't that look's verification trial is reported.

### F6 [major] B43 + B10 — N can be understated by filing searches as VERIFICATION
- Where: B43 `run_point(...)` "with `kind` and `purpose` passed explicitly"; B10 defines VERIFICATION as "cost stress, a null draw, a sub-window, a re-run" with no constraint.
- Any number of new parameter points (or sub-windows: window shopping) can be run as `kind=VERIFICATION` on the research window; they never raise `search_n`, and B48's search freeze only blocks SEARCH inserts, so this is also the way round the freeze. CLAUDE.md hard rule 2 / V2-D03.
- Fix: in `run_point` (and ideally a trigger), a VERIFICATION trial must reference an existing SEARCH trial of the same hypothesis with identical strategy class and params; its window must equal that trial's window (re-run / cost stress) or be the sealed window bound to a look (F5). Add a test: `run_point(kind=VERIFICATION)` with params not in the hypothesis's SEARCH set -> refused.

### F7 [major] B46 — `join_prices_to_series` takes caller-chosen event times, so it can reconstruct the sealed price path
- Where: B46 `join_prices_to_series(series_key, event_times, horizon_bars)`; check "No function returns a frame of consecutive bars (asserted on the return shape: one row per event)".
- Passing `event_times` = every bar in the window with `horizon_bars=1` returns one row per "event" = the full bar-by-bar return series of post-seal BTC. The shape assertion is satisfied literally while defeating V2-D46 ("no price charts ... only through code that joins prices to that series").
- Fix: the join reads event times from the stored series itself (by `series_key`; the caller passes event ids, not times), refuses event times not present in the series, and caps horizons; add a test that a dense synthetic event list (one per bar) is refused.
- (F2 addendum) BUILD_NOTES §2 "Two look-ahead tests": the slice test must match "every indicator value **and signal** at that bar". B44's "entries only" narrows the method the notes require; per CLAUDE.md rule 9 that is a fork for the founder, not a builder default.

### F8 [major] B47/B48 — DSR deflation depends on V, and V can come from a tiny or hand-picked subset; two known answers are unreachable as written
- Where: B47 C2 ("V = sample variance ... over the hypothesis's SEARCH trials that have complete stored returns"); B47 "Honest N end to end"; B48 end-to-end "T-e ... FAIL, on C2".
- SR* = sqrt(V) * f(N). With N large but only 2 complete trials that are near-identical, V ~ 0 and DSR -> PSR(sr_hat, 0) whatever N is: an honest N with no bite. Errored/partial/no-return trials drop out of V silently.
- B48 T-e world: B20's T-e is "the committed returns of the 280-point sweep's winner" (one series; V is a constant in B20). Stored "under a hypothesis with 280 SEARCH trials", only 1 trial has returns -> V unavailable -> C2 **unavailable**, not fail. With no grid and N > 1, C5 fails `undeclared_search_breadth` -> the verdict is FAIL **on C5**, contradicting "FAIL, on C2". Same gap in B47's "280 registered SEARCH trials ... verdict is FAIL" (B47 run leaves C4–C6 empty, so FAIL needs C2 to fail, which needs V).
- Fix: (a) C2 is `unavailable` unless complete returns exist for at least a stated share of N (e.g. >= 90%, founder to set; protected) — else INCOMPLETE; (b) the two end-to-end known answers must say how the 280 trials get returns (e.g. v1's `sweep_trial_variance` construction) or explicitly inject V = 8.659587301602424e-05 through a test-only path, and assert "C2 fail" with C5 passing (give the hypothesis a grid).

### F9 [major] B47 — nothing stops freezing many configs for the same candidate (seed, window and target shopping)
- Where: B47 "Frozen configuration" (`freeze()` returns a hash; "the same config frozen twice gives ... one row"). The config contains the null seed, the research window and `target_sharpe_annual`, all chosen after the search results are visible.
- A different seed/window/target is a different hash, so a researcher can freeze k configs for one candidate and keep the best verdict (hard rule 10, "no seed shopping, no verdict-fitting"). Window choice moves DSR and the null; target moves C1 between INSUFFICIENT_DATA and judged (an INSUFFICIENT_DATA verdict also launders what would have been a FAIL: "nothing else is judged").
- Fix: DB-unique `edge_config` per (hypothesis_id, candidate_trial_id) (or per hypothesis), refusing a second freeze; the seed derived deterministically from the config's other fields (e.g. hash), not chosen; the research window must equal the candidate trial's window; `target_sharpe_annual` taken from the hypothesis registration (B10), not supplied at freeze time.

### F10 [major] B48 — re-running a config after its final verdict writes a second, contradictory final verdict
- Where: B48 "a second `run_edge_check` on the same config ends `LOOK_SPENT`"; B47 `edge_verdict` (append-only, many rows per config).
- A candidate that ended PASS (or FAIL on C6) and is re-run gets a new `final` row `LOOK_SPENT` for the same config and same facts. Two final states for one config; whichever a reader takes ("latest" erases a PASS; "any PASS" lets a later run be ignored).
- Fix: at most one `final` verdict per config (unique partial index `(config_hash) WHERE stage='final'`); a re-run returns the stored final verdict and writes nothing. `LOOK_SPENT` only for a config whose own look was never taken because the lineage's look was used by another config/hypothesis. Change the B48 check accordingly.

### F11 [major] B47 vs B49 — the protected file is "exactly five keys" in B47, then B49 adds a sixth with `may_modify_tests: []`
- Where: B47 Deliver 1 ("exactly the five keys in the table ... an unknown key raises"), B47 Halt-if ("would need a key not in the table"), B47 test `v2/tests/core/test_protected_edge.py`; B49 Deliver 1 (`change_check: {confidence: 0.95}` added to `edge_check.yaml`), B49 `may_modify_tests: []`.
- B47's own test (exact key set; unknown key raises) goes red when B49 adds the key, and B49 may not edit it -> B49 must halt. Also: every `EdgeConfig` frozen before B49 stores the old file hash, so all of them become `ProtectedChanged` and un-runnable; changing the change-check confidence later invalidates every frozen edge check (coupling two unrelated protected values).
- Fix: put `change_check.confidence` in its own protected file (`v2/config/protected/change_check.yaml`, B49 creates it, `load_change()`), or have B47 ship the key now and B49 only read it. Either way list it in B47's table so the founder approves it once.

### F12 [major] B48 — C4 inputs are unspecified: the eligibility mask, and which pricer gives the candidate's statistic
- Where: B48 "C4 evidence = B45's null_benchmark on the candidate's trades over the research window"; B45 `null_benchmark(candidate_trades, n_bars, bar_of, eligible, pricer, ...)`, `OpenToOpenPricer` (entry and exit at bar opens).
- `eligible` (warm-up, data gaps, "declared trading hours") has no source: `ScreeningStrategy` (B43) declares only `signals` and `warmup_bars`, no trading hours. An over-permissive or adversarial mask changes p (e.g. letting long draws fall in bars the strategy could never trade).
- The candidate's trades from B43 include **stop exits filled intrabar at the stop price**; draws exit at bar opens. If `candidate_stat` is taken from the B43-priced trades, candidate and null are priced under different fill rules (V2-D21: "the same pricer"), biased in the candidate's favour when stops fill better than the next open.
- Fix: B48 defines `eligible` = not in a door-reported gap AND index >= warmup_bars AND (if the strategy declares hours, inside them; add an optional `trading_hours` to `ScreeningStrategy` in B43); `candidate_stat` is recomputed by the same `Pricer` from (entry_bar, exit_bar, side, contracts), with a test that the candidate's stat and its B43 net differ only by the stop-fill effect and that the pricer passed is the one used for both.

### F13 [major] B48 — the end-to-end "planted edge -> PASS" world is not pre-registered and the look end has no source
- Where: B48 end-to-end worlds; `run_edge_check(config_hash)` (one parameter); B46 look range `[seal, moment of the look)`.
- `take_look` needs `look_end`; `EdgeConfig` doesn't hold one, so it must come from the wall clock: the sealed trade count, the door read and the verdict then depend on the date CI runs. With daily bars, the sealed block is ~230–270 days at today's date; ">= 200 positive trades" there needs roughly one non-overlapping trade a day (holds of ~1 bar), which is not the shape of B45 (c)'s "20 trades of 10 bars" that the world is defined by ("strong enough that B45's test (c) finds it"). The world, the strategy that exploits it and the generator parameters are left to the builder, so the pass/fail rule isn't committed before the run (V2-D25).
- Fix: `EdgeConfig` carries `look_end` (or an injected clock in tests); pin the planted world (B19 generator call, seed, edge size, bar size — hourly makes 200 sealed trades easy), the strategy, and the expected sealed trade count.

### F14 [major] B48 — after the search freeze, a second candidate of the same hypothesis has no defined outcome
- Where: B48 "The order of a run" step 2 (run missing neighbours as SEARCH, then freeze; afterwards SEARCH starts are refused).
- Edge-checking another candidate of the same hypothesis whose neighbours were never run requires new SEARCH trials, which the freeze refuses. Spec is silent: crash? C5 unavailable? C5 fail? Also the halt line names the table `mnemosyne.search_freeze` while the migration is `0007_search_frozen.sql` and the rule text calls it a "`search_frozen` event": pick one name.
- Fix: state it: a neighbour that can't be run because the search is frozen makes C5 `unavailable` (reason `search_frozen_missing_neighbours`) -> INCOMPLETE; add a test. Use one name (`search_freeze`).

### F15 [minor/major] B48 — the `v1_plateau` "cliff" fixture doesn't isolate the cliff condition
- Where: B48 Rules table row 3: neighbours 0.9, 0.8, -0.1, -0.2 -> "fail (cliff)".
- Median = 0.35 < 0.5, so the median condition already fails; an implementation with no cliff check passes this row. BUILD_NOTES §2 asks for a fixture each condition alone catches.
- Fix: add e.g. neighbours 0.9, 0.8, 0.7, -0.1, -0.2 (median 0.7 >= 0.5; 40% negative > 25%) -> fail (cliff only). Also say what "sorted" means for the neighbour list (the stated order (5,100),(20,100),(40,100),(10,50),(10,200) is axis-then-value, not lexicographic).

### F16 [major] B49 — a change can reach live without the look-ahead kit, on an unspecified window, with config shopping
- Where: B49 "What is compared", "The decision", "frozen and hashed before the run".
- (a) Nothing requires the candidate version to have a passing B44 report (B47 refuses edge checks without one; B49 doesn't). A change that introduces a look-ahead bug is the classic way an "improvement" beats the live version; ACCEPT puts it into a live strategy.
- (b) "the same window": which one, and read through which door purpose? The seal grows with time (V2-D38), so a research read can never go past 31 Mar 2026; a change check on a strategy live in 2027 either uses only pre-seal data (stale) or needs a purpose the door doesn't have. Unstated = the builder decides.
- (c) Same shopping hole as F9: many `change_config`s (different windows) per candidate trial, keep the best.
- (d) Order: rule 3 (adverse run unavailable -> INCOMPLETE) is applied before rule 4 (comparison fails -> REJECT), so a candidate that clearly fails the comparison is INCOMPLETE. B47 states the opposite principle ("a fail outranks a gap", row 15).
- Fix: (a) require `has_passing_report` for the candidate (refuse before reading); (b) name the window and the purpose (or flag it to the founder as an open question tied to V2-D38/D46); (c) one change_config per candidate trial (DB unique), window fixed at registration; (d) evaluate all fail conditions before any `unavailable`, and add a row: comparison fails + adverse unset -> REJECT.
- Checked fine: all B49 numbers reproduce (Šidák z(1,2,12,100) to 1e-16; HAC m=5, NW=0.010000000000000175, t=9.9999999999999, plain t 0.99499). Simulated worlds under my own reading (shared market noise, live = 0.35+noise-0.30): no-edge comparison-alone 0.952 / full 0.000; improvement 0.860; trades-less 0.003. Bands are not flaky. But the worlds are under-specified (how live "earns 0.35", whether candidate and live share noise); state the generator exactly. Note also the no-edge "full rule = 0" is guaranteed by rule 1 alone (live net ~ -150 +/- 22), so that world never exercises rule 2; only decision-table row 5 does (acceptable, say so).

### F17 [minor] B45 — order, under-specified draws, an off-by-one in (d1), a field name
- `null_min_draws` and "the seed comes from the frozen edge-check configuration" live in B47's protected file/config, but B45 needs only B43 and is built first. Say B45 takes `min_draws` as a parameter defaulting to a constant 1000 that B47 later wires to the protected value (and test that B48 passes the protected value).
- Draw counts for (c) and (d2) are not stated ((b) says 199). State them (my d2 check used 1000).
- (d1) 15 back-to-back trades of 100 bars on 1,500 bars: with "exit at the exit bar's open", the last exit needs bar index 1500 on a 0..1499 series. Define exit_bar = start + duration and require start + duration <= n_bars - 1, and make the fixture 1,501 bars (or say exits at the last bar's close).
- (a) asserts `strict_percentile_rank` but `NullResult` lists only `percentile_rank`. Name it.
- Sparse placement (largest-first sequential random placement) is not uniform over arrangements, and the method switches at 60%: the null's distribution jumps at that line. Acceptable for v0 if written down as such; the uniformity test (b) can't see it because the candidate is placed by `place` itself.
- Checked fine: band arithmetic ((b) mean 0.5025 +/- 4*0.2887/sqrt(1000) = [0.466, 0.539]; share at 0.05 +/- 4*0.00689 = [0.022, 0.078]; (b2) [0.445, 0.560]); KS bands have P(false fail) ~ 3e-4. My (d2) simulation (uniform placement, 1000 draws, 6 seeds incl. 45004): share p<=0.05 = 0.030–0.063, t-test 100%. Not flaky; a null that doesn't match exposure would fail it.

### F18 [minor] B43 — gaps the fixes leave
- Row 2 asserts only the exit **bar** on a gap-through stop (open 90 below a 95 stop). If VectorBT fills at 95, every gap-through stop is flattered by the gap. Assert the exit fill used for repricing is <= min(open, stop) for a long (the open, 90), and the mirror for shorts.
- The additive identity `Σ net_returns × capital = Σ trade nets`: a position still open at the window end has mark-to-market P&L but no closed trade. Say what happens (forced exit at the last bar's open, priced with costs).
- Python 3.14 (V2-D45): VectorBT pulls numba; add a halt "vectorbt or its numba doesn't install on the locked Python".
- README "Who may write what" names "the two that add libraries"; B43 is a third (and B47, B49, B50 touch `v2/config/protected/`). Update the README list at the gate.

### F19 [minor] B44 — the report key and the static check
- `has_passing_report` is keyed by "code coordinate", which V2-D42/B10 define as git commit + uv.lock hash + engine version: any unrelated commit invalidates every report, and neighbour runs in B48 happen at a later commit than the candidate. Key it by a hash of the strategy's source (+ lock hash), and state which coordinate B47 compares.
- The static check runs "when a strategy is registered", but no build defines registration and B44 can't touch `screen/**`. Say `check_strategy` runs it first (fixtures bypass via the three functions directly, as stated).

### F20 [minor] B48 — the capacity warning is not v1's, despite "[Certain — read]"
- v1 `configs/gauntlet/v001.json` and `stages/capacity.py`: capacity = per-bar Sharpe degradation <= 0.3 at 10x, remainder-cancelled <= 0.2, participation cap 5% of bar volume. B48's "median trade notional > 1% of median dollar volume of its entry bar" is a new rule. Retag it as new ([Guessing]/founder) or port v1's. The other warning values check out (min_round_trips 30, subperiod 12 months / 0.6 / 0.6).

### F21 [minor] B50 — wording that a literal builder would get wrong; bisection noise
- "Periods per year is √365 for daily crypto bars" — periods per year is 365; the formula divides by sqrt(365). Read literally it gives 20000/365^(1/4) = 4575.69 instead of 1046.85. (The known answer catches it, but fix the text.) For hourly bars, the "daily" names are wrong (it is an hourly cash-vol target against an hourly value vol).
- `r_boot` by bisection to 1e-6: `ruin_boot(r)` must use the same 20,000 paths for every r (common random numbers) or it isn't monotone and bisection can wander. State it.

### F22 [minor] B46 / B47 small consistency points
- B14's existing test expects `SealedDataError` for `sealed_look`; B46 must keep that type for "no `look_id`" (it has `may_modify_tests: []`). Say so.
- B46's anchor is "read from the protected file" — name it (`validation.yaml` `seal`, B02). For a `series_key` look the anchor is X from `series_window`, which is not in a protected file; say so.
- B47 step 7: a sealed VERIFICATION run that errors makes C6 not-pass -> FAIL, with the look spent. Decide whether that is FAIL or INCOMPLETE (infrastructure failure), and test it.
- `lookahead_review_required` "stops the strategy until a person has run the kit and written the result down": there's no table or flag that stops anything. Say where it is stored and what reads it.

### F23 [major] B43 — VectorBT runs cost-free; nothing stops its own (gross) stats being used
- Where: B43 rules ("Every run uses fees=0, slippage=0"; fix 5 "freq and year_freq always set ... a run without them is refused" because `stats()` drops Sharpe).
- With fees and slippage at 0, every `Portfolio` statistic (Sharpe, returns, drawdown) is gross of costs. Fix 5 exists only so that `stats()` reports a Sharpe, i.e. it anticipates someone reading it. If `run_point`/`run_grid` or the stored trial ever carries VectorBT's numbers, that is a cost-free path (hard rule 3) and a Sharpe that disagrees with the one C2 uses.
- Fix: the wrapper returns trial ids only and never exposes the `Portfolio` object or its `stats()`; the stored per-bar Sharpe is computed from the repriced additive net returns. Add a test: for a grid point with costs, the stored Sharpe != VectorBT's `stats()['Sharpe Ratio']` on the same run and == `per_bar_sharpe(net_returns)`. Keep fix 5 only as a guard on internal use.
- Related minor: B47 C3 hard-codes "2 x" while B16's `stress(…, "x2_frictions")` reads `stress_friction_multiplier` from B02's protected file. Compute `net_x2` through `stress` so there is one source for the multiplier.

### F24 [major] B47/B48 — "no grid, N = 1 -> C5 pass" contradicts "nothing passes while the rule is null" and lets every idea skip V2-D20
- Where: B48 "Neighbours" (no grid and N = 1: C5 `pass`, `no_neighbourhood_defined`); B48 "It stays `null` until G5, so C5 is unavailable and nothing passes"; B47 row 14; B48 planted-edge world ("N = 1").
- The two rules give different answers for the same facts (rule null, N = 1, no grid): pass vs unavailable. Under the first, an N = 1 strategy can reach PENDING_SEALED_LOOK, spend its lineage's look and PASS before G5. Beyond the ordering bug: V2-D20 says the neighbourhood check is **binding**; filing every idea as a single pre-registered point makes C5 pass by construction and the lone-spike/look-ahead trigger never fires. The planted-edge end-to-end PASS reaches C5 through this exemption, so it never exercises `test_rule` at all.
- Fix: state the order: `neighbourhood_rule` null -> C5 unavailable, before any grid logic. Flag the N = 1 exemption to the founder as a fork (options: keep v1's exemption; or require a declared neighbourhood for every candidate and run it as SEARCH trials, which raises N honestly). Give the planted-edge world a grid so the end-to-end PASS goes through the rule.

### F25 [major] B47/B48 — the lone-spike 0.25 decides verdicts but is an unprotected, unapproved value
- Where: B47 C5 rule ("a lone spike is a fail **and** sets `lookahead_review_required`", decision row 13); B48 "Lone spike ... *The 0.25 is set here as a starting value ... it only decides when a review opens, never a verdict*".
- B47 makes a lone spike a FAIL independently of the active rule, so the 0.25 is a validation threshold (hard rule 7 / V2-D11: protected, founder-approved), yet it is hard-coded in B48 and described as never deciding. Today it's masked (any lone spike also fails `v1_plateau`, since 0.25 < 0.5), but the G5 rule is unknown.
- Fix: choose one: (a) lone spike only flags (C5 decided by the active rule alone; the review flag blocks promotion separately), or (b) put `lone_spike_frac: 0.25` (and `min_neighbours: 3`) in `edge_check.yaml`, in B47's table for the founder's approval.

---

## VERDICT: ADOPT WITH FIXES

The specs are careful and most of the numbers are right, but one blocker (F5: sealed data can be read outside the one look) and several majors must be fixed **in the specs** before B43–B50 start. Build order: B43–B46 and B50 can start once their own findings are fixed. B47–B49 wait for F5, F8–F11 and F24–F25.

| # | Sev | Spec | One line |
|---|---|---|---|
| F5 | blocker | B43/B46/B47/B48 | any holder of a look_id reads sealed data unboundedly; take_look callable outside the edge check |
| F1 | major | B47 | N=1 with V=0 gives DSR = NaN (certain halt, or silent FAIL) |
| F2 | major | B44 | exit look-ahead caught by none of the three tests; narrows BUILD_NOTES' slice test |
| F3 | major | B44 | ema200 "history needed 1,500–3,000" depends on method; precise answer 1,070 |
| F4 | major | B44 | report passes on a frame with no entries; not tied to the candidate's bars |
| F6 | major | B43/B10 | N understated by filing new points as VERIFICATION (also gets round the freeze) |
| F7 | major | B46 | caller-chosen event times rebuild the sealed price path through the join |
| F8 | major | B47/B48 | V from a subset neutralises N; T-e "FAIL on C2" unreachable (it's C2 unavailable / C5 fail) |
| F9 | major | B47 | many frozen configs per candidate = seed/window/target shopping |
| F10 | major | B48 | a re-run writes a second final verdict (PASS then LOOK_SPENT) |
| F11 | major | B47/B49 | "exactly five keys" + B49's sixth key + may_modify_tests [] -> B49 halts; hash coupling |
| F12 | major | B48/B45 | C4 eligibility mask has no source; candidate and null priced under different fill rules |
| F13 | major | B48 | planted-edge PASS world not pre-registered; look_end comes from the wall clock |
| F14 | major | B48 | second candidate after the freeze has no defined outcome; table name mismatch |
| F16 | major | B49 | no look-ahead report required; window and purpose unstated; config shopping; gap outranks fail |
| F23 | major | B43 | VectorBT runs at zero cost; its stats must never leave the wrapper |
| F24 | major | B47/B48 | N=1/no-grid C5 auto-pass contradicts "nothing passes while the rule is null"; bypasses V2-D20 |
| F25 | major | B47/B48 | lone-spike 0.25 decides FAILs but isn't protected |
| F15 | minor/major | B48 | cliff fixture also fails on median; doesn't isolate the cliff |
| F17 | minor | B45 | depends on B47's values; draw counts; (d1) off-by-one; field name |
| F18 | minor | B43 | gap-through stop price not asserted; open trades vs identity; 3.14/numba halt; README list |
| F19 | minor | B44 | report key = git commit; static check unwired |
| F20 | minor | B48 | capacity warning isn't v1's despite [Certain — read] |
| F21 | minor | B50 | "periods per year is √365" wording; bisection needs common random numbers |
| F22 | minor | B46/B47 | B14 error type; anchor source; errored sealed run; review flag has no home |

## Checked and found correct
- B47 C1: years_to_significance 24.730228928079065 / 6.182557232019766 / 2.7478032142310074 / 1.5456393080049415; 2922/365.25 = 8.0; 2191/365.25 = 5.99863.
- B47 C2 (T-e): DSR N=280 = 0.05423064441493044, N=1 = 0.563048882547666 (= PSR(0)), with raw kurtosis (excess would differ at 4e-7, so the 1e-12 tolerance tells them apart).
- B47 C3: trade A net_x1 +7, net_x2 −1 (not +4), trade B +17/+9/adverse −1. B48 break-even 15/8 = 1.875 and 40/16 = 2.5; k* > 2 equals net_x2 > 0.
- B47 provenance: v1 config dsr.confidence 0.95, percentile_gate 95, plateau 0.5/0.25/steps 2, min_round_trips 30, subperiod 12 m / 0.6 / 0.6.
- B48 neighbour lists for (10,100) and (5,50); rules table medians (0.41, 0.35, −0.025) and the lone-spike column.
- B49: Šidák z(1,2,12,100) exact; HAC example (m=5, NW 0.01, t 10.0, plain 0.99499); simulated-world bands reproduce under an independent reading (0.952/0, 0.860, 0.003), not flaky.
- B50: θ_A 0.369016532170913, ruin 0.0249678739694576; coin θ = ln(11/9), (9/11)^20; the bug-pair table (c = 0, 0.3, 0.6) correct and buggy columns; Kelly 0.2 / 0.11965811965811965 / 0.1; r_formula 0.0154021146319 (ε 0.05), 0.0100193065664 (ε 0.01); kelly cap 0.0299145299145; contracts 1 and 0 (30.80 at risk); Carver 1046.8478451804274, 3.4894928172680912, 1250 / 4.1667, 19.406%; 24-ordering drawdowns {0.20:4, 0.208:4, 0.244:4, 0.28:12}, terminal 0.8316 for all.
- B50 bootstrap bands (own stationary bootstrap): independent 0.0140–0.0156 over 4 seeds (band [0.009, 0.036]); clustered 0.101–0.106 (band >= 0.054); an iid bootstrap on the clustered series gives 0.017 and fails, so the band can catch a wrong method.
- B44 counts reproduce exactly (clean 0/192, 0/30; peek 747/747, 30/30; whole_mean 19/25, 27/30 with replacement; ema 1.03e-4 at 250).
- B45 band arithmetic and (d2) robustness (0.030–0.063 vs a 0.10 cap over 6 seeds).
- B43 fix 4: 10,000 × 10 × 0.00001 = 1.00; 17,544 = 731 × 24.
- B46 decision rows 1–11 follow from the exclusion constraint and direct-sibling members as described.
- Migration numbers 0004–0008 are unique and follow B09–B11's 0001–0003; ladder `needs` match the headers; no spec lets an LLM size, order or decide.
