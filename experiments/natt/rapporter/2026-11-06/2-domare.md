# Uppgift 2: domaren för analysen

Uppgift 1 (artefakterna) var klar enligt sin rapport, så inget behövde göras om före den här uppgiften.

## Vad jag gjorde

`experiments/analys/domare.py` är domaren, med tester i `tests/test_analys_domare.py` (11 tester på syntetiska data). Kommandona:

    uv run python experiments/analys/domare.py kor A0 A1 [--del validering] [--dag ÅÅÅÅ-MM-DD] [--bit 0/2]
    uv run python experiments/analys/domare.py tabell A1 --mot A0

### Gränssnittet

Ett system är en klass med `namn`, `matare` (True om det använder regnmätarna) och `falt(dag, matare) -> (kvart, timme)`. Fälten är nederbörden i mm per kvart, (96, H, W), och per timme, (24, H, W), på radarns rutnät, med NaN där analysen saknar data. Kvart k slutar 00:15 + 15k min och timme h slutar 01:00 + h timmar (UTC), som mätarnas tidsstämplar (de anger periodens slut, som i `bias.py` och bortfallsdomaren). `dag` (klassen `Dag`) har mätarna för dagen, höjden och lovartmasken; `matare` är `None` för system utan mätare och annars de mätare systemet får se.

### Korsvalideringen

- Rutnätet delas i block om 100 km (50 rutor). Varje block hör till en av fem grupper, grupp = (blockrad + 2 · blockkolumn) mod 5, så att två block som gränsar till varandra aldrig hör till samma grupp. Det ger 30 till 50 mätare per grupp.
- Ett system med mätare körs en gång per grupp k och får bara mätarna utanför gruppen **och mer än 25 km från den** (`Dag.training`), så att en grannmätare på andra sidan blockgränsen inte avslöjar svaret.
- Fältet som bedöms sätts ihop ruta för ruta: rutorna i grupp k tas ur körningen som inte såg grupp k (`run_system`). Alla mått räknas sedan på det sammansatta fältet, även kartmåttet för falska ekon.
- System utan mätare (A0, A1) körs en gång, och det sammansatta fältet är då fältet självt. De bedöms alltså på samma mätare och grupper.
- Testet `test_cross_validation_hides_the_judged_group` kontrollerar med ett spionsystem att ingen körning ser en mätare i gruppen eller inom 25 km från den, och att varje grupps rutor kommer ur rätt körning.

### Måtten

Per dag sparas summor (antal, summor, träffar, missar, falsklarm, FSS-termer, hopp) per upplösning och delmängd i `/data/analys/domare/<system>/<dag>.json`. Måtten för flera dagar och för varje bootstrapdragning räknas ur summorna, så att dagar med mycket regn väger som de ska.

- **Mängden**: kvoten summa(analys) / summa(mätare); samma kvot för perioder där mätaren har över 1, 5 och 10 mm; MAE i mm per period.
- **Träffen**: CSI vid 0,5, 1 och 5 mm per period i mätarens ruta. FSS mot punkterna: P är andelen rutor över tröskeln i ett fönster om 11 × 11 rutor (22 km) kring mätaren, O är 0 eller 1 för mätaren, och FSS = 1 − Σ(P − O)² / (ΣP² + ΣO²).
- **Falska ekon**: andelen perioder med analyserat regn (över 0,5 mm per timme, för kvarten 0,125 mm, alltså samma intensitet) vid mätare som visar 0 mm, och samma där alla mätare inom 25 km visar 0 mm. Dessutom per dag antalet rutor med eko (över 0,5 mm) i mer än hälften av de torra timmarna, för rutor med minst 6 torra timmar (torr = minst en p7-mätare inom 25 km, och alla visar 0).
- **Terrängen**: alla mått ovan för mätare över 400 m (GLO-90 i mätarens ruta) och för mätartimmar på lovartsidan. Lovart är när rörelsen uppför den utjämnade terrängen (Gauss 10 km) är minst 3 m per 5 min, och rutan ligger i fjällen (höjden utjämnad med Gauss 20 km över 300 m) eller på sydsvenska höjdområdet (lat 56,5 till 58,5, lon 13,3 till 16,2, utjämnad höjd över 120 m). Rörelsen är timmens medel av kedjans rörelsefält ur radarn; det är samma för alla system, så delmängden beror inte på systemet.
- **Hoppen mellan kvartarna**: för timmar där mätaren har alla fyra kvartarna och någon av mätaren och analysen har regn, Σ|kvart(k) − kvart(k − 1)| för analysen delat med samma summa för mätaren. 1 betyder att analysen hoppar lika mycket som mätaren.
- **Skillnaden mot en baslinje**: dagarna dras med återläggning 2000 gånger med fast frö, summorna läggs ihop och måtten räknas om för båda systemen på samma dragning. Skillnaden redovisas som skillnad i *godhet*, där större alltid är bättre: +Δ för CSI och FSS, −Δ för MAE och falska ekon, och för kvoterna −(|ln kvot| − |ln kvot_bas|), så att det är avståndet till 1 som räknas. 95 %-intervallet är 2,5 och 97,5 percentilerna.
- **Domen** (`verdict`): bättre bara om något mått för mängd eller träff (kvart eller timme, alla mätare) har intervallet helt över 0, och inget mått för falska ekon (alla mätare och kartmåttet) eller för mängd, träff och falska ekon i terrängens delmängder har intervallet helt under 0. Hoppen redovisas men ingår inte i domen, eftersom uppdraget bara kräver att de inte är större än mätarnas.

### Mätarna

`p7.npz` (timme) och `p14.npz` (kvart) filtreras på dagens perioder direkt när filen läses. **Båda har orimliga värden** (största värde 498 071 mm), så värden under 0 eller över 100 mm per timme och 60 mm per kvart tas bort. Bortfallsdomaren använder 60 och 30 mm; skillnaden påverkar bara de extremt få värdena där emellan. Mätarnas tid räknas om till period och en rad per station och period behålls.

### Baslinjerna

`Radardag` läser dagens bilder från 23:30 dagen före till 24:00 och räknar kedjans rörelsefält (`motion_field` på bilderna t − 30, t − 15 och t, steg 4, som `Chain` med gap 3) **var 15:e minut** i stället för var 5:e minut som i drift, för att hinna. Rörelsen sparas glest (var 4:e ruta, float16) i `/data/analys/domare/rorelse/` och interpoleras bilinjärt upp, vilket är samma sak som kedjan gör med steg 4. Ett intervall använder senaste rörelsefältet, som drift.

- **A0**: SMHI:s komposit med den lagrangeska utfyllnaden vid bortfall (`composite.fill_gaps`, utan reserverna OPERA och volymer, som drift utan `--fallback`) och utan volymkorrektion, eftersom bias-v1 inte är släppt. Varje bild gäller de fem minuterna före den.
- **A1**: `knep.analys.a1.interval_mean` på A0:s bilder längs rörelsen, en tid per minut.
- Kvart och timme är medlet av intervallen gånger periodens längd, om minst två tredjedelar av intervallen har data.

Provkörningen på 2023-08-08 tog 2 min för A0 och 5 min för A1 med en process. Den ingår i valideringen (2023-08-08 är en valideringsdag).

Hela körningen på de 16 valideringsdagarna tog cirka 1 h 45 min med två processer, 11 till 19 min per dag och process (A1 är den dyra delen, 8 till 14 min). Mätarna per dag: cirka 3 200 till 3 600 timvärden och 11 000 till 12 600 kvartsvärden. Underlaget ligger i `/data/analys/domare/` (90 MB, varav rörelsefälten 80 MB). /data har 5,8 GB ledigt.

### En rättning av domaren under körningen

Den första tabellen (14 dagar) flaggade A1 som sämre i "kvot > 5 mm" för mätare över 400 m, med intervallet −0,200 till −0,200. Ett intervall som är en punkt betyder att måttet bygger på en eller ett par händelser på en enda dag: varje bootstrapdragning som har dagen ger samma värde. Det säger inget om systemet. Domaren räknar därför nu för varje mått hur många dagar som har underlag i nämnaren (kolumnen `dagar` i tabellerna), och **ett mått bedöms bara om underlaget kommer från minst 5 dagar** (`MIN_DAYS`). Det gäller alla system lika och ändrar inga summor. Domen redovisas både med och utan kravet (`dom_utan_underlagskrav` i tabellfilen), och baslinjerna räknades om (det är bara tabellen som räknas om, summorna per dag är oförändrade). Testet `test_metric_with_one_day_of_support_is_not_judged` täcker regeln.

Ett tekniskt fel rättades också: båda processerna dödades av minnet (kod 137) när nästa dag lästes, eftersom förra dagens bilder fortfarande låg i minnet. Nu släpps de mellan dagarna, och de dagar som redan var klara hoppades över vid omstarten.

## Resultaten: A1 mot A0 på valideringen (16 dagar)

Skillnaden är i godhet, där större alltid är bättre (se Måtten). Intervallen är 95 % från bootstrap över dagarna. `dagar` är antalet dagar med underlag. Hela tabellen med alla delmängder finns i `/data/analys/domare/tabell_A1_mot_A0_validering.json` och skrivs ut med `domare.py tabell A1 --mot A0`.

**Kvart, alla mätare**

| mått | A1 | A0 | skillnad i godhet (95 %) | dagar |
|---|---|---|---|---|
| kvot summa | 0,824 | 0,825 | −0,001 (−0,008 till +0,004) | 16 |
| kvot > 1 mm | 0,466 | 0,468 | −0,004 (−0,019 till +0,019) | 15 |
| MAE (mm) | 0,067 | 0,069 | **+0,003 (+0,002 till +0,004)** | 16 |
| CSI 0,5 | 0,303 | 0,287 | **+0,015 (+0,009 till +0,023)** | 16 |
| CSI 1 | 0,196 | 0,179 | **+0,017 (+0,006 till +0,027)** | 16 |
| CSI 5 | 0,064 | 0,060 | +0,004 (+0,000 till +0,005) | 6 |
| FSS 0,5 | 0,486 | 0,481 | **+0,005 (+0,002 till +0,008)** | 16 |
| FSS 1 | 0,333 | 0,327 | +0,006 (−0,000 till +0,012) | 16 |
| FSS 5 | 0,067 | 0,077 | −0,010 (−0,018 till −0,000) | 15 |
| falskt vid torr mätare | 0,025 | 0,026 | +0,001 (+0,000 till +0,001) | 16 |
| falskt där allt inom 25 km är torrt | 0,024 | 0,025 | +0,001 (+0,000 till +0,001) | 16 |
| hopp, kvot mot mätarna | 0,809 | 0,884 | −0,089 (−0,109 till −0,003) | 16 |

**Timme, alla mätare**

| mått | A1 | A0 | skillnad i godhet (95 %) | dagar |
|---|---|---|---|---|
| kvot summa | 0,889 | 0,890 | −0,001 (−0,007 till +0,006) | 16 |
| kvot > 1 mm | 0,714 | 0,716 | −0,004 (−0,012 till +0,006) | 16 |
| kvot > 5 mm | 0,494 | 0,499 | −0,009 (−0,030 till +0,031) | 11 |
| MAE (mm) | 0,228 | 0,233 | **+0,005 (+0,003 till +0,007)** | 16 |
| CSI 0,5 | 0,528 | 0,520 | **+0,008 (+0,005 till +0,013)** | 16 |
| CSI 1 | 0,429 | 0,423 | **+0,006 (+0,002 till +0,012)** | 16 |
| CSI 5 | 0,169 | 0,160 | +0,009 (−0,005 till +0,036) | 16 |
| FSS 0,5 | 0,725 | 0,723 | **+0,003 (+0,002 till +0,004)** | 16 |
| FSS 1 | 0,635 | 0,634 | +0,001 (−0,001 till +0,002) | 16 |
| falskt vid torr mätare | 0,010 | 0,010 | +0,001 (+0,000 till +0,001) | 16 |
| falskt där allt inom 25 km är torrt | 0,009 | 0,010 | +0,001 (+0,000 till +0,002) | 16 |

**Terrängen** (det som behövs för domen och det som är tydligt)

| delmängd | mått | A1 | A0 | skillnad i godhet (95 %) | dagar |
|---|---|---|---|---|---|
| timme, över 400 m | kvot summa | 0,505 | 0,524 | −0,036 (−0,154 till +0,042) | 16 |
| timme, över 400 m | MAE | 0,169 | 0,177 | +0,008 (+0,002 till +0,019) | 16 |
| timme, över 400 m | CSI 0,5 | 0,317 | 0,302 | +0,015 (+0,003 till +0,029) | 15 |
| timme, över 400 m | FSS 5 | 0,267 | 0,284 | −0,018 (−0,028 till +0,000) | 14 |
| timme, lovart | **kvot summa** | 0,653 | 0,671 | **−0,028 (−0,051 till −0,006)** | 16 |
| timme, lovart | MAE | 0,238 | 0,243 | +0,006 (+0,002 till +0,010) | 16 |
| timme, lovart | CSI 0,5 | 0,472 | 0,472 | −0,000 (−0,017 till +0,013) | 16 |
| kvart, lovart | **kvot summa** | 0,592 | 0,604 | **−0,020 (−0,039 till −0,001)** | 16 |
| kvart, lovart | CSI 1 | 0,204 | 0,186 | +0,018 (+0,003 till +0,041) | 13 |

**Kartmåttet**: rutor med eko i mer än hälften av de torra timmarna, medel per dag: A1 40,4 och A0 36,6, skillnad i godhet −3,9 (−9,5 till +1,0).

**Domen**: A1 räknas **inte** som bättre än A0. A1 är bättre i MAE, CSI 0,5, CSI 1 och FSS 0,5, både per kvart och per timme, men sämre i summakvoten på lovartsidan (kvart och timme) med intervallet helt på fel sida. Utan kravet på 5 dagar flaggas också "kvot > 5 mm" och "> 10 mm" över 400 m, med 1 till 3 dagars underlag.

### Svaren på frågorna i uppgiften

- **Mängden**: A1 är inte sämre än A0 för alla mätare. Summakvoten är densamma (0,824 mot 0,825 per kvart och 0,889 mot 0,890 per timme), och MAE är lite bättre med intervallet helt över 0. Kvoterna för perioder över 1 och 5 mm skiljer sig inte.
- **Falska ekon**: A1 är inte sämre vid mätarna. Andelen falskt eko vid torra mätare är lite lägre för A1 (intervallet ligger på den bättre sidan eller precis vid 0). Kartmåttet går åt andra hållet: A1 har i medel 3,9 fler rutor per dag med eko i mer än hälften av de torra timmarna. Intervallet går över 0, så det räknas inte som sämre. Det är ändå väntat: A1 flyttar fast klotter fram och tillbaka längs rörelsen och smetar ut det över fler rutor. Det talar för att artefakterna ska tas bort i A0 innan A1 räknas (uppgift 4).
- **Träffen per kvart**: ja, A1 är bättre. CSI 0,5 går från 0,287 till 0,303 och CSI 1 från 0,179 till 0,196, och FSS 0,5 blir bättre. Båda har intervallet helt över 0. Vinsten är ungefär dubbelt så stor per kvart som per timme, vilket är vad interpoleringen ska ge: pärlbanden syns mest i korta summor. FSS 5 per kvart är däremot lite sämre (0,067 mot 0,077, intervallet slutar vid 0). Interpoleringen jämnar ut de starkaste kärnorna.
- **Terrängen**: A1 ger **2 till 3 % mindre regn på lovartsidan**. Underskottet kommer mest från 2023-08-08 (Hans, 197 mm mot 212 mm vid lovartmätarna, som hade 314 mm) och 2021-10-20 (77 mot 84 mm, mätarna 81 mm). Det är det uppdraget varnar för: regn som står still vid en sluttning flyttas av interpoleringen längs rörelsefältet, framåt ur den första bilden och bakåt ur den andra, så att toppen vid mätaren sjunker. Över 400 m är tendensen densamma (kvoten 0,505 mot 0,524) men intervallet går över 0.
- **Hoppen**: varken A0 eller A1 hoppar mer än mätarna mellan kvartarna (kvoten 0,88 och 0,81, under 1). Det är väntat, eftersom en ruta om 2 km är ett medel över en yta och mätaren är en punkt. A1 hoppar mindre än A0.

### Vad siffrorna säger om analysen i stort

- Radarn ger 82 till 89 % av mätarnas mängd för alla mätare, men bara **cirka 50 % över 400 m** och 60 till 67 % på lovartsidan. Det är strålen som går över den låga nederbörden i fjällen. Där har A2 (rättningen mot mätarna) mest att vinna, och det är också där ett filter mot artefakter lättast gör skada.
- Kvoten för perioder över 5 och 10 mm är 0,3 till 0,5: de kraftiga mätarvärdena underskattas mycket. Det beror delvis på att de väljs efter mätaren, så att mätarens slumpfel drar upp nämnaren, och delvis på ytmedlet.

## Begränsningar och det som skiljer sig från uppdraget

- **"Alla mätare inom 25 km torra" skiljer sig knappt från "mätaren torr"** (till exempel 2 026 mot 2 061 torra timmar 2023-08-08). Nätet är glest, cirka 200 stationer, så de flesta mätare har ingen granne inom 25 km. Måttet finns kvar enligt uppdraget men tillför lite. Kartmåttet är det som ser fast klotter utanför mätarna.
- **Kvoterna över 5 och 10 mm** har underlag från 1 till 11 dagar och bedöms oftast inte med kravet på 5 dagar.
- **Rörelsen räknades var 15:e minut** i stället för var 5:e som i drift. Fältet med gap 3 ändras långsamt, men A1 här är inte exakt A1 i drift.
- **Lovartsidan bygger på radarns rörelsefält**, som är molnens rörelse och inte vinden vid marken. Regionen (fjällen över 300 m i utjämnad höjd, sydsvenska höjdområdet som en ruta i lat och lon) är en tumregel och inte vald på data.
- **FSS mot mätarna** är en variant mot punkter (andelen i ett fönster mot 0 eller 1 vid mätaren), inte FSS mellan två fält. Den kan bara jämföra system med varandra.
- **A2 finns inte**, så korsvalideringen har bara prövats med spionsystemet i testerna och inte med ett riktigt system som använder mätare.
- Träningsdagarna kördes inte. De behövs först när något ska väljas eller tränas (uppgift 4 och A2), och `domare.py kor A0 A1 --del traning` gör det på cirka 2,5 h med två processer.

## Ändrade filer

- `experiments/analys/domare.py` (ny): domaren, A0 och A1, kommandona `kor` och `tabell`.
- `experiments/analys/domare_prov.py` (ny): provkörningen som mätte tiden för rörelsefältet och ett A1-intervall och såg mätarnas orimliga värden.
- `tests/test_analys_domare.py` (ny): 12 tester. Bland dem: att testdelen aldrig läses, grupperna, ett perfekt system, falska ekon, NaN, terrängens delmängder, att korsvalideringen döljer gruppen och bufferten, att ett system utan mätare körs en gång, summorna ur intervallen, lovartmasken, bootstrap och domen samt kravet på underlag.
- Inget i `src/` ändrades. `uv run pytest` ger 150 godkända.
- Den här rapporten.

## Nästa steg

- Uppgift 4 (filtret mot artefakterna): bedöm med `domare.py`, och lägg filtret som ett nytt system i `SYSTEMS`. Terrängens mått över 400 m och på lovartsidan är de som avgör om filtret tar orografin.
- A1 bör inte flytta det som står still vid terrängen. En billig väg är att låta interpoleringen använda en mindre rörelse där lyftet är stort, som `Chain.stay` gör i prognosen. Då försvinner underskottet på lovartsidan. Domaren kan bedöma det direkt.
- A2: ett system med `matare = True`. Underlaget per dag finns redan i `Dag.training(k)`.
- Kör träningsdagarna med `--del traning` innan något väljs.

Status: klar
