# 0020 snabb utjämning och toppskydd för blockmaxet

## Disken

`df -m /data`: 1 784 MB ledigt vid start (1 708 MB vid slutet; skillnaden kommer inte från den här uppgiften). Summorna skrevs till `/dev/shm/knep_domare` (minnet, 1 896 MB, högst ett par MB använt) via `experiments/projektion/kor_shm.py`, som sätter `domare.OUT` dit och kopierar in `kedja_om`, `persistens` och `utjamning_V_ab_f2_al95` (kB per dygn). Tabellerna nedan är kopierade hit eftersom `/dev/shm` töms.

**Avvikelse:** rörelsecachen skrevs ändå en gång. Jag körde `traning` först utan `--dagar`, så att körningen gick över alla 28 träningsdygn i stället för de 12 som `kedja_om` har från 0018. För de 16 dygnen utan cache skrev domaren 437 nya rörelsefiler (2,7 MB) under `/data/projektion/cache/rorelse/2km/`. Jag avbröt körningen så fort jag såg felet. Kontrollen i skriptet jämför bara före och efter inom ett anrop, så den såg det inte; den fångar nu inte heller det som redan är gjort. Filerna är rena cachefiler (samma innehåll som domaren annars räknar om) och kan raderas utan följder, men jag tog inte bort dem. Skriptet har en `--dagar`-gräns för körningen och tabellen använder nu bara de dagar baslinjen har.

## Del 1: tiden

Profil på 2 km (`profil_utjamning.py`, dygn 2020-08-29 kl 12, tre utgåvor i `jamfor_snabb.py`). Av de cirka 16 s extra i den gamla versionen gick nästan allt till `blend_levels` (normaliserade `scipy.ndimage.gaussian_filter`, två per nivå och kvart, upp till sigma 12 pixlar) och `sigma_b` (filter och förflyttningar på fullt rutnät).

Ändringar i `utjamning_snabb.py`:
- `cv2.GaussianBlur` med reflekterande kant, nivåer med sigma över 2 pixlar körs på ett grövre rutnät (nedsampling med `INTER_AREA`, uppsampling med `INTER_LINEAR`, ungefär 2 pixlar sigma);
- hattvikter per nivå i stället för en `where` per nivå, nämnaren (filtrerad täckningsmask) återanvänds mellan kvartarna;
- `sigma_b` räknas på ett rutnät om minst 4 km (förflyttningar, boxfilter, gauss), `sigma_a`s utjämning med cv2.

Tid per utgåva på 2 km (`forecast_seconds`, Pi:n delad med driften, så bruset är stort):

| utgåva | kedja_om | V_ab_f2_al95 (gammal) | S_ab_gol (snabb) | S_ab_a / b / c |
|---|---|---|---|---|
| 2020-08-29 12 | 11,0 s | 27,3 s | 15,7 s | 16,2 / 16,0 / 16,1 s |
| 2021-05-11 15 | 9,5 s | 33,2 s | 21,3 s (brus) | 19,2 / 15,8 / 15,0 s |
| 2024-07-28 12 | 10,7 s | 30,6 s | 16,4 s | 15,6 / 15,6 / 15,9 s |

Extra mot kedjan: cirka 17 till 23 s gammal, cirka 5 till 6 s snabb (en mätning med 10 s på grund av brus). **Målet på högst 5 s extra nås nästan men inte helt**: det typiska är 5 till 6 s. Resten är sigma_b (20 + 20 förflyttningar), en Lucas-Kanade och fyra filter per kvart; nästa steg vore att utjämna varannan kvart eller räkna sigma_b på 8 km.

Skillnad mot den gamla utjämningen (S_ab_gol mot V_ab_f2_al95, samma toppskydd, 2 km, i minnet): medelskillnad 0,0075 / 0,0015 / 0,0098 mm/h, störst 2,5 / 2,4 / 4,4 mm/h (fält med max 449, 118 och 353 mm/h; gamla utjämningens avvikelse från kedjan är i medel 0,10 / 0,04 / 0,17 mm/h, så den snabba ger inom några procent samma förändring). Testerna (`test_utjamning_snabb.py`, 6 tester, och `test_utjamning.py`) visar att sigma = 0 ger exakt kedjans fält för alla fyra varianter, att konstant sigma ligger inom 8 % av maxvärdet från det exakta filtret (vitt brus, värsta fallet), att halv nivå är medelvärdet av två nivåer, och egenskaperna hos de tre toppskydden. `uv run pytest`: 224 gick igenom.

## Del 2: toppskydd i `snabb` (6 dygn, 4 km, 48 utgåvor)

Alla tre med måtten a och b, fri = 2 (ingen utjämning första 30 min), blocken `BLK_KM` = 16 km:
- **S_ab_a**: skala upp utjämnat fält per block så att blockets max blir kedjans (faktor högst 4);
- **S_ab_b**: rutor som är största värdet i ett fönster om 16 km (och över noll) behåller kedjans värde;
- **S_ab_c**: bara massan under blockets 90-percentil utjämnas, överskottet ovanför läggs tillbaka.

Variant minus `kedja_om`, plus är bättre för csi/fss, för blockmax_q90 och hopp är minus bättre; `*` intervallet helt på bättre sidan, `!` helt på sämre. Hopp avser 15, 30, 60, 120 min. Referensen `V_ab_f2_al95` (golv 0,95) är med.

| mått | variant | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|
| csi1 | V (golv) | +0,018* | +0,016* | +0,012* | +0,014* |
| | a | +0,005 | +0,007 | +0,008 | +0,014* |
| | b | +0,025* | +0,021* | +0,015* | +0,014* |
| | c | +0,026* | +0,022* | +0,016* | +0,015* |
| csi5 | V | +0,013* | +0,009* | +0,007* | +0,008* |
| | a | +0,002 | 0,000 | +0,001 | +0,006* |
| | b | +0,018* | +0,015* | +0,011 | +0,011* |
| | c | +0,019* | +0,015* | +0,012 | +0,012* |
| fss1_30 | V | −0,006 ! | −0,009 ! | −0,010 ! | 0,000 |
| | a | −0,022 ! | −0,023 ! | −0,019 ! | −0,003 |
| | b | −0,009 ! | −0,012 ! | −0,016 ! | −0,010 ! |
| | c | −0,007 ! | −0,010 ! | −0,014 ! | −0,008 ! |
| fss5_10 | V | +0,005 | +0,005 | +0,006 | +0,012 |
| | a | −0,031 | −0,024 | −0,018 | +0,001 |
| | b | +0,004 | +0,012 | +0,011 | +0,016 |
| | c | +0,004 | +0,012 | +0,013 | +0,017 |
| blockmax_q90 (+ sämre) | V | +0,057 ! | +0,061 ! | +0,066 ! | +0,069 ! |
| | a | +0,092 ! | +0,107 ! | +0,130 ! | +0,184 ! |
| | b | +0,077 ! | +0,076 ! | +0,129 ! | +0,135 ! |
| | c | +0,207 ! | +0,249 ! | +0,279 ! | +0,376 ! |

(fss5_10 ser tecknet ut ur domarens träffkolumn: variantens värde minus kedjans; inget av dem har intervallet helt på en sida utom a vid 60 min där det är skillnad åt det sämre hållet i punktvärdet.)

hopp (variant minus kedja_om, 15 / 30 / 60 / 120 min): V −0,040* / −0,040* / −0,064* / −0,076*; a −0,003 / −0,005 / −0,020 / −0,038*; b −0,067* / −0,068* / −0,120* / −0,137*; c −0,071* / −0,071* / −0,127* / −0,145*.

Övrigt ur tabellerna: a ger en tydlig massökning (volym +0,32 till +0,41 log, `!`, ytan över 5 mm/h +0,33 till +0,42) eftersom blocken skalas upp; b och c håller volymen (±0,02) men tappar form (form4_8 och form8_16 `!` för alla). Kriteriet i `snabb` (csi1 och csi5 bättre vid 1 till 3 h, blockmax_q90 och fss1_30 inte sämre, hopp inte sämre) uppfylls av **ingen**: alla tre gör blockmax_q90 säkert sämre, och fss1_30 sämre. Inget av skydden är bättre än golvet 0,95 på blockmaxet; det som försvinner är det som utjämningen tar bort i de rutor som inte är lokala maxima (b), eller att den utjämnade massan bygger på ett lägre underlag (c), och rutorna är fortfarande inte det block om 30 km som domaren mäter (en lutande topp i ett block är inte ett lokalt max i fönstret).

**Fryst:** `S_ab_b` (bästa csi1, csi5 och hopp tillsammans med c, men med lägre skada på blockmaxet än c och utan massförlust som a), trots att den inte uppfyller kriteriet.

## `traning` (12 dygn, 2 km, 96 utgåvor)

`S_ab_b` mot `kedja_om`, samma dagar som 0018 och 0019 (`V_ab_f2_al95` omräknad ur samma summor). Samma tecken som ovan.

| mått | variant | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|
| csi1 (`kedja_om` 0,359 / 0,219 / 0,159 / 0,107 enligt 0019) | V | +0,024* | +0,025* | +0,021* | +0,018* |
| | S_ab_b | +0,031* | +0,029* | +0,024* | +0,020* |
| csi5 | V | +0,013* | +0,012* | +0,011* | +0,008 |
| | S_ab_b | +0,017* | +0,022* | +0,017 | +0,008 |
| fss1_30 | V | −0,015 ! | −0,009 | −0,005 | +0,004 |
| | S_ab_b | −0,021 ! | −0,020 ! | −0,017 ! | −0,009 |
| fss5_10 | V | +0,001 | +0,014* | +0,019* | +0,018 |
| | S_ab_b | −0,012 | +0,020 | +0,024 | +0,013 |
| blockmax_q90 (+ sämre) | V | +0,057 ! | +0,061 ! | +0,064 ! | +0,089 ! |
| | S_ab_b | +0,112 ! | +0,134 ! | +0,092 ! | +0,121 ! |
| q99,9 (log kvot, + sämre) | V | +0,002 | +0,134 | +0,116 | +0,228 |
| | S_ab_b | +0,282 ! | +0,569 ! | +0,635 ! | +0,831 ! |
| hopp (15 / 30 / 60 / 120) | V | −0,074* / −0,075* / −0,137* / −0,170* | | | |
| | S_ab_b | −0,110* / −0,110* / −0,207* / −0,255* | | | |

Fler spärrar blir säkert sämre för S_ab_b på `traning`: q99 och q99,9 vid 1 till 5 h (intervallen helt över noll: q99,9 +0,28 till +0,83), blockmax_q50 och q90, fss1_30 vid 1 till 3 h och formen (form4_8 och form8_16 mycket sämre än hos V). Att bevara lokala maxima ger alltså inte konservering av extremerna: de enstaka rutorna behålls men resten av de höga värdena (kvantilerna) smetas ut, och fördelningen av högt blir smalare. V var klart bättre på extremerna (q99,9 inom brus). Körtiden för S_ab_b på `traning`: 91 processorminuter för 96 utgåvor (mot 128 för V).

## Omdöme: redo för validering?

**Nej.** Hoppet blir klart bättre (−0,11 till −0,26) och csi1/csi5 vid 1 till 3 h ännu något bättre än 0019:s variant, men inget toppskydd bevarar blockmaxet (alla säkert sämre än kedjan, och sämre än golvet 0,95) och S_ab_b skadar dessutom extremerna (q99,9) mer än golvet. Den som stannar närmast kriteriet är fortfarande golvvarianten (`S_ab_gol`, i snabb version samma fält som V inom 0,01 mm/h i medel), som bara tappar log(1/0,95) ≈ 0,05 i blockmax_q90.

Nästa steg, i den här ordningen: (1) en skydd som utgår från domarens egen enhet, det vill säga block om 30 km, och mäter om blockets max kan bevaras utan att utjämna rutorna kring toppen på samma sätt (till exempel utjämna bara fält under blockets 50-percentil och lägg toppen ovanför oförändrad, med större block för c: min c-variant använde 16 km och q90 och blev sämst); (2) minska skadan på extremerna genom att begränsa sigma efter intensitet (stora sigma bara där fältet är under 5 mm/h); (3) om hoppet är värt priset kan golvvarianten gå vidare till `validering` som den är, med blockmax_q90 +0,06 som känd kostnad; det beslutet hör till användaren. Tiden: kvar att ta cirka 1 s för att nå 5 s, genom att räkna `sigma_b` på 8 km.

## Filer

Nya: `experiments/projektion/utjamning_snabb.py`, `test_utjamning_snabb.py`, `profil_utjamning.py`, `jamfor_snabb.py`, `kor_shm.py`. Inget i `src/`, `deploy/`, `models/` ändrat. Summor under `/dev/shm/knep_domare/{snabb,traning}/utjamning_snabb_S_ab_*` (töms), tabeller `/dev/shm/knep_snabb_tabell.md` och `/dev/shm/knep_traning_tabell.md` (töms; innehållet är återgivet ovan). Skrivet till `/data`: 437 rörelsecachefiler, 2,7 MB (se Disken).

Kort: Den snabba utjämningen kostar cirka 5 till 6 s extra per utgåva på 2 km (mot cirka 19 s i 0019, målet 5 s nästan nått), men inget av de tre toppskydden (a, b, c) bevarar blockmax_q90 (+0,08 till +0,38 sämre i `snabb`); det frysta S_ab_b ger csi1 +0,031 till +0,020 och hopp −0,11 till −0,26 på `traning` men blockmax_q90 +0,09 till +0,13 och q99,9 säkert sämre, så den är inte redo för validering.
Säkerställd förbättring: nej
Status: delvis
