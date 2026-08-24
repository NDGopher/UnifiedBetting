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

# Pull-first auto-sync: GitHub wins when ahead; never upload Qubic over sbsports.
echo "[post-merge] Syncing with GitHub (pull-first, stale-guard)..."
python scripts/github_autosync.py
