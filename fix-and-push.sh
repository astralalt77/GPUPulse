#!/bin/bash
# Fix the "fetch first" rejection and push.
#
# The remote had an initial commit (basic .gitignore/LICENSE/README).
# We need to pull it first with --allow-unrelated-histories.
#
# 1. Create a GitHub Personal Access Token at:
#    https://github.com/settings/tokens
#    (Classic token, check the "repo" box)
#
# 2. Edit ONLY the TOKEN line below with your ghp_... token.
#
# 3. Run: bash fix-and-push.sh

TOKEN="ghp_PASTE_YOUR_TOKEN_HERE"

REMOTE="https://${TOKEN}@github.com/astralalt77/GPUPulse.git"

echo "Setting temporary remote with token..."
git remote set-url origin "$REMOTE"

echo "Pulling remote changes (merging histories)..."
git pull origin main --allow-unrelated-histories

echo "Pushing..."
git push -u origin main

echo ""
echo "Resetting remote to clean URL..."
git remote set-url origin https://github.com/astralalt77/GPUPulse.git

echo "Done! Repo should now be up to date on GitHub."
