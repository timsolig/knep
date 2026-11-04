# knep

Nederbördsnowcast 0 till 5 h från SMHI:s radarkomposit. Körs på en Raspberry Pi (arm64, ingen GPU) var femte minut, och en cykel ska bli klar på under två minuter. Resultatet publiceras som statiska filer på GitHub Pages.

## Kommandon

- `uv sync` installerar
- `uv run pytest` kör testerna (syntetiska data, inget nätverk)
- `uv run knep --time 2026-07-14T15:30 --out web/data` kör en historisk analys mot SMHI:s arkiv (finns från 2008)
- `python3 -m http.server -d web 8000` visar sidan lokalt

## Struktur

- `src/knep/radar.py` hämtning och avkodning. GeoTIFF 0..255 i EPSG:3006, dBZ = 0,4 · v − 30, 0 = inget eko, 255 = utanför täckning, Z = 200 R^1,5
- `src/knep/model.py` modellen. `Chain.run(obs, tid, steg, tillstånd)` är kedjan (rörelse, extrapolering, fördelningsmatchning, platskarta, sannolikheter för kraftig nederbörd); `nowcast(obs, steps)` är referensen. Tillståndet (senaste timmens analyser och 30-minutersprognoser) sparas i `cache/state/`
- `src/knep/seamless.py` och `nwp.py` MEPS rättad mot radarn och blandad med kedjan, så att prognosen räcker 5 h (standard; `--no-seamless` stänger av). Bara i realtid, eftersom MEPS bara finns för senaste körningen. Sannolikheterna för kraftig nederbörd gäller de första 2 h (`--prob-hours`), som extremmodellen är kalibrerad för
- `src/knep/extremes.py` särdrag och sannolikheter som delas av drift och träning; modellen ligger i `models/extremes.pkl`
- `src/knep/bias.py` volymkorrektion mot SMHI:s regnmätare (`knep-bias`); kartan ligger i `models/bias.npz`, underlaget, veckofaktorn och kandidaten till ny karta i `cache/bias/`
- `src/knep/models.py` modellversioner (`knep-models`): filerna ligger i GitHub Releases, `models/models.json` låser tagg och sha256; nya versioner med `deploy/release_model.sh`
- `src/knep/composite.py` och `sources.py` kompositen: SMHI, OPERA och enskilda radarvolymer som reserv, lagrangesk utfyllnad vid bortfall
- `src/knep/compare.py` MET Norges nowcast (thredds, OPeNDAP med 4 km) och SMHI:s SNOW (multipoint på MEPS rutnät) som kartor till mosaiken, under `compare` i manifestet
- `src/knep/gauges.py` SMHI:s regnmätare till sidan (kvart, parameter 14, och timme, parameter 7): bara senaste timmen finns för alla stationer, så varje cykel lägger till den i `gauges.json` och behåller 12 h. SMHI lägger ut värdena ungefär en timme efter radarn
- `src/knep/runs.py` tidigare utgåvor: första cykeln i varje timme sparas prognosernas timsummor (Tim-KNEP, MET Norge, SNOW) i `runs/` i 12 h (`--runs`) och listas under `runs` i manifestet. Sidan jämför dem med radarns timsummor i `hist/`, som är facit
- `src/knep/verify.py` verifieringen till fliken Verifiering: första cykeln i varje timme sparas Tim-KNEP:s, MET Norges, SNOW:s och persistensens timsummor för +1 till +5 h på 4 km (radarns rutnät i block om 2) i `cache/verif/pending/`; när mätarna har kommit (2,5 h efter sista timmen) räknas kontingenstabeller, kontinuerliga summor och FSS mot radarn (bara uppmätta rutor) och mot regnmätarna, per dygn i `cache/verif/days/` (35 dygn). `verif.json` har 7 och 30 dygn med 90 %-intervall (bootstrap över dygnen), skillnaden mot Tim-KNEP på samma urval, råa summor per dygn och underlaget (område, mätare, loppens ålder). `compare.py` sparar jämförelsekällornas timsummor som tal i `cache/verif/src/`; `--no-verify` stänger av
- `src/knep/cases.py` namngivna händelser (`knep-case`), skriver till `web/cases/`
- `src/knep/render.py` omprojicering till EPSG:3857, PNG per ruta i 5 min, kvart och timme, värdefil (`values.bin.gz`) och manifest.json; radaranalysen 12 h bakåt ritas en gång per bild till `hist/` med tiden i namnet och listas under `history` i manifestet (`--back`)
- `web/index.html` sidan med flikarna Prognos (kartorna fyller skärmen med tidslisten, panelen och legenden ovanpå; en karta per modell, Tim-KNEP, MET Norge, SNOW och varje ny källa under `compare` i manifestet, som följer varandra och avgränsas till MEPS-området; mätare, punktstaplar, värdet under markören och regnytan i utsnittet ur kartbildernas palett; en tidigare utgåva visas per timme med radarns kontur som facit och FSS per ledtid mot persistens; en förklaring visas första gången och med frågetecknet), Händelser och Verifiering (måtten per ledtid och dygn, skillnaden mot Tim-KNEP och underlaget, ur `verif.json`); Leaflet från cdnjs, ingen byggkedja; punktserien hämtar MET Norge och SMHI SNOW direkt från webbläsaren (SNOW:s punktingång; kartorna tar multipoint-ingången på Pi:n). Förklaringen i sidan (`#intro`) ska följa med när något på sidan ändras; höj `INTRO` så att den visas igen
- `deploy/` driften som en container: `Dockerfile` (bara verktygen), `compose.yaml`, `drift.sh` (följer `main` och installerar varje ny commit, med återgång om den inte fungerar), `cycle.sh` (en cykel) och `publish.sh` som tvingar grenen `data`
- `.github/workflows/pages.yml` slår ihop `web/` och grenen `data` och publicerar
- `experiments/` jämförelsen mot en KNEP-proxy på öppna radarfall, med resultat i `experiments/results/`. Kör om den innan en ändring av modellen tas in

## Mål

pysteps är bara referens, och modellen behöver inte likna KNEP, MET Norge eller annan radarextrapolering. Metoden är fri så länge den slår referenserna i verifieringen och går att köra på Pi:n. Det som särskilt ska lösas är terrängen: nederbörd som är bunden till topografin ska inte advekteras bort. Fältens form är lika viktig som punktvisa mått, och prognoser för samma tid från på varandra följande körningar ska inte hoppa. Indata är öppna data (radar, satellit, observationer, en öppen höjdmodell).

## Miljö

Claude Code körs i containern i `dev/`. Repot ligger i `/work` och radararkivet i `/data`. Driften går på värden i containern från `deploy/compose.yaml` och följer `main` av sig själv (en sammanslagning är i drift inom fem minuter), så ändringar går via grenar och pull requests, aldrig direkt mot driften.

## Regler

- En ny modell ersätter baslinjen bara om den slår den i verifieringen på ett fryst testset (FSS och CSI per ledtid).
- Tränade modeller checkas aldrig in; de släpps i GitHub Releases och låses i `models/models.json`.
- Håll beroendena få och installerbara på arm64.
- Text i gränssnitt och dokumentation skrivs på svenska, utan tankstreck som skiljetecken.
