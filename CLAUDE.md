# knep

Nederbördsnowcast 0 till 2 h från SMHI:s radarkomposit. Körs på en Raspberry Pi (arm64, ingen GPU) var femte minut, och en cykel ska bli klar på under två minuter. Resultatet publiceras som statiska filer på GitHub Pages.

## Kommandon

- `uv sync` installerar
- `uv run pytest` kör testerna (syntetiska data, inget nätverk)
- `uv run knep --time 2026-07-14T15:30 --out web/data` kör en historisk analys mot SMHI:s arkiv (finns från 2008)
- `python3 -m http.server -d web 8000` visar sidan lokalt

## Struktur

- `src/knep/radar.py` hämtning och avkodning. GeoTIFF 0..255 i EPSG:3006, dBZ = 0,4 · v − 30, 0 = inget eko, 255 = utanför täckning, Z = 200 R^1,5
- `src/knep/model.py` modellen. `Chain.run(obs, tid, steg, tillstånd)` är kedjan (rörelse, extrapolering, fördelningsmatchning, platskarta, sannolikheter för kraftig nederbörd); `nowcast(obs, steps)` är referensen. Tillståndet (senaste timmens analyser och 30-minutersprognoser) sparas i `cache/state/`
- `src/knep/extremes.py` särdrag och sannolikheter som delas av drift och träning; modellen ligger i `models/extremes.pkl`
- `src/knep/bias.py` volymkorrektion mot SMHI:s regnmätare (`knep-bias`); kartan ligger i `models/bias.npz`, underlaget, veckofaktorn och kandidaten till ny karta i `cache/bias/`
- `src/knep/models.py` modellversioner (`knep-models`): filerna ligger i GitHub Releases, `models/models.json` låser tagg och sha256; nya versioner med `deploy/release_model.sh`
- `src/knep/composite.py` och `sources.py` kompositen: SMHI, OPERA och enskilda radarvolymer som reserv, lagrangesk utfyllnad vid bortfall
- `src/knep/cases.py` namngivna händelser (`knep-case`), skriver till `web/cases/`
- `src/knep/render.py` omprojicering till EPSG:3857, PNG per ruta i 5 min, kvart och timme, värdefil (`values.bin.gz`) och manifest.json
- `web/index.html` sidan med flikarna Prognos och Händelser (Leaflet från cdnjs, ingen byggkedja); punktserien hämtar MET Norge och SMHI SNOW direkt från webbläsaren
- `deploy/` systemd-timer, `run.sh` och `publish.sh` som tvingar grenen `data`
- `.github/workflows/pages.yml` slår ihop `web/` och grenen `data` och publicerar
- `experiments/` jämförelsen mot en KNEP-proxy på öppna radarfall, med resultat i `experiments/results/`. Kör om den innan en ändring av modellen tas in

## Mål

pysteps är bara referens, och modellen behöver inte likna KNEP, MET Norge eller annan radarextrapolering. Metoden är fri så länge den slår referenserna i verifieringen och går att köra på Pi:n. Det som särskilt ska lösas är terrängen: nederbörd som är bunden till topografin ska inte advekteras bort. Fältens form är lika viktig som punktvisa mått, och prognoser för samma tid från på varandra följande körningar ska inte hoppa. Indata är öppna data (radar, satellit, observationer, en öppen höjdmodell).

## Miljö

Claude Code körs i containern i `dev/`. Repot ligger i `/work` och radararkivet i `/data`. Driften går på värden från en egen klon av `main`, så ändringar går via grenar och pull requests, aldrig direkt mot driften.

## Regler

- En ny modell ersätter baslinjen bara om den slår den i verifieringen på ett fryst testset (FSS och CSI per ledtid).
- Tränade modeller checkas aldrig in; de släpps i GitHub Releases och låses i `models/models.json`.
- Håll beroendena få och installerbara på arm64.
- Text i gränssnitt och dokumentation skrivs på svenska, utan tankstreck som skiljetecken.
