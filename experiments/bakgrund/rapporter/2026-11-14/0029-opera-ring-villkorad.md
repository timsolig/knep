# Uppgift 0029: ringen vid OPERA-radarerna, mask villkorad per bild

Kort: Den villkorade masken (eko inom r NaN bara när ringen r + 4 till 40 km är torr) tar kärnorna vid alla sex platser ner till omgivningens nivå och tar bara 0,009 % av den våta volymen på träningen och 0,005 % på valideringen, mot 5,1 % och 4,4 % för den fasta masken, men den frysta radien 8 km är för liten för skivan vid Røst den 7 november (den ligger kvar; en radie på 24 km tar bort den i 9 av 10 bilder, men valdes inte); lagd bakom `--opera-ring villkor`, avstängd som standard, ingen säkerställd förbättring.

## Vad som gjordes

Skelett och commit först. Nytt skript `experiments/riksgransen/ring_villkor.py` (läget `trana`, `fall`, `validera`; återanvänder inläsning och mått ur `ring_kand.py`). Dagarna kommer ur `domare.days` via `rk.dagar`: 9 träningsdagar för valet, 7 valideringsdagar en gång; testdelen lästes aldrig. Inget skrevs till `/data`; kartor och json ligger i `/dev/shm/opera_ring/` (`trana_villkor.json`, `fryst_villkor.json`, `validera_villkor.json`, `fall_villkor_rost.png`, `fall_villkor_andoya.png`). Skalet nekade omdirigering och `sed -i`.

## Kandidaterna (fastlagda i docstringen före siffrorna)

För varje plats och bild: eko inom radien r blir NaN bara om andelen eko (>= 0,1 mm/h) bland täckta rutor i ringen r + 4 till 40 km är under p (mindre än 30 täckta rutor: ingen maskering). Radier: 8, 12, 16, 24 km lika för alla platser och "per" (0028:s radier men 24 för Røst). Villkor: andel p i 0,02, 0,05, 0,10, eller intensitet (medel under 0,1 mm/h). Totalt 20 kandidater, med den fasta masken 0028 som jämförelse. Förhandsregel: bland dem som tar ringarna 0 till 4 och 4 till 8 km ner till högst 2 gånger andelen vid 25 till 30 km vid alla sex platser, den med minst borttagen våt volym; kravet för att ersätta den fasta masken är under 1 % borttagen volym.

## Träning (9 dagar)

Andel eko i ring 0-4 och 4-8 km i torra bilder, och borttagen våt volym (inom 100 km, timmar med över 20 % våta rutor inom 150 km). Alla kandidaters siffror står i körningens utdata; här urvalet:

| plats | före | fast mask 0028 | **r8, p 0,10 (vald)** | r24, p 0,10 | r12, p 0,05 |
|---|---|---|---|---|---|
| Røst | 0,706 0,163 | 0 0 | 0 0 | 0 0 | 0 0 |
| Sømna | 0,219 0,074 | 0 0 | 0,019 0,007 | 0 0 | 0,104 0,043 |
| Hurum-fjell | 0,268 0,135 | 0 0 | 0,028 0,028 | 0 0 | 0,054 0,044 |
| Kortpi | 0,250 0,062 | 0 0 | 0 0 | 0 0 | 0,001 0,001 |
| Vimpeli | 0,254 0,095 | 0 0 | 0,001 0,001 | 0 0 | 0,012 0,006 |
| Utajärvi | 0,402 0,111 | 0 0 | 0 0 | 0 0 | 0,010 0,002 |
| **borttagen volym, alla** | | **5,100 %** | **0,009 %** | 0,042 % | 0,006 % |

Borttagen volym per plats för vald variant: Røst 0,005, Sømna 0,013, Hurum-fjell 0,010, Kortpi 0,009, Vimpeli 0,002, Utajärvi 0,014 % (fasta masken: 13,1, 3,1, 6,0, 1,0, 1,0, 6,8 %).

Regeln (strikt, 2 gånger andelen vid 25 till 30 km) klarades av sex kandidater: r8_v0,10 (0,009 %), per_v0,10 (0,011), r12_v0,10 (0,012), r16_v0,10 (0,015), r24_v0,05 (0,023), r24_v0,10 (0,042). Intensitetsvillkoret (medel under 0,1 mm/h) klarade regeln inte för någon radie (kvar vid Vimpeli: 0,15 till 0,17 i ring 0-4 km med r8, r12, r16) och tog mer volym (upp till 0,29 % per plats, r24: 0,128 % totalt); andelsvillkoret var bättre. Låga p (0,02) rensar för lite, eftersom ringens egna ytterkanter räknas in. **Vald: r8_v0,10 (radie 8 km vid alla sex platser, p 0,10)**, fryst innan fallet och valideringen kördes.

Skillnaden mellan kandidaterna på volym är liten (alla under 0,3 %); valet av r8 är ett resultat av förhandsregeln, inte av att radien 8 km är rätt för skivorna (se fallet).

## Fallet 2026-11-07 (steg 4)

Vald variant (r8, p 0,10): tar **inte** bort skivan vid Røst. Andel eko i ringarna 0-4 ... 25-30 km vid Røst är 0,85 0,87 0,85 0,84 0,72 0,42 0,27 (16:00) och likadant efter, i alla 10 bilder; ringen 12 till 40 km är aldrig under 10 % eko (andelen vid 25 till 30 km är 0,04 till 0,27 och skivan går ut till cirka 20 km), och radien 8 km hade ändå lämnat 8 till 24 km. Andøya: verkligt regn över hela området (andel 0,7 till 1,0 i alla ringar), ingen mask där och inget syns att ta bort.

Som upplysning efteråt (inte vald, inget ändrat utifrån den): r24_v0,10 tar bort skivan vid Røst i 9 av 10 bilder (0-20 km ner till 0, 20 till 25 km 0,02 till 0,06 mot 0,29 till 0,51) och behåller den i första bilden (kl. 16:00, andel 0,27 vid 25 till 30 km). På träningen kostar den 0,042 % av volymen (Røst 0,006 %), så den skulle klara kravet på volym. Kartorna `fall_villkor_rost.png` och `fall_villkor_andoya.png` i `/dev/shm/opera_ring/` visar den senaste körningen (r24_v0,10).

## Validering (steg 5, en gång, vald variant mot fast mask)

| plats | torra bilder | före (0-4, 4-8) | villkorad efter | borttagen volym villkorad | borttagen volym fast mask |
|---|---|---|---|---|---|
| Røst | 259 | 0,067 0,023 | 0,011 0,004 | 0,008 % | 5,83 % |
| Sømna | 87 | 0,485 0,152 | 0 0 | 0,006 % | 3,76 % |
| Hurum-fjell | 177 | 0,083 0,017 | 0,004 0,001 | 0,005 % | 6,49 % |
| Kortpi | 168 | 0,096 0,026 | 0 0 | 0,007 % | 1,14 % |
| Vimpeli | 138 | 0,168 0,053 | 0 0 | 0,001 % | 1,22 % |
| Utajärvi | 147 | 0,494 0,239 | 0 0 | 0,002 % | 9,54 % |
| **alla** | | | | **0,005 %** | **4,36 %** |

Kravet (under 1 %) klaras med stor marginal, och ringarna 0 till 4 och 4 till 8 km hamnar i nivå med 25 till 30 km vid alla platser (Røst 0,011 mot 0,006). Ringarna utanför 8 km rörs inte (8 till 12 km vid Sømna är 0,062 före och efter).

## Koden (steg 6)

`composite.mask_opera_ring_villkor` (och `OPERA_RING_VILLKOR_KM`, 8 km för de sex platserna; `RING_GAP_KM`, `RING_MAX_KM`, `RING_ANDEL`), `analys._analyses` väljer den vid `opera_ring == "villkor"`, och `knep --opera-ring [fast|villkor]` (utan värde är `fast`, så den fasta masken går att köra som förut; av som standard, kräver `--fallback`). Tre nya tester i `tests/test_opera_ring.py` (kärnan maskas när ringen är torr, behålls vid regn runt, ingen maskering utan täckt ring). `uv run pytest`: 253 godkända. `deploy/` och `models/` orörda. A0O-domaren kördes inte (den skriver till `/data`); rutorna som maskas ligger ändå mest långt från mätarna i zonen nordväst om Kiruna, och volymen som tas bort är under 0,01 %, så ändringen syns knappast där.

## Ändrade filer

`src/knep/analys/composite.py`, `src/knep/analys/__init__.py`, `src/knep/cli.py`, `tests/test_opera_ring.py`, `experiments/riksgransen/ring_villkor.py`, denna rapport.

## Rekommendation och nästa steg

Drift (användaren beslutar): `--opera-ring villkor` är ofarlig (under 0,01 % av regnet) och tar bort kärnorna (0 till 8 km), så den kan slås på, men den löser inte det användaren såg den 7 november, eftersom skivan där är 18 till 24 km. Jag rekommenderar att först köra om valet med radien 24 km för Røst (och en radie per plats ur fler torra bilder), vilket kräver en ny förhandsregel eftersom den här regeln väljer minsta radie som klarar kraven på 0 till 8 km och därför inte ser skivan. Den fasta masken bör inte slås på.

Nästa steg: (1) en regel som också kräver att ringarna 8 till 25 km faller för de bilder där skivan syns (fallet och fler dygn med klar luft vid Røst, till exempel via bilder med över 50 % eko inom 12 km), valt på träningen; (2) Andøya på fler dagar med klar luft; (3) A0O-domaren med `--ut` till en katalog med plats, eller en körning av domaren på en annan disk.

Säkerställd förbättring: nej

Status: delvis
