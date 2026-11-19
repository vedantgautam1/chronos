"""B03 step 4(i) -- the lock's races, against a throwaway local bare repository.

Twenty pairs of racing ``acquire`` and twenty pairs of racing ``take_over``,
each pair run in two real threads against one bare repository, asserting
exactly one winner every time.

**What this proves and what it does not.** ``BareRepoRefs`` below emulates the
two properties of GitHub's API that the lock design rests on: a reference
cannot be created twice, and an update with ``force: false`` is refused unless
it is a fast-forward. These tests prove that *the lock protocol yields exactly
one winner given a backend with those properties*. They do **not** prove that
GitHub has those properties -- that is step 4(ii), the proof against GitHub
itself, which the building session could not run. See the build report.

Two sessions racing to take over build their commits on the same stale commit,
so their lock commits differ only by what the message says. Git commits are
content-addressed, so it is the **session id in the message** that makes the two
commits different objects; identical messages would produce one sha and both
racers would believe they had won. The racers below therefore carry distinct
session ids, as two real sessions do.
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from lock import Lock, LockError, push_if_mine, ref_for

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
PAIRS = 20


class BareRepoRefs:
    """A reference backend over a local bare repository.

    ``create`` uses ``git update-ref --stdin``'s ``create`` command, which
    fails if the reference exists. ``update`` emulates ``force: false``: read
    the current value, refuse unless the new commit is a descendant of it, then
    compare-and-swap against the value just read. If another thread moved the
    reference in between, the swap fails -- so the pair is equivalent to one
    atomic fast-forward-only update.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._git("init", "-q", "--bare", str(path), cwd=None)

    def _git(self, *args: str, cwd: Path | None = ...) -> subprocess.CompletedProcess:
        where = self.path if cwd is ... else cwd
        cmd = ["git"] + (["-C", str(where)] if where else []) + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def read(self, ref: str) -> str | None:
        done = self._git("rev-parse", "--verify", "-q", ref)
        return done.stdout.strip() or None

    def message(self, sha: str) -> str:
        return self._git("log", "-1", "--format=%B", sha).stdout

    def commit(self, message: str, parent: str | None) -> str:
        args = ["commit-tree", EMPTY_TREE]
        if parent:
            args += ["-p", parent]
        done = self._git(*args, "-m", message)
        if done.returncode != 0:
            raise LockError(done.stderr)
        return done.stdout.strip()

    def create(self, ref: str, sha: str) -> bool:
        done = subprocess.run(
            ["git", "-C", str(self.path), "update-ref", "--stdin"],
            input=f"create {ref} {sha}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode == 0

    def update(self, ref: str, sha: str, expect: str | None = None) -> bool:
        current = self.read(ref)
        if current is None:
            return False
        if self._git("merge-base", "--is-ancestor", current, sha).returncode != 0:
            return False  # not a fast-forward: force: false refuses it
        done = subprocess.run(
            ["git", "-C", str(self.path), "update-ref", "--stdin"],
            input=f"update {ref} {sha} {current}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode == 0

    def delete(self, ref: str) -> None:
        self._git("update-ref", "-d", ref)


@pytest.fixture
def refs(tmp_path):
    return BareRepoRefs(tmp_path / "bare.git")


def lock_for(refs, build_id: str, session: str) -> Lock:
    return Lock(refs=refs, build_id=build_id, session=session, claim_hours=3)


def race(first, second) -> list[bool]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(first), pool.submit(second)]
        return [f.result() for f in futures]


# ------------------------------------------------------------------ the races


def test_twenty_racing_acquire_pairs_have_exactly_one_winner_each(refs):
    winners = []
    for n in range(PAIRS):
        build = f"b{n:02d}"
        a = lock_for(refs, build, "session-a")
        b = lock_for(refs, build, "session-b")
        results = race(lambda a=a: a.acquire("build", NOW), lambda b=b: b.acquire("build", NOW))
        assert sum(results) == 1, f"pair {n}: {results}"
        winners.append(results)
        assert refs.read(ref_for(build)) is not None
    assert len(winners) == PAIRS


def test_twenty_racing_take_over_pairs_have_exactly_one_winner_each(refs):
    stale_at = NOW - timedelta(hours=4)
    for n in range(PAIRS):
        build = f"c{n:02d}"
        held = lock_for(refs, build, "session-dead")
        assert held.acquire("build", stale_at) is True

        a = lock_for(refs, build, "session-a")
        b = lock_for(refs, build, "session-b")
        assert a.is_stale(NOW) is True
        results = race(lambda a=a: a.take_over("build", NOW), lambda b=b: b.take_over("build", NOW))
        assert sum(results) == 1, f"pair {n}: {results}"


# ------------------------------------------------------- the rest of the rules


def test_acquire_then_a_second_session_cannot_acquire(refs):
    a = lock_for(refs, "b06", "session-a")
    b = lock_for(refs, "b06", "session-b")
    assert a.acquire("build", NOW) is True
    assert b.acquire("build", NOW) is False
    assert a.still_mine() is True


def test_a_fresh_lock_is_not_stale_and_cannot_be_taken_over(refs):
    a = lock_for(refs, "b06", "session-a")
    a.acquire("build", NOW - timedelta(hours=1))
    b = lock_for(refs, "b06", "session-b")
    assert b.is_stale(NOW) is False
    assert b.take_over("build", NOW) is False


def test_renew_moves_the_reference_and_keeps_it_ours(refs):
    a = lock_for(refs, "b06", "session-a")
    a.acquire("build", NOW)
    first = a.mine
    assert a.renew("build", NOW + timedelta(minutes=5)) is True
    assert a.mine != first
    assert a.still_mine() is True
    assert refs.read(ref_for("b06")) == a.mine


def test_a_session_that_lost_its_lock_stops(refs):
    """``still_mine`` is false after a takeover, and the push helper refuses."""
    loser = lock_for(refs, "b06", "session-slow")
    loser.acquire("build", NOW - timedelta(hours=4))
    winner = lock_for(refs, "b06", "session-fast")
    assert winner.take_over("review", NOW) is True

    assert loser.still_mine() is False
    pushed = []
    assert push_if_mine(loser, lambda: pushed.append("pushed")) is False
    assert pushed == []
    assert loser.renew("build", NOW) is False

    assert winner.still_mine() is True
    assert push_if_mine(winner, lambda: pushed.append("pushed")) is True
    assert pushed == ["pushed"]


def test_release_deletes_the_reference(refs):
    a = lock_for(refs, "b06", "session-a")
    a.acquire("build", NOW)
    a.release()
    assert refs.read(ref_for("b06")) is None
    assert a.still_mine() is False


def test_take_over_acquires_when_there_is_no_lock_at_all(refs):
    a = lock_for(refs, "b06", "session-a")
    assert a.take_over("build", NOW) is True
    assert a.still_mine() is True


def test_a_lock_whose_age_cannot_be_read_is_not_treated_as_free(refs):
    """A lock the loop cannot judge is left alone: treating it as free is the
    one answer that would let two sessions run at once."""
    sha = refs.commit("lock b06 with no stamp at all\n", None)
    refs.create(ref_for("b06"), sha)
    a = lock_for(refs, "b06", "session-a")
    with pytest.raises(LockError, match="cannot be read"):
        a.is_stale(NOW)


def test_a_missing_lock_is_not_stale(refs):
    assert lock_for(refs, "b06", "session-a").is_stale(NOW) is False


def test_the_reference_name_is_exactly_lock_slash_id_in_lower_case():
    assert ref_for("B06") == "refs/heads/lock/b06"
    assert ref_for("B01A") == "refs/heads/lock/b01a"


def test_the_lock_commit_records_the_session_the_action_and_the_time(refs):
    a = lock_for(refs, "b06", "session-a")
    a.acquire("review", NOW)
    message = refs.message(a.mine)
    assert "session-a" in message
    assert "review" in message
    assert NOW.isoformat() in message
