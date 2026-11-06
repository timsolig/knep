# Uppgift 1: inventering av radarns artefakter

Före uppgiften fanns bara provet av behörigheterna (`prov.md`), så ingen tidigare uppgift var halvfärdig.

## Vad jag gjorde

Jag räknade per ruta på radarns rutnät (887 × 471 rutor, 2 km) för de 28 träningsdagarna och de 16 valideringsdagarna, 44 dagar och 288 bilder per dag. Testdagarna lästes aldrig: `days()` i skriptet tar bara träningen och delen `validering` och kontrollerar att ingen testdag kommer med. Mätarna i `p7.npz` filtreras på dagens timmar direkt när filen läses.

- `experiments/analys/artefakter.py dag` räknar summor och antal per ruta och dag och sparar dem i `/data/analys/artefakter/dag/<dag>.npz` (5 MB per dag). Där finns också rörelsefältet glest var 30:e minut.
  - Eko betyder R ≥ 0,1 mm/h.
  - Rörelsen var 30:e minut kommer ur `motion_field` på bilderna t−30, t−15 och t, som i kedjan (step 4).
  - Stillastående räknas var 15:e minut där rörelsen över 15 min är minst 6 km. Jag jämför felet på platsen (Euler, |dBZ(t) − dBZ(t−15)|) med felet längs rörelsen (Lagrange). `euler_lagr` är kvoten mellan dem, och under 1 betyder att rutan står still fast allt annat rör sig. `f_still` är andelen fall där Euler ≤ 1 dB och Lagrange minst 3 dB större.
  - Torra timmar är timmar då minst en p7-mätare finns inom 25 km och alla är torra (0 mm). `f_torr` är andelen eko under dem.
  - Texturen `tex` är |dBZ − medlet av de 8 grannarna|. Tidsvariationen är `d5`, medelvärdet av |ΔdBZ| över 5 min, och `flip`, hur ofta ekot slås av och på.
  - `f_iso` är andelen eko där färre än 3 % av rutorna inom 42 km har eko.
  - `lyft` är P(eko | rörelsen mot sluttningen) / P(eko | rörelsen nedför), med GLO-90 från `/data/projektion/hojd_2km.npz`.
- `experiments/analys/karta.py` slår ihop dagarna.
  - Det ger `overskott`, ekofrekvensen minus medianen inom 30 km, och `dagar_eko30` och `dagar_torr30`, alltså hur många dagar rutan har eko i mer än 30 % av bilderna eller av de torra timmarna.
  - Ekrarna hittas som smala toppar i azimutprofilen av överskottet kring varje radar i `composite.RADARS`, på 40 till 200 km avstånd. Det görs för alla dagar ihop och per dag, och toppar per dag jämförs med solens azimut vid upp- och nedgång.
  - Vindkraftverken kommer från OpenStreetMap: 5 605 noder i Sverige med `generator:source=wind`, via Overpass och delvis importerade från Vindbrukskollen. Länsstyrelsens egen nedladdning hittade jag ingen direkt länk till.
  - Kandidaterna **väljs på träningsdagarna**: överskott ≥ 0,05 eller `f_torr` ≥ 0,10. De typas i den här ordningen: närklotter (≤ 15 km från en radar), hav, vindkraft (inom 2 km från ett verk), eker, fast klotter på land (`euler_lagr` < 0,6 eller `f_torr` ≥ 0,10), möjlig orografi (över 300 m, lyft ≥ 1,3, `f_torr` < 0,05) och övrigt.

Resultatet ligger i `/data/analys/artefakter/`, 231 MB, med 6,1 GB ledigt på /data:

- `kartor.npz`: alla kartor i float16, typen, kandidaterna och vindkraftsrutorna.
- `tabell.json`: klasser, de 40 värsta rutorna, ekrarna och stabiliteten.
- `bild/*.png`: kartorna med radarerna och 400-meterskurvan.
- `vind/osm_vindkraft.json`.
- `dag/`: underlaget per dag.

## De värsta rutorna

Rutorna är sorterade efter överskott + `f_torr` på alla 44 dagar, med en ruta per 10 km. `_val` är samma mått på bara valideringsdagarna. Medianen för alla täckta rutor ges som jämförelse: f_eko 0,17, överskott 0, f_torr 0,05, euler_lagr 1,07, f_still 0,05, tex 2,4, f_iso 0,002 och dagar_eko30 8.

| lat | lon | typ | f_eko | överskott | f_torr | f_torr_val | euler_lagr | f_still | tex | d5 | f_iso | lyft | dagar_eko30 | höjd m | radar, km |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 63,59 | 15,09 | vindkraft | 0,62 | 0,46 | 0,57 | 0,53 | 0,37 | 0,12 | 11,6 | 6,3 | 0,31 | 1,15 | 35 | 433 | seosd 36 |
| 63,52 | 19,30 | vindkraft | 0,62 | 0,41 | 0,55 | 0,54 | 0,37 | 0,13 | 8,4 | 4,7 | 0,48 | 1,03 | 39 | 147 | seoer 45 |
| 65,40 | 21,87 | närklotter | 0,61 | 0,37 | 0,55 | 0,53 | 0,18 | 0,40 | 10,2 | 2,4 | 0,51 | 1,46 | 28 | 4 | sella 2 |
| 62,00 | 16,82 | fast klotter | 0,60 | 0,37 | 0,48 | 0,39 | 0,37 | 0,18 | 9,4 | 5,5 | 0,36 | 1,55 | 38 | 155 | sehuv 48 |
| 60,44 | 15,08 | eker | 0,60 | 0,32 | 0,39 | 0,45 | 0,35 | 0,15 | 10,3 | 4,7 | 0,16 | 1,51 | 38 | 397 | selek 32 |
| 64,22 | 18,41 | vindkraft | 0,46 | 0,31 | 0,39 | 0,36 | 0,13 | 0,19 | 22,7 | 10,0 | 0,42 | 0,94 | 27 | 470 | seoer 65 |
| 64,02 | 18,18 | vindkraft | 0,45 | 0,28 | 0,39 | 0,26 | 0,36 | 0,11 | 13,1 | 9,0 | 0,38 | 1,44 | 27 | 434 | seoer 45 |
| 68,04 | 20,33 | fast klotter | 0,47 | 0,27 | 0,37 | 0,32 | 0,22 | 0,30 | 9,3 | 3,1 | 0,38 | 0,50 | 16 | 365 | sekrn 40 |
| 63,36 | 16,22 | vindkraft | 0,45 | 0,29 | 0,34 | 0,34 | 0,38 | 0,12 | 6,6 | 5,4 | 0,36 | 1,05 | 29 | 442 | seosd 72 |
| 58,23 | 12,88 | närklotter | 0,47 | 0,27 | 0,35 | 0,33 | 0,29 | 0,34 | 7,8 | 3,2 | 0,35 | 0,57 | 29 | 90 | sevax 2 |
| 60,80 | 14,49 | fast klotter | 0,51 | 0,22 | 0,39 | 0,48 | 0,41 | 0,13 | 9,5 | 4,9 | 0,24 | 1,44 | 31 | 354 | selek 24 |
| 67,89 | 18,51 | eker | 0,44 | 0,25 | 0,34 | 0,39 | 0,33 | 0,18 | 12,2 | 6,3 | 0,12 | 1,14 | 20 | 1573 | sekrn 92 |
| 63,77 | 17,42 | vindkraft | 0,45 | 0,26 | 0,34 | 0,33 | 0,28 | 0,09 | 15,4 | 10,0 | 0,35 | 1,43 | 27 | 376 | seoer 51 |
| 63,70 | 18,88 | vindkraft | 0,46 | 0,26 | 0,32 | 0,35 | 0,50 | 0,09 | 9,7 | 7,0 | 0,33 | 1,04 | 31 | 197 | seoer 24 |
| 60,33 | 15,15 | fast klotter | 0,46 | 0,17 | 0,40 | 0,35 | 0,18 | 0,11 | 26,2 | 20,0 | 0,35 | 0,80 | 33 | 278 | selek 45 |
| 58,44 | 13,52 | vindkraft | 0,77 | 0,53 | (ingen mätare) | | 0,28 | 0,13 | 11,9 | 6,4 | 0,35 | 1,38 | 41 | 127 | sevax 45 |
| 63,88 | 18,00 | vindkraft | 0,65 | 0,46 | (ingen mätare) | | 0,30 | 0,17 | 10,5 | 5,3 | 0,40 | 1,14 | 33 | 429 | seoer 34 |
| 65,40 | 20,65 | vindkraft | 0,69 | 0,44 | (ingen mätare) | | 0,29 | 0,12 | 10,1 | 9,9 | 0,22 | 1,18 | 42 | 353 | sella 57 |
| 67,61 | 20,13 | vindkraft | 0,63 | 0,43 | (ingen mätare) | | 0,16 | 0,12 | 25,7 | 12,2 | 0,52 | 0,90 | 30 | 564 | sekrn 23 |
| 67,84 | 20,33 | fast klotter | 0,62 | 0,41 | (ingen mätare) | | 0,16 | 0,32 | 12,3 | 3,2 | 0,48 | 1,03 | 24 | 442 | sekrn 20 |
| 56,37 | 15,79 | närklotter | 0,59 | 0,42 | (ingen mätare) | | 0,26 | 0,29 | 9,2 | 3,5 | 0,49 | 1,32 | 33 | 92 | sekaa 13 |

"Ingen mätare" betyder att det inte finns någon p7-mätare inom 25 km, så `f_torr` kan inte räknas. Hela listan med 40 rutor finns i `tabell.json`.

Det som syns:

- **De värsta rutorna är tydligt klotter och står kvar på valideringsdagarna.** De har eko i 45 till 77 % av bilderna mot 17 % i medel, och eko under torra timmar i 30 till 57 % mot 5 %. De står still (`euler_lagr` 0,13 till 0,5 mot 1,07) och är isolerade (`f_iso` 0,1 till 0,5 mot 0,002). Texturen är 3 till 10 gånger medlet. De har eko på 20 till 42 av 44 dagar, alltså i alla väderlägen. `f_torr_val` och överskottet på valideringsdagarna ligger nära träningens.
- **Vindkraft**: de flesta av de värsta rutorna ligger i vindkraftsområden i Jämtland, Västernorrland och Västerbotten (seosd, seoer) och vid Markbygden (65,40 / 20,65). De har högre textur och tidsvariation (d5 upp till 10 dB, flip 0,12) än fast klotter vid radarn (d5 cirka 3). Det stämmer med att rotorerna blinkar. Men den **typiska** vindkraftsrutan är ren: över alla 1 972 verksrutor är medianöverskottet 0,001 och `f_torr` 0,053, ungefär som ringen 4 till 10 km runt dem. Bara en del parker syns, troligen de som ligger i strålen nära en radar. En mask på alla verk vore alltså fel.
- **Närklotter** vid radarplatserna (sella, sevax, sekaa, seoer) står mest still av alla typer (`f_still` 0,3 till 0,4) och har låg tidsvariation.
- **Ekrar** som återkommer, på alla dagar ihop med z > 6: 32 på träningsdagarna och 63 på valideringsdagarna, varav 29 finns i båda. De starkaste är noand 118°, nohfj 49 till 51°, sebaa 84 till 85° och 132°, seoer 336 till 339° (19 toppar, flest av alla radarer), seatv 269° och 285° och seang 32°. Per dag finns 904 toppar, och flest har noand (118° och 140° på 2019-03-08 och 2019-03-17) och norsa (102 till 120° på 2021-01-20).
- **Solstrålar**: av ekrarna per dag ligger 82 av 904 (9 %) inom ±8° från solens azimut vid upp- eller nedgång. Det är vad slumpen ger (32°/360° = 9 %), så **daglig ekofrekvens räcker inte för att se solen**. Solstrålar varar några bilder och behöver hittas bild för bild. Det hann jag inte göra.
- **Havsklotter** syns inte tydligt i de här dagarna. Kandidaterna över havet (343 rutor) har medianöverskott 0,006 och `euler_lagr` 1,12, och rör sig alltså med vädret. Det är mest verkligt regn och snöbyar nära kusten som har blivit kandidater genom `f_torr`. `f_torr` är svagt där, eftersom bara kustmätarna når ut 25 km. Anaprop, som kommer med inversioner, syns inte heller som en egen grupp i dygnsfrekvenserna.

## Jämförelse med höjdmodellen

Över 400 m finns 48 585 täckta rutor, och 865 av dem är kandidater (1,8 %): 326 fast klotter, 98 vindkraft, 88 ekrar, 32 möjlig orografi och 321 övrigt. Där höjden är över 300 m och lyftet över 1,3 är 395 av 26 907 rutor kandidater.

Medianer per klass, för alla 44 dagar:

| klass | rutor | f_eko | överskott | f_torr | f_vat | euler_lagr | f_still | tex | d5 | flip | f_iso | lyft | dagar_eko30 | dagar_torr30 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| närklotter vid radar | 67 | 0,28 | 0,050 | 0,111 | 0,65 | 0,64 | 0,104 | 5,1 | 5,6 | 0,088 | 0,023 | 1,02 | 19 | 5 |
| vindkraft (kandidat) | 322 | 0,32 | 0,091 | 0,117 | 0,61 | 0,49 | 0,095 | 7,2 | 6,6 | 0,118 | 0,105 | 1,15 | 21 | 2 |
| eker | 216 | 0,23 | 0,058 | 0,093 | 0,59 | 0,61 | 0,102 | 4,0 | 5,3 | 0,058 | 0,010 | 1,13 | 13 | 0 |
| fast klotter (land) | 813 | 0,28 | 0,009 | 0,109 | 0,64 | 0,91 | 0,070 | 2,5 | 4,6 | 0,053 | 0,002 | 1,10 | 19 | 4 |
| havsklotter (kandidat) | 343 | 0,25 | 0,006 | 0,103 | 0,64 | 1,12 | 0,054 | 2,3 | 5,7 | 0,055 | 0,003 | 1,77 | 15 | 3 |
| **möjlig orografi** | 49 | 0,22 | 0,058 | **0,044** | 0,54 | 0,68 | 0,090 | **2,6** | 4,2 | 0,052 | **0,010** | **1,71** | 13 | **0** |
| övrigt | 1064 | 0,27 | 0,003 | 0,092 | 0,59 | 1,10 | 0,054 | 2,0 | 4,4 | 0,049 | 0,001 | 1,08 | 18 | 3 |
| över 400 m, ej kandidat | 47 720 | 0,09 | 0 | 0,035 | 0,39 | 0,87 | 0,065 | 2,9 | 6,2 | 0,029 | 0,002 | 1,07 | 3 | 0 |
| låglandet under 100 m, ej kandidat | 53 488 | 0,18 | 0 | 0,048 | 0,62 | 1,08 | 0,052 | 2,4 | 6,2 | 0,042 | 0,002 | 1,11 | 9 | 0 |
| alla täckta | 261 280 | 0,17 | 0 | 0,050 | 0,57 | 1,07 | 0,052 | 2,4 | 6,0 | 0,041 | 0,002 | 1,09 | 8 | 0 |

Vad som skiljer de misstänkta rutorna där orografisk nederbörd är väntad (över 300 m, eko oftare när det blåser mot sluttningen) från klottret:

- **Stillheten skiljer dem inte åt.** Orografin har `euler_lagr` 0,68, och även fjällen utan kandidater har 0,87 mot 1,08 i låglandet. Nederbörd bunden till terrängen står också still i förhållande till rörelsefältet. Ett filter som tar bort det som står still tar bort orografin. Det är precis den fälla uppdraget varnar för.
- **Det som skiljer:**
  - *Torrt vid mätarna*: `f_torr` är 0,04 för orografin, under medlet 0,05, och 0,3 till 0,57 för det värsta klottret.
  - *Antal dagar med eko under torra timmar*: 0 för orografin och 2 till 5 för klottret.
  - *Isolering*: `f_iso` 0,01 mot 0,1 till 0,5. Orografin hänger ihop med det övriga regnet.
  - *Textur*: 2,6, som vanligt regn, mot 7 till 26.
  - *Lyftet*: 1,7, alltså eko 70 % oftare med vind mot sluttningen, mot 0,5 till 1,15 för klottret.
- Klassen "fast klotter (land)" är bred. Medianerna (`tex` 2,5, `f_iso` 0,002, `euler_lagr` 0,91) ligger nära vanligt regn, och bara 325 av 813 rutor står kvar på valideringsdagarna. Hela klassen är alltså inte klotter: den innehåller många rutor som kom med bara för att `f_torr` var hög på några regniga träningsdagar. Det rena klottret är toppen av klassen.

Stabilitet (kandidater på träningsdagarna som också är kandidater på valideringsdagarna):

| typ | kvar |
|---|---|
| ekrar | 168 av 216 (78 %) |
| vindkraft | 235 av 322 (73 %) |
| havet | 201 av 343 |
| närklotter | 36 av 67 |
| fast klotter | 325 av 813 |
| möjlig orografi | 35 av 49 |
| övrigt | 87 av 1 064 (8 %) |

Totalt står 1 087 av 2 874 kandidater kvar. Den låga andelen för "övrigt" visar att den klassen mest är vädret på enstaka dagar.

## Förslag till filtret i uppgift 4

1. **En klotterkarta som räknas en gång** på träningsdagarna, eller bättre på ett längre arkiv: per ruta `f_torr` minus omgivningen, `dagar_torr30`, `f_iso`, `tex` och `d5`. Den ska ge en sannolikhet för klotter, inte en mask. Ekofrekvensen eller stillheten får inte ingå ensam, eftersom båda är höga i fjällen.
2. **En dynamisk kontroll i varje cykel**, bara på rutor där kartan säger klotter:
   - Ta bort ekot om det är isolerat, alltså lite eko inom cirka 20 km.
   - Ta bort ekot om det har hög textur mot grannarna, eller om det står still fast rörelsen är tydlig och omgivningen är torr.
   - Behåll ekot om omgivningen inom 20 till 40 km har regn och vinden går mot sluttningen (lyftet ur rörelsen och GLO-90).
   - Det billiga är fönster med `uniform_filter`, rörelsefältet som redan räknas, och gradienten ur höjdmodellen.
3. **Vindkraft**: använd inte förteckningen över verk som mask. Använd den som förhandssannolikhet tillsammans med blinkandet (`flip`, `d5`), eftersom bara en del parker syns.
4. **Ekrar**: rätta de 29 ekrarna som återkommer, som azimutsektorer per radar, genom att jämföra med grannsektorerna. Solstrålar och tillfälliga ekrar behöver en test bild för bild: en smal azimut med eko som sträcker sig radiellt och följer solens azimut. Det byggdes inte här.
5. Domaren ska avgöra. Terrängens mått, mätare över 400 m och på lovartsidan, är de som kan bli sämre om filtret tar orografin.

## Det som inte blev gjort

- Satellitens molnmask hämtades inte. Testen bild för bild för solstrålar och anaprop finns inte.
- Mätarnas torrhet bygger bara på p7 inom 25 km, och i fjällen och vid havet saknas mätare ofta. Där kan `f_torr` inte räknas.
- Typningen är en tumregel med fasta trösklar för att visa var och vad. Den är inte ett filter och är inte bedömd av domaren, som byggs i uppgift 2.

## Ändrade filer

- `experiments/analys/artefakter.py` (ny): räkningen per dag.
- `experiments/analys/karta.py` (ny): sammanställningen, typningen, ekrarna och bilderna.
- Den här rapporten. Inget i `src/` ändrades, och `uv run pytest` gav 138 godkända.

Status: delvis
