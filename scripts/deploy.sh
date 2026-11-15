#!/usr/bin/env bash
# Update the LIVE city to a tested release tag. Run from the live checkout:
#   cd ~/ai-mayor-live && ./scripts/deploy.sh v0.2.0
# 1. backs up the live city's data  2. switches the code to the tag  3. runs the tests
set -euo pipefail
TAG="${1:?usage: deploy.sh <tag>}"
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
if [ -d data/live ]; then
  tar -czf "backups/live-$STAMP-before-$TAG.tgz" data/live
  echo "backed up data/live -> backups/live-$STAMP-before-$TAG.tgz"
fi
git fetch --tags --quiet
git -c advice.detachedHead=false checkout "$TAG"
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest -q tests
echo "live city is now on $TAG"
