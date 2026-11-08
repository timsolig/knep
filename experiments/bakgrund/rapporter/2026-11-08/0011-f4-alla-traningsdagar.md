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

## Dagfilerna med kvot våt på träningen

    uv run python experiments/analys/filter.py kor A0 F4 --del traning --dagar 2020-05-01        # provkörningen
    uv run python experiments/analys/filter.py kor A0 F4 --del traning --dagar <de 27 andra>     # en process
    uv run python experiments/analys/domare.py kontroll A0 F4 --del traning

`filter.py kor A0 F4` räknar A0 och låter F4 återanvända samma A0-bilder (`domare.cmd_kor`), så bilderna läses en gång per dag. Nu finns dagfiler med `saw` och `sgw` för **A0 och F4 på alla 28 träningsdagar** i `/data/analys/domare_v2/{A0,F4}/` (44 filer var, med valideringens 16).

- **Kontrollen mot de gamla dagfilerna:** 28 jämförda (A0 på 15 dagar och F4 på 13 dagar som fanns i `/data/analys/domare/`), **0 skillnader**.
- **Mot uppgift 0010:s A0:** de 9 dagfilerna i `/data/riksgransen/domare_tr/alla/A0/` har samma sha256 som de nya.

## F4 mot A0 på alla 28 träningsdagar

    uv run python experiments/analys/domare.py tabell F4 --mot A0 --del traning    # /data/analys/domare_v2/tabell_F4_mot_A0_traning.json
    uv run python experiments/analys/filter.py urval F4 --del traning              # /data/analys/filter/urval_traning_F4.json
    uv run python experiments/analys/f4_traning.py                                 # 28 och 13 dagar, /data/analys/domare_v2/f4_traning_jamforelse.json
    uv run python experiments/analys/f4_traning.py --validering                    # huvudraderna ur valideringens sparade tabell

Skillnaden är i godhet (större är bättre) med 95 % från bootstrap över dagarna (2 000 dragningar, som i domaren). Utdrag; hela tabellen finns i filen.

| delmängd | mått | F4 | A0 | skillnad i godhet (95 %) |
|---|---|---|---|---|
| kartan | rutor med eko i över hälften av de torra timmarna, per dag | **42,0** | 51,8 | **+9,79 (+7,82 till +11,93)** |
| kvart, alla | kvot våt | 0,68684 | 0,68684 | −0,000014 (−0,000040 till +0,000000) |
| timme, alla | kvot våt | 0,83021 | 0,83022 | −0,000014 (−0,000034 till −0,000001) |
| timme, alla | kvot summa | 0,90058 | 0,90060 | −0,000022 (−0,000049 till −0,000003) |
| kvart, alla | FSS 0,5 | 0,46155 | 0,46154 | +0,000012 (+0,000008 till +0,000017) |
| kvart, alla | FSS 1 | 0,33072 | 0,33071 | +0,000012 (+0,000007 till +0,000019) |
| kvart, alla | FSS 5 | 0,10347 | 0,10344 | +0,000034 (+0,000013 till +0,000056) |
| timme, alla | FSS 0,5 | 0,70736 | 0,70735 | +0,000014 (+0,000007 till +0,000021) |
| timme, alla | FSS 1 | 0,63517 | 0,63516 | +0,000015 (+0,000010 till +0,000020) |
| timme, alla | FSS 5 | 0,32089 | 0,32086 | +0,000031 (+0,000008 till +0,000079) |
| kvart, alla | MAE (mm) | 0,05674 | 0,05674 | +0,000001 (+0,000000 till +0,000003) |
| timme, alla | falskt vid torr mätare | 0,01024 | 0,01024 | 0 (0 till 0) |
| timme, alla | falskt där allt inom 25 km är torrt | 0,00990 | 0,00990 | 0 (0 till 0) |
| kvart, alla | falskt vid torr mätare | 0,02390 | 0,02390 | 0 (0 till 0) |
| **timme, över 400 m** | **kvot våt** | **0,48880** | **0,48886** | **−0,000112 (−0,000261 till −0,000012)** |
| timme, över 400 m | kvot summa | 0,57540 | 0,57549 | −0,000155 (−0,000344 till −0,000029) |
| kvart, över 400 m | kvot våt | 0,41284 | 0,41287 | −0,000070 (−0,000189 till +0,000000) |
| kvart, över 400 m | kvot summa | 0,56549 | 0,56558 | −0,000161 (−0,000355 till −0,000030) |
| timme, över 400 m | FSS 1 | 0,43152 | 0,43148 | +0,000040 (+0,000014 till +0,000074) |
| timme, över 400 m | falskt vid torr mätare | 0,01029 | 0,01029 | 0 (0 till 0) |
| timme, över 400 m | MAE (mm) | 0,15674 | 0,15674 | −0,000004 (−0,000019 till +0,000015) |
| timme, lovart | kvot våt | 0,67663 | 0,67670 | −0,000103 (−0,000400 till +0,000000) |
| kvart, lovart | kvot våt | 0,61095 | 0,61103 | −0,000127 (−0,000501 till +0,000000) |
| timme, lovart | FSS 0,5 | 0,66166 | 0,66165 | +0,000010 (+0,000004 till +0,000018) |
| timme, lovart | falskt vid torr mätare | 0,00839 | 0,00839 | 0 (0 till 0) |

**Domen på träningen, 28 dagar:**

| regel | bättre i | sämre i | dom |
|---|---|---|---|
| ny (kvot våt) | kvart MAE, kvart FSS 0,5, 1 och 5, timme FSS 0,5, 1 och 5 | **timme över 400 m kvot våt** | **inte bättre** |
| gammal (kvot summa) | samma | **kvart och timme över 400 m kvot summa** | **inte bättre** |
| ny, utan kravet på underlag | samma | timme över 400 m kvot våt | inte bättre |

`filter.py urval F4 --del traning` väljer därför ingen variant (`valt: None`). Ingenting väljs om utifrån det här: F4 är vald 2026-11-06 och godkänd på valideringen.

### Varför F4 fälls på 28 dagar men inte på 13

`f4_dagar.py` visar per dag vad F4 tar bort vid mätarna (Σanalys vid våta mätartimmar, F4 − A0):

| dag | timme över 400 m, saw F4 − A0 (mm) | Σmätare våta timmar över 400 m (mm) | med i de 13 |
|---|---|---|---|
| 2020-10-22 | −0,036 | 46,2 | nej |
| 2024-01-24 | −0,033 | 33,4 | nej |
| 2025-10-24 | −0,027 | 70,4 | ja |
| 2024-08-09 | −0,010 | 97,3 | nej |
| (2023-03-17) | 0 (−0,066 vid torra mätare) | 78,6 | nej |
| övriga 23 dagar | 0 | | |
| summa | **−0,106** | | |

Över 400 m tar F4 alltså bort 0,1 mm vid våta mätare på fyra av 28 dagar, ingenting på de andra (2023-03-17 tar den bort 0,066 mm vid torra mätare, alltså falskt eko, vilket är det filtret ska göra). Vilka mätare och timmar det gäller, och om det är kartdelen eller ekrarna, tog jag inte fram (det kräver att dagarna körs om med utdata per mätare). Kvoten ändras med 0,0001, men i bootstrap över dagarna kan skillnaden aldrig bli positiv, och sannolikheten att ingen av de fyra dagarna dras bland 28 är (24/28)^28 ≈ 0,013, under 2,5 %. Därför hamnar hela intervallet under 0. På de 13 dagarna fanns bara 2025-10-24 med ((12/13)^13 ≈ 0,35), så intervallet nådde 0. På valideringen finns två sådana dagar (2023-11-04 −0,016 mm och 2025-07-29 −0,025 mm av 16), och sannolikheten att ingen av dem dras är (14/16)^16 ≈ 0,12, så intervallet når 0 där (−0,000072, −0,000136 till +0,000000).

Det här är en verklig liten effekt, inte ett räknefel: på de här timmarna tar filtret bort eko vid en mätare över 400 m som har regn, så en liten del av den nederbörd som F4 tar bort i terrängen är verklig. Den är försumbar i mängd (0,106 mm av de 947 mm som A0 har vid våta mätartimmar över 400 m på de 28 dagarna, där mätarna har 1 937 mm; 0,011 %), men domarens regel är att intervallet inte får ligga helt på fel sida, och det gör det på träningen.

### Jämförelsen med valideringen och med de 13 dagarna

| | 13 träningsdagar 2026-11-06 (gammal domare) | 13 träningsdagar, ny domare | **28 träningsdagar, ny domare** | validering 16 dagar, ny domare |
|---|---|---|---|---|
| kartmåttet, F4 mot A0 | 43,0 mot 52,1, +9,1 (+6,8 till +11,5) | 43,0 mot 52,1, +9,08 (+6,69 till +11,46) | 42,0 mot 51,8, **+9,79 (+7,82 till +11,93)** | 27,6 mot 36,6, +9,00 (+5,87 till +12,50) |
| timme FSS 1 | bättre | +0,000015 (+0,000010 till +0,000022) | +0,000015 (+0,000010 till +0,000020) | +0,000009 (+0,000005 till +0,000015) |
| timme över 400 m kvot våt | (fanns inte) | −0,000066 (−0,000240 till +0,000000) | **−0,000112 (−0,000261 till −0,000012)** | −0,000072 (−0,000136 till +0,000000) |
| timme över 400 m kvot summa | −0,000053 (−0,000189 till 0) | −0,000053 (−0,000189 till +0,000000) | **−0,000155 (−0,000344 till −0,000029)** | −0,000064 (−0,000126 till +0,000000) |
| timme lovart kvot våt | (fanns inte) | 0 (0 till 0) | −0,000103 (−0,000400 till +0,000000) | −0,000042 (−0,000090 till +0,000000) |
| falska ekon (alla delmängder) | 0 | 0 | 0 | 0 |
| dom, ny regel | | bättre (FSS 0,5, 1, 5 kvart och timme) | **inte bättre** (sämre timme över 400 m kvot våt) | bättre (FSS 0,5, 1 kvart, 0,5, 1, 5 timme) |
| dom, gammal regel | bättre (samma FSS) | bättre (samma FSS) | **inte bättre** (sämre kvart och timme över 400 m kvot summa) | bättre |

Den nya domaren ger på de 13 dagarna samma tal som den gamla (kvot summa −0,000053, kartmåttet 43,0 mot 52,1), som kontrollen väntade. Kartmåttet och FSS säger samma sak på 28 dagar som förut: F4 tar bort cirka 10 rutor med fast klotter per dag och ger en liten men säker vinst i FSS. Falska ekon vid torra mätare ändras inte i någon delmängd.

**Varning inför testdelen.** På alla 28 träningsdagar fäller domaren F4 mot A0, av kvot våt per timme över 400 m (och med den gamla regeln av summakvoten över 400 m per kvart och timme). Skillnaden är 0,0001 i kvoten, och på valideringen når intervallet 0 med samma tecken. Om testdelen har en eller två dagar där F4 tar bort lite eko vid en våt fjällmätare, och tillräckligt många dagar för att de nästan alltid dras, fälls F4 på testdelen av samma skäl. Det är det troligaste sättet för F4 att inte klara testdelen, och det bör stå i testdelens rapport oavsett utfall. Inget ändras i F4 eller i domaren av det här; att ändra något nu, innan testdelen, vore att välja på träningen efter att valideringen är sedd, och det skulle kräva en ny bedömning på valideringen.

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
