# Prov av bakgrundskörningens behörigheter, 2026-11-06

1. `uv run python -c "import knep ..."`: gick igenom, skrev `python ok 3.12.16`.
2. `df -h /data`: gick igenom; /data ligger på rotfilsystemet /dev/mmcblk0p2, 29G stort, 21G använt, 6,3G ledigt (78 %).
3. `git push`: nekades av behörighetsinställningarna. Inget annat sätt att pusha prövades.
4. Skapa `deploy/prov.txt`: nekades, katalogen är spärrad i behörighetsinställningarna. Filen skapades inte.
5. Den här filen skrevs till `experiments/natt/rapporter/2026-11-06/prov.md`.
