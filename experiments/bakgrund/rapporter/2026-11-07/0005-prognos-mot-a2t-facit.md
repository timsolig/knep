# Uppgift 0005: kedjan och persistensen mot A2T som facit, på träningsdagarna

Kort: på 15 träningsdagar (90 utgåvor) slår kedjan persistensen vid alla ledtider mot alla tre facit, men försprånget vid +1 h krymper när radarn byts mot A2T (CSI 1 mm +0,257 till +0,196, FSS 1 mm/10 km +0,253 till +0,204, MAE −0,084 till −0,066 mm) och mest mot mätarna (CSI 1 mm +0,105, 95 % +0,066 till +0,136, mindre än vid +2 h med +0,142); klottermasken (F4) ändrar skillnaden med högst 0,01, så klottret ger persistensen nästan ingenting på de här dagarna.

Uppgiften byggde på `experiments/natt/rapporter/2026-11-05/1-verif-persistens.md` och rapporterna 0001, 0003 och 0004 från 2026-11-07, som jag läste först. Ingen domare och inget system ändrades, och inget i `src/` behövde ändras. Valideringen och testdelen lästes inte: dagarna tas med `domare.days("traning")` ur analysens domare (som kontrollerar att ingen testdag finns med), och skriptet kontrollerar varje dag. Mätarna läses bara för dagarna i fråga (`load_gauges` filtrerar på dagen).

## Vad jag gjorde

Skriptet `experiments/projektion/facit_a2t.py` har tre steg, så att de två tunga kan gå i var sin process:

1. **`analys`** per dag: A0 (SMHI:s komposit med utfyllnad, som `A0` i analysens domare), A1 (`A1` i domaren, eller A1 sparad i `/data/analys/a2/a1falt_traning/` för de tre dagar där den fanns) och A2T ur `knep.analys.a2` med samma konstanter som i drift, A1 och alla timmätare (p7) och kvartsmätare (p14) för dagen, fönstret på 6 h som i `a2_src_likhet.py`. A2T räknades också en gång per grupp i domarens korsvalidering (5 grupper om 100 km, mätarna utanför gruppen och mer än 25 km från den), så att A2T kan bedömas vid mätare den inte har sett. Sparat: A0 och A2T i block om 2 (4 km), värdena i mätarnas rutor och masken eko90.
2. **`kedja`** per dag: `KedjaOm` ur projektionens domare (läget `traning`): `model.Chain(None)`, utan MEPS, extremmodell och volymkorrektion, platskartan uppvärmd 90 min, rörelsecachen under `/data/projektion/cache/rorelse/2km/`. Timsummorna +1 till +5 h är medlet av kvartarna 4(k−1) till 4k−1 efter driftens kodning (värdefilen), som i domaren.
3. **`summera`**: måtten per dag och ledtid, summerade över dagarna, med bootstrap över dagarna (B = 2000) för varje system och för skillnaden kedjan minus persistensen. Tabellerna skrivs med `facit_a2t_tabell.py`, tabellen per dag med `facit_a2t_perdag.py`.

Val som är värda att känna till:

- **Utgåvorna** är 03, 06, 09, 12, 15 och 18 UTC: de var 3:e hel timme där persistensen (timmen som slutar vid utgåvan) och alla fem målen (timmarna som slutar 04:00 till 23:00) ligger inom dagen. Varje ledtid har då samma utgåvor. 00 och 21 UTC kom inte med, eftersom de skulle kräva grannarnas dagar.
- **Persistensen** är A0:s timsumma som slutar vid utgåvan (bilderna hh−0:55 till hh:00, med utfyllnad som A0, en timme räknas om minst 2/3 av intervallen finns, som i analysens domare). Facit radarn är samma A0.
- **Kartmåtten** på 4 km, på rutorna där A0, A2T, persistensen och kedjan alla finns, samma rutor för båda kartfacit: CSI vid 1 och 5 mm, FSS vid 1 och 5 mm med fönster 10 och 30 km (3 och 7 block, andelarna bara ur rutorna i masken som `verify.fss_many`), summakvoten och MAE i mm per timme.
- **Mätarna** (p7 med domarens grovkontroll) i mätarens ruta på 2 km; kedjan och persistensen tas ur samma ruta. Samma mätartimmar för kedjan, persistensen och analyserna.
- **Maskerna**: `alla`; `utan_f4`, utan blocken där någon ruta ligger i F4:s klotterkarta (`/data/analys/filter/klotter_f4.npz`, 621 rutor på 2 km); `utan_eko90`, utan rutorna med eko i över 90 % av dagens bilder (räknat på de råa bilderna, minst hälften av bilderna uppmätta).
- **Intervallen** är 95 % (2,5 och 97,5 percentilerna). För kvoten är skillnaden räknad i |ln kvot|, så att negativ betyder att kedjans mängd ligger närmare facit.
- A2T:s fönster för timmarna strax efter midnatt har färre än 6 timmar (bara dagens). Det rör bara målet som slutar 04:00 och 05:00 (fönster 4 och 5 timmar).

## Dagarna

De 15 träningsdagar där analysens domare har A1: 2020-02-10, 2020-05-01, 2020-07-24, 2020-08-29, 2020-10-07, 2021-01-23, 2021-05-11, 2022-12-20, 2023-01-04, 2023-07-12, 2023-11-22, 2024-07-28, 2024-09-26, 2025-06-23 och 2025-10-24. Alla fick sex utgåvor (90 utgåvor). Cirka 5,5 miljoner block per ledtid i kartmåtten och 11 600 till 12 250 mätartimmar per ledtid.

## Tabellerna

Kedjan / persistensen, och kedjan minus persistensen med 95 %-intervall; * betyder att intervallet ligger helt på ena sidan. Positivt i CSI och FSS och negativt i MAE och |ln kvot| är bättre för kedjan.

### Facit radarn (A0), alla rutor

| mått | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,598 / 0,340 | 0,357 / 0,207 | 0,259 / 0,158 | 0,209 / 0,130 | 0,177 / 0,107 |
| CSI 5 | 0,382 / 0,179 | 0,160 / 0,083 | 0,086 / 0,049 | 0,066 / 0,044 | 0,059 / 0,033 |
| FSS 1/10 | 0,850 / 0,596 | 0,623 / 0,405 | 0,492 / 0,321 | 0,414 / 0,271 | 0,361 / 0,228 |
| FSS 1/30 | 0,906 / 0,682 | 0,708 / 0,473 | 0,574 / 0,375 | 0,487 / 0,316 | 0,429 / 0,267 |
| FSS 5/10 | 0,717 / 0,412 | 0,388 / 0,203 | 0,226 / 0,116 | 0,175 / 0,104 | 0,157 / 0,078 |
| FSS 5/30 | 0,815 / 0,528 | 0,497 / 0,270 | 0,301 / 0,155 | 0,232 / 0,137 | 0,207 / 0,101 |
| kvot | 0,971 / 0,974 | 0,955 / 0,978 | 0,952 / 0,975 | 0,954 / 0,964 | 0,976 / 0,967 |
| MAE | 0,119 / 0,203 | 0,202 / 0,263 | 0,243 / 0,289 | 0,264 / 0,301 | 0,273 / 0,307 |

| kedjan − persistensen | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,257 (0,233 till 0,282) * | 0,150 (0,131 till 0,171) * | 0,102 (0,081 till 0,122) * | 0,079 (0,057 till 0,100) * | 0,070 (0,046 till 0,093) * |
| CSI 5 | 0,203 (0,173 till 0,227) * | 0,077 (0,011 till 0,116) * | 0,038 (−0,024 till 0,083) | 0,022 (−0,034 till 0,073) | 0,025 (−0,029 till 0,071) |
| FSS 1/10 | 0,253 (0,219 till 0,287) * | 0,218 (0,191 till 0,248) * | 0,171 (0,142 till 0,199) * | 0,143 (0,106 till 0,177) * | 0,134 (0,094 till 0,170) * |
| FSS 1/30 | 0,224 (0,191 till 0,259) * | 0,234 (0,205 till 0,267) * | 0,199 (0,166 till 0,232) * | 0,171 (0,128 till 0,211) * | 0,162 (0,118 till 0,203) * |
| FSS 5/10 | 0,305 (0,255 till 0,376) * | 0,185 (0,054 till 0,253) * | 0,110 (−0,035 till 0,210) | 0,071 (−0,064 till 0,191) | 0,079 (−0,056 till 0,185) |
| FSS 5/30 | 0,286 (0,236 till 0,372) * | 0,227 (0,073 till 0,304) * | 0,146 (−0,041 till 0,277) | 0,096 (−0,074 till 0,246) | 0,106 (−0,064 till 0,239) |
| \|ln kvot\| | 0,004 (−0,021 till 0,034) | 0,024 (−0,010 till 0,057) | 0,025 (−0,023 till 0,061) | 0,010 (−0,049 till 0,058) | −0,009 (−0,073 till 0,067) |
| MAE | −0,084 (−0,098 till −0,068) * | −0,062 (−0,073 till −0,050) * | −0,046 (−0,058 till −0,033) * | −0,038 (−0,054 till −0,020) * | −0,034 (−0,054 till −0,013) * |

### Facit A2T, alla rutor

| mått | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,523 / 0,327 | 0,337 / 0,205 | 0,252 / 0,152 | 0,205 / 0,126 | 0,176 / 0,103 |
| CSI 5 | 0,310 / 0,154 | 0,152 / 0,072 | 0,083 / 0,039 | 0,066 / 0,037 | 0,058 / 0,034 |
| FSS 1/10 | 0,780 / 0,576 | 0,592 / 0,401 | 0,478 / 0,311 | 0,405 / 0,263 | 0,356 / 0,219 |
| FSS 1/30 | 0,838 / 0,658 | 0,673 / 0,467 | 0,558 / 0,363 | 0,477 / 0,306 | 0,422 / 0,256 |
| FSS 5/10 | 0,612 / 0,355 | 0,370 / 0,177 | 0,218 / 0,093 | 0,173 / 0,085 | 0,151 / 0,079 |
| FSS 5/30 | 0,704 / 0,453 | 0,478 / 0,235 | 0,294 / 0,125 | 0,229 / 0,108 | 0,195 / 0,099 |
| kvot | 0,990 / 0,994 | 0,965 / 0,989 | 0,970 / 0,994 | 0,967 / 0,977 | 0,979 / 0,970 |
| MAE | 0,139 / 0,206 | 0,206 / 0,262 | 0,241 / 0,286 | 0,262 / 0,299 | 0,272 / 0,305 |

| kedjan − persistensen | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,196 (0,168 till 0,220) * | 0,132 (0,113 till 0,152) * | 0,100 (0,078 till 0,120) * | 0,079 (0,061 till 0,098) * | 0,073 (0,050 till 0,098) * |
| CSI 5 | 0,156 (0,129 till 0,174) * | 0,080 (0,023 till 0,114) * | 0,044 (−0,009 till 0,087) | 0,029 (−0,028 till 0,082) | 0,024 (−0,026 till 0,074) |
| FSS 1/10 | 0,204 (0,172 till 0,235) * | 0,192 (0,166 till 0,219) * | 0,167 (0,138 till 0,195) * | 0,142 (0,114 till 0,171) * | 0,137 (0,100 till 0,174) * |
| FSS 1/30 | 0,180 (0,151 till 0,212) * | 0,206 (0,180 till 0,236) * | 0,195 (0,162 till 0,226) * | 0,170 (0,139 till 0,203) * | 0,166 (0,124 till 0,206) * |
| FSS 5/10 | 0,257 (0,224 till 0,309) * | 0,193 (0,091 till 0,241) * | 0,124 (0,001 till 0,212) * | 0,088 (−0,046 till 0,205) | 0,072 (−0,046 till 0,190) |
| FSS 5/30 | 0,251 (0,211 till 0,320) * | 0,243 (0,133 till 0,293) * | 0,168 (0,016 till 0,276) * | 0,121 (−0,042 till 0,260) | 0,097 (−0,044 till 0,242) |
| \|ln kvot\| | 0,004 (−0,034 till 0,018) | 0,024 (−0,057 till 0,049) | 0,025 (−0,063 till 0,054) | 0,010 (−0,058 till 0,058) | −0,009 (−0,079 till 0,069) |
| MAE | −0,066 (−0,079 till −0,053) * | −0,056 (−0,067 till −0,044) * | −0,046 (−0,057 till −0,034) * | −0,037 (−0,052 till −0,021) * | −0,033 (−0,053 till −0,013) * |

### Facit mätarna (p7 i mätarens ruta), alla

| mått | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,392 / 0,288 | 0,319 / 0,177 | 0,241 / 0,132 | 0,193 / 0,105 | 0,164 / 0,094 |
| CSI 5 | 0,194 / 0,101 | 0,107 / 0,044 | 0,028 / 0,025 | 0,042 / 0,036 | 0,037 / 0,027 |
| kvot | 0,914 / 0,948 | 0,982 / 0,870 | 0,964 / 0,874 | 0,888 / 0,870 | 0,935 / 0,898 |
| MAE | 0,212 / 0,265 | 0,281 / 0,319 | 0,314 / 0,344 | 0,319 / 0,361 | 0,343 / 0,369 |

| kedjan − persistensen | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,105 (0,066 till 0,136) * | 0,142 (0,091 till 0,196) * | 0,109 (0,071 till 0,149) * | 0,088 (0,065 till 0,109) * | 0,070 (0,036 till 0,109) * |
| CSI 5 | 0,094 (−0,035 till 0,190) | 0,063 (0,000 till 0,117) | 0,004 (−0,026 till 0,025) | 0,006 (−0,007 till 0,030) | 0,010 (−0,024 till 0,044) |
| \|ln kvot\| | 0,036 (−0,066 till 0,088) | −0,121 (−0,189 till 0,098) | −0,097 (−0,180 till 0,093) | −0,021 (−0,114 till 0,098) | −0,041 (−0,157 till 0,127) |
| MAE | −0,052 (−0,080 till −0,028) * | −0,037 (−0,056 till −0,018) * | −0,030 (−0,048 till −0,010) * | −0,042 (−0,066 till −0,012) * | −0,026 (−0,064 till 0,015) |

### Analyserna mot mätarna (samma mätartimmar som +1 h)

| analys | CSI 1 | CSI 5 | kvot | MAE (mm) |
|---|---|---|---|---|
| A0 (radarn) | 0,440 (0,377 till 0,499) | 0,295 (0,145 till 0,378) | 0,941 (0,832 till 1,073) | 0,194 (0,168 till 0,218) |
| A1 | 0,452 (0,389 till 0,509) | 0,301 (0,171 till 0,385) | 0,938 (0,832 till 1,066) | 0,188 (0,163 till 0,211) |
| A2T (har sett mätaren) | 0,839 (0,797 till 0,877) | 0,809 (0,696 till 0,889) | 0,958 (0,946 till 0,968) | 0,033 (0,026 till 0,039) |
| A2T utan mätaren (korsvalidering) | 0,484 (0,421 till 0,536) | 0,245 (0,102 till 0,333) | 0,952 (0,904 till 1,006) | 0,177 (0,152 till 0,198) |

Där A2T inte har sett mätaren är den bättre än radarn i CSI 1 mm (+0,044) och MAE (−0,017 mm), sämre i CSI 5 mm (0,245 mot 0,295, få fall och brett intervall). Intervallen ovan är för varje analys för sig, inte för skillnaden. A2T är alltså ett bättre facit än radarn vid 1 mm men inte bevisat vid 5 mm, och i mätarnas rutor är A2T nästan mätaren själv (MAE 0,033 mm).

### Maskerna

Skillnaden kedjan minus persistensen vid +1 h med och utan klottermasker (hela tabellerna för alla ledtider och masker finns i `results/facit_a2t.json` och skrivs med `facit_a2t_tabell.py`):

| facit | mask | block per ledtid | CSI 1 | CSI 5 | FSS 1/10 | FSS 5/10 | MAE |
|---|---|---|---|---|---|---|---|
| radarn | alla | 5 513 042 | 0,257 (0,233 till 0,282) | 0,203 (0,173 till 0,227) | 0,253 | 0,305 | −0,084 |
| radarn | utan F4 | 5 474 494 | 0,261 (0,236 till 0,286) | 0,212 (0,184 till 0,237) | 0,255 | 0,307 | −0,084 |
| radarn | utan eko90 | 5 507 084 | 0,259 (0,234 till 0,283) | 0,206 (0,178 till 0,230) | 0,254 | 0,306 | −0,084 |
| A2T | alla | 5 513 042 | 0,196 (0,168 till 0,220) | 0,156 (0,129 till 0,174) | 0,204 | 0,257 | −0,066 |
| A2T | utan F4 | 5 474 494 | 0,199 (0,172 till 0,223) | 0,163 (0,139 till 0,183) | 0,205 | 0,259 | −0,067 |
| A2T | utan eko90 | 5 507 084 | 0,197 (0,169 till 0,221) | 0,159 (0,133 till 0,177) | 0,204 | 0,258 | −0,067 |
| mätarna | alla | 12 217 | 0,105 (0,066 till 0,136) | 0,094 (−0,035 till 0,190) | | | −0,052 |
| mätarna | utan F4 | 12 135 | 0,103 (0,064 till 0,135) | 0,094 (−0,035 till 0,190) | | | −0,052 |
| mätarna | utan eko90 | 12 215 | 0,104 (0,065 till 0,136) | 0,094 (−0,035 till 0,190) | | | −0,052 |

Klottret syns mest vid 5 mm: utan F4:s rutor faller persistensens CSI 5 mm mot radarn från 0,179 till 0,174 vid +1 h och från 0,033 till 0,028 vid +5 h, medan kedjans stiger något. Skillnaden ändras ändå med högst 0,01 i CSI och FSS, och vid +5 h mot radarn med 0,007 i CSI 5 mm. Eko90 tar bort ännu färre rutor (cirka 6 000 block per ledtid) och ändrar ännu mindre.

### Per dag (CSI 1 mm, kedjan / persistensen, alla rutor)

| dag | radarn +1 h | A2T +1 h | mätarna +1 h | radarn +5 h | A2T +5 h | mätarna +5 h | persistensens kvot mot mätarna +1 h |
|---|---|---|---|---|---|---|---|
| 2020-02-10 | 0,354 / 0,138 | 0,291 / 0,140 | 0,205 / 0,191 | 0,026 / 0,039 | 0,045 / 0,035 | 0,100 / 0,000 | 1,09 |
| 2020-05-01 | 0,642 / 0,294 | 0,559 / 0,288 | 0,459 / 0,344 | 0,129 / 0,099 | 0,135 / 0,076 | 0,126 / 0,051 | 1,12 |
| 2020-07-24 | 0,588 / 0,289 | 0,511 / 0,267 | 0,356 / 0,248 | 0,137 / 0,085 | 0,142 / 0,078 | 0,113 / 0,110 | 0,90 |
| 2020-08-29 | 0,615 / 0,370 | 0,578 / 0,358 | 0,490 / 0,331 | 0,172 / 0,090 | 0,161 / 0,092 | 0,121 / 0,118 | 1,14 |
| 2020-10-07 | 0,533 / 0,263 | 0,453 / 0,223 | 0,295 / 0,228 | 0,067 / 0,057 | 0,066 / 0,045 | 0,081 / 0,042 | 1,57 |
| 2021-01-23 | 0,719 / 0,527 | 0,561 / 0,453 | 0,111 / 0,136 | 0,260 / 0,176 | 0,211 / 0,179 | 0,214 / 0,364 | 0,57 |
| 2021-05-11 | 0,624 / 0,406 | 0,443 / 0,322 | 0,384 / 0,394 | 0,174 / 0,127 | 0,101 / 0,073 | 0,101 / 0,081 | 1,69 |
| 2022-12-20 | 0,482 / 0,189 | 0,419 / 0,187 | 0,231 / 0,200 | 0,058 / 0,029 | 0,071 / 0,030 | 0,087 / 0,000 | 0,68 |
| 2023-01-04 | 0,567 / 0,309 | 0,480 / 0,283 | 0,433 / 0,293 | 0,152 / 0,173 | 0,156 / 0,155 | 0,136 / 0,128 | 0,85 |
| 2023-07-12 | 0,682 / 0,436 | 0,634 / 0,440 | 0,570 / 0,344 | 0,274 / 0,213 | 0,281 / 0,213 | 0,300 / 0,156 | 0,86 |
| 2023-11-22 | 0,541 / 0,361 | 0,433 / 0,339 | 0,309 / 0,183 | 0,160 / 0,041 | 0,134 / 0,041 | 0,137 / 0,043 | 0,78 |
| 2024-07-28 | 0,626 / 0,435 | 0,561 / 0,414 | 0,143 / 0,104 | 0,239 / 0,143 | 0,255 / 0,150 | 0,094 / 0,067 | 1,24 |
| 2024-09-26 | 0,676 / 0,358 | 0,636 / 0,390 | 0,511 / 0,324 | 0,258 / 0,113 | 0,287 / 0,124 | 0,263 / 0,114 | 0,70 |
| 2025-06-23 | 0,561 / 0,267 | 0,489 / 0,271 | 0,374 / 0,280 | 0,132 / 0,065 | 0,128 / 0,074 | 0,134 / 0,094 | 0,83 |
| 2025-10-24 | 0,630 / 0,431 | 0,598 / 0,446 | 0,430 / 0,436 | 0,256 / 0,130 | 0,271 / 0,131 | 0,303 / 0,104 | 0,75 |

Mot radarn och A2T vinner kedjan vid +1 h alla 15 dagarna. Mot mätarna vinner persistensen eller står lika vid +1 h på tre dagar (2021-01-23, 2021-05-11 och 2025-10-24) och är nära 2020-02-10. 2021-01-23 är en vinterdag där radarn ser lite av det mätarna fångar (persistensens kvot 0,57) och persistensen vinner tydligt mot mätarna också vid +5 h (0,364 mot 0,214), trots att kedjan vinner mot radarn och A2T. Det är just det mönster som rapporten från 2026-11-05 beskrev för driften i november: facit radarn och facit mätarna säger olika saker när radarn ser lite.

## Svaret

**Ändras kedjans läge mot persistensen när facit byts?** Inte i tecken: kedjan slår persistensen vid alla ledtider i CSI och FSS vid 1 mm och i MAE med alla tre facit, med intervallet helt på den positiva sidan (mot mätarna vid +5 h är MAE-intervallet inte helt på ena sidan). Men storleken ändras, och mest vid +1 h:

- **Radarn till A2T:** vid +1 h krymper försprånget med cirka en fjärdedel (CSI 1 mm 0,257 till 0,196, FSS 1 mm/10 km 0,253 till 0,204, CSI 5 mm 0,203 till 0,156, MAE −0,084 till −0,066). Från +3 h är skillnaden mot de två facit nästan densamma (CSI 1 mm 0,102 mot 0,100 vid +3 h, 0,070 mot 0,073 vid +5 h). Det är kedjan som tappar, inte persistensen som vinner: kedjans CSI 1 mm vid +1 h faller från 0,598 till 0,523, persistensens bara från 0,340 till 0,327. Radarn som facit belönar alltså prognoser som delar radarns egna fel, och det gör kedjan mest de första timmarna, eftersom den då nästan är radarn flyttad en timme.
- **Mätarna:** vid +1 h är försprånget i CSI 1 mm bara 0,105, mindre än vid +2 h (0,142); mot radarn är det tvärtom (0,257 mot 0,150). Kedjan är alltså relativt sett svagast vid +1 h när facit är mätarna. Kedjans kvot mot mätarna är 0,914 vid +1 h men 0,98 vid +2 h, och persistensens 0,948: kedjan ger för lite regn i mätarnas rutor just den första timmen.
- **Klottret** förklarar nästan ingenting av det här: med F4:s karta eller eko90 bortmaskad ändras skillnaden med högst 0,01 för alla facit och ledtider. Fast klotter är en liten del av ytan på de här dagarna (F4 tar bort 0,7 % av blocken) och ger persistensen bara lite vid 5 mm.

**Varför uppgiftens premiss inte syns här.** Kedjan utan MEPS ligger inte under persistensen vid +1 h på någon träningsdag mot kartfacit, precis som på valideringsdagarna 2026-11-05 (kedjan vann alla 16). Svagheten i drift 4 och 5 november gällde Tim-KNEP med MEPS-blandningen och ett facit som såg lite regn. De här dagarna innehåller en vinterdag av den sorten (2021-01-23), och där syns det: mot mätarna förlorar kedjan mot persistensen vid +1 h och +5 h, fast den vinner mot radarn. Ett radarfacit kan alltså både blåsa upp kedjan vid +1 h och dölja att persistensen är bättre när radarn ser lite.

**Rekommendation (inte en ändring):** använd A2T som facit i `verify.py` vid sidan av radarn, inte i stället för den. Där A2T inte har sett mätaren är det bättre än radarn vid 1 mm, och det tar bort det mesta av den uppblåsta fördelen vid +1 h. Det skulle kräva:

1. att `--a2` är på i drift (användarens beslut, se 0004), och att A2T:s timsumma sparas som tal (som `cache/verif/src/`), inte bara som PNG i `a2/`;
2. att verifieringen väntar på A2T: A2T kommer 1 till 2,5 h efter timmen, och `verify.py` väntar redan 2,5 h efter sista timmen på mätarna (`GAUGE_DELAY`), så fördröjningen ändras inte, men A2T ska helst tas den senaste versionen (`a2_cykel` räknar om timmen när fler mätare kommer, under 3 h);
3. att måtten mot mätarna fortsatt räknas mot mätarna och inte mot A2T, och att A2T-facit och mätarfacit inte räknas som två oberoende bevis (A2T i mätarens ruta är nästan mätaren);
4. en ny grupp `a2t` i `Day` och i `verif.json`, och en rad på fliken Verifiering (en ändring av vad sidan visar, så användaren beslutar);
5. kontrollen av trasiga mätare per station och dygn (`IDEER.md`) innan A2T blir ett facit som modeller väljs mot.

**Vad i kedjan som troligen tappar vid +1 h (för mål 4).** Mot mätarna är kedjans fördel minst vid +1 h och kedjan har för lite regn där (kvot 0,914 mot 0,98 vid +2 h). Två kandidater i kedjan påverkar just de första kvartarna: platskartan, som rampas in de första 30 minuterna (`corr * min(1, (k+1)/6)`) och dämpar där senaste timmens 30-minutersprognoser var för höga, och den bilinjära flytten med fördelningsmatchning, som jämnar ut topparna i mätarnas rutor. Båda finns redan som avstängningar i projektionens domare (`kedja_utan_platskarta`, `kedja_utan_matchning`). Nästa steg är att köra dem med det här skriptets mätarfacit och A2T-facit på samma träningsdagar och se om kvoten och CSI vid +1 h mot mätarna går upp.

## Kostnaden

- `analys`: A0 och A1 324 till 453 s per dag (54 till 58 s där A1 redan fanns sparad), A2T med alla mätare 31 till 48 s för 24 timmar, korsvalideringen 105 till 142 s (5 grupper gånger 20 timmar). Totalt cirka 1 h 50 min för 15 dagar i en process.
- `kedja`: 355 till 505 s per dag, 18 till 24 s per utgåva och resten uppvärmningen av platskartan. Totalt cirka 1 h 45 min i en process, parallellt med analysen.
- `summera`: cirka 3 min (bootstrap med 2000 dragningar).
- Disk: 107 MB under `/data/projektion/facit_a2t/` (analys 64 MB, kedja 43 MB) och några nya rörelsefiler i den delade cachen. `/data` hade 4,6 GB ledigt efteråt.
- Minne: analysen cirka 1 GB (en dags bilder och A1), kedjan några hundra MB; högst två processer i taget.

## Filerna

- `experiments/projektion/facit_a2t.py` (nytt): de tre stegen.
- `experiments/projektion/facit_a2t_tabell.py` (nytt): tabellerna i markdown.
- `experiments/projektion/facit_a2t_perdag.py` (nytt): tabellen per dag.
- `experiments/projektion/results/facit_a2t.json` (nytt, 149 kB): alla tabeller med intervall och siffrorna per dag.
- Ingenting i `src/`, `deploy/`, `models/`, domarna eller `dagar.json`.
- Kvar i utcheckningen utan att vara committade (jag fick inte ta bort dem i den här sessionen): `experiments/projektion/facit_insp.py` (tre rader som kontrollerade klotterkartan) och `experiments/projektion/results/facit_a2t_prov.json` (provkörningen på en dag). Båda kan tas bort.

`uv run pytest`: 195 passerade.

## Nästa steg

1. **Mål 4:** kör `kedja_utan_platskarta` och `kedja_utan_matchning` mot mätarna och A2T med det här skriptet (lägg till systemet som ett val i steget `kedja`), för att se vad som ger kedjans underskott i mätarnas rutor vid +1 h.
2. **A2T som facit i drift:** rekommendationen ovan, ett beslut för användaren efter `--a2` (står under Frågor till användaren i `MAL.md` som en uppdatering av frågan om A2T).
3. **Fler vinterdagar:** träningsdagarna har få dagar där radarn ser lite (bara 2021-01-23 tydligt). Om planeraren vill veta hur ofta persistensen slår kedjan mot mätarna i november, behövs A1 för fler kalla träningsdagar (13 av 28 träningsdagar har ingen A1 ännu, cirka 6 min per dag).
4. **`IDEER.md`:** idén att pröva A2T som facit för prognosen är nu gjord; den kan ändras till "A2T som andra facit i `verify.py`" (väntar på användaren) och idén om klottrets inverkan på persistensen kan strykas (ger högst 0,01).

Status: klar
