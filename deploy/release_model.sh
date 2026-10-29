#!/usr/bin/env bash
# Släpp en ny version av en tränad modell som tillgång i GitHub Releases och lås den i
# models/models.json. Låsningen checkas sedan in på en gren och går via pull request.
#
#   deploy/release_model.sh extremes extremes-v2 models/extremes.pkl models/release-notes/extremes-v2.md
#   deploy/release_model.sh bias bias-v1 cache/bias/kandidat.npz models/release-notes/bias-v1.md
#
# Kräver gh inloggad mot repot (gh auth login, eller GH_TOKEN med Contents: read/write).
set -euo pipefail
name=$1 tag=$2 file=$3 notes=$4
target=models/$(basename "$file")
case $name in extremes) target=models/extremes.pkl ;; bias) target=models/bias.npz ;; esac
[ "$(realpath "$file")" = "$(realpath -m "$target")" ] || cp "$file" "$target"
gh release create "$tag" "$target" --title "$tag" --notes-file "$notes"
uv run knep-models pin "$name" "$tag" "$target"
echo "Skapa en gren, checka in models/models.json och $notes, och öppna en pull request."
