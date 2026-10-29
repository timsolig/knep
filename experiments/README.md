# Experiment: vad slår KNEP-kedjan?

Syftet är att mäta de designval som går att testa utan träning, på riktig radardata, och jämföra mot en proxy för dagens kedja (cheddar-obs följt av KNEP med pysteps och optiskt flöde).

## Data

Öppna radarfall från [pysteps-data](https://github.com/pySTEPS/pysteps-data), omräknade till 2 km och 5 min som SMHI:s öppna komposit:

| Fall | Tid (UTC) | Karaktär |
|---|---|---|
| FMI 2016-09-28 | 14:45 till 18:00 | konvektion, Finland |
| FMI 2017-05-09 | 10:45 till 14:00 | svag nederbörd, Finland |
| MeteoSwiss 2015-05-15 | 15:45 till 19:00 | konvektion i alpin terräng |
| MeteoSwiss 2017-01-31 | 09:45 till 13:00 | vinter, frontal nederbörd |
| KNMI 2010-08-26 | 00:00 till 07:35 | ihållande kraftigt regn, Nederländerna |
| RMI 2021-07-04 | 15:50 till 19:00 | skyfall, Belgien |

Fallen med extrem nederbörd (FMI 2016, MeteoSwiss 2015, KNMI 2010, RMI 2021) används för att träna och testa sannolikheterna för kraftig nederbörd, alltid med det testade fallet utanför träningen.

## System

KNEP-proxy: analyser var 15:e minut på 15-minuters medelintensitet (som cheddar-obs `prec15min`), Lucas-Kanade på tre kvartsbilder och semi-Lagrangesk extrapolering i 15-minuterssteg. Fördröjningen till publicering är okänd; huvudjämförelsen antar 10 min och 5 min prövas som gynnsamt fall. Ingen MEPS-blandning, vilket påverkar KNEP lite den första timmen då radarandelen är cirka 90 procent.

Våra varianter: analyser var 5:e minut på momentana bilder, 3 min fördröjning.

| Namn | Innehåll |
|---|---|
| `lk` | Lucas-Kanade på 15 min historik, extrapolering |
| `lk30` | Lucas-Kanade på 30 min historik, extrapolering |
| `ema` | rörelsefältet utjämnat mellan körningar |
| `filt` | lagrangeskt tidsfiltrerad analys |
| `cdf` | `lk30` där varje bild matchas mot analysens intensitetsfördelning |
| `oro` | `lk30` med en platsbunden tillväxtkarta som lärs online ur senaste timmens fel |
| `oro_cdf` | `cdf` med platskartan, den föreslagna kedjan |
| `lag` | viktat medel (4:2:1) av de tre senaste körningarnas `oro` för samma tid |
| `sprog` | S-PROG, skaldämpning med ledtid |
| `steps` | STEPS-ensemble med 8 medlemmar; ensemblen ger CRPS, PMM-produkten används inte (se nedan) |

`cdf`, `oro`, `oro_cdf` och `lag` räknas fram i `verify.py` ur de lagrade `lk30`-prognoserna.

## Jämförelser och mått

1. Användarperspektiv: senaste tillgängliga prognos vid varje klocktid, 15 till 60 min framåt, på 15-minuters medelintensitet, samma yta och samma prov för alla system.
2. Samma perspektiv mot momentan radar var 5:e minut, där proxyns kvartsvärde gäller hela kvarten.
3. Algoritm: samma kvartsanalyser, ingen fördröjning, för att skilja metod från färskhet.
4. Korsvalidering över fall: varianten väljs på de finska fallen med formkrav och testas på de schweiziska, och tvärtom (`select_fold.py`).

Mått: ETS och MCC vid 0,5 till 10 mm/h, CSI, POD, FAR, frekvensbias, FSS på 2, 10 och 30 km, MAE, SAL, spektral textur (effekt i 4 till 16 km-skalor relativt observationen, 0 är som observerat), hoppighet (andel regnpixlar som byter status när prognosen för samma tid uppdateras 15 min senare), fram och tillbaka (status som ändras och sedan ändras tillbaka över tre uppdateringar) och CRPS för ensemblen. Skillnader mot KNEP-proxyn med klusterbootstrap över giltighetstider; intervallen blir för smala eftersom proven inom ett fall är korrelerade, så resultatet per fall redovisas också.

## Resultat

Huvudresultat på alla sex fall i `results/extremer.md` (rådata `results/res_ext.json`): kedjan `oro_cdf` mot KNEP-proxyn med 10 min fördröjning, senaste prognos vid varje klocktid, 15-minuters medelintensitet. Resultaten på de fyra första fallen ligger kvar i `results/resultat.md`.

| Horisont | ETS 1 proxy | ETS 1 kedja | ETS 5 proxy | ETS 5 kedja | MCC 1 proxy | MCC 1 kedja |
|---|---|---|---|---|---|---|
| 15 min | 0,43 | 0,56 | 0,15 | 0,29 | 0,60 | 0,72 |
| 30 min | 0,35 | 0,43 | 0,08 | 0,15 | 0,52 | 0,61 |
| 45 min | 0,29 | 0,35 | 0,05 | 0,08 | 0,45 | 0,52 |
| 60 min | 0,26 | 0,29 | 0,04 | 0,04 | 0,42 | 0,45 |

- Kedjan vinner vid 1 mm/h i alla sex fall och på alla horisonter (0,02 till 0,16 i ETS per fall).
- Korsvalideringen (`results/korsvalidering.md`) väljer `oro_cdf` både på de finska och på de schweiziska fallen, och den slår proxyn i testgruppen på alla horisonter.
- Formen: hoppighet som proxyns (0,44 vid 30 min) och textur i 5-minutersbilderna −0,05 mot proxyns −0,32.
- S-PROG har högst ETS vid långa ledtider men faller på formkraven: textur −0,7 till −1,0 och för stor yta med kraftig nederbörd.
- `filt` och `lag` sänker hoppigheten med 4 till 8 procent men kostar ETS och textur.
- STEPS-PMM är rättad (saknade medlemsvärden hamnade i de kraftigaste kärnorna) och prognoserna är omgenererade med rättelsen.
- Kedjan tar 6 s för hela Sverige och 2 h på en molnkärna (`bench_chain.py`).

## Aspekter: tajming, volym, intensitet, spridning och avtagande

`aspects.py` delar upp felet per ledtid (`results/aspekter.json`), på ytan där banan bakåt börjar inom täckningen så att inflödet inte drar resultatet:

- **Tajming**: vilken radarbild runt giltighetstiden prognosen liknar mest. Alla extrapoleringar ligger efter med 3 min vid 15 min och 10 min vid 60 min, även S-PROG.
- **Volym**: summan mot radarns, 1,00 till 1,03 för kedjan på alla ledtider.
- **Intensitet**: 99,9-percentilen 1,01 till 1,04 av radarns för kedjan; utan fördelningsmatchning sjunker ytan över 5 mm/h till 0,78 av radarns vid 60 min.
- **Spridning**: våt yta över 0,5 mm/h 0,97 till 1,00.
- **Avtagande**: korrelationen mellan prognosens och radarns volymförändring från analysen, 0,4 till 0,5. Fördelningsmatchningen mot hela analysen håller kvar nederbörd som lämnar området, vilket sänker den.

Med kedjan i drift (nedan, `results/aspekter_ny_kedja.md`) ligger den 9 min efter vid 60 min i stället för 10, korrelationen för avtagandet är 0,62 i stället för 0,47 och prognosens volym avtar som radarns (0,94 mot 0,95 vid 60 min). Det som återstår är att ytan över 5 mm/h krymper till 0,80 av radarns vid 60 min; där är sannolikheterna produkten.

## Kedjevarianter mot aspekterna

`tune_chain.py` bygger varianter av kedjan direkt ur analyserna och rörelsefälten och väljer med ett fall utanför i taget (`summarize_tune.py`, `results/kedjevarianter*.md`):

- **Fart gånger 1,1 till 1,3** tar bort eftersläpningen i tajmingmåttet men ger inte bättre ETS eller FSS; bara vinterfallet vinner. Eftersläpningen beror alltså delvis på tillväxt och avtagande, inte bara på för låg fart, och farten lämnas orörd.
- **Glesare bilder till rörelsen** (Lucas-Kanade på bilder med 15 minuters mellanrum) väljs i alla sex korsvalideringsvarv och vinner i alla fall: FSS för 10 mm/h på 30 km vid 60 min 0,19 till 0,24, ETS 10 0,012 till 0,018.
- **Fördelningen följer fältet** (matchning mot analysen flyttad med närmaste granne): volymen närmare 1 vid 30 och 45 min och korrelationen för avtagandet 0,48 till 0,60 vid 60 min, utan att ETS eller FSS sjunker.
- **Tre iterationer** för banorna bakåt ändrar ingenting.
- **Glesare än så** (30 minuters mellanrum) ger högre FSS för 10 mm/h vid 60 min men sämre ETS vid korta ledtider och för stor volym; 10 minuters mellanrum eller fyra bilder är inte bättre än tre bilder med 15 minuter.
- **Rörelsen utjämnad mellan körningarna** sänker hoppet med högst 2 procent och kostar FSS för 10 mm/h, så den tas inte in.

Kedjan i drift har därför glesa bilder till rörelsen och matchning mot den flyttade analysen. Verifierad som huvudresultatet ovan (`results/ny_kedja.md`, rådata `results/res_ny_kedja.json`, prognoserna omskrivna med `regen_motion.py`):

| Horisont | ETS 5 före | ETS 5 nu | SEDI 10 före | SEDI 10 nu | FSS 10 mm/h 30 km före | nu | proxyn |
|---|---|---|---|---|---|---|---|
| 15 min | 0,288 | 0,295 | 0,800 | 0,802 | 0,679 | 0,688 | 0,491 |
| 30 min | 0,148 | 0,156 | 0,630 | 0,655 | 0,430 | 0,459 | 0,318 |
| 45 min | 0,075 | 0,084 | 0,443 | 0,511 | 0,225 | 0,288 | 0,214 |
| 60 min | 0,044 | 0,050 | 0,323 | 0,379 | 0,133 | 0,188 | 0,170 |

ETS 1 är oförändrad till 0,008 bättre, inget fall förlorar mer än 0,002 och textur blir bättre (−0,05 mot −0,07 vid 60 min). Vid 60 min låg den förra kedjan under proxyn i FSS för 10 mm/h; nu ligger den över. Priset är något mer hopp mellan körningarna: 0,42 till 0,45 mot 0,41 till 0,43, i nivå med proxyn.

## Extremer

`extremes.py` tränar en gradient boosting-modell per tröskel (1, 5, 10, 20 mm/h) på lagrangeska särdrag från kedjan: värdet och grannskapet (max, medel, andel över trösklar i 6 till 62 km), intensitetstrenden längs banan de senaste 15 och 30 min, platskartan, ledtid, fart och händelsens nivå (analysens 99- och 99,9-percentil och regnandel). Ut kommer en sannolikhet per pixel, och den förväntade ytan över 5, 10 och 20 mm/h styr en monoton omskalning av kedjans värden (`ext`), så att läge och struktur behålls men frekvensen av extremer anpassas till situationen och ledtiden. `exth` tar halva steget mot den förväntade ytan. Särdragen och omskalningen ligger i `src/nowcast/extremes.py` och delas med driften.

Utfallet på sex fall, alltid med det testade fallet utanför träningen (`results/extremer.md`):

- Sannolikheterna har skicklighet: Brier skill score för minst 5 mm/h 0,31 vid 15 min mot 0,22 för en grannskapssannolikhet på 30 km, och 0,18 mot 0,12 för minst 10 mm/h. Efter den isotona omkalibreringen (nästlad, utanför urvalet) är de tillförlitliga: prognosen 0,14 motsvarar observerat 0,12 och 0,23 motsvarar 0,15.
- Omskalningen av fältet förlorar: ETS 10 vid 15 min 0,21 för kedjan utan omskalning mot 0,18 med (`ext`) och 0,20 med halva (`exth`), SEDI och FSS lika. Den rättar visserligen ytan över 20 mm/h, men på bekostnad av läget.
- Därför används sannolikheterna i drift och kedjans fält lämnas orört. Kedjan behåller redan analysens intensiteter genom fördelningsmatchningen: 99,9-percentilen ligger på 1,00 till 1,07 av radarns och SEDI 10 är högre än proxyns på alla horisonter.

Måtten för extremer: ETS, POD, FAR och bias vid 10 och 20 mm/h, SEDI (oberoende av hur sällsynt händelsen är), FSS vid 10 mm/h, toppkvoten (prognosens 99,9-percentil mot radarns) och för sannolikheterna Brier skill score, ROC-yta och tillförlitlighet.

## Radarbortfall

`outage.py` släcker en skiva med radien 100 km kring den regnigaste platsen i en timme och jämför prognoser utan störning, med hålet kvar och med hålet fyllt av `composite.fill_gaps`.

Utfyllnaden räddar analysen i hålet (ETS 1 0,17 till 0,47 mot 0 utan) och ger bättre ETS 1 för prognosen nära bortfallet i fem fall av sex. För kraftig nederbörd är den inte bättre än hålet: FSS 5 mm/h vid 30 min sjunker i två fall (Finland 2016 0,44 till 0,40, Belgien 0,42 till 0,36), eftersom en flyttad gammal kärna hamnar fel. En variant som jämnar ut den flyttade analysen mer ju äldre den är (`--smooth`, `results/outage_utjamnad.json`) ger något bättre prognoser men sämre ETS 5 i själva analysen och tas inte in. I drift är utfyllnaden sista lagret; OPERA och grannradarernas volymer kommer före och är riktiga mätningar.

## Köra

```sh
experiments/run_all.sh <pysteps-data> <utkatalog>        # prognoser, cirka 40 min på två kärnor
.venv/bin/python experiments/verify.py <utkatalog> --out res.json --skip algorithmic variants \
    --latencies 5 10 --ours lk30 oro cdf oro_cdf filt lag sprog --sal-systems oro oro_cdf sprog
.venv/bin/python experiments/summarize.py res.json > resultat.md
.venv/bin/python experiments/verify.py <utkatalog> --cases fmi_20160928 fmi_20170509 --out fold_fmi.json \
    --skip inst algorithmic variants --no-sal --no-per-case --latencies 10 --ours lk30 oro cdf oro_cdf filt lag sprog
.venv/bin/python experiments/select_fold.py fold_fmi.json fold_mch.json
.venv/bin/python experiments/extremes.py features <utkatalog>   # särdrag för träningen
.venv/bin/python experiments/extremes.py train <utkatalog>      # en modell per utelämnat fall och en på alla
.venv/bin/python experiments/extremes.py predict <utkatalog>    # ext och sannolikheter utanför urvalet
.venv/bin/python experiments/extremes.py evalprob <utkatalog> --out prob.json
.venv/bin/python experiments/verify.py <utkatalog> --out res_ext.json --skip algorithmic variants \
    --latencies 5 10 --ours lk30 oro_cdf ext exth sprog --sal-systems oro_cdf ext exth
.venv/bin/python experiments/outage.py <utkatalog> --out outage.json
.venv/bin/python experiments/summarize_ext.py res_ext.json prob.json outage.json > results/extremer.md
cp <utkatalog>/ext/models/model_utan_alla.pkl models/extremes.pkl
.venv/bin/python experiments/aspects.py <utkatalog> --out aspekter.json         # tajming, volym, intensitet, spridning, avtagande
.venv/bin/python experiments/tune_chain.py <utkatalog> --out tune.json --variants bas rörelse=gles "rörelse=gles,mål=flyttad"
.venv/bin/python experiments/summarize_tune.py tune.json > results/kedjevarianter.md
.venv/bin/python experiments/demo_cases.py <pysteps-data> <utkatalog>   # händelseflikar av testfallen
.venv/bin/python experiments/bench_chain.py              # tid för kedjan på Sverigerutnätet
.venv/bin/python experiments/bench_infer.py              # inferenstid för föreslagna nät
```
