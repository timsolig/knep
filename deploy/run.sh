#!/usr/bin/env bash
# En prognoscykel: räkna och publicera om det finns en ny radarbild.
set -uo pipefail
cd "$(dirname "$0")/.."

.venv/bin/nowcast --out out/data --cache cache --fallback "$@"
rc=$?
case $rc in
  0)  exec deploy/publish.sh out/data ;;
  75) exit 0 ;;  # ingen ny radarbild, inget att publicera
  *)  exit "$rc" ;;
esac
