#!/usr/bin/env bash
# B97's known-answer check (specs/B97-probe-whole-build.md). Exit 0 only if
# scratch/probe/b97.md holds exactly the bytes the spec gives.
set -euo pipefail
want="c758daee7e6c36a38ea6f6720160294e9cfe8931208927e1b3f078f8f71b71fd"
file="$(git rev-parse --show-toplevel)/scratch/probe/b97.md"
got="$(sha256sum "$file" | cut -d' ' -f1)"
if [ "$got" = "$want" ]; then
  echo "B97 known answer: PASS ($got)"
else
  echo "B97 known answer: FAIL: expected $want, got $got"
  exit 1
fi
