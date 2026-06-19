#!/bin/bash
# Reliable push script for divergent histories.
# Edit only the TOKEN line.

TOKEN="ghp_PASTE_YOUR_TOKEN_HERE"

REMOTE="https://${TOKEN}@github.com/astralalt77/GPUPulse.git"

echo "Configuring pull behavior..."
git config pull.rebase false

echo "Setting temp remote..."
git remote set-url origin "$REMOTE"

echo "Fetching..."
git fetch origin

echo "Merging remote (allowing unrelated histories)..."
git merge origin/main --allow-unrelated-histories -m "Merge remote initial commit"

echo "Pushing..."
git push -u origin main

echo "Resetting remote..."
git remote set-url origin https://github.com/astralalt77/GPUPulse.git

echo "Done."
