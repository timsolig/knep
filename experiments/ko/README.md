# Kön

Experiment som körs utan Claude, ett i taget, dygnet runt med låg prioritet, och en genomgång med Opus en gång i veckan som väljer vad som är värt att räkna. Ersätter bakgrunden i `experiments/bakgrund/`, som körde en Claude-session per uppgift och använde för mycket av användningen.

- `ko.py` körskriptet: tar nästa experiment i `ko/`, kör det, sätter domen mekaniskt ur domarens egen regel och skriver `/data/ko/resultat/<id>.json` och `/data/ko/SAMMANFATTNING.md`. Hämtar `main` mellan experimenten.
- `ko/` experimenten, en JSON-fil per experiment (formatet i docstringen i `ko.py`).
- `SPAR.md` spåren och reglerna för att ompröva vägar (budget per spår, mättade spår stängs, en tredjedel till andra spår, omprövning från grunden var fjärde vecka).
- `vecka.md` instruktionen för veckans genomgång.
- `knep-ko.service` tjänsten (systemd för användaren), som körs i arbetskopian `~/ko` av `main`.

Installera: `sed "s#@PATH@#$PATH#" experiments/ko/knep-ko.service > ~/.config/systemd/user/knep-ko.service && systemctl --user daemon-reload && systemctl --user enable --now knep-ko`. Stoppa: `systemctl --user stop knep-ko`. Följ: `journalctl --user -u knep-ko -f` och `/data/ko/SAMMANFATTNING.md`.
