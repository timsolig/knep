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

Körningen gick 23:36 till cirka 00:05 (en process, ungefär 30 s per dag), utan fel. Logg: `/data/bortfall/fall_bygg.log`. `fall.py kontroll`:

| | Träning | Validering |
|---|---|---|
| Fall | 223 (28 dagar; 2023-01-04 fick 7) | 128 (16 dagar) |
| 30 / 60 / 120 / 180 / 360 min | 47 / 44 / 42 / 46 / 44 | 26 / 28 / 28 / 23 / 23 |
| Radarer släckta 1 / 2 / 3 / 4 / alla 12 | 39 / 62 / 78 / 29 / 15 | 19 / 30 / 43 / 25 / 11 |
| Hålets storlek, median (min till max) | 5730 px (390 till 77 695) | 4463 px (349 till 77 759) |
| Våt andel av hålet vid start, median | 0,14 | 0,18 |
| MEPS för hela fönstret | 223 | 112 (de 16 som saknas är 2019) |
| Mätare p7 och p14 | alla | alla |
| Storlek | 290 MB, störst 5,6 MB | 168 MB, störst 7,6 MB |

Hålen i ett typiskt dygn (täckningen från en bild, `fall.py hal`): bara `sehem` (42 000 km², mest Östersjön) och `sella` (1 560 km²) ger hål ensamma; resten av Sverige ses av en annan radar inom 240 km. 15 olika hål återstår efter rensningen, från 1 560 km² (`sella`) till 292 000 km² (alla svenska). Antalet hål per dag varierar (9 till 19) eftersom täckningen räknas per dag och SMHI:s komposit har haft olika täckning genom åren; därför förekommer till exempel `sekrn` ensam vissa dagar.

Data i natt: fallen 438 MB och p14 1,8 MB. Med rapport 1 är nattens nya data ungefär 1,4 GB av 2 GB; ledigt på `/data` är 3,6 GB.

## Vad som fungerade och inte

- Fungerade: hålen, urvalet och lagringen; provkörningen visade rätt MEPS-timmar (till exempel timmen 09 till 10 ur 06Z-körningen, ledtid 3) och mätare i hålet. p14 hämtades klart (185 stationer, 663 864 värden i `/data/bortfall/matare/p14.npz`), så rapport 1:s rest är gjord.
- Begränsningar att känna till:
  - Hålet följer uppgiftens definition med alla radarer i `RADARS` och 240 km. Det är försiktigt: med det täta nätet blir de flesta hål där flera radarer släckts, och de enskilda svenska radarerna ger sällan hål. Ett verkligt bortfall i SMHI:s komposit kan bli större om grannländernas radarer inte bidrar fullt ut där.
  - Fall samma dag delar ofta regn (8 fall av 15 möjliga hål per dag). Domaren ska göra bootstrap över dagar.
  - I fältet `radar` finns hela utsnittet; i hålet under bortfallet är det facit och får inte ges till systemen. Domaren ska maskera det (`hal` och bilderna från index 12).
  - Ingen OPERA och inga volymer (se ovan).
- Inte tillåtet i natt: omdirigering och heredoc i skalet, därför `--logg` även i `fall.py`.

`uv run pytest`: 68 passerade.

## Filer

- `experiments/bortfall/fall.py` (nytt)
- `tests/test_bortfall_fall.py` (nytt)
- `experiments/natt/rapporter/2026-11-03/2-bortfallsfall.md`

Inga ändringar i `src/knep/`.

## Nästa steg

Uppgift 3 (domaren) läser `/data/bortfall/fall/validering/index.json` och fallen; fälten står ovan. Bilden med index `uppvarmning_bilder` (12) är bortfallets första bild och ålder 0; bild `uppvarmning_bilder + k` har åldern 5k min. Baslinjerna (hål, `fill_gaps`, utjämnad) kan köras direkt på utsnittet, med rörelsen skattad på uppvärmningen. För prognosen efteråt finns radarn 180 min efter slutet i `/data/radar/`.

```sh
uv run python experiments/bortfall/fall.py hal          # hålen
uv run python experiments/bortfall/fall.py kontroll     # vad som finns
uv run python experiments/bortfall/fall.py bygg --del traning --om --logg /data/bortfall/fall_bygg.log   # bygger om (samma fall)
```

Status: klar
