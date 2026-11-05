# S13–S17 deep pass: checks written before running

Items: Arwaz Az, "How to Build a Self-Improving AI Trading Agent", Parts 3–7 (evaluation engine, agent team, self-improvement loop, validation and safety layer, complete architecture). Code: the author's `agentlab-lab` pack as shipped with Part 7 (157 tests).

Written 2026-11-05 13:34 UTC, before any of the checks below was run. Reruns of the author's own scripts (K0) were already running at that time; K1–K4 had not been written or run.

Rules (V2-D25): the expectation and what counts as a finding are fixed here. Seeds are fixed below and are not changed after seeing results. Results are reported whichever way they fall. Where a check is deterministic (a code property), "finding" means the stated behaviour happens at least once.

## K0. Do the author's published numbers reproduce?

Rerun every Part 3–7 script at the author's settings (Part 3 W=60, decoy N=200; Part 4 W=150; Part 5 W=150; Part 6 W=100; Part 7 W=300, NCAL=500). Compare with the author's shipped `figs/results_p3..p7.json`.
- Expectation: exact match (the code is seeded and deterministic), except wall-clock timings.
- Any mismatch is reported with the figure it affects.

## K1. Can promotion evidence be forged? (Part 6 registry)

The book says promotion "computes the checklist itself … so a forged 'all green' list is worthless" and reports 13 of 14 promotion attacks refused. The checklist is computed from objects the caller passes in (ladder record, monitor calibration, risk engine, audit log). Deterministic tests, same set-up as the author's registry matrix (`scripts/p6_experiments.py` §6):
- K1a: promote the decoy (`trend=1`, whose real ladder fails) to SHADOW then LIVE with a hand-built ladder dict: right candidate hash, contract hash, all rungs PASS, `passed=True`.
- K1b: promote the good version with a hand-written monitor calibration (`false_alarm_rate=0.0`) instead of a measured one.
- K1c: edit the real audit log (drop trigger, change a row), then promote passing a freshly built audit log instead of the real one, no anchor.
- Expectation: all three ACCEPTED. Finding if any is accepted.

## K2. Is the "one sealed look" actually one look? (Parts 3, 5, 6)

- K2a (deterministic): call `ladder.climb` twice on the same dataset without passing a `SealedTest`. Expectation: both calls perform the sealed look (no `SealedTestBurned`).
- K2b (deterministic): a dataset one day longer than another (same world) has a different content hash; measure the overlap of their sealed windows and whether a shared `SealedTest` allows the second look. Expectation: overlap ≥ 99% of the first window; second look allowed.
- K2c (arithmetic): overlap of each Part 5 cycle's sealed window with the previous cycle's, from `Contract.split` and `CYCLE_DAYS`. Expectation: about 43%, 50%, 56%.
- K2d (descriptive): in the Part 5 guided + memory loop, edge worlds, seeds 11000–11059 (60 worlds, the author's seeds), count how often the same idea label receives a sealed look in more than one cycle on the same baseline version. No pass/fail; reported as a count.
- K2e (Monte Carlo, 20,000 reps, seed 1301): a null idea (true difference zero; daily differences iid normal) given a sealed look in cycles 1..k of the Part 5 geometry, confirm rule `t ≥ 1.645` (the book's `sealed_confirm` without the net > 0 part). Report P(confirmed at least once) for k = 1..4, and the same for non-overlapping windows of the same lengths. Expectation: ≈5% at k=1, 11–15% at k=4. Finding if k=4 exceeds 7.5%.

## K3. Can the risk engine be bypassed with the engine in its own process? (Part 6)

The book reports 0 of 11 attacks succeed against the engine in a separate process. Its 11 attacks all target the engine. Set-up: `Executor(Registry, RiskProcess, PaperBroker, AuditLog)` as in the book's rehearsal, all in the test's process, a version live.
- K3a: call `executor.broker.send(order)` directly with a 20× oversize order. Expectation: the broker records the fill.
- K3b: replace `executor.risk` with a permissive object, then `executor.submit(oversize)`. Expectation: FILLED.
- K3c: halt the system, then un-halt it by direct SQL on the registry database (INSERT halted=0 as "research"; separately DELETE FROM halt). Expectation: `halted()` becomes False, `submit` is no longer refused for SYSTEM_HALTED, and the audit chain still verifies (the un-halt is invisible to it).
- K3d: terminate the risk process, then submit a normal order. Expectation: an exception and no fill (fail-closed). This is a check the author's design should pass.
- K3e (simulation): size-bug sweep. 3× leverage, default limits (`max_order` 5× equity), 100 stationary worlds (seeds 15000–15099, 3,000 days, the author's Part 6 set-up), bug multiplier m ∈ {1.25, 1.5, 1.6, 2, 5, 20} from a random day 1700–2499 (rng seed 6, as the author). Report per m: share of buggy entries blocked, ruined share, median and p90 max drawdown, with and without the engine; plus no-bug reference. Expectation: m ≤ 1.6 → 0 entries blocked by the order-size limit (4.8 < 5); protection comes only from the 30% drawdown kill. Finding if m ≤ 1.6 blocks no entries.

## K4. Why does the break-even monitor detect less? (Part 7)

The book (Ch. 7) reports break-even reference 36% detected vs shadow reference 69%, "and I did not investigate why". Proposed explanation, fixed now: with slack k = 0.10 sd, the post-death shortfall against a zero reference (≈ 4 bps / 30 bps ≈ 0.13 sd) barely exceeds k, so the CUSUM barely drifts; standard CUSUM practice sets k at about half the shift to be detected.

Set-up: the author's Part 7 calibration code (`scripts/p7_experiments.py` stage `cal`), 200 calibration worlds (seeds 20000–20199) and 200 test worlds (21000–21199) instead of 500/500, edge dies at live day 500, h chosen as the smallest grid value with ≤ 5% false alarms on calibration worlds over the live period. Detectors:
1. shadow reference, k = 0.10 (the book's);
2. break-even reference, k = 0.10 (the book's);
3. break-even reference, k = 0.065 (half of a 4 bps drop on a 30 bps sd, the contract's round-trip cost and the book's reported sd);
4. shadow reference, k = 0.17 (half of a ≈ 10 bps drop on 30 bps).

Report h, test false alarms, share detected within the live period, early alarms, median delay in trades and days.
- Explanation supported if detector 3 detects at least 1.3× as many dead edges as detector 2 at a test false-alarm rate no more than 3 points higher.
- Secondary (no pass/fail): detector 4 vs detector 1.

## Not run, by decision

- A "positive drift, no skill" world through the ladder (the gap the author names in Parts 6–7). Reason: for v2 the matched-exposure random-entry null (V2-D21, known-answer test (d)) already targets it, and at intraday holds drift per trade is small relative to costs (to be shown by arithmetic, not simulation).
- Validation on a fresh block vs on the research block. Reason: in these worlds every false candidate already loses to costs, so the comparison cannot show false passes; it would only measure power. Presented as a design question instead.
