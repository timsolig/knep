# 0018 tillväxt och avtagande ur historiken

Del 1 (taket vid 32, 64 och 128 km) och del 2 (kandidat utan facit, `snabb` och `traning`) är gjorda. Disken sist: 2 478 MB ledigt (över 2 000 MB).

## Disken

`df -m /data`: 2 553 MB ledigt vid starten (över 2 000 MB). Summorna är små.

## Del 1: taket vid 32, 64 och 128 km

`TakTillvaxt64` och `TakTillvaxt128` (ärver `TakTillvaxt`, `block_km` som klassvärde) kördes på `snabb` (6 dygn, 48 utgåvor, 4 km, två processer, 548 s respektive cirka 15 processorminuter). Hela tabellerna (med `persistens`) ligger i `/data/projektion/tak_tillvaxt_tabell.md`; siffrorna nedan är skillnaden mot `kedja_om`, positiv är bättre (domarens tabell visar csi och fss med omvänt tecken). Intervallen är 95 % från bootstrap över dygnen och ligger för csi1 och fss1_30 helt över noll i alla celler. Referensvärden för `kedja_om` står i 0017.

| mått | block | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|---|
| csi1 | 32 km | +0,035 | +0,065 | +0,104 | +0,120 | +0,117 | +0,097 |
| csi1 | 64 km | +0,019 [+0,013, +0,026] | +0,034 [+0,021, +0,050] | +0,059 [+0,043, +0,078] | +0,076 [+0,062, +0,092] | +0,079 [+0,068, +0,091] | +0,073 [+0,057, +0,089] |
| csi1 | 128 km | +0,010 [+0,007, +0,014] | +0,016 [+0,009, +0,026] | +0,030 [+0,019, +0,042] | +0,042 [+0,031, +0,054] | +0,048 [+0,038, +0,058] | +0,050 [+0,035, +0,066] |
| fss1_30 | 32 km | +0,013 | +0,040 | +0,099 | +0,169 | +0,195 | +0,200 |
| fss1_30 | 64 km | +0,009 [+0,006, +0,014] | +0,029 [+0,018, +0,048] | +0,075 [+0,049, +0,114] | +0,133 [+0,099, +0,180] | +0,160 [+0,127, +0,206] | +0,173 [+0,136, +0,222] |
| fss1_30 | 128 km | +0,006 [+0,003, +0,010] | +0,017 [+0,010, +0,029] | +0,044 [+0,027, +0,071] | +0,084 [+0,057, +0,120] | +0,106 [+0,081, +0,143] | +0,129 [+0,096, +0,175] |
| csi5 | 32 km | +0,051 | +0,078 | +0,098 | +0,106 | +0,092 | +0,065 |
| csi5 | 64 km | +0,029 | +0,045 | +0,050 | +0,058 | +0,060 | +0,044 |
| csi5 | 128 km | +0,019 | +0,025 | +0,023 | +0,030 | +0,036 | +0,029 |
| fss5_10 | 32 km | +0,044 | +0,099 | +0,162 | +0,217 | +0,218 | +0,165 |
| fss5_10 | 64 km | +0,029 | +0,062 | +0,092 | +0,132 | +0,151 | +0,119 |
| fss5_10 | 128 km | +0,020 | +0,037 | +0,046 | +0,073 | +0,094 | +0,082 |

Blockmax_q90 (skillnaden i |log kvot| mot radarn, negativ är bättre; sämre än `kedja_om` vid 120, 180, 300 min):

| block | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| 32 km | +0,054 | +0,036 | +0,004 | +0,173 (sämre) | +0,233 (sämre) | +0,371 (sämre) |
| 64 km | +0,040 | -0,002 | -0,048 | +0,079 | +0,138 (sämre) | +0,251 (sämre) |
| 128 km | +0,009 | +0,001 | -0,053 | -0,002 | +0,071 | +0,169 (sämre) |

**Andel av luckan till CSI 1** (1 − csi1 för `kedja_om`: 0,266, 0,425, 0,586, 0,729, 0,793, 0,854):

| block | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| 32 km | 13 % | 15 % | 18 % | 16 % | 15 % | 11 % |
| 64 km | 7 % | 8 % | 10 % | 10 % | 10 % | 9 % |
| 128 km | 4 % | 4 % | 5 % | 6 % | 6 % | 6 % |

Tolkning: taket faller ungefär till hälften för varje fördubbling av blocket (32 till 64 km: 55 till 65 % av taket kvar, 64 till 128 km: 50 till 65 %). Vid 128 km, där kvoten knappast kan rätta något lägesfel, återstår ändå 4 till 6 % av luckan, med intervallen helt över noll i csi1 och fss1_30 vid alla ledtider. Det är alltså sant tillväxt och avtagande i stor skala, men bara cirka en tredjedel av 32 km-taket; resten är massa som flyttas mellan block på 32 till 128 km, alltså lägesfel och bruset i facit. Blockmaxet slutar vara säkert sämre först vid 128 km för 120 till 180 min. Prognosens verkliga kvot ur historiken ska alltså förväntas ge en bråkdel av 4 till 6 % av luckan (CSI 1 mm några hundradelar vid 1 till 3 h).

## Del 2: kandidaten utan facit

`experiments/projektion/tillvaxt.py`: klassen `Tillvaxt` (ärver `domare.KedjaOm`) som tar kedjans fält och multiplicerar med exp(s · L · exp(−L/τ)). s är trenden (log-kvot per timme) per block av A0:s blockmedel (box, `block_km`) nu och för 30 och 60 min sedan, den äldre bilden flyttad fram till utgåvan med kedjans rörelsefält (`advect.displacements` och `warp`, bilinjärt, bara rutor där hela källan är giltig, block med under hälften giltiga rutor räknas inte); s = Σ(h·ΔL)/Σ h² med h = 0,5 och 1 h och ΔL = L_nu − L_äldre (eps 0,02 mm/h som i `block_ratio`), s klippt till ±3 per timme. Kvoten (L = kvartens mitt) klipps till [1/2, 2] och utjämnas med gauss sigma = block/4 som `block_ratio`. Där kedjan har noll blir resultatet noll. Inget facit och ingen vädermodell. Klasserna heter `TV_t<τ i min>_b<block i km>`.

Fyra varianter på `snabb` (valda utifrån del 1: 64 km tappar inte mer än hälften jämfört med 32 km, och 128 km är för litet): `TV_t30_b32`, `TV_t60_b32`, `TV_t120_b32`, `TV_t60_b64`. Hela tabellerna i `/data/projektion/tillvaxt_snabb_tabell.md`. Skillnad mot `kedja_om`, positiv är bättre, intervall 95 % (bootstrap över sex dygn), `*` helt på bättre sidan:

| variant | mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|---|
| t30 b32 | csi1 | +0,001 | +0,003* | +0,006* | +0,001* | 0,000 | 0,000 |
| t60 b32 | csi1 | 0,000 | 0,000 | +0,009* | +0,005* | +0,003* | 0,000* |
| t120 b32 | csi1 | 0,000 | −0,001 | +0,008* | +0,005 | +0,005* | +0,001 |
| t60 b64 | csi1 | +0,001* | +0,003* | +0,010* [+0,006, +0,013] | +0,006* [+0,002, +0,012] | +0,002* | 0,000* |
| t30 b32 | fss1_30 | 0,000 | +0,002* | +0,008* | +0,002* | 0,000 | 0,000* |
| t60 b32 | fss1_30 | 0,000 | 0,000 | +0,010* | +0,010* | +0,006* | +0,001* |
| t120 b32 | fss1_30 | 0,000 | −0,001 | +0,008* | +0,009 | +0,008 | +0,003* |
| t60 b64 | fss1_30 | 0,000 | +0,002* | +0,011* [+0,006, +0,017] | +0,011* [+0,004, +0,023] | +0,005* | +0,001* |

Kostnaden: csi5, fss5_10 och `hopp` (spärren: skillnaden mellan utgåvor för samma tid) blir säkert sämre vid 15 till 60 min i alla fyra. För t60 b64: csi5 −0,007 [−0,015, −0,002] vid 15 min, −0,012 vid 30 min, −0,005 vid 60 min; fss5_10 −0,007, −0,016, −0,009; hopp +0,012, +0,034, +0,035 (sämre, 1,45 till 1,48 mot 1,44 för kedja_om). Vid 2 till 5 h är csi5 och fss5_10 lika (inom ±0,006). `blockmax_q90` är inte säkert sämre i någon variant och säkert bättre vid 15 och 30 min för t60 b64 och t30 b32. `persistens` för jämförelse (skillnad mot `kedja_om`, csi1): −0,143, −0,151, −0,108, −0,068, −0,050, −0,036, alltså kandidatens vinst är liten mot hur långt kedjan redan ligger över persistensen (`kedja_om` csi1 0,734 / 0,575 / 0,414 / 0,271 / 0,207 / 0,146; `persistens` 0,590 / 0,424 / 0,306 / 0,204 / 0,157 / 0,110).

**Vald variant: `TV_t60_b64`** (τ = 1 h, block 64 km): bäst csi1 vid 15 till 30 min och 60 min (delat med t120 b32 vid 120 min), bäst fss1_30 vid 30 till 60 min, och minst skada på hopp av de fyra. Skillnaden mellan varianterna är liten (några tusendelar), så valet är svagt. Vinsten är +0,010 CSI 1 mm vid 1 h, cirka 1,7 % av luckan till 1, att jämföra med taket vid 64 km på 10 %: historikens trend fångar ungefär en sjättedel av det som perfekt kvot vid 64 km ger.

Körtid: `forecast_seconds` per utgåva är 4,40 s för `TV_t60_b32` mot 4,28 s för `kedja_om` på `snabb` (4 km), alltså cirka 0,12 s extra. På `traning` (2 km) är det 21,9 s mot 17,8 s, alltså cirka 4 s extra. Det är mer än "någon sekund", men mätningen delade Pi:n med driften och två processer, så den är grov; de 20 gaussfiltren (sigma 8 px vid 2 km) är troligen den största delen och kan sänkas genom att utjämna trenden en gång i stället för kvoten per kvart.

### Den frysta varianten på `traning`

`TV_t60_b64` (inte ändrad efter `snabb`) kördes på 12 av de 28 träningsdagarna (varannan: 2020-02-10, 2020-07-24, 2020-10-07, 2020-12-27, 2021-04-05, 2022-05-21, 2023-01-04, 2023-04-25, 2023-08-02, 2024-01-24, 2024-07-28, 2024-09-26; 96 utgåvor, 2 km), eftersom `kedja_om` och `persistens` också behövde köras för `traning` och tiden inte räckte för alla 28. Valideringen och testdelen är inte rörda. Tabellen: `/data/projektion/tillvaxt_traning_tabell.md`. Skillnad mot `kedja_om`, positiv är bättre:

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 (`kedja_om`) | 0,675 | 0,516 | 0,367 | 0,225 | 0,161 | 0,107 |
| csi1 (skillnad) | +0,001 [−0,000, +0,002] | +0,003* [+0,000, +0,005] | +0,008* [+0,006, +0,010] | +0,006* [+0,004, +0,007] | +0,002* | +0,000* |
| fss1_30 (skillnad) | 0,000 | 0,000 | +0,008* [+0,005, +0,012] | +0,011* [+0,008, +0,015] | +0,006* [+0,004, +0,008] | +0,001* |
| csi5 (skillnad) | −0,004* (sämre) | −0,004 | +0,001 | +0,003* | +0,001* | 0,000 |
| fss5_10 (skillnad) | −0,005* (sämre) | −0,012* (sämre) | −0,004 | +0,005 | +0,003 | +0,001* |
| blockmax_q90 (|log kvot|, negativ är bättre) | −0,021* | −0,070* | −0,078* | −0,012 | −0,002 | −0,001 |
| hopp (spärr, positiv är sämre) | +0,009 (sämre) | +0,027 (sämre) | +0,031 (sämre) | +0,014 (sämre) | | |

Resultatet håller alltså på de andra dagarna: csi1 och fss1_30 är säkert bättre vid 30 min till 5 h (största vinst +0,008 csi1 vid 1 h, +0,011 fss1 vid 2 h), blockmaxet är säkert bättre vid 15 till 60 min och aldrig sämre. Men det är små tal (csi1 +0,8 punkter av 0,367; cirka 1,3 % av luckan till 1 vid 1 h), och kandidaten är säkert sämre på hopp vid 15 min till 2 h (utgåvorna för samma tid hoppar mer, `kedja_om` 1,44 till 1,46 mot 1,45 till 1,49) och på fss5_10 och csi5 vid 15 till 30 min. `persistens` (jämförelse): csi1 0,505 / 0,344 / 0,239 / 0,152 / 0,116 / 0,073, alltså långt under båda.

## Filer

`experiments/projektion/tak.py` (klasserna `TakTillvaxt64`, `TakTillvaxt128`), `experiments/projektion/tillvaxt.py`, `experiments/projektion/tabell_0018.py`.

## Nästa steg

- Trenden bär lite: den fångar cirka en sjättedel av taket vid 64 km (csi1 +0,008 mot +0,059 vid 1 h) och sedan ingenting efter 3 h. Det mesta av taket vid 32 km är lägesfel, inte tillväxt.
- Hoppet mellan utgåvor försämras eftersom trenden varierar från utgåva till utgåva. Pröva trenden utjämnad i tiden (medel över de senaste utgåvornas trender, eller längre bakåt än 60 min) eller dämpad efter osäkerhet (liten kvot där blockmedlet är lågt eller trenden är brusig), så att hopp och csi5 inte försämras.
- Bedömning på `validering` först när hoppet är lagat; som den är ger den inget som väger upp ett säkert sämre hopp. Ingen rekommendation till användaren om drift.
- Köra klart de 16 återstående träningsdagarna är inte motiverat förrän varianten ändrats.

Kort: Trenden ur A0:s blockmedel (64 km, dämpning 1 h) ger bara CSI 1 mm +0,008 [+0,006, +0,010] vid 1 h och FSS 1 mm +0,011 vid 2 h mot `kedja_om` (12 träningsdagar, 2 km; liknande på `snabb`), vilket är cirka en sjättedel av taket vid 64 km (+0,059), taket faller från +0,12 (32 km) via +0,076 (64 km) till +0,042 (128 km) CSI 1 mm vid 2 h, och hopp, csi5 och fss5_10 vid 15 till 60 min blir säkert sämre.
Säkerställd förbättring: nej
Status: klar
