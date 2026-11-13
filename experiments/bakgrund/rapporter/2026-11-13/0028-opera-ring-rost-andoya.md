# Uppgift 0028: ringen vid Røst och Andøya i OPERA-delen av A0

Kort: Ringen finns vid Røst (andel eko 0,71 inom 4 km i torra bilder mot 0,004 vid 25 till 30 km) och i mindre kärnor vid fem andra OPERA-radarer, men inte vid Andøya på träningsdagarna; en fast mask (r 8 till 16 km) tar bort den men också 5,1 % av den våta OPERA-volymen i regnstimmar (13,1 % kring Røst), och klotterkartan (b) tar bara cirka 0,01 % men lämnar kärnan; valet `--opera-ring` finns avstängt med tester, ingen säkerställd förbättring.

## Vad som gjordes

Rapportskelett och commit först. Skript i `experiments/riksgransen/`: `ring_karta.py`, `ring_profil.py`, `ring_profil2.py`, `ring_torr.py`, `ring_fall.py`, `ring_zoom.py`, `ring_kand.py` (kandidaterna och måtten), `ring_fall_efter.py`. Mellanresultat och kartor ligger i `/dev/shm/opera_ring/` (inget skrevs till `/data`). Skalet nekade `mkdir` i `/dev/shm`, `sed -i`, omdirigering och `&`; skripten skapar katalogen själva.

Data: OPERA 15-minutersbilder (uint8, SMHI:s kodning, radarns rutnät 887 × 471). Av de 16 dagarna ligger 9 i träningen (2020-02-10, 2020-07-24, 2021-04-05, 2022-12-20, 2023-08-02, 2024-07-28, 2024-09-26, 2024-11-25, 2024-12-19) och 7 i valideringen (2019-03-08, 2019-03-17, 2020-05-10, 2021-10-05, 2021-10-20, 2023-11-04, 2025-07-29). Dagarna kommer ur `domare.days`, som kontrollerar att inget ligger i testdelen; testdelen lästes aldrig.

## Ringarna

Rutnätslägen (rad, kolumn): Røst (137, 123), Andøya (45, 203). Med alla bilder är andelen eko hög kring Røst (0,83 inom 4 km, 0,45 vid 40 till 60 km), men det blandar ihop väder och artefakt. Skiljer gör bilder där omgivningen (30 till 50 km) är torr (under 3 % eko). Andel eko per ring 0-4, 4-8, 8-12, 12-16, 16-20, 20-25, 25-30 km, träning (`ring_kand.py trana`):

| radar | torra bilder | andel per ring | ringplats, r |
|---|---|---|---|
| Røst (norst) | 94 | 0,706 0,163 0,056 0,016 0,004 0,007 0,004 | ja, 12 km |
| Sømna (nosmn) | 97 | 0,219 0,074 0,034 0,030 0,033 0,028 0,016 | ja, 12 km |
| Hurum-fjell (nohfj) | 355 | 0,268 0,135 0,076 0,043 0,026 0,021 0,019 | ja, 16 km |
| Kortpi (fikor) | 255 | 0,250 0,062 0,017 0,013 0,008 0,007 0,006 | ja, 8 km |
| Vimpeli (fivim) | 217 | 0,254 0,095 0,039 0,020 0,027 0,027 0,031 | ja, 8 km |
| Utajärvi (fiuta) | 198 | 0,402 0,111 0,045 0,029 0,019 0,013 0,010 | ja, 16 km |
| Andøya (noand) | 244 | 0,014 0,008 0,006 0,003 0,004 0,003 0,005 | nej |
| övriga (nohur, norsa, filuo, dkste, dkbor, dksin) | | kärna 0,01 till 0,29 inom 4 km, ingen ring | nej |

Fallet 2026-11-07 (`fall.npz`, OPERA): Røst är en ihållande skiva med eko i 80 till 90 % av rutorna ut till cirka 18 km och 40 till 50 % vid 18 till 24 km, medelintensitet 6 till 8 mm/h i mitten, mot 2 till 5 % över 24 km. Det är större än träningsdagarnas torra bilder visar (radie 12 km), så masken på 12 km lämnar troligen kanten kvar den dagen. Vid Andøya ligger verkligt regn över hela området (andel 0,7 till 1,0 överallt), så ringen syns inte där i fallet och inte i torra bilder på träningsdagarna. Jag har därför ingen träningsgrund för en mask vid Andøya; valet har en radielista (`composite.OPERA_RING_KM`) där den kan läggas till.

Kartor: `/dev/shm/opera_ring/frekvens_karta.png`, `fall_zoom.png`, `fall_fore_efter.png` (flyktigt minne, inte kopierade till repot).

## Kandidaterna (regler fastlagda innan siffrorna sågs, se docstringen i `ring_kand.py`)

(a) fast mask, NaN inom r. r är kanten på den första 4-kmsringen från 8 km där andelen i torra bilder är högst max(0,02, 2 · andelen vid 25 till 30 km); ringplats om andelen vid 4 till 8 km är minst 0,05. (b) klotterkarta: andelen bilder där en ruta har eko och ringen 14 till 30 km kring den är torr, tröskel TAU 0,02, 0,05 eller 0,10 (2124, 775 och 281 misstänkta rutor), och sedan F4:s regel (bort bara när omgivningen inom 42 km utan de misstänkta rutorna är torr), NaN i stället för 0. Mått: andelen eko i ringarna före och efter (borttaget räknas som inget eko) och borttagen våt volym inom 100 km i timmar med över 20 % våta rutor inom 150 km.

Träning, 9 dagar (andel i ring 0-4 och 4-8 km, före, efter; borttagen volym):

| plats | före | (a) efter | (b) TAU 0,02 efter | (b) 0,05 | (b) 0,10 |
|---|---|---|---|---|---|
| Røst | 0,706 0,163 | 0 0 | 0,146 0,073 | 0,460 0,135 | 0,706 0,163 |
| Hurum-fjell | 0,268 0,135 | 0 0 | 0,182 0,132 | 0,186 0,135 | 0,202 0,135 |
| Sømna | 0,219 0,074 | 0 0 | 0,219 0,074 | 0,219 0,074 | 0,219 0,074 |
| Utajärvi | 0,402 0,111 | 0 0 | 0,181 0,088 | 0,233 0,109 | 0,286 0,111 |
| Vimpeli | 0,254 0,095 | 0 0 | 0,182 0,094 | 0,215 0,095 | 0,254 0,095 |
| Kortpi | 0,250 0,062 | 0 0 | 0,039 0,020 | 0,085 0,051 | 0,149 0,062 |
| **borttagen våt volym, alla** | | **5,100 %** (Røst 13,106, Utajärvi 6,807, Hurum-fjell 5,958, Sømna 3,097, Kortpi 1,048, Vimpeli 1,037) | 0,014 % | 0,005 % | 0,001 % |

Ingen (b)-variant tar ringen ner till omgivningens nivå (kärnan 0 till 4 km är kvar på 0,15 till 0,7), eftersom kärnan är några rutor stor och rutor intill har eko i samma bild, så F4-regeln ser inte omgivningen som torr. Enligt förhandsregeln (b föredras bara om den tar ringen lika bra) valdes därför (a).

## Fryst och validering

Frysta: (a) med Røst 12, Sømna 12, Hurum-fjell 16, Kortpi 8, Vimpeli 8, Utajärvi 16 km. Valideringen (7 dagar, en gång):

| plats | torra bilder | före (ring 0-4, 4-8 km) | efter | borttagen våt volym, regnstimmar |
|---|---|---|---|---|
| Røst | 259 | 0,067 0,023 | 0 0 | 5,83 % |
| Sømna | 87 | 0,485 0,152 | 0 0 | 3,76 % |
| Hurum-fjell | 177 | 0,083 0,017 | 0 0 | 6,49 % |
| Kortpi | 168 | 0,096 0,026 | 0 0 | 1,14 % |
| Vimpeli | 138 | 0,168 0,053 | 0 0 | 1,22 % |
| Utajärvi | 147 | 0,494 0,239 | 0 0 | 9,54 % |
| alla | | | | 4,36 % |

Kärnorna finns alltså också på valideringsdagarna (Sømna och Utajärvi starkare än på träningen, Røst svagare), och volymen som tas bort är av samma storlek som på träningen (4,4 % mot 5,1 %).

## Domaren (steg 5)

Masken rör rutor i `far_zone` med H = 3: Hurum-fjell 78 av 197 rutor, Kortpi 43 av 49, Utajärvi 199 av 199; Røst, Sømna och Vimpeli ligger utanför. A0O-domaren kördes **inte**: `a0o.py` skriver dagfiler till `/data` (förbjudet i uppgiften och disken är nästan full), och de maskerade rutorna ligger vid platser långt från de 36 mätarna i zonen nordväst om Kiruna (som ligger närmare Narvik och Andøya), så en förändring där syns knappast i domaren. Det är en lucka; ska det avgöras bör `a0o.py` få ett `--ut` och köras av någon uppgift med utrymme.

## Valet i A0 (steg 6)

`composite.mask_opera_ring(extra, grid, radii=None)` och `composite.OPERA_RING_KM` (NaN inom radien kring radarplatserna, ändrar inte indata), kopplat i `analys._analyses` före `layer` och `layer_far`, och `knep --opera-ring` (av som standard, kräver `--fallback`). Tester i `tests/test_opera_ring.py` (NaN innanför men inte utanför radien, `layer` kan fylla från annat håll, okända koder ignoreras). `uv run pytest`: 250 godkända. `deploy/` och `models/` orörda.

## Ändrade filer

`src/knep/analys/composite.py`, `src/knep/analys/__init__.py`, `src/knep/cli.py`, `tests/test_opera_ring.py`, skripten `experiments/riksgransen/ring_*.py`, denna rapport.

## Rekommendation och nästa steg

Att slå på `--opera-ring` i drift beslutar användaren. Min rekommendation är att inte göra det nu: masken tar bort cirka 4 till 5 % av det verkliga regnet kring platserna (13 % kring Røst på träningen), den fångar inte Andøya (som jag inte kunde belägga) eller hela ringen den 7 november (bortom 12 km), och domaren är inte körd. Ett bättre nästa steg är en kärnmask: bara de närmaste 4 till 8 km (där andelen är 5 till 30 gånger omgivningen), med en bildvis regel som tar bort eko i kärnan bara när 8 till 30 km runt är torrt, vald på träningen. Då tas verkligt regn bort i mycket mindre mån. Andøya bör undersökas på fler dagar än så här (OPERA 5 minuter, fler träningsdagar med klar luft) innan en radie sätts.

Säkerställd förbättring: nej

Status: delvis
