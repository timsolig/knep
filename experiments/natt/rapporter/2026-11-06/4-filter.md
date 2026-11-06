# Uppgift 4: ett första filter mot radarns artefakter i A0

Före uppgiften fanns rapporterna 1 (artefakterna), 2 (domaren) och 3 (A2), alla med `Status: klar`. Inget var halvfärdigt, och domaren användes som den är.

## Vad jag gjorde

`experiments/analys/filter.py` är filtret, med tester i `tests/test_analys_filter.py`. Kommandona:

    uv run python experiments/analys/filter.py karta                          # kartan och ekrarna ur träningsdagarna
    uv run python experiments/analys/filter.py kor A0 F0 F1 F2 F3 --del traning --dagar ...
    uv run python experiments/analys/filter.py urval --del traning            # valet enligt regeln
    uv run python experiments/analys/filter.py kor F? --del validering --dagar ...
    uv run python experiments/analys/filter.py tabell F? --mot A0             # domarens tabell och dom

### Filtret

Filtret verkar på varje A0-bild (efter utfyllnaden vid bortfall) och sätter eko till 0 där det slår till; NaN förblir NaN. Det använder ingen klimatologisk mask över rutor som ofta är våta. Det har tre delar.

1. **Klotterrutor**, en karta som räknas en gång ur uppgift 1:s summor per dag, **bara på de 28 träningsdagarna** (`/data/analys/filter/karta.npz`). En ruta är misstänkt om
   - den har eko under torra timmar (alla p7-mätare inom 25 km visar 0) minst 0,10 oftare än medianen inom 30 km **och** gör det (mer än 30 % av de torra timmarna) på minst 2 dagar, alltså på samma plats i olika väderlägen, eller
   - den har eko minst 0,10 oftare än medianen inom 30 km **och** samtidigt hög textur (|dBZ − grannarnas medel| i medel minst 6 dB) eller är isolerad (minst 5 % av ekot har under 3 % eko inom 42 km).

   Rutorna utvidgas en ruta. Ekofrekvensen ensam och stillheten ingår inte, eftersom båda är höga i fjällen (uppgift 1: `euler_lagr` 0,68 för den möjliga orografin). Trösklarna sattes i förväg ur uppgift 1:s tabeller (orografin har `f_torr` 0,044, textur 2,6 och `f_iso` 0,01; klottret 0,3 till 0,57, 7 till 26 och 0,1 till 0,5) och valdes inte på data. Kartan har **2 122 rutor** (0,8 % av de täckta), 557 av dem över 400 m (av 66 739).
2. **Kontrollen bild för bild** på klotterrutorna: ekot tas bort bara om omgivningen inom 42 km, utan klotterrutorna själva, har eko (R ≥ 0,1 mm/h) i mindre än en andel `kontext` av de täckta rutorna. Klotter som syns när det är torrt runt omkring tas bort. Regn på en misstänkt ruta när det regnar omkring står kvar. Det är det som skyddar den orografiska nederbörden: den hänger ihop med det övriga regnet (uppgift 1: isoleringen 0,01).
3. **Ekrar** med testet ur `bild.py` (andel eko i strålen minst 0,4, minst 0,25 i tre av fyra avståndsband och medianen 3 till 10° åt sidan högst 0,1). En stråle som klarar testet tas bort om
   - solen står mellan −1,5 och +1,5° vid radarn och strålen ligger inom ±3° från solens azimut (solstrålar), eller
   - den ligger inom ±1° från en fast eker, alltså samma radar och azimut på minst 5 av de 28 träningsdagarna (utan ekrarna nära solen). Det ger 28 strålar: sebaa 133 till 135° och 84 till 89°, seosd 293 till 298° och 218 till 221°, seoer 328 till 330° och 338 till 340°, sekaa 192 till 193° och sevax 141°. Med 3 dagar blev det 174 strålar, mest regnband, och det förkastades före körningen.

   I andra strålar tas inget bort, eftersom det regnar i sektorerna också.

Valfritt (`prickar`): isolerade kantiga prickar var som helst (eko med textur minst 8 dB och under 3 % eko inom 42 km).

Filtret läser bara den aktuella bilden, kartan och listan, så det kan köras i varje cykel. Det tar cirka 0,1 till 0,2 s per bild på Pi:n (se Tiden).

### Varianterna och valet på träningsdagarna

| variant | kartan | kontext | ekrar och sol | prickar |
|---|---|---|---|---|
| F0 | nej | | ja | nej |
| F1 | ja | 0,03 | ja | nej |
| F2 | ja | 0,10 | ja | nej |
| F3 | ja | 0,03 | ja | ja |

Regeln för valet skrevs i `cmd_urval` innan träningen kördes: bland varianterna som domaren inte flaggar som sämre i något mått för falska ekon eller terrängen (mot A0 på träningsdagarna) väljs den som minskar kartmåttet (rutor med eko i över hälften av de torra timmarna) mest; vid lika den med minst ingrepp.

Träningen kördes på **13 av de 28 träningsdagarna** (2020-02-10, 2020-07-24, 2020-10-07, 2021-01-23, 2021-05-11, 2022-12-20, 2023-01-04, 2023-07-12, 2023-11-22, 2024-07-28, 2024-09-26, 2025-06-23, 2025-10-24), utvalda för att täcka alla årstider. Alla 28 dagarna med fem system hade tagit cirka 70 min med två processer, för mycket för uppgiftens tid. Kartan bygger på alla 28 träningsdagar, så på de här 13 dagarna är filtret delvis bedömt på samma dagar som kartan räknades på. Därför avgör bara valideringen.

## Träningen (13 dagar, mot A0)

Skillnaden är i godhet (större är bättre) med 95 % ur bootstrap över dagarna, som i domaren (`/data/analys/filter/urval_traning.json`).

| mått | A0 | F0 | F1 | F2 | F3 |
|---|---|---|---|---|---|
| rutor med eko i över hälften av de torra timmarna, per dag | 52,1 | 52,1 | **40,1** (+8,4 till +16,2) | **35,8** (+9,7 till +25,0) | **37,3** (+10,9 till +19,1) |
| timme, falskt vid torr mätare | 0,0106 | 0,0106 | 0,0104 | 0,0103 | 0,0103 |
| timme över 400 m, falskt vid torr mätare | 0,0123 | 0,0123 | 0,0105 | 0,0102 | 0,0105 |
| timme över 400 m, MAE (mm) | 0,160 | 0,160 | 0,157 | (ej utskrivet) | (ej utskrivet) |
| timme över 400 m, kvot summa | 0,637 | 0,637 | **0,625** (−0,049 till −0,000) | **0,619** (−0,077 till −0,000) | **0,625** (−0,051 till −0,002) |
| kvart över 400 m, kvot summa | 0,608 | 0,608 | **0,595** (−0,055 till −0,000) | **0,589** | **0,595** |
| timme lovart, kvot summa | 0,714 | 0,714 | 0,714 | 0,714 | **0,714** (−0,002 till −0,000) |
| timme, kvot summa | 0,940 | 0,940 | 0,939 | 0,938 | 0,938 |
| timme, CSI 0,5 | 0,523 | 0,523 | 0,523 | 0,523 | 0,523 |

Domen mot A0 på träningen:

- **F0** (bara ekrar och sol): varken bättre eller sämre. Den ändrar nästan ingenting vid mätarna och inget i kartmåttet; de fasta ekrarna och solstrålarna klarar testet för en smal och lång stråle i få bilder.
- **F1, F2**: bättre i FSS 0,5, 1 och 5 (kvart och timme) och MAE per kvart, men **sämre i summakvoten över 400 m** (kvart och timme) med intervallet helt under 0, dock bara precis (övre gränsen −0,0001).
- **F3** (med prickarna): dessutom sämre i summakvoten på lovartsidan.

Enligt regeln väljs därför **F0**. Det är det försiktiga valet, men F0 gör nästan ingenting.

### Vad som ger förlusten över 400 m

Förlusten vid mätarna kommer **helt från mätare över 400 m på tre dagar** (2020-02-10 −7,5 mm, 2020-07-24 −1,0 mm och 2020-10-07 −1,5 mm, summerat över mätarna); på de andra tio dagarna ändras summan vid mätarna med högst 0,03 mm. `filter_diag.py` visar att bara två mätare ligger i kartans rutor, och ingen av dem uppfyller kriterierna själv; de ligger i utvidgningen bredvid klottret. Den som ger förlusten är station 105220 på 448 m. Den visade 3,0 mm 2020-02-10, och filtret tog bort 7,5 mm där, så **A0 låg minst 4,5 mm över mätaren** och filtret flyttade analysen mot mätaren. Det syns också i att MAE och falska ekon över 400 m blir bättre med F1 (0,160 till 0,157 mm och 0,0123 till 0,0105).

Summakvoten blir ändå sämre, eftersom den är under 1 över 400 m (0,64): radarn underskattar i fjällen, och varje överskott någonstans (även klotter vid en torr eller nästan torr mätare) drar summan närmare mätarnas och räknas som en förbättring. Det är en svaghet i måttet och inte ett tecken på att filtret tar orografin. Domaren ändrades inte (uppdraget: ändra inte domaren för att ett system ska se bättre ut), och valet följer regeln. Förslaget till domaren står under Nästa steg.

## Valideringen (16 dagar, domaren mot A0)

Parametrarna och valet var frysta innan valideringen kördes. **F0 är det valda filtret.** F1 kördes också, som upplysning om kartdelen, och användes inte för något val. Hela tabellerna skrivs ut med `filter.py tabell F0 --mot A0` och `tabell F1 --mot A0` och ligger i `/data/analys/domare/tabell_F0_mot_A0_validering.json` och `tabell_F1_mot_A0_validering.json`.

**F0 mot A0: inte bättre och inte sämre.** Inget mått har intervallet helt på någon sida. Kartmåttet går från 36,6 till 35,9 rutor per dag (+0,7 i godhet, −0,0 till +1,75). Ekrarna och solstrålarna gör alltså för lite för att märkas i dygnens summor vid mätarna.

**F1 mot A0** (urval, skillnad i godhet med 95 %):

| delmängd | mått | F1 | A0 | skillnad (95 %) |
|---|---|---|---|---|
| kartan | rutor med eko i över hälften av de torra timmarna, per dag | **24,1** | 36,6 | **+12,5 (+8,1 till +17,6)** |
| timme, alla | falskt vid torr mätare | 0,010 | 0,010 | +0,000 (+0,000 till +0,001) |
| timme, alla | kvot summa | 0,889 | 0,890 | −0,001 (−0,004 till +0,001) |
| timme, alla | MAE (mm) | 0,233 | 0,233 | **+0,000 (+0,000 till +0,001)** |
| timme, alla | CSI 1 | 0,423 | 0,423 | +0,001 (+0,000 till +0,002) |
| kvart, alla | kvot summa | 0,824 | 0,825 | −0,002 (−0,005 till −0,000) |
| timme, över 400 m | falskt vid torr mätare | **0,007** | 0,009 | +0,002 (+0,000 till +0,008) |
| timme, över 400 m | MAE (mm) | 0,174 | 0,177 | +0,003 (+0,000 till +0,011) |
| timme, över 400 m | CSI 0,5 | 0,306 | 0,302 | +0,004 (+0,000 till +0,015) |
| timme, över 400 m | CSI 1 | 0,253 | 0,248 | +0,005 (+0,000 till +0,020) |
| timme, över 400 m | kvot > 1 mm | 0,481 | 0,481 | +0,000 (+0,000 till +0,000) |
| timme, över 400 m | **kvot summa** | 0,508 | 0,524 | **−0,030 (−0,100 till −0,000)** |
| kvart, över 400 m | **kvot summa** | 0,480 | 0,495 | **−0,031 (−0,102 till −0,000)** |
| timme, lovart | kvot summa | 0,671 | 0,671 | −0,000 (−0,000 till +0,000) |
| timme, lovart | CSI 0,5 | 0,472 | 0,472 | +0,000 |
| kvart, lovart | falskt vid torr mätare | 0,016 | 0,016 | +0,000 |

Domen för F1: bättre i MAE (kvart och timme) och FSS 0,5 och 1 (kvart och timme) och FSS 5 per timme, men **sämre i summakvoten över 400 m** (kvart och timme), så **inte bättre**. Mönstret är detsamma som på träningen:

- **Kartdelen tar bort fast klotter**: en tredjedel av rutorna med eko under torra timmar försvinner, med intervallet helt på den bättre sidan, och de falska ekona vid torra mätare över 400 m minskar från 0,009 till 0,007.
- **Den tar inte orografisk nederbörd på lovartsidan**: alla mått på lovartsidan är oförändrade (skillnaden är 0,000 med intervallet 0 i båda ändarna), alltså rörs inte ekot vid mätarna där.
- **Över 400 m tas inget bort i timmar när mätaren har över 1 mm** (kvoten för perioder över 1 mm är exakt densamma, 0,481), och MAE och CSI blir bättre. Det som försvinner ur summan är eko vid mätare som visar 0 eller nästan 0 mm, alltså överskott. Summakvoten blir ändå sämre, eftersom den är 0,52 och varje överskott drar den mot 1 (se Träningen).

Enligt regeln är inget av filtren bättre än A0, och F0, som valdes på träningen, ändrar ingenting som syns. F1 klarar inte regeln på grund av summakvoten över 400 m, trots att allt annat pekar på att den tar bort klotter och inte orografi. Jag har inte ändrat domaren eller regeln för att släppa igenom F1.

## Tiden på Pi:n

Ur körningarna (två processer, delad processor med driften): varje system räknas efter det förra på samma A0-bilder, och tidsstämplarna i loggen visar att F0 tar 27 till 45 s och F1 40 till 60 s per dag om 288 bilder, inklusive domarens bedömning av dagen (cirka 20 s). Filtret kostar alltså i storleksordningen 0,1 s per bild för F0 och 0,15 s för F1, vilket ryms i en cykel. Det är inte mätt separat från bedömningen.

## Det som inte blev gjort och begränsningar

- **Inget i drift.** Valet i `src/knep/analys/` lades bara till om filtret höll, och det gjorde det inte. Jag kopplade först in kartdelen som ett val (`bygg(..., klotter_path=None)` och `--klotter`, standard av) och tog sedan bort inkopplingen igen när valideringen var klar; `src/knep/analys/__init__.py` och `src/knep/cli.py` är oförändrade mot `main`. Modulen `src/knep/analys/klotter.py` (kartdelen, samma regel som i F1) och dess test `tests/test_klotter.py` ligger kvar **utan att användas**, eftersom körningen inte fick radera filer. Den som vill ha bort dem kan ta bort de två filerna; inget annat beror på dem.
- **Rörelsen ingår inte i filtret.** Stillheten mot rörelsefältet skiljer inte klotter från orografi (uppgift 1), så den användes inte. Ett test för klotter som står still medan omgivningen rör sig behöver kombineras med att omgivningen är torr, och det gör kontrollen mot omgivningen redan.
- **Satellitens molnmask** hämtades inte (nätet användes inte i den här uppgiften heller).
- **Träningen gjordes på 13 av 28 dagar**, och kartan räknades på alla 28, så träningssiffrorna för kartdelen är delvis i urvalet. Valideringen är oberoende.
- **Mätarna i utvidgningen**: de två mätarna i kartans rutor ligger i den utvidgning med en ruta som lades runt klottret. Utan utvidgningen hade filtret troligen inte rört dem alls, men det prövades inte (det hade varit ett val på valideringen).

## Ändrade filer

- `experiments/analys/filter.py` (ny): kartan, filtret, varianterna F0 till F3 som system i domaren, kommandona `karta`, `kor`, `urval` och `tabell`.
- `experiments/analys/filter_diag.py` (ny): mätarna i kartans rutor på träningsdagarna.
- `tests/test_analys_filter.py` (ny): 4 tester (isolerat klotter tas bort och NaN står kvar, eko på misstänkta rutor står kvar när det regnar omkring, inget utanför kartan rörs utan valen, fasta ekrar tas bara bort när testet för en smal stråle slår till).
- `src/knep/analys/klotter.py` och `tests/test_klotter.py` (nya, oanvända, se ovan).
- Inget i domaren, `deploy/`, `models/` eller `.github/` ändrades. `uv run pytest` ger 162 godkända.
- Data under `/data/analys/filter/` (karta, ekrar, urvalet, under 1 MB), domarens summor i `/data/analys/domare/F0` till `F3` och A0 på de 13 träningsdagarna, och rörelsefälten för träningsdagarna i `/data/analys/domare/rorelse/` (cirka 70 MB). Allt under `/data/analys` är cirka 0,75 GB, och /data hade 5,4 GB ledigt.

## Nästa steg

1. **Domaren**: summakvoten belönar överskott när analysen är för torr (över 400 m är kvoten 0,5). Ett mått som inte gör det vore kvoten för perioder där mätaren har regn (> 0,1 mm), eller att kvoten i terrängens delmängder bara bedöms tillsammans med MAE. Det är en ändring av domaren och ska beslutas för sig och köras om för A0, A1 och A2, inte för att få igenom F1.
2. **Kartdelen utan utvidgning**, vald på träningsdagarna (alla 28), och bedömd igen på valideringen. Då rör den sannolikt ingen mätare alls, och domaren kan bara se den i kartmåttet.
3. **Filtret före A1 och A2**: uppgift 2 och 3 visade att A1 och A2 smetar ut och skalar upp klottret. F1 under A1 och A2 bör ge färre falska ekon per kvart i terrängen, där A2 förlorade mot A1.
4. **Ekrarna**: testet för en smal och lång stråle slår till för sällan för att märkas. Ett test med lägre andel längs strålen inne i de fasta sektorerna, eller per avståndsband, vore nästa försök.

Status: delvis
