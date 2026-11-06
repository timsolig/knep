# 4 Terrängen: en stillastående och en rörlig del

## Sammanfattning

- Höjdmodellen (Copernicus GLO-90) är hämtad direkt från de öppna COG-filerna och skalad till radarns rutnät: `/data/projektion/hojd_2km.npz`, 887 x 471 rutor på 2 km, 1 MB, högst 2129 m. Inga hela rutor sparades.
- Kedjan har ett nytt val `stay`: en andel av analysen per pixel står still och resten flyttas, med andelen styrd av lyftet (rörelsen gånger höjdgradienten) och av platskartans fel. Standardvärdet (`None`) ger exakt driftens kedja.
- På träningsdagarna (snabb, 6 dygn, 4 km) ger andelen styrd av **lyftet** små, säkra vinster i FSS och CSI och inga sämre celler, men ingen säkert bättre konservering. Andelen styrd av **platskartans fel** blir sämre (volymen, ytan ≥ 5 mm/h, blockmaxet och FSS efter 2 h), eftersom den stillastående delen avtar utan att ersättas.
- Finalisten `Lyft` på valideringen (6 av 16 dygn, för tidens skull): **inte bättre**. Träffen vid 1 h blir något bättre (FSS, CSI, formen, hoppen), men ytan ≥ 5 och 10 mm/h och volymen blir säkert sämre efter 2 till 3 h. Orsaken är att den stillastående delen avtar utan att ersättas. Driften ändras inte.

## Utgångsläget

Rapport 3 (`delvis`) hade ingen variant som slog baslinjen, så det här bygger på driftens kedja (`kedja_om` på träningsdagarna, `kedja` på valideringen), inte på något från uppgift 3. Rapport 1 och 2 behövde inget mer för det här.

## Höjdmodellen

`experiments/projektion/hojd.py` läser GLO-90-rutorna (1 x 1 grad) med `/vsicurl/` från `copernicus-dem-90m.s3.amazonaws.com`, med medelvärde ned till 0,01 grader i läsningen (översiktsnivåerna används av GDAL), lägger dem i ett latlon-rutnät i minnet och projicerar om med medelvärde till radarens rutnät (transformen läses ur en radarfil). Hav och saknade rutor blir 0. 383 rutor lästes på cirka 5 min. Bara resultatet sparades (1 MB). Ny data i natt från uppgiften: cirka 1 MB plus domarens resultat (några MB); `df /data` visade 3,1 GB ledigt vid start.

## Metoden

Valet `Chain(stay=(smax, lyft, fel, tau), terrain=h)` i `src/knep/model.py`:

- Andelen som står still: s = smax (1 − exp(−(lyft · max(u·∇h, 0) + fel · max(K, 0)))), där u·∇h är lyftet i m per 5 min (kedjans rörelsefält i pixlar per 5 min gånger gradienten av höjden, utjämnad med σ 1 pixel, i m per pixel; det blir oberoende av upplösningen) och K är platskartan i dB (senaste timmens fel vid 30 min, som kedjan redan räknar). Bara uppförsvind och positiva fel (radarn ser mer än prognosen på platsen) ger en stillastående del.
- Fältet delas: s · a står still och avtar som exp(−ledtid / tau), (1 − s) · a flyttas som förut. Matchningens mål delas på samma sätt (den rörliga delen flyttad med närmaste granne plus den stillastående). Platskartan räknas nu före flytten i `run` (samma värde som förut, den beror bara på tillståndet).
- I domaren: `experiments/projektion/terrang.py`, en underklass till uppgift 3:s `Variant`, där 30-minutersprognosen i platskartans tillstånd görs med variantens egen delning, som i drift. Höjden skalas till lägets upplösning med domarens `coarsen`.
- Test: `tests/test_smoke.py::test_chain_stay_keeps_terrain_rain` (utan terräng och fel samma som kedjan; uppför vinden står 80 % kvar; volymen bevaras utan avtagande). `uv run pytest`: 79 passerade.

Kostnad: en gradient och en extra multiplikation per steg, 5,3 s per utgåva på 4 km mot cirka 4,3 s för kedjan i rapport 3 (med konkurrens från driften; mätningen är brusig, `Fel` tog 3,9 s).

## Träningsdagarna (snabb, 6 dygn, 4 km, mot `kedja_om`)

Hela tabellen: `experiments/projektion/resultat/terrang_snabb.md`. Parametrarna sattes för hand efter storleksordningen (10 m/s uppför 50 m per 2 km ger cirka 75 m per 5 min), inte med slumpsökning, eftersom varje variant tar 7,5 min på 6 dygn med 2 processer.

| variant | (smax, lyft, fel, tau) | yta5 3 h / 5 h | volym 5 h | q99 3 h | blockmax q90 1 h | FSS 5 mm/h 10 km 2 h / 5 h | CSI 5 mm/h 2 h | FSS 1 mm/h 30 km 1 h | form 4–8 km 1 h | hopp 1 h | domen |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `Lyft` | (0,5, 0,01, 0, 120) | +0,016 / +0,020 | +0,013 | −0,026 | +0,006 | −0,002* / −0,001* | −0,001* | −0,001* | −0,021 | −0,003* | inte bättre (inga sämre celler) |
| `Fel` | (0,5, 0, 0,5, 120) | +0,110! / +0,130! | +0,066! | −0,056 | +0,057! | +0,010 / +0,006! | +0,005 | −0,002 | −0,155* | −0,011* | inte bättre (volym, yta5, blockmax, FSS, CSI, SEDI) |

(Negativt är bättre; `*` intervallet helt på den bättre sidan, `!` helt på den sämre.)

Det träningsdagarna visar:

- **Lyftet** påverkar lite, eftersom det bara är stort i fjällen och längs kustbergen; där det verkar blir träffen något bättre på alla ledtider (FSS 5 och 10 mm/h, CSI 5 mm/h, SEDI 10 mm/h efter 3 h och båda spärrarna, säkert men med 0,001 till 0,002) och hoppen mindre. Konserveringen rör sig åt båda hållen: q99 närmare radarn, ytan ≥ 5 mm/h och volymen något längre ifrån längre fram (inte säkert). Det senare är avtagandet med tau 120 min: den stillastående delen försvinner utan att något ersätter den.
- **Platskartans fel** som styrning ger stor stillastående andel på många rutor (platskartan är positiv på en stor del av regnet), och då gör avtagandet att volymen och ytan tappas tydligt efter 2 h, och träffen blir sämre. Formen blir bättre (mindre utjämning när mindre flyttas). Felet är inte terrängbundet i sig; det fångar också tillväxt i rörliga system, som ska flyttas.
- `LyftFel`, `LyftFelStark`, `LyftFelLang` (tau 600 min) och kontrollen `Noll` (ska ge exakt `kedja_om`) hanns inte med: körningen stoppades av en tidsgräns på 10 min för bakgrundskommandon mitt i `Fel`, och `Fel` kördes klart för de fyra återstående dygnen för sig. Kontrollen ersätts bara av testet ovan (samma kod med andelen 0 ger samma fält); den är inte körd i domaren.

`Lyft` valdes som finalist: den enda utan sämre celler.

## Valideringen

`Lyft` i `validering_gles` (2 km) mot `kedja`, men bara på **6 av de 16 dygnen** (vart tredje i listan, valda innan något resultat fanns: 2019-03-08, 2020-05-10, 2021-01-20, 2021-10-20, 2024-06-28, 2025-07-29), eftersom hela valideringen (cirka 80 min) inte fick plats i tiden. 23 min med 2 processer, 20,5 s per utgåva. Tabellen: `experiments/projektion/resultat/terrang_validering_gles.md`. Testdelen lästes inte.

**Domen: inte bättre.** Skillnad mot kedjan (negativt är bättre):

| mått | 15 min | 1 h | 2 h | 3 h | 5 h |
|---|---|---|---|---|---|
| \|log kvot\| yta ≥ 5 mm/h | +0,001 | +0,009 | +0,022! | +0,027! | +0,033! |
| \|log kvot\| yta ≥ 10 mm/h | −0,001 | +0,017 | +0,024 | +0,029! | +0,030! |
| \|log kvot\| volym | −0,001 | −0,001 | +0,007 | +0,013! | +0,017! |
| \|log kvot\| q99 | −0,002 | +0,011 | +0,014 | +0,015 | +0,011 |
| blockmax q90 | +0,004 | +0,037 | +0,043 | +0,024 | +0,021 |
| FSS 5 mm/h 10 km | 0,000 | −0,002* | −0,001 | −0,001 | +0,001 |
| CSI 5 mm/h | +0,001 | −0,001* | 0,000 | 0,000 | 0,000 |
| SEDI 10 mm/h | +0,001! | 0,000 | 0,000 | −0,001 | −0,001 |
| FSS 1 mm/h 30 km (spärr) | 0,000 | −0,002* | −0,002 | 0,000 | +0,001 |
| CSI 1 mm/h (spärr) | 0,000 | −0,001* | −0,001 | 0,000 | +0,000! |
| form 4–8 km (spärr) | +0,008 | −0,061* | −0,046 | −0,024 | +0,002 |
| hopp (spärr) | −0,002* | −0,002* | −0,001 | | |

Vad valideringen säger:

- **Konserveringen blir sämre, inte bättre.** Ytan ≥ 5 och 10 mm/h och volymen kommer säkert längre från radarn efter 2 till 3 h (0,01 till 0,03 i |log kvot|), och toppvärdena (q99, blockmaxet) blir inte bättre. Det är avtagandet av den stillastående delen (tau 120 min): det regn som låses fast i terrängen försvinner med ledtiden i stället för att ersättas av det som flyttas in, och matchningens mål, som delas på samma sätt, tar inte tillbaka det. På träningsdagarna syntes samma riktning men inte säkert.
- **Träffen den första timmen blir något bättre**: FSS 5 mm/h, CSI 5 mm/h, FSS och CSI 1 mm/h vid 1 h säkert bättre med 0,001 till 0,002, formen 4 till 8 km vid 1 h −0,06 och hoppen mindre. Det stämmer med tanken: där vinden blåser uppför står regnet kvar, och det är rätt de första timmarna.
- SEDI 10 mm/h vid 15 min och CSI 1 mm/h vid 5 h är säkert sämre men med 0,001 och mindre.

Slutsatsen: delningen efter lyftet hjälper träffen den första timmen men kostar ytan och volymen längre fram, så som den är byggd (avtagande stillastående del) håller den inte kvar extremerna. Med 6 dygn är intervallen breda och resultatet ska läsas som riktning.

## Sist: målet ur det odelade fältet (`LyftHel`, bara träningsdagarna)

Med tiden som var kvar prövades nästa steg 1 på träningsdagarna: `Chain.stay_target = "whole"` gör matchningens mål till hela analysen flyttad med närmaste granne, som i kedjan, så att delningen bara ändrar var värdena hamnar och inte vilka värden som finns. `LyftHel` är `Lyft` med det målet.

Resultatet (snabb, 6 dygn, mot `kedja_om`, tabellen i `resultat/terrang_snabb.md`): förlusten av yta och volym är borta (ytan ≥ 5 mm/h och volymen inom ±0,002 av kedjan på alla ledtider, mot +0,020 och +0,013 vid 5 h för `Lyft`), träffen är kvar (FSS 5 mm/h 10 km −0,001* vid 2, 3 och 5 h, CSI 1 mm/h −0,001* vid 1 till 3 h, formen 4 till 8 km −0,05* vid 1 h, hoppen −0,001*), men konserveringen blir inte heller bättre (topparna och blockmaxet inom ±0,005). Domen: **inte bättre**, med en sämre cell (FSS 10 mm/h 10 km vid 30 min). Den kördes inte på valideringen. Den är den naturliga utgångspunkten för nästa försök: den gör det uppdraget frågar efter (terrängbundet regn flyttas inte bort) utan kostnad i volym, men den håller inte kvar fler extremer än kedjan, eftersom kedjans matchning redan återställer fördelningen; det som tappas längre fram är inflödet (rapport 3), inte terrängen.

## Filer

- `src/knep/model.py`: `Chain(stay=, terrain=)`, `Chain.stay_target`, `Chain.stay_fraction`, `Chain.project(…, stay=)` (den gamla flytten är `_project`), platskartan räknas före flytten i `run`.
- `tests/test_smoke.py`: `test_chain_stay_keeps_terrain_rain`.
- `experiments/projektion/hojd.py` (ny): höjdmodellen.
- `experiments/projektion/terrang.py` (ny): varianterna för domaren.
- `experiments/projektion/kons_sammanfatt.py`: `--namn=` för en egen tabellfil och, för den, bara de dygn som alla systemen har körts på.
- `experiments/projektion/resultat/terrang_snabb.md`, `terrang_validering_gles.md`.
- Data: `/data/projektion/hojd_2km.npz`, `/data/projektion/domare/snabb/terrang_*`, `/data/projektion/domare/validering_gles/terrang_Lyft`, loggen `/data/projektion/logg/4-snabb.log`.

## Nästa steg

1. **Bevara volymen i delningen.** Målet ur det odelade fältet (`LyftHel`) tog bort förlusten på träningsdagarna; kör den på hela valideringen (16 dygn, cirka 80 min), och pröva `Fel` och `LyftFel` med samma mål, eftersom det var avtagandet som fällde `Fel`. Kombinera sedan med inflödet från rapport 3 (`Inflode25`), som är det som faktiskt tar tillbaka ytan och volymen.
2. **Bättre styrning än platskartans fel.** Felet bör bara räknas där det är stabilt över flera utgåvor (platskartan över längre tid än en timme) eller där det samvarierar med lyftet, så att tillväxt i rörliga celler inte låses fast.
3. **Slumpsökning** över (smax, lyft, tau) med successiv halvering på träningsdagarna; varje bakgrundskörning måste få `timeout` upp till 2 h, annars stoppas den efter 10 min.
4. En orografisk förstärkning i stället för en stillastående andel: den rörliga delen gånger en faktor som beror på lyftet (seeder-feeder), lärd med minsta kvadrat på träningsdagarna mot platskartans fel.

Status: delvis
