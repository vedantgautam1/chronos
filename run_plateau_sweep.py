"""280-point MA-crossover plateau-robustness sweep.

Runs every (fast, slow) combination through run_experiment() with a config
otherwise identical to trial #4 (H-003-ma-crossover-milestone): same symbol,
timeframe, date range, seed, and all other RunConfig defaults. Only
strategy_params vary.

NOTE ON WHAT THIS IS: these 280 runs are ONE search over ONE hypothesis
family, not 280 independent beliefs. All 280 calls share ONE Hypothesis,
built via register_search() and reused — not 280 separate hypothesis ids —
and every call is tagged kind=RunKind.SEARCH. Any DSR computed on a cell
selected from this sweep must use N = compute_search_n(hypothesis.id, store),
not N = 1. (Individual (fast, slow) combinations are no longer addressable
by hypothesis_id — see the caveat below — look them up via
config.strategy_params in records/runs.jsonl instead.)
"""

from datetime import datetime, timezone

from chronos.mnemosyne.stub import RecordStore
from chronos.oceanus.model import Timeframe
from chronos.run import (
    DEFAULT_RECORDS_DIR,
    Hypothesis,
    RunConfig,
    RunKind,
    RunStatus,
    register_search,
    run_experiment,
)
from chronos.strategies.ma_crossover import MACrossover

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)

fasts = range(5, 55, 5)      # 5, 10, ..., 50            -> 10 values
slows = range(60, 200, 5)    # 60, 65, ..., 195          -> 28 values
# Every fast < every slow by construction, so no filtering is needed.


def main() -> None:
    # MACrossover is stateless (params come from ctx.params each bar), so a
    # single instance is safely reused across all 280 runs.
    strategy = MACrossover("BTC/USDT")

    combos = [(f, s) for f in fasts for s in slows]
    total = len(combos)
    assert total == 280, f"expected 280 combinations, built {total}"

    # ONE hypothesis for the whole 280-point search, reused across every
    # call — not 280 separate beliefs. register_search() makes that
    # explicit at the call site and persists the grid shape on every
    # 'hypothesis' record.
    hypothesis = register_search(
        Hypothesis(
            id="H-SWEEP-ma-crossover-280pt",
            statement=(
                "One search over the MA-crossover family: 10 fast values x "
                "28 slow values (280 combinations), same symbol/timeframe/"
                "date-range/seed as trial #4. NOT 280 independent beliefs."
            ),
            prediction=(
                "No standalone prediction for any single cell. Only the "
                "shape of the result surface across all 280 points is "
                "interpretable; any cell selected from this sweep carries "
                "search breadth N=280 (see compute_search_n), not N=1."
            ),
        ),
        param_grid_description=(
            "fast in range(5,55,5) x slow in range(60,200,5), 280 combinations"
        ),
    )

    store = RecordStore(DEFAULT_RECORDS_DIR)
    counter_before = store.trial_count

    completed, errored = [], []

    for i, (fast, slow) in enumerate(combos, start=1):
        config = RunConfig(
            symbol="BTC/USDT",
            timeframe=Timeframe.H1,
            start=START,
            end=END,
            seed=42,
            strategy_params={"fast": fast, "slow": slow, "fraction": "0.95"},
            # initial_cash, participation_rate, cost, optimistic_touch_fills,
            # and unsafe_same_bar_fill all left at RunConfig defaults —
            # matching trial #4 exactly.
        )

        # run_experiment RE-RAISES on failure (it persists an ERRORED record,
        # then lets the exception propagate). It therefore never RETURNS an
        # ERRORED RunRecord. Catching here is what lets the sweep continue and
        # lets step 7 report an errored count at all. See the note below.
        try:
            record = run_experiment(strategy, config, hypothesis, kind=RunKind.SEARCH)
            completed.append(record)
        except Exception as exc:
            errored.append((fast, slow, f"{type(exc).__name__}: {exc}"))

        print(f"{i}/{total} complete")

    counter_after = store.trial_count

    print()
    print("=" * 60)
    print(f"COMPLETED : {len(completed)} / {total}")
    print(f"ERRORED   : {len(errored)} / {total}")
    for fast, slow, err in errored:
        print(f"    f{fast}-s{slow}: {err}")

    # Authoritative range from the persisted trial counter — this covers
    # errored runs too, which never come back as RunRecords.
    print()
    print(f"trial_index range (new records): {counter_before + 1} .. {counter_after}")
    if completed:
        indices = [r.trial_index for r in completed]
        print(f"  min trial_index (completed)  : {min(indices)}")
        print(f"  max trial_index (completed)  : {max(indices)}")
    assert all(r.status is RunStatus.COMPLETED for r in completed)


if __name__ == "__main__":
    main()
