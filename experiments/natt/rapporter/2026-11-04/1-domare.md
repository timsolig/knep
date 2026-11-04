# 1 Domaren

## Vad som gjordes

`experiments/projektion/domare.py` med tester i `experiments/projektion/test_domare.py`, och en liten ändring i `src/knep/model.py` (med test i `tests/test_smoke.py`). Träningsdagarna är kopierade oförändrade till `experiments/projektion/traning.json` (kontrollerat lika med `natt/2026-11-03:experiments/bortfall/traning.json`, 28 dagar).

### Lägen och utgåvetider

| läge | dagar | upplösning | utgåvetider |
|---|---|---|---|
| `validering` | de 16 valideringsdagarna | 2 km | samma som `/data/sverige/kedja` (varje hel timme där kedjan finns, 381 st) |
| `validering_gles` | samma | 2 km | var 3:e timme av dem, för dyra system; jämförs med kedjan på samma tider |
| `traning` | de 28 träningsdagarna | 2 km | var 3:e timme |
| `snabb` | 6 träningsdagar (2020-02-10, 2021-05-11, 2023-07-12, 2024-07-28, 2024-09-26, 2024-12-19) | 4 km (medel av 2 x 2, NaN om någon saknas) | var 3:e timme |

Testdelen finns inte i något läge; `mode_days` stoppar om en testdag skulle komma med, och ett test kontrollerar det. Baslinjen är `kedja` (driftens sparade prognoser) på valideringen och `kedja_om` (kedjan körd om här) på träningsdagarna, där driftens prognoser inte finns.

### Systemen

Ett system är en klass med `reset()` (nytt dygn), `observe(t, ctx)` och `forecast(t, ctx)`, som ger (20, H, W) kvartsmedel i mm/h. Med `warm = True` anropas `observe` var 5:e minut under 90 min före varje utgåvetid, i tidsordning, så att platskartans tillstånd byggs upp som i drift (med utgåvor varje timme blir det var 5:e minut hela dygnet, precis som `experiments/sverige/kedja.py`). `ctx` ger bara radarn bakåt från t (`frame`, `history` med högst 12 bilder i följd och minst 7 som i drift, `motion`). System i andra filer anges som `modul:Klass`.

Baslinjerna i `SYSTEMS`:

- `kedja`: driftens prognoser ur `/data/sverige/kedja` (kedjan utan extremmodell, som `kedja.py` körde den).
- `kedja_om`: `model.Chain` körd om med uppvärmt tillstånd. Kontroll mot driften på 2023-08-08 14 UTC: efter värdefilens kodning **identisk** (största skillnad 0,0 över alla 20 kvartar).
- `kedja_utan_matchning`, `kedja_utan_platskarta`: samma med de nya valen `Chain(match=False)` och `Chain(location=False)`. Utan platskarta behövs ingen uppvärmning.
- `persistens`: analysen oförändrad.
- `pysteps`: `model.nowcast`, det vill säga tätt Lucas-Kanade-fält på senaste timmens 12 bilder och semi-Lagrangesk extrapolering. Extrapoleringen görs med `advect.extrapolate`, som `tests/test_advect.py` visar ger samma värden som pysteps (högst 1e-3 mm/h skillnad bilinjärt), eftersom pysteps egen tar en halv minut per prognos.
- `sprog`: S-PROG ur pysteps (6 nivåer, AR(2)) med kedjans rörelse, i 15-minuterssteg på bilderna 30, 15 och 0 min bakåt (20 steg i stället för 60, en tredjedel av tiden). Värdet vid kvartens slut får stå för kvartsmedlet, vilket ger S-PROG lite mindre utjämning i tiden än de andra. Körs bara i `validering_gles` (60 s per prognos med 5-minuterssteg vore 6 h för valideringen).

Alla systems kvartar kodas och avkodas som värdefilen (`render.encode_values`) innan de bedöms, eftersom driftens sparade prognoser är kodade. Utan det får kedjan en systematisk skillnad på cirka 1 % i medelintensitet bara av kvantiseringen.

### Rörelsefälten

`Ctx.motion(t)` räknar kedjans Lucas-Kanade (bilderna 30, 15 och 0 min bakåt) och sparar de glesa vektorerna per 5-minuterstid i `/data/projektion/cache/rorelse/<res>km/<dag>/<HHMM>.npz` (cirka 10 kB styck). Det täta fältet byggs med `model.dense_motion` (steg 4) när det läses, så det är exakt kedjans. `Chain.run` tar nu ett förberäknat fält (`motion=`). Senare uppgifter som vill ha andra rörelsefält får lägga dem bredvid.

### Måtten

Vid ledtiderna 15, 30, 60, 90, 120, 180, 240 och 300 min (tabellen visar 15, 30, 60, 120, 180 och 300), på rutorna där radaranalysen vid utgåvetiden och radarns kvartsmedel har data (samma för alla system). Allt sparas som summor per dygn i `/data/projektion/domare/<läge>/<system>/<dag>.npz`, så att kvoterna bildas på de sammanslagna summorna och bootstrap kan dra dygn:

- Konservering (`kons`, log kvot mot radarn, 0 är rätt): 99- och 99,9-percentilen av de våta rutorna (minst 0,1 mm/h, ur histogram med 400 logaritmiska fack), ytan över 5, 10 och 20 mm/h, volymen, och blockmaxet i block om 30 km helt inom masken (median och 90-percentil bland block med max minst 0,5 mm/h; antalet sådana block redovisas som `info`).
- Träff: FSS vid 5 och 10 mm/h på 10 och 30 km, CSI vid 5 mm/h, SEDI vid 5 och 10 mm/h.
- Spärrar: FSS 1 mm/h 30 km, CSI 1 mm/h, formen (effekten för dBR i banden 4 till 8 och 8 till 16 km i rutor om 256 km helt inom masken, som `form.py`, som log kvot), och hoppet: summan av |ny − föregående utgåva| genom summan av medelintensiteten för samma giltighetstid (`form.jump` på de sammanslagna summorna), mot utgåvan närmast före (1 h på valideringen, 3 h i de glesa lägena).
- Skillnaden mot baslinjen med 95 %-intervall ur 1000 bootstrapdragningar över dygnen. Den är vänd så att negativt alltid är bättre: |log kvot| systemet − baslinjen för konservering och form, baslinjen − systemet för FSS, CSI och SEDI, systemet − baslinjen för hoppet.
- Domen (`verdict`): bättre bara om minst en konserveringscell (mått och ledtid) har intervallet helt under 0 och ingen cell för konservering, träff eller spärr har intervallet helt över 0.

I 4 km-läget finns inte bandet 4 till 8 km (under Nyquist), och det står som saknat.

Körning: `uv run python experiments/projektion/domare.py kör --läge <läge> --system <namn> ...` och `... tabell --läge <läge> --system <namn> ...` (skriver `experiments/projektion/resultat/<läge>.md`). Varje dygn sparas för sig, så en avbruten körning fortsätter där den slutade. `experiments/projektion/kor_baslinjer.py` kör baslinjerna i nattens ordning.

Testerna kontrollerar percentilen ur histogrammet mot numpy, kontingenstabellen och SEDI, FSS för perfekt och disjunkt prognos, blockmax bara för hela block, grovskalningen, att utjämning ger negativ effekt i banden, att en perfekt prognos ger 0 och 1 överallt, att uppblåsta toppar (×1,5) ger sämre konservering, falsklarm vid 1 mm/h och domen "inte bättre", att den snabba uppvärmningen ger samma tillstånd som `Chain.run(…, 6)` och att testdagarna inte finns i något läge.

## Resultat på valideringen

Bara en del av baslinjerna hann köras, och bara i läget `validering_gles` (var 3:e timme, 125 utgåvor på 16 dygn). Hela tabellen med intervallen finns i `experiments/projektion/resultat/validering_gles.md`.

| baslinje | körd |
|---|---|
| `kedja` | `validering_gles` och 2 dygn av `validering` (som `kedja_om`, för tidmätningen) |
| `persistens` | `validering_gles` |
| `kedja_utan_platskarta` | `validering_gles` |
| `pysteps`, `kedja_utan_matchning`, `sprog` | **inte körda** (hann inte; se tiderna nedan) |
| `kedja`, `persistens` i `validering` (varje timme) | **inte körda** |

### Kedjan (driften) mot radarn, log kvot där 0 är rätt

| mått | 15 min | 30 min | 1 h | 2 h | 3 h | 5 h |
|---|---|---|---|---|---|---|
| 99-percentilen, våta rutor | +0,07 | +0,08 | +0,03 | +0,05 | +0,05 | +0,08 |
| 99,9-percentilen | +0,08 | +0,10 | −0,01 | +0,03 | +0,06 | +0,04 |
| yta ≥ 5 mm/h | +0,03 | +0,04 | −0,05 | −0,09 | −0,18 | −0,26 |
| yta ≥ 10 mm/h | +0,13 | +0,16 | +0,02 | −0,01 | −0,07 | −0,12 |
| yta ≥ 20 mm/h | +0,12 | +0,18 | −0,02 | −0,05 | −0,03 | −0,13 |
| volym | 0,00 | 0,00 | −0,06 | −0,13 | −0,19 | −0,30 |
| blockmax 30 km, median | −0,10 | −0,09 | −0,05 | −0,06 | −0,07 | −0,06 |
| blockmax 30 km, 90-percentil | −0,13 | −0,11 | −0,13 | −0,12 | −0,08 | −0,08 |
| antal våta block (info) | −0,08 | −0,08 | −0,11 | −0,17 | −0,23 | −0,35 |
| effekt 4 till 8 km | −0,67 | −0,70 | −0,77 | −0,85 | −0,91 | −1,07 |
| effekt 8 till 16 km | −0,02 | −0,04 | −0,05 | −0,13 | −0,17 | −0,28 |
| FSS 5 mm/h 30 km | 0,946 | 0,830 | 0,637 | 0,394 | 0,282 | 0,133 |
| FSS 10 mm/h 30 km | 0,906 | 0,771 | 0,561 | 0,326 | 0,213 | 0,044 |
| CSI 5 mm/h | 0,510 | 0,330 | 0,187 | 0,091 | 0,061 | 0,027 |
| SEDI 10 mm/h | 0,877 | 0,776 | 0,632 | 0,485 | 0,407 | 0,179 |
| FSS 1 mm/h 30 km (spärr) | 0,978 | 0,923 | 0,807 | 0,632 | 0,512 | 0,370 |
| CSI 1 mm/h (spärr) | 0,705 | 0,553 | 0,400 | 0,268 | 0,200 | 0,135 |

Det domaren visar om kedjan redan nu, som underlag för uppgift 2:

- Percentilerna bland de våta rutorna hålls (matchningen gör det per konstruktion), men **ytan** över 5 mm/h och **volymen** krymper med ledtiden, till −0,26 och −0,30 vid 5 h, och antalet våta block om 30 km faller till −0,35. Extremerna försvinner alltså som yta, inte som toppvärde: det som lämnar området eller dör ut tas bort, och resten behåller sin fördelning.
- Blockmaxet ligger 0,06 till 0,13 under radarn redan från 15 min och ändras lite med ledtiden. Det tyder på att toppen i ett regnområde sprids ut i rummet vid matchningen (rangordningen efter det utsmetade fältet), inte på att den avtar.
- Effekten i bandet 4 till 8 km är −0,67 redan vid 15 min och −1,07 vid 5 h; 8 till 16 km faller från −0,02 till −0,28. Den bilinjära flytten tar bort de minsta skalorna direkt, och matchningen återställer inte strukturen.
- Ytan vid 60 min är 0,95 av radarns (−0,05), inte 0,8 som i `experiments/README.md`; där var det enskilda 5-minutersbilder på de öppna fallen, här kvartsmedel över hela Sverige mot radarns kvartsmedel, som också är utjämnat.

### Persistens och kedjan utan platskarta, skillnaden mot kedjan

Negativt är bättre. `*` intervallet helt på den bättre sidan, `!` helt på den sämre.

| mått | system | 30 min | 1 h | 2 h | 5 h |
|---|---|---|---|---|---|
| \|log kvot\| 99,9-percentilen | persistens | +0,118 ! | +0,152 | +0,190 ! | +0,177 ! |
| | utan platskarta | −0,078 | +0,028 | −0,003 | +0,005 |
| \|log kvot\| yta ≥ 5 | persistens | +0,065 ! | +0,049 | +0,030 | −0,103 |
| | utan platskarta | −0,009 | +0,030 | +0,043 ! | +0,019 ! |
| FSS 5 mm/h 30 km | persistens | +0,123 ! | +0,167 ! | +0,121 ! | +0,027 |
| | utan platskarta | +0,008 | +0,016 | +0,008 | +0,002 |
| CSI 5 mm/h | persistens | +0,148 ! | +0,078 ! | +0,029 ! | +0,001 |
| | utan platskarta | +0,013 ! | +0,009 ! | +0,004 ! | 0,000 |
| \|log kvot\| effekt 4 till 8 km | persistens | −0,334 * | −0,403 * | −0,514 * | −0,765 * |
| | utan platskarta | −0,001 | −0,002 | 0,000 | −0,001 |
| hopp (spärr) | persistens | +0,114 ! | +0,115 ! | +0,107 ! | . |
| | utan platskarta | −0,018 * | −0,011 * | −0,004 * | . |

Domen för båda är "inte bättre". Persistensen behåller formen (ingen utjämning) men förlorar allt annat. Platskartan ger en liten men säker vinst i CSI och SEDI för det kraftiga de första 2 h och för ytan över 5 mm/h efter 2 h, och kostar lite i hopp mellan utgåvorna och i 99-percentilen de första 30 min.

Hoppet i läget `validering_gles` jämför utgåvor 3 h isär, så det finns bara till 2 h ledtid och är stort (cirka 1,4 gånger medelintensiteten); i läget `validering` jämförs utgåvor 1 h isär.

## Tiderna

Pi:n delade processorn med driften; processerna fick cirka 85 % var.

| körning | tid med 2 processer | per utgåva (processortid) |
|---|---|---|
| `kedja` (läser driftens filer), `validering_gles`, 125 utgåvor | 5,5 min | 5,2 s, allt i domaren |
| `persistens`, `validering_gles` | 3,6 min | 6,8 s |
| `kedja_utan_platskarta`, `validering_gles` | 28,5 min | 27 s, varav 20 s prognosen (med Lucas-Kanade vid utgåvan, nu sparat) |
| `kedja_om`, `validering`, 2 dygn x 24 utgåvor | 20,8 min | 1240 s per dygn, varav 528 s prognoserna (22 s styck) och resten uppvärmningen var 5:e minut (med Lucas-Kanade första gången) och måtten |

**Kravet på cirka 45 min för en full körning på valideringen nås inte med varje timme som utgåvetid.** Ett uppvärmt system som kedjan tar cirka 16 x 1240 s / 2 ≈ 2,8 h första gången och uppskattningsvis 2 h när rörelsefälten finns sparade; ett system utan uppvärmning cirka 1,4 h; bara domarens egen del (läsa radarn och räkna måtten) cirka 16 min. Det dyra är kedjans 60 steg med fördelningsmatchning i varje steg (cirka 10 s utan konkurrens), uppvärmningens 288 körningar per dygn och 4 till 6 s mått per utgåva. Det som går att hålla inom 45 min är läget `validering_gles` (ett system utan uppvärmning cirka 30 min, med uppvärmning uppskattningsvis 45 till 60 min) och `snabb` för sökningen (persistensen tog 19 s för ett dygn). Förslaget till de följande uppgifterna är att bedöma kandidater i `validering_gles`, med `kedja` som baslinje på samma tider, och köra finalisten i `validering` om tiden räcker.

Rörelsecachen: 288 filer per dygn, cirka 15 kB styck (4,5 MB för två dygn); allt nytt under `/data/projektion` var 6,4 MB i slutet. Valideringsdagarna är sparade vid utgåvorna i `validering_gles`, för alla tider på 2021-05-17 och 2023-08-08, och vid de utgåvetider som kördes för `kedja_utan_platskarta`.

## Det som inte fungerade eller är svagt

- Första bakgrundskörningen stoppades av verktygets gräns på 10 min för bakgrundskommandon; den startades om med längre gräns och fortsatte från de sparade dygnen. Körningen stoppades sedan av mig 20:10 för att lämna tid åt rapporten, under `pysteps`; inga halva dygn sparades.
- Histogrammen för percentilerna och blockmaxet har fack som är cirka 3 % breda i log. Mellan två nästan lika system (kedjan med och utan platskarta) gör det percentilskillnaderna grova, och bootstrapintervallet kan hamna precis på ena sidan om 0 för skillnader på 0,002 (blockmax-medianen är markerad som sämre för kedjan utan platskarta för den skillnaden). **Rättning till nästa uppgift**: fler fack (till exempel 2000) i `EDGES`, och en nedre gräns för hur liten skillnad som räknas (till exempel 0,01 i log kvot) i domen. Båda ändrar de sparade summorna, så baslinjerna måste köras om (kedjan och persistensen tar 9 min tillsammans i `validering_gles`). Jag ändrade inte detta i natt eftersom omkörningen av kedjan utan platskarta inte hade hunnits med.
- Hoppet var 0 i stället för saknat när ingen tidigare utgåva täckte ledtiden; det rättades i tabellen (bara redovisningen, inga summor ändrades).
- S-PROG i 15-minuterssteg med värdet vid kvartens slut är inte exakt samma sak som kvartsmedlet. Det har inte provats än.
- Extremmodellen finns inte med; driftens sparade kedja kördes utan den (`kedja.py` använder `Chain(None)`), så baslinjen är jämförbar med `kedja_om`.

## Filer

- `experiments/projektion/domare.py` (ny), `experiments/projektion/test_domare.py` (ny), `experiments/projektion/kor_baslinjer.py` (ny), `experiments/projektion/traning.json` (kopia), `experiments/projektion/resultat/validering_gles.md` (tabellen)
- `src/knep/model.py`: `Chain(match=True, location=True)` och `Chain.run(…, motion=None)`; standardvärdena ger samma kedja som förut
- `tests/test_smoke.py`: test för de nya valen
- Data: `/data/projektion/cache/rorelse/`, `/data/projektion/domare/`, `/data/projektion/logg/baslinjer.log`

## Nästa steg

1. Rätta histogrammens upplösning och domens minsta skillnad (se ovan) och kör om `kedja`, `persistens` och `kedja_utan_platskarta` i `validering_gles`.
2. Kör de baslinjer som saknas: `uv run python experiments/projektion/kor_baslinjer.py /data/projektion/logg/baslinjer.log` fortsätter med `pysteps`, `kedja_utan_matchning` och `sprog` i `validering_gles` (uppskattat 30, 45 och 25 min) och sedan `kedja` och `persistens` i `validering`.
3. Kör `kedja_om` i läget `traning` (baslinjen där) och `snabb` innan sökningen i uppgift 3 börjar.
4. För att nå 45 min i läget `validering`: spara radarns sida av måtten per utgåva och ledtid (kvartsmedel, histogram, spektrum) så att den räknas en gång för alla system, och låt systemen ge bara de kvartar som behövs.

Status: delvis
