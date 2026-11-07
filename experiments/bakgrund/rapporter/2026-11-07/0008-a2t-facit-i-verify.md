# 0008 A2T som andra facit i `src/knep/verify.py`

Kort: A2T:s timsumma sparas nu som tal i `cache/verif/a2t/` (senaste versionen skriver över), `score()` och `summary()` ger gruppen `a2t` i `Day` och `verif.json` med exakt samma radar- och mätartal som förut (prövat mot en körning utan A2T-filer), och fliken Verifiering visar Mot A2T bara när underlaget finns; i en provkörning på träningsdagen 2020-07-24 (3 utgåvor) är Tim-KNEP:s försprång mot persistensen vid +1 h för CSI 1 mm +0,305 mot radarn, +0,219 mot A2T och −0,006 mot mätarna.

## Vad som ändrades

- `src/knep/verify.py`
  - `store_a2t(vdir, end, field, n, now)` och `a2t_hour(vdir, end)`: A2T:s timsumma i block (`block`, samma 4 km som radarns timsumma), float16, med `n` (antalet mätarvärden ur märket) och `computed`, i `cache/verif/a2t/ÅÅÅÅMMDDTHH.npz` (timmens slut). Skrivs atomärt (tmp och `replace`), och filer äldre än `A2T_KEEP` = 12 h före `now` tas bort.
  - `_add_fields(...)`: det som förut låg i `score()` för radarn (grupperna av modeller med samma block, FSS, paren `ours@modell`), nu använt för både `radar` och `a2t`. Radarns kod är flyttad, inte ändrad.
  - `score()`: gruppen `a2t` på blocken där radarns mask (`base`, alltså radarn och Tim-KNEP), A2T och modellen finns, med minst `MIN_CELLS`. Saknas A2T för en ledtid (eller radarn), räknas bara det som fanns förut; utgåvan väntar aldrig på A2T. `day.meta` har nya `a2t_hours` (timmar med A2T som facit) och `a2t_n` (summan av `n`). I mätargruppen är A2T en kandidat bredvid `radar` (`cand["a2t"]`).
  - `Day`: gamla dygnsfiler utan `a2t_hours` och `a2t_n` får 0 när de läses.
  - `OBS = ("radar", "gauges", "a2t")`; `_window` och `_daily` räknar FSS för allt utom `gauges`, och tar bara med `a2t` när något dygn har A2T, så att `verif.json` ser ut som förut utan underlaget.
  - `summary()`: perioderna med `a2t` får `a2t_hours` och `a2t_gauges` (mätarvärden per timme i medel). Posten till manifestet (`_entry`) får `"a2t": true` bara när någon period har A2T; annars är den som förut.
- `src/knep/analys/a2_cykel.py`: `kor(..., verif_dir=None)` sparar varje räknad timme med `verify.store_a2t` (import i funktionen, eftersom verifieringen ligger ovanför analysen). Docstringen har en punkt 5.
- `src/knep/cli.py`: skickar `verif_dir = cache/verif` till `a2_cykel.kor`, utom med `--no-verify`. Ingen ny flagga; utan `--a2` skrivs inga filer.
- `web/index.html`: se nedan.
- `CLAUDE.md`: raderna om `a2_cykel.py`, `verify.py` och fliken Verifiering.
- `tests/test_verify.py` (tre nya tester), `tests/test_a2_cykel.py` (ett nytt).
- `experiments/verifiering/a2t_facit_prov.py` (nytt): provkörningen.

Ingenting i `deploy/`, `models/`, `.github/`, domarna, `dagar.json` eller `experiments/natt/`.

## Versionerna och väntetiden

- `a2_cykel.rakna` räknar om en timme under de senaste 3 timmarna när fler mätarvärden har kommit. Varje räkning skriver samma fil, så den som finns när utgåvan räknas är den senaste versionen (punkt 2 i 0005).
- Utgåvan med heltimme hh räknas `hh + 5 h + GAUGE_DELAY` (7,5 h). Den sista ledtidens A2T (timmen som slutar hh+5) räknas sist om vid hh+8, alltså 0,5 h efter att utgåvan räknats. I praktiken kommer nästan alla mätare inom 2,5 h (0004), så den versionen som används är nästan alltid den sista; jag har inte ändrat väntetiden för att ta den allra sista omräkningen, eftersom det skulle fördröja radar- och mätarmåtten. Det kan göras senare genom att höja `GAUGE_DELAY` till 3 h om det visar sig spela roll.
- Filerna behålls 12 h, mer än de 6,5 h som den äldsta ledtiden behöver vid räkningen. Står Pi:n still längre än så räknas utgåvan mot radarn och mätarna som förut, utan A2T.

## Mätarmåtten och A2T

Gruppen `gauges` räknas fortsatt mot mätarna. A2T är en kandidat där precis som radarn, men **A2T har rättats mot samma mätare** (optimal interpolation nära varje mätare), så A2T i mätarens ruta är nästan mätaren: i provkörningen CSI 1 mm 0,875 vid +1 h mot mätarna, mot radarns 0,420. A2T-facit och mätarfacit är alltså inte två oberoende bevis (punkt 3 i 0005), och raden A2T mot mätarna visar bara hur nära rättningen kommer, inte hur bra A2T är där den inte har sett mätaren. Det står också på sidan.

## Sidan

- Fliken Verifiering har ett tredje val, **Mot A2T**, som är dolt (`hidden`) tills den valda perioden i `verif.json` har `a2t` med Tim-KNEP. Utan underlaget ser sidan ut som i dag: knappen syns inte, och ett sparat val `a2t` faller tillbaka till radarn som andra saknade facit gör. Mot A2T fungerar som Mot radarn (FSS finns, raden heter Rutor).
- I mätarläget är A2T en referens (streckad, `#0a7d8c`, tävlar inte om fetstilen), och texten under Alla mått säger att A2T i mätarens ruta är nästan mätaren.
- Underlaget får en rad "timmar med A2T som facit, i medel n mätarvärden per timme", och metodtexten ett stycke "Facit, A2T", båda bara när `a2t` finns.
- Förklaringen (`#intro`, Verifiering) får en mening i `.intro-a2t-ja`, som visas när manifestet har `verification.a2t`. **`INTRO` är 6** och gjord som i 0007: `introVer()` är 6 med A2T som facit, 5 med A2 och 4 utan. Den automatiska förklaringen vid start gäller fortfarande bara den som sett en version under 4, och förklaringen öppnas igen bara en gång när ett manifest med en högre version än den man har sett kommer. Med A2 men utan A2T-facit (som i drift i dag) är allt alltså som förut.
- Ingen webbläsare eller JavaScript-motor finns på Pi:n, och sessionen fick inte köra hjälpskript i `/tmp`, så sidan har inte ritats här. Jag har gått igenom diffen för hand (att `W.a2t`, `R.a2t`, `hasA2T` och `VFACIT` finns där de används, att `[hidden]` döljer knappen med `display: none !important`). **Kvar:** öppna sidan lokalt med `web/data` länkad till `/data/verif_prov/2020-07-24/out` och se på fliken Verifiering med Mot A2T, och med en `verif.json` utan `a2t`.

## Testerna

- `test_a2t_store_overwrites_and_prunes`: en omräkning skriver över (n 10 till 25, fältet byts), ingen tmp-fil kvar, gamla filer tas bort efter 12 h.
- `test_score_with_a2t_leaves_radar_and_gauges_unchanged`: samma utgåva räknad utan och med A2T-filer (A2T saknas för +3 h). Gruppen `radar` och `daily.radar` är lika med `==`, `gauges` likaså för alla modeller och par som fanns förut, och `a2t` finns bara som ny kandidat; `a2t` har timmarna [1, 1, 0, 1, 1], FSS, paret mot MET Norge, `a2t_hours` 4 och manifestposten `a2t: true`. Utan filer finns inget `a2t` i `verif.json` eller posten.
- `test_summary_reads_old_days_without_a2t`: ett dygn utan `a2t`-nycklar i meta och ett med, och sedan bara det gamla.
- `test_timsumman_sparas_till_verifieringen_och_skrivs_over`: `a2_cykel.kor` med `verif_dir` sparar blocken av samma fält som `rakna` ger, skriver över vid fler mätare och sparar inget utan `verif_dir`.

`uv run pytest`: 203 passerade.

## Provkörningen

`uv run python experiments/verifiering/a2t_facit_prov.py --dag 2020-07-24 --fran 6 --till 16 --ut /data/verif_prov/2020-07-24`: elva historiska cykler, en per timme, med `--a2 --a2-matare /data/bortfall/matare` (träningsdag), och efter varje cykel `verify.cycle` med cykelns rutor (cli.py kör inte verifieringen med `--time`, så skriptet fångar rutorna i `Renderer.write`) och mätarna ur arkivet som `gauges.json`. Utgåvorna 06, 07 och 08 räknades i cyklerna 14, 15 och 16. `verif.json` fick `a2t`, och manifestposten `a2t: true`.

Underlaget: 3 utgåvor, 15 timmar (utgåva gånger ledtid) mot radarn, mätarna och A2T, i medel 1 608 mätarvärden per A2T-timme (timmens, fönstrets och kvartarnas).

| +1 h, 2020-07-24 (3 utgåvor) | mot radarn | mot A2T | mot mätarna |
|---|---|---|---|
| Tim-KNEP, CSI 1 mm | 0,527 | 0,428 | 0,356 |
| Persistens, CSI 1 mm | 0,222 | 0,210 | 0,362 |
| Skillnad | +0,305 | +0,219 | −0,006 |
| Tim-KNEP, FSS 1 mm på 20 km | 0,867 | 0,766 | |
| Persistens, FSS 1 mm på 20 km | 0,515 | 0,491 | |
| Tim-KNEP, volymkvot | 1,015 | 1,097 | 0,852 |

Mönstret är detsamma som i 0005 på 15 dagar (+0,257 mot radarn, +0,196 mot A2T, +0,105 mot mätarna): radarn som facit blåser upp Tim-KNEP:s försprång mot persistensen vid +1 h, och A2T tar bort en del av det. En dag och tre utgåvor ger inga intervall (färre än 3 dygn) och är bara en kontroll av att kedjan fungerar, inget resultat.

## Kostnaden

- Tid: att spara en A2T-timme är ett blockmedel och en komprimerad fil, under 0,1 s. Verifieringens steg tog 1,2 till 2,1 s i cyklerna utan räkning och 3,0 till 3,3 s när en utgåva räknades (med A2T, radarn och mätarna). Hela cykeln 42 till 78 s i provkörningen (Pi:n delad med driften och testerna).
- Disk: cirka 63 kB per A2T-timme på radarns hela rutnät, 12 filer, alltså under 0,8 MB i `cache/verif/a2t/`. Dygnsfilerna växer med gruppen `a2t` (ungefär som `radar`), och `verif.json` var 184 kB efter ett dygn med tre grupper. Provkörningen tog 81 MB under `/data/verif_prov/` (mest bilder och tillstånd); `/data` hade 4,1 GB ledigt efteråt.

## Rekommendation

Ändringen behöver inget nytt val: med `--a2` (redan på i drift) sparas A2T:s timmar och gruppen `a2t` fylls av sig själv cirka 7,5 h efter sammanslagningen; utan underlaget är `verif.json`, manifestet och sidan som förut. Att fliken då visar valet Mot A2T och förklaringen öppnas en gång till (`INTRO` 6) är den ändring av sidan som användaren har beslutat (beslut 2). Inget i `deploy/` behöver ändras.

## Nästa steg

1. **Beslut c:** analysens domare (`experiments/analys/domare.py`) med kvoten för perioder då mätaren har regn bredvid summakvoten, och baslinjerna A0, A1, A2T och F4 omkörda; den gamla kvoten redovisas kvar.
2. Efter några dygn i drift: se på fliken Verifiering att Mot A2T fylls och att intervallen kommer efter 3 dygn; jämför skillnaden mot persistensen vid +1 h mot radarn och A2T.
3. Om omräkningarna efter 7,5 h visar sig vanliga (jämför `computed` i `cache/verif/a2t/` med räkningens tid), överväg `GAUGE_DELAY` 3 h; det beslutar användaren, eftersom det fördröjer alla mått.

Status: klar
