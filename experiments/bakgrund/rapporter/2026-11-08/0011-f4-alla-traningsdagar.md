# 0011 F4 på alla 28 träningsdagar och klotterkartan som modellfil

Kort: UTKAST

Säkerställd förbättring: nej. Inget nytt är visat på valideringen; F4 var redan godkänd där, och bedömningen på träningen avgör inget. F4 i drift kräver släppet efter testdelen (beslut e).

## Vad som gjordes

Användarens beslut 4 (`MAL.md`, 2026-11-07): klotterkartan för F4 som modellfil, omtränad på alla 28 träningsdagar, före testdelen. Planeraren läste det som att kartan byggs om ur nuvarande kod, att F4 bedöms på alla 28 träningsdagar med den nya domaren och att kartan görs i ordning som modellfil. Jag läste `CLAUDE.md`, `MAL.md`, rapporterna `natt/2026-11-06/4-filter.md`, `0009-domare-vat-kvot.md` och `0010-glappet-riksgransen.md` först.

1. Inventering av dagfiler, artefaktsummor och disk.
2. Kartan och driftkartan byggda om ur nuvarande kod till `/data/analys/filter/v2/` (nytt val `--karta-ut` i `filter.py`) och jämförda bit för bit med de gamla (`karta_lika.py`).
3. A0 och F4 genom domaren på alla 28 träningsdagar i en process (`filter.py kor A0 F4 --del traning --dagar ...`, där F4 återanvänder A0:s bilder), med kontrollen mot de gamla dagfilerna.
4. F4 mot A0 på träningen med den nya och den gamla regeln, på alla 28 och på de 13 dagarna från 2026-11-06 (`f4_traning.py`, `domare.py tabell`, `filter.py urval`).
5. Modellfilen under `/data/analys/filter/klotter-v1/` med sha256 och metadata (`klotter_modell.py`), och släppet beskrivet.
6. A1 på träningsdagarna som saknar den: se nedan.

Testdelen lästes inte och kördes inte. Valideringen kördes inte igen; dess tabell lästes ur den sparade filen (`f4_traning.py --validering` räknar inget). Domaren är inte ändrad. `deploy/`, `models/`, `.github/`, `dagar.json` och `experiments/natt/` är inte ändrade.

## Inventeringen

Före uppgiften (`experiments/projektion/traning.json`, 28 dagar):

| underlag | träningsdagar som fanns |
|---|---|
| `/data/analys/artefakter/dag/<dag>.npz` (det `build_map` läser via `karta.load("traning")`) | **28 av 28** |
| `/data/analys/domare/rorelse/<dag>.npz` (rörelsen för lovartsidan) | 28 av 28 |
| `/data/analys/domare_v2/A0/` (med `saw`, `sgw`) | 0 (bara de 16 valideringsdagarna) |
| `/data/analys/domare_v2/F4/` | 0 |
| `/data/riksgransen/domare_tr/alla/A0/` (uppgift 0010, samma domare) | 9 |
| `/data/analys/domare/A0/` (gamla, utan `saw`, `sgw`) | 15 |
| `/data/analys/domare/F4/` (gamla) | 13 (de 13 från 2026-11-06) |
| `/data/analys/domare/A1/` (gamla) | 15 |

Kartan byggdes alltså redan på alla 28 träningsdagar (`build_map` skriver `dagar 28`), och det som saknades var dagfilerna med `kvot våt` på träningen. Ledigt på `/data` var 3,8 GB före och efter (gränsen är 3 GB).

## Kartan, ombyggd och jämförd bit för bit

    uv run python experiments/analys/filter.py karta --karta-ut /data/analys/filter/v2
    uv run python experiments/analys/filter.py karta_drift --karta-ut /data/analys/filter/v2
    uv run python experiments/analys/karta_lika.py /data/analys/filter /data/analys/filter/v2

`build_map` skrev "klotterrutor 2122 torr 433 eko+textur/isolering 287 dagar 28", över 400 m 557 av 66 739, och samma fasta ekrar (sebaa 9, seoer 6, seosd 10, sekaa 2, sevax 1 azimuter). Jämförelsen:

| fil | sha256 (början) | storlek | innehåll |
|---|---|---|---|
| `karta.npz` | f2e25077048b3441, lika | 114 595 byte, lika | `klotter` 2 122, `torr` 433, `eko` 287 rutor, `f_torr` (float16): 0 olika element |
| `klotter_f4.npz` | 535dd606b6d9c6af, lika | 1 724 byte, lika | `klotter` 621 rutor: 0 olika element |
| `ekrar.json` | 95c94e103dd53289, lika | 267 byte, lika | lika |

**Kartan är densamma bit för bit.** Den gamla kartan byggde redan på alla 28 träningsdagar, så ingen ny karta behövs; modellfilen är den gamla (och den ombyggda, som är samma fil). De gamla filerna i `/data/analys/filter/` är orörda.

UTKAST_DOMARE

## Modellfilen

    uv run python experiments/analys/klotter_modell.py

kopierar `/data/analys/filter/v2/klotter_f4.npz` till modellfilens plats, kontrollerar att `knep.analys.klotter.load` läser den med radarns rutnät och skriver metadata bredvid:

| | |
|---|---|
| fil | `/data/analys/filter/klotter-v1/klotter_f4.npz` |
| metadata | `/data/analys/filter/klotter-v1/klotter_f4.json` |
| sha256 | `535dd606b6d9c6afbdf318ecbfd2d418b1cf7c2f46971c282a326484e24de51b` |
| storlek | 1 724 byte |
| innehåll | en nyckel, `klotter`, bool (887, 471), som `klotter.load` läser |
| rutor | 621 (433 ur torra mätare, 287 ur eko med textur eller isolering, 99 i båda), varav 183 över 400 m |
| dagar | de 28 träningsdagarna i `traning.json`, alla med `artefakter.py`:s summor; inga saknas |
| byggd av | `filter.py karta` och `karta_drift` (F4: `torr | eko` utan utvidgning), kod som i commit `99f4efb` på grenen `bakgrund/2026-11-08-0212` (kartans kod är oförändrad sedan `58ad82c`, 2026-11-06, där den gamla filen byggdes; samma sha256) |

Filen ligger inte i repot (`models/*.npz` är ignorerade i `.gitignore`).

Kartan är bara kartdelen av F4. Ekrarna och solstrålarna i `filter.py` finns inte i `src/` (de märktes inte i något mått, F0), så det som domaren bedömde som F4 och det som `--klotter` gör skiljer sig i ekrarna; `filter_lika.py` visade 2026-11-06 att kartdelen ger samma bilder (0 olika rutor på 99 bilder). Testdelen bör därför bedöma F4 som i experimentet, och släppet gäller kartdelen.

## Släppet, så som det skulle göras efter testdelen (inte gjort)

Inget är släppt, och `models/` och `deploy/` är inte ändrade. Efter testdelen och om användaren godkänner, i en PR mot `main` från en gren ur `main`, från repots rot:

1. Release-texten `models/release-notes/klotter-v1.md`: vad kartan är (F4:s kartdel), träningsdagarna (28), sha256, domarens tabell på valideringen och testdelen.
2. Släppet:

       deploy/release_model.sh klotter klotter-v1 /data/analys/filter/klotter-v1/klotter_f4.npz models/release-notes/klotter-v1.md

   Skriptet kopierar filen till `models/klotter_f4.npz` (namnet `klotter` har inget eget fall i `case`, så målet blir `models/$(basename fil)`), skapar releasen `klotter-v1` med filen som tillgång (`gh release create`) och låser den med `knep-models pin klotter klotter-v1 models/klotter_f4.npz`, som lägger till i `models/models.json`:

       "klotter": {"tag": "klotter-v1", "file": "klotter_f4.npz",
                   "sha256": "535dd606b6d9c6afbdf318ecbfd2d418b1cf7c2f46971c282a326484e24de51b"}

3. Checka in `models/models.json` och release-texten (inte `.npz`-filen). `drift.sh` kör `knep-models fetch` i varje ny utcheckning innan den byts in, så filen hämtas och kontrolleras mot sha256 av sig själv. Kontrollera med `uv run knep-models status`.
4. Att slå på filtret i drift är ett eget steg: `--klotter models/klotter_f4.npz` i anropet i `deploy/cycle.sh` (som står i repots rot efter `cd`). Saknas filen loggar `analys.bygg` en varning och filtrerar inget, så cykeln går ändå. Det steget beslutar användaren om efter testdelen (beslut 4 nämner släppet och låsningen; påslagningen är en ändring i `deploy/`).

UTKAST
