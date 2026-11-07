# Uppgift 8: sammanfattningen av uppgift 6 och 7

## Vad jag gjorde

- Läste rapporterna `6-lovart.md` och `7-inflode.md` (båda `Status: delvis`) och kvällens sammanfattning `2026-11-06/sammanfattning.md` med `5-sammanfattning.md`, och `2026-11-04/6-sammanfattning.md` för prognosens testkommandon.
- Skrev [sammanfattning.md](sammanfattning.md): vad uppgift 6 och 7 kom fram till med domarens tabeller och intervall, rekommendationen för drift (oförändrad), körtiderna, det som återstår och kommandona för testdelen. Den hänvisar till `2026-11-06/sammanfattning.md` för kvällens del.
- Kontrollerade att kommandona stämmer med koden: `lovart.py kor` läser dagarna med `domare.days(a.del_)` och har en assertion på rad 172 och `choices` på rad 278 som bara tillåter validering och träning; `domare.py` har `kor`/`tabell`, `system`, `--mot`, `--bit` och `--del`; `kedja.py` har `--part` och `--shard`. Testdelen är spärrad i båda domarna, och upplåsningen beskrivs som en ändring som bara görs när användaren beslutar det.
- Uppgift 6 och 7 lämnade inget som den här uppgiften behövde göra klart: deras återstående steg (13 träningsdagar, 9 valideringsdygn, domarens summakvot) är längre körningar eller beslut och står under "Det som återstår" i sammanfattningen.

## Kontrollen

- `uv run pytest`: 168 godkända på 2 min 20 s.
- Disken: `/data/analys` 785 MB, `/data` 5,1 GB ledigt. Ingen ny data i den här uppgiften.
- Committat på grenen `natt/2026-11-06`. Inget pushades, ingen PR öppnades. Loggfilen `logg/8-sammanfattning2.txt` skrivs av körskriptet och committas av det.

## Ändrade filer

- `experiments/natt/rapporter/2026-11-07/sammanfattning.md` (ny)
- `experiments/natt/rapporter/2026-11-07/8-sammanfattning2.md` (den här rapporten)

## Nästa steg

Användaren beslutar om testdelen ska köras (baslinjerna A0, A1 och kedjan, eventuellt A1L1 mot A1) och om domarens summakvot ska ändras innan dess.

Status: klar
