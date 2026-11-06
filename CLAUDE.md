# knep

Nederbördsnowcast 0 till 5 h från SMHI:s radarkomposit. Körs på en Raspberry Pi (arm64, ingen GPU) var femte minut, och en cykel ska bli klar på under två minuter. Resultatet publiceras som statiska filer på GitHub Pages.

## Kommandon

- `uv sync` installerar
- `uv run pytest` kör testerna (syntetiska data, inget nätverk)
- `uv run knep --time 2026-07-14T15:30 --out web/data` kör en historisk analys mot SMHI:s arkiv (finns från 2008)
- `python3 -m http.server -d web 8000` visar sidan lokalt

## Struktur

Koden är delad i två produkter och det som bygger sidan av dem. `cli.py` kör en cykel i ordningen analys, prognos, produkter.

**Analysen** (`src/knep/analys/`): nederbörden som den är nu. `analys.bygg(t0, ...)` ger en `Analys` (tider, fält i mm/h, rutnät, källor, saknade radarer); prognosen läser bara den.

- `src/knep/analys/radar.py` hämtning och avkodning. GeoTIFF 0..255 i EPSG:3006, dBZ = 0,4 · v − 30, 0 = inget eko, 255 = utanför täckning, Z = 200 R^1,5
- `src/knep/analys/composite.py` och `sources.py` kompositen: SMHI, OPERA och enskilda radarvolymer som reserv, lagrangesk utfyllnad vid bortfall
- `src/knep/analys/a1.py` A1, analysens nästa nivå: varje 5-minutersintervall interpolerat minut för minut längs kedjans rörelsefält, så att kvarts- och timsummor inte blir pärlband. Intervallen räknas en gång och sparas i `cache/state/a1_*.npz`, och ritas som radaranalysen bakåt till `a1/`, under `levels` i manifestet (`a0` är `history`, `a2` är ännu tom). Nivåerna A0 (analysen som den är), A1 och A2 (rättad mot mätarna, inte byggd) visas i fliken Analys
- `src/knep/analys/bias.py` volymkorrektion mot SMHI:s regnmätare (`knep-bias`); kartan ligger i `models/bias.npz`, underlaget, veckofaktorn och kandidaten till ny karta i `cache/bias/`
- `src/knep/analys/gauges.py` SMHI:s regnmätare till sidan (kvart, parameter 14, och timme, parameter 7): bara senaste timmen finns för alla stationer, så varje cykel lägger till den i `gauges.json` och behåller 12 h. SMHI lägger ut värdena ungefär en timme efter radarn

**Prognosen** (`src/knep/prognos/`): 0 till 5 h framåt ur analysen. `prognos.kor(analys, ...)` ger en `Prognos`. Rörelsefältet i `cache/state/motion.npy` är det enda som går tillbaka till analysen (utfyllnaden vid bortfall i nästa cykel).

- `src/knep/prognos/model.py` modellen. `Chain.run(obs, tid, steg, tillstånd)` är kedjan (rörelse, extrapolering, fördelningsmatchning, platskarta, sannolikheter för kraftig nederbörd); `nowcast(obs, steps)` är referensen. Tillståndet (senaste timmens analyser och 30-minutersprognoser) sparas i `cache/state/`
- Kedjan går hela vägen till 5 h (`--hours`), utan vädermodell. Sannolikheterna för kraftig nederbörd gäller de första 2 h (`--prob-hours`), som extremmodellen är kalibrerad för. MEPS rättad mot radarn och blandad med kedjan (den sömlösa modellen) finns bara som experiment i `experiments/meps/` (`seamless.py`, `nwp.py`), där de äldre experimenten fortfarande använder den
- `src/knep/prognos/extremes.py` särdrag och sannolikheter som delas av drift och träning; modellen ligger i `models/extremes.pkl`

**Produkter, verifiering och drift**:

- `src/knep/models.py` modellversioner (`knep-models`): filerna ligger i GitHub Releases, `models/models.json` låser tagg och sha256; nya versioner med `deploy/release_model.sh`
- `src/knep/compare.py` MET Norges nowcast (thredds, OPeNDAP med 4 km) och SMHI:s SNOW (multipoint på MEPS rutnät) som kartor till mosaiken, under `compare` i manifestet
- `src/knep/runs.py` tidigare utgåvor: första cykeln i varje timme sparas prognosernas timsummor (Tim-KNEP, MET Norge, SNOW) i `runs/` i 12 h (`--runs`) och listas under `runs` i manifestet. Sidan jämför dem med radarns timsummor i `hist/`, som är facit
- `src/knep/verify.py` verifieringen till fliken Verifiering: första cykeln i varje timme sparas Tim-KNEP:s, MET Norges, SNOW:s och persistensens timsummor för +1 till +5 h på 4 km (radarns rutnät i block om 2) i `cache/verif/pending/`; när mätarna har kommit (2,5 h efter sista timmen) räknas kontingenstabeller, kontinuerliga summor och FSS mot radarn (bara uppmätta rutor) och mot regnmätarna, per dygn i `cache/verif/days/` (35 dygn). `verif.json` har 7 och 30 dygn med 90 %-intervall (bootstrap över dygnen), skillnaden mot Tim-KNEP på samma urval, råa summor per dygn och underlaget (område, mätare, loppens ålder). `compare.py` sparar jämförelsekällornas timsummor som tal i `cache/verif/src/`; `--no-verify` stänger av
- `src/knep/cases.py` namngivna händelser (`knep-case`), skriver till `web/cases/`
- `src/knep/render.py` omprojicering till EPSG:3857, PNG per ruta i 5 min, kvart och timme, värdefil (`values.bin.gz`) och manifest.json; radaranalysen 12 h bakåt ritas en gång per bild till `hist/` med tiden i namnet och listas under `history` i manifestet (`--back`)
- `web/index.html` sidan med flikarna Prognos (kartorna fyller skärmen med tidslisten, panelen och legenden ovanpå; en karta per modell, Tim-KNEP, MET Norge, SNOW och varje ny källa under `compare` i manifestet, som följer varandra och avgränsas till MEPS-området; mätare, punktstaplar, värdet under markören och regnytan i utsnittet ur kartbildernas palett; en tidigare utgåva visas per timme med radarns kontur som facit och FSS per ledtid mot persistens; en förklaring visas första gången och med frågetecknet), Analys (samma vy som Prognos, med kartorna A0, A1 och A2 i stället för modellerna och bara tid bakåt; `live.analys` och `vy=analys` i länken), Händelser och Verifiering (måtten per ledtid och dygn, skillnaden mot Tim-KNEP och underlaget, ur `verif.json`); Leaflet från cdnjs, ingen byggkedja; punktserien hämtar MET Norge och SMHI SNOW direkt från webbläsaren (SNOW:s punktingång; kartorna tar multipoint-ingången på Pi:n). Förklaringen i sidan (`#intro`) ska följa med när något på sidan ändras; höj `INTRO` så att den visas igen
- `deploy/` driften som en container: `Dockerfile` (bara verktygen), `compose.yaml`, `drift.sh` (följer `main` och installerar varje ny commit, med återgång om den inte fungerar), `cycle.sh` (en cykel) och `publish.sh` som tvingar grenen `data`
- `.github/workflows/pages.yml` slår ihop `web/` och grenen `data` och publicerar
- `experiments/` jämförelsen mot en KNEP-proxy på öppna radarfall, med resultat i `experiments/results/`. Kör om den innan en ändring av modellen tas in

## Mål

Tim-KNEP bygger bara på observationer: radarn och regnmätarna, och på sikt satellit i analysen. Ingen vädermodell (MEPS eller annan) blandas in i analysen eller prognosen; MEPS finns bara som jämförelse (SNOW) och i experimenten. pysteps är bara referens, och modellen behöver inte likna KNEP, MET Norge eller annan radarextrapolering. Metoden är fri så länge den slår referenserna i verifieringen och går att köra på Pi:n. Det som särskilt ska lösas är terrängen: nederbörd som är bunden till topografin ska inte advekteras bort. Fältens form är lika viktig som punktvisa mått, och prognoser för samma tid från på varandra följande körningar ska inte hoppa. Indata är öppna data (radar, satellit, observationer, en öppen höjdmodell).

## Miljö

Claude Code körs direkt på Pi:n. Repot ligger i `~/knep` och radararkivet i `~/radar-arkiv`; experimenten och nattkörningen använder de gamla sökvägarna `/work` och `/data`, som ska vara symlänkar dit. Driften går i containern från `deploy/compose.yaml` och följer `main` av sig själv (en sammanslagning är i drift inom fem minuter), så ändringar går via grenar och pull requests, aldrig direkt mot driften. Rör aldrig driftens container eller volymer.

## Pull requests

Claude öppnar och slår ihop sina egna pull requests. `main` är skyddad: kontrollerna `pytest` och `docker` måste gå igenom och grenen måste vara à jour med `main`, även för administratören.

- Kör `uv run pytest` lokalt innan grenen pushas. Ändringar av modellen kräver dessutom att experimenten körs om (se Regler).
- Öppna med `gh pr create` och slå ihop med `gh pr merge --auto --merge --delete-branch`, så att GitHub väntar på kontrollerna. Aldrig `--admin`, aldrig push direkt till `main` eller `data`, aldrig `--force`.
- Följ upp efter sammanslagningen: kontrollera att driften har bytt till den nya commiten och att nästa cykel publicerar. Om den inte fungerar, öppna en PR som återställer.
- Fråga användaren först om ändringen tar bort data, ändrar vad sidan visar på ett sätt som inte är beställt, eller släpper en ny modellversion.

## Regler

- En ny modell ersätter baslinjen bara om den slår den i verifieringen på ett fryst testset (FSS och CSI per ledtid).
- Tränade modeller checkas aldrig in; de släpps i GitHub Releases och låses i `models/models.json`.
- Håll beroendena få och installerbara på arm64.
- Text i gränssnitt och dokumentation skrivs på svenska, utan tankstreck som skiljetecken.
