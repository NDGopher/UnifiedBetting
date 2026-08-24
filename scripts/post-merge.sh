#!/bin/bash
set -e

# Install backend Python dependencies
cd backend
pip install -r requirements.txt -q
cd ..

# Install frontend Node dependencies
cd frontend
npm install --legacy-peer-deps --silent
cd ..

# Do not push to GitHub from post-merge. The old auto-sync daemon kept
# uploading a stale Qubic checkout onto main. scripts/github_autosync.py
# stays in the repo for manual use only.
echo "[post-merge] Skipping GitHub auto-sync (disabled)."
