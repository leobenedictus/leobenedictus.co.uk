#!/bin/bash
# Pull the site, rebuild the Writing page and home page latest post from the
# Substack feed, and push if anything changed. Run by launchd daily at 06:20
# from a separate clone (~/leobenedictus.co.uk-updater), never the copy Leo
# edits, so it can't commit half-finished work.

set -euo pipefail
cd "$(dirname "$0")/.."
echo "── $(date '+%Y-%m-%d %H:%M')"

# Apple's Python doesn't always find the system certificates on its own.
export SSL_CERT_FILE=/etc/ssl/cert.pem

git pull --ff-only --quiet
/usr/bin/python3 scripts/build_writing.py

FILES="writing.html index.html data/substack-posts.json"
if [ -z "$(git status --porcelain -- $FILES)" ]; then
    exit 0
fi
git add $FILES
git commit --quiet -m "Update Writing page from Substack feed"
git push --quiet
echo "Pushed."
