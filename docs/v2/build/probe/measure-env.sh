#!/usr/bin/env bash
# B05 — map which GitHub routes this session can reach.
#
# Run it inside a **Claude Code session**, because that is the environment the
# loop will actually run in. A plain Terminal with your own `gh` login proves
# nothing about the loop. Run it on the Mac and in a cloud session and compare.
#
#   bash docs/v2/build/probe/measure-env.sh
#
# Writes are probed against non-existent targets (PR/issue 99999, label
# __nope__, empty required fields) so an allowed route answers 404/422 instead
# of changing anything. The one exception is the lock cycle, which is the thing
# we actually need to know: it creates refs/heads/lock/mactest and then tries to
# delete it. If delete is refused that branch is left behind — the script says so.

set -uo pipefail
R="${CHRONOS_REPO:-vedantgautam1/chronos}"
BASE="${CHRONOS_BASE:-v2-build}"

say() { printf '%-42s %s\n' "$1" "$2"; }

# allowed vs blocked: "blocked" is only the proxy's own wording, nothing else.
probe() {
  local label="$1"; shift
  local out
  out=$(gh api "$@" 2>&1 | tr -d '\n' | head -c 400)
  if printf '%s' "$out" | grep -q "not permitted through this proxy"; then
    say "$label" "BLOCKED  (proxy)"
  else
    say "$label" "allowed  -> $(printf '%s' "$out" | head -c 90)"
  fi
}

echo "=== repo $R  base $BASE ==="
echo "=== identity, and WHERE IT COMES FROM ==="
# Which account matters, but so does which credential supplies it. A cloud
# session is handed a GH_TOKEN; a Mac session may instead use the founder's own
# `gh auth login` keychain. Today both are vedantgautam1 so they look the same.
# Once Claude's GitHub connection is switched to the automation they diverge,
# and attacks run under the founder's own token prove nothing about the
# automation. Print enough to tell them apart.
gh api user --jq '"  api user      login=\(.login)  id=\(.id)"' 2>&1 | head -2
# Never print the value — only whether it is set and how long it is. This
# output gets pasted around.
if [ -n "${GH_TOKEN:-}" ]; then say "  GH_TOKEN set?" "yes (${#GH_TOKEN} chars, value not shown)"; else say "  GH_TOKEN set?" "no"; fi
if [ -n "${GITHUB_TOKEN:-}" ]; then say "  GITHUB_TOKEN set?" "yes (${#GITHUB_TOKEN} chars, value not shown)"; else say "  GITHUB_TOKEN set?" "no"; fi
echo "  gh auth status:"
gh auth status 2>&1 | sed 's/^/    /' | head -8
echo
echo "=== reads ==="
probe "GET  /git/ref/heads/$BASE"        "repos/$R/git/ref/heads/$BASE"
probe "GET  /collaborators        (A12)" "repos/$R/collaborators"
probe "GET  /actions/permissions  (D2)"  "repos/$R/actions/permissions"
probe "GET  /rulesets             (D3)"  "repos/$R/rulesets"
printf '%-42s ' "GraphQL"
gh api graphql -f query='{viewer{login}}' 2>&1 | tr -d '\n' | head -c 90; echo
echo
echo "=== writes that must NOT change anything ==="
probe "POST   /pulls (open PR)"          -X POST "repos/$R/pulls" -f title= -f head=__nope__ -f base="$BASE"
probe "PUT    /pulls/99999/merge"        -X PUT  "repos/$R/pulls/99999/merge"
probe "POST   /pulls/99999/reviews"      -X POST "repos/$R/pulls/99999/reviews" -f event=APPROVE
# Deliberately a sha that cannot exist. The first version of this script aimed
# at origin/$BASE's real tip, which is fine where the route is blocked and is a
# permanent write where it is not: run on the Mac on 23 Nov it put a `success`
# status named __b05probe__ on v2-build's tip b9c4f5d, and GitHub does not let
# a status be deleted. A fake sha gets 422 "No commit found for SHA", which
# proves the route is reachable and changes nothing.
probe "POST   /statuses/<fake sha> (A4)" -X POST "repos/$R/statuses/deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" -f state=success -f context=__b05probe__
probe "POST   /issues (halt issue)"      -X POST "repos/$R/issues" -f title=
probe "PATCH  /issues/99999       (A11)" -X PATCH "repos/$R/issues/99999" -f state=closed
probe "DELETE /labels/__nope__    (A11)" -X DELETE "repos/$R/labels/__nope__"
probe "POST   /rulesets            (A6)" -X POST "repos/$R/rulesets" -f name=
echo
echo "=== the lock cycle, for real, on refs/heads/lock/mactest ==="
SHA=$(git rev-parse "origin/$BASE")
TREE=$(gh api "repos/$R/git/commits/$SHA" --jq '.tree.sha' 2>/dev/null)
if [ -z "${TREE:-}" ]; then
  echo "  could not read the base tree; the lock cycle was not attempted"
else
  printf '%-42s ' "POST /git/commits   (lock take, 1/2)"
  C=$(printf '{"message":"b05 lock probe","tree":"%s","parents":["%s"]}' "$TREE" "$SHA" \
      | gh api -X POST "repos/$R/git/commits" --input - --jq '.sha' 2>&1 | tr -d '\n')
  echo "$(printf '%s' "$C" | head -c 90)"
  LOCKSHA=$SHA
  printf '%s' "$C" | grep -qE '^[0-9a-f]{40}$' && LOCKSHA=$C

  printf '%-42s ' "POST /git/refs      (lock take, 2/2)"
  printf '{"ref":"refs/heads/lock/mactest","sha":"%s"}' "$LOCKSHA" \
    | gh api -X POST "repos/$R/git/refs" --input - 2>&1 | tr -d '\n' | head -c 90; echo

  # Did the ref actually come into existence? Everything below is only
  # meaningful if it did. Asking GitHub beats trusting the call's output.
  TOOK=no
  gh api "repos/$R/git/ref/heads/lock/mactest" >/dev/null 2>&1 && TOOK=yes
  say "lock ref actually created?" "$TOOK"

  if [ "$TOOK" = "no" ]; then
    echo "  -> the take failed, so renew/release say nothing here. Not attempted."
  else
    printf '%-42s ' "POST /git/refs again (must be 422)"
    printf '{"ref":"refs/heads/lock/mactest","sha":"%s"}' "$LOCKSHA" \
      | gh api -X POST "repos/$R/git/refs" --input - 2>&1 | tr -d '\n' | head -c 90; echo

    probe "PATCH  /git/refs    (lock renew)" -X PATCH "repos/$R/git/refs/heads/lock/mactest" -F sha="$LOCKSHA" -F force=false
    probe "DELETE /git/refs  (lock release)" -X DELETE "repos/$R/git/refs/heads/lock/mactest"

    printf '%-42s ' "VERDICT: lock take+release"
    if gh api "repos/$R/git/ref/heads/lock/mactest" >/dev/null 2>&1; then
      echo "TAKEN BUT NOT RELEASED — delete lock/mactest by hand"
    else
      echo "FULL CYCLE WORKED"
    fi
  fi
fi
echo
echo "=== git push: create, force, delete ==="
if [ "${CHRONOS_PUSH_TEST:-0}" != "1" ]; then
  echo "  skipped (set CHRONOS_PUSH_TEST=1 to run it)."
  echo "  It is only worth running where DELETE /git/refs above was refused:"
  echo "  it creates doc/b05-pushtest, and where no delete route works that"
  echo "  branch cannot be removed afterwards."
else
  printf '%-42s ' "git push (create doc/b05-pushtest)"
  git push origin "$SHA:refs/heads/doc/b05-pushtest" >/dev/null 2>&1 && echo "allowed" || echo "refused"
  printf '%-42s ' "git push --force"
  git push --force origin "$SHA:refs/heads/doc/b05-pushtest" >/dev/null 2>&1 && echo "allowed" || echo "refused"
  printf '%-42s ' "git push --delete"
  git push origin --delete refs/heads/doc/b05-pushtest >/dev/null 2>&1 && echo "allowed" || echo "refused"
  printf '%-42s ' "DELETE /git/refs (same branch)"
  gh api -X DELETE "repos/$R/git/refs/heads/doc/b05-pushtest" >/dev/null 2>&1 && echo "deleted" || echo "refused / already gone"
fi
echo
echo "=== housekeeping: the branch left over from round 1 ==="
printf '%-42s ' "DELETE doc/b05-deltest"
gh api -X DELETE "repos/$R/git/refs/heads/doc/b05-deltest" >/dev/null 2>&1 && echo "deleted" || echo "refused / already gone"
echo
echo "=== leftovers that need deleting by hand, if any ==="
gh api "repos/$R/branches?per_page=100" --jq '.[].name' 2>/dev/null \
  | grep -E '^lock/|^doc/b05-' || echo "  none"
