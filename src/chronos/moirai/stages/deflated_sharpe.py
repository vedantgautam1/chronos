"""deflated_sharpe.py — stage 4.3, Deflated Sharpe at honest N (spec §4.3, R1).

The selection-bias gate. All statistics come from `moirai/statistics.py` — nothing
is reimplemented here. Inputs are non-annualized at native H1 frequency (trap #4:
never feed annualized Sharpe). N and V come from the store's SEARCH records under
the SAME kind/hypothesis filter `compute_search_n` uses, so legacy records (<= #284,
no `kind`) are excluded by construction — never touched (trap #1: N never comes from
trial_counter.txt).

Gate: DSR at RAW N >= thresholds["dsr.confidence"]. Evidence carries DSR at N-hat
(JPM Appendix C, D-08 guard), DSR at union-N if 4.0 flagged fragmentation, and V's
measurement window alongside the verdict window (§3.1). N-hat is EVIDENCE ONLY.

--- N handling this phase (design decision, see HANDOFF) ----------------------
There is no stage 4.2 upstream yet (Phase 4b), so N is UN-FROZEN: this stage reads
`compute_search_n(hypothesis_id)` live and stamps `n_frozen: false`. For a candidate
drawn from NO logged search (compute_search_n == 0 — e.g. the milestone, whose
selecting 280-sweep is legacy `kind=None`), the deflation N is floored to 1: a
candidate is always at least one trial (itself), and DSR@N=1 floors SR* to 0 so the
DSR degenerates to a plain PSR (the honest "no logged search breadth to deflate
against" answer, and exactly the T-e N=1 case). The verdict's `search_n` still
records the raw compute_search_n value verbatim.
"""

import numpy as np

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.context import GauntletContext
from chronos.moirai import statistics as stats
from chronos.moirai.types import TestOutcome
from chronos.run import compute_search_n

MOIRA_ID = "M4.3-dsr"

_CONFIDENCE_KEY = "dsr.confidence"


def _deflation_note(raw_n, n_deflation, v_estimable) -> str:
    """Plain-English audit of how N was handled — worded to match `_deflated`
    exactly (the explicit guard, not just the math). Two branches, discriminated
    by the SAME condition `_deflated` guards on (`N < 2 or not v_estimable`):

      - degenerate: no real search breadth → the guard returns PSR(SR*=0) directly
        (mentions the guard AND why it exists — the nan-fix); Phase 7 re-establishes N.
      - real deflation: >= 2 aligned siblings → statistics.dsr with the actual N and V.
    """
    if n_deflation < 2 or not v_estimable:
        return (
            f"search_n_raw={raw_n}: fewer than 2 SEARCH records for this hypothesis "
            f"(compute_search_n={raw_n}); the selecting sweep, if any, is legacy "
            f"(kind=None, trial_index<=284) and excluded by construction. Deflation "
            f"N floored to {n_deflation} (a candidate is at least one trial). An "
            f"explicit N<2-or-V-not-estimable guard in the stage (_deflated) returns "
            f"PSR(SR*=0) DIRECTLY rather than computing SR* — this both encodes 'no "
            f"multiple-testing deflation applied' and avoids the sqrt(0)*Phi_inv(0) = "
            f"0*-inf = nan that sr_star hits at N=1. N is un-frozen this phase (no "
            f"stage 4.2 upstream). Honest N is re-established live in Phase 7, which "
            f"re-runs the 280-point sweep under kind=SEARCH."
        )
    return (
        f"search_n_raw={raw_n}, used as the deflation N (n_used_for_deflation="
        f"{n_deflation}); V estimated from >= 2 aligned SEARCH-sibling per-bar "
        f"Sharpes. Real multiple-testing deflation applied via statistics.dsr "
        f"(SR* floored at 0)."
    )


def _deflated(sr_hat, T, V, N, skew, kurt, v_estimable) -> float:
    """DSR with the honest degenerate case handled explicitly.

    When N < 2 (a candidate drawn from no logged search) or V is not estimable,
    there is no multiple-testing correction to apply: SR* is 0 and the DSR
    degenerates to a plain PSR against a zero benchmark. Computing it directly
    avoids the `sqrt(0) * norm.ppf(0) = 0 * -inf = nan` trap that `sr_star`
    would hit at N == 1. For N >= 2 with an estimable V this is exactly
    `statistics.dsr` (SR* floored at 0)."""
    if N < 2 or not v_estimable:
        return float(stats.psr(sr_hat, 0.0, T, skew, kurt))
    return float(stats.dsr(sr_hat, T, V, N, skew, kurt))


class DeflatedSharpe:
    """Stage 4.3. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        returns = [v for v in result.returns.to_list()] \
            if hasattr(result.returns, "to_list") else list(result.returns)
        T = len(returns)
        sr_hat = stats.per_bar_sharpe(returns)
        skew = stats.sample_skewness(returns)
        kurt = stats.sample_kurtosis(returns)

        # Raw N and the sibling per-bar Sharpes for V — same filter as compute_search_n.
        raw_n = compute_search_n(result.hypothesis_id, ctx.store)
        sibling_sharpes, sibling_returns, v_window = self._read_siblings(result, ctx)

        n_deflation = max(raw_n, 1)  # a candidate is always >= 1 trial (see docstring)

        # V: cross-trial variance of per-bar Sharpes; needs >= 2 siblings. When
        # n_deflation == 1 the SR* floor makes V irrelevant, so 0.0 is safe there.
        if len(sibling_sharpes) >= 2:
            v_value = float(np.var(sibling_sharpes, ddof=1))
            v_estimable = True
        else:
            v_value = 0.0
            v_estimable = False

        dsr_raw = _deflated(sr_hat, T, v_value, n_deflation, skew, kurt,
                            v_estimable)
        confidence = ctx.config.thresholds[_CONFIDENCE_KEY]
        passed = bool(dsr_raw >= confidence)

        evidence = {
            "sr_hat_per_bar": sr_hat,
            "T": T,
            "skew": skew,
            "kurt": kurt,
            "search_n_raw": raw_n,
            "n_used_for_deflation": n_deflation,
            "n_frozen": False,  # no stage 4.2 upstream this phase
            "V": v_value if v_estimable else "not_estimable",
            "V_estimable": v_estimable,
            "V_measurement_window": v_window,
            "verdict_window": [result.date_range[0].isoformat(),
                               result.date_range[1].isoformat()],
            "dsr_at_raw_n": dsr_raw,
            "dsr_confidence_threshold": confidence,
            "deflation_note": _deflation_note(raw_n, n_deflation, v_estimable),
        }

        # Effective N-hat (JPM Appendix C, R7/D-08) — EVIDENCE ONLY, never the gate.
        self._effective_n_evidence(
            sr_hat, T, v_value, skew, kurt, raw_n, sibling_returns, evidence)

        # DSR at union-N when 4.0 flagged fragmentation (evidence only).
        self._union_n_evidence(
            sr_hat, T, v_value, skew, kurt, result, ctx, evidence)

        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=float(dsr_raw), evidence=evidence)

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _read_siblings(result, ctx):
        """Per-bar Sharpes and return-series of the SEARCH records selecting this
        candidate — the SAME kind/hypothesis filter as compute_search_n. Returns
        (sharpes, return_series_list, measurement_window)."""
        sharpes, return_series = [], []
        windows = []
        for r in ctx.store.read_all():
            if r.get("type") != "run" or r.get("kind") != "SEARCH":
                continue
            if r.get("hypothesis_id") != result.hypothesis_id:
                continue
            res = r.get("result")
            if not res:
                continue
            series = [v for _, v in res.get("returns", [])]
            if not series:
                continue
            sharpes.append(stats.per_bar_sharpe(series))
            return_series.append(series)
            dr = res.get("date_range")
            if dr:
                windows.append(dr)
        window = None
        if windows:
            starts = [w[0] for w in windows]
            ends = [w[1] for w in windows]
            window = [min(starts), max(ends)]
        return sharpes, return_series, window

    @staticmethod
    def _effective_n_evidence(sr_hat, T, v_value, skew, kurt, raw_n,
                              sibling_returns, evidence):
        """Stamp DSR at N-hat, guarded by D-08 (only when M < T/2 and M >= 2 with
        aligned series); else effective_n: not_estimable."""
        M = raw_n
        aligned = [s for s in sibling_returns if len(s) == T]
        if M >= 2 and M < T / 2 and len(aligned) >= 2:
            rho_bar = stats.mean_pairwise_correlation(np.asarray(aligned, float))
            if np.isnan(rho_bar):
                evidence["effective_n"] = "not_estimable"
                return
            n_hat = stats.effective_trials(rho_bar, M)
            evidence["effective_n"] = n_hat
            evidence["mean_pairwise_correlation"] = rho_bar
            evidence["dsr_at_effective_n"] = _deflated(
                sr_hat, T, v_value, max(n_hat, 1.0), skew, kurt, v_estimable=True)
        else:
            evidence["effective_n"] = "not_estimable"
            evidence["effective_n_reason"] = (
                f"D-08 guard: M={M}, T={T}, aligned_siblings={len(aligned)} "
                f"(need M>=2, M<T/2, >=2 aligned series)")

    @staticmethod
    def _union_n_evidence(sr_hat, T, v_value, skew, kurt, result, ctx, evidence):
        """If 4.0 stamped fragmentation, report DSR additionally at the union N
        (spec §4.0/§4.3). 4.0's outcome isn't threaded here, so recompute the union
        N the same way 4.0 does — cheap, and keeps stages independent."""
        from chronos.moirai.stages.eligibility import _grid_axes

        records = ctx.store.read_all()
        hypotheses = {r["hypothesis"]["id"]: r for r in records
                      if r.get("type") == "hypothesis"}
        candidate = hypotheses.get(result.hypothesis_id)
        if candidate is None:
            return
        candidate_axes = _grid_axes(candidate["hypothesis"].get("param_grid_description"))
        if not candidate_axes:
            return
        siblings = [
            hid for hid, rec in hypotheses.items()
            if hid != result.hypothesis_id
            and _grid_axes(rec["hypothesis"].get("param_grid_description")) == candidate_axes
        ]
        if not siblings:
            return
        union_ids = {result.hypothesis_id, *siblings}
        union_n = sum(
            1 for r in records
            if r.get("type") == "run" and r.get("kind") == "SEARCH"
            and r.get("hypothesis_id") in union_ids)
        evidence["dsr_at_union_n"] = _deflated(
            sr_hat, T, v_value, max(union_n, 1), skew, kurt,
            v_estimable=(union_n >= 2))
        evidence["union_n"] = union_n
