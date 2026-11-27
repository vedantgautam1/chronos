"""The lock that stops two sessions doing the same work.

Every action takes a lock first. The lock is a git reference,
``refs/heads/lock/<id>``, created through the GitHub API, pointing at a commit
whose message records the session, the action and the time.

The whole design rests on two properties of the API:

* **creating a reference that already exists is refused**, so of two sessions
  racing to acquire, one wins;
* **updating a reference with ``force: false`` is refused unless the update is
  a fast-forward**, so of two sessions racing to take over the same stale lock,
  the first wins and the second is refused -- its commit is built on the stale
  commit and so is no longer a descendant of the reference.

**Both are [Certain — run], proved against GitHub on 19 Nov 2026** by step
4(ii): 20 racing ``acquire`` pairs and 20 racing ``take_over`` pairs, exactly
one winner in every one of the 40. The harness is
``prove_lock_on_github.py`` beside this file; the full output is in the build
report.

GitHub's documentation, read fresh the same day, confirms the *semantics* of
the second -- ``force`` is a boolean defaulting to ``false``, described as
"Indicates whether to force the update or to make sure the update is a
fast-forward update" -- but states the status code for neither refusal. The
run supplied both, and they are recorded here because nothing else documents
them:

* a duplicate create is refused **422 "Reference already exists"**;
* a non-fast-forward update with ``force: false`` is refused
  **422 "Reference cannot be updated"**.

Two residual gaps are known and accepted (red-team third pass, finding l):
a small window remains between ``still_mine`` and the push that follows it, and
a lock's age is read from a date the holding session wrote. A session can only
keep or lose its *own* lock by getting them wrong, and the overrun halt bounds
the damage.

**Two backends (B05A).** ``GitHubRefs`` is the original, over the REST API. A
cloud session's proxy refuses every REST write it makes (B05,
``probe/B05-environment-measurements.md`` §4), so the loop now runs on
``GitPushRefs``, which does the same through ``git push`` from a local clone.
``git push`` has both properties above: a push leased ``--force-with-lease=
<ref>:`` is refused if the ref exists, and a push without ``+`` is refused
unless it is a fast-forward (measured from a cloud session on 27 Nov, B05A
spec "Why"). A cloud session cannot delete a branch by any route, so
``GitPushRefs`` releases a lock by moving its branch onto a **release
marker** commit, which every reader treats as "no lock".
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LOCK_PREFIX = "lock/"
STAMP = "Chronos-Lock-At:"
SESSION = "Chronos-Lock-Session:"
ACTION = "Chronos-Lock-Action:"
RELEASED = "Chronos-Lock-Released:"  # a release marker's trailer (B05A)


class LockError(RuntimeError):
    """The lock could not be read. Never treated as "the lock is free"."""


def ref_for(build_id: str) -> str:
    return f"refs/heads/{LOCK_PREFIX}{build_id.lower()}"


def message_for(build_id: str, session: str, action: str, at: datetime) -> str:
    """The lock commit's message: who, what and when, so a later session can
    read the age and the holder without asking anything else."""
    return (
        f"lock {build_id} for {action}\n\n"
        f"{SESSION} {session}\n"
        f"{ACTION} {action}\n"
        f"{STAMP} {at.astimezone(UTC).isoformat()}\n"
    )


def release_message(at: datetime) -> str:
    """A release marker's message: the trailer, and no lock stamp."""
    return f"lock released\n\n{RELEASED} {at.astimezone(UTC).isoformat()}\n"


def is_release_marker(message: str) -> bool:
    """True for a release marker: a ``Chronos-Lock-Released:`` trailer and
    **no** ``Chronos-Lock-At:`` line. A message carrying both is a lock, so a
    marker can never hide a lock that also claims to be held."""
    text = message or ""
    return bool(
        re.search(rf"^{RELEASED}", text, re.MULTILINE)
        and not re.search(rf"^{STAMP}", text, re.MULTILINE)
    )


def stamp_in(message: str) -> datetime | None:
    found = re.search(rf"^{STAMP}\s*(\S+)", message or "", re.MULTILINE)
    if not found:
        return None
    try:
        return datetime.fromisoformat(found.group(1)).astimezone(UTC)
    except ValueError:
        return None


@dataclass
class Lock:
    """One build's or gate's lock, held by one session."""

    refs: object  # a backend: read / create / update / delete / commit
    build_id: str
    session: str
    claim_hours: int = 3
    mine: str | None = None  # the last lock commit this session wrote

    @property
    def ref(self) -> str:
        return ref_for(self.build_id)

    # ---------------------------------------------------------------- take

    def acquire(self, action: str, now: datetime | None = None) -> bool:
        """Create the reference. Refused if it exists, so one session wins."""
        now = now or datetime.now(UTC)
        sha = self.refs.commit(message_for(self.build_id, self.session, action, now), None)
        if not self.refs.create(self.ref, sha):
            return False
        self.mine = sha
        return True

    def take_over(self, action: str, now: datetime | None = None) -> bool:
        """Claim a stale lock: a commit on top of the stale one, moved there
        without force. Two sessions racing both build on the same stale commit,
        so the first update wins and the second is no longer a fast-forward."""
        now = now or datetime.now(UTC)
        current = self.refs.read(self.ref)
        if current is None:
            return self.acquire(action, now)
        if not self.is_stale(now):
            return False
        sha = self.refs.commit(message_for(self.build_id, self.session, action, now), current)
        if not self.refs.update(self.ref, sha, current):
            return False
        self.mine = sha
        return True

    # -------------------------------------------------------------- hold

    def renew(self, action: str, now: datetime | None = None) -> bool:
        """On every push: a commit on top of this session's own lock commit,
        moved there without force. Refused if the lock is no longer ours."""
        now = now or datetime.now(UTC)
        if self.mine is None or not self.still_mine():
            return False
        sha = self.refs.commit(message_for(self.build_id, self.session, action, now), self.mine)
        if not self.refs.update(self.ref, sha, self.mine):
            return False
        self.mine = sha
        return True

    def still_mine(self) -> bool:
        """Checked before every push. A session that has lost its lock stops
        writing rather than pushing over the winner."""
        return self.mine is not None and self.refs.read(self.ref) == self.mine

    def is_stale(self, now: datetime | None = None) -> bool:
        """Older than ``claim_hours``, by the date the holding session wrote.

        A lock that cannot be read is **not** stale: a lock the loop cannot
        judge is left alone, because treating it as free is the one answer that
        lets two sessions run at once.
        """
        now = now or datetime.now(UTC)
        sha = self.refs.read(self.ref)
        if sha is None:
            return False
        at = stamp_in(self.refs.message(sha))
        if at is None:
            raise LockError(
                f"{self.ref} points at {sha[:8]}, whose message carries no "
                f"{STAMP} date, so its age cannot be read. That is a halt, not a free lock."
            )
        return (now - at).total_seconds() > self.claim_hours * 3600

    def release(self) -> None:
        self.refs.delete(self.ref)
        self.mine = None


def push_if_mine(lock: Lock, push) -> bool:
    """Every push goes through here. The holder reads the reference and stops,
    without pushing, if it no longer points at its own last lock commit -- so a
    slow session that lost its lock stops writing instead of pushing over the
    session that won. Returns False when it refused."""
    if not lock.still_mine():
        return False
    push()
    return True


class GitHubRefs:
    """The production backend: references through the GitHub REST API.

    REST only, never GraphQL. ``create`` and ``update`` return False rather
    than raising when GitHub refuses, because a refusal is the normal outcome
    of a race and the caller's answer to it is "another session won".
    """

    def __init__(self, repo: str, tree_from: str = "v2-build", runner=None) -> None:
        self.repo = repo
        self.tree_from = tree_from
        self._run = runner or self._gh

    def _gh(self, *args: str, body: dict | None = None) -> tuple[int, str]:
        cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json", *args]
        if body is not None:
            cmd += ["--input", "-"]
        done = subprocess.run(
            cmd,
            input=json.dumps(body) if body is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode, (done.stdout or done.stderr)

    def _path(self, ref: str, *, singular: bool = False) -> str:
        """The API path for a reference.

        GitHub spells the reference WITHOUT its leading ``refs/`` in the URL
        and then puts it back in the route: reading is
        ``/git/ref/heads/<name>`` (singular, deliberately) and writing is
        ``/git/refs/heads/<name>``. Built in one place because doing it inline
        with string replacement is how ``delete`` came to be missing a segment
        entirely -- it asked for ``/git/heads/<name>``, which does not exist,
        so ``release`` could never have released anything.
        """
        bare = ref.removeprefix("refs/")
        return f"repos/{self.repo}/git/{'ref' if singular else 'refs'}/{bare}"

    def read(self, ref: str) -> str | None:
        code, out = self._run(self._path(ref, singular=True))
        if code != 0:
            return None
        try:
            return ((json.loads(out) or {}).get("object") or {}).get("sha")
        except json.JSONDecodeError:
            return None

    def message(self, sha: str) -> str:
        code, out = self._run(f"repos/{self.repo}/git/commits/{sha}")
        if code != 0:
            raise LockError(f"could not read lock commit {sha[:8]}")
        return (json.loads(out) or {}).get("message") or ""

    def commit(self, message: str, parent: str | None) -> str:
        code, out = self._run(f"repos/{self.repo}/branches/{self.tree_from}")
        if code != 0:
            raise LockError(f"could not read {self.tree_from} for a tree")
        tree = (((json.loads(out) or {}).get("commit") or {}).get("commit") or {}).get("tree")
        body = {"message": message, "tree": (tree or {}).get("sha")}
        if parent:
            body["parents"] = [parent]
        code, out = self._run("-X", "POST", f"repos/{self.repo}/git/commits", body=body)
        if code != 0:
            raise LockError(f"could not write a lock commit: {out[:200]}")
        return (json.loads(out) or {})["sha"]

    def create(self, ref: str, sha: str) -> bool:
        code, _ = self._run(
            "-X", "POST", f"repos/{self.repo}/git/refs", body={"ref": ref, "sha": sha}
        )
        return code == 0

    def update(self, ref: str, sha: str, expect: str | None = None) -> bool:
        """``force: false`` -- GitHub refuses anything but a fast-forward."""
        code, _ = self._run(
            "-X", "PATCH", self._path(ref), body={"sha": sha, "force": False}
        )
        return code == 0

    def delete(self, ref: str) -> None:
        # B05A Deliver 3 (raise on a non-zero answer) is held: it turns two
        # frozen tests in test_lock.py red. See status/B05A.json.
        self._run("-X", "DELETE", self._path(ref))


# --------------------------------------------------------------- git push


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# Lock commits carry this identity whatever the machine has, so the backend
# works where no git identity is configured at all. `test_lock.py`'s IDENTITY
# comment records how the opposite went green locally and red in CI.
LOOP_IDENTITY = {
    "GIT_AUTHOR_NAME": "Chronos Loop",
    "GIT_AUTHOR_EMAIL": "loop@chronos.invalid",
    "GIT_COMMITTER_NAME": "Chronos Loop",
    "GIT_COMMITTER_EMAIL": "loop@chronos.invalid",
}

def _subprocess_runner(argv: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    # Fixed argv, never a shell string.
    done = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)
    return done.returncode, done.stdout, done.stderr


class GitPushRefs:
    """The production backend from B05A: references through ``git push``.

    Works on a local clone, so it runs wherever ``git push`` does -- including
    a cloud session, whose proxy refuses ``GitHubRefs``'s REST writes.

    **The outcome of every push is read, never assumed.** Each push runs with
    ``--porcelain`` and is judged on that output and the exit code:

    * a ref line flagged ``!`` -- rejected -- makes ``create``/``update``
      return False: another session won, the normal end of a race;
    * any other non-zero exit (network, proxy, authentication, HTTP 429)
      raises ``LockError`` with git's stderr: that is a fault, not a holder;
    * ``delete`` raises on **every** failure, rejections included. A release
      that did not happen must never look like one that did.

    ``read`` raises when the remote cannot be read: an unreadable lock is
    never reported as free.

    Pushes and fetches go to the remote's **URL**, not its name, so git never
    updates a local remote-tracking ref as a side effect. Two threads (or two
    sessions in one clone) racing would otherwise contend for the same
    tracking-ref lock file, and a failure there is a local artefact that says
    nothing about who holds the lock.
    """

    def __init__(self, repo_dir, remote: str = "origin", runner=None) -> None:
        self.repo_dir = Path(repo_dir)
        self.remote = remote
        self._runner = runner or _subprocess_runner

    # ------------------------------------------------------------ plumbing

    def _git(self, *args: str) -> tuple[int, str, str]:
        env = {**os.environ, **LOOP_IDENTITY}
        return self._runner(["git", "-C", str(self.repo_dir), *args], env)

    def _must(self, what: str, *args: str) -> str:
        code, out, err = self._git(*args)
        if code != 0:
            raise LockError(f"could not {what}: git exit {code}: {(err or out).strip()}")
        return out

    def _url(self) -> str:
        return self._must(
            f"read the URL of remote {self.remote!r}", "remote", "get-url", "--push", self.remote
        ).strip()

    def _tip(self, ref: str) -> str | None:
        """The remote's tip for exactly ``ref``, or None if it has none."""
        out = self._must(f"read {ref} from {self.remote}", "ls-remote", self.remote, ref)
        for line in out.splitlines():
            sha, _, name = line.partition("\t")
            if name.strip() == ref:
                return sha.strip()
        return None

    def _have(self, sha: str) -> bool:
        code, _, _ = self._git("cat-file", "-e", f"{sha}^{{commit}}")
        return code == 0

    def _fetch(self, ref: str, sha: str) -> None:
        """Make ``sha`` (the tip just read for ``ref``) present locally."""
        if self._have(sha):
            return
        url = self._url()
        self._must(
            f"fetch {ref}", "fetch", "-q", "--no-tags", "--no-write-fetch-head", url, ref
        )
        if not self._have(sha):
            # The ref moved between ls-remote and the fetch. Ask for the
            # commit itself; a failure is a fault, never a free lock.
            self._must(
                f"fetch {sha[:8]} for {ref}",
                "fetch", "-q", "--no-tags", "--no-write-fetch-head", url, sha,
            )

    def _state(self, ref: str) -> tuple[str | None, bool]:
        """(remote tip, is it a release marker). (None, False) if absent."""
        sha = self._tip(ref)
        if sha is None:
            return None, False
        self._fetch(ref, sha)
        return sha, is_release_marker(self.message(sha))

    def _push(self, ref: str, refspec: str, *lease: str) -> tuple[bool, str]:
        """One push. (True, "") if it landed; (False, reason) if the remote
        refused the ref; raises ``LockError`` for anything else."""
        code, out, err = self._git("push", "--porcelain", *lease, self._url(), refspec)
        line = next(
            (ln for ln in out.splitlines() if ln[:1] in " +-*!=" and f":{ref}\t" in ln),
            None,
        )
        if line is not None and line.startswith("!"):
            # Rejected: `stale info`, `non-fast-forward`, `fetch first`,
            # `already exists`, or `remote rejected` when both racers saw the
            # same tip and the receiving end's compare-and-swap decided it.
            # All of them mean "not this session", and stopping is the safe
            # answer. The caller (delete) decides whether that is a fault.
            return False, line.split("\t", 2)[-1]
        if code != 0 or line is None:
            raise LockError(
                f"push to {ref} failed: git exit {code}: {(err or out).strip()}"
            )
        return True, ""

    # ------------------------------------------------------------ the duck type

    def read(self, ref: str) -> str | None:
        """The remote tip, or None if the ref is absent **or released**."""
        sha, released = self._state(ref)
        return None if released else sha

    def message(self, sha: str) -> str:
        if not self._have(sha):
            url = self._url()
            self._must(
                f"fetch lock commit {sha[:8]}",
                "fetch", "-q", "--no-tags", "--no-write-fetch-head", url, sha,
            )
        return self._must(f"read lock commit {sha[:8]}", "log", "-1", "--format=%B", sha)

    def commit(self, message: str, parent: str | None) -> str:
        args = ["commit-tree", EMPTY_TREE, "-m", message]
        if parent:
            args += ["-p", parent]
        return self._must("write a lock commit", *args).strip()

    def create(self, ref: str, sha: str) -> bool:
        tip, released = self._state(ref)
        if tip is None:
            ok, _ = self._push(ref, f"{sha}:{ref}", f"--force-with-lease={ref}:")
            return ok
        if released:
            # Replace the marker only if it is still the tip.
            ok, _ = self._push(ref, f"+{sha}:{ref}", f"--force-with-lease={ref}:{tip}")
            return ok
        return False  # held: another session's lock

    def update(self, ref: str, sha: str, expect: str | None = None) -> bool:
        """Never ``+`` and never ``--force``: only a fast-forward lands."""
        ok, _ = self._push(ref, f"{sha}:{ref}")
        return ok

    def delete(self, ref: str) -> None:
        """Release: a marker commit on top of the tip, pushed as a plain
        fast-forward. The branch stays (a cloud session cannot delete one)."""
        tip, released = self._state(ref)
        if tip is None or released:
            return
        marker = self.commit(release_message(datetime.now(UTC)), tip)
        ok, reason = self._push(ref, f"{marker}:{ref}")
        if not ok:
            raise LockError(
                f"could not release {ref}: the push was refused ({reason}). "
                "The lock is still held."
            )
