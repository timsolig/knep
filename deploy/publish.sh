#!/usr/bin/env bash
# Publicera prognosrutorna: tvinga grenen "data" till en enda commit med senaste
# rutorna och be Pages-workflowet bygga om sidan. Historiken växer därför inte.
#
# Kräver GITHUB_TOKEN, en fine-grained token som bara gäller repot med Contents och
# Actions satta till read and write. Repot tas ur models/models.json om GITHUB_REPO saknas.
set -euo pipefail
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "GITHUB_TOKEN saknas, prognosen publiceras inte" >&2
  exit 0
fi
GITHUB_REPO=${GITHUB_REPO:-$(python -c 'import json; print(json.load(open("models/models.json"))["repo"])')}
src=$(realpath "$1")

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp -r "$src"/. "$tmp"
cd "$tmp"

git init -q -b data
git add -A
git -c user.name=knep -c user.email=knep@localhost commit -q -m "prognos $(date -u +%FT%H:%MZ)"
git push -q -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" data

curl -fsS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/pages.yml/dispatches" \
  -d '{"ref":"main"}'
echo "publicerade prognosen till ${GITHUB_REPO}" >&2
