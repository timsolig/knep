# 3 Domare: måtten, baslinjerna och facit för natten

## Vad jag gjorde

1. Läste rapport 1 och 2. Båda är klara (Status: klar) och lämnade inget halvfärdigt som domaren behöver; fallen (128 validering, 223 träning) och mätarna p7 och p14 finns.
2. Skrev `experiments/bortfall/domare.py` (systemens gränssnitt, baslinjerna, måtten, körningen, bootstrap och tabellen) och `tests/test_bortfall_domare.py` (20 tester på syntetiska data).
3. Provkörde på tre fall, körde sedan facit och de tre baslinjerna på alla 128 valideringsfall i bakgrunden med två processer.

## Hur domaren fungerar

Allt står också i docstringen överst i `domare.py`.

**Gränssnittet.** Ett system är en klass med `start(indata)` och `steg(k, indata)`, som returnerar analysen i mm/h för hela utsnittet. Domaren matar systemet bild för bild, så att det bara ser det som hade funnits i realtid:

- `start`: uppvärmningen (60 min riktig radar), hålet, avståndet till närmaste fungerande radar och fallets metadata.
- `steg(k)`: bortfallets bild k med radarn utanför hålet och NaN i hålet; MEPS för timmar som har börjat (körningen valdes i fall.py som den som fanns vid timmens början); regnmätare vars period slutade minst 60 min före bilden (så sent kommer de i realtid).
- Domaren använder bara hålet ur svaret. Utanför hålet sätts den riktiga radarn, så att ett system inte kan påverka sömmen genom att ändra radarn utanför. NaN i hålet räknas som 0 mm/h.
- Andra system laddas som `modul:Klass` (till exempel `kor mitt_system:Blandning`), med filen i `experiments/bortfall/`.

Ett test (`test_system_sees_no_truth_in_hole`) kontrollerar att systemet aldrig får facit i hålet eller mätare som inte har kommit.

**Bortfallet och åldern.** Fallets bilder går från 60 min före starten till slutet. Bilderna start ≤ t < slut saknas och har åldern 5, 10, ..., längden min, räknat som tid sedan senaste riktiga bilden (samma som `age` i `fill_gaps`). Bilden vid slutet är när radarn kommer tillbaka och bedöms inte. Åldersklasserna är halvöppna, (0, 30], (30, 90] och (90, 360] min. Med den indelningen släpper `fill_gaps` (`max_age` 90) pixlarna precis när klass 3 börjar, så **fylld och utjämnad är lika med hål i klassen 90 till 360 min**. Så fungerar driften, och domaren ändrar inte på det.

**Måtten.** Pixlarna som bedöms är hålet där radarn har data. Allt sparas som summor per fall och klass, så att det kan läggas ihop över dagar och dras om i bootstrap.

| Mått | Definition |
|---|---|
| FSS 1 och 5 mm/h, 10 och 30 km | Fönster 5 och 15 pixlar. Andelarna räknas med normaliserad faltning bara ur pixlarna i hålet, så att den riktiga radarn utanför hålet inte höjer FSS nära kanten. FSS = 1 − Σ(Pf − Po)² / Σ(Pf² + Po²), summerat över pixlar och bilder |
| CSI 0,5, 1 och 5 mm/h | träffar / (träffar + missar + falsklarm), summerat |
| volym | Σ system / Σ radar i hålet. Skillnaden mot baslinjen räknas på \|volym − 1\| |
| söm | I ett band två pixlar på var sida om hålets kant: medel av \|‖∇R_analys‖ − ‖∇R_radar‖\| i mm/h per pixel (centrala differenser), där analysen är systemet i hålet och radarn utanför. Pixlar utan radar räknas inte |
| söm skev | samma med tecken (positiv: brantare kant än radarn); bara beskrivande, ingen dom |
| MAE kvart, timme | Mätare i hålet (p14 och p7) vars hela period ligger i bortfallet: medelabsolutfel i mm mot mätaren, för systemet och, på egen rad, för radarn. Klass efter åldern vid periodens slut |

**Bootstrap.** Skillnaden system − baslinje (normalt `fylld`, alltså driften) per mått och klass, med 95 %-intervall från 2000 dragningar av dagarna med återläggning (fast frö). Fallen samma dag delar regn och är beroende, därför dagar och inte fall. Domen **bättre** eller **sämre** ges bara när hela intervallet ligger på ena sidan, och bara med minst 5 dagar.

**Baslinjerna.**

- `hal`: ingen utfyllnad.
- `fylld`: `composite.fill_gaps` som i drift. Tillståndet byggs upp över uppvärmningen; den förväntade täckningen börjar som andelen bilder med data under uppvärmningen (i drift ett glidande dygn, men hålets pixlar har data i uppvärmningen och får alltså 1, som i drift). Rörelsen räknas som i kedjan, `model.motion_field(analyser, 3, 3, 4)` på de senaste sju analyserna (med de utfyllda) och används i nästa steg, precis som `motion.npy` från förra cykeln i drift. Skillnad mot drift: rörelsen räknas på utsnittet runt hålet (150 km marginal), inte på hela Sverige, och utan OPERA och volymer (de går inte att simulera ärligt, rapport 1 och 2).
- `utjamnad`: samma med `smooth=True`. Rörelsen räknas på den visade (utjämnade) analysen, eftersom det är den som sparas och används av kedjan i drift.
- `facit`: radarn själv, bara för att kontrollera domaren (FSS och CSI 1, volym 1, söm 0).

**Testerna** (`tests/test_bortfall_domare.py`, 21 st): åldersklassernas gränser, fönsterbredderna, FSS (perfekt, disjunkt, växer med skalan, fönster 1 är pixelvis och stämmer med CSI-räkningen, opåverkad av fältet utanför hålet), CSI-räkningen, kantbandet, sömmen (0 för radarn, positiv för ett tomt hål, hoppar över pixlar utan radar), att NaN i hålet blir 0 och att systemet utanför hålet ignoreras, att summorna läggs ihop rätt, bootstrap (lika system ger ingen dom, en tydlig förbättring ger bättre, volymen räknas åt rätt håll, för få dagar ger ingen dom, fall samma dag blir en dag), och körningen på ett syntetiskt fall: facit ger perfekt (även mot mätarna), hål ger 0, fylld behåller stillastående regn till 90 min och släpper det sedan, mätarspärren och att systemet inte ser facit.

## En rättning under körningen: felaktiga mätarvärden

Första körningen gav en orimlig kontroll: radarn var knappt bättre än inget regn alls mot mätarna (MAE per kvart 1,23 mot 1,26 mm). Arkivet för p14 och p7 (`/data/bortfall/matare/`) har uppenbart felaktiga värden: station 22228110 har 180 mm per kvart (720 mm per timme) konstant i timmar, och station 2208802 ett värde på 498 071 mm. Över 20 mm per kvart finns 1451 värden, och nästan alla är sådana (mellan 10 och 20 mm bara 16). Domaren räknar därför inte mätarvärden under 0 eller över 30 mm per kvart och 60 mm per timme (`MATARE_MAX_MM`). Spärren gäller lika för alla system och radarn; den rör bara mätarkolumnerna. Jag avbröt körningen och körde om alla fyra system (facit, hål, fylld, utjämnad) med spärren. Systemen får fortfarande se de råa mätarvärdena i `indata.matare`; ett system som använder mätare måste själv rensa dem (bra att veta för uppgift 4 och 5).

## Siffror

<!-- TABELL -->

Status: delvis
