"""signal_null.py — stage 4.1, Signal-only null gate (spec §4.1, M-a, R5).

Does the entry rule beat noise *before costs even enter*? We extract the
candidate's per-bar intended direction s_t ∈ {+1, 0} (long/flat; −1 reserved for
later stages) by running a `SignalCapture` wrapper through `ctx.run` — the exact
`_DecisionRecorder` pattern the invariant probes use (`tests/hephaestus/
invariants/test_probes.py`): the wrapper calls the inner strategy's real
`on_bar(view, ctx)`, records the intended direction, and emits **no orders**.
No engine change.

Because no orders are emitted the portfolio stays flat throughout, so the views
the inner strategy sees assume a flat portfolio — **exact** for
portfolio-state-independent entry rules (the MA milestone is one: its long/flat
signal is `fast_ma > slow_ma`, and with nothing ever held it emits a BUY on every
such bar, so the captured signal is exactly `1{fast>slow}`), an approximation for
state-dependent strategies (flagged; stage 4.9's full-engine null is the
state-aware backstop). Evidence stamps `flat_portfolio_assumption: true`.

Statistic (spec §4.1): with the market's log returns x_t detrended (x_t − x̄),
θ̂ = mean(s_t · (x_{t+1} − x̄)) — the signal decided at close(t) is exposed to
bar t+1, matching next-bar-open timing to first order (the close-to-close vs
next-open approximation is documented in evidence). Null: `null_signal.B` draws of
θ under the **stationary bootstrap** (Politis–Romano, from `statistics.py` — never
i.i.d.), block parameter p per D-R5-p (`statistics.block_p_from_returns`), signals
held fixed and the detrended returns resampled. One-sided p-value = fraction of
bootstrap θ ≥ θ̂. Gate: p ≤ `null_signal.alpha`.

RNG is `ctx.rng` ONLY (I10). Sensitivity bracket at {p/2, 2p} is mandatory in
evidence; a gate decision that flips across the bracket stamps
`fragile_to_block_length` (warn, not fail — the bracket exists to make fragility
visible, §4.1).

Kind accounting: the capture run is VERIFICATION (one logged, counted execution;
never toward N, §4.1).
"""

import numpy as np

from chronos.hephaestus.types import BacktestResult, Side
from chronos.moirai import statistics as stats
from chronos.moirai.context import GauntletContext
from chronos.moirai.types import TestOutcome
from chronos.run import RunKind

MOIRA_ID = "M4.1-signal-null"

_ALPHA_KEY = "null_signal.alpha"
_B_KEY = "null_signal.B"


class SignalCapture:
    """Wraps a strategy, records its per-bar intended direction, emits NO orders.

    `on_bar` calls the inner strategy's real method, reads the net intended order
    flow (net BUY → long → s_t=1; otherwise flat → s_t=0), records `(now, close,
    s_t)`, and returns `[]` so the engine executes nothing and the portfolio stays
    at initial state (flat). The close is captured from the same bounded view the
    engine saw, so the market series and the signals are aligned by construction —
    no second data-door read. Holds its records on the instance; the stage reads
    them after `ctx.run` returns (exactly as the probe reads `recorder.decisions`)."""

    def __init__(self, inner, symbol: str):
        self.inner = inner
        self.symbol = symbol
        self.signals: list[tuple] = []  # (now, s_t)
        self.closes: list[tuple] = []   # (now, close)

    def on_bar(self, view, ctx):
        orders = self.inner.on_bar(view, ctx)
        net = 0.0
        for o in orders:
            net += float(o.qty) if o.side == Side.BUY else -float(o.qty)
        s_t = 1 if net > 0.0 else 0  # {+1, 0}; −1 reserved for later stages
        self.signals.append((view.now, s_t))
        bars = view.bars(self.symbol, 1)
        if len(bars) > 0:
            self.closes.append((view.now, float(bars["close"].iloc[-1])))
        return []  # emit nothing — the whole point of the capture


def _theta(signals: np.ndarray, forward_returns: np.ndarray) -> float:
    """θ = mean(s_i · (fr_i − mean(fr))) — the signal-weighted mean of the
    forward returns, detrended by THIS sample's own mean. Detrending inside θ (not
    once up front) is what makes the bootstrap correctly calibrated: θ̂ carries a
    mean-subtraction constraint that shrinks its variance, and every bootstrap
    replicate must carry the identical constraint or the null is over-dispersed and
    the test turns conservative (verified: naive pre-detrending gave ~0.005
    rejection at α=0.05; re-detrending per replicate restores ≈α)."""
    if signals.size == 0:
        return 0.0
    fr = forward_returns
    return float(np.mean(signals * (fr - fr.mean())))


def signal_null_pvalue(signals, forward_returns, *, p_block, B, rng) -> tuple:
    """One-sided bootstrap p-value that the signal beats noise, plus θ̂.

    `signals[i]` (∈{0,1}) is decided at close(i); `forward_returns[i]` is the market
    log return realized over bar i→i+1 (i.e. `np.diff(np.log(closes))`, which is
    START-indexed), so signal i pairs DIRECTLY with `forward_returns[i]` — the last
    signal, which has no following bar, is dropped by truncating both to
    `L = min(len(signals), len(forward_returns))`.

    θ̂ = mean(s_i · (fr_i − fr̄)). The null holds the signals fixed and resamples the
    forward returns via the stationary bootstrap (block prob `p_block`, preserving
    autocorrelation), re-detrending each replicate by its own mean. p-value =
    fraction of bootstrap θ ≥ θ̂. Invariant to a constant added to `forward_returns`
    (the per-replicate detrend cancels it in θ̂ and every θ_b alike). `rng` is the
    sole randomness source (I10)."""
    s = np.asarray(signals, float)
    fr = np.asarray(forward_returns, float)
    L = min(s.size, fr.size)
    if L < 2:
        return 1.0, 0.0  # too short to say anything — the honest non-rejection
    s = s[:L]
    fr = fr[:L]
    theta_hat = _theta(s, fr)
    ge = 0
    for _ in range(int(B)):
        idx = stats.stationary_bootstrap_indices(L, p_block, rng)
        if _theta(s, fr[idx]) >= theta_hat:
            ge += 1
    return ge / float(B), theta_hat


class SignalNull:
    """Stage 4.1. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.1 needs ctx.candidate (strategy + base config + hypothesis) "
                "to run the signal capture; none was provided."
            )
        symbol = ctx.candidate.base_config.symbol

        # Capture pass: the wrapper records intent, emits no orders. VERIFICATION
        # (counted, logged, never toward N). No engine change.
        wrapper = SignalCapture(ctx.candidate.strategy, symbol)
        ctx.run(kind=RunKind.VERIFICATION, config=ctx.candidate.base_config,
                strategy=wrapper, hypothesis=ctx.candidate.hypothesis)

        signals = np.array([s for _, s in wrapper.signals], dtype=float)
        closes = np.array([c for _, c in wrapper.closes], dtype=float)

        alpha = ctx.config.thresholds[_ALPHA_KEY]
        B = ctx.config.thresholds[_B_KEY]

        evidence: dict = {
            "flat_portfolio_assumption": True,
            "n_bars": int(signals.size),
            "n_long_bars": int(signals.sum()),
            "alpha": alpha,
            "bootstrap_B": int(B),
            "signal_timing_note": (
                "signal decided at close(t) exposed to bar t+1; close-to-close vs "
                "next-bar-open approximation (H1 granularity; revisit at E2)."),
            "flat_portfolio_note": (
                "orders suppressed → portfolio flat throughout; signal = net-BUY "
                "intent per bar. Exact for portfolio-state-independent entry rules "
                "(the MA milestone); approximate otherwise — 4.9 is the state-aware "
                "backstop."),
        }

        if closes.size < 3 or signals.sum() == 0:
            # No usable series or the rule is never long → nothing to reject.
            evidence["reason"] = (
                "insufficient signal series (n_bars<3 or no long bars); no edge to "
                "detect before costs.")
            evidence["p_value"] = 1.0
            evidence["theta_hat"] = 0.0
            return TestOutcome(moira_id=self.moira_id, passed=False, score=1.0,
                               evidence=evidence)

        log_returns = np.diff(np.log(closes))

        # Block parameter p per D-R5-p, recomputed on THIS window's returns.
        p_block = stats.block_p_from_returns(log_returns)
        p_value, theta_hat = signal_null_pvalue(
            signals, log_returns, p_block=p_block, B=B, rng=ctx.rng)

        # Mandatory sensitivity bracket at {p/2, 2p} (2p clamped to a valid prob).
        p_half = p_block / 2.0
        p_double = min(2.0 * p_block, 1.0)
        p_at_half, _ = signal_null_pvalue(
            signals, log_returns, p_block=p_half, B=B, rng=ctx.rng)
        p_at_double, _ = signal_null_pvalue(
            signals, log_returns, p_block=p_double, B=B, rng=ctx.rng)

        passed = bool(p_value <= alpha)
        decisions = [p_value <= alpha, p_at_half <= alpha, p_at_double <= alpha]
        fragile = len(set(decisions)) > 1  # the gate call flips within the bracket

        evidence.update({
            "theta_hat": theta_hat,
            "p_value": p_value,
            "p_block": p_block,
            "mean_block_length": 1.0 / p_block,
            "p_value_bracket": {
                "p_block_half": {"p_block": p_half, "p_value": p_at_half},
                "p_block_double": {"p_block": p_double, "p_value": p_at_double},
            },
            "fragile_to_block_length": fragile,
        })
        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=float(p_value), evidence=evidence)
