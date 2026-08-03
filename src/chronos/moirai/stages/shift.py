"""shift.py — stage 4.7, Shifted-window stability (spec §4.7).

Re-run the identical candidate with the window START shifted by `shift.offsets_w` =
[−2, −1, +1, +2] weeks, LENGTH preserved (start AND end move by the same delta). Four
`kind=VERIFICATION` re-runs through the shared `rerun_candidate` helper. A result that
flips because the window moved a week was a window-edge artifact, not an edge.

Gate (v001 formulation, per the build brief): `shift.pass_fraction` (0.8) of the
configured offsets have per-bar Sharpe within `shift.max_sharpe_deviation_pct` (50%)
of the base run's per-bar Sharpe. Denominator = ALL configured offsets, so a refused
shift (see forward guards) counts against the fraction — a stability gate a window
cannot even demonstrate does not pass.

**v001-vs-spec drift (v002 reconciliation — beyond the two named 4.5 drifts; FLAGGED
in the phase-4c handoff for founder review).** v001 keys `shift.offsets_w`,
`shift.pass_fraction`, `shift.max_sharpe_deviation_pct` differ from spec §4.7's
`shift.offsets_weeks`, `shift.min_sign_agree`, `shift.sharpe_band`. More than a
rename: the spec's SIGN-OF-NET-RETURN-agreement sub-gate has NO key in v001 and is
absent from this v001-keyed formulation. v001 is the frozen hashed judge (I9); the
stage binds to its actual keys. Re-adding a sign-agreement sub-gate would require a
v002 config key — a founder decision, out of this session's scope.

**Forward guards (before each shifted re-run).** A shift is REFUSED, not clipped:
  1. Sealed-range guard: if the shifted window overlaps the Oceanus sealed-range
     registry (I4), refuse it. Nothing is sealed yet (Atropos seals in Phase 8); this
     is the forward guard that will bite then.
  2. Data-availability guard: if the shifted window runs past the stored data range
     (`oceanus.access.available_range`), refuse it rather than trigger a live
     edge-fetch or silently truncate.
A refused shift is recorded with its reason and does not count toward the pass
fraction (it is neither within-band nor evaluable).

Kind accounting: up to 4 × VERIFICATION (one per shift that is not refused).
"""

from dataclasses import replace
from datetime import timedelta

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.context import GauntletContext
from chronos.moirai.rerun import net_return, per_bar_sharpe, rerun_candidate
from chronos.moirai.types import TestOutcome
from chronos.oceanus.access import available_range
from chronos.oceanus.seal import SealRegistry

MOIRA_ID = "M4.7-shift"

_OFFSETS_KEY = "shift.offsets_w"                     # spec: shift.offsets_weeks (v002 rename)
_PASS_FRACTION_KEY = "shift.pass_fraction"           # spec: shift.sharpe_band pass rule (v002)
_MAX_DEVIATION_PCT_KEY = "shift.max_sharpe_deviation_pct"  # spec: shift.sharpe_band (v002 rename)

# DROPPED SPEC GATE (not a rename): spec §4.7 also requires the SIGN of net return to
# agree with the base run in >= `shift.min_sign_agree` of (base + shifts). v001 carries
# NO such key, so the sub-gate below is built but DORMANT — it reads its threshold from
# config and, finding the key absent under v001, reports not-applicable and does not
# affect the verdict. It hardcodes no literal (G2-clean) and does not re-key v001 (I9).
# v002 activates it by adding `shift.min_sign_agree` AND calibrating it (Phase 6).
_SIGN_AGREE_KEY = "shift.min_sign_agree"

_PERCENT = 100.0


def _relative_deviation(value: float, base: float) -> float:
    """|value − base| / |base|. Base 0 → 0.0 if identical, else +inf (an infinite
    relative move off a zero base can never be 'within band')."""
    if base == 0.0:
        return 0.0 if value == base else float("inf")
    return abs(value - base) / abs(base)


def _same_net_sign(value: float, base: float) -> bool:
    """Whether a run's net return has the same sign as the base run's — positive vs
    non-positive (a flat/negative window is not a positive edge). The primitive of the
    spec §4.7 sign-agreement sub-gate (dormant under v001)."""
    return (value > 0.0) == (base > 0.0)


class ShiftedWindow:
    """Stage 4.7. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.7 needs ctx.candidate (strategy + base config + hypothesis) "
                "to re-run shifted windows; none was provided."
            )
        base_config = ctx.candidate.base_config
        base_sr = per_bar_sharpe(result)
        base_net = net_return(result)

        offsets = list(ctx.config.thresholds[_OFFSETS_KEY])
        pass_threshold = ctx.config.thresholds[_PASS_FRACTION_KEY]
        max_dev = ctx.config.thresholds[_MAX_DEVIATION_PCT_KEY] / _PERCENT

        symbol = base_config.symbol
        timeframe = base_config.timeframe
        registry = SealRegistry()
        coverage = available_range(symbol, timeframe)

        per_offset: list[dict] = []
        wall_clocks: list[float] = []
        within = 0
        evaluated = 0
        refused = 0
        for weeks in offsets:
            delta = timedelta(weeks=weeks)
            shifted_start = base_config.start + delta
            shifted_end = base_config.end + delta

            if registry.is_sealed(symbol, timeframe, shifted_start, shifted_end):
                refused += 1
                per_offset.append({
                    "offset_weeks": weeks, "refused": True, "reason": "sealed_range",
                    "start": shifted_start.isoformat(), "end": shifted_end.isoformat(),
                })
                continue

            if (coverage is None or shifted_start < coverage[0]
                    or shifted_end > coverage[1]):
                refused += 1
                per_offset.append({
                    "offset_weeks": weeks, "refused": True,
                    "reason": "past_available_data",
                    "start": shifted_start.isoformat(), "end": shifted_end.isoformat(),
                    "available_range": (
                        None if coverage is None
                        else [coverage[0].isoformat(), coverage[1].isoformat()]),
                })
                continue

            modified = replace(base_config, start=shifted_start, end=shifted_end)
            rr = rerun_candidate(ctx, modified)
            wall_clocks.append(rr.wall_clock_s)
            shifted_sr = per_bar_sharpe(rr.result)
            shifted_net = net_return(rr.result)
            dev = _relative_deviation(shifted_sr, base_sr)
            in_band = bool(dev <= max_dev)
            sign_ok = _same_net_sign(shifted_net, base_net)
            evaluated += 1
            if in_band:
                within += 1
            per_offset.append({
                "offset_weeks": weeks, "refused": False,
                "per_bar_sharpe": shifted_sr,
                "net_return": shifted_net,
                "net_sign_agrees_base": sign_ok,
                "deviation_frac": dev,
                "within_band": in_band,
                "start": shifted_start.isoformat(), "end": shifted_end.isoformat(),
                "config_hash": rr.result.config_hash,
                "data_snapshot_hash": rr.result.data_snapshot_hash,
                "wall_clock_s": rr.wall_clock_s,
            })

        n_offsets = len(offsets)
        pass_frac = (within / n_offsets) if n_offsets else 0.0
        passed = bool(pass_frac >= pass_threshold)

        # --- DROPPED SPEC GATE (dormant under v001): sign-of-net-return agreement ---
        # Count of runs (base + each evaluated shift) whose net-return sign matches the
        # base. Threshold read from config; absent under v001 → sub-gate not applicable,
        # does not touch `passed`. Present (v002) → folded into the verdict.
        sign_agree_count = 1 + sum(  # the base run trivially agrees with itself
            1 for o in per_offset if (not o["refused"]) and o["net_sign_agrees_base"])
        n_considered = 1 + evaluated
        min_sign_agree = ctx.config.thresholds.get(_SIGN_AGREE_KEY)
        if min_sign_agree is None:
            sign_subgate = {
                "active": False,
                "sign_agree_count": sign_agree_count,
                "n_considered": n_considered,
                "reason": (
                    "spec §4.7 net-return-sign-agreement sub-gate has no v001 key "
                    "(shift.min_sign_agree) — DROPPED under v001, dormant here; adding "
                    "and calibrating the key activates it at v002. Does not affect the "
                    "v001 verdict."),
            }
        else:
            subgate_pass = sign_agree_count >= min_sign_agree
            sign_subgate = {
                "active": True,
                "sign_agree_count": sign_agree_count,
                "n_considered": n_considered,
                "min_sign_agree": min_sign_agree,
                "subgate_pass": subgate_pass,
            }
            passed = bool(passed and subgate_pass)

        evidence: dict = {
            "base_per_bar_sharpe": base_sr,
            "offsets_weeks": list(offsets),
            "max_sharpe_deviation_frac": max_dev,
            "pass_fraction_threshold": pass_threshold,
            "per_offset": per_offset,
            "n_offsets": n_offsets,
            "n_evaluated": evaluated,
            "n_refused": refused,
            "n_within_band": within,
            "pass_fraction_observed": pass_frac,
            "refused_note": (
                "refused shifts (sealed range or past available data) count against "
                "the pass fraction: a stability gate a window cannot demonstrate does "
                "not pass. Nothing is sealed yet (Phase 8); past-data refusals reflect "
                "the stored data edge."),
            "sign_agreement_subgate": sign_subgate,
            "v002_drift_note": (
                "gated on v001 keys (offsets_w/pass_fraction/max_sharpe_deviation_pct); "
                "spec §4.7's net-return-sign-agreement sub-gate is a DROPPED SPEC GATE "
                "(no v001 key), built dormant and activated at v002 by adding + "
                "calibrating shift.min_sign_agree — see sign_agreement_subgate."),
            "run_wall_clock_s": wall_clocks,
            "kind_accounting": f"{evaluated} × VERIFICATION (never toward N)",
        }
        if not passed:
            evidence["reason"] = "shift_instability"

        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=float(pass_frac), evidence=evidence)
