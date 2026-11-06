#!/usr/bin/env bash
# Läget för bakgrundskörningen: vad som pågår, rapporterna och commitarna. Går att köra när som helst.
NATT=${NATT_DIR:-$HOME/natt}
[ -d "$NATT" ] || { echo "ingen bakgrundskörning i $NATT"; exit 0; }
cd "$NATT" || exit 1
echo "== körningen"
if pgrep -f experiments/natt/kor.sh >/dev/null; then echo "kor.sh kör (pid $(pgrep -f experiments/natt/kor.sh | head -1))"; else echo "kor.sh kör inte"; fi
pgrep -fa "claude -p" | cut -c1-80 | head -3
uptime
echo
echo "== senaste raderna i natt.log"
tail -n 12 natt.log 2>/dev/null
echo
echo "== rapporter"
for f in experiments/natt/rapporter/*/[0-9]*.md experiments/natt/rapporter/*/sammanfattning.md; do
  [ -f "$f" ] && printf '%-70s %s\n' "$f" "$(grep -m1 -i '^Status:' "$f")"
done
echo
echo "== commits på $(git branch --show-current) som inte är i main"
git log --oneline main..HEAD | head -20
echo
df -h /data | tail -1
