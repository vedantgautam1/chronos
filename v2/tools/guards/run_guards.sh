#!/usr/bin/env bash
# Decide which copy of the guard code runs, then run it.
#
# This is the one property the whole design rests on, so it lives in a script
# the tests drive directly rather than in shell inside the workflow YAML where
# no test would reach it:
#
#   * if the BASE commit has guard code, it is extracted into a temp folder
#     OUTSIDE the work tree and that copy runs. A pull request that rewrites
#     run_all.py, or widens its own spec, changes nothing.
#   * if the base commit has no guard code at all, the pull request's own copy
#     runs and says so in bold at the top of its summary (the bootstrap rule).
#     By construction that happens exactly twice: B02's own pull request, and
#     the first gate move, since main has no guard code until G1 lands. The
#     founder is present for both.
#
# The extracted code is read as data and run with `python -I` from outside its
# own folder, per CLAUDE.md's conventions. It never imports or executes
# anything from the pull request.

set -euo pipefail

REPO=""; BASE_SHA=""; HEAD_SHA=""; HEAD_REF=""; BASE_REF=""; FORK=""; MODE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)     REPO="$2"; shift 2 ;;
    --base-sha) BASE_SHA="$2"; shift 2 ;;
    --head-sha) HEAD_SHA="$2"; shift 2 ;;
    --head-ref) HEAD_REF="$2"; shift 2 ;;
    --base-ref) BASE_REF="$2"; shift 2 ;;
    --fork)     FORK="--fork"; shift ;;
    # The second job goes through this same script, so there is one extraction
    # path and one entry point, both exercised by the tests.
    --earlier-tests) MODE="--earlier-tests"; shift ;;
    *) echo "run_guards.sh: unknown argument $1" >&2; exit 2 ;;
  esac
done

for required in REPO BASE_SHA HEAD_SHA HEAD_REF BASE_REF; do
  if [ -z "${!required}" ]; then
    echo "run_guards.sh: --${required,,} is required" >&2
    exit 2
  fi
done

PYTHON="${PYTHON:-python3}"
GUARD_PATH="v2/tools/guards"
ENTRY="$GUARD_PATH/run_all.py"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if git -C "$REPO" cat-file -e "$BASE_SHA:$ENTRY" 2>/dev/null; then
  # The base commit has guard code: extract it and run that copy.
  git -C "$REPO" archive "$BASE_SHA" "$GUARD_PATH" | tar -x -C "$WORK"
  RUNNER="$WORK/$ENTRY"
  BOOTSTRAP=""
else
  RUNNER="$REPO/$ENTRY"
  BOOTSTRAP="--bootstrap"
  if [ ! -f "$RUNNER" ]; then
    echo "run_guards.sh: no guard code at the base commit and none in the pull" >&2
    echo "request either ($RUNNER). Nothing to run, which is a halt, not a pass." >&2
    exit 2
  fi
fi

exec "$PYTHON" -I "$RUNNER" \
  --repo "$REPO" \
  --base-sha "$BASE_SHA" \
  --head-sha "$HEAD_SHA" \
  --head-ref "$HEAD_REF" \
  --base-ref "$BASE_REF" \
  ${FORK:+$FORK} ${BOOTSTRAP:+$BOOTSTRAP} ${MODE:+$MODE}
