#!/bin/bash
# GPUPulse - Easy GitHub push helper
#
# 1. First, go to https://github.com/new
#    - Create a new repo called "gpupulse" (or whatever name you want)
#    - Make it Public
#    - DO NOT initialize it with README, .gitignore, or license
#
# 2. Edit this file and put your GitHub details below.
#
# 3. Then run: bash setup-remote.sh

# === EDIT THESE TWO LINES ===
GITHUB_USER="YOUR_GITHUB_USERNAME_HERE"     # <--- CHANGE THIS
REPO_NAME="gpupulse"                        # <--- change if you used a different repo name

# The full remote URL (HTTPS)
REMOTE_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo "========================================"
echo "  GPUPulse GitHub Setup"
echo "========================================"
echo
echo "Your remote will be: $REMOTE_URL"
echo
echo "If this looks correct, press Enter to continue."
echo "Otherwise, edit this file (nano setup-remote.sh) and change the values."
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Add the remote (safe even if it already exists)
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_URL"

echo
echo "Remote added."
echo
echo "Now run this command to push:"
echo
echo "    git push -u origin main"
echo
echo "If it asks for a password, use a Personal Access Token (not your normal password)."
echo "Create one at: https://github.com/settings/tokens"
echo
echo "After first push, you can just run 'git push' in the future."
