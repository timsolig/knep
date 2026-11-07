# Uppgift 0004: A2T i cykeln med valet `--a2`

Kort: valet `--a2` (av som standard) räknar nu A2T i cykeln ur A1:s sparade timsummor och mätarna i `gauges.json`, fyller `a2/` och `levels.a2` med kvart och timme bakåt, ger samma fält som `a2.A2T.timme` direkt (`np.array_equal` i testerna, PNG byte för byte i hela cykeln), och kostade i en provkörning på träningsdagen 2020-07-24 2,9 till 5,0 s extra i de cykler som räknar en timme och cirka 11 MB på disk.

Uppgiften byggde på `0003-a2t-till-src.md` (API:et och Nästa steg), som jag läste först. Ingen domare behövdes och ingen kördes; A2T är redan bedömd (0001). Valideringen och testdelen lästes inte; provkörningen använde bara träningsdagen 2020-07-24 (skriptet kontrollerar `domare.days("traning")`).

## Vad som ändrades

- `src/knep/analys/a2_cykel.py` (ny): A2T i cykeln.
  - `summor`: A1:s timsumma och fyra kvartssummor ur tolv intervall, samma regel som `sums` i domaren (en period räknas om minst två tredjedelar av intervallen har data). Ett test jämför mot domarens `sums`.
  - `spara_a1`: när intervallet som slutar på timmen finns och minst 8 av 12 intervall finns sparas `cache/state/a1t_ÅÅÅÅMMDDTTMM.npz` (timme och kvartar, float16, cirka 0,88 MB) en gång. Filer äldre än `BEHALL` = 10 h (3 h att räkna om plus fönstret på 6 h plus 1) tas bort. A1 räknas aldrig om.
  - `Platser` och `indata`: stationerna till rad och kolumn som `_to_rc` i domaren (golv av rutan), grovkontrollen 0 till 100 mm per timme och 0 till 60 mm per kvart som domaren, fönstret med timmätarna för de sex timmarna till och med timmen och A1:s timsumma i mätarens ruta (NaN för en timme i fönstret utan sparad A1, som `_kvot` hoppar över).
  - `rakna` och `kor`: A2T för timmarna de senaste 3 h; ritning med `Renderer.periods` till `a2/`.
  - `las_arkiv`: testkroken som läser `p7.npz` och `p14.npz` i samma form som `gauges.json`.
- `src/knep/render.py`: `A2_DIR = "a2"`, ny metod `Renderer.periods` som ritar kvarts- och timsummor som inte byggs ur 5-minutersbilder, med ett märke i filnamnet (`h20200724T1400_n1580.png`). Listningen delas nu av `history` och `periods` (`_listing`); för `hist/` och `a1/` är beteendet oförändrat (regexen tillåter bara ett märke till).
- `src/knep/cli.py`: valen `--a2` och `--a2-matare KATALOG` (arkivet för historiska körningar). Utan `--a2` körs exakt samma kod som förut och `levels.a2` är `None`; inga `a1t`-filer skrivs. Med valet körs A2 efter A1 i ett eget `try`/`except` med en varning, så ett fel aldrig stoppar prognosen.
- `src/knep/analys/a2.py`: bara docstringen (körs nu med `--a2`).
- `tests/test_a2_cykel.py` (nytt, 8 tester): summorna som domaren; sparandet en gång och rensningen; fälten ur `rakna` lika med `a2.A2T.timme` direkt på samma indata för fyra timmar (`np.array_equal`); timmar utan timmätare hoppas över och inget ritas utan mätare; omräkning när fler värden kommer (nytt filnamn, de gamla bort, också kvartarna); hela cykeln utan valet (`levels.a2` är `None`, ingen `a2/`, inga `a1t`); hela cykeln med valet och syntetiskt arkiv (en timme och fyra kvartar i `levels.a2`, PNG lika byte för byte med A2T.timme direkt på de sparade summorna); ett fel i A2 ger bara varningen `A2: ...`.
- `experiments/analys/a2_cykel_prov.py` (nytt): provkörningen nedan.
- `CLAUDE.md`: en rad om `a2_cykel.py` och valet under Analysen; raden om `a2.py` ändrad.
- Inget i `deploy/`, `models/`, `.github/`, domaren, `dagar.json` eller `web/`.

`uv run pytest`: 195 passerade (8 nya).

## Mätarnas fördröjning

- Mätarna tas ur `gauges.json`, som `gauges.py` redan fyller varje cykel (12 h). Inga nya anrop till SMHI. Med `--no-gauges` läses en befintlig `gauges.json` om den finns, annars räknas inget.
- Varje cykel ser på timmarna som slutar de senaste `RAKNA` = 3 h (mätarna kommer 1 till 2,5 h efter timmen). En timme räknas när den har sparad A1 och minst en timmätare; utan timmätare ritas inget för den (sidan säger då "inte klar än").
- Antalet mätarvärden (fönstret, timmen och kvartarna) står i filnamnet. Timmen räknas om när antalet har ökat med minst 10 %, eller när det har ökat alls och förra bilden är minst 30 min gammal. Då ritas timmen och de fyra kvartarna med nytt namn och de gamla tas bort, så att sidan inte visar en gammal bild ur webbläsarens cache (filerna i `a2/` cachas som `hist/`). Efter 3 h ligger den sista versionen kvar till 12 h bakåt (`--back`).
- Sena värden för en äldre timme i fönstret räknas också, eftersom fönstret ingår i antalet.

## Provkörningen och kostnaden

`experiments/analys/a2_cykel_prov.py --dag 2020-07-24`, en cykel per timme 06 till 16 UTC med `--history 13 --no-bias --no-verify`, radarn länkad från `/data/radar`, mätarna ur `/data/bortfall/matare/` (`--a2-matare`). Mätarna fanns i arkivet direkt, så varje cykel räknade sin senaste timme; i drift kommer de en timme senare. Resultaten i `/tmp/a2prov/` (inget sparat under `/data/`).

| timme (UTC) | timmätare | i fönstret | kvartsvärden | A2T (s) | A2 i cykeln (s) | cykeln (s) |
|---|---|---|---|---|---|---|
| 06 | 157 | 899 | 534 | 1,2 | 2,4 | 36,4 |
| 07 | 155 | 915 | 528 | 1,1 | 2,4 | 40,2 |
| 08 | 158 | 930 | 531 | 2,6 | 4,4 | 46,8 |
| 09 | 158 | 940 | 531 | 1,8 | 3,4 | 50,2 |
| 10 | 154 | 942 | 517 | 1,2 | 2,9 | 43,2 |
| 11 | 151 | 933 | 520 | 1,2 | 3,1 | 37,4 |
| 12 | 150 | 926 | 514 | 1,2 | 3,2 | 37,1 |
| 13 | 147 | 918 | 502 | 1,2 | 3,5 | 40,5 |
| 14 | 151 | 911 | 518 | 1,2 | 3,3 | 37,6 |
| 15 | 153 | 906 | 517 | 2,6 | 5,0 | 42,8 |
| 16 | 143 | 895 | 496 | 1,2 | 3,2 | 36,9 |

- "A2 i cykeln" är hela steget: spara A1:s timme, läsa fönstret, radaravståndet (0,5 s, räknas varje gång en timme räknas), A2T och fem PNG. Topparna på 2,6 s för A2T sammanföll med driftens cykel. I en jämförelse av samma cykel utan och med valet (06 och 07) var skillnaden i hela cykelns tid mindre än bruset mellan körningarna (41,3 mot 36,4 s och 33,6 mot 40,2 s).
- I drift räknas en timme först när mätarna kommer och sedan högst några gånger till när fler kommer, så de flesta cykler gör bara `spara_a1` (en npz när timmen blir hel) och listningen, under 0,1 s.
- Disk: `a1t_*.npz` 0,80 till 0,89 MB per timme, 11 filer och 9,7 MB när 10 h behålls (rensningen behåller också gränstimmen). `a2/` cirka 16,6 KB per bild, 55 bilder och 0,9 MB för 11 timmar, alltså cirka 1 MB för 12 h på sidan.
- Minne: som A2T i 0003, cirka 57 MB extra under anropet.

**Hur valet provas på riktiga data i realtid:** `uv run knep --a2 --out /tmp/a2rt/data --cache /tmp/a2rt/cache` utan `--time`, några cykler i rad: `gauges.py` hämtar mätarna till `/tmp/a2rt/data/gauges.json`, och efter ungefär en timme dyker den första A2-timmen upp. Det kördes inte här (det kräver flera cykler i realtid och delar SMHI:s anrop med driften).

## Det som återstår för att visa A2 på sidan

Sidan läser redan `levels.a2` med samma form som `history` och `levels.a1` (`frames`, `frames15`, `frames60`, `hours`, filerna med katalogen i namnet), så kartan A2 fylls i Analys för kvart och timme utan ändringar. Jag ändrade inte `web/index.html`. När valet slås på bör två texter ändras, som en egen liten ändring:

1. Förklaringen `#intro` säger att A2 "byggs fortfarande"; den bör säga att A2 är A1 rättad mot mätarna, bara som kvart och timme, och klar 1 till 2,5 h efter timmen. Höj `INTRO`.
2. `frames` (5 min) är tom för A2, så i 5-minutersläget säger kartan "inte klar än, mätarna kommer 1 till 2,5 h efter timmen". Bättre vore "bara kvart och timme" i `levelSrc` när `levels.a2` finns och upplösningen är 5 min.

## Rekommendation till användaren

Slå på `--a2` i cykelns anrop i `deploy/` (det beslutar du; jag har inte ändrat `deploy/`), tillsammans med de två texterna ovan. A2T slår A0 och A1 enligt domaren på valideringen (0001), fältet i cykeln är detsamma som i modulen, och kostnaden är cirka 3 s i de cykler som räknar en timme och cirka 11 MB på disk. Inga nya anrop till SMHI. Står också under Frågor till användaren i `MAL.md`.

## Nästa steg

1. Om valet slås på: de två texterna på sidan och en kontroll efter några timmar i drift att `a2/` fylls och räknas om när sena mätare kommer.
2. Radaravståndet kan sparas i `cache/state/` för att spara 0,5 s per räknad timme (inte nödvändigt).
3. Kontrollen per station och dygn mot trasiga mätare (`IDEER.md`) som eget avstängt val, innan A2T blir facit i verifieringen.

Status: klar
