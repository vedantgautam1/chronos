#!/usr/bin/env python3
"""B05A step 4 -- prove the git-push lock against GitHub, from a cloud session.

Run by hand, from a **cloud** session, in a clone of this repository whose
``origin`` is GitHub:

    cd v2
    uv run python tools/loop/prove_lock_by_push.py

It drives the REAL shipped code -- ``lock.Lock`` over ``lock.GitPushRefs`` on
this clone, and ``facts._locks`` -- never a copy of it, so what it proves is
about the code the loop runs. ``prove_lock_on_github.py`` beside it did the
same for the REST backend from the Mac (B03); that backend cannot write from
the cloud at all.

What it runs, on exactly one ref, ``refs/heads/lock/zz-proof-b05a``:

1. 20 racing ``acquire`` pairs: two threads, distinct session ids, on the ref
   absent or released. Exactly one must win; the winner then releases.
2. 20 racing ``take_over`` pairs: a lock is written with a stamp 4 hours old,
   then two threads take over at "now". Exactly one must win; the winner then
   releases.
3. One ``acquire`` -> ``renew`` -> ``release`` cycle, then ``facts._locks`` on
   a fresh fetch, which must not report the ref.

A pair in which either racer hit a transport fault (a ``LockError``, not a
rejection) is recorded and **re-run**, not counted. A pair with two winners is
a failure of the design: the B05A spec says halt.

It leaves the ref in the released state (a marker commit): a cloud session
cannot delete a branch. Exit code 0 means every check passed.
"""

from __future__ import annotations

import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
REPO_ROOT = LOOP_DIR.parents[2]
if str(LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(LOOP_DIR))

# Imported after the path insert above, which is the point of it.
import facts
from lock import GitPushRefs, Lock, LockError, ref_for
from lock import _subprocess_runner as real_runner

BUILD_ID = "ZZ-PROOF-B05A"
REF = ref_for(BUILD_ID)
assert REF == "refs/heads/lock/zz-proof-b05a"  # the one ref this script may touch
PAIRS = 20
STALE_HOURS = 4  # claim_hours is 3
MAX_RERUNS = 15  # past this, 20 clean pairs cannot be reached in one tick: halt


class Recorder:
    """The real runner, plus a record of every push's porcelain output."""

    def __init__(self) -> None:
        self.pushes: list[tuple[str, int, str, str]] = []
        self._lock = threading.Lock()
        self.recording = False

    def __call__(self, argv, env):
        code, out, err = real_runner(argv, env)
        if self.recording and "push" in argv:
            with self._lock:
                self.pushes.append((threading.current_thread().name, code, out, err))
        return code, out, err


def race(first, second):
    """Run both, return [result-or-exception, result-or-exception]."""

    def guarded(fn):
        try:
            return fn()
        except LockError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="racer") as pool:
        futures = [pool.submit(guarded, first), pool.submit(guarded, second)]
        return [f.result() for f in futures]


def make_free(refs: GitPushRefs) -> None:
    """Leave the ref absent or released before a pair. Only ever this ref."""
    if refs.read(REF) is not None:
        refs.delete(REF)
    if refs.read(REF) is not None:
        raise LockError(f"{REF} could not be freed before a pair")


def run_pairs(kind: str, refs: GitPushRefs, rec: Recorder, sample: dict) -> tuple[int, list]:
    clean, reruns, attempt = 0, [], 0
    while clean < PAIRS:
        attempt += 1
        if len(reruns) > MAX_RERUNS:
            raise SystemExit(f"FAIL: {kind}: {len(reruns)} re-runs; 20 clean pairs not reachable")
        tag = uuid.uuid4().hex[:8]
        a = Lock(refs=refs, build_id=BUILD_ID, session=f"proof-a-{tag}")
        b = Lock(refs=refs, build_id=BUILD_ID, session=f"proof-b-{tag}")
        try:
            make_free(refs)
            now = datetime.now(UTC)
            if kind == "acquire":
                first = partial(a.acquire, "proof", now)
                second = partial(b.acquire, "proof", now)
            else:
                dead = Lock(refs=refs, build_id=BUILD_ID, session=f"proof-dead-{tag}")
                if not dead.acquire("proof", now - timedelta(hours=STALE_HOURS)):
                    raise LockError("could not write the stale lock for a take-over pair")
                if not a.is_stale(now):
                    raise SystemExit("FAIL: a 4-hour-old lock did not read as stale")
                first = partial(a.take_over, "proof", now)
                second = partial(b.take_over, "proof", now)
        except LockError as exc:
            reruns.append(f"attempt {attempt}: setup fault: {str(exc)[:160]}")
            continue

        rec.recording = not sample
        rec.pushes.clear()
        results = race(first, second)
        rec.recording = False

        faults = [r for r in results if isinstance(r, LockError)]
        winners = [lk for lk, r in zip((a, b), results, strict=True) if r is True]
        if faults:
            reruns.append(f"attempt {attempt}: transport fault: {str(faults[0])[:160]}")
            for lk in winners:
                try:
                    lk.release()
                except LockError:
                    pass
            continue
        if len(winners) != 1:
            raise SystemExit(f"FAIL: {kind} pair {clean}: {len(winners)} winners {results}")
        if not sample:
            sample.update(kind=kind, pushes=list(rec.pushes))
        winners[0].release()
        clean += 1
        print(f"  {kind} pair {clean:2d}: one winner ({'a' if winners[0] is a else 'b'})")
    return clean, reruns


def cycle(refs: GitPushRefs) -> None:
    make_free(refs)
    lk = Lock(refs=refs, build_id=BUILD_ID, session=f"proof-cycle-{uuid.uuid4().hex[:8]}")
    now = datetime.now(UTC)
    assert lk.acquire("proof", now), "cycle: acquire refused"
    first = lk.mine
    assert lk.renew("proof", now + timedelta(seconds=1)), "cycle: renew refused"
    assert lk.mine != first and lk.still_mine(), "cycle: renew did not move the ref"
    lk.release()
    assert refs.read(REF) is None, "cycle: the ref still reads as held after release"

    tracking = f"refs/remotes/origin/{REF.removeprefix('refs/heads/')}"
    code, _, err = real_runner(
        ["git", "-C", str(REPO_ROOT), "fetch", "-q", "origin", f"+{REF}:{tracking}"], None
    )
    if code != 0:
        raise SystemExit(f"FAIL: fresh fetch of {REF}: {err.strip()}")
    seen = facts._locks(facts._git, REPO_ROOT, {REF.removeprefix("refs/heads/")})
    print(f"  facts._locks after a fresh fetch: {seen or '{}'}")
    if BUILD_ID in seen:
        raise SystemExit("FAIL: facts._locks reports the released lock as held")


def main() -> int:
    rec = Recorder()
    refs = GitPushRefs(REPO_ROOT, runner=rec)
    print(f"git push lock proof, {datetime.now(UTC).isoformat()}, on {REF}")
    print(f"clone: {REPO_ROOT}")
    sample: dict = {}

    print("1. racing acquire pairs")
    acq, acq_reruns = run_pairs("acquire", refs, rec, sample)
    print("2. racing take_over pairs")
    tko, tko_reruns = run_pairs("take_over", refs, rec, sample)
    print("3. acquire -> renew -> release, then facts._locks")
    cycle(refs)

    print()
    print(f"acquire:   {acq} of {PAIRS} pairs with exactly one winner; re-runs {len(acq_reruns)}")
    for line in acq_reruns:
        print(f"    {line}")
    print(f"take_over: {tko} of {PAIRS} pairs with exactly one winner; re-runs {len(tko_reruns)}")
    for line in tko_reruns:
        print(f"    {line}")
    print(f"sample pair ({sample.get('kind')}), each push's porcelain output:")
    for thread, code, out, _err in sample.get("pushes", []):
        lines = [ln for ln in out.splitlines() if ln and not ln.startswith(("To ", "Done"))]
        print(f"    {thread}: exit {code}: {' | '.join(lines)}")
    print(f"final state of {REF}: released (read -> {refs.read(REF)})")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
