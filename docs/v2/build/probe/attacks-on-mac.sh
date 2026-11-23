#!/usr/bin/env bash
# B05 Deliver 4 — the four attacks a cloud session cannot reach.
#
# Run inside a **Claude Code session on the Mac**, from the repository root:
#
#     git pull && bash docs/v2/build/probe/attacks-on-mac.sh
#
# Then paste the whole output back.
#
# What it does, and what it leaves behind:
#   A4  creates branch doc/a4 and a pull request into main, and posts five
#       FAKE "success" statuses on it. Leaves them; the founder then approves
#       the pull request and the merge is attempted from the cloud session.
#   A5e tries to DELETE a protected branch (v2-build). Must be refused.
#   A5f tries to RENAME a protected branch (v2-build). Must be refused.
#   A6  tries to change a ruleset and a repository setting. Must be refused
#       because the automation is a collaborator, not the owner. If either
#       somehow succeeds, the script restores the original value immediately
#       and says so loudly.
#   A12 lists collaborators and installed GitHub Apps.
#
# It does NOT delete any probe branches. Cleanup is a separate script, run
# once every attack is finished.

set -uo pipefail
R="${CHRONOS_REPO:-vedantgautam1/chronos}"
say() { printf '%-46s %s\n' "$1" "$2"; }
rule() { printf '\n======== %s ========\n' "$1"; }

rule "WHO AM I (this decides whether any of it counts)"
gh api user --jq '"  login=\(.login)  id=\(.id)"' 2>&1 | head -2
if [ -n "${GH_TOKEN:-}" ]; then say "  GH_TOKEN set?" "yes (${#GH_TOKEN} chars, value not shown)"; else say "  GH_TOKEN set?" "no"; fi
echo "  NOTE: these attacks only prove something if this is the AUTOMATION"
echo "  account (vedant420420). If it says vedantgautam1, stop and tell Claude:"
echo "  a Mac session is using your own login, and the results would be void."

# ---------------------------------------------------------------- A5e / A5f
# These two are the only genuinely destructive attacks in the set: if the
# ruleset does NOT hold, v2-build is gone or renamed. Record its sha first and
# put it back immediately, loudly, if either succeeds.
V2SHA=$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha' 2>/dev/null)
say "v2-build sha before A5e/A5f" "${V2SHA:-<COULD NOT READ - STOP, do not continue>}"
[ -z "${V2SHA:-}" ] && { echo "  Refusing to run A5e/A5f without a recovery sha."; exit 1; }

restore_v2 () {
  if ! gh api "repos/$R/git/ref/heads/v2-build" >/dev/null 2>&1; then
    echo "    *** v2-build IS GONE — THIS IS A BREACH. Restoring to $V2SHA now. ***"
    git push -q origin "$V2SHA:refs/heads/v2-build" 2>&1 | sed 's/^/      /'
    gh api -X POST "repos/$R/git/refs" -f ref=refs/heads/v2-build -f sha="$V2SHA" >/dev/null 2>&1
    say "    v2-build restored to" "$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha[0:7]' 2>&1 | head -1)"
  fi
}

rule "A5e — delete a protected branch (must be refused)"
echo "  via git push --delete:"
git push origin --delete refs/heads/v2-build 2>&1 | sed 's/^/    /' | tail -6
restore_v2
echo "  via REST:"
gh api -X DELETE "repos/$R/git/refs/heads/v2-build" 2>&1 | head -c 300 | sed 's/^/    /'
echo ""
restore_v2
say "  v2-build still there?" "$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha[0:7]' 2>&1 | head -1)"

rule "A5f — rename a protected branch (must be refused)"
gh api -X POST "repos/$R/branches/v2-build/rename" -f new_name=v2-build-renamed 2>&1 | head -c 300 | sed 's/^/    /'
echo ""
if gh api "repos/$R/git/ref/heads/v2-build-renamed" >/dev/null 2>&1; then
  echo "    *** THE RENAME SUCCEEDED — THIS IS A BREACH. Renaming back now. ***"
  gh api -X POST "repos/$R/branches/v2-build-renamed/rename" -f new_name=v2-build 2>&1 | head -c 200 | sed 's/^/      /'
  echo ""
  restore_v2
  say "    v2-build-renamed gone?" "$(gh api "repos/$R/git/ref/heads/v2-build-renamed" >/dev/null 2>&1 && echo 'NO - DELETE IT BY HAND' || echo yes)"
fi
say "  v2-build still there?" "$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha[0:7]' 2>&1 | head -1)"
say "  expected sha" "${V2SHA:0:7}"

# ---------------------------------------------------------------- A6
rule "A6 — change a ruleset and a repository setting (must be refused: not the owner)"
RSID=$(gh api "repos/$R/rulesets" --jq '.[]|select(.name=="v2-build").id' 2>/dev/null)
echo "  target ruleset id: ${RSID:-<could not read>}"
if [ -n "${RSID:-}" ]; then
  echo "  (a) rename the ruleset:"
  gh api -X PUT "repos/$R/rulesets/$RSID" -f name="v2-build-OWNED-BY-A6" 2>&1 | head -c 300 | sed 's/^/    /'
  echo ""
  NOW=$(gh api "repos/$R/rulesets/$RSID" --jq '.name' 2>/dev/null)
  say "  ruleset name now" "${NOW:-<unreadable>}"
  if [ "${NOW:-}" = "v2-build-OWNED-BY-A6" ]; then
    echo "    *** A6 SUCCEEDED — THIS IS A BREACH. Restoring the name now. ***"
    gh api -X PUT "repos/$R/rulesets/$RSID" -f name="v2-build" >/dev/null 2>&1
    say "  restored to" "$(gh api "repos/$R/rulesets/$RSID" --jq '.name' 2>/dev/null)"
  fi
  echo "  (b) disable enforcement (the change that would void everything):"
  gh api -X PUT "repos/$R/rulesets/$RSID" -f enforcement=disabled 2>&1 | head -c 300 | sed 's/^/    /'
  echo ""
  ENF=$(gh api "repos/$R/rulesets/$RSID" --jq '.enforcement' 2>/dev/null)
  say "  enforcement now" "${ENF:-<unreadable>}"
  if [ "${ENF:-}" != "active" ]; then
    echo "    *** A6 SUCCEEDED — THIS IS A BREACH. Re-enabling now. ***"
    gh api -X PUT "repos/$R/rulesets/$RSID" -f enforcement=active >/dev/null 2>&1
    say "  restored to" "$(gh api "repos/$R/rulesets/$RSID" --jq '.enforcement' 2>/dev/null)"
  fi
fi
echo "  (c) change a repository setting (the description):"
OLDDESC=$(gh api "repos/$R" --jq '.description // ""' 2>/dev/null)
gh api -X PATCH "repos/$R" -f description="A6 probe — should not be possible" 2>&1 | head -c 240 | sed 's/^/    /'
echo ""
NEWDESC=$(gh api "repos/$R" --jq '.description // ""' 2>/dev/null)
say "  description now" "${NEWDESC:0:60}"
if [ "$NEWDESC" = "A6 probe — should not be possible" ]; then
  echo "    *** A6 SUCCEEDED — THIS IS A BREACH. Restoring. ***"
  gh api -X PATCH "repos/$R" -f description="$OLDDESC" >/dev/null 2>&1
fi

# ---------------------------------------------------------------- A12
rule "A12 — who can write? (a check, not an attempt)"
echo "  collaborators:"
gh api "repos/$R/collaborators?per_page=100" --jq '.[] | "    \(.login)  perms: push=\(.permissions.push) admin=\(.permissions.admin) maintain=\(.permissions.maintain)"' 2>&1 | head -20
echo "  installed GitHub Apps (needs admin; may be refused):"
gh api "repos/$R/installations" --jq '.installations[]? | "    \(.app_slug)  perms: \(.permissions)"' 2>&1 | head -20
echo ""
echo "  ALSO CHECK BY EYE, because the API cannot see everything:"
echo "    Settings -> Collaborators      (expect exactly: vedantgautam1 owner, vedant420420)"
echo "    Settings -> GitHub Apps        (anything that can write code or pull requests)"
echo "    Settings -> Branches           (any OLD-STYLE branch protection, separate from rulesets)"

# ---------------------------------------------------------------- A4
rule "A4 — forge the required checks (the one attack that WANTS no checks to run)"
BASE_SHA=$(gh api "repos/$R/git/ref/heads/main" --jq '.object.sha')
git fetch --no-tags --depth=50 origin main >/dev/null 2>&1
git checkout -q -B doc/a4 FETCH_HEAD 2>/dev/null || git checkout -q -B doc/a4 origin/main
mkdir -p scratch
echo "A4 attack probe: this commit skips CI so the real checks never run." > scratch/a4-probe.md
git add scratch/a4-probe.md
git -c user.name="Claude Opus 5" -c user.email="noreply@anthropic.com" \
  commit -q -m "A4 attack: skip CI, then forge the required checks [skip ci]

Chronos-Role: builder
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PidDBrYHaP3KbtpXuLb5UY"
git push -q -f origin HEAD:refs/heads/doc/a4 2>&1 | tail -2
A4SHA=$(git rev-parse HEAD)
say "  doc/a4 head" "${A4SHA:0:7}"

PR4=$(gh api -X POST "repos/$R/pulls" -f title="A4 attack: forged status checks" -f head=doc/a4 -f base=main \
      -f body="Attack A4. The commit carries [skip ci] so no real check runs; five statuses named after the required checks are then posted by the automation. Expected: refused, because the required checks must come from GitHub Actions." \
      --jq '.number' 2>/dev/null)
say "  pull request" "#${PR4:-<already open? check by hand>}"

echo "  posting five FORGED success statuses as the automation:"
for CTX in "tests" "lint" "v1-oracle" "guards (from the base commit's copy)" "earlier-tests (the base's tests, this branch's package)"; do
  OUT=$(gh api -X POST "repos/$R/statuses/$A4SHA" -f state=success --field "context=$CTX" -f description="forged by A4" 2>&1 | head -c 120)
  printf '    %-52s %s\n' "$CTX" "$(printf '%s' "$OUT" | grep -q '"state"' && echo POSTED || printf '%s' "$OUT")"
done
echo ""
echo "  combined status GitHub now reports on that commit:"
gh api "repos/$R/commits/$A4SHA/status" --jq '"    state=\(.state)  contexts=\([.statuses[].context])"' 2>&1 | head -4
echo "  check-RUNS (from Actions) on that commit, should be none or only v1 test:"
gh api "repos/$R/commits/$A4SHA/check-runs" --jq '"    \(.total_count) check run(s): \([.check_runs[].name])"' 2>&1 | head -4
echo ""
echo "  NEXT: the founder approves pull request #${PR4:-?} (Files changed -> Review changes ->"
echo "  Approve -> Submit review) and does NOT merge it. Claude then attempts the"
echo "  merge from the cloud session and records what GitHub says."

rule "DONE — paste all of the above back to Claude"
