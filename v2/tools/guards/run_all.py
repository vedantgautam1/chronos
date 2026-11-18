"""Run every guard and print a summary a non-technical reader can act on.

Invoked by ``run_guards.sh``, which is the thing that decides *which copy* of
this code runs -- the base commit's, or, under the bootstrap rule, the pull
request's own. That decision cannot live here: a pull request that had replaced
this file would be deciding it.

Exits non-zero if any guard produced a finding, or if any guard could not do
its job. A guard that cannot run is never a pass.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import checks
from gitrepo import Context, Finding, GuardError

GUARDS = (
    ("branch_kind", checks.branch_kind),
    ("v1_frozen", checks.v1_frozen),
    ("scope", checks.scope),
    ("roles", checks.roles),
    ("frozen_files", checks.frozen_files),
    ("plumbing", checks.plumbing),
    ("protected", checks.protected),
)

BOOTSTRAP_NOTICE = (
    "**BOOTSTRAP: the base commit has no guard code, so these guards ran from the "
    "pull request's own copy. A branch can therefore have changed what just "
    "checked it. By construction this happens exactly twice -- this build's own "
    "pull request, and the first gate move -- and the founder is present for both.**"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Chronos v2 guards. In CI every argument is passed explicitly. "
            "Run by hand with no arguments, each one is worked out from the checkout "
            "you are standing in, so the command in specs/README.md rule 7 works as "
            "it is written."
        )
    )
    parser.add_argument("--repo")
    parser.add_argument("--base-sha")
    parser.add_argument("--head-sha")
    parser.add_argument("--head-ref")
    parser.add_argument("--base-ref")
    parser.add_argument("--fork", action="store_true", help="the head branch is in a fork")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="this copy came from the pull request because the base has no guard code",
    )
    parser.add_argument(
        "--earlier-tests",
        action="store_true",
        help="run the earlier builds' tests against this pull request's package instead",
    )
    args = parser.parse_args(argv)
    _fill_from_git(args)

    if args.bootstrap:
        print(BOOTSTRAP_NOTICE)
        print()

    ctx = Context(
        repo=Path(args.repo),
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        head_ref=args.head_ref,
        base_ref=args.base_ref,
        is_fork=args.fork,
    )

    print(f"Guards for {args.head_ref} -> {args.base_ref}")
    print(f"  head {args.head_sha[:12]}   base {args.base_sha[:12]}")
    print(f"  {len(ctx.commits)} commit(s), {len(ctx.changed_paths)} path(s) changed")
    print()

    if args.earlier_tests:
        return _earlier_tests(ctx, args)

    findings: list[Finding] = []
    for name, guard in GUARDS:
        try:
            result = guard(ctx)
        except GuardError as exc:
            result = [Finding(name, f"could not run: {exc}")]
        except Exception as exc:  # noqa: BLE001 - a crashed guard must not pass
            result = [Finding(name, f"crashed: {type(exc).__name__}: {exc}")]
        findings += result
        print(f"  {'FAIL' if result else 'ok  '}  {name}" + (f"  ({len(result)})" if result else ""))

    try:
        notes = checks.notes(ctx)
    except GuardError as exc:
        notes = []
        findings.append(Finding("notes", f"could not be collected: {exc}"))

    if notes:
        print()
        print("For the founder and the reviewer to read (not failures):")
        for note in notes:
            print(f"  - {note.guard}: {note.message}")

    print()
    if findings:
        print(f"{len(findings)} finding(s). This pull request does not pass the guards.")
        print()
        for finding in findings:
            print(f"  [{finding.guard}] {finding.message}")
            print()
    else:
        print("No findings.")

    print(
        "These guards are tripwires: they catch a session that makes a mistake or "
        "takes a shortcut.\nThey are not proof against a session that sets out to "
        "deceive. What stands behind them is\nGitHub's own rules on main and on "
        "founder-owned files, and the audit at every gate."
    )
    return 1 if findings else 0


def _fill_from_git(args: argparse.Namespace) -> None:
    """Work out anything not passed, from the checkout we are standing in.

    Only for running by hand. CI passes all five, because there the base commit
    is the one GitHub names in the event, not whatever the local clone happens
    to have fetched.
    """
    import subprocess

    def git(*cmd: str) -> str:
        return subprocess.run(
            ("git", "-C", args.repo or ".", *cmd),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    if not args.repo:
        args.repo = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    if not args.head_sha:
        args.head_sha = git("rev-parse", "HEAD")
    if not args.head_ref:
        args.head_ref = git("rev-parse", "--abbrev-ref", "HEAD")
    if not args.base_ref:
        args.base_ref = "v2-build"
    if not args.base_sha:
        for candidate in (f"origin/{args.base_ref}", args.base_ref):
            try:
                args.base_sha = git("merge-base", candidate, args.head_sha)
                break
            except subprocess.CalledProcessError:
                continue
        if not args.base_sha:
            raise SystemExit(
                f"could not resolve the base commit for {args.base_ref!r}. Pass "
                "--base-sha, or fetch the base branch."
            )


def _earlier_tests(ctx: Context, args: argparse.Namespace) -> int:
    """The second job: the earlier builds' tests, run as they were approved,
    against this pull request's package."""
    import tempfile

    import earlier_tests

    try:
        spec = ctx.base_spec
    except GuardError as exc:
        print(f"  FAIL  earlier-tests  could not read the base spec: {exc}")
        return 1
    may_modify = list(spec.may_modify_tests) if spec else []
    if may_modify:
        print(f"  the base spec allows these earlier test files to change: {may_modify}")

    with tempfile.TemporaryDirectory() as work:
        result = earlier_tests.run(
            repo=ctx.repo,
            base_sha=ctx.base_sha,
            head_sha=ctx.head_sha,
            workdir=Path(work) / "earlier",
            may_modify_tests=may_modify,
        )
        print(f"  {'FAIL' if not result.ok else 'ok  '}  earlier-tests")
        print(f"  base collected {len(result.base_ids)} test(s); {len(result.ran_ids)} ran")
        print()
        print(f"  {result.reason}")
        if not result.ok:
            print()
            print("  The earlier builds' tests are run from the base branch's copy of")
            print("  everything under v2/ except the package, the migrations and the two")
            print("  dependency files, with entry-point plugins off. So this is a result")
            print("  about this pull request's package, not about its tests.")
            print()
            print(result.output[-4000:])
        return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
