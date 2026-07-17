# CHRONOS — Hephaestus Engine Specification

**Audience:** the implementing developer and reviewing quant.
**Scope:** the event-driven backtesting engine core, the cost model it plugs into, and the handoff contract to the Moirai (validation gauntlet).
**Companion:** `HEPHAESTUS_BUILD_BRIEF.md` (the phased Claude Code build instructions). This document is the contract; the brief is the sequence.

> **STATUS NOTE (updated 2026-07-08, see HANDOFF.md):** Stage 0 is
> **spot-only, no shorting** (founder decision; a brief same-day halt for a
> perps scope choice was reverted). All §13 decisions are recorded in
> HANDOFF.md. Build in progress under this spec as written.

---
## 0. What this component is, and where the rigor lives
Hephaestus is the trust core of Chronos: an event-driven simulator that walks
historical bars in time order, exposes a strategy only to information available
at decision time, routes intended trades through a simulated broker with a
realistic cost model, and accounts for every unit of value to the cent.

**A deliberate framing note:** the engine's hard problem is *correctness under
self-deception*, not mathematics. The statistically deep work (Deflated Sharpe,
purged CV, annualization corrections) lives in the Moirai, downstream of this
component. The engine's job is to make the numbers those methods consume
*true*. Its rigor is therefore concentrated in three places:
1. **Structural no-look-ahead** — the strategy is physically unable to see the future (not merely "asked not to").
2. **Exact, auditable accounting** — every fill, fee, and mark reconciles against hand-computed fixtures.
3. **Determinism** — identical (code, config, data snapshot, seed) → byte-identical results.

Everything else in this spec serves those three.

---
## 1. Invariants this component enforces
These are inherited from the Stage 0 specification and are **build-breaking**
requirements, verified by automated probes (§9):
- **I1 — No future leakage.** A strategy may only access data with
  timestamp ≤ its current decision time. Enforced by the `MarketView`
  abstraction, not by convention.
- **I2 — Costs always applied.** No code path in the trusted engine produces
  returns without passing through the cost model. Parameters may be set low;
  the cost path may never be skipped.
- **I3 — Every run is logged.** The engine's execute method is module-private.
  The sole public entry point is `run_experiment()`, which writes a record on
  every exit path, including exceptions.
- **I5 — Determinism.** All randomness flows through one injected, seeded RNG.
  No global `random`/`np.random` calls anywhere in the engine. Determinism
  means: identical (code SHA, config hash, data snapshot hash, seed,
  candidate search-N) → identical outputs. `candidate_n` is computed by
  `compute_search_n()` from the record store — a differing search-N
  between runs is a legitimate difference, not a determinism failure.
- **I6 — Every trial counted.** `run_experiment()` increments a monotonic
  trial counter before execution. Every execution is logged with a
  monotonic execution index (unchanged). Additionally, every execution
  carries a `kind` tag — `SEARCH` (one point in a parameter sweep,
  counted by `compute_search_n()` toward the DSR's N) or `VERIFICATION`
  (a standalone pre-registered run, a walk-forward window, a
  cost-sensitivity re-run — not counted toward N). The distinction
  cannot be inferred after the fact. See `RunKind` in `run.py` and the
  2026-07-17 HANDOFF.md entry.
- **I8 — Hypothesis precedes results.** `run_experiment()` requires a
  pre-registered hypothesis object; results cannot be recorded without one.
- **I9 — The judge is fixed before the trial.** The gauntlet's threshold
  vector is a versioned, hashed artifact (`gauntlet_config_hash` on
  `RunConfig`). Changing a threshold is a protected-path commit requiring
  full CI plus human review, and it invalidates every prior verdict
  stamped with the old hash — visibly, the way `core_version` already
  does. Enforcement deferred to the Moirai build; the anchor field
  exists in run records now.

(I4 — the sealed holdout — is a Moirai/data concern; the engine only needs to
respect snapshot pinning. I7 — one data door — is already enforced by Oceanus:
**the engine reads data exclusively via `get_bars()`** and must never import
`ccxt` or touch `data/` directly.)

---
## 2. Core data types
Final field names are the implementer's call; the *contracts* are not.

```
Order:
  id            : unique per run (deterministic generation — no uuid4 unless seeded)
  symbol        : str
  side          : BUY | SELL
  type          : MARKET | LIMIT
  qty           : Decimal/float (see §8 numeric policy)
  limit_price   : optional, required iff type == LIMIT
  created_at    : the bar-time t at which the strategy emitted it
Fill:
  order_id, symbol, side
  qty_filled    : may be < order qty (partial fills are normal)
  price         : the modeled execution price INCLUDING slippage/spread adjustment
  fee           : absolute cost charged, itemized
  bar_time      : the bar in which the fill occurred (t+1 under default timing)
Position:
  symbol, qty (signed), avg_entry_price, realized_pnl
BacktestResult:              # the object the Moirai consume — see §10
  run_id, core_version, config_hash, data_snapshot_hash, seed
  bars_processed, date_range, symbols, timeframe
  trades        : full fill list with itemized costs
  equity_curve  : per-bar equity series (see §7)
  returns       : per-bar simple returns derived from equity
  cost_summary  : total fees, total slippage cost, total spread cost
  warnings      : e.g. unsafe flags used, provisional cost constants active
  hypothesis_id : link to the pre-registered hypothesis
  trial_index   : from the monotonic counter
```

---
## 3. The strategy contract and MarketView (enforces I1)
A strategy is a pure decision function over a **bounded view**:

```
class Strategy(Protocol):
    def on_bar(self, view: MarketView, ctx: Context) -> list[Order]: ...
MarketView (READ-ONLY, bounded by decision time t):
    now: datetime                     # == t
    bars(symbol, lookback) -> frame   # ONLY bars with open_time + timeframe <= t
                                      # i.e. only bars that have CLOSED by t
```

**Structural requirements:**
- The view is constructed by the Feed from a slice; the strategy never receives
  a reference to the full series. Look-ahead must be *impossible*, not
  discouraged. Copy or otherwise protect the slice so the strategy cannot
  mutate shared state.
- Indicators are computed by the strategy from the view's data only. There is
  no engine-provided "precomputed indicator over the full series" facility —
  that pattern is the classic warm-up leak (an indicator computed over all
  history, then sliced, contains future information in its early values).
- `Context` carries: the injected seeded RNG, current portfolio snapshot
  (read-only), and strategy parameters. Nothing else.

---
## 4. The event loop
Per bar t, in strict order:

```
1. Clock advances to bar t (bars come from Oceanus get_bars(), already
   validated, final-only, UTC, sorted).
2. Broker processes orders created at t-1: attempts fills against bar t
   (see §5), producing Fills.
3. Portfolio applies fills: updates cash, positions, realized PnL.
4. Feed constructs MarketView bounded at t.
5. Strategy.on_bar(view, ctx) -> new orders, timestamped t.
6. Portfolio marks to market at close(t) -> equity[t] recorded.
7. t -> t+1.
```

**Execution timing (the single most important convention):** a signal computed
on the close of bar t executes at the **open of bar t+1**. This is the default
and the safe choice — it eliminates the "trade at the very close you used to
decide" leak. A same-bar-close fill mode may exist for research comparison but
must be gated behind an explicit `unsafe_same_bar_fill=True` flag that is
recorded in `BacktestResult.warnings`. It is never the default and the Moirai
must treat results carrying that flag as non-promotable.

**End-of-data:** orders created on the final bar never fill (there is no t+1).
They are recorded as expired, not silently dropped.

---
## 5. The simulated broker and fill model
**Market orders:** fill at `open(t+1)` adjusted by the cost model's slippage
(§6), subject to the participation cap.

**Participation cap:** a fill may consume at most `participation_rate ×
volume(t+1)` (configurable; default conservative, e.g. 5–10%). If the order
exceeds the cap it **partially fills** up to the cap.

**Decision required (flag to founder):** what happens to the unfilled
remainder — carry it to the next bar, or cancel it. Recommendation: **cancel
the remainder and record it**, for simplicity and auditability at Stage 0;
carrying introduces order-management state that isn't needed yet. Either way
the choice is explicit, configured, and logged.

**Limit orders:** the conservative convention — a buy limit fills only if the
bar **trades through** the limit (`low(t+1) < limit_price`), at the limit
price; symmetric for sells. Touching the limit exactly (`low == limit`) does
not fill — that optimism flatters results. The optimistic touch-fills variant
may exist only behind an explicit flag recorded in warnings.

**No liquidity assumption beyond the bar:** the broker never fills more than
the participation cap allows, never fills at prices outside the bar's range,
and never fills against zero-volume bars.

**Rejection cases:** insufficient cash (for buys) / insufficient position (for
sells, no shorting at Stage 0 unless explicitly decided otherwise — flag it),
zero-volume bar, malformed order. Rejections are recorded events, not
exceptions.

---
## 6. The cost model (enforces I2)
A separate module with a hard rule: **the engine cannot execute a fill without
routing it through this model.** There is no zero-cost path; a "frictionless"
run is achieved only by setting parameters low, never by skipping the code
path — and the difference is testable (§9, no-cost-path probe).

```
CostModel:
  fee(side, notional)                      -> absolute fee
  slippage(order, bar, participation)      -> price adjustment
  spread(bar)                              -> half-spread applied per side
  funding(position, interval)              -> perps only; see decision below
```

**Fees:** maker/taker bps on notional. Default to **taker** for market orders.
The actual bps values are configuration, sourced from the exchange's published
fee schedule — **verify current values at build time against the exchange's
own page; do not hardcode remembered numbers.** Record the values and their
source URL/date in config.

**Spread:** at bar granularity we have no order book, so spread is modeled: a
configurable half-spread (bps) charged on each side. This is an admitted
approximation; record it as such.

**Slippage:** start with a **fixed-bps model** (configurable), structured so a
size-aware model (participation- or √-impact-based) can replace it behind the
same interface. **R6 register note, non-negotiable:** any slippage/impact
coefficients used now are **provisional constants** — they cannot be derived
from papers and must eventually be estimated from Chronos's own real fills
(Stage 2). Every `BacktestResult` produced while provisional constants are
active must carry a warning saying so. The cost-sensitivity test in the Moirai
(re-run at 2× and 5× costs) is mandatory precisely because these constants are
uncertain.

**Funding (perpetuals):** **recommendation — Stage 0 is spot-only.** Perps add
funding accrual, margin, and liquidation mechanics that expand the accounting
surface substantially for no Stage-0 benefit. If spot-only is accepted (flag
to founder), `funding()` is stubbed to raise `NotImplementedError` with a
clear message, and shorting is disabled. If perps are insisted on, funding
accrual on held positions at the venue's interval becomes in-scope and this
spec must be extended before build.

---
## 7. Portfolio and accounting
- State: cash, positions (per symbol), realized PnL, cumulative costs
  (itemized: fees / slippage / spread).
- **Equity[t] = cash + Σ position_qty × close(t)**, marked at every bar close,
  producing the equity curve.
- Per-bar simple returns derived from the equity curve are part of
  `BacktestResult` (the Moirai consume returns; the engine computes them one
  way, once, here — not ad hoc downstream).
- **Reconciliation identity (tested):** at every bar,
  `equity[t] == initial_cash + realized_pnl + unrealized_pnl − total_costs`
  to within the numeric policy's tolerance. A drift here is a build-breaking
  bug.
- **Hand-computed fixtures:** the accounting is validated against micro
  scenarios computed by hand (on paper / spreadsheet, checked into the test
  suite with the derivation in comments): e.g. two fills, known fees, known
  closes → exact expected cash, position, equity at each bar. These fixtures
  are the accounting's known-answer tests and reviewers should check the
  hand derivations, not just the assertions.

---
## 8. Numeric policy (decision required)
Oceanus stores prices as float64 (per its HANDOFF). For engine accounting the
options are:
- **float64 throughout** — simple, fast, consistent with the data layer;
  requires tolerance-based assertions (e.g. abs diff < 1e-9 on normalized
  values) and care with cumulative summation.
- **Decimal for cash/position accounting, float for series math** — exact
  cent-level reconciliation, slightly more ceremony at the boundary.

**Recommendation:** Decimal for the accounting ledger (cash, fees, realized
PnL), float64 for price series and derived returns. The reconciliation
identity then holds exactly on the ledger side. Flag to founder; record in
HANDOFF. Whatever is chosen, the hand-computed fixtures must pass **exactly**
under the chosen policy — "close enough" on the ledger is not accepted.

---
## 9. Determinism and the invariant probes
**Determinism (I5):** a run is fully specified by (core git SHA, config hash,
Oceanus snapshot hash, seed). Two runs with identical coordinates produce
byte-identical `BacktestResult`s — same trades, same equity curve, same
warnings. All stochastic elements (if any) draw from the injected RNG.

**The probes (automated tests, CI-required on the engine's protected paths):**
1. **Poisoned-future probe (I1):** run a strategy; then corrupt every bar with
   `open_time > t` for each decision point (garbage prices/volumes) and re-run.
   Assert outputs byte-identical. Any difference proves a future leak.
   *Implementation note:* the practical form is: duplicate the dataset, poison
   the tail beyond a cut, run both to the cut, compare.
2. **No-cost-path probe (I2):** the same strategy under zero-parameter costs vs
   realistic costs must produce different returns, and grep/import-level
   checks confirm no execute path bypasses `CostModel`.
3. **Determinism probe (I5):** two runs, identical coordinates, byte-identical
   results — asserted on the serialized `BacktestResult`.
4. **Logging probe (I3):** calling the private execute directly raises; a run
   that throws mid-way still yields a persisted record with status=ERRORED.
5. **Trial-count probe (I6):** N runs → counter advanced exactly N, including
   errored runs.
6. **Reconciliation probe:** the §7 identity holds at every bar on all
   fixtures.
7. **Unsafe-flag probe:** enabling `unsafe_same_bar_fill` stamps the warning
   into the result; the default path never carries it.

The probes are the definition of "the engine can be trusted." A green suite is
the Gate 0→1 requirement, together with the touchstones (built after the
engine, per the Stage 0 sequence).

---
## 10. Handoff to the Moirai (the boundary contract)
The engine does **not** compute validation statistics. It produces a complete,
truthful `BacktestResult`; the Moirai judge it. The boundary:
- **The engine provides:** the full per-bar equity curve and returns, the
  itemized trade list, cost summary, config/data/seed coordinates, warnings,
  hypothesis link, and trial index. This must be *sufficient* for every
  planned Moira: walk-forward needs re-runs over windows (so the engine must
  be cheaply re-invokable over sub-ranges via the same `run_experiment()`
  path); cost-sensitivity needs cost parameters exposed in config;
  the Deflated Sharpe needs per-bar returns and the search-breadth N,
  computed by `compute_search_n(hypothesis_id, store)` — which counts
  `SEARCH`-kind records sharing the hypothesis. This is NOT the global
  execution counter in `trial_counter.txt` (which conflates every run
  regardless of purpose). See I6 above and `RunKind`;
  regime decomposition needs timestamps on everything.
- **The Moirai provide (later, quant's domain):** `evaluate(result, ctx) ->
  TestOutcome {passed, score, evidence}` per test, sequenced cheapest-first,
  short-circuiting on failure, writing outcomes to the same run record.
- **run_experiment() is the seam:** hypothesis in → engine executes → result
  logged → (later) gauntlet consumes. Build the seam now with a minimal
  record store (append-only JSONL/Parquet is fine as the Mnemosyne stub);
  the full Mnemosyne schema arrives with its own component. The stub must
  already be append-only, must already require the hypothesis, and must
  already count trials — those invariants are not deferred, only the storage
  sophistication is.
- **Results carrying warnings** (unsafe fill mode, provisional cost constants)
  are marked; the gauntlet treats unsafe-flagged results as non-promotable
  and provisional-cost results as requiring the cost-sensitivity test to pass
  with margin.

---
## 11. The vectorized screener (explicitly untrusted)
A separate module, clearly bannered UNTRUSTED, that computes signals across
the whole series with array operations for fast idea-killing. Contract:
- Its verdict can only **reject** candidates. It can never promote; promotion
  requires the event-driven engine.
- It shares the cost *parameters* (so its rejections aren't cost-naive) but
  none of the engine's trust guarantees.
- Its results are never written as authoritative runs — they are logged as
  screen events, not trials that inflate the DSR count. (Quant to confirm
  this counting decision: screens as non-trials is the recommendation, on the
  grounds that only full evaluations feed selection; if the quant disagrees,
  counting screens is the conservative alternative. Record the decision.)

---
## 12. Failure modes and guards
| Failure mode | How it bites | Guard |
|---|---|---|
| Indicator warm-up leak | Indicator computed over full series then sliced → future in early values | Strategies compute from MarketView only; no engine-wide indicator facility; poisoned-future probe |
| Same-bar fill | Trading at the close used for the signal → unrealizable returns | Next-open default; unsafe flag recorded; gauntlet treats flagged results as non-promotable |
| Costless path | Phantom edge under zero costs | No skip path (I2); no-cost-path probe |
| Assumed full fills | Ignoring liquidity → fantasy size | Participation cap; partial fills; conservative limit convention |
| Optimistic limit fills | Touch-fills flatter results | Trade-through convention default; optimism behind recorded flag |
| Accounting drift | Equity diverges from cash+positions−costs | Reconciliation identity tested every bar |
| Hidden RNG | Irreproducible runs | Injected seeded RNG only; determinism probe |
| Unlogged runs | Trial count understated → DSR inflated | Private execute; run_experiment sole entry; logging + trial probes |
| Provisional cost constants trusted | R6 coefficients are guesses until measured | Warning stamped on every result; mandatory cost-sensitivity downstream |
| End-of-data fills | Orders on the last bar filling impossibly | Expire-and-record convention |

---
## 13. Decisions the founder must make before/at build start
1. **Spot-only for Stage 0?** (Recommended: yes. Removes funding/margin/shorting scope.)
2. **Shorting allowed?** (Recommended: no at Stage 0 — spot-only implies it.)
3. **Unfilled remainder policy:** cancel-and-record (recommended) vs carry.
4. **Numeric policy:** Decimal ledger + float series (recommended) vs float throughout.
5. **Initial capital convention** for runs (e.g. 10,000 USDT notional) — arbitrary but fixed and recorded.
6. **Fee values:** confirm the exchange's current spot maker/taker bps from its published schedule (build-time verification, source recorded in config).
7. **Provisional slippage bps** to start with (a placeholder like 5–10 bps is defensible *only because* it is flagged provisional and stress-tested at 2×/5× downstream — the number itself is not a claim).

## 14. What the founder does NOT need to provide
- **No API keys.** Stage 0 uses Oceanus's public-data path exclusively; the
  engine never talks to an exchange.
- **No research papers for the engine core.** The primary-source register
  items (R1 DSR, R3 annualization — already sourced; R2, R4, R5 pending) are
  Moirai inputs, not engine inputs. The engine's only register touchpoint is
  R6 (slippage), which is explicitly *unsourceable from papers* — its
  coefficients await real Stage-2 fill data, hence the provisional-constant
  discipline above.
- **No exchange account.** That is a Stage 2 concern.

---
## 15. Derive-From-Source Register (R1–R5)

These methods have a primary academic source; each entry's status tracks
whether Chronos's implementation has been verified against that source.

- **R1 (Deflated Sharpe)** — status: FORMULA SOURCED (secondary: AFML
  §14.7.3), KNOWN-ANSWER TEST PENDING. The primary is Bailey & López de
  Prado (2014), JPM Vol 40 No 5 — its worked example must still be
  checked before this is fully SOURCED. Per Chronos's own register rule,
  AFML is a secondary source.
- **R2 (purged/embargoed CV)** — unchanged, deferred until ML labeling.
- **R3 (Sharpe annualization)** — SOURCED, verified against Lo (2002)
  Tables 1 & 2.
- **R4 (HAC significance)** — SOURCED (Newey-West 1987), structural
  properties verified (PSD, m=0 reduction, i.i.d./AR(1) behavior). The
  source paper gives NO automatic lag-selection rule and says so
  explicitly — the choice of m must be documented as a separate,
  explicit decision.
- **R5 (stationary bootstrap)** — SOURCED (Politis-Romano 1994), verified
  against Lemma 1 closed-form variance. The source paper gives no rule
  for optimal p beyond an asymptotic rate; practical choice must follow
  the autocovariance inspection procedure described in their Section 5.

**Note:** verification for R3–R5 currently lives in
`chronos_math_probe.py`, which is untracked scratch code at the repo
root, not yet part of the committed test suite. Promoting these checks
into a permanent, CI-required test module (e.g. `tests/statistics/`) is
an explicit follow-up task.

---
## 16. Assumptions Register (R6–R7)

These methods have no primary source; a plausible number substitutes for
a derivation. Any verdict depending on an entry here must report a range
(e.g. DSR at both raw N and effective N), not a point estimate.

- **R6 (slippage/impact)** — currently 10 bps, a guess defended as
  conservative. This is roughly half the total 42 bps per-round-trip
  cost hurdle. A "conservative" assumption that is actually too high is
  not a safety margin — it is a false-negative generator. Replacement
  plan: measure from Binance historical aggTrades data at the project's
  actual order sizes and pairs.
- **R7 (effective independent trials)** — DEMOTED, NOT CLOSED. The DSR's
  SR* formula already partially self-corrects via the cross-trial
  variance term V[{SR_n}] (measured empirically: 8.66e-05 for the
  280-point MA sweep). At that V, going from N=1 to N=280 raises the
  annualized DSR bar by approximately 1.33, not catastrophically. If a
  future search is more tightly correlated, effective-N estimation could
  matter again. Concrete instruction: whenever DSR is reported, always
  show both raw N and (if estimated) effective N as a bracket.

---
## Appendix A — Metric Definitions

**Sharpe ratio:** SR = mean(returns) / std(returns, ddof=1), computed at
the strategy's native bar frequency.

The DSR and PSR (§7, R1) operate on the non-annualized Sharpe ratio,
computed at the strategy's native decision frequency — per López de
Prado, AFML §14.7.3. Annualization via the formula below is a REPORTING
convenience only, applied after the gauntlet's verdict is reached, and
is subject to R3's correction whenever returns are non-i.i.d.

**Annualized Sharpe:** SR_annual = SR_bar × √(bars_per_year), where
bars_per_year depends on the timeframe (e.g. 8760 for H1, 365 for D1).
This √T scaling assumes i.i.d. returns; when returns are autocorrelated,
R3's Lo (2002) correction must be applied (see §15).

---
*End of specification. The build sequence, checkpoints, and Claude Code
instructions are in `HEPHAESTUS_BUILD_BRIEF.md`.*
