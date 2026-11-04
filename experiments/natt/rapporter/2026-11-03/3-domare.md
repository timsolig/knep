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

Valideringen: 128 fall på 16 dagar. Körtid med två processer: fylld 25 min, utjämnad 24 min, hål 7 min, facit 6 min. Skillnaden är mot `fylld` (driften), med 95 %-intervall från bootstrap över dagarna. **Fetstil** betyder att hela intervallet ligger på ena sidan. FSS och CSI: högre är bättre. Volymen visas som Σ system / Σ radar, men skillnaden räknas på |volym − 1|. Söm och MAE: lägre är bättre. MAE i mm per kvart respektive timme. Raden "radarn mot mätarna" är radarns egen MAE mot samma mätare, alltså golvet för kontrollen.

### Ålder 0 till 30 min (128 fall, 768 bilder, 16 dagar)

| system | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm | söm skev | MAE kvart | MAE timme |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fylld | 0,896 | 0,948 | 0,765 | 0,880 | 0,682 | 0,620 | 0,360 | 1,000 | 0,120 | −0,005 | 0,091 |  |
| hal | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,151 | −0,035 | 0,118 |  |
| utjamnad | 0,888 | 0,941 | 0,753 | 0,862 | 0,684 | 0,626 | 0,369 | 1,000 | 0,115 | −0,038 | 0,090 |  |
| facit | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 0,000 | 0,000 | 0,089 |  |
| (radarn mot mätarna) |  |  |  |  |  |  |  |  |  |  | 0,089 |  |
| hal − fylld | −0,896 [−0,925; −0,856] **sämre** | −0,948 [−0,969; −0,919] **sämre** | −0,765 [−0,811; −0,687] **sämre** | −0,880 [−0,918; −0,802] **sämre** | −0,682 [−0,731; −0,623] **sämre** | −0,620 [−0,673; −0,554] **sämre** | −0,360 [−0,407; −0,289] **sämre** | 1,000 [0,957; 0,999] **sämre** | 0,031 [0,018; 0,043] **sämre** | −0,029 [−0,071; 0,004] | 0,027 [−0,002; 0,071] |  |
| utjamnad − fylld | −0,008 [−0,012; −0,005] **sämre** | −0,008 [−0,012; −0,005] **sämre** | −0,013 [−0,019; −0,008] **sämre** | −0,018 [−0,025; −0,013] **sämre** | 0,002 [−0,002; 0,005] | 0,007 [0,003; 0,010] **bättre** | 0,009 [0,002; 0,013] **bättre** | 0,000 [−0,002; 0,002] | −0,005 [−0,013; 0,000] | −0,033 [−0,056; −0,015] | −0,001 [−0,002; 0,000] |  |
| facit − fylld | 0,104 [0,075; 0,144] **bättre** | 0,052 [0,031; 0,081] **bättre** | 0,235 [0,189; 0,313] **bättre** | 0,120 [0,082; 0,198] **bättre** | 0,318 [0,269; 0,377] **bättre** | 0,380 [0,327; 0,446] **bättre** | 0,640 [0,593; 0,711] **bättre** | −0,000 [−0,043; −0,001] **bättre** | −0,120 [−0,191; −0,067] **bättre** | 0,005 [−0,002; 0,013] | −0,002 [−0,009; 0,005] |  |

### Ålder 30 till 90 min (102 fall, 1056 bilder, 16 dagar)

| system | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm | söm skev | MAE kvart | MAE timme |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fylld | 0,727 | 0,818 | 0,501 | 0,680 | 0,516 | 0,440 | 0,199 | 1,123 | 0,141 | 0,017 | 0,116 | 0,312 |
| hal | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,149 | −0,023 | 0,138 | 0,321 |
| utjamnad | 0,725 | 0,801 | 0,496 | 0,635 | 0,528 | 0,461 | 0,209 | 1,130 | 0,138 | −0,035 | 0,113 | 0,301 |
| facit | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 0,000 | 0,000 | 0,105 | 0,272 |
| (radarn mot mätarna) |  |  |  |  |  |  |  |  |  |  | 0,105 | 0,272 |
| hal − fylld | −0,727 [−0,794; −0,626] **sämre** | −0,818 [−0,880; −0,723] **sämre** | −0,501 [−0,613; −0,336] **sämre** | −0,680 [−0,780; −0,463] **sämre** | −0,516 [−0,590; −0,424] **sämre** | −0,440 [−0,513; −0,346] **sämre** | −0,199 [−0,284; −0,118] **sämre** | 0,877 [0,771; 0,948] **sämre** | 0,008 [−0,010; 0,023] | −0,040 [−0,085; −0,007] | 0,022 [−0,011; 0,068] | 0,008 [−0,073; 0,108] |
| utjamnad − fylld | −0,002 [−0,011; 0,005] | −0,017 [−0,026; −0,009] **sämre** | −0,005 [−0,042; 0,020] | −0,046 [−0,090; −0,013] **sämre** | 0,012 [0,005; 0,019] **bättre** | 0,020 [0,014; 0,027] **bättre** | 0,010 [−0,012; 0,025] | 0,006 [−0,001; 0,014] | −0,003 [−0,009; 0,001] | −0,052 [−0,091; −0,027] | −0,004 [−0,008; −0,001] **bättre** | −0,011 [−0,065; 0,009] |
| facit − fylld | 0,273 [0,206; 0,374] **bättre** | 0,182 [0,120; 0,277] **bättre** | 0,499 [0,387; 0,664] **bättre** | 0,320 [0,220; 0,537] **bättre** | 0,484 [0,410; 0,576] **bättre** | 0,560 [0,487; 0,654] **bättre** | 0,801 [0,716; 0,882] **bättre** | −0,123 [−0,229; −0,052] **bättre** | −0,141 [−0,223; −0,085] **bättre** | −0,017 [−0,032; −0,005] | −0,011 [−0,024; −0,000] **bättre** | −0,041 [−0,125; 0,014] |

### Ålder 90 till 360 min (74 fall, 1824 bilder, 16 dagar)

| system | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm | söm skev | MAE kvart | MAE timme |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fylld | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,128 | −0,017 | 0,208 | 0,815 |
| hal | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,128 | −0,017 | 0,209 | 0,900 |
| utjamnad | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,128 | −0,017 | 0,205 | 0,813 |
| facit | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 0,000 | 0,000 | 0,152 | 0,575 |
| (radarn mot mätarna) |  |  |  |  |  |  |  |  |  |  | 0,152 | 0,575 |
| hal − fylld | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0,002 [−0,004; 0,004] | 0,085 [0,032; 0,137] **sämre** |
| utjamnad − fylld | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | −0,002 [−0,006; −0,000] **bättre** | −0,002 [−0,010; 0,020] |
| facit − fylld | 1,000 **bättre** | 1,000 **bättre** | 1,000 **bättre** | 1,000 **bättre** | 1,000 **bättre** | 1,000 **bättre** | 1,000 **bättre** | −1,000 **bättre** | −0,128 [−0,197; −0,077] **bättre** | 0,017 [−0,004; 0,038] | −0,056 [−0,104; −0,001] **bättre** | −0,240 [−0,408; 0,028] |

I klassen 90 till 360 min är fylld och utjämnad exakt lika med hål i radarfälten (intervallen [0; 0] förkortade till 0), eftersom `fill_gaps` släpper pixlarna efter 90 min. Mätarkolumnerna skiljer sig ändå något, eftersom en timsumma som slutar vid ålder 95 till 150 min också täcker bilder som var utfyllda.

Tabellen kommer ur `uv run python experiments/bortfall/domare.py tabell fylld hal utjamnad facit --mot fylld`; summorna per fall ligger i `experiments/bortfall/resultat/validering/{fylld,hal,utjamnad,facit}.json`.

## Vad siffrorna säger

- **Driftens utfyllnad är värdefull de första 90 minuterna** och slår hål med marginal i alla radarmått (FSS 1 mm på 30 km 0,95 de första 30 min och 0,82 för 30 till 90 min). Efter 90 min finns ingenting; där kan alla nya system bara vinna mot baslinjen, och det är troligen där det mesta finns att hämta (1824 av 3648 bedömda bilder ligger i den klassen).
- **Volymen växer med åldern i den flyttade analysen**: 1,00 de första 30 min, 1,12 för 30 till 90 min. Regn utanför hålet förs in i hålet, och regnet i hålet försvinner inte när det skulle ha dött ut.
- **Utjämnad är inte bättre än fylld.** Den vinner lite i CSI 1 mm (+0,007 och +0,020) och i MAE mot mätarna 30 till 90 min (−0,004 mm per kvart), men förlorar i FSS på alla skalor de första 30 min och vid 30 km för 30 till 90 min (−0,046 för 5 mm). Sömmen är inte säkert bättre. Det finns alltså inget skäl i domaren att slå på `smooth` i driften.
- **Sömmen**: hål ger en brantare kant än fylld de första 30 min (+0,031), men för 30 till 90 min är fylld inte säkert bättre än hål. Den flyttade analysen blir alltså kantig mot den riktiga radarn ganska snart.
- **Mätarna** stämmer med radarn: radarns MAE är lägst, fylld ligger nära radarn de första 30 min (0,091 mot 0,089 mm per kvart) och glider isär med åldern. Mätarkolumnerna har breda intervall; det är få mätare i hålen, så de duger som kontroll och inte som avgörande mått.

## Begränsningar och sådant att veta

- **Volymintervallet är skevt nära 1.** Skillnaden räknas på |volym − 1|, och ett percentilintervall för ett absolutbelopp är förskjutet bort från noll när volymen ligger nära 1 (se facit − fylld 0 till 30 min: punkten −0,000 ligger utanför intervallet [−0,043; −0,001]). En dom om volymen när båda systemen ligger nära 1 ska därför läsas försiktigt. Jag har inte ändrat det; ett alternativ vore att räkna intervallet på volymen själv och döma efter riktningen mot 1.
- Rörelsen räknas på utsnittet och inte på hela Sverige; OPERA och volymer är inte med (rapport 1 och 2). `fylld` är alltså driften utan reservlager, vilket är rätt jämförelse för simulerade svenska bortfall.
- Alla måtten gäller analysen i hålet. **Prognosen efteråt** (kedjan körd när radarn kommer tillbaka) mäter domaren inte än; det var planerat till uppgift 6 och kan läggas till som en egen kolumn med samma bootstrap.
- MEPS saknas för de 16 fallen från 2019 (äldre rutnät); system som använder MEPS får klara sig utan där (`indata.meps` är tom).
- Systemen får de råa mätarvärdena, med felen ovan; de måste själva rensa dem.
- Provkörningens filer `experiments/bortfall/resultat/validering/*_prov3.json` räknades före mätarspärren och är inaktuella. Jag fick inte ta bort dem i natt (`rm` är inte tillåtet), så de ligger kvar ocommittade och kan tas bort.

## Filer

- `experiments/bortfall/domare.py` (nytt)
- `tests/test_bortfall_domare.py` (nytt, 21 tester)
- `experiments/bortfall/resultat/validering/{facit,fylld,hal,utjamnad}.json` (nya, summorna per fall och klass)
- `experiments/natt/rapporter/2026-11-03/3-domare.md`

Inga ändringar i `src/knep/`. `uv run pytest`: 89 passerade.

## Nästa steg

Uppgift 4 (MEPS i hålet) och 5 (inlärd blandning) skriver ett system som en klass med `start` och `steg` i `experiments/bortfall/` och kör

```sh
uv run python experiments/bortfall/domare.py kor min_modul:MinKlass --processer 2 --logg /data/bortfall/logg/<namn>.log
uv run python experiments/bortfall/domare.py tabell fylld hal min_modul:MinKlass --mot fylld
```

Baslinjerna behöver inte köras om så länge domaren inte ändras. Träna och välj parametrar på `--del traning` (fallen finns), och kör valideringen först när systemet är fryst. Det mesta finns att vinna efter 90 min, där driften inte har något alls, och i volymen för 30 till 90 min.

Status: klar
