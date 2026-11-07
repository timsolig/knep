# Uppgift 1: inventering av radarns artefakter

Före uppgiften fanns bara provet av behörigheterna (`prov.md`), så ingen tidigare uppgift var halvfärdig.

Rapporten skrevs i två försök. Försök 1 gjorde inventeringen per ruta och dag (avsnitten från "Vad jag gjorde" till "Förslag till filtret"). Försök 2 lade till testet bild för bild för solstrålar, fasta ekrar och anaprop, som saknades. Det står i avsnittet "Försök 2" längre ned, och förslaget till filtret har kompletterats där.

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
- **Solstrålar**: av ekrarna per dag ligger 82 av 904 (9 %) inom ±8° från solens azimut vid upp- eller nedgång. Det är vad slumpen ger (32°/360° = 9 %), så **daglig ekofrekvens räcker inte för att se solen**. Solstrålar varar några bilder och behöver hittas bild för bild. Det gjordes i försök 2 (se nedan), och där syns de tydligt.
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
4. **Ekrar**: rätta de 29 ekrarna som återkommer, som azimutsektorer per radar, genom att jämföra med grannsektorerna. Solstrålar och tillfälliga ekrar behöver en test bild för bild: en smal azimut med eko som sträcker sig radiellt och följer solens azimut. Den byggdes i försök 2; se punkt 6 och 7 nedan.
5. Domaren ska avgöra. Terrängens mått, mätare över 400 m och på lovartsidan, är de som kan bli sämre om filtret tar orografin.

## Försök 2: bild för bild (solstrålar, fasta ekrar, anaprop)

### Vad jag gjorde

`experiments/analys/bild.py dag` läser alla 288 bilder på var och en av de 44 dagarna (samma urval som ovan, `days()` med kontrollen mot testdagarna). Det tog cirka 2,5 min per dag med två processer. Utdata per dag ligger i `/data/analys/artefakter/bild_dag/<dag>.json`, 65 MB. `bild.py sammanstall` (koden i `bild_sammanstall.py`) skriver `/data/analys/artefakter/bild_tabell.json`. `bild_prov.py` är provkörningen som användes för att ställa in ekertestet.

- **Ekrar per bild**: för varje radar i `composite.RADARS` räknas andelen eko (R ≥ 0,1 mm/h) i strålar om 1° på 40 till 200 km avstånd, i fyra band om 40 km. En stråle räknas som eker om andelen eko är minst 0,4, om minst tre av de fyra banden har minst 0,25 (strålen är radiellt lång) och om medianen av strålarna 3 till 10° åt sidan är högst 0,1 (strålen är smal). Azimuten är rättad för meridiankonvergensen på rutnätet (EPSG:25833). Solens azimut och höjd räknas för bildens tid och radarns plats med NOAA:s förenklade formler.
- **Prickar per bild**: per radar inom 150 km räknas eko som är isolerade (under 3 % eko inom 42 km) och kantiga (texturen |dBZ − grannarnas medel| ≥ 8 dB). De räknas också utanför de kända klotterrutorna (`kandidat` på träningsdagarna och vindkraftsrutorna i `kartor.npz`, utvidgade en ruta). Det görs isolerade (`prickar_nya`) och kantiga oavsett isolering (`kantigt_nytt`), och var för sig under timmar då mätarna inom 25 km (p7) är torra.

Första provkörningen krävde andel ≥ 0,5 och ≥ 0,3 i alla fyra banden. Det gav 0 ekrar på 2019-03-08, eftersom en stråle om 1° bara täcker 9 till 33 rutor per band på 2 km-rutnätet. Därför sänktes trösklarna innan hela körningen startades.

### Solstrålar: tydliga, och bara när solen står vid horisonten

Totalt hittades 8 041 ekrar per bild. Andelen som ligger inom ±3° från solens azimut, per solhöjd:

| solhöjd | ekrar | nära solen | andel |
|---|---|---|---|
| under −5° | 2 754 | 44 | 1,6 % |
| −5 till 0° | 606 | 123 | **20 %** |
| 0 till 5° | 910 | 235 | **26 %** |
| 5 till 10° | 678 | 9 | 1,3 % |
| 10 till 20° | 1 164 | 26 | 2,2 % |
| 20 till 30° | 777 | 16 | 2,1 % |
| över 30° | 1 152 | 7 | 0,6 % |

Slumpen ger 7/360 = 1,9 %. Som kontroll räknades samma ekrar mot solens azimut förskjuten 20 till 40°, och det ger 1,4 %. **Solstrålarna finns alltså, och nästan bara när solen står mellan cirka −1 och +1°.** Då är var fjärde eker solen. Försök 1 såg dem inte, eftersom de varar 10 till 70 minuter och försvinner i dygnsfrekvensen.

22 händelser följer solen i minst tre bilder i rad: strålen flyttar sig med solens azimut, och solhöjden ligger hela tiden mellan −0,7 och +0,8°. Några exempel:

| radar | tid (UTC) | bilder | strålens azimut | solens azimut | del |
|---|---|---|---|---|---|
| sekrn | 2023-07-12 21:30 till 22:40 | 14 | 344 till 359° | 343 till 359° | träning |
| sekrn | 2023-07-12 22:55 till 23:50 | 12 | 2 till 15° | 3 till 16° | träning |
| sekrn | 2024-07-13 21:20 till 22:05 | 9 | 341 till 352° | 341 till 351° | validering |
| sekrn | 2024-07-13 23:25 till 23:55 | 7 | 9 till 17° | 10 till 17° | validering |
| sevax | 2019-03-17 15:15 till 15:40 | 6 | 243 till 247° | 243 till 248° | validering |
| seoer | 2022-12-20 08:40 till 09:00 | 5 | 150 till 155° | 152 till 156° | träning |
| sehem | 2024-07-13 02:15 till 02:25 | 3 | 45 till 48° | 46 till 48° | validering |
| sella | 2023-01-04 09:00 till 09:15 | 4 | 156 till 160° | 158 till 161° | träning |

Kiruna (sekrn) dominerar med 11 av de 22 händelserna. Vid midnattssolen står solen vid horisonten i timmar och vandrar genom norr. Strålarna är starka: andelen eko längs strålen är 0,7 till 0,94. Sevax 2019-03-17 hade solen på 11 till 14° och är undantaget. Den och seatv 2020-10-07, med solen på 23°, kan vara slump eller en högre elevation i kompositen.

### Fasta ekrar som återkommer bild för bild

Fasta ekrar är samma radar och azimut (±1°) på minst tre dagar. De starkaste:

| radar | azimut | dagar av 44 | träning / validering | bilder |
|---|---|---|---|---|
| sebaa | 134° | **34** | 23 / 11 | 712 |
| sebaa | 86 till 89° | 20 | 14 / 6 | 520 + 111 |
| seosd | 295 till 298° | 12 | 9 / 3 | 133 + 74 |
| seosd | 218 till 221° | 10 | 8 / 2 | 23 + 27 |
| sekaa | 193 till 203° | 8 | 4 / 4 | 30 + 23 |
| sehem | 120° och 134° | 7 och 7 | 2 / 5 och 5 / 2 | 215 och 203 |
| seoer | 338° | 6 | 5 / 1 | 16 |

Sebaa 134° och 85° stämmer med försök 1:s ekrar ur dygnsfrekvensen (132 till 133° och 84 till 85°), och seoer 338° stämmer med 336 till 339°. Sebaa 134° finns på tre av fyra dagar och är därmed den enskilt vanligaste artefakten i inventeringen. Sebaa har flest ekrar per bild (1 541), följt av sehem (991) och sekaa (800). Ekrarna från noand och nohfj, som syntes i dygnsfrekvensen, kommer knappt med här, eftersom bara en liten del av deras strålar ligger inne i rutnätet (nohfj har 24 ekrar). Många av de 8 041 ekrarna är regnband som råkar ligga radiellt. Det syns på att de inte återkommer.

### Anaprop: syns inte i de här dagarna

- **Isolerade kantiga prickar utanför de kända klotterrutorna** (`prickar_nya`): 18 timmar ligger långt över radarns vanliga nivå (minst 20 per bild och 8 MAD över medianen). 13 av dem är 2023-01-04 vid sekrn och sella i januarimörker, med prickar spridda över hela dygnet. Andelen av prickarna som ligger vid torra mätare är 0,27 till 0,48, mot 0,27 för alla prickar. Det talar inte tydligt för klotter. Det kan vara lätt snö i kall luft eller anaprop under en inversion; det går inte att avgöra utan mätare (de saknas där) eller satellit.
- **Kantiga ekon vid torra mätare** (`torr_kantigt_nytt`): 303 timmar ligger över radarns nivå (236 på träningsdagarna och 67 på valideringsdagarna). Fördelningen över lokal soltid är 0 till 3: 18, 3 till 6: 11, 6 till 9: 21, 9 till 12: 39, **12 till 15: 87, 15 till 18: 64**, 18 till 21: 38 och 21 till 24: 25. Dagarna är 2020-10-07, 2024-07-28, 2020-08-29 och 2020-07-24, alltså skurdagar. Medlet per bild har samma topp på sommaren: 22 kantiga torra ekon per bild kl. 12 till 15 mot 9 på natten. Anaprop borde ha sin topp på natten och morgonen, under inversioner. **Det här är alltså mest konvektiva skurar som mätarna inom 25 km inte har fångat**, och inte anaprop.

Det är en viktig varning för filtret och domaren. Att mätarna är torra inom 25 km är ett svagt tecken på klotter för små skurceller på sommaren. Kännetecknet `f_torr` fungerar för fast klotter, eftersom det räknas över många dagar, men som test i en enskild bild skulle det ta bort riktiga skurar. Det måste kombineras med rörelsen (skurar rör sig, klotter står still) eller begränsas till rutor där kartan redan säger klotter.

Över alla bilder är 0,2 % av ekona isolerade och kantiga. 58 % av dem ligger utanför de kända klotterrutorna, och 30 % av alla prickar ligger vid torra mätare, mot 6 % av allt eko.

### Tillägg till förslaget för filtret i uppgift 4

6. **Solstrålar** är billiga att ta bort i varje cykel. Gör testet bara när solen står mellan −1,5 och +1,5° vid en radar (det är någon timme om dagen, och flera timmar vid midnattssolen i norr). Ta bort strålen inom ±3° från solens azimut om den är smal och lång (eko längs strålen mot torrt åt sidorna, samma test som i `bild.py`). Det ger nästan inga falska larm: på andra solhöjder är andelen nära solen på slumpnivån.
7. **Fasta ekrar** (sebaa 134° och 86 till 89°, seosd 295 till 298° och 218 till 221°, sekaa 193 till 203°, sehem 120° och 134°, seoer 338°): en lista per radar som räknas på träningsdagarna. Ta bort ekot i sektorn bara när testet för en smal och lång stråle slår till i bilden, och inte i allmänhet, eftersom det regnar i sektorn också.
8. **Anaprop** kan inte motivera något filter på de här dagarna. Ett test som tar bort kantiga ekon vid torra mätare tar framför allt bort sommarens skurar. Ska anaprop sökas, behövs nätter med inversioner (klara sommarnätter och vinternätter) och satellitens molnmask.

## Det som inte blev gjort

- Satellitens molnmask hämtades inte. Körningen fick inte gå ut på nätet (curl mot EUMETSAT:s WMS nekades av behörighetsinställningarna), så det gick inte att se om EUMETSAT:s öppna produkter kan läsas utan konto. Det gör att varken prickarna 2023-01-04 eller de torra skurarna kan avgöras mot molnen.
- Ett test för anaprop med rörelsen per bild (står ekot still?) byggdes inte; försök 2 räknade bara textur, isolering och torra mätare per bild.
- Mätarnas torrhet bygger bara på p7 inom 25 km, och i fjällen och vid havet saknas mätare ofta. Där kan `f_torr` inte räknas.
- Typningen är en tumregel med fasta trösklar för att visa var och vad. Den är inte ett filter och är inte bedömd av domaren, som byggs i uppgift 2.

## Ändrade filer

- `experiments/analys/artefakter.py` (ny): räkningen per dag.
- `experiments/analys/karta.py` (ny): sammanställningen, typningen, ekrarna och bilderna.
- `experiments/analys/bild.py` (ny i försök 2): ekrar och prickar bild för bild.
- `experiments/analys/bild_sammanstall.py` (ny i försök 2): solen, de återkommande ekrarna och skurarna.
- `experiments/analys/bild_prov.py` (ny i försök 2): provkörningen av ekertestet.
- Den här rapporten. Inget i `src/` ändrades, och `uv run pytest` gav 138 godkända (även efter försök 2).

Allt under `/data/analys/artefakter/` tar cirka 300 MB, under gränsen på 1 GB, och /data har 5,9 GB ledigt.

## Nästa steg

- Uppgift 4: bygg filtret av klotterkartan (punkt 1 och 2), soltestet (punkt 6) och de fasta ekrarna (punkt 7), och låt domaren avgöra med terrängens mått.
- Hämta satellitens molnmask när nätet får användas, och sök anaprop på klara nätter.

Inventeringen som uppgiften beställde är gjord: kartorna per ruta, ekrarna, solstrålarna, havet, vindkraften, jämförelsen med höjdmodellen och förslaget till filtret. Satellitens molnmask saknas eftersom nätet var spärrat, och anaprop kunde inte påvisas i de här dagarna.

Status: klar
