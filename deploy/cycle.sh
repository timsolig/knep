#!/usr/bin/env bash
# En prognoscykel ur den här utcheckningen: räkna, och publicera om det fanns en ny radarbild.
# Startas av drift.sh med driftens katalog som argument; ändras via main som all annan kod.
#
# Avslutar med 0 när cykeln gick bra (också när det inte fanns någon ny bild) och med
# knep:s kod annars, så att drift.sh kan gå tillbaka till förra versionen.
set -uo pipefail
root=$1
cd "$(dirname "$0")/.."

timeout 4m knep --out "$root/out/data" --cache "$root/cache" --fallback
rc=$?
case $rc in
  0)  timeout 2m deploy/publish.sh "$root/out/data" || echo "publiceringen misslyckades (kod $?)" >&2 ;;
  75) rc=0 ;;  # ingen ny radarbild, inget att publicera
  *)  echo "cykeln avbröts med kod $rc" >&2 ;;
esac
exit "$rc"
