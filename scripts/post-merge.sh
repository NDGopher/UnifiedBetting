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
