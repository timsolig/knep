# Prov av nattkörningens behörigheter 2026-11-04

1. `uv run python -c "import knep ..."`: gick igenom, utskrift `python ok 3.12.16`.
2. `df -h /data`: gick igenom, /dev/mmcblk0p2 29G, 24G använt, 3,5G ledigt (88 %).
3. `git push`: nekades av behörigheterna ("Permission to use Bash with command git push has been denied"). Inget annat försök gjordes.
4. Skriva `deploy/prov.txt`: nekades ("File is in a directory that is denied by your permission settings"). Filen skapades inte.
5. Den här filen skrevs till `experiments/natt/rapporter/2026-11-04/prov.md`.
