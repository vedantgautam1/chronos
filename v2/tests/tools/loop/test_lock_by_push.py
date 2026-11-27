"""B05A known answers 1-15 -- the production lock backend, ``GitPushRefs``.

Every test here runs the **real** ``GitPushRefs`` and real ``git push`` from a
real local clone to a throwaway bare repository reached as a ``file://``
remote. Nothing is emulated. That is the difference from ``test_lock.py``'s
``BareRepoRefs``, which emulates GitHub's API to prove the *protocol*; these
prove the *backend the loop runs* (spec "Known answers", first paragraph).

The bare repository is read directly with ``git -C <bare>`` to check what
really landed, never through the backend under test.
"""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from lock import (
    GitHubRefs,
    GitPushRefs,
    Lock,
    LockError,
    is_release_marker,
    message_for,
    ref_for,
)

NOW = datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)
PAIRS = 20
REF = ref_for("t01")

# Only the fixtures' own commits use this; the backend must bring its own.
FIXTURE_IDENTITY = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["git"] + (["-C", str(cwd)] if cwd else []) + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **FIXTURE_IDENTITY},
    )


class Remote:
    """The bare repository, read directly -- the ground truth."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def tip(self, ref: str) -> str | None:
        return (
            git("rev-parse", "--verify", "-q", ref, cwd=self.path).stdout.strip()
            or None
        )

    def message(self, sha: str) -> str:
        return git("log", "-1", "--format=%B", sha, cwd=self.path).stdout

    def parents(self, sha: str) -> list[str]:
        return git("log", "-1", "--format=%P", sha, cwd=self.path).stdout.split()


@pytest.fixture
def world(tmp_path):
    """(backend, remote, clone): a real clone whose ``origin`` is a bare repo."""
    bare = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    assert git("init", "-q", "--bare", str(bare)).returncode == 0
    assert git("init", "-q", str(clone)).returncode == 0
    assert git("remote", "add", "origin", bare.as_uri(), cwd=clone).returncode == 0
    return GitPushRefs(clone), Remote(bare), clone


def lock_for(refs, build_id: str, session: str) -> Lock:
    return Lock(refs=refs, build_id=build_id, session=session, claim_hours=3)


def race(first, second) -> list[bool]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(first), pool.submit(second)]
        return [f.result() for f in futures]


def held(refs, session: str = "session-a", at: datetime = NOW) -> str:
    """Put a lock on REF through the backend and return its sha."""
    sha = refs.commit(message_for("T01", session, "build", at), None)
    assert refs.create(REF, sha) is True
    return sha


# ---------------------------------------------------------- 1-4: create, update


def test_01_create_on_an_absent_ref_creates_it(world):
    refs, remote, _ = world
    sha = refs.commit(message_for("T01", "session-a", "build", NOW), None)
    assert refs.create(REF, sha) is True
    assert remote.tip(REF) == sha


def test_02_create_on_a_held_ref_is_refused_and_changes_nothing(world):
    refs, remote, _ = world
    first = held(refs)
    rival = refs.commit(message_for("T01", "session-b", "build", NOW), None)
    assert rival != first
    assert refs.create(REF, rival) is False
    assert remote.tip(REF) == first


def test_03_update_with_a_child_of_the_tip_moves_the_ref(world):
    refs, remote, _ = world
    tip = held(refs)
    child = refs.commit(message_for("T01", "session-a", "build", NOW), tip)
    assert refs.update(REF, child, tip) is True
    assert remote.tip(REF) == child


def test_04_update_with_a_sibling_of_the_tip_is_refused(world):
    """A child of an *older* commit: what a take-over race's loser pushes."""
    refs, remote, _ = world
    older = held(refs)
    tip = refs.commit(message_for("T01", "session-a", "renew", NOW), older)
    assert refs.update(REF, tip, older) is True
    sibling = refs.commit(message_for("T01", "session-b", "take", NOW), older)
    assert refs.update(REF, sibling, older) is False
    assert remote.tip(REF) == tip


# ------------------------------------------------------------- 5-8: release


def test_05_delete_leaves_the_ref_pointing_at_a_release_marker(world):
    refs, remote, _ = world
    before = held(refs)
    refs.delete(REF)
    after = remote.tip(REF)
    assert after is not None, "a cloud session cannot delete a branch; the ref stays"
    assert after != before
    assert is_release_marker(remote.message(after)) is True
    assert remote.parents(after) == [before]
    assert refs.read(REF) is None


def test_06_create_on_a_released_ref_replaces_the_marker(world):
    refs, remote, _ = world
    held(refs)
    refs.delete(REF)
    fresh = refs.commit(message_for("T01", "session-b", "build", NOW), None)
    assert refs.create(REF, fresh) is True
    assert remote.tip(REF) == fresh


def test_07_delete_on_an_absent_ref_is_quiet_and_creates_nothing(world):
    refs, remote, _ = world
    refs.delete(REF)
    assert remote.tip(REF) is None


def test_08_delete_on_a_released_ref_writes_no_second_marker(world):
    refs, remote, _ = world
    held(refs)
    refs.delete(REF)
    marker = remote.tip(REF)
    refs.delete(REF)
    assert remote.tip(REF) == marker


# --------------------------------------------- 9: a fault is never a refusal


def test_09_an_unreachable_remote_raises_and_never_reads_as_free_or_refused(world):
    refs, _, clone = world
    sha = refs.commit(message_for("T01", "session-a", "build", NOW), None)
    missing = clone.parent / "no-such-remote.git"
    assert (
        git("remote", "set-url", "origin", missing.as_uri(), cwd=clone).returncode == 0
    )

    calls = {
        "create": lambda: refs.create(REF, sha),
        "update": lambda: refs.update(REF, sha, sha),
        "read": lambda: refs.read(REF),
        "delete": lambda: refs.delete(REF),
    }
    for name, call in calls.items():
        with pytest.raises(LockError) as caught:
            call()
        # git's own stderr names the path it could not reach.
        assert "no-such-remote.git" in str(caught.value), f"{name}: {caught.value}"


# ---------------------------------------------------------- 10-11: the races


def test_10_twenty_racing_acquire_pairs_have_exactly_one_winner_each(world):
    refs, remote, _ = world
    for n in range(PAIRS):
        build = f"r{n:02d}"
        a = lock_for(refs, build, "session-a")
        b = lock_for(refs, build, "session-b")
        results = race(
            lambda a=a: a.acquire("build", NOW), lambda b=b: b.acquire("build", NOW)
        )
        assert sum(results) == 1, f"pair {n}: {results}"
        winner = a if results[0] else b
        assert remote.tip(ref_for(build)) == winner.mine
        winner.release()
        assert refs.read(ref_for(build)) is None


def test_11_twenty_racing_take_over_pairs_have_exactly_one_winner_each(world):
    refs, remote, _ = world
    stale_at = NOW - timedelta(hours=4)
    for n in range(PAIRS):
        build = f"s{n:02d}"
        assert lock_for(refs, build, "session-dead").acquire("build", stale_at) is True
        a = lock_for(refs, build, "session-a")
        b = lock_for(refs, build, "session-b")
        assert a.is_stale(NOW) is True
        results = race(
            lambda a=a: a.take_over("build", NOW), lambda b=b: b.take_over("build", NOW)
        )
        assert sum(results) == 1, f"pair {n}: {results}"
        winner = a if results[0] else b
        assert remote.tip(ref_for(build)) == winner.mine


# ------------------------------------------------- 12-13: identity, re-take


def test_12_commit_needs_no_git_identity_on_the_machine(world, tmp_path, monkeypatch):
    refs, _, clone = world
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in FIXTURE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("EMAIL", raising=False)

    sha = refs.commit(message_for("T01", "session-a", "build", NOW), None)
    assert len(sha) == 40
    assert git("cat-file", "-t", sha, cwd=clone).stdout.strip() == "commit"


def test_13_a_released_lock_is_free_for_the_next_session(world):
    refs, _, _ = world
    first = lock_for(refs, "t01", "session-a")
    assert first.acquire("build", NOW) is True
    first.release()
    second = lock_for(refs, "t01", "session-b")
    assert second.acquire("build", NOW) is True
    assert second.still_mine() is True


# ------------------------------------- 14: GitHubRefs stops discarding answers


def test_14_github_refs_delete_raises_on_a_refusal():
    def runner(*args, body=None):
        if "DELETE" in args:
            return 1, "HTTP 403 not permitted"
        return 0, "{}"

    with pytest.raises(LockError, match="403"):
        GitHubRefs("owner/repo", runner=runner).delete(REF)


# --------------------------------------------- 15: what every push looks like


def test_15_every_push_is_porcelain_never_forced_and_plus_only_over_a_marker(world):
    _, remote, clone = world
    seen: list[list[str]] = []

    def spy(argv, env):
        seen.append(list(argv))
        done = subprocess.run(
            argv, capture_output=True, text=True, check=False, env=env
        )
        return done.returncode, done.stdout, done.stderr

    refs = GitPushRefs(clone, runner=spy)
    # Every kind of push the backend makes: create on absent, a refused create,
    # update, a refused update, release, re-create over a marker.
    tip = held(refs)
    rival = refs.commit(message_for("T01", "session-b", "build", NOW), None)
    assert refs.create(REF, rival) is False
    child = refs.commit(message_for("T01", "session-a", "renew", NOW), tip)
    assert refs.update(REF, child, tip) is True
    assert refs.update(REF, rival, tip) is False
    refs.delete(REF)
    again = refs.commit(message_for("T01", "session-c", "build", NOW), None)
    assert refs.create(REF, again) is True

    pushes = [argv for argv in seen if "push" in argv]
    assert len(pushes) >= 5, pushes
    plus_seen = False
    for argv in pushes:
        assert "--porcelain" in argv, argv
        assert "--force" not in argv, argv
        assert "-f" not in argv, argv
        forcing = [a for a in argv if a.startswith(("--force", "-f"))]
        assert all(a.startswith("--force-with-lease=") for a in forcing), argv
        plus = [a for a in argv if a.startswith("+")]
        if plus:
            plus_seen = True
            leases = [a for a in argv if a.startswith("--force-with-lease=")]
            assert len(leases) == 1, argv
            ref, _, expect = (
                leases[0].removeprefix("--force-with-lease=").partition(":")
            )
            assert ref == REF, argv
            assert expect, f"a + push must lease a named marker, not absence: {argv}"
            assert is_release_marker(remote.message(expect)), argv
    assert plus_seen, "re-creating over a marker must have used the + push"
