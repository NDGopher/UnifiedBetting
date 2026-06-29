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

# Sync changed source files to GitHub
echo "[post-merge] Syncing to GitHub..."
python scripts/github_autosync.py
