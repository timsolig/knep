# 1 Inventering: källor, träningsdagar och plan för natten

## Vad jag gjorde

1. Läste `src/knep/composite.py`, `src/knep/sources.py`, `experiments/outage.py`, `experiments/sverige/data.py` och hur `src/knep/cli.py` använder kompositen i drift.
2. Kartlade vad som finns lokalt och i de öppna arkiven för historiska timmar (provade arkiven direkt).
3. Valde 28 träningsdagar med ett skript (`experiments/bortfall/valj_traning.py`) och frös dem i `experiments/bortfall/traning.json`.
4. Skrev `experiments/bortfall/hamta.py`, som hämtar radar, MEPS och regnmätare för träningsdagarna (mätarna även för valideringsdagarna), och startade den i bakgrunden.

Inga tidigare rapporter fanns för i natt.

## Kompositen i drift (så som den är i dag)

`cli.py` bygger analysen bild för bild: SMHI:s komposit; där den saknar data och pixeln brukar ha data (`GapState.expected >= 0,5`) läggs OPERA-kompositen på, sedan en egen komposit av upp till fyra närmaste volymer med räckvidd 320 km (de radarer som `missing_radars` säger är nere undantas), och sist `fill_gaps`: förra analysen flyttad med rörelsen, kvalitet exp(−ålder/30 min), släpps efter 90 min. Driften kör `fill_gaps` utan `smooth`. `experiments/outage.py` är det gamla experimentet: syntetiska fall ur `generate.py`, en skiva med radien 100 km släckt i en timme, ETS i hålet och prognosens ETS/FSS efteråt.

## Källor för historiska timmar

| Källa | Finns historiskt | Var | Anmärkning |
|---|---|---|---|
| SMHI:s komposit, 5 min, 2 km | ja, från 2008 | SMHI:s öppna API, lokalt i `/data/radar/` | ca 19 MB per dygn. Lokalt fanns 76 dygn (dagar.json med grannar) före i natt |
| MEPS deterministisk, timsummor | ja, körningarna 00/06/12/18 alla år (2023 även var 3:e h) | MET Norges thredds `meps25epsarchive`, lokalt `/data/meps/` | ca 2,5 MB per körning (14 h, float16). 2019 på ett äldre rutnät, därför inga träningsdagar från 2019 |
| Regnmätare, timme (parameter 7) | ja | SMHI metobs `corrected-archive`, en CSV per station | 238 stationer (168 aktiva), ca 0,4 MB per station att ladda ner |
| Regnmätare, kvart (parameter 14) | ja, från 1995 | samma | 210 stationer (150 aktiva), ca 0,6 MB per station |
| OPERA-kompositen (DBZH, ACRR, RATE) | ja, från 2012, var 15:e min | EUMETNET S3 `openradar-archive` | ca 3 MB per bild (DBZH h5). **Se nedan: kan inte användas ärligt i simulerade bortfall** |
| Enskilda radarvolymer | bara från januari 2025 (2024-12-31 finns bara OPERA) | `openradar-archive` | SE och FI som `SCAN` (en fil per elevation), NO och DK som `PVOL` |
| SNOW (SMHI) | bara de senaste dygnen som `snow_samla.py` samlat | `/data/snow/` | inget arkiv, oanvändbart för historiska fall |
| MNWC | nej | | inte öppen data (se `experiments/sverige/README.md`) |

### Två saker att veta om reservlagren

1. **OPERA innehåller den släckta radarn.** OPERA-kompositen bygger på samma svenska radarer. Simulerar vi att en svensk radar är nere ser OPERA den ändå, så OPERA i hålet vore fusk. Det realistiska fallet för OPERA är när SMHI:s komposit saknas men radarerna fungerar (eller när en svensk radar saknas i SMHI:s komposit men inte i OPERA), och det kan inte simuleras ur arkivet utan facit från en tredje källa. Förslag: OPERA lämnas utanför systemen i natt; i rapporterna står det som en begränsning.
2. **Volymlagret i drift hittar inga svenska eller finska radarer.** `sources.fetch_pvol` letar under `.../<site>/PVOL/`, men SE och FI publicerar `SCAN` (`sevax@20251030T0000@0.5@DBZH_TH_VRADH.h5`), både i `openradar-24h` (kollat 2026-11-03) och i arkivet. Bara norska och danska volymer används alltså i dag. Det är ett fel i driften, inte i natt. Rättningen är liten (leta även under `SCAN/`, ta lägsta elevationens fil) men rör `src/knep/sources.py` och behöver ett test; jag har inte gjort den eftersom den inte behövs för experimenten och påverkar driften när den mergas. Tas upp i sammanfattningen.

För simulerade bortfall är alltså de ärliga källorna: SMHI-radarn utanför hålet (även tidigare bilder), MEPS (rättad mot radarn utanför hålet), regnmätarna (som kontroll, och möjligen som källa, men de kommer ungefär en timme sent i realtid), och för dagar från 2025 grannländernas volymer med förlängd räckvidd. Uppgift 2 definierar hålet som där ingen annan radar i `composite.RADARS` når inom 240 km, så grannradarerna når per definition bara hålets kant med förlängd räckvidd.

## Träningsdagarna

`experiments/bortfall/valj_traning.py` väljer ur `/data/sverige/kandidater.json` (radarn kl 00, 06, 12, 18 var 3:e dag 2019 till 2025) med reglerna:

- 2020 till 2025 (MEPS-rutnätet), alla fyra proven finns, våt yta minst 5 % i medel
- aldrig en dag i `dagar.json` eller inom två dygn från en sådan. Skriptet läser bara fältet `day` för alla dagar i `dagar.json` för att kunna utesluta dem; ingen data från testdagarna har lästs eller hämtats
- sju dagar per årstid, regnigast först; på sommaren varannan efter ytan med kraftigt regn
- högst två per år och årstid, minst sex dygn mellan två träningsdagar

Resultat, 28 dagar (7 per årstid, 2020: 7, 2021: 3, 2022: 2, 2023: 6, 2024: 7, 2025: 3):

| Dag | Årstid | Våt yta | Kraftig yta |
|---|---|---|---|
| 2020-02-10 | vinter | 0,089 | 0,046 |
| 2020-05-01 | vår | 0,070 | 0,007 |
| 2020-07-24 | sommar | 0,094 | 0,008 |
| 2020-08-29 | sommar (kraftig) | 0,066 | 0,023 |
| 2020-10-07 | höst | 0,099 | 0,011 |
| 2020-10-22 | höst | 0,100 | 0,010 |
| 2020-12-27 | vinter | 0,071 | 0,001 |
| 2021-01-23 | vinter | 0,073 | 0,016 |
| 2021-04-05 | vår | 0,065 | 0,003 |
| 2021-05-11 | vår | 0,070 | 0,014 |
| 2022-05-21 | vår | 0,061 | 0,016 |
| 2022-12-20 | vinter | 0,076 | 0,007 |
| 2023-01-04 | vinter | 0,083 | 0,006 |
| 2023-03-17 | vår | 0,066 | 0,003 |
| 2023-04-25 | vår | 0,069 | 0,006 |
| 2023-07-12 | sommar (kraftig) | 0,086 | 0,028 |
| 2023-08-02 | sommar | 0,106 | 0,013 |
| 2023-11-22 | höst | 0,089 | 0,002 |
| 2024-01-24 | vinter | 0,087 | 0,013 |
| 2024-04-14 | vår | 0,054 | 0,012 |
| 2024-07-28 | sommar (kraftig) | 0,061 | 0,024 |
| 2024-08-09 | sommar | 0,100 | 0,012 |
| 2024-09-26 | höst | 0,098 | 0,015 |
| 2024-11-25 | höst | 0,113 | 0,006 |
| 2024-12-19 | vinter | 0,075 | 0,005 |
| 2025-06-23 | sommar | 0,102 | 0,014 |
| 2025-09-15 | höst | 0,111 | 0,019 |
| 2025-10-24 | höst | 0,087 | 0,007 |

Tre dagar från 2025 har grannländernas volymer i arkivet, så ett litet volymexperiment går att göra. Urvalet är committat och ska inte ändras.

## Hämtningen

HAMTNING_STATUS

`hamta.py` hoppar över det som finns och kan köras om. Den avbryts om `/data` har mindre än 2 GB ledigt eller om processen skrivit mer än `--max-gb` (0,75 GB för radar och mätare, 0,35 GB för MEPS, alltså högst 1,1 GB av nattens 2 GB). Radarn hämtas med fyra samtidiga anrop men högst 2 anrop/s totalt (`sverige/data.Throttled`), och svarstiden ger ungefär 1 bild/s, så alla 28 dygn tar runt 2,5 h.

```sh
uv run python experiments/bortfall/hamta.py kontroll                      # vad som finns
uv run python experiments/bortfall/hamta.py radar matare --logg /data/bortfall/hamta_radar.log
uv run python experiments/bortfall/hamta.py meps --logg /data/bortfall/hamta_meps.log
```

Loggar: `/data/bortfall/hamta_radar.log`, `/data/bortfall/hamta_meps.log`. Mätarna sparas som `/data/bortfall/matare/p7.npz` och `p14.npz` (station, lat, lon, tid i unix-sekunder för periodens slut, mm), för tränings- och valideringsdagarna från 90 min före dygnet till 5 h efter.

## Plan för resten av natten

Datatak: kvar efter den här uppgiften är ungefär 0,9 GB av nattens 2 GB. **Uppgift 2 ska därför inte spara radarbilderna igen** utan bara fallens beskrivning (dag, starttid, längd, släckta radarer, hålets mask komprimerad, MEPS-körning) och läsa facit ur `/data/radar/` vid behov. Annars spräcks taket.

2. **Bortfallsfall.** Hålet: pixlar inom 240 km från de släckta radarerna och utanför 240 km från alla andra radarer i `composite.RADARS` (bara de som faktiskt bidrar till SMHI:s komposit vore riktigare, men de grannländska är med i RADARS och ger ett mindre, försiktigare hål). Start när minst ett par procent av hålet är vått, längd dragen ur {30 min, 1, 2, 3, 6 h}, 30 till 60 min av riktig radar före som uppvärmning. Fallen dras med fast frö, ett antal per dag, med typ ett fall per dag och radarkombination för att undvika att samma regn räknas många gånger. Kontrollera först att alla träningsdagar har radarn hämtad (`hamta.py kontroll`), och kör om hämtningen om den inte blev klar. Valideringsdagarna har redan radar och MEPS lokalt.
3. **Domaren.** Måtten per ålderklass (0 till 30, 30 till 90, 90 till 360 min). Bootstrap över dagar, inte fall, eftersom fall samma dag är beroende. Sömmen som skillnaden i gradientens storlek i ett band på några pixlar längs kanten. Baslinjerna hål, fylld och utjämnad. Obs: `fill_gaps` släpper pixlarna efter 90 min (`max_age`), så för åldern 90 till 360 min är fylld lika med hål; det är så driften fungerar och ska inte ändras i domaren, men det ska stå i tabellen.
4. **MEPS i hålet.** Rättning mot radarn utanför hålet som i `seamless.py` (fördelning och volym), vikt mellan flyttad analys och MEPS som funktion av åldern, vald på träningen. Tänk på att MEPS-körningen ska vara tillgänglig 2,5 h efter körtiden (`nwp.available`), samma regel som i `experiments/sverige`.
5. **Inlärd blandning.** HistGradientBoosting per pixel på ett urval av pixlar (inte alla, minnet). Höjdmodell: ingen finns lokalt vad jag har sett; uppgift 5 får se om en liten öppen DEM går att hämta inom taket (Copernicus GLO-90 över Sverige är några hundra MB, en grövre 1 km räcker och är liten).
6. **Ablation och söm, och prognosen efteråt** med kedjan som i `experiments/outage.py`, men på de riktiga fallen i stället för de syntetiska.
7. **Sammanfattning**, inklusive de två fynden ovan (OPERA, `SCAN`).

Regnmätarna: oberoende kontroll av volymen i hålet i uppgift 3 och 6 (timsummor från p7, kvart från p14). Gauges i realtid kommer cirka en timme efter radarn, så som källa duger de bara för bortfall som varat mer än en timme.

## Filer

- `experiments/bortfall/valj_traning.py` (nytt)
- `experiments/bortfall/traning.json` (nytt, fryst)
- `experiments/bortfall/hamta.py` (nytt)
- `experiments/natt/rapporter/2026-11-03/1-inventering.md`

Inga ändringar i `src/knep/`. `uv run pytest`: 56 passerade.

Status: STATUS_RAD
