# 0021 utjämningen med kedjans fördelning tillbaka

## Vad som gjordes

Ny modul `experiments/projektion/utjamning_match.py` (klassen `Match` ärver `Snabb`; utjämningen är oförändrad, sedan mappas g efter rang till kedjans f för samma kvart, bara ändliga rutor):

- `match_hel` (`M_hel`): g:s rang får f:s värde. Bara de n = antal f > 0 högsta g-rutorna sorteras (`argpartition`), resten blir 0.
- `match_svans` (`M_svans1`, `M_svans2`, `M_svansq`): bara rutor med g ≥ tröskel (1 mm/h, 2 mm/h eller g:s 95-percentil bland regnrutor) får f:s högsta värden; under tröskeln står g kvar.
- `match_block` (`M_blk64`, `M_blk128`): som `M_hel` per block om 64 eller 128 km (bara block med regn i f), med mjuk övergång som medelvärde av två rutnät förskjutna ett halvt block.
- `M_hel_gol`: `M_hel` följt av golvet max(·, 0,95 · f).

Tester i `test_utjamning_match.py` (5 st): `M_hel` ger exakt kedjans sorterade värden och följer g:s rang, `M_svans` lämnar g orört under tröskeln, `M_blk` ger blockets värdemängd, sigma = 0 ger kedjans fält. `uv run pytest experiments/projektion`: 31 gick igenom. Tidtagning: `tid_match.py`. Inget i `src/`, `deploy/`, `models/` ändrat.

## Disken

Summorna låg i `/dev/shm/knep_domare` (`kor_shm.py`), med `--dagar` på traning. Kontrollen i skriptet (antal filer i rörelsecachen före och efter) gav "orörd (7 432 filer)" för körningen i `snabb`; inget skrevs till `/data`.

## Tid per utgåva (2 km, 2020-08-29 kl 12, Pi:n delad med driften)

| variant | tid | volym mot kedjan |
|---|---|---|
| kedja_om | 11,0 s | 1 |
| S_ab_gol | 15,5 s | 1,278 |
| M_hel | 15,4 s | 1,000 |
| M_hel_gol | 16,6 s | 1,108 |
| M_svans2 / 1 / q | 15,3 / 15,4 / 15,5 s | 1,17 / 1,14 / 1,17 |
| M_blk64 / 128 | 18,4 / 16,8 s | 0,999 / 1,001 |

Matchningen `M_hel` och `M_svans` kostar i praktiken ingenting extra (inom bruset); blockvarianten cirka 1 till 3 s (Pythonslinga över block).

## `snabb` (6 dygn, 4 km, 48 utgåvor), variant minus `kedja_om`

Negativt är bättre i domarens orientering; här skrivet så att `+` är bättre för csi och fss (teckenvänt mot domaren), och för blockmax_q90 och hopp är minus bättre. `*` intervallet helt på bättre sidan, `!` helt på sämre.

| mått (ledtid) | S_ab_gol | M_hel | M_svans2 | M_svansq | M_blk64 | M_blk128 | M_hel_gol |
|---|---|---|---|---|---|---|---|
| csi1 60 min | +0,018* | +0,020* | +0,027* | +0,027* | +0,010* | +0,014* | +0,012* |
| csi1 120 min | +0,016* | +0,016* | +0,023* | +0,023* | +0,006* | +0,009* | +0,009* |
| csi1 180 min | +0,012* | +0,008* | +0,016* | +0,015* | +0,004* | +0,005* | +0,007* |
| csi5 60 min | +0,013* | +0,021* | +0,021* | +0,020* | +0,008* | +0,011* | +0,010* |
| csi5 120 min | +0,009* | +0,015* | +0,015* | +0,015* | +0,002* | +0,003* | +0,006* |
| fss1_30 60 / 120 / 180 | −0,006 / −0,009! / −0,010! | −0,013! / −0,018! / −0,026! | −0,010! / −0,013! / −0,017! | −0,010! / −0,014! / −0,018! | −0,005! / −0,010! / −0,012! | −0,007! / −0,012! / −0,016! | −0,003 / −0,005! / −0,007! |
| blockmax_q90 60 / 120 / 180 | +0,057! / +0,062! / +0,066! | +0,199! / +0,237! / +0,263! | +0,266! / +0,309! / +0,383! | +0,271! / +0,326! / +0,387! | +0,014 / +0,038 / +0,029 | +0,033! / +0,059 / +0,068! | +0,018! / +0,039! / +0,019 |
| q99 och q99,9 (60 till 300) | inom brus | inom brus (intervall ±0) | inom brus | inom brus | inom brus | inom brus | inom brus |
| form4_8 60 min | +0,90! | +2,47! | +2,84! | +2,85! | +1,25! | +1,78! | +0,46! |
| hopp 15 / 30 / 60 / 120 | −0,040* / −0,041* / −0,064* / −0,077* | −0,021* / −0,019 / −0,036 / −0,042 | −0,049* / −0,049* / −0,094* / −0,108* | −0,049* / −0,049* / −0,090* / −0,102* | −0,010* / −0,010* / −0,015* / −0,019* | −0,011* / −0,011* / −0,019* / −0,024* | −0,019* / −0,019* / −0,022* / −0,028* |

(Avrundade ur domarens tabell; `/dev/shm` töms, så tabellen ovan är det som sparas. Förklaringen till varför blockmaxet blir sämre är en tolkning, inte testad.)

Läsning: `M_hel` och `M_svans` ger bra csi men en mycket större skada på blockmax_q90 än golvet (+0,2 till +0,4 mot +0,06) och på formen. Att ge tillbaka kedjans värdemängd räddar alltså kvantilerna över rutorna (q99 och q99,9 är identiska med kedjans, intervallet ±0 vid 15 och 30 min och brus vid 1 till 5 h) men inte blockmaxet: g:s högsta rang hamnar i utsmetade centrum, och när f:s få höga värden läggs där blir blockmaxet i andra block lägre (de höga värdena samlas på färre block). Block (`M_blk64`) och `M_hel_gol` skadar minst: blockmax_q90 +0,01 till +0,07 men fortfarande säkert sämre vid något tillfälle, och fss1_30 säkert sämre.

Kriteriet (csi1 och csi5 bättre vid 1 till 3 h, blockmax_q90, q99, q99,9 och fss1_30 inte säkert sämre, hopp inte sämre) uppfylls av **ingen**. Alla har blockmax_q90 eller fss1_30 säkert sämre någon ledtid.

**Fryst:** `M_hel_gol`. Skälen: den kommer närmast (fss1_30 sämre bara vid 120 och 180 min med −0,005 och −0,007, blockmax_q90 +0,02 till +0,04, bäst form av matchningsvarianterna, hopp −0,02 till −0,03), csi1 +0,012 till +0,007 och csi5 +0,010 till +0,006, och alltså något svagare csi än `S_ab_gol` (+0,018 till +0,012) men klart mindre skada på blockmax_q90 (+0,02 till +0,04 mot +0,06 till +0,07). Varianterna med störst csi1 (`M_svans2`, `M_svansq`) har en skada på blockmaxet som är fyra gånger större.

## `traning` (12 dygn, 2 km, 96 utgåvor): `M_hel_gol` och `V_ab_f2_al95` mot `kedja_om`

Samma dagar som 0018 till 0020. Skillnad mot `kedja_om`: för csi och fss är `+` bättre; för kons (log kvot), blockmax, form och hopp är `+` sämre (domarens orientering). Kolumner: 60 / 120 / 180 / 300 min. Körtid 85 processorminuter för M_hel_gol (V: 128).

| mått | M_hel_gol | V_ab_f2_al95 |
|---|---|---|
| csi1 | +0,016* / +0,014* / +0,011* / +0,008* | +0,024* / +0,025* / +0,021* / +0,018* |
| csi5 | +0,009* / +0,008* / +0,007* / +0,003* | +0,013* / +0,012* / +0,011* / +0,008 |
| fss1_30 | −0,006! / −0,005! / −0,004 / −0,001 | −0,015! / −0,009 / −0,005 / +0,004 |
| fss5_10 | 0,000 / +0,009* / +0,013* / +0,007 | +0,001 / +0,014* / +0,019* / +0,018 |
| blockmax_q50 (+ sämre) | +0,042! / +0,021! / +0,021! / +0,017 | +0,050! / +0,056! / +0,038! / +0,064! |
| blockmax_q90 (+ sämre) | +0,010 / +0,010 / +0,007 / +0,023 (intervall helt över 0 utom 300 min) | +0,057! / +0,061! / +0,064! / +0,089! |
| q99 (log kvot, + sämre) | −0,052 / −0,057 / −0,066 / −0,033 (brus) | +0,011 / −0,012 / +0,078 / +0,157 (brus) |
| q99,9 | −0,029 / +0,003 / −0,034 / +0,066 (brus) | +0,002 / +0,134 / +0,116 / +0,228 (brus) |
| form4_8 | +0,529! / +0,473! / +0,431! / +0,389! | +0,966! / +0,939! / +0,900! / +0,843! |
| form8_16 | +0,652! / +0,600! / +0,555! / +0,501! | +1,240! / +1,218! / +1,174! / +1,103! |
| volym (+ sämre) | +0,046 / +0,020 / −0,046 / −0,108 (brus) | +0,136! / +0,130! / +0,081 / −0,045 |
| hopp 15 / 30 / 60 / 120 min | −0,037* / −0,037* / −0,052* / −0,069* | −0,074* / −0,075* / −0,137* / −0,170* |

(Absoluta värden vid 60 / 120 / 180 / 300 min: csi1 M_hel_gol 0,375 / 0,233 / 0,170 / 0,115, V 0,383 / 0,244 / 0,179 / 0,125; fss1_30 M_hel_gol 0,801 / 0,608 / 0,482 / 0,353.)

Domarens dom för `M_hel_gol`: **inte bättre**. Säkert sämre: blockmax_q50 vid 1 till 3 h (+0,02 till +0,04), fss1_30 vid 1 och 2 h, fss5_30 och fss10_30 vid 1 h (fss10_30 också 2 och 5 h), formen (form4_8 och form8_16). blockmax_q90 har intervall helt på den sämre sidan men under domarens 0,01-gräns från 0 i flera punkter. Kvantilerna q99 och q99,9 är inom brus. Mot V (golv utan matchning) är blockmax_q90 klart mindre skadat (+0,01 mot +0,06 till +0,09) och formen halverad, men csi1 vinsten är också ungefär hälften (+0,016 mot +0,024 vid 1 h) och hoppet minskar mindre (−0,05 mot −0,14 vid 1 h).

Validering kördes **inte**: spärrarna håller inte på `traning` (blockmax_q50, fss1_30 och formen säkert sämre).

## Omdöme

Matchningen med kedjans fördelning är **inte redo för validering**; utjämningen bör läggas vilande om inget nytt tillkommer. Den ger exakt kedjans värdemängd och kostar nästan ingen tid, och q99 och q99,9 hålls (vilket toppskydden i 0020 inte klarade), men blockmaxet (domarens fördelning över block om 30 km) blir ändå sämre, och det blir formen: bytet av kedjans värden mellan rutor flyttar de höga värdena från där kedjan hade dem till där utjämningen har sitt maximum, och det ändrar hur de höga värdena fördelas över block. Vinsten i csi1 (+0,016 till +0,008) och hoppet (−0,05 till −0,07) är densamma storleksordning som 0019, med en skada på blockmaxet som är mindre än golvets men fortfarande säker. Det som återstår är att priset (blockmax_q90 +0,01, blockmax_q50 +0,02 till +0,04, fss1_30 −0,005, form) står mot csi1 +0,01 och hopp −0,05; det beslutet är användarens, men domaren säger "inte bättre".

## Nästa steg

1. Lägg utjämningen vilande som sådan (lösa toppar och blockmax har nu prövats med golv, tre toppskydd och fem matchningar).
2. Om hoppet är målet i sig: pröva utjämning som bara verkar på tid, alltså blandning mellan på varandra följande utgåvor (rörelsevektorn är ändå gemensam), i stället för rumsligt filter, eftersom hoppet mäts mellan utgåvor och inte kräver att fältet smetas ut.
3. Matcha per block efter blockens egna rangordning mot kedjans block men med utjämningen bara över blockgränserna, så att blockets värdemängd bevaras. `M_blk64` visade minst skada på blockmaxet i `snabb` (+0,01 till +0,06) men ger också minst vinst; det är den mest lovande om en variant ska följas upp.

## Filer

`experiments/projektion/utjamning_match.py`, `test_utjamning_match.py`, `tid_match.py`, rapporten. Inget skrevs till `/data` (rörelsecachen orörd, 7 432 filer före och efter, i båda körningarna).

Kort: Matchning av den utjämnade prognosen mot kedjans fördelning kostar ingen extra tid och bevarar q99 och q99,9, men den frysta `M_hel_gol` ger på `traning` csi1 +0,016 till +0,008 och hopp −0,05 till −0,07 mot en säker försämring av blockmax_q50 (+0,02 till +0,04), fss1_30 och formen, så domaren säger inte bättre och valideringen kördes inte.
Säkerställd förbättring: nej
Status: klar

## Filer

`experiments/projektion/utjamning_match.py`, `test_utjamning_match.py`, `tid_match.py`. Rapporten.
