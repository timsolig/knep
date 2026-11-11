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

(Siffrorna är oviktade avrundningar ur domarens tabell; fullständiga rader finns i `/dev/shm` bara tills den töms, så avläsningarna ovan är de som gäller.)

Läsning: `M_hel` och `M_svans` ger bra csi men en mycket större skada på blockmax_q90 än golvet (+0,2 till +0,4 mot +0,06) och på formen. Att ge tillbaka kedjans värdemängd räddar alltså kvantilerna över rutorna (q99 och q99,9 är identiska med kedjans, intervallet ±0 vid 15 och 30 min och brus vid 1 till 5 h) men inte blockmaxet: g:s högsta rang hamnar i utsmetade centrum, och när f:s få höga värden läggs där blir blockmaxet i andra block lägre (de höga värdena samlas på färre block). Block (`M_blk64`) och `M_hel_gol` skadar minst: blockmax_q90 +0,01 till +0,07 men fortfarande säkert sämre vid något tillfälle, och fss1_30 säkert sämre.

Kriteriet (csi1 och csi5 bättre vid 1 till 3 h, blockmax_q90, q99, q99,9 och fss1_30 inte säkert sämre, hopp inte sämre) uppfylls av **ingen**. Alla har blockmax_q90 eller fss1_30 säkert sämre någon ledtid.

**Fryst:** `M_hel_gol`. Skälen: den kommer närmast (fss1_30 sämre bara vid 120 och 180 min med −0,005 och −0,007, blockmax_q90 +0,02 till +0,04, bäst form av matchningsvarianterna, hopp −0,02 till −0,03), csi1 +0,012 till +0,007 och csi5 +0,010 till +0,006, och alltså något svagare csi än `S_ab_gol` (+0,018 till +0,012) men klart mindre skada på blockmax_q90 (+0,02 till +0,04 mot +0,06 till +0,07). Varianterna med störst csi1 (`M_svans2`, `M_svansq`) har en skada på blockmaxet som är fyra gånger större.

TRANING_PLATS

## Filer

`experiments/projektion/utjamning_match.py`, `test_utjamning_match.py`, `tid_match.py`. Rapporten.
