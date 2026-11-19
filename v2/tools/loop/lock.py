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

GitHub's own documentation, read fresh on 19 Nov 2026, confirms the *semantics*
of the second: ``force`` is a boolean defaulting to ``false``, described as
"Indicates whether to force the update or to make sure the update is a
fast-forward update". It does **not** state the status code returned when a
non-fast-forward update is refused, nor the one returned when a reference is
created twice. Both therefore stay **[Likely]** until step 4's proof against
GitHub has been run. See the build report: that proof could not be run from the
building session, so these two claims are not yet [Certain — run].

Two residual gaps are known and accepted (red-team third pass, finding l):
a small window remains between ``still_mine`` and the push that follows it, and
a lock's age is read from a date the holding session wrote. A session can only
keep or lose its *own* lock by getting them wrong, and the overrun halt bounds
the damage.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

LOCK_PREFIX = "lock/"
STAMP = "Chronos-Lock-At:"
SESSION = "Chronos-Lock-Session:"
ACTION = "Chronos-Lock-Action:"


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
        self._run("-X", "DELETE", self._path(ref))
