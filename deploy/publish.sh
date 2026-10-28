#!/usr/bin/env bash
# Publicera prognosrutorna: tvinga grenen "data" till en enda commit med senaste
# rutorna och be Pages-workflowet bygga om sidan. Historiken växer därför inte.
#
# Kräver GITHUB_REPO (ägare/repo) och GITHUB_TOKEN, en fine-grained token som
# bara gäller det här repot med Contents: read/write och Actions: read/write.
set -euo pipefail
: "${GITHUB_REPO:?}" "${GITHUB_TOKEN:?}"
src=$(realpath "$1")

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp -r "$src"/. "$tmp"
cd "$tmp"

git init -q -b data
git add -A
git -c user.name=nowcast -c user.email=nowcast@localhost commit -q -m "prognos $(date -u +%FT%H:%MZ)"
git push -q -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" data

curl -fsS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/pages.yml/dispatches" \
  -d '{"ref":"main"}'
