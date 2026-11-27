"""B05A known answers 16-19 -- the release marker, as the rest of the loop sees it.

A release no longer deletes the ``lock/<id>`` branch (a cloud session cannot
delete a branch by any route, B05 trap 1); it moves the branch onto a marker
commit. So everything that reads ``lock/*`` must read the tip, not just test
that the branch exists. These pin the three readers: ``is_release_marker``,
``facts._locks`` and ``loop_cli`` (``production_refs`` and ``finish``).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import facts
from lock import GitPushRefs, Lock, is_release_marker, message_for, ref_for

REPO_ROOT = Path(__file__).resolve().parents[4]
CLI_PATH = REPO_ROOT / ".claude" / "skills" / "chronos-tick" / "loop_cli.py"
NOW = datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)

MARKER = "lock released\n\nChronos-Lock-Released: 2026-11-27T12:00:00+00:00\n"
B09_MESSAGE = message_for("B09", "session-a", "start_build", NOW)


def load_cli():
    spec = importlib.util.spec_from_file_location("loop_cli_b05a", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["git"] + (["-C", str(cwd)] if cwd else []) + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False, env=dict(os.environ)
    )


# ------------------------------------------------------- 16: the marker itself


def test_16_is_release_marker_tells_a_marker_from_a_lock_and_from_nothing():
    assert is_release_marker(MARKER) is True
    assert is_release_marker(message_for("B06", "session-a", "build", NOW)) is False
    assert is_release_marker("") is False


# ------------------------------------------------ 17: the loop skips released


def test_17_facts_locks_does_not_report_a_released_lock():
    def fake_git(repo_dir, *args):
        assert args[:3] == ("log", "-1", "--format=%cI%n%B"), args
        if args[-1] == "refs/remotes/origin/lock/b06":
            return "2026-11-27T12:05:00+00:00\n" + MARKER.strip()
        if args[-1] == "refs/remotes/origin/lock/b09":
            return "2026-11-27T12:00:00+00:00\n" + B09_MESSAGE.strip()
        raise AssertionError(f"unexpected git call {args}")

    got = facts._locks(fake_git, Path("/nowhere"), {"lock/b06", "lock/b09", "v2-build"})

    assert "B06" not in got
    assert set(got) == {"B09"}
    at, message = got["B09"]
    assert at == datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)
    # Read exactly as today: the body's lines after the date, joined by spaces.
    assert message == " ".join(B09_MESSAGE.strip().split("\n"))


# --------------------------------------------------- 18-19: loop_cli's backend


def test_18_production_refs_is_the_git_push_backend_on_the_repo_root(tmp_path):
    cli = load_cli()
    refs = cli.production_refs(tmp_path, "owner/repo")
    assert isinstance(refs, GitPushRefs)
    assert refs.repo_dir == tmp_path


def test_19_finish_releases_through_git_push_and_leaves_a_marker(tmp_path):
    bare = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    assert git("init", "-q", "--bare", str(bare)).returncode == 0
    assert git("init", "-q", str(clone)).returncode == 0
    assert git("remote", "add", "origin", bare.as_uri(), cwd=clone).returncode == 0

    refs = GitPushRefs(clone)
    assert (
        Lock(refs=refs, build_id="T01", session="session-a").acquire("build", NOW)
        is True
    )

    cli = load_cli()
    code, out = cli.finish(
        ["--build", "T01"],
        status_report=lambda argv: (0, "nothing is running.", ""),
        refs=refs,
    )
    assert code == 0
    assert "released" in out
    assert "could not be released" not in out

    tip = git("rev-parse", "--verify", "-q", ref_for("T01"), cwd=bare).stdout.strip()
    assert tip, "the branch stays behind; only its tip changes"
    assert (
        is_release_marker(git("log", "-1", "--format=%B", tip, cwd=bare).stdout) is True
    )
