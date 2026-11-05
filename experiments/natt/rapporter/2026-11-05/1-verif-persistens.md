# Uppgift 1: verifieringens persistens

## Slutsats

Jag hittade inget fel i verifieringen. Persistensen är radarns timsumma för timmen som slutar på utgåvans heltimme hh. Den jämförs mot timmen som slutar hh + k. Tim-KNEP:s timsumma k är medlet av de tolv 5-minutersbilderna som slutar hh + k. Alla modeller räknas på block där facit och Tim-KNEP finns, plus modellens egna block, och kontingenstabellerna räknas med samma funktion. Persistensens lägre n är avsiktligt: timmen hh måste vara uppmätt (SMHI, OPERA eller volymer i minst 11 av 12 bilder). Det tar bort 7 till 13 % av blocken, och jämförelsen mot Tim-KNEP görs parvis på exakt de blocken (`ours@persistens`). Fördelen kvarstår där: +0,07 till +0,17 i CSI vid 1 mm.

Persistensens styrka är alltså verklig de här två nätterna. Det rör sig om sex utgåvor (4 nov 19:05 till 5 nov 00:05 UTC) och två dygn, så verif.json har inget intervall, eftersom bootstrap kräver minst 3 dygn. Siffrorna är ett fall och inte en statistik.

## Vad jag granskade i `src/knep/verify.py`

| Fråga | Svar |
|---|---|
| Är persistensen rätt timme? | `issue()` tar `obs_hour(vdir, _floor(t0))`, alltså timmen som slutar hh (bilderna hh−0:55 till hh:00). `observe()` körs före `issue()` i `cycle()`, så timmen är färdig vid utgåvan hh:00 till hh:15. Om en bild saknas vid första cykeln skrivs utgåvan utan persistens och görs inte om. Det ger färre timmar men inget skevt urval. |
| Rätt giltighetstimme? | `ends = hh + k·1h`, samma för alla modeller. `score()` hämtar facit `obs_hour(hh + k)`. |
| Tim-KNEP:s timmar | `render.aggregate(..., 60)` märker perioden med sluttiden och tar medlet av bilderna end−55 till end. Det är samma konvention som facit. Enheten är mm/h som timmedel, alltså mm under timmen, både för facit och för prognosen. |
| Samma mask | `base = finite(O) & finite(Tim-KNEP)`, och varje modell får `base & finite(F)`. Modeller med samma mask räknas ihop. SNOW har exakt Tim-KNEP:s n. Persistensen har en egen grupp, och Tim-KNEP räknas om på den (`ours@persistens`). |
| Kontingenstabellerna | `contingency()` är samma för alla. Träff, falsklarm och miss räknas med `>=`, och rätt torrt är resten. |

## Testerna

`tests/test_verify_persistence.py` (nytt). Testerna i `test_verify.py` har stillastående regn, och där blir persistensen och en perfekt prognos rätt oavsett vilken timme som används. De nya testerna har ett band som flyttar sig en ruta (2 km) per bild, ett stillastående område, ett hål utan mätning under timmen hh och en östlig remsa där Tim-KNEP saknar värden. Facit räknas oberoende av verify.py.

- `test_moving_rain_puts_every_hour_where_it_belongs`: utgåvor hh:00, hh:05 och hh:15. Persistensen i `pending` är exakt timmen hh för alla k. Tim-KNEP är timmen hh + k. En perfekt prognos ger noll falsklarm och noll missar vid alla ledtider. Persistensens tabeller är lika med en oberoende räkning av timmen hh mot timmen hh + k, och n är lika med antalet block där facit, persistensen och Tim-KNEP finns.
- `test_pairs_use_the_same_blocks`: persistensens n är lika med parets n och mindre än Tim-KNEP:s. Paret är Tim-KNEP på persistensens block.
- `test_tables_are_counted_the_same_for_every_model`: en jämförelsekälla (MET-plats) med exakt persistensens fält får exakt samma tabeller, summor och FSS.

Jag kontrollerade testerna med tre tillfälliga fel i verify.py, som togs bort efteråt. Diffen mot HEAD är tom.

1. Persistensen tar timmen hh − 1. Alla tre testerna faller.
2. Tim-KNEP:s timme förskjuts en timme. Alla tre testerna faller.
3. Masken tas utan Tim-KNEP (`finite(O) & finite(F)`). Först föll inget test, eftersom Tim-KNEP inte hade NaN någonstans. Jag lade därför till remsan utanför prognosens område, och efter det faller två tester.

`uv run pytest`: 82 passed (sviten före de nya testerna och de tre nya; körd med verify.py oförändrad).

## Siffrorna ur verif.json (`experiments/projektion/verif_json.py`)

CSI per ledtid vid timsumman ≥ 1 mm, 7-dygnsfönstret (6 utgåvor):

| ledtid | Tim-KNEP | persistens | SNOW | MET Norge | persistens − Tim-KNEP på samma block |
|---|---|---|---|---|---|
| +1 h | 0,136 | 0,215 | 0,006 | 0,018 | +0,074 |
| +2 h | 0,020 | 0,163 | 0,008 | 0,006 | +0,143 |
| +3 h | 0,008 | 0,172 | 0,004 | | +0,165 |
| +4 h | 0,003 | 0,179 | 0,002 | | +0,177 |
| +5 h | 0,003 | 0,164 | 0,005 | | +0,162 |

Vid 0,1 mm är skillnaden liten vid +1 h (+0,021), men från +2 h ligger persistensen på 0,36 mot 0,18 till 0,24 för Tim-KNEP. Vid +3 till +5 h är även SNOW bättre än Tim-KNEP vid 0,1 mm (+0,025 till +0,049).

Därför är persistensen stark. Träffarna vid 1 mm är nästan desamma vid alla ledtider: 542, 397, 378, 441 och 413 block den 4 november, av ungefär 1 700 till 1 900 block med regn. Ungefär en fjärdedel av ytan över 1 mm låg kvar i samma 4 km-block i fem timmar, det vill säga stillastående eller terrängbunden nederbörd. Persistensens CSI faller inte med ledtiden, vilket den hade gjort om systemen hade rört sig. Dessutom avtog regnet under natten. Persistensens kvot mot radarn är 1,13 till 1,45 och FBI vid 1 mm 1,17 till 1,54. Persistensen överskattar alltså ytan men träffar ändå.

Var Tim-KNEP förlorar. Kedjans medelvikt i blandningen (`seamless.weight`, standardvärdena, för timmen k från utgåvan hh:05) är 0,82, 0,30, 0,10, 0,04 och 0,02 för de små skalorna, och 0,97, 0,79, 0,51, 0,31 och 0,19 för de stora (σ 30 km).

- Vid +1 h är vikten nästan bara kedjan, och den förlorar ändå mot timgammal persistens vid 1 mm (0,136 mot 0,215 på samma block, 0,458 mot 0,486 vid 0,1 mm). En extrapolering 5 till 60 min fram borde slå en timme gammal persistens. Att den inte gör det tyder på att kedjan flyttar bort regn som står stilla, alltså terrängproblemet i CLAUDE.md.
- Fallet från +1 till +2 h (träffarna 421 till 47 den 4 november) sammanfaller med att kedjans vikt för de små skalorna går från 0,82 till 0,30. Vid +3 till +5 h har Tim-KNEP samma CSI vid 1 mm som SNOW (0,003 till 0,008 mot 0,002 till 0,005), och SNOW är MEPS. Läget i Tim-KNEP:s fält kommer då nästan helt från den rättade MEPS. Det mesta av förlusten efter +2 h kommer alltså från den sömlösa blandningen, som ersätter det stillastående mönstret med MEPS mönster. Mängdrättningen gör att FBI ändå blir rimligt (1,0 till 1,1).
- Om kedjan ensam hade hållit kvar mönstret till +3 till +5 h kan jag inte visa. Den förlorar redan vid +1 h, så den hade troligen också tappat, men långsammare än blandningen.

Detta gäller standardvärdena. I drift kan `seamless.adapted` flytta viktkurvan efter senaste timmens träffsäkerhet, och vilka vikter som faktiskt användes står i manifestet (`seamless`), som inte finns här.

## Det som inte gick

Radarn för 4 och 5 november finns inte i `/data/radar`, som slutar 2025, och MEPS i `/data/meps` slutar 2025-10-30. Jag skrev `experiments/projektion/persistens_nov.py`, som hämtar kompositerna 2026-11-04 17:00 till 2026-11-05 06:00 ur SMHI:s öppna arkiv till `/data/projektion/drift/radar/` (cirka 160 bilder) och kör kedjan utan MEPS för de sex utgåvorna. Skriptet räknar också hur stillastående regnet är: andelen av ytan över 1 mm som låg kvar, och förskjutningen med bäst korrelation. Att köra skriptet nekades i den här sessionen (nätåtkomst). Jag försökte inte på annat sätt, så **skriptet är aldrig kört och oprovat**. Siffrorna ovan kommer bara ur verif.json och viktfunktionen.

## Vad som behöver köras om i drift

Inget, eftersom inget fel hittades. Underlaget i drift är rätt.

## Nästa steg

1. Kör `uv run python experiments/projektion/persistens_nov.py` där nätet är tillåtet (eller med radarn kopierad till `/data/radar/2026/11/`). Det skiljer kedjan från blandningen med radardata och visar hur stillastående regnet var. Räkna med ett par minuter per utgåva för kedjan på Pi:n. Skriptet saknar extremmodell, volymkorrektion och platskarta (tomt tillstånd), så det är en tillnärmning av driften.
2. Spara kedjans timsummor före blandningen som en egen modell i verifieringen (`kedja` bredvid `ours`), så att driften själv visar om förlusten kommer från kedjan eller blandningen. Det är en liten ändring i `cli.py` och `verify.issue` (fältet `fc` före `seamless.run_operational`).
3. Persistensen bör finnas med i domaren för projektionsarbetet som en referens för stillastående regn. När den slår kedjan är det ett tecken på att terrängbunden nederbörd flyttas bort.
4. MET Norge är mycket torr här (FBI 0,15 vid 1 mm, kvot 0,44). Det är värt att kontrollera omprojiceringen i `compare.py` med medel för 4 km när fler dygn finns.

## Filer

- `tests/test_verify_persistence.py` (nytt): tre tester med rörligt regn.
- `experiments/projektion/verif_json.py` (nytt): sammanfattning av en verif.json.
- `experiments/projektion/persistens_nov.py` (nytt, inte kört).
- `src/knep/` är oförändrad.

Status: delvis
