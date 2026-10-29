#!/usr/bin/env bash
# Driften: en prognoscykel direkt vid start och sedan var femte minut, 2 min efter mättiden.
# SMHI lägger normalt upp bilden 1,5 till 3 min efter mättiden, och knep väntar upp till
# 2 min på den. Varje cykel är en egen process, så minnet lämnas tillbaka mellan körningarna.
set -uo pipefail
cd "$(dirname "$0")/.."

first=1
while true; do
  if (( ! first )); then
    now=$(date +%s)
    next=$(( now - now % 300 + 120 ))
    (( next > now )) || next=$(( next + 300 ))
    sleep $(( next - now ))
  fi
  first=0

  timeout 4m knep --out out/data --cache cache --fallback "$@"
  rc=$?
  case $rc in
    0)  timeout 2m deploy/publish.sh out/data || echo "publiceringen misslyckades (kod $?)" >&2 ;;
    75) ;;  # ingen ny radarbild, inget att publicera
    *)  echo "cykeln avbröts med kod $rc" >&2 ;;
  esac
done
