# Uppgift 0013: kedjan utan fördelningsmatchning på valideringen

Kort: kedjan utan matchning är redan dömd på valideringen (`validering_gles`, 16 dygn, 125 utgåvor, körd 2026-11-04 i natt 1) och domen är **inte bättre**: CSI och FSS blir 0,001 till 0,006 bättre, men blockmaxets 90-percentil är säkert sämre vid alla ledtider (+0,058 till +0,065 i |log kvot|, intervallen +0,033 till +0,094), formen 4 till 8 km säkert sämre (+0,042 till +0,053) och SEDI 10 mm/h säkert sämre vid 15 till 60 min; jag körde inte valideringen en gång till, utan räknade om tabellen ur de sparade summorna och ett dygn bit för bit lika med dagens kod. Inflödet vid randen var också redan valt och fällt i natt 1 (`Inflode25`); på träningen tar det tillbaka hälften av förlusten nära randen (kvoten mot radarn vid +60 min 0,897 mot kedjans 0,778).

Uppgiften byggde på `rapporter/2026-11-07/0006-kedjans-underskott-1h.md`, `MAL.md` och docstringen i `experiments/projektion/domare.py`. Testdelen lästes inte; `domare.mode_days` stoppar testdagarna som förut. Inget i `src/`, `deploy/`, `models/` eller domarens mått ändrades.

## Disken

`df -m /data` vid start (08:56 lokal tid): 3 668 MB ledigt, över gränsen 3 000 MB, så huvuduppgiften kördes och reserven behövdes inte.

## Det viktiga först: valideringen var redan sedd för det här systemet

Systemet finns i `SYSTEMS` i `domare.py` sedan natt 1 (2026-11-04): `"kedja_utan_matchning": lambda: KedjaOm(match=False)`. Det är exakt samma system som uppgift 0006 körde (`facit_a2t.py kedja --system kedja_utan_matchning` går genom `make_system`). Natt 1 körde det redan på `validering_gles` (`experiments/natt/rapporter/2026-11-04/1-domare.md`, försök 2, 52 min) med domen **inte bättre**, och tabellen står i `experiments/projektion/resultat/validering_gles.md`. Summorna ligger kvar under `/data/projektion/domare/validering_gles/kedja_utan_matchning/` (16 dygn). Planeraren och rapporten 0006 hade inte sett det.

Jag valde därför att **inte** köra valideringen igen, varken `validering` (varje timme) eller `validering_gles`:

- Uppgiften säger att systemet ska bedömas en gång på valideringen. Det är gjort. En körning till på samma 16 dygn, med tre gånger fler utgåvor, vore en andra titt på valideringen för samma system, och den kan inte vända domen: de sämre cellerna i blockmaxets 90-percentil ligger med hela intervallet 0,033 till 0,094 över noll vid alla sex ledtider, och bootstrapen är över samma dygn.
- Hela `validering` med uppvärmning tar enligt natt 1 cirka 2 till 2,8 h med två processer (1240 s per dygn och process), alltså mer än uppgiftens tid.

I stället kontrollerade jag att de sparade summorna gäller för dagens kod:

1. **Tabellen ur de sparade summorna** med dagens `domare.table` (skriptet `experiments/projektion/utan_matchning_kontroll.py tabell`, som inte skriver över `resultat/validering_gles.md`): identisk med tabellen från 2026-11-04.
2. **Ett dygn räknat om** (`utan_matchning_kontroll.py om --dag 2021-05-17 --ut /tmp/k0013`, 8 utgåvor, 222 s mot 224 s då): alla summor (`hist_f`, `hist_o`, `bmax_f`, `bmax_o`, `area_f`, `area_o`, `vol`, `ct`, `fss`, `spec`, `jump`, `n`) är **bit för bit lika** med de sparade. Kedjan och domaren har alltså inte ändrats på något sätt som rör systemet sedan natt 1.

Läget är `validering_gles`: de 16 valideringsdygnen, utgåvor var 3:e hel timme där driftens kedja finns (125 utgåvor), 2 km, baslinjen `kedja` (driftens sparade prognoser, som natt 1 visade är identiska med `kedja_om` efter värdefilens kodning) på samma tider.

## Domarens tabell

`validering_gles`, 16 dygn, 125 utgåvor, mot `kedja`. Varje cell: systemets värde (log kvot mot radarn för kons och form, poäng för träff och spärrar) och skillnaden mot `kedja` med 95 %-intervall (bootstrap över dygnen, 1000 dragningar), orienterad så att **negativt är bättre**. `*` intervallet helt på den bättre sidan, `!` helt på den sämre (för log kvot dessutom minst 0,01 från 0).

| mått | slag | 15 min | 30 min | 1 h | 2 h | 3 h | 5 h |
|---|---|---|---|---|---|---|---|
| q99 | kons | −0,054 (−0,063, −0,029)* | −0,031 (−0,073, −0,026)* | −0,006 (−0,059, +0,058) | −0,040 (−0,060, +0,054) | −0,044 (−0,059, +0,054) | −0,053 (−0,060, +0,057) |
| q99,9 | kons | −0,073 (−0,106, +0,075) | −0,103 (−0,109, +0,096) | +0,079 (−0,088, +0,121) | +0,040 (−0,097, +0,129) | −0,039 (−0,106, +0,116) | −0,011 (−0,104, +0,127) |
| yta ≥ 5 | kons | −0,022 (−0,042, −0,006) | −0,018 (−0,031, +0,017) | +0,021 (−0,025, +0,033) | +0,024 (+0,011, +0,043)! | +0,023 (+0,009, +0,045) | +0,024 (+0,008, +0,054) |
| yta ≥ 10 | kons | −0,062 (−0,113, −0,035)* | −0,055 (−0,092, −0,033)* | +0,031 (−0,085, +0,095) | +0,066 (−0,082, +0,108) | +0,062 (+0,003, +0,110) | +0,058 (−0,050, +0,129) |
| yta ≥ 20 | kons | −0,120 (−0,168, +0,170) | −0,119 (−0,194, +0,125) | +0,130 (−0,137, +0,245) | +0,144 (−0,143, +0,291) | +0,135 (−0,124, +0,261) | +0,124 (−0,119, +0,289) |
| volym | kons | −0,000 (−0,001, +0,001) | −0,001 (−0,004, +0,002) | −0,001 (−0,005, +0,002) | +0,000 (−0,003, +0,003) | +0,001 (−0,001, +0,002) | +0,000 (−0,001, +0,002) |
| blockmax 50 % | kons | +0,012 (+0,009, +0,036) | +0,011 (+0,008, +0,035) | +0,032 (+0,008, +0,034) | +0,032 (+0,008, +0,035) | +0,031 (+0,007, +0,034) | +0,012 (+0,008, +0,037) |
| blockmax 90 % | kons | +0,058 (+0,034, +0,078)! | +0,059 (+0,033, +0,090)! | +0,058 (+0,033, +0,091)! | +0,065 (+0,037, +0,092)! | +0,063 (+0,040, +0,094)! | +0,062 (+0,034, +0,093)! |
| FSS 1 mm/h 30 km | spärr+ | −0,000 (−0,000, −0,000)* | −0,000 (−0,001, −0,000)* | −0,001 (−0,001, −0,001)* | −0,002 (−0,002, −0,001)* | −0,002 (−0,002, −0,002)* | −0,002 (−0,003, −0,001)* |
| FSS 5 mm/h 10 km | träff | −0,001 (−0,002, −0,001)* | −0,001 (−0,002, −0,000)* | −0,001 (−0,002, −0,000)* | −0,002 (−0,003, −0,001)* | −0,002 (−0,002, +0,000) | −0,001 (−0,002, +0,000) |
| FSS 5 mm/h 30 km | träff | −0,001 (−0,002, −0,000)* | −0,000 (−0,001, +0,000) | −0,001 (−0,001, −0,000)* | −0,002 (−0,004, −0,001)* | −0,002 (−0,003, +0,001) | −0,001 (−0,002, +0,001) |
| FSS 10 mm/h 10 km | träff | −0,006 (−0,010, −0,004)* | −0,004 (−0,006, −0,002)* | −0,002 (−0,004, +0,002) | −0,004 (−0,005, +0,000) | −0,003 (−0,004, +0,001) | −0,000 (−0,001, +0,001) |
| FSS 10 mm/h 30 km | träff | −0,005 (−0,011, −0,002)* | −0,004 (−0,007, −0,002)* | −0,002 (−0,004, +0,003) | −0,004 (−0,005, +0,001) | −0,003 (−0,004, +0,002) | −0,000 (−0,001, +0,002) |
| CSI 1 mm/h | spärr+ | −0,001 (−0,002, −0,001)* | −0,001 (−0,002, −0,001)* | −0,002 (−0,002, −0,001)* | −0,002 (−0,002, −0,001)* | −0,001 (−0,002, −0,001)* | −0,001 (−0,002, −0,001)* |
| CSI 5 mm/h | träff | −0,003 (−0,004, −0,002)* | −0,001 (−0,002, −0,000)* | −0,001 (−0,001, −0,000)* | −0,001 (−0,002, −0,000)* | −0,001 (−0,001, −0,000)* | −0,000 (−0,001, +0,000) |
| SEDI 5 mm/h | träff | +0,001 (−0,000, +0,004) | +0,001 (−0,000, +0,002) | +0,000 (−0,001, +0,001) | −0,002 (−0,003, −0,001)* | −0,002 (−0,003, −0,001)* | −0,002 (−0,004, −0,000)* |
| SEDI 10 mm/h | träff | +0,004 (+0,002, +0,009)! | +0,003 (+0,001, +0,007)! | +0,001 (+0,000, +0,004)! | −0,003 (−0,003, +0,001) | −0,004 (−0,005, +0,001) | −0,002 (−0,005, +0,003) |
| form 4 till 8 km | spärr\| | +0,053 (+0,046, +0,059)! | +0,053 (+0,046, +0,059)! | +0,051 (+0,045, +0,055)! | +0,048 (+0,041, +0,053)! | +0,045 (+0,038, +0,051)! | +0,042 (+0,035, +0,048)! |
| form 8 till 16 km | spärr\| | +0,036 (−0,019, +0,041) | +0,035 (+0,004, +0,039) | +0,033 (+0,007, +0,037) | +0,030 (+0,025, +0,035)! | +0,029 (+0,024, +0,035)! | +0,027 (+0,021, +0,033)! |
| hopp | spärr− | −0,020 (−0,023, −0,017)* | −0,019 (−0,022, −0,017)* | −0,019 (−0,022, −0,017)* | −0,019 (−0,022, −0,017)* | . | . |

Kedjans egna värden (baslinjen) för de mått som rör extremerna, log kvot mot radarn: blockmaxets 90-percentil −0,13, −0,11, −0,13, −0,12, −0,08, −0,08; utan matchning −0,19, −0,17, −0,19, −0,18, −0,14, −0,14. Formen 4 till 8 km −0,67 till −1,07 för kedjan, −0,72 till −1,11 utan matchning. q99,9 −0,00, +0,00, −0,09, −0,08, −0,02, −0,03 utan matchning mot kedjans +0,08, +0,10, −0,01, +0,03, +0,06, +0,04.

Domaren: **inte bättre** (yta5@120, blockmax_q90 vid alla sex ledtider, sedi10@15, @30, @60, form4_8 vid alla, form8_16 från 2 h).

Persistensen på samma utgåvor är också inte bättre än kedjan (den är sämre i nästan allt utom volymen); hela tabellen står i `resultat/validering_gles.md` och är oförändrad.

## Domen

**Kedjan utan fördelningsmatchning är inte bättre än kedjan.**

- Huvudmåtten: konserveringen blir säkert bättre bara vid 15 och 30 min (q99 och ytan ≥ 10 mm/h, där kedjans platskarta annars överskattar), och träffen (CSI 5 mm/h, FSS 5 och 10 mm/h) blir 0,001 till 0,006 bättre de första 2 h. Det är samma små vinster som 0006 såg på träningen (CSI 1 mm +0,001 till +0,002, FSS +0,001 till +0,002).
- Extremerna, som uppgiften bad mig se särskilt på: **blockmaxets 90-percentil är säkert sämre vid alla ledtider** (kedjan ligger redan 0,08 till 0,13 under radarn, utan matchning 0,14 till 0,19), formen 4 till 8 km säkert sämre överallt (fältet blir slätare), SEDI 10 mm/h säkert sämre under den första timmen och ytan ≥ 5 mm/h säkert sämre vid 2 h. 99,9-percentilen och ytan ≥ 20 mm/h har breda intervall som innehåller noll åt båda hållen; ytan ≥ 10 mm/h är bättre vid 15 och 30 min och sämre (inte säkert) därefter.
- Matchningen gör alltså det den finns för: den håller toppen per regnområde och de små skalorna. Det som 0006 mätte (CSI, FSS och MAE mot radarn, A2T och mätarna) belönar ett slätare fält, och det är just det domarens spärrar för extremerna fångar.

## Inför testdelen

Kedjan utan matchning bör enligt domen **inte** in bland testdelens system; baslinjen `kedja` (med matchningen) står kvar. Det beslutar användaren och står som fråga i rapporten och i `MAL.md`: vill du ändå ha med `kedja_utan_matchning` i testdelen som en jämförelse (inte en kandidat)? Min rekommendation är nej, eftersom den är fälld på valideringen och testdelen bara ska köras för de system som står i beslut 5.

## Punkt 2: inflödet vid randen

**Också det var redan gjort i natt 1** (`experiments/natt/rapporter/2026-11-04/3-konservering.md`, försök 2): `Chain(inflow=L)` med L = 25, 75 och 250 km (`konservering:Inflode25`, `Inflode75`, `Inflode250`) valdes i `snabb` mot `kedja_om`, `Inflode25` frystes (minst överskott av det kraftiga) och bedömdes på `validering_gles` tillsammans med `Inflode75`. Domen för båda: **inte bättre**, bara för att ytan ≥ 10 mm/h vid 15 och 30 min och ytan ≥ 20 mm/h vid 30 min blir säkert större (+0,02), där kedjans platskarta redan överskattar; volymen från 2 h, ytan ≥ 5 mm/h från 3 h, CSI 5 mm/h och alla spärrar var säkert bättre. Natt 3 (2026-11-07, `7-inflode.md`) prövade att klippa platskartan (`Inflode25Topp10`), som tog bort överskottet men fälldes av blockmaxet.

Jag valde därför inga nya värden och körde ingen ny validering. **Frys-kandidaten är fortfarande `Inflode25`** (`inflow` = 25 km, 12,5 rutor på 2 km); den är redan sedd på valideringen och fälld, så det som behövs är inte ett annat L utan ett sätt att bli av med överskottet de första 30 minuterna som inte sänker blockmaxet.

Det som saknades var måttet från 0006: hur mycket av förlusten vid randen inflödet tar tillbaka, och vad det gör mot radarn, A2T och mätarna. Det räknade jag på de 15 träningsdagarna ur 0006 (90 utgåvor, samma rutor och mätartimmar som kedjan, B = 2000), med `facit_a2t.py kedja --system konservering:Inflode25` och `summera --varianter konservering:Inflode25 --namn inflode25`. Det är en diagnos på träningen, inte en dom.

**Kvoten mot radarns kvart nära randen** (`facit_a2t_rand.py --system konservering:Inflode25`, kedjans rand och rutor; kedjan räknad om ger exakt 0006:s värden):

| | +15 min | +30 min | +45 min | +60 min |
|---|---|---|---|---|
| kedja, inom 50 km från randen | 0,963 | 0,885 | 0,817 | 0,778 |
| `Inflode25`, inom 50 km | 1,009 | 0,984 | 0,934 | 0,897 |
| kedja, längre in | 0,989 | 0,995 | 0,985 | 0,980 |
| `Inflode25`, längre in | 0,989 | 0,995 | 0,985 | 0,982 |

Inflödet tar alltså tillbaka ungefär hälften av förlusten vid randen vid +60 min (från −22 % till −10 %) och ändrar nästan inget inne i området. Vid +15 min ger det ett litet överskott vid randen (1,009), samma tecken som det som fällde det på valideringen.

**Mot radarn, A2T och mätarna** (`Inflode25` minus kedjan, 95 %-intervall, * helt på ena sidan):

| facit | mått | +1 h | +2 h | +3 h | +5 h |
|---|---|---|---|---|---|
| radarn | CSI 1 | +0,003 (0,001 till 0,004) * | +0,005 (0,002 till 0,009) * | +0,005 (0,002 till 0,008) * | +0,004 (0,002 till 0,007) * |
| radarn | CSI 5 | +0,009 (0,001 till 0,023) * | +0,008 (0,000 till 0,022) * | +0,002 (−0,001 till 0,006) | −0,000 (−0,002 till 0,001) |
| radarn | FSS 1/10 | +0,002 (0,001 till 0,003) * | +0,005 (0,002 till 0,009) * | +0,007 (0,003 till 0,011) * | +0,007 (0,003 till 0,011) * |
| radarn | kvot | 0,984 mot 0,971 * | 0,973 mot 0,955 * | 0,974 mot 0,952 * | 1,006 mot 0,976 * |
| radarn | MAE | −0,000 (−0,001 till 0,000) | −0,000 (−0,001 till 0,001) | +0,001 (0,000 till 0,002) * | +0,003 (0,001 till 0,005) * |
| A2T | CSI 1 | +0,002 * | +0,004 * | +0,004 * | +0,004 * |
| A2T | FSS 1/10 | +0,002 * | +0,005 * | +0,006 * | +0,007 * |
| A2T | kvot | 1,003 mot 0,990 * | 0,984 mot 0,965 * | 0,993 mot 0,970 * | 1,009 mot 0,979 * |
| A2T | MAE | +0,001 (−0,000 till 0,003) | +0,001 (−0,000 till 0,002) | +0,002 (0,000 till 0,003) * | +0,003 (0,001 till 0,005) * |
| mätarna | CSI 1 | +0,001 (0,000 till 0,002) | +0,001 (−0,001 till 0,004) | +0,002 (−0,001 till 0,006) | +0,005 (0,001 till 0,009) * |
| mätarna | kvot | 0,915 mot 0,914 * | 0,986 mot 0,982 * | 0,979 mot 0,964 * | 0,961 mot 0,935 * |
| mätarna | MAE | −0,000 | +0,000 | +0,002 (−0,000 till 0,006) | +0,002 (−0,000 till 0,007) |

Vid mätarna, som oftast ligger inne i området, är skillnaden liten (som 0006 väntade sig). Mot radarn och A2T blir CSI 1 mm och FSS säkert bättre vid alla ledtider och kvoten närmare 1, men MAE blir något sämre från +3 h (mer regn där fyllningen gissar fel). Över hela fältet stiger kvoten mot radarns kvart med 0,008 till 0,019 under första timmen (0,949 blir 0,969 vid +60 min).

Kostnad: 277 till 383 s per dygn och process (18 till 26 s per prognos), cirka 45 min i två processer; `summera` cirka 20 min; 65 MB ny data under `/data/projektion/facit_a2t/` (`konservering:Inflode25/` och `kvartar/konservering:Inflode25/`).

## Vad som kördes

- `utan_matchning_kontroll.py tabell`: domarens tabell för `validering_gles` (kedja, kedja_utan_matchning, persistens) ur summorna från 2026-11-04, cirka 3 min. Ingen ny data.
- `utan_matchning_kontroll.py om --dag 2021-05-17 --ut /tmp/k0013`: ett valideringsdygn, 8 utgåvor (00, 03, ..., 21 UTC), 222 s, till `/tmp` (inte `/data`). Bit för bit lika.
- `facit_a2t.py kedja --system konservering:Inflode25` på de 15 träningsdagarna i 0006 (två processer, 6 utgåvor per dygn), sedan `summera` och `facit_a2t_rand.py`. De två första körningarna stoppades av verktygets standardgräns på 10 min efter 2 och 1 dygn; de färdiga dygnen hoppades över vid omstarten och resten kördes klart.
- `uv run pytest`: 214 gick igenom (5 min 14 s).
- Disk: 3 668 MB ledigt vid start, 3 572 MB i slutet (en del av skillnaden är driften).

## Filerna

- `experiments/projektion/utan_matchning_kontroll.py` (ny): tabellen ur de sparade summorna utan att skriva över resultatfilen, och omräkningen av ett dygn med jämförelse.
- `experiments/projektion/facit_a2t_rand.py`: valet `--system` (ett annat systems kvartar mot radarns kvartar, med kedjans rand och rutor). Utan val som förut.
- `experiments/projektion/facit_a2t_varianter_tabell.py`: namnet på resultatfilen och varianterna som argument. Utan argument som förut.
- `experiments/projektion/results/facit_a2t_inflode25.json` (ny).
- Rapporten, `MAL.md` (frågan om testdelen) och `IDEER.md` (de två posterna).

## Nästa steg

1. **Testdelen (beslut e) kan köras utan att vänta på mål 2**: båda ändringarna av kedjan som skulle bedömas före den är redan bedömda på valideringen och fällda (utan matchning av blockmaxet och formen, `Inflode25` av ytan ≥ 10 och 20 mm/h vid 15 och 30 min). Testdelen körs för `kedja` som beslutat.
2. **Inflödet utan överskottet tidigt** är fortfarande den kandidat i kedjan som har mest att ge: hälften av förlusten vid randen, CSI och FSS bättre mot både radarn och A2T. Det som fäller den sitter i platskartans förstärkning de första 30 minuterna. En idé som inte är prövad: rampa in inflödet med ledtiden (ingen fyllning de första 30 minuterna, full från 1 h), eller låta platskartan inte verka i de fyllda rutorna utanför täckningen. Väljs på träningen (`snabb`, sedan `traning`) och bedöms en gång på valideringen, och måste i så fall bedömas före testdelen eller vänta på en ny testdel.
3. Planeraren bör kontrollera `experiments/projektion/resultat/` och natt-rapporterna innan en ändring av kedjan sätts på valideringen, så att den inte bedöms två gånger.

## Frågor till användaren

- Ska `kedja_utan_matchning` in bland testdelens system? Rekommendationen är **nej**: den är fälld på valideringen (blockmaxets 90-percentil säkert sämre vid alla ledtider), och beslut 5 nämner bara kedjan.

Säkerställd förbättring: nej

Status: klar
