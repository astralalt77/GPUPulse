#!/bin/bash
# GPUPulse push helper
# 
# 1. Go to https://github.com/settings/tokens
#    - Generate new token (classic)
#    - Check "repo" scope
#    - Copy the token (starts with ghp_ )
#
# 2. Edit ONLY the TOKEN line below. Replace with your real token.
#
# 3. Run: bash do-push.sh

TOKEN="ghp_PASTE_YOUR_TOKEN_HERE"

REMOTE="https://${TOKEN}@github.com/astralalt77/GPUPulse.git"

echo "Temporarily setting remote with token..."
git remote set-url origin "$REMOTE"

echo "Pushing..."
git push -u origin main

echo ""
echo "Done. Resetting remote to clean URL (no token)..."
git remote set-url origin https://github.com/astralalt77/GPUPulse.git

echo "Push complete! Your repo should now be up to date."
