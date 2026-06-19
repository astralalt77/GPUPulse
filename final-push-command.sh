#!/bin/bash
# This is the ready command to add remote and push.
# Edit the URL below with your actual GitHub repo URL.
# Then run: bash final-push-command.sh

# === CHANGE THIS LINE TO YOUR REPO URL ===
REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/gpupulse.git"

echo "Adding remote and pushing to: $REPO_URL"
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git push -u origin main
