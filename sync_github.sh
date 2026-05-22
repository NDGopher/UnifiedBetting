#!/bin/bash
# Push all Replit commits to GitHub (force push to overwrite diverged history)
# Run this from the Replit shell whenever you want to sync: bash sync_github.sh

TOKEN="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"
REMOTE="https://${TOKEN}@github.com/NDGopher/UnifiedBetting.git"

echo "[sync] Pushing to GitHub..."
git push --force "$REMOTE" HEAD:main 2>&1

if [ $? -eq 0 ]; then
    echo "[sync] Done — GitHub is now up to date with Replit."
else
    echo "[sync] Push failed. Check token validity or network."
fi
