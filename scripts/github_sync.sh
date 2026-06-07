#!/bin/bash
set -euo pipefail

REMOTE_URL="https://github.com/NDGopher/UnifiedBetting.git"
BRANCH="main"
LOG_PREFIX="[github-sync]"

if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "$LOG_PREFIX ERROR: GITHUB_TOKEN secret is not set. Cannot sync to GitHub." >&2
    exit 1
fi

AUTHED_URL="https://NDGopher:${GITHUB_TOKEN}@github.com/NDGopher/UnifiedBetting.git"

cleanup() {
    git remote set-url origin "$REMOTE_URL" 2>/dev/null || true
}
trap cleanup EXIT

git remote set-url origin "$AUTHED_URL"

if ! git fetch origin "$BRANCH" --quiet 2>&1; then
    echo "$LOG_PREFIX WARN: Could not fetch from origin. Will force-push current HEAD."
    git push --force origin "$BRANCH" --quiet
    echo "$LOG_PREFIX Force-push successful (fetch failed — pushed without comparison)."
    exit 0
fi

LOCAL_HEAD=$(git rev-parse HEAD)
ORIGIN_HEAD=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "")

if [ "$LOCAL_HEAD" = "$ORIGIN_HEAD" ]; then
    echo "$LOG_PREFIX Already up to date with origin/$BRANCH. Nothing to push."
    exit 0
fi

AHEAD=$(git rev-list "origin/$BRANCH..HEAD" --count 2>/dev/null || echo "?")
BEHIND=$(git rev-list "HEAD..origin/$BRANCH" --count 2>/dev/null || echo "0")

if [ "$BEHIND" != "0" ] && [ "$BEHIND" != "?" ]; then
    echo "$LOG_PREFIX Histories have diverged ($AHEAD ahead, $BEHIND behind). Force-pushing Replit as canonical source."
    git push --force origin "$BRANCH" --quiet
    echo "$LOG_PREFIX Force-push successful. GitHub updated to Replit HEAD."
else
    echo "$LOG_PREFIX Local is $AHEAD commit(s) ahead of origin/$BRANCH. Pushing..."
    git push origin "$BRANCH" --quiet
    echo "$LOG_PREFIX Push successful. GitHub is now up to date."
fi
