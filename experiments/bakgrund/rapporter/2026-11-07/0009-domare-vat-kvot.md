# 0009 Analysens domare med kvoten för våta perioder

Kort: Domaren har nu `kvot våt` (Σanalys/Σmätare där mätaren har regn) i stället för summakvoten i domens mängdgrupp, med den gamla regeln kvar bredvid. På hela valideringen (16 dagar) ändras ingen av de fyra domarna: A2T slår fortfarande A0 och A1 utan sämre mått (kvot våt per timme över 400 m 0,614 mot A0 0,467 och A1 0,455), F4 godkänns fortfarande mot A0 (bara FSS bättre, kvoterna exakt som A0), och A1 fälls fortfarande mot A0, nu av `kvot våt` per timme på lovartsidan (0,598 mot 0,609, −0,020, −0,038 till −0,002) i stället för av summakvoten per kvart och timme där.

## Beslutet och vad som ändrades i domaren

Användaren beslutade 2026-11-07 (`MAL.md`, Användarens beslut, punkt 3) att summakvoten ska kompletteras med kvoten för perioder då mätaren har regn, att baslinjerna A0, A1, A2T och F4 körs om och att den gamla kvoten står kvar bredvid. Skälet är att summakvoten Σa/Σg över alla perioder också räknar eko vid torra mätare som mängd. Så länge radarn i stort är för torr belönar den då för höga toppar och falska ekon (det fällde F1 över 400 m och gav A1 dess "underskott" på lovartsidan). Det här är en av användaren beslutad ändring av domaren, inte en ändring för att något system ska se bättre ut.

`experiments/analys/domare.py`:

- `_empty` och `_accumulate`: nya summor `saw` = Σa och `sgw` = Σg över perioder där mätaren har g > 0, för alla delmängder (alla, over400, lovart) och båda upplösningarna.
- `metrics`: måttet `kvot våt` = saw/sgw, bättre är nära 1. `_support`: nämnaren är `sgw`. Dagfiler utan `saw` och `sgw` (de gamla) ger NaN för `kvot våt` och bedöms inte; `_sum` och räkningen av dagar tål att summorna saknas.
- `GROUPS["mängd"]`: `kvot våt` ersätter `kvot summa` i domen. `GROUPS_GAMMAL` är den gamla gruppen. `kvot summa` står kvar i alla tabeller.
- `verdict(tab, min_days, regel="ny")`: `regel="gammal"` ger domen med summakvoten som förut. `cmd_tabell` skriver båda domarna (med och utan underlagskravet) och tabellfilens json har `dom`, `dom_utan_underlagskrav`, `dom_gammal_regel` och `dom_gammal_regel_utan_underlagskrav`.
- `OUT` är nu `/data/analys/domare_v2/` (valet `--ut` i `domare.py`, `filter.py` och `a2.py`, och `set_out`). `OUT_V1` = `/data/analys/domare/` står orörd. Rörelsefälten läses och sparas som förut i `/data/analys/domare/rorelse/` (`RORELSE`), eftersom de är desamma.
- Kommandot `kontroll`: jämför dagfilerna i `OUT` med de gamla i `OUT_V1` (`compare_old`): varje gammal summa ska vara exakt densamma, och de nya filerna får bara ha `saw` och `sgw` utöver dem.
- Docstringen beskriver måttet, regeln, den gamla regeln och katalogerna.

Inga trösklar, ingen mätarkontroll och ingen bootstrap är ändrade. Två ändringar för minnets skull, som inte ändrar några tal (se Körningen):

- `sums_hourly(interval, dtype)`: samma tal som `sums(np.stack(...))` men en timme (12 intervall) i taget. A1 (`domare.A1.falt`, fortfarande float16) och filtren (`filter.py`, float32) använder den, så att de 288 intervallen aldrig ligger i minnet samtidigt. Ett test visar att talen är exakt desamma, och kontrollen nedan att dagfilerna är det.
- `a2.py`: `_load_val` läser bara rutnätet och rörelsen ur cachen (`_Rutnat`) i stället för dagens 295 bilder, eftersom A2T läser A1:s sparade fält (`/data/analys/a2/a1falt/`). Det sparar cirka 1 GB och 30 till 350 s per dag. Saknas rörelsen i cachen läses hela dagen som förut.

## Kontrollen att de gamla måtten är oförändrade

`uv run python experiments/analys/domare.py kontroll A0 A1 A2T F4`: **64 dagfiler jämförda (4 system × 16 valideringsdagar), 0 skillnader.** Varje summa i de gamla dagfilerna (antal, summor, träffar, falska larm, hopp, rutorna) är exakt densamma i de nya, och de nya har bara `saw` och `sgw` utöver dem. Det gäller också A1 och F4 med `sums_hourly` och A2T med `_Rutnat`.

Dessutom ger den gamla regeln på de nya filerna **exakt samma domar** (samma listor över bättre och sämre mått) som tabellerna i `/data/analys/domare/` för A1, A2T mot A0, A2T mot A1 och F4. Tester: `tests/test_analys_domare.py` har fyra nya (kvot våt bortser från eko vid torra mätare; `compare_old`; ny och gammal regel ger olika dom när bara kvot våt skiljer, och gamla dagfiler bedöms inte i kvot våt; `sums_hourly` är exakt som `sums`).

## Kvoterna

Valideringen, 16 dagar, alla med mätarnas korsvalidering som förut. `uv run python experiments/analys/vat_kvot.py A0 A1 A2T F4`.

| system | upplösning | delmängd | kvot summa | kvot våt |
|---|---|---|---|---|
| A0 | kvart | alla | 0,825 | 0,704 |
| A0 | kvart | over400 | 0,495 | 0,366 |
| A0 | kvart | lovart | 0,604 | 0,499 |
| A0 | timme | alla | 0,890 | 0,841 |
| A0 | timme | over400 | 0,524 | 0,467 |
| A0 | timme | lovart | 0,671 | 0,609 |
| A1 | kvart | alla | 0,824 | 0,709 |
| A1 | kvart | over400 | 0,475 | 0,363 |
| A1 | kvart | lovart | 0,592 | 0,495 |
| A1 | timme | alla | 0,889 | 0,840 |
| A1 | timme | over400 | 0,505 | 0,455 |
| A1 | timme | lovart | 0,653 | 0,598 |
| A2T | kvart | alla | 0,851 | 0,748 |
| A2T | kvart | over400 | 0,575 | 0,454 |
| A2T | kvart | lovart | 0,705 | 0,608 |
| A2T | timme | alla | 0,945 | 0,899 |
| A2T | timme | over400 | 0,676 | 0,614 |
| A2T | timme | lovart | 0,821 | 0,764 |
| F4 | kvart | alla | 0,825 | 0,704 |
| F4 | kvart | over400 | 0,495 | 0,366 |
| F4 | kvart | lovart | 0,604 | 0,499 |
| F4 | timme | alla | 0,890 | 0,841 |
| F4 | timme | over400 | 0,524 | 0,467 |
| F4 | timme | lovart | 0,671 | 0,609 |

`kvot våt` är lägre än `kvot summa` överallt, med 0,05 till 0,13: en del av det som summakvoten räknade som mängd är eko vid mätare som visar 0 mm (per kvart mer, eftersom fler kvartar är torra). Radarn är alltså torrare där det regnar än summakvoten visade, särskilt per kvart över 400 m (A0 0,366 mot 0,495). F4 har samma kvoter som A0 med tre decimaler (filtret tar bort eko där det är torrt runt omkring, nästan inget vid mätarna).

## Domarna

Skillnaden är i godhet (större är bättre) med 95 % från bootstrap över dagarna (2 000 dragningar). Tabellerna i `/data/analys/domare_v2/tabell_{A1_mot_A0,A2T_mot_A0,A2T_mot_A1,F4_mot_A0}_validering.json`; utskrift med `uv run python experiments/analys/domare.py tabell A2T --mot A0` och sammanställningen med `uv run python experiments/analys/vat_kvot.py A0 --jmf A1:A0 A2T:A0 A2T:A1 F4:A0`.

| jämförelse | ny regel (kvot våt) | gammal regel (kvot summa) |
|---|---|---|
| A1 mot A0 | **inte bättre**: sämre i timme lovart kvot våt | **inte bättre**: sämre i kvart och timme lovart kvot summa |
| A2T mot A0 | **bättre**: 15 mått, inget sämre | **bättre**: 15 mått, inget sämre |
| A2T mot A1 | **bättre**: 13 mått, inget sämre | **bättre**: 13 mått, inget sämre |
| F4 mot A0 | **bättre**: FSS 0,5 och 1 per kvart, FSS 0,5, 1 och 5 per timme, inget sämre | **bättre**: samma |

### A1 mot A0

Bättre med den nya regeln i kvart kvot våt (0,709 mot 0,704, +0,007, +0,002 till +0,012; nytt), MAE, CSI 0,5 och 1 och FSS 0,5 per kvart och MAE, CSI 0,5 och 1 och FSS 0,5 per timme. Fälls av:

| delmängd | mått | A1 | A0 | skillnad (95 %) |
|---|---|---|---|---|
| kvart lovart | kvot summa | 0,592 | 0,604 | −0,020 (−0,039 till −0,001) |
| kvart lovart | kvot våt | 0,495 | 0,499 | −0,008 (−0,019 till +0,007) |
| timme lovart | kvot summa | 0,653 | 0,671 | −0,028 (−0,051 till −0,006) |
| **timme lovart** | **kvot våt** | **0,598** | **0,609** | **−0,020 (−0,038 till −0,002)** |
| timme lovart | MAE | 0,238 | 0,243 | +0,006 (+0,002 till +0,010) |
| timme lovart | falskt vid torr mätare | 0,0101 | 0,0113 | +0,0013 (+0,0002 till +0,0028) |

Per kvart på lovartsidan försvinner underskottet med den nya kvoten (intervallet går över 0), men per timme står det kvar vid de våta mätarna. A1 är alltså lite torrare än A0 vid lovartmätare som har regn, samtidigt som MAE och de falska ekona där är bättre. Det stämmer med uppgift 6 (natten 2026-11-07): A1 jämnar ut toppar i regn som rör sig fort, och en del av de topparna låg vid våta mätare. Summakvoten förklarar alltså bara en del av A1:s "underskott"; resten är en verklig, liten minskning av mängden vid våta lovartmätare per timme.

Utan kravet på underlag (min_days=0) är A1 också sämre i kvot > 5 mm per kvart och timme och > 10 mm per timme över 400 m, men de har för få dagar för domen.

### A2T mot A0 och A1

A2T slår fortfarande båda med båda reglerna och utan något sämre mått. `kvot våt` är inte ett av måtten som avgör (alla mätare: +0,060, −0,027 till +0,140 mot A0 per kvart; +0,067, −0,023 till +0,148 per timme), men i terrängen är A2T tydligt bättre också i den nya kvoten: över 400 m per timme 0,614 mot A0 0,467 (+0,274, +0,119 till +0,380) och mot A1 0,455 (+0,300, +0,201 till +0,367), på lovartsidan per timme 0,764 mot 0,609 och 0,598. Det som avgör är som förut kvot > 1 och 5 mm, MAE, CSI och FSS. Förbättringen i terrängen var alltså inte en effekt av eko vid torra mätare.

### F4 mot A0

Godkänd som förut, av FSS 0,5 och 1 per kvart och FSS 0,5, 1 och 5 per timme. Kvoterna är exakt som A0:s med tre decimaler i alla delmängder, så den nya kvoten ändrar ingenting för F4.

### Tidigare utfall

- **A1 på lovartsidan:** fälls fortfarande, nu av `kvot våt` per timme i stället för `kvot summa` per kvart och timme (se ovan). Domen blir inte annorlunda.
- **F1 mot A0** (fälld 2026-11-06 av kvot summa per kvart och timme över 400 m) är **inte omkörd**: tiden räckte inte (se Körningen). Om `kvot våt` över 400 m avgör den behöver F1 köras om: `uv run python experiments/analys/filter.py kor F1 --dagar <de 16 valideringsdagarna>` (cirka 4,5 min per dag med en process, eftersom A0:s bilder måste läsas för varje dag), sedan `domare.py tabell F1 --mot A0`. F4 har samma kvoter som A0 och är det filter som valdes, så F1 är inte längre en kandidat; körningen behövs bara för att svara på frågan.

## Körningen, tiden och disken

- Provkörning 2023-08-08 med A0, A1, F4 och F1 i en process: A0 46 s, A1 cirka 390 s, F4 cirka 175 s, F1 cirka 180 s (med `pytest` samtidigt), cirka 1 GB minne. Kontrollen på dagen: 0 skillnader för alla fyra.
- **Minnet var gränsen, inte processorn.** Två processer som båda läser in en hel dags radarbilder (cirka 1 GB var) fick inte plats bredvid driften (baslinjen var cirka 1,2 GB använt utan mina processer): tre körningar dödades tyst (en med kod 137) och har startats om. Därför de två minnesändringarna ovan. Med dem gick A2T (cirka 0,6 GB) bredvid en körning av A0, A1 och F4, men två körningar av A0, A1 och F4 samtidigt gick fortfarande inte, så de sista sex dagarna kördes med en process.
- A2T: 8 s läsning och 280 till 320 s för A2 och domaren per dag, 16 dagar på cirka 80 min med en annan process igång.
- A0, A1 och F4: 11 till 15 min per dag med två processer, 6 till 6,5 min per dag ensam. Totalt cirka 2 h 40 min väggtid för körningarna.
- Tabellerna: under 1 min var.
- Disk: `/data/analys/domare_v2/` 632 kB (dagfiler och tabeller). Ledigt på `/data` 4,0 GB före och efter. Inga nya rörelsefält behövdes. De gamla filerna i `/data/analys/domare/` är orörda.
- Testdelen lästes inte och kördes inte. `deploy/`, `models/`, `dagar.json` och `experiments/natt/` är inte ändrade.

## Filerna som ändrades

- `experiments/analys/domare.py`: kvot våt, båda reglerna, `OUT`/`OUT_V1`/`RORELSE`, `--ut`, `kontroll` och `compare_old`, `sums_hourly`, docstringen.
- `experiments/analys/filter.py`: `--ut`; filtren summerar med `sums_hourly`.
- `experiments/analys/a2.py`: `--ut`; `_Rutnat` i `_load_val`.
- `experiments/analys/vat_kvot.py` (nytt): sammanställningen av kvoterna och domarna.
- `tests/test_analys_domare.py`: fyra nya tester och `saw`/`sgw` i de konstgjorda dagarna.
- Den här rapporten.

`MAL.md` och `IDEER.md` hade ändringar i utcheckningen som inte är mina (planeraren eller loopen); jag har inte rört eller committat dem.

## Nästa steg

1. **Beslut d:** F4 omtränad på alla 28 träningsdagar (klotterkartan som modellfil), bedömd med den nya domaren (`kvot våt` i mängden) mot A0 på valideringen; dagfilerna för A0 finns redan i `/data/analys/domare_v2/A0/`. Träningsdagarna har inga dagfiler med `saw` och `sgw` än: ett urval på träningen (`filter.py urval --del traning`) kräver att A0 och varianterna körs om där först (cirka 6 min per dag och process, en process i taget för minnets skull med A0:s bilder).
2. Därefter testdelen (beslut e) en gång, med den nya domaren och den gamla regeln bredvid.
3. Om frågan om F1 ska besvaras: kör om F1 på valideringen (kommandot ovan).
4. A1 och A0 som start för prognosen: den nya kvoten bekräftar att A1 är något torrare än A0 vid våta lovartmätare per timme; det är ingen artefakt av summakvoten och bör vägas in om A1 ska ersätta A0.

Status: klar
