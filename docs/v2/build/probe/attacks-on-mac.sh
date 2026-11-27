#!/usr/bin/env bash
# B05 Deliver 4 — the four attacks a cloud session cannot reach.
#
# MUST run as the AUTOMATION account. A Mac Claude Code session uses the
# founder's own `gh` login, so the token has to be supplied for the one
# command:
#
#     GH_TOKEN=<vedant420420 classic PAT, repo scope> \
#       bash docs/v2/build/probe/attacks-on-mac.sh
#
# Run it from the repository root, inside a Claude Code session on the Mac.
# Then paste the whole output back. Do not paste the token itself anywhere.
#
# Everything here goes through `gh api`, never `git push`, because GH_TOKEN
# governs gh and does NOT govern the Mac's git credential helper — a git push
# would silently run as the founder and the result would be void.
#
# What it leaves behind: branch doc/a4 and one pull request into main, with
# five forged statuses. Nothing else. Every destructive attempt is paired with
# a restore that runs immediately and says BREACH loudly if it was needed.

set -uo pipefail
R="${CHRONOS_REPO:-vedantgautam1/chronos}"
EXPECT_LOGIN="${CHRONOS_AUTOMATION:-vedant420420}"
say()  { printf '%-46s %s\n' "$1" "$2"; }
rule() { printf '\n======== %s ========\n' "$1"; }

rule "IDENTITY GATE — nothing below counts unless this is the automation"
WHO=$(gh api user --jq '.login' 2>/dev/null)
say "  acting as" "${WHO:-<could not read>}"
if [ -n "${GH_TOKEN:-}" ]; then say "  GH_TOKEN" "set (${#GH_TOKEN} chars, value not shown)"; else say "  GH_TOKEN" "NOT SET"; fi
if [ "${WHO:-}" != "$EXPECT_LOGIN" ]; then
  echo ""
  echo "  STOP. Expected $EXPECT_LOGIN, got '${WHO:-nothing}'."
  echo "  Running these as the owner would not test anything, and A5e/A6 would"
  echo "  really delete the branch / disable the ruleset. Nothing has been run."
  exit 1
fi
echo "  OK — proceeding as the automation."

V2SHA=$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha' 2>/dev/null)
say "v2-build sha (recovery point)" "${V2SHA:-<UNREADABLE>}"
[ -z "${V2SHA:-}" ] && { echo "  Refusing to run without a recovery sha."; exit 1; }

restore_v2 () {
  if ! gh api "repos/$R/git/ref/heads/v2-build" >/dev/null 2>&1; then
    echo "    *** v2-build IS GONE — BREACH. Restoring to ${V2SHA:0:7}. ***"
    gh api -X POST "repos/$R/git/refs" -f ref=refs/heads/v2-build -f sha="$V2SHA" >/dev/null 2>&1
    say "    restored to" "$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha[0:7]' 2>&1 | head -1)"
  fi
}

# ------------------------------------------------------------------ A5e/A5f
rule "A5e — delete a protected branch (must be refused)"
gh api -X DELETE "repos/$R/git/refs/heads/v2-build" 2>&1 | head -c 320 | sed 's/^/    /'
echo ""
restore_v2
say "  v2-build" "$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha[0:7]' 2>&1 | head -1)  (expected ${V2SHA:0:7})"

rule "A5f — rename a protected branch (must be refused)"
gh api -X POST "repos/$R/branches/v2-build/rename" -f new_name=v2-build-renamed 2>&1 | head -c 320 | sed 's/^/    /'
echo ""
if gh api "repos/$R/git/ref/heads/v2-build-renamed" >/dev/null 2>&1; then
  echo "    *** THE RENAME SUCCEEDED — BREACH. Renaming back. ***"
  gh api -X POST "repos/$R/branches/v2-build-renamed/rename" -f new_name=v2-build 2>&1 | head -c 200 | sed 's/^/      /'
  echo ""
  restore_v2
  say "    v2-build-renamed gone?" "$(gh api "repos/$R/git/ref/heads/v2-build-renamed" >/dev/null 2>&1 && echo 'NO — DELETE BY HAND' || echo yes)"
fi
say "  v2-build" "$(gh api "repos/$R/git/ref/heads/v2-build" --jq '.object.sha[0:7]' 2>&1 | head -1)  (expected ${V2SHA:0:7})"

# ---------------------------------------------------------------------- A6
rule "A6 — change a ruleset / a repository setting (must be refused: not the owner)"
RSID=$(gh api "repos/$R/rulesets" --jq '.[]|select(.name=="v2-build").id' 2>/dev/null)
say "  target ruleset" "${RSID:-<could not read>}"
if [ -n "${RSID:-}" ]; then
  echo "  (a) rename it:"
  gh api -X PUT "repos/$R/rulesets/$RSID" -f name="v2-build-OWNED-BY-A6" 2>&1 | head -c 300 | sed 's/^/    /'
  echo ""
  NOW=$(gh api "repos/$R/rulesets/$RSID" --jq '.name' 2>/dev/null)
  say "  name now" "${NOW:-<unreadable>}"
  [ "${NOW:-}" = "v2-build-OWNED-BY-A6" ] && {
    echo "    *** BREACH. Restoring. ***"
    gh api -X PUT "repos/$R/rulesets/$RSID" -f name="v2-build" >/dev/null 2>&1
    say "    restored to" "$(gh api "repos/$R/rulesets/$RSID" --jq '.name' 2>/dev/null)"; }

  echo "  (b) disable enforcement — the change that would void everything:"
  gh api -X PUT "repos/$R/rulesets/$RSID" -f enforcement=disabled 2>&1 | head -c 300 | sed 's/^/    /'
  echo ""
  ENF=$(gh api "repos/$R/rulesets/$RSID" --jq '.enforcement' 2>/dev/null)
  say "  enforcement now" "${ENF:-<unreadable>}"
  [ "${ENF:-active}" != "active" ] && {
    echo "    *** BREACH. Re-enabling. ***"
    gh api -X PUT "repos/$R/rulesets/$RSID" -f enforcement=active >/dev/null 2>&1
    say "    restored to" "$(gh api "repos/$R/rulesets/$RSID" --jq '.enforcement' 2>/dev/null)"; }
fi
echo "  (c) change a repository setting (the description):"
OLD=$(gh api "repos/$R" --jq '.description // ""' 2>/dev/null)
gh api -X PATCH "repos/$R" -f description="A6 probe - should not be possible" 2>&1 | head -c 260 | sed 's/^/    /'
echo ""
NEW=$(gh api "repos/$R" --jq '.description // ""' 2>/dev/null)
say "  description now" "${NEW:0:58}"
[ "$NEW" = "A6 probe - should not be possible" ] && {
  echo "    *** BREACH. Restoring. ***"
  gh api -X PATCH "repos/$R" -f description="$OLD" >/dev/null 2>&1; }

# --------------------------------------------------------------------- A12
rule "A12 — who can write? (a check, not an attempt)"
echo "  collaborators:"
gh api "repos/$R/collaborators?per_page=100" --jq '.[] | "    \(.login)  push=\(.permissions.push) admin=\(.permissions.admin) maintain=\(.permissions.maintain)"' 2>&1 | head -20
echo "  installed GitHub Apps (needs admin; likely refused as the automation):"
gh api "repos/$R/installations" --jq '.installations[]? | "    \(.app_slug)"' 2>&1 | head -20
echo ""
echo "  MUST ALSO BE CHECKED BY EYE — the API cannot see all of it, and a"
echo "  refusal here is not the same as 'there is nothing there':"
echo "    Settings -> Collaborators   (expect exactly vedantgautam1 + vedant420420)"
echo "    Settings -> GitHub Apps     (anything that can write code or pull requests)"
echo "    Settings -> Branches        (old-style protection, separate from rulesets)"

# ---------------------------------------------------------------------- A4
rule "A4 — forge the required checks (the only main attack still isolatable)"
BASE=$(gh api "repos/$R/git/ref/heads/main" --jq '.object.sha')
BTREE=$(gh api "repos/$R/git/commits/$BASE" --jq '.tree.sha')
say "  main" "${BASE:0:7}  tree ${BTREE:0:7}"

BLOB=$(printf '{"content":"A4 attack probe: this commit skips CI so no real check runs.\\n","encoding":"utf-8"}' \
       | gh api -X POST "repos/$R/git/blobs" --input - --jq '.sha' 2>/dev/null)
say "  blob" "${BLOB:0:7}"
TREE=$(printf '{"base_tree":"%s","tree":[{"path":"scratch/a4-probe.md","mode":"100644","type":"blob","sha":"%s"}]}' "$BTREE" "$BLOB" \
       | gh api -X POST "repos/$R/git/trees" --input - --jq '.sha' 2>/dev/null)
say "  tree" "${TREE:0:7}"
CMSG='A4 attack: skip CI, then forge the required checks [skip ci]\n\nChronos-Role: builder\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>'
A4SHA=$(printf '{"message":"%s","tree":"%s","parents":["%s"]}' "$CMSG" "$TREE" "$BASE" \
        | gh api -X POST "repos/$R/git/commits" --input - --jq '.sha' 2>/dev/null)
say "  commit" "${A4SHA:0:7}"
if [ -z "${A4SHA:-}" ]; then
  echo "    could not create the commit; A4 not set up. Paste the output above anyway."
else
  gh api -X POST "repos/$R/git/refs" -f ref=refs/heads/doc/a4 -f sha="$A4SHA" --jq '"  branch \(.ref)"' 2>&1 | head -c 200 | sed 's/^/  /'
  echo ""
  PR4=$(gh api -X POST "repos/$R/pulls" -f title="A4 attack: forged status checks" -f head=doc/a4 -f base=main \
        -f body="Attack A4. The commit carries [skip ci] so no real check runs; five statuses named after the required checks are then posted by the automation. Expected: refused, because required checks must come from GitHub Actions." \
        --jq '.number' 2>/dev/null)
  say "  pull request" "#${PR4:-<see error above>}"

  echo "  posting five FORGED success statuses as the automation:"
  for CTX in "tests" "lint" "v1-oracle" "guards (from the base commit's copy)" "earlier-tests (the base's tests, this branch's package)"; do
    OUT=$(gh api -X POST "repos/$R/statuses/$A4SHA" -f state=success --field "context=$CTX" -f description="forged by A4" 2>&1 | head -c 140)
    printf '    %-52s %s\n' "$CTX" "$(printf '%s' "$OUT" | grep -q '"state"' && echo POSTED || printf '%s' "$OUT")"
  done
  echo ""
  echo "  what GitHub now reports on that commit:"
  gh api "repos/$R/commits/$A4SHA/status" --jq '"    combined=\(.state)  contexts=\([.statuses[].context])"' 2>&1 | head -4
  gh api "repos/$R/commits/$A4SHA/check-runs" --jq '"    \(.total_count) real check-run(s): \([.check_runs[].name])"' 2>&1 | head -4
  echo ""
  echo "  NEXT: the founder approves pull request #${PR4:-?} and does NOT merge it."
  echo "  Claude then attempts the merge from the cloud session."
fi

rule "DONE — paste all of the above back. Then revoke the token."
