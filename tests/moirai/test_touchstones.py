"""test_touchstones.py — CI assertion of the pinned touchstone verdicts (SPEC §6).

Any FLIPPED verdict fails CI: these pin the gauntlet's behavior forever. The DIE/reject
cases (T-b, T-c, T-d, T-e) are threshold-robust and pinned now; the should-PASS canaries
(T-a1, T-a2) are DEFERRED (`BLOCKED-ON-PHASE-6-CALIBRATION`, not asserted — see touchstones.py).

Each engine touchstone runs through `touchstones.judge()` in an ISOLATED tmp store (never
production; the harness constructor refuses the production path). T-e is pure math (no engine).
"""

from chronos.moirai.calibration import touchstones as T


def _executed_failures(verdict) -> set:
    """The moira_ids that EXECUTED and did not pass (the full-eval failing set)."""
    return {o.moira_id for o in verdict.outcomes if o.executed and not o.passed}


# --- T-b: should-DIE, cause ∈ {4.2, 4.3} (GATE A) --------------------------------------
def test_t_b_dies_at_overfit_gates(tmp_path):
    verdict, _ = T.judge(T.build_t_b(), store_path=tmp_path, full_eval=True)

    assert verdict.status == T.TB_VERDICT == "FAIL"

    # Honest search-N: the grid was charged (N == grid size), NOT 1. If the winner were scored
    # at N=1 the whole test is meaningless (fork condition 1).
    assert verdict.search_n == T.TB_EXPECTED_N
    assert verdict.search_n > 1

    failures = _executed_failures(verdict)
    # GATE A: the OVERFIT gates {4.2, 4.3} are the pinned cause. 4.8 is NOT asserted (its gate (ii)
    # form is unratified until v002). If 4.2 AND 4.3 both PASSED and death were only downstream,
    # this assertion fails LOUDLY — surface it as a finding, do not force the verdict.
    assert set(T.TB_OVERFIT_CAUSE_GATES).issubset(failures), (
        f"T-b overfit gates {T.TB_OVERFIT_CAUSE_GATES} not all in failures {sorted(failures)}")
    assert {"M4.2-plateau", "M4.3-dsr"} & failures, "T-b must die at an overfit gate (4.2/4.3)"


# --- T-c: should-DIE via safety, NON_PROMOTABLE terminal at 4.0 ------------------------
def test_t_c_non_promotable_at_eligibility(tmp_path):
    verdict, _ = T.judge(T.build_t_c(), store_path=tmp_path, full_eval=False)
    assert verdict.status == T.TC_VERDICT == "NON_PROMOTABLE"
    assert verdict.cause_of_death == T.TC_CAUSE == "M4.0-eligibility"


# --- T-d: null baseline, FAIL and 4.9 self-percentile ∈ [0.2, 0.8] --------------------
def test_t_d_null_baseline(tmp_path):
    verdict, _ = T.judge(T.build_t_d(), store_path=tmp_path, full_eval=True)
    assert verdict.status == T.TD_VERDICT == "FAIL"

    null_bench = next(o for o in verdict.outcomes if o.moira_id == "M4.9-null-bench")
    assert null_bench.executed, "4.9 must run (full-eval) for the self-percentile to exist"
    self_pct = (null_bench.evidence or {}).get("candidate_percentile_in_null_dist")
    assert self_pct is not None
    lo, hi = T.TD_SELF_PERCENTILE_BAND
    assert lo <= self_pct / 100.0 <= hi, (
        f"T-d 4.9 self-percentile {self_pct}% outside [{lo*100:.0f}%, {hi*100:.0f}%] — "
        f"the null benchmark would be mis-calibrated. Surface, do not reseed.")


# --- T-e: the laundering demo (stats-only) --------------------------------------------
def test_t_e_laundering_regression():
    r = T.evaluate_t_e()
    # (1) laundering inflates the score ~10× when N is mis-charged as 1;
    # (2) the honest N=280 reading correctly sits below the 0.95 confidence gate.
    assert r["dsr_at_n1"] > r["dsr_at_n280"]
    assert r["dsr_at_n280"] < r["dsr_confidence"]
    assert r["laundering_holds"]
    # The canonical reproduced values (SESSION_FINDINGS 2026-07-16), on the SHIPPED statistics.dsr.
    assert abs(r["dsr_at_n1"] - T.TE_DSR_N1) < 5e-4
    assert abs(r["dsr_at_n280"] - T.TE_DSR_N280) < 5e-4
    assert r["cell"] == {"fast": 25, "slow": 60} and r["trial_index"] == 117
