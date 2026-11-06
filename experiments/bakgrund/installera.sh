#!/usr/bin/env bash
# Installerar bakgrunden som en systemd-tjänst under användaren. Kör från en utcheckning av main:
#   experiments/bakgrund/installera.sh
# Sedan uppdaterar loopen sig själv från origin/main mellan varven.
set -euo pipefail
K=$(cd "$(dirname "$0")" && pwd)
INST=$HOME/.local/share/knep-bakgrund
mkdir -p "$INST" "$HOME/.config/systemd/user" "$HOME/.bakgrund/logg"
for f in loop.sh settings.json uppdrag.md; do cp "$K/$f" "$INST/.$f.ny" && mv "$INST/.$f.ny" "$INST/$f"; done
chmod +x "$INST/loop.sh"
sed "s#@PATH@#$PATH#" "$K/knep-bakgrund.service" > "$HOME/.config/systemd/user/knep-bakgrund.service"
systemctl --user daemon-reload
systemctl --user enable knep-bakgrund.service
systemctl --user restart knep-bakgrund.service
if ! loginctl show-user "$USER" -p Linger | grep -q yes; then
  loginctl enable-linger "$USER" 2>/dev/null || echo "Tjänsten går bara medan du är inloggad. Kör: sudo loginctl enable-linger $USER"
fi
systemctl --user --no-pager status knep-bakgrund.service | head -n 5
