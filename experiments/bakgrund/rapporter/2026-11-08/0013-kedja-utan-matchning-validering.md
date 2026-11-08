# Uppgift 0013: kedjan utan fördelningsmatchning på valideringen

Kort: kedjan utan matchning är redan dömd på valideringen (`validering_gles`, 16 dygn, 125 utgåvor, körd 2026-11-04 i natt 1) och domen är **inte bättre**: CSI och FSS blir 0,001 till 0,006 bättre, men blockmaxets 90-percentil är säkert sämre vid alla ledtider (+0,058 till +0,065 i |log kvot|, intervallen +0,033 till +0,094), formen 4 till 8 km säkert sämre (+0,042 till +0,053) och SEDI 10 mm/h säkert sämre vid 15 till 60 min; jag körde inte valideringen en gång till, utan räknade om tabellen ur de sparade summorna och ett dygn bit för bit lika med dagens kod.

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

Säkerställd förbättring: nej

## Inför testdelen

Kedjan utan matchning bör enligt domen **inte** in bland testdelens system; baslinjen `kedja` (med matchningen) står kvar. Det beslutar användaren och står som fråga i rapporten och i `MAL.md`: vill du ändå ha med `kedja_utan_matchning` i testdelen som en jämförelse (inte en kandidat)? Min rekommendation är nej, eftersom den är fälld på valideringen och testdelen bara ska köras för de system som står i beslut 5.

PUNKT2
