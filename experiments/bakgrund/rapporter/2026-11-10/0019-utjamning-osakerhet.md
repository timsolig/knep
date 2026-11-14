# 0019 utjämning efter fältets osäkerhet

Disken: 2 470 MB ledigt vid start, 2 400 MB före `traning` (över 2 000 MB). Bara summor under `/data/projektion/domare/` skrevs.

## Kandidaten

`experiments/projektion/utjamning.py`, klassen `Utjamning` (ärver `domare.KedjaOm`; domaren och `src/` är orörda). Kedjans fält per kvart blandas linjärt mellan gaussfilter med fasta sigma 0, 4, 8, 16, 24 km, med ett sigma per ruta ur ett osäkerhetsmått utan facit:

- **a, två rörelsefält:** kedjans fält (tre bilder med 15 min) mot ett fält ur de tre senaste bilderna med 5 min. sigma = ka · |v1 − v2| · steg · ruta (km), utjämnat med gauss 32 km. ka = 1.
- **b, start 30 min tidigare:** bilden vid t−30 min flyttad med rörelsen då och bilden vid t flyttad med rörelsen nu, till kvartarnas mitt; u = medel|a − b| / (medel(a+b)/2 + 0,1) i block om 24 km; sigma = kb · u, kb = 8 km. Billig: ingen extra kedjekörning, 20 förflyttningar per start.
- Toppskydd: utdata = max(utjämnat, α · original). Under de första `fri` kvartarna ingen utjämning. Med sigma = 0 blir resultatet exakt kedjans (`test_utjamning.py`, 4 tester, går igenom).

Två fel rättades under provkörningen innan något sökt räknades: a fick ingen historik (`ctx.history` kräver 7 bilder), och b fick NaN utanför bilden i förflyttningen. Resultaten med klassnamnen `U_*` i `/data/projektion/domare/snabb/utjamning_U_*` är ogiltiga och ska ignoreras (de kan inte tas bort från sessionen); de giltiga heter `V_*`.

## Provkörning och tid

Ett dygn, 8 utgåvor, `snabb` (4 km): `forecast_seconds` 36,1 s för `kedja_om` mot 39,1 s för kandidaten (a och b), alltså cirka 0,4 s extra per utgåva på 4 km. På 2 km väntas cirka 4 gånger så mycket, cirka 1,5 till 2 s per cykel (grov mätning, Pi:n delades med driften och två processer). Under 5 s-målet. (Mätningen med den inledande bugg-versionen; de rättade körningarna tog 124 s per dygn mot ca 90 s för `kedja_om` inklusive domarens egen tid.)

## Sökningen i `snabb` (6 dygn, 48 utgåvor, 4 km)

Fyra varianter. Skillnad mot `kedja_om`, `csi1`/`fss1_30`/`csi5`/`fss5_10` positiv är bättre (tabellen visar csi med omvänt tecken, här omvänt till bättre = plus), `blockmax_q90` och `hopp` negativ är bättre. 95 %-intervallen i `/data/projektion/utjamning_snabb_*.md`.

| variant | mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|---|
| V_a1 (a, α 0,8) | csi1 | +0,001* | +0,006* | +0,011* | +0,013* | +0,010* | +0,013* |
| | fss1_30 | −0,000 | −0,002 | −0,004 | −0,010 | −0,013 | −0,004 |
| | blockmax_q90 | +0,036 sämre | +0,067 sämre | +0,089 sämre | +0,168 sämre | +0,150 sämre | +0,198 sämre |
| | hopp | −0,046* | −0,051* | −0,061* | −0,080* | | |
| V_b8 (b, α 0,8) | csi1 | −0,033 sämre | +0,008 | +0,021* | +0,015* | +0,010* | +0,007* |
| | blockmax_q90 | +0,167 sämre | +0,170 sämre | +0,139 sämre | +0,176 sämre | +0,154 sämre | +0,185 sämre |
| | hopp | −0,062* | −0,061* | −0,062* | −0,063* | | |
| V_ab (a och b, α 0,8) | csi1 | −0,033 sämre | +0,009 | +0,021* | +0,018* | +0,013* | +0,014* |
| | csi5 | −0,018 sämre | +0,010* | +0,017* | +0,011* | +0,009 | +0,009* |
| | fss1_30 | −0,018 sämre | −0,012 | −0,007 | −0,010 | −0,012 | −0,003 |
| | blockmax_q90 | +0,167 sämre | +0,170 sämre | +0,141 sämre | +0,181 sämre | +0,164 sämre | +0,201 sämre |
| | hopp | −0,078* | −0,078* | −0,084* | −0,096* | | |
| V_ab_f2_al95 (a och b, α 0,95, ingen utjämning första 30 min) | csi1 | 0 | 0 | +0,018* | +0,016* | +0,012* | +0,014* |
| | csi5 | 0 | 0 | +0,013* | +0,009* | +0,007* | +0,008* |
| | fss1_30 | 0 | 0 | −0,006 | −0,009 | −0,010 | 0,000 |
| | fss5_10 | 0 | 0 | −0,005 | −0,005 | −0,006 | −0,012 |
| | blockmax_q90 | 0 | 0 | +0,057 sämre | +0,061 sämre | +0,066 sämre | +0,069 sämre |
| | hopp | −0,040* | −0,040* | −0,064* | −0,076* | | |

Teckenförklaring: csi1, csi5, fss1_30, fss5_10 är angivna som (variant − `kedja_om`) i poäng, plus är bättre; `*` markerar att domaren (`!` sämre, `*` bättre) har intervallet helt på bättre sidan. Siffrorna är avlästa ur domarens tabeller (skillnadsraderna, `/data/projektion/utjamning_snabb_*.md`, där csi visas med omvänt tecken). `kedja_om` (snabb): csi1 0,734 / 0,575 / 0,414 / 0,271 / 0,207 / 0,146, fss1_30 0,979 / 0,933 / 0,825 / 0,654 / 0,536 / 0,401, hopp 1,438 / 1,445 / 1,447 / 1,456.

Anm. om fss1_30: variantens fss1_30 är lägre än `kedja_om` (till exempel V_a1 0,931 mot 0,933 vid 30 min och 0,644 mot 0,654 vid 2 h), domaren markerar det `!` (sämre) vid 30 min till 3 h. Det är alltså lite sämre FSS 1 mm på 30 km trots bättre CSI 1 mm; min tolkning, inte prövad, är att utjämningen breddar regnytan över tröskeln.

Ingen variant uppfyller kriteriet: `blockmax_q90` blir säkert sämre i alla fyra (minst +0,057 med α 0,95, vilket är ungefär den gräns log(0,95) = 0,051 som toppskyddet ger; utjämningen tar bort toppen så fort α < 1), och `fss1_30` blir svagt sämre. Hoppet blir däremot säkert bättre, −0,04 till −0,096, åt rätt håll.

**Fryst:** `V_ab_f2_al95` (minst skada på blockmaxet, ingen utjämning de första 30 min eftersom csi1 och csi5 blev sämre vid 15 min för b). Frysning trots att den inte uppfyller kriteriet, för att få `traning`-siffrorna.

## `traning` (12 dagar, 2 km)

Den frysta `V_ab_f2_al95` på samma 12 träningsdagar som i 0018 (96 utgåvor, 2 km; `kedja_om` och `persistens` återanvända ur 0018). Tabell: `/data/projektion/utjamning_traning_tabell.md`. Poäng variant − `kedja_om` (plus bättre för csi och fss), `*` bättre och `!` sämre enligt domaren:

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 (`kedja_om` 0,674 / 0,513 / 0,359 / 0,219 / 0,159 / 0,107) | 0 | 0 | +0,024* | +0,025* | +0,021* | +0,018* |
| csi5 | 0 | 0 | +0,013* | +0,012* | +0,011* | +0,008 |
| fss1_30 (0,978 / 0,922 / 0,807 / 0,613 / 0,486 / 0,354) | 0 | 0 | −0,015 sämre | −0,009 | −0,005 | +0,004 |
| fss5_10 (0,892 / 0,747 / 0,534 / 0,314 / 0,217 / 0,120) | 0 | 0 | +0,001 | +0,014* | +0,019* | +0,018 |
| blockmax_q90 (|log kvot|, + är sämre) | 0 | 0 | +0,057 sämre | +0,061 sämre | +0,064 sämre | +0,089 sämre |
| hopp (1,442 / 1,453 / 1,457 / 1,476) | −0,074* | −0,075* | −0,137* | −0,170* | | |

(fss5_10 här: domarens tabell visar träffmått med omvänt tecken; variantens fss5_10 är högre än kedjans vid 2 och 3 h, 0,328 mot 0,314 och 0,236 mot 0,217, och markeras `*`.) Resultatet från `snabb` håller på de andra dagarna och är större: csi1 +0,018 till +0,025 vid 1 till 5 h (6 till 11 % av luckan till 1 vid 1 h: 0,024 av 0,641), hopp klart bättre (−0,07 till −0,17, även vid 15 och 30 min där inget utjämnas, eftersom prognoserna för samma tid hänger ihop), men `blockmax_q90` säkert sämre vid 1 till 5 h (+0,057 till +0,089) och fss1_30 sämre vid 1 h.

Körtid på 2 km: `forecast_seconds` per utgåva 15,3 s för `kedja_om` mot 51,8 s för kandidaten (genomsnitt för två av dygnen, två processer, Pi:n delad med driften), alltså cirka 36 s extra. **Det är långt över målet på 5 s** och skulle med en cykel på under två minuter vara oacceptabelt (kedjan ensam ligger på 15 s). Orsaken är sannolikt de normaliserade gaussfiltren (`smooth` gör två filter per nivå, sigma upp till 12 pixlar, fyra nivåer, 18 kvartar) plus en extra Lucas-Kanade; det är inte profilerat. Billigare vägar: filtrera på 4 km och interpolera upp, färre nivåer, utjämna bara var 2:a kvart och interpolera mellan dem, eller använd `cv2.GaussianBlur` utan normalisering.

## Jämförelse med taken

- Utjämningstaket `TakUtjamningBast` (0017, i efterhand per utgåva): CSI 1 mm +0,010 till +0,044 vid 30 min till 3 h. Kandidaten tar +0,016 till +0,018 csi1 vid 1 till 2 h på `snabb` utan facit, vilket är i samma storleksordning som taket (se 0017 för exakta tal per ledtid; jag har inte räknat någon exakt andel), men taket väljer sigma på FSS 1 mm och kandidaten tappar blockmaxet. Kandidaten tar ingenting vid 15 till 30 min (fri = 2).
- `TV_t60_b64` (0018): CSI 1 mm +0,008 vid 1 h på `traning`. Utjämningen ger mer csi1 (+0,018 vid 1 h på `snabb`) och lagar hoppet i stället för att förvärra det (−0,06 mot +0,035 för tillväxten).
- Hopp påverkas åt rätt håll: −0,04 till −0,10 i alla varianter.

## Redo för validering?

Nej, inte som den är. Spärren `blockmax_q90` blir säkert sämre och fss1_30 svagt sämre. Det som talar för den är hoppet och csi1/csi5 vid 1 till 5 h. Nästa försök borde skydda toppen på ett annat sätt än en golvandel, till exempel utjämna bara rutor under en intensitetsgräns (men rutorna kring toppen utjämnas då fortfarande) eller bevara blockmaxet genom att lägga tillbaka blockets max efter utjämningen, och prova bara 1 till 5 h. Skulle den bedömas på `validering` ihop med tillväxten ur 0018 är hoppet den gemensamma nämnaren som bör följas.

## Kostnad på Pi:n

Cirka 0,4 s per utgåva på 4 km men mätt cirka 36 s extra per utgåva på 2 km (15,3 s för kedjan mot 51,8 s), så den skalade inte med 4 som väntat; tidsuppskattningen i provkörningen ovan (1,5 till 2 s) var fel. Ingen extra kedjekörning. Max två processer användes; körtiden på `traning` var cirka 650 s per dygn med två processer.

## Filer

`experiments/projektion/utjamning.py`, `experiments/projektion/test_utjamning.py`, denna rapport. Summor under `/data/projektion/domare/{snabb,traning}/utjamning_*`, tabeller `/data/projektion/utjamning_snabb_*.md` och `utjamning_traning_tabell.md`.

Kort: På 12 träningsdagar (2 km) ger den frysta utjämningen csi1 +0,018 till +0,025 och csi5 +0,008 till +0,013 vid 1 till 5 h och säkert lägre hopp (−0,07 till −0,17), men blockmax_q90 blir säkert sämre (+0,057 till +0,089), fss1_30 sämre vid 1 h och kostnaden är 36 s extra per utgåva på 2 km (mot 5 s-målet), så den klarar varken spärren eller tiden.
Säkerställd förbättring: nej
Status: delvis
