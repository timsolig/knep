# Uppgift 0003: A2T till `src/knep/analys/a2.py` som avstängt val

Kort: A2T finns nu som en liten, avstängd modul i `src/knep/analys/a2.py` som ger bit för bit samma fält som experimentet (`np.array_equal`, största skillnad 0 mm per kvart och per timme) på 8 syntetiska fall och på alla 24 timmar och 96 kvartar för tre träningsdagar, domaren ger exakt samma tal på 2020-07-24, och en timme med sina fyra kvartar tar 1,1 till 1,3 s på hela rutnätet på Pi:n med cirka 57 MB extra minne.

Uppgiften byggde på `0001-a2-falska-ekon.md` och `0002-a2t-kontroll-matare.md`, som jag läste först, och på klassen `A2` med hjälpfunktionerna i `experiments/analys/a2.py`. Ingen baslinje eller domare ändrades. Valideringen kördes inte, och testdelen lästes aldrig: dagarna valdes med `domare.days("traning")` och skriptet kontrollerar att varje dag är en träningsdag.

## API:et

```python
from knep.analys import a2

m = a2.A2T.fran_grid(grid)            # eller a2.A2T(rng_km), rng_km = a2.radaravstand_km(grid)
timme, kvartar = m.timme(
    a1_timme,                          # (H, W) A1:s timsumma i mm, NaN utanför täckningen
    a1_kvartar,                        # (4, H, W) A1:s fyra kvartssummor i mm
    fonster,                           # a2.Matare(rad, kol, mm, a1): timmätarna för de 6 senaste timmarna
                                       #   till och med timmen, med A1:s timsumma i mätarens ruta i a1
    timmatare,                         # a2.Matare(rad, kol, mm): timmens mätare
    kvartsmatare,                      # lista med en a2.Matare per kvart
)                                      # -> (H, W) och (4, H, W), float32, mm per period
```

- Parametrarna står som konstanter `TIMME` och `KVART` (frysta värden ur `system_params("A2T")`, med kommentar som pekar på rapporterna), och `STEG = 4`, `STEG_K = 16`, `KMAX = 4`.
- `RES_KM = 2,0`: avstånden räknas med 2,0 km per ruta som i domaren och experimentet (`D.RES_KM`), fast SMHI:s rutnät har 2,015 km. Den första körningen på riktiga data tog rutans storlek ur rutnätet och gav då skillnader på upp till 0,08 mm per kvart och 0,19 mm per timme; parametrarna (`L_STOR`, `L`, `R_TORR`) valdes i enheten 2,0 km per ruta, så `src` följer den. Ett test låser `RES_KM` mot domaren.
- Mätare med NaN som värde tas bort (experimentet förutsätter att de redan är borta; med NaN hade hela OI-tillskottet blivit NaN).
- Beroenden: numpy, scipy (`cdist`, `cKDTree`), cv2 (`remap`, används redan i `prognos/advect.py`) och pyproj för radaravståndet. Inga nya i `pyproject.toml` (scipy kommer redan med pysteps och scikit-learn och används i `src/`).

**Utelämnat ur experimentet:** kontrollen av mätarna (`kontroll`, `QC_*`, A2TK), `TORR2` och `R_TORR2` (av i A2T), de syntetiska felen, punktversionen (`analys_punkter`, `Punktdag`, träningen och varianterna), korsvalideringen och `falt` för en hel dag. `svag_kvot` och `svag_tak` styrs bara av `K_SVAG` (0 för timmen, 0,125 för kvarten), eftersom `SVAG_TAK` alltid är på i A2T.

**Inte gjort, med avsikt:** inget val i `cli.py`. Ett `--a2` skulle behöva hämta timmätarna för sex timmar bakåt och spara A1:s timsummor vid mätarna, vilket inte är en liten ändring, och uppgiften sa att det bara fick göras om det var litet. `a2` i manifestet fylls inte och sidan är orörd.

## Likheten med experimentet

**Syntetiska data** (`tests/test_a2_src.py`, i CI): 8 fall med olika frön och timmar, 130 × 170 rutor, A1 med NaN-kanter och svagt eko, jämfört med `experiments/analys/a2.py` `A2(..., system_params("A2T")).falt`. Alla ger `np.array_equal` (med NaN på samma ställen) per timme och per kvart, också utan mätare, utan våta mätare, med 3 mätare och fönstret i timme 0, och med mycket regn. Egenskapstester: utan mätare är A2T lika med A1 (kvoten 1, inget tak lyfter), NaN bevaras, inga negativa värden, torrmasken sätter 0 vid torr mätare där A1 är under `TORR`, taket håller A2 högst A1 där 0 < A1 < 0,125 mm, eko på minst 1 mm tas aldrig bort, och en mätare med NaN ändrar ingenting. Ett test kontrollerar att konstanterna är lika med `system_params("A2T")` och att kontrollen och `TORR2` är av där.

**Riktiga data** (`experiments/analys/a2_src_likhet.py likhet`, tre träningsdagar, alla mätare, alla 24 timmar). A1 räknades som i domaren och sparades i `/data/analys/a2/a1falt_traning/` (float16 som valideringens fält); resultaten i `/data/analys/a2/src_likhet/<dag>.json`.

| dag | timmätare | kvartsvärden | upplösning | lika | största skillnad (mm) | rutor olika | summa (mm, alla rutor) |
|---|---|---|---|---|---|---|---|
| 2020-07-24 | 3 585 | 12 315 | kvart | ja | 0 | 0 | 1 186 111 |
| 2020-07-24 | | | timme | ja | 0 | 0 | 1 228 012 |
| 2023-11-22 | 3 184 | 10 923 | kvart | ja | 0 | 0 | 975 439 |
| 2023-11-22 | | | timme | ja | 0 | 0 | 1 052 111 |
| 2020-10-07 | 3 425 | 11 865 | kvart | ja | 0 | 0 | 942 136 |
| 2020-10-07 | | | timme | ja | 0 | 0 | 956 162 |

Avståndet till radarn (`radaravstand_km` mot `radar_range_km`) var också lika på alla rutor.

**Domaren** på 2020-07-24 (`--domare`, korsvalideringen i fem grupper med båda versionerna): alla tal i domarens resultat (summor, kontingenstabeller, FSS-delar, kartmåttet) är identiska, 0 tal olika. Några mått ur dem (samma för båda):

| delmängd | kvot summa | MAE (mm) | CSI 1 | FSS 1 | falskt vid torr mätare |
|---|---|---|---|---|---|
| kvart, alla | 0,770 | 0,0601 | 0,196 | 0,321 | 0,0149 |
| kvart, över 400 m | 0,628 | | 0,000 | 0,047 | 0,0204 |
| timme, alla | 0,893 | 0,187 | 0,501 | 0,678 | 0,0060 |
| timme, över 400 m | 0,783 | | 0,373 | 0,535 | 0,0121 |

Kartmåttet: 89 av 61 686 torra rutor med eko. En dag ger inget intervall och siffrorna jämförs inte med baslinjerna här; de visar bara att domaren ser samma system.

## Körtiden och minnet på Pi:n

`a2_src_likhet.py tid`: en timme och dess fyra kvartar på hela rutnätet (887 × 471), alla mätare, fem upprepningar, ensam process (driften körde som vanligt).

| dag, timme | timmätare | i fönstret | kvartsvärden | median (s) | spann (s) | topp numpy (MB) |
|---|---|---|---|---|---|---|
| 2020-07-24, 14 | 153 | 906 | 517 | 1,26 | 1,23 till 1,30 | 57 |
| 2020-10-07, 12 | 140 | 862 | 490 | 1,14 | 1,11 till 1,14 | 50 |

Dessutom 0,5 s en gång för radaravståndet och det glesa rutnätet (`A2T.fran_grid`), som kan räknas en gång per process eller sparas. Toppen är det som tillkommer under anropet (tracemalloc), utöver A1:s fem fält (cirka 8 MB). Hela dagen med 24 timmar tog 29 till 48 s med båda versionerna, alltså 1,2 till 2 s per timme.

**Kostnad per cykel:** mätarna kommer ungefär en timme efter radarn, så A2T behöver räknas en gång per timme (för den senaste timmen med mätare, gärna om igen när sena värden kommer), inte var femte minut. Det är 1 till 2 s av cykelns två minuter, eller under 0,5 s per cykel i medel om det sprids. Inget behöver göras snabbare. Det som tar tid är OI-tillskottet (26 000 grova rutor gånger cirka 150 mätare) och fem `remap` till hela rutnätet. I drift tillkommer att läsa A1:s timsummor för sex timmar bakåt vid mätarna, vilket är litet om de sparas vid mätarna när A1 räknas.

## Ändrade filer

- `src/knep/analys/a2.py` (ny): A2T, API:et ovan.
- `tests/test_a2_src.py` (nytt): likheten mot experimentet på syntetiska data och egenskaperna.
- `experiments/analys/a2_src_likhet.py` (nytt): likheten på träningsdagar, domaren med båda och körtiden.
- `CLAUDE.md`: en rad om modulen under Analysen (finns, är av).
- Inget i `deploy/`, `models/`, `.github/`, domaren, `experiments/sverige/dagar.json` eller `cli.py`.
- Data: `/data/analys/a2/a1falt_traning/` (A1 för de tre träningsdagarna, cirka 50 MB) och `/data/analys/a2/src_likhet/`.

`uv run pytest`: 187 passerade, varav 12 i nya `test_a2_src.py`.

## Nästa steg

Rekommendationer till användaren (besluten är dina):

1. **Fyll `a2` i manifestet med A2T**, som timme och kvart bakåt i fliken Analys. A2T slår A0 och A1 enligt domaren på valideringen (0001) och ger nu samma fält ur `src`. Det kräver ett val i `cli.py` (av som standard) som sparar A1:s timsummor vid mätarna, läser timmätarna för sex timmar ur `gauges.json` och räknar om de senaste timmarna när sena värden kommer. Det är en egen, liten uppgift.
2. **A2T som facit i verifieringen** i stället för radarns timsummor, eftersom radarn ser en liten del av de våta mätartimmarna i november. Facit ska då bara bedömas med mätare som inte användes i A2T (korsvalidering som i domaren), annars bedömer mätarna sig själva.
3. Innan A2T blir facit: kontrollen per station och dygn mot trasiga mätare (står i `IDEER.md`), som ett eget avstängt val.

Status: klar
