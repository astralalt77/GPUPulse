#!/bin/bash
# Reliable push for this project.
# Only edit the TOKEN line.

TOKEN="ghp_PASTE_YOUR_TOKEN_HERE"

REMOTE="https://${TOKEN}@github.com/astralalt77/GPUPulse.git"

echo "Setting pull config..."
git config pull.rebase false

echo "Temp remote..."
git remote set-url origin "$REMOTE"

echo "Fetching..."
git fetch origin

echo "Merging remote initial commit (preferring local files)..."
git merge origin/main --allow-unrelated-histories -X ours -m "Merge remote initial commit"

echo "Pushing..."
git push -u origin main

echo "Resetting remote to clean..."
git remote set-url origin https://github.com/astralalt77/GPUPulse.git

echo "Success! Check https://github.com/astralalt77/GPUPulse"
