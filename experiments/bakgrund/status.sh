#!/usr/bin/env bash
# Läget för bakgrunden: tjänsten, pauser, grenen och PR:en, de senaste raderna i loggen och journalen.
S=${BAKGRUND_STATE:-$HOME/.bakgrund}
T=${BAKGRUND_DIR:-$HOME/bakgrund}
echo "== tjänsten"
systemctl --user is-active knep-bakgrund.service 2>/dev/null || true
[ -f "$S/STOPP" ] && echo "PAUSAD: $S/STOPP finns"
[ -f "$S/SPARR" ] && { echo "SPÄRRAD (pushas inte förrän $S/SPARR tas bort):"; cat "$S/SPARR"; }
pgrep -fa "claude -p" | cut -c1-80 | head -n 3
uptime
echo
if [ -d "$T" ]; then
  echo "== grenen"
  g=$(cat "$S/gren" 2>/dev/null); echo "${g:-ingen}"
  [ -n "$g" ] && (cd "$T" && gh pr view "$g" --json url,state -q '.state + " " + .url' 2>/dev/null)
  echo
fi
echo "== loggen"
tail -n 12 "$S/logg.txt" 2>/dev/null
echo
echo "== journalen, de senaste posterna"
[ -f "$T/experiments/bakgrund/JOURNAL.md" ] && grep -A3 -m5 '^### [0-9]' "$T/experiments/bakgrund/JOURNAL.md"
echo
df -h /data | tail -n 1
