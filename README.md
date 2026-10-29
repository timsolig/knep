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

Sidan har två flikar. **Prognos** är en mosaik med tre kartor sida vid sida: min modell, MET Norges nowcast och SMHI:s SNOW, avgränsade till MEPS-området. Drar eller zoomar man i en karta följer de andra med, och tidsreglaget styr alla tre. Senaste radarbilden kan ligga svagt i bakgrunden under prognoserna. Kartorna finns i tre upplösningar: momentan intensitet var 5:e minut, summa per kvart (som KNEP) och summa per timme (som SNOW). Samma färg betyder samma medelintensitet i alla tre och i alla källor; legenden för summorna är i mm per period, och SNOW, som bara finns per timme, visas som timmens medel även i 5 och 15 min. Ett klick på en karta ger en tidsserie i punkten med radarn, min modell, MET Norges nowcast (5 min) och SNOW (median per timme med min till max i ensemblen), och en tabell med timsummorna sida vid sida. **Händelser** spelar upp namngivna väderhändelser med radarn, kedjans och KNEP-proxyns prognos sedda 30 och 60 min i förväg, i samma tre upplösningar, med risken för kraftig nederbörd och poäng per horisont (ETS, SEDI och volym).

KNEP är inte fri öppen data hos SMHI (realtidsfilerna levereras mot avgift), så den jämförs via proxyn i händelseflikarna.

## GitHub

1. Repot ska vara publikt.
2. Settings → Pages → Source: **GitHub Actions**.
3. Skapa en fine-grained token som bara gäller repot, med Contents och Actions satta till read and write.

## Raspberry Pi

Driften är en enda container som innehåller allt: beroendena (pysteps kompileras när bilden byggs), de låsta modellerna ur `models/models.json` och en slinga som räknar och publicerar en prognos var femte minut. Bilden byggs direkt från `main` på GitHub, så Pi:n behöver bara Docker, `deploy/compose.yaml` och token.

```sh
mkdir -p ~/knep-drift && cd ~/knep-drift
curl -fsSLO https://raw.githubusercontent.com/timsolig/knep/main/deploy/compose.yaml
echo "GITHUB_TOKEN=github_pat_..." > .env && chmod 600 .env
docker compose up -d --build
docker compose logs -f
```

Första bygget tar en stund eftersom pysteps kompileras. Sedan körs en cykel direkt och därefter två minuter efter varje femminutersbild. Utan token i `.env` räknas prognoserna men publiceras inte, vilket går bra för att prova. Radarbilderna, modelltillståndet och insamlingen mot regnmätarna ligger i Docker-volymen `cache` och överlever omstarter och uppdateringar. Containern startar om av sig själv efter strömavbrott.

En uppdatering till senaste `main`, med nya modellversioner, är samma kommando:

```sh
cd ~/knep-drift && docker compose up -d --build
```

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
3. På Pi:n: hämta `deploy/compose.yaml`, lägg token i `.env` och starta med `docker compose up -d --build` (avsnittet Raspberry Pi ovan).
4. Skatta volymkartan ur arkivet och släpp den som `bias-v1`, eller låt driften samla och släpp kandidaten efter 60 dygn.
5. Bygg händelserna (avsnittet Händelser) på en gren och slå ihop dem via pull request.

En uppdatering av driften är `docker compose up -d --build` i `~/knep-drift`. Workflowet `test` bygger också driftens bild på arm64 för varje pull request, så ett trasigt bygge syns innan det når Pi:n.

## Utvecklingsmiljö med Claude Code

`dev/` innehåller en container med Claude Code, GitHub CLI och uv. Den monterar `~/knep` som `/work` och `~/radar-arkiv` som `/data`. Driften ovan är en egen container byggd från `main`; `KNEP_SOURCE=.. docker compose up -d --build` i `deploy/` bygger den i stället från en klon, för att prova en gren.

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
