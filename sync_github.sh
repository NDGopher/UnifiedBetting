#!/bin/bash
# Sync Replit <-> GitHub.
# Run from the Replit shell: bash sync_github.sh
# This PULLS GitHub first, then pushes — so local commits are never overwritten.

TOKEN="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"
REMOTE="https://${TOKEN}@github.com/NDGopher/UnifiedBetting.git"

echo "[sync] Pulling from GitHub first..."
git pull --rebase "$REMOTE" main

if [ $? -ne 0 ]; then
    echo "[sync] Pull/rebase failed — aborting. Run 'git rebase --abort' then fix conflicts manually."
    exit 1
fi

echo "[sync] Pushing to GitHub..."
git push "$REMOTE" HEAD:main

if [ $? -ne 0 ]; then
    echo "[sync] Normal push failed, trying force push..."
    git push --force "$REMOTE" HEAD:main
fi

echo "[sync] Done."
