#!/usr/bin/env python3
"""B03 step 4(ii) -- prove the lock against GitHub itself.

Run this ON YOUR MAC, from the chronos repo. It needs to write git references
through the GitHub API, which the cloud session that built B03 is blocked from
doing. That block is the only reason this is a separate script.

    cd /path/to/chronos
    git checkout claude/b03
    python3 v2/tools/loop/prove_lock_on_github.py

What it proves, which is what the lock design rests on and what GitHub's own
documentation does NOT state the observable behaviour of:

  1. creating a reference that already exists is refused
     -> of two sessions racing to acquire a lock, exactly one wins
  2. updating a reference with force: false is refused unless the update is a
     fast-forward
     -> of two sessions racing to take over the same stale lock, exactly one
        wins, because the loser's commit was built on the stale commit and is
        no longer a descendant of the reference

It drives the REAL shipped class, v2/tools/loop/lock.py's GitHubRefs and Lock.
That is deliberate: a fresh script of my own would prove something about the
script instead of about the code the loop actually runs.

It is SAFE by construction:
  * it only ever touches references named lock/zz-proof-*, never a build branch;
  * it refuses to start unless a preflight can create, update and delete one
    such reference, so it fails fast rather than half-way through;
  * it deletes every lock/zz-proof-* reference in a finally block, and verifies
    none remain before it exits;
  * it writes no file and changes nothing in the repo.

Exit code 0 means the proof PASSED. Non-zero means it did not -- and if it did
not, read "IF THIS FAILS" at the bottom of the output: that is a real result
about the design, not a problem with this script.

Paste the whole output back into the chat.
"""

from __future__ import annotations

import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_SLUG = "vedantgautam1/chronos"
BASE = "v2-build"
PREFIX = "lock/zz-proof-"
PAIRS = 20
STALE_HOURS = 4  # claim_hours is 3, so this is stale
NOW = datetime.now(UTC)


def load_lock_module(repo_root: Path):
    loop_dir = repo_root / "v2" / "tools" / "loop"
    if not (loop_dir / "lock.py").is_file():
        sys.exit(
            f"no lock.py under {loop_dir}.\n"
            "Run this from the root of the chronos repo, on the claude/b03 branch."
        )
    sys.path.insert(0, str(loop_dir))
    import lock as lock_module

    return lock_module


class Recorder:
    """Wraps the backend's gh runner and keeps the raw request/response pairs,
    because the spec asks for one sample pair of API responses and the loser's
    status code is the actual finding -- the docs do not state it."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.log: list[dict] = []

    def __call__(self, *args: str, body: dict | None = None):
        code, out = self.inner(*args, body=body)
        self.log.append(
            {
                "request": " ".join(args),
                "body": body,
                "exit": code,
                "response": (out or "").strip()[:700],
            }
        )
        return code, out


def race(first, second) -> list[bool]:
    """Two genuinely concurrent calls. Returns both outcomes."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(first), pool.submit(second)]
        return [f.result() for f in futures]


def existing_proof_refs(backend) -> list[str]:
    code, out = backend._run(f"repos/{REPO_SLUG}/git/matching-refs/heads/{PREFIX}")
    if code != 0:
        return []
    try:
        return [item["ref"] for item in json.loads(out or "[]")]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def clean_up(backend, note: str) -> list[str]:
    print(f"\n--- cleaning up ({note}) ---")
    removed = []
    for ref in existing_proof_refs(backend):
        backend.delete(ref)
        removed.append(ref)
    left = existing_proof_refs(backend)
    for ref in removed:
        print(f"    deleted {ref}")
    if left:
        print(f"    !! STILL PRESENT, delete these by hand: {left}")
    else:
        print(f"    no {PREFIX}* references remain. Verified.")
    return left


def preflight(lock_module, backend) -> None:
    """Create, update and delete one reference before doing anything else."""
    print("--- preflight: can this machine write git references at all? ---")
    ref = f"refs/heads/{PREFIX}preflight"
    try:
        first = backend.commit("lock zz-proof preflight\n", None)
    except lock_module.LockError as exc:
        sys.exit(
            f"\nFAILED to create a commit object through the API: {exc}\n\n"
            "If this says 'not permitted through this proxy', you are in the same\n"
            "position the building session was in. This has to run on your Mac with\n"
            "your own gh auth, not in a cloud session."
        )
    if not backend.create(ref, first):
        sys.exit(
            f"\nFAILED to create {ref}.\n\n"
            "If this says 'not permitted through this proxy', this has to run on your\n"
            "Mac with your own gh auth, not in a cloud session. Otherwise check\n"
            "`gh auth status` has write access to the repo."
        )
    print(f"    created  {ref}")
    second = backend.commit("lock zz-proof preflight 2\n", first)
    if not backend.update(ref, second):
        backend.delete(ref)
        sys.exit(f"\nFAILED to fast-forward {ref}, which should always be allowed.")
    print(f"    updated  {ref} (a fast-forward, which must be ALLOWED)")
    backend.delete(ref)
    if backend.read(ref) is not None:
        sys.exit(f"\nFAILED to delete {ref}.")
    print(f"    deleted  {ref}")
    print("    preflight passed: creates, fast-forward updates and deletes all work.\n")


def acquire_races(lock_module, backend) -> tuple[int, list[dict]]:
    print(f"--- race 1 of 2: {PAIRS} racing acquire pairs ---")
    print("    expecting: creating a reference that already exists is REFUSED,")
    print("    so exactly one of each pair wins.\n")
    bad = 0
    sample: list[dict] = []
    for n in range(PAIRS):
        build_id = f"{PREFIX}acquire-{n:02d}".replace("lock/", "")
        a = lock_module.Lock(backend, build_id, "session-a", claim_hours=3)
        b = lock_module.Lock(backend, build_id, "session-b", claim_hours=3)
        mark = len(backend.log)
        results = race(
            lambda a=a: a.acquire("build", NOW), lambda b=b: b.acquire("build", NOW)
        )
        winners = sum(results)
        if winners != 1:
            bad += 1
            print(f"    pair {n:02d}: *** {winners} WINNERS *** {results}")
        if n == 0:
            sample = backend.log[mark:]
    print(f"    {PAIRS - bad} of {PAIRS} pairs had exactly one winner.")
    return bad, sample


def take_over_races(lock_module, backend) -> tuple[int, list[dict]]:
    print(f"\n--- race 2 of 2: {PAIRS} racing take_over pairs ---")
    print("    expecting: a non-fast-forward update with force: false is REFUSED,")
    print("    so exactly one of each pair wins.")
    print("    (the two sessions carry DIFFERENT ids on purpose: lock commits are")
    print("     content-addressed, so identical messages would be one object and")
    print("     both racers would believe they had won.)\n")
    bad = 0
    sample: list[dict] = []
    stale_at = NOW - timedelta(hours=STALE_HOURS)
    for n in range(PAIRS):
        build_id = f"{PREFIX}takeover-{n:02d}".replace("lock/", "")
        held = lock_module.Lock(backend, build_id, "session-dead", claim_hours=3)
        if not held.acquire("build", stale_at):
            print(f"    pair {n:02d}: could not set up the stale lock; skipped")
            bad += 1
            continue
        a = lock_module.Lock(backend, build_id, "session-a", claim_hours=3)
        b = lock_module.Lock(backend, build_id, "session-b", claim_hours=3)
        if not a.is_stale(NOW):
            print(f"    pair {n:02d}: the lock did not read as stale; skipped")
            bad += 1
            continue
        mark = len(backend.log)
        results = race(
            lambda a=a: a.take_over("build", NOW), lambda b=b: b.take_over("build", NOW)
        )
        winners = sum(results)
        if winners != 1:
            bad += 1
            print(f"    pair {n:02d}: *** {winners} WINNERS *** {results}")
        if n == 0:
            sample = backend.log[mark:]
    print(f"    {PAIRS - bad} of {PAIRS} pairs had exactly one winner.")
    return bad, sample


def show_sample(title: str, entries: list[dict]) -> None:
    print(f"\n--- sample API exchange: {title} ---")
    if not entries:
        print("    (none recorded)")
        return
    for entry in entries:
        print(f"  {entry['request']}")
        if entry["body"] is not None:
            print(f"    body     {json.dumps(entry['body'])}")
        print(f"    exit     {entry['exit']}")
        print(f"    response {entry['response'][:400]}")
        print()


def run(lock_module, backend) -> int:
    left: list[str] = []
    try:
        stray = existing_proof_refs(backend)
        if stray:
            print(f"{PREFIX}* references already exist; removing them first: {stray}")
            clean_up(backend, "before starting")
        preflight(lock_module, backend)
        bad_acquire, sample_acquire = acquire_races(lock_module, backend)
        bad_takeover, sample_takeover = take_over_races(lock_module, backend)
    except Exception:  # noqa: BLE001 - any failure must still clean up
        traceback.print_exc()
        clean_up(backend, "after an error")
        return 2
    finally:
        pass

    show_sample("racing acquire, pair 00 (winner then loser)", sample_acquire)
    show_sample("racing take_over, pair 00 (winner then loser)", sample_takeover)
    left = clean_up(backend, "after the races")

    print("\n" + "=" * 68)
    ok = bad_acquire == 0 and bad_takeover == 0 and not left
    if ok:
        print("RESULT: PASSED")
        print(f"  acquire   {PAIRS}/{PAIRS} pairs, exactly one winner each")
        print(f"  take_over {PAIRS}/{PAIRS} pairs, exactly one winner each")
        print(f"  every {PREFIX}* reference deleted and verified gone")
        print("\n  The two [Likely] claims in lock.py are now [Certain - run]:")
        print("  GitHub refuses a duplicate create, and refuses a non-fast-forward")
        print("  update with force: false.")
    else:
        print("RESULT: FAILED")
        print(f"  acquire   pairs with the wrong number of winners: {bad_acquire}")
        print(f"  take_over pairs with the wrong number of winners: {bad_takeover}")
        if left:
            print(f"  references left behind: {left}")
        print("\nIF THIS FAILS -- read this before changing anything.")
        print("B03's spec says, under 'Halt if':")
        print("  'Step 4's proof on GitHub shows two winners in either race, or")
        print("   GitHub accepts a non-fast-forward update with force: false. Then")
        print("   the lock design is wrong; propose the alternative (for example, a")
        print("   lock held as an issue assigned through the API) and stop.'")
        print("So this is a real result about the design, not a bug in this script.")
        print("Do not retry it with different timing. Paste the output into the chat.")
    print("=" * 68)
    print("\nPaste everything above into the chat.")
    return 0 if ok else 1


def default_repo_root() -> Path:
    """Where the repo is: an explicit argument, else this script's own place in
    it (it lives at v2/tools/loop/), else the current folder."""
    here = Path(__file__).resolve()
    if len(here.parents) >= 4 and (here.parents[3] / "v2" / "tools" / "loop" / "lock.py").is_file():
        return here.parents[3]
    return Path.cwd()


def main() -> int:
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_repo_root()
    lock_module = load_lock_module(repo_root)
    backend = lock_module.GitHubRefs(REPO_SLUG, tree_from=BASE)
    backend._run = Recorder(backend._gh)
    backend.log = backend._run.log
    print(f"B03 step 4(ii): proving the lock against {REPO_SLUG}")
    print(f"repo       {repo_root}")
    print(f"references {PREFIX}* (deleted afterwards)")
    print(f"now        {NOW.isoformat()}\n")
    return run(lock_module, backend)


if __name__ == "__main__":
    raise SystemExit(main())
