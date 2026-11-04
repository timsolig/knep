# knep

Nederbördsprognos för de kommande två timmarna, byggd på SMHI:s öppna radarkomposit. Räknas på en Raspberry Pi var femte minut och visas på GitHub Pages.

```
SMHI radar (GeoTIFF, var 5:e min)
  → Pi: komposit (SMHI, OPERA som reserv, lagrangesk utfyllnad vid bortfall)
  → volymkorrektion mot SMHI:s regnmätare (nivå per plats och månad, svans, veckofaktor)
  → kedjan (Lucas-Kanade på bilder med 15 min mellanrum, extrapolering, fördelningsmatchning, platskarta)
  → sannolikhet för minst 5 och 10 mm/h (tränad modell)
  → PNG-rutor per 5 min, kvart och timme, värdefil för punktserier, manifest.json
  → publish.sh (i driftcontainern): tvingar grenen data till en commit och startar workflowet pages
  → GitHub Actions: web/ från main plus data → GitHub Pages
```

Sidan har tre flikar. **Prognos** är en mosaik med tre kartor sida vid sida: min modell, MET Norges nowcast och SMHI:s SNOW, avgränsade till MEPS-området. Drar eller zoomar man i en karta följer de andra med, och tidsreglaget styr alla tre. Senaste radarbilden kan ligga svagt i bakgrunden under prognoserna. Kartorna finns i tre upplösningar: momentan intensitet var 5:e minut, summa per kvart (som KNEP) och summa per timme (som SNOW). Samma färg betyder samma medelintensitet i alla tre och i alla källor; legenden för summorna är i mm per period, och SNOW, som bara finns per timme, visas som timmens medel även i 5 och 15 min. Ett klick på en karta ger en tidsserie i punkten med radarn, min modell, MET Norges nowcast (5 min) och SNOW (median per timme med min till max i ensemblen), och en tabell med timsummorna sida vid sida. **Händelser** spelar upp namngivna väderhändelser med radarn, kedjans och KNEP-proxyns prognos sedda 30 och 60 min i förväg, i samma tre upplösningar, med risken för kraftig nederbörd och poäng per horisont (ETS, SEDI och volym). **Verifiering** visar hur Tim-KNEP, MET Norge, SNOW och persistens har träffat de senaste 7 eller 30 dygnen, mot radarn och mot regnmätarna (avsnittet Verifiering).

KNEP är inte fri öppen data hos SMHI (realtidsfilerna levereras mot avgift), så den jämförs via proxyn i händelseflikarna.

## GitHub

1. Repot ska vara publikt.
2. Settings → Pages → Source: **GitHub Actions**.
3. Skapa en fine-grained token som bara gäller repot, med Contents och Actions satta till read and write.

## Raspberry Pi

Driften är en container som följer `main` på GitHub. Bilden innehåller bara verktygen (Python, uv, git och kompilatorn för pysteps) och `deploy/drift.sh`; själva koden checkas ut per commit i en Docker-volym. Pi:n behöver Docker, `deploy/compose.yaml` och token.

```sh
mkdir -p ~/knep-drift && cd ~/knep-drift
curl -fsSLO https://raw.githubusercontent.com/timsolig/knep/main/deploy/compose.yaml
echo "GITHUB_TOKEN=github_pat_..." > .env && chmod 600 .env
docker compose up -d --build
docker compose logs -f
```

Var femte minut, före cykeln, frågar driften GitHub vilken commit `main` pekar på. En ny commit checkas ut, installeras med `uv sync` (någon minut ur paketcachen, längre när `uv.lock` ändras och pysteps kompileras om), hämtar sina låsta modeller ur `models/models.json` och provas med `knep --help`. Sedan kör driften den. En sammanslagning till `main` är alltså i drift inom fem minuter, utan att något görs på Pi:n.

Misslyckas den nya versionens första cykel går driften tillbaka till den förra och provar den nya igen efter en timme, eller direkt om `main` ändras. Det syns i loggen som `drift: första cykeln med ... misslyckades`. De tre senaste versionerna ligger kvar i volymen `releases`.

Bilden behöver bara byggas om när `deploy/Dockerfile` eller `deploy/drift.sh` ändras, med samma `docker compose up -d --build`. Radarbilderna, modelltillståndet och insamlingen mot regnmätarna ligger i volymen `cache` och överlever både versionsbyten och ombyggen. Utan token i `.env` räknas prognoserna men publiceras inte. `KNEP_BRANCH=gren` i `.env` låter driften följa en annan gren, för att prova något innan det slås ihop.

## Händelser

Händelserna byggs en gång på Pi:n ur SMHI:s arkiv och checkas in under `web/cases/` på `main` (via en gren och pull request), eftersom grenen `data` skrivs om var femte minut.

```sh
uv run knep-case list                     # kända händelser: Hans 2023, Anna 2026, Gävle 2021
uv run knep-case build hans-2023          # hämtar cirka 300 bilder, kör kedjan var 5:e minut
uv run knep-case index                    # skriver web/cases/index.json
```

En ny händelse läggs till i `EVENTS` i `src/knep/cases.py` med namn, tidsfönster i UTC och en kort text med källa. Kedjan körs var 5:e minut över hela fönstret, så ett dygn tar några timmar på en Pi 5; kör det gärna över natten.

## Jämförelsekällorna i mosaiken

Driften hämtar MET Norge och SNOW som kartor (`src/knep/compare.py`) och ritar dem med samma färgskala som min modell, i `out/data/met/` och `out/data/snow/`. Manifestet får dem under `compare`.

- **MET Norge**: radarnowcasten på thredds.met.no, 24 steg om 5 min på 1 km. Hela filen är 73 MB och servern komprimerar inte utsnitt, så var 4:e punkt hämtas via OPeNDAP (4 km, cirka 22 MB per lopp), och ett nytt lopp högst var 15:e minut. Det blir cirka 2 GB per dygn.
- **SNOW**: SMHI:s median per timme ur ensemblen, som hela fält på MEPS rutnät (2,5 km) utan koordinater, cirka 35 KB per timme. Rutnätet avgränsar också kartan på sidan.

Hämtningen tar cirka 15 sekunder när ett nytt MET-lopp hämtas och någon sekund annars. Fallerar en källa saknas den bara den cykeln, och prognosen publiceras ändå. `--no-compare` stänger av hämtningen, och historiska körningar (`--time`) hämtar inget eftersom källorna bara har senaste loppet.

## Verifiering

`verify.py` räknar på Pi:n, i varje cykel men med det tunga arbetet en gång i timmen:

1. Radarns analyser läggs på ett rutnät om 4 km (radarns 2 km i block om 2). Ett block räknas som uppmätt bara om alla dess pixlar kom från SMHI, OPERA eller radarvolymer, alltså inte från utfyllnad med flyttad analys, och timsumman sparas när minst 11 av 12 bilder finns.
2. Första cykeln i timmen sparas utgåvan: timsummorna för +1 till +5 h från Tim-KNEP, MET Norges och SNOW:s senaste lopp (som `compare.py` sparar som tal i `cache/verif/src/`) och persistens, radarns senaste timme.
3. När mätarna för utgåvans sista timme har kommit, 2,5 h efter den, räknas kontingenstabeller för 0,1, 0,5, 1, 2 och 4 mm, kontinuerliga summor och FSS (0,5, 1 och 4 mm på 4, 20 och 60 km) mot radarn, och tabeller mot SMHI:s timsummor (parameter 7) i blocket där mätaren står. Radarn verifieras också mot mätarna, som jämförelse. Allt summeras per dygn (UTC) i `cache/verif/days/`.
4. `verif.json` får måtten (ETS, CSI, POD, FAR, frekvensbias, HSS, PSS, MCC, SEDI, FSS, MAE, RMSE, medelfel, korrelation och volymkvot) för 7 och 30 dygn med 90 %-intervall ur bootstrap över dygnen, och skillnaden mot Tim-KNEP räknad på exakt samma rutor och timmar som den andra modellen. Där finns också de råa summorna per dygn, kartan över området (`verif/area.png`), mätarna som använts och hur gamla MET Norges och SNOW:s lopp var vid utgåvan.

Tim-KNEP utgår från samma radaranalys som är facit, så mot radarn gynnas Tim-KNEP de första timmarna. Mätarna är oberoende och står därför bredvid. `--no-verify` stänger av allt.

## Radarbortfall

Kompositen (`src/knep/composite.py`) fyller pixlar som brukar ha data men saknar data nu: först med OPERA-kompositen om `--fallback` är satt, sedan med förra analysen flyttad med rörelsefältet. Kvaliteten för flyttade pixlar avtar med tiden och efter 90 min släpps de. Sidan visar vilka svenska radarer som saknas. För en egen komposit av enskilda radarvolymer finns `sources.volume_composite`, som hämtar ODIM-volymer från EUMETNET:s öppna radardata.

## Volymkorrektion mot regnmätarna

Radarns årsvolym rättas mot SMHI:s automatiska stationer (parameter 7, timsumma). Metoden följer BALTEX-justeringen (Michelson m.fl. 2000, SMHI RMK 90) men som klimatologi, i `src/knep/bias.py`:

- **Nivå**: log K = a + b·h + c·h² per månad, där h är höjden på den lägsta radarstrålen, plus en restkarta med Barnes-viktning för det som inte beror på höjden (blockering, klotterfilter). Faktorn beror inte på intensiteten, så den kan inte trycka ned toppar för att få summan rätt.
- **Svans**: efter nivån jämförs timkvantilerna 99 till 99,95 % för mätare och radar, och radarns svans rättas med R·(R/5)^γ över 5 mm/h.
- **Volymslutning**: nivån per månad justeras sist så att nätets summa stämmer med svanstermen på plats.
- **Veckofaktor**: en faktor för hela nätet de senaste sju dygnen, krympt mot 1 och räknad bara på timmar under 10 mm, så att ett enskilt skyfall inte styr nästa veckas nivå.

Kartan är en tränad modell som alla andra: den skattas ur par av radar och mätare, släpps som en version och låses i `models/models.json`. Den skattas bäst en gång ur arkivet, i utvecklingscontainern där arkivet ligger i `/data`:

```sh
uv run knep-bias gauges --archive                                      # mätarnas timvärden, cirka 170 stationer
uv run knep-bias radar --archive /data --start 2023-01-01 --end 2025-12-31
uv run knep-bias fit --start 2023-01-01 --end 2025-12-31 --grid <en kompositfil.tif> --cv
```

`fit` skriver `models/bias.npz` och visar årsvolym och timkvantiler före och efter, i urvalet och med stationsvis korsvalidering. Ser rapporten bra ut släpps den som `bias-v1` (se Modellversioner).

Driften skriver aldrig över den låsta kartan. Varje cykel sparar den radarns råa värde vid stationerna, en gång i timmen hämtar den mätarna, och kl 03 UTC räknar den två saker i `cache/bias/`: veckofaktorn mot den låsta kartan (`vecka.json`, används direkt) och en kandidat till ny karta ur allt insamlat (`kandidat.npz` och `kandidat.json`). Kandidaten sparas först när det finns 60 dygn med par, eftersom en karta ur färre dygn bara täcker några månader och en enda säsong. Utan släppt karta körs alltså driften okorrigerad tills man antingen släpper en karta ur arkivet eller släpper kandidaten när den finns. `--no-bias` stänger av både korrektionen och insamlingen.

## Extremerna

`models/extremes.pkl` tränas med `experiments/extremes.py` på öppna fall med kraftig nederbörd och ger sannolikheten för minst 5 och 10 mm/h per pixel. Utan filen körs kedjan utan sannolikheter. Kedjans eget fält skalas inte om mot sannolikheterna: det förlorade ETS, SEDI och FSS vid 10 mm/h i verifieringen. Modellen är beroende av scikit-learn-versionen i `pyproject.toml`; byts versionen, träna om på Pi:n (`experiments/README.md`).

## Modellversioner

De tränade modellerna (`extremes.pkl`, `bias.npz`) checkas inte in. De ligger som tillgångar i GitHub Releases, en release per version med träning och verifiering i texten (`models/release-notes/`), och `models/models.json` låser tagg och sha256. Repot anger alltså exakt vilken modell som gäller, historiken syns under Releases, och manifestet på sidan visar vilka versioner som räknade varje prognos.

```sh
uv run knep-models fetch          # hämta de låsta versionerna till models/
uv run knep-models status         # vad som är låst och om filerna stämmer
deploy/release_model.sh extremes extremes-v2 models/extremes.pkl models/release-notes/extremes-v2.md
```

`release_model.sh` laddar upp filen med `gh release create` och låser den. Låsningen checkas in på en gren med release-texten och går in via pull request, som all annan kod. En modell byts bara om den slår den förra i verifieringen (`experiments/`). Att gå tillbaka är att låsa en äldre tagg.

## Driftsättning

1. Skapa repot på GitHub (publikt), skjut upp historiken (se nedan) och slå på Pages med källan GitHub Actions. Workflowet `test` kör testerna på varje pull request.
2. Ange repot i `models/models.json` (`"repo": "ägare/knep"`) och släpp den första modellen: `deploy/release_model.sh extremes extremes-v1 models/extremes.pkl models/release-notes/extremes-v1.md`.
3. På Pi:n: hämta `deploy/compose.yaml`, lägg token i `.env` och starta med `docker compose up -d --build` (avsnittet Raspberry Pi ovan). Därefter följer driften `main` av sig själv.
4. Skatta volymkartan ur arkivet och släpp den som `bias-v1`, eller låt driften samla och släpp kandidaten efter 60 dygn.
5. Bygg händelserna (avsnittet Händelser) på en gren och slå ihop dem via pull request.

Workflowet `test` bygger driftens bild på arm64 för varje pull request och installerar grenen i den som driften gör, så ett trasigt bygge syns innan det når `main`.

## Utvecklingsmiljö med Claude Code

`dev/` innehåller en container med Claude Code, GitHub CLI och uv. Den monterar `~/knep` som `/work` och `~/radar-arkiv` som `/data`. Driften ovan är en egen container som följer `main`; `KNEP_BRANCH` i dess `.env` låter den följa en gren i stället.

```sh
cd ~/knep/dev && docker compose up -d --build
docker exec -it knep-dev bash
```

## Utveckla

```sh
uv run pytest                          # syntetiska data, inget nätverk
uv run knep --out web/data             # senaste radarbilden
uv run knep --time 2026-07-14T15:30 --out web/data   # historisk analys
python3 -m http.server -d web 8000     # sidan på localhost:8000
```

Radardata: SMHI och EUMETNET OPERA, CC BY 4.0. Regnmätare och SNOW: SMHI:s öppna data. Nowcast för jämförelse: MET Norge (api.met.no). Testfallen: pysteps-data (FMI, MeteoSwiss, KNMI, RMI).
