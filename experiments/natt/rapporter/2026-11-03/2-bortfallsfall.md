# 2 Bortfallsfall: simulerade bortfall ur riktiga timmar

## Vad jag gjorde

1. Läste rapport 1. Den lämnade kvartssummorna från mätarna (p14) ohämtade; jag startade `hamta.py matare` i bakgrunden först av allt (p7 fanns och hoppades över).
2. Skrev `experiments/bortfall/fall.py` (hål per radarkombination, urval av starttider, lagring) och `tests/test_bortfall_fall.py` (12 tester på syntetiska data).
3. Provkörde på två träningsdagar (3 fall per dag) och en valideringsdag (8 fall), kontrollerade innehållet och körde sedan alla fall i bakgrunden, efter att p14 blivit klar.

## Hur ett fall görs

- **Kombinationer.** Varje svensk radar ensam, grannar två (högst 300 km isär), tre (330 km) och fyra (360 km) i taget, och alla svenska (SMHI:s komposit nere), 54 kombinationer.
- **Hålet.** Pixlar som SMHI:s komposit har data i minst halva dygnet, inom 240 km från någon släckt radar och längre än 240 km från alla andra radarer i `composite.RADARS` (även de norska, finska och danska). Kombinationer med hål under 300 pixlar (1200 km²) tas bort, och nästan samma hål (IoU över 0,9) räknas en gång, med färst radarer.
- **Start.** Provas var 15:e minut genom dygnet. Det ska regna i hålet vid starten: minst 3 % och minst 100 pixlar med 0,5 mm/h. Hela fönstret från 60 min före starten till 180 min efter slutet ska finnas i `/data/radar/`; fall som skulle behöva en av de saknade bilderna (rapport 1) väljs alltså aldrig.
- **Längd.** 30, 60, 120, 180 och 360 min i tur och ordning, så att alla åldersklasser i domaren får fall.
- **Urval.** Högst 8 fall per dag, med olika kombinationer, slumpat med ett frö ur dag och del (sha256), alltså samma fall vid omkörning. Fall samma dag delar ofta regn; domaren ska därför göra bootstrap över dagar.
- **Dagar.** Träning: de 28 i `traning.json` (med kontrollen att ingen ligger inom två dygn från `dagar.json`). Validering: de 16 i delen `validering`. `days_for("test")` ger fel; testdelen läses inte.

## Vad som sparas

`/data/bortfall/fall/traning/` och `/data/bortfall/fall/validering/`, en komprimerad npz per fall (`<start>_<längd>_<radarer>.npz`) och `index.json` med alla fallens metadata:

| Fält | Innehåll |
|---|---|
| `meta` | json: dag, del, start, slut, längd, radarer, första bild, antal bilder (de första 12 är uppvärmning), utsnitt i det stora rutnätet, rutnätets transform, hålets storlek, våt andel vid start, MEPS-timmar och körningar, vilka mätare som finns |
| `radar` | uint8 (T, h, w), SMHI:s koder (dBZ = 0,4 v − 30, 0 inget eko, 255 ingen data) var 5:e min från start − 60 min till slutet, i ett utsnitt runt hålet med 150 km marginal. Facit i hålet och riktig radar utanför |
| `hal` | bool (h, w) |
| `avstand` | uint16 (h, w), km till närmaste radar som fungerar |
| `meps` | float16 (timmar, h, w), mm/h på radarns rutnät. Timmen ur den senaste körningen som fanns när timmen började (`nwp.available` med 6 h, 2,5 h fördröjning), som i `experiments/sverige`. Tomt för 2019 (äldre rutnät) |
| `matare_p7_*`, `matare_p14_*` | mätarna i utsnittet och fönstret: station, lat, lon, rad, kol, tid (periodens slut), mm, i_hal |

Radarn utanför utsnittet och efter bortfallet (för prognosen efteråt, 180 min finns garanterat) läses ur `/data/radar/` med tiderna i `meta`.

Källor som inte sparas: OPERA-kompositen innehåller de släckta radarerna och vore fusk (rapport 1). Enskilda volymer finns i arkivet bara från 2025, de svenska bara som `SCAN`, och de skulle ta mycket av datataket; grannradarerna når per definition bara hålets kant. Det är en begränsning: systemen i natt kan inte använda volymer.

## Siffror

(fylls i när körningen är klar)

## Filer

- `experiments/bortfall/fall.py` (nytt)
- `tests/test_bortfall_fall.py` (nytt)
- `experiments/natt/rapporter/2026-11-03/2-bortfallsfall.md`

Inga ändringar i `src/knep/`.

## Nästa steg

Uppgift 3 (domaren) läser `index.json` och fallen; se ovan för fälten.

Status: delvis
