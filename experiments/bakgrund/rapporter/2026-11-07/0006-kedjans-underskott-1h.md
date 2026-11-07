# Uppgift 0006: vad i kedjan ger underskottet vid +1 h mot mätarna

Kort: varken platskartan eller fördelningsmatchningen förklarar underskottet; utan platskartan blir kedjans kvot mot mätarna vid +1 h 0,920 och utan matchningen 0,919 mot kedjans 0,914 (skillnad +0,006, 95 % −0,015 till +0,043, och +0,005, −0,002 till +0,011), alltså under en tiondel av avståndet till 0,98; det mesta av "underskottet" är att radarn själv har kvoten 0,941 mot mätarna just de målen (kedjan är 0,971 av radarn vid mätarna), och resten av förlusten under första timmen sitter vid täckningens rand (kvoten mot radarn 0,778 vid +60 min inom 50 km från randen, 0,980 inne i området).

Uppgiften byggde på `rapporter/2026-11-07/0005-prognos-mot-a2t-facit.md`, som jag läste först, och på `experiments/projektion/facit_a2t.py`. Ingen domare, `KedjaOm` eller något i `src/`, `deploy/` eller `models/` ändrades. Bara de 15 träningsdagarna ur 0005 (`dagar()` i skriptet, genom analysens `domare.days("traning")`) lästes; valideringen och testdelen rördes inte, inte heller deras mätare (`load_gauges` filtrerar på dagen).

## Vad jag gjorde

1. **`facit_a2t.py kedja --system <namn>`**: kör ett system ur projektionens `SYSTEMS` (`make_system`) och sparar timsummorna under `/data/projektion/facit_a2t/<namn>/`. `kedja` (standard) är som förut `KedjaOm()`. Dessutom sparas den första timmens fyra kvartar (+15 till +60 min, kodade som värdefilen) under `kvartar/<namn>/`, och för `kedja` också radarns egna kvartar (`ctx.quarter`, kompositen utan utfyllnad) för samma tider. Finns timfilen redan räknas den om och jämförs bit för bit, men skrivs inte över. System med `warm = False` (utan platskarta) värms inte upp: tillståndet läses bara av `location_map`, så resultatet är detsamma och det går dubbelt så fort. `--prov` kör bara utgåvan 12 UTC till `prov/`.
2. **`summera --varianter ...`**: varianterna räknas på samma utgåvor, rutor och mätartimmar som kedjan (skriptet avbryter om en variant saknas där kedjan finns), med samma dragningar i bootstrap (B = 2000, 95 %). Nya tabeller: variant minus persistensen, variant minus `kedja` (också själva kvoten, inte bara |ln kvot|), och kvoten per kvart mot kvartsmätarna p14, mot radarns kvart i p14-mätarnas rutor och mot radarns kvart över hela fältet. Till `results/facit_a2t_varianter.json`; tabellerna skrivs med `facit_a2t_varianter_tabell.py`.
3. **Kontrollen av `kedja`**: omkörningen av `kedja` (för kvartarna) gav bitvis samma timsummor som de sparade på alla 15 dagar och 90 utgåvor, och `summera` utan varianter gav en fil som är byte för byte lika med `results/facit_a2t.json` (`cmp`).
4. **Provkörning** på 2020-07-24, utgåvan 12 UTC: `kedja` lika med den sparade (31 s), `kedja_utan_platskarta` 16 s.
5. **Randen** (`facit_a2t_rand.py`): kedjans kvartar mot radarns kvartar för rutor inom 50 km från täckningens rand och inne i området, eftersom kvoten över hela fältet föll med ledtiden.

## Tabellerna

Alla 15 dagar, 90 utgåvor, alla rutor (utan mask). Skillnaderna är variant minus `kedja` med 95 %-intervall; * betyder att intervallet ligger helt på ena sidan. Positivt i CSI och FSS, negativt i MAE är bättre för varianten; för kvoten är positivt mer regn.

### Facit radarn (A0)

| mått | system | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|---|
| CSI 1 | kedja | 0,598 | 0,357 | 0,259 | 0,209 | 0,177 |
| CSI 1 | utan platskarta | 0,591 | 0,356 | 0,257 | 0,208 | 0,177 |
| CSI 1 | utan matchning | 0,599 | 0,359 | 0,261 | 0,210 | 0,178 |
| CSI 1 | persistens | 0,340 | 0,207 | 0,158 | 0,130 | 0,107 |
| CSI 5 | kedja | 0,382 | 0,160 | 0,086 | 0,066 | 0,059 |
| CSI 5 | utan platskarta | 0,377 | 0,156 | 0,082 | 0,062 | 0,058 |
| CSI 5 | utan matchning | 0,384 | 0,161 | 0,087 | 0,066 | 0,059 |
| FSS 1/10 | kedja | 0,850 | 0,623 | 0,492 | 0,414 | 0,361 |
| FSS 1/10 | utan platskarta | 0,845 | 0,621 | 0,488 | 0,413 | 0,361 |
| FSS 1/10 | utan matchning | 0,851 | 0,624 | 0,493 | 0,416 | 0,362 |
| kvot | kedja | 0,971 | 0,955 | 0,952 | 0,954 | 0,976 |
| kvot | utan platskarta | 0,964 | 0,959 | 0,953 | 0,953 | 0,975 |
| kvot | utan matchning | 0,972 | 0,955 | 0,951 | 0,953 | 0,975 |
| MAE | kedja | 0,119 | 0,202 | 0,243 | 0,264 | 0,273 |
| MAE | utan platskarta | 0,119 | 0,203 | 0,244 | 0,264 | 0,273 |
| MAE | utan matchning | 0,117 | 0,199 | 0,240 | 0,262 | 0,271 |

| utan platskarta − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | −0,006 (−0,009 till −0,004) * | −0,002 (−0,004 till 0,000) | −0,002 (−0,004 till −0,001) * | −0,001 (−0,003 till 0,001) | −0,000 (−0,002 till 0,001) |
| CSI 5 | −0,005 (−0,010 till 0,003) | −0,004 (−0,008 till 0,003) | −0,004 (−0,009 till 0,001) | −0,004 (−0,006 till −0,001) * | −0,001 (−0,002 till 0,001) |
| FSS 1/10 | −0,005 (−0,007 till −0,003) * | −0,002 (−0,004 till 0,001) | −0,003 (−0,006 till −0,001) * | −0,001 (−0,005 till 0,001) | −0,000 (−0,003 till 0,002) |
| kvot | −0,007 (−0,019 till 0,010) | 0,004 (−0,011 till 0,022) | 0,001 (−0,010 till 0,013) | −0,001 (−0,009 till 0,008) | −0,001 (−0,008 till 0,005) |
| MAE | 0,000 (−0,001 till 0,002) | 0,002 (−0,000 till 0,005) | 0,001 (−0,000 till 0,003) | 0,000 (−0,001 till 0,002) | −0,000 (−0,001 till 0,001) |

| utan matchning − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,002 (0,001 till 0,002) * | 0,002 (0,001 till 0,002) * | 0,001 (0,001 till 0,002) * | 0,001 (0,001 till 0,002) * | 0,001 (0,000 till 0,001) * |
| CSI 5 | 0,002 (0,000 till 0,004) | 0,001 (−0,001 till 0,002) | 0,001 (−0,001 till 0,002) | 0,001 (−0,001 till 0,002) | 0,001 (−0,000 till 0,002) |
| FSS 1/10 | 0,001 (0,000 till 0,001) * | 0,002 (0,001 till 0,002) * | 0,002 (0,001 till 0,002) * | 0,002 (0,001 till 0,003) * | 0,001 (0,000 till 0,002) * |
| kvot | 0,001 (−0,001 till 0,003) | 0,000 (−0,002 till 0,003) | −0,001 (−0,003 till 0,001) | −0,001 (−0,003 till 0,001) | −0,001 (−0,003 till 0,000) |
| MAE | −0,002 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * |

### Facit A2T

| mått | system | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|---|
| CSI 1 | kedja | 0,523 | 0,337 | 0,252 | 0,205 | 0,176 |
| CSI 1 | utan platskarta | 0,520 | 0,336 | 0,250 | 0,203 | 0,175 |
| CSI 1 | utan matchning | 0,525 | 0,339 | 0,254 | 0,206 | 0,177 |
| CSI 5 | kedja | 0,310 | 0,152 | 0,083 | 0,066 | 0,058 |
| CSI 5 | utan platskarta | 0,301 | 0,148 | 0,080 | 0,062 | 0,056 |
| CSI 5 | utan matchning | 0,313 | 0,153 | 0,085 | 0,066 | 0,059 |
| FSS 1/10 | kedja | 0,780 | 0,592 | 0,478 | 0,405 | 0,356 |
| FSS 1/10 | utan platskarta | 0,777 | 0,591 | 0,475 | 0,403 | 0,356 |
| FSS 1/10 | utan matchning | 0,781 | 0,594 | 0,480 | 0,406 | 0,358 |
| kvot | kedja | 0,990 | 0,965 | 0,970 | 0,967 | 0,979 |
| kvot | utan platskarta | 0,983 | 0,969 | 0,971 | 0,966 | 0,978 |
| kvot | utan matchning | 0,991 | 0,966 | 0,970 | 0,965 | 0,977 |
| MAE | kedja | 0,139 | 0,206 | 0,241 | 0,262 | 0,272 |
| MAE | utan platskarta | 0,140 | 0,208 | 0,242 | 0,263 | 0,271 |
| MAE | utan matchning | 0,137 | 0,204 | 0,238 | 0,260 | 0,269 |

| utan platskarta − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | −0,004 (−0,006 till −0,001) * | −0,001 (−0,003 till 0,001) | −0,003 (−0,004 till −0,001) * | −0,001 (−0,003 till 0,000) | −0,000 (−0,002 till 0,001) |
| CSI 5 | −0,009 (−0,019 till 0,003) | −0,004 (−0,010 till 0,003) | −0,004 (−0,009 till 0,002) | −0,003 (−0,007 till −0,000) * | −0,002 (−0,004 till 0,001) |
| FSS 1/10 | −0,003 (−0,005 till −0,000) * | −0,001 (−0,004 till 0,002) | −0,004 (−0,006 till −0,002) * | −0,002 (−0,005 till 0,000) | −0,001 (−0,003 till 0,001) |
| kvot | −0,007 (−0,019 till 0,011) | 0,004 (−0,011 till 0,024) | 0,001 (−0,010 till 0,014) | −0,001 (−0,009 till 0,008) | −0,001 (−0,008 till 0,005) |
| MAE | 0,000 (−0,002 till 0,004) | 0,002 (−0,001 till 0,005) | 0,001 (−0,000 till 0,003) | 0,000 (−0,001 till 0,002) | −0,000 (−0,001 till 0,001) |

| utan matchning − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,001 (0,000 till 0,003) * | 0,002 (0,001 till 0,002) * | 0,001 (0,001 till 0,002) * | 0,001 (0,001 till 0,002) * | 0,001 (0,001 till 0,002) * |
| CSI 5 | 0,003 (−0,000 till 0,007) | 0,001 (−0,001 till 0,003) | 0,001 (−0,001 till 0,003) | 0,001 (−0,001 till 0,002) | 0,001 (−0,000 till 0,003) |
| FSS 1/10 | 0,001 (−0,000 till 0,002) | 0,002 (0,001 till 0,002) * | 0,001 (0,001 till 0,002) * | 0,002 (0,001 till 0,003) * | 0,001 (0,001 till 0,002) * |
| kvot | 0,001 (−0,001 till 0,003) | 0,000 (−0,002 till 0,003) | −0,001 (−0,003 till 0,001) | −0,001 (−0,003 till 0,001) | −0,001 (−0,003 till 0,000) |
| MAE | −0,002 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * | −0,003 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * | −0,002 (−0,003 till −0,002) * |

### Facit mätarna (p7 i mätarens ruta)

Samma mätartimmar för alla system (12 217 vid +1 h, 11 599 vid +5 h). FSS finns inte mot mätarna. Radarns (A0:s) egen kvot mot samma mätartimmar står med, eftersom den förklarar det mesta.

| mått | system | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|---|
| CSI 1 | kedja | 0,392 | 0,319 | 0,241 | 0,193 | 0,164 |
| CSI 1 | utan platskarta | 0,398 | 0,331 | 0,236 | 0,193 | 0,165 |
| CSI 1 | utan matchning | 0,398 | 0,323 | 0,242 | 0,196 | 0,166 |
| CSI 1 | persistens | 0,288 | 0,177 | 0,132 | 0,105 | 0,094 |
| CSI 5 | kedja | 0,194 | 0,107 | 0,028 | 0,042 | 0,037 |
| CSI 5 | utan platskarta | 0,188 | 0,099 | 0,050 | 0,042 | 0,036 |
| CSI 5 | utan matchning | 0,206 | 0,102 | 0,030 | 0,044 | 0,038 |
| kvot | kedja | 0,914 (0,815 till 1,029) | 0,982 (0,869 till 1,138) | 0,964 | 0,888 | 0,935 |
| kvot | utan platskarta | 0,920 (0,810 till 1,065) | 1,003 (0,869 till 1,188) | 0,986 | 0,895 | 0,931 |
| kvot | utan matchning | 0,919 (0,823 till 1,032) | 0,980 (0,868 till 1,134) | 0,964 | 0,893 | 0,940 |
| kvot | persistens | 0,948 | 0,870 | 0,874 | 0,870 | 0,898 |
| kvot | radarn (A0) samma timme | 0,941 (0,832 till 1,073) | 0,961 (0,830 till 1,107) | 0,973 | 0,941 | 0,961 |
| kvot | kedja / radarn | 0,971 | 1,022 | 0,991 | 0,944 | 0,973 |
| MAE | kedja | 0,212 | 0,281 | 0,314 | 0,319 | 0,343 |
| MAE | utan platskarta | 0,214 | 0,285 | 0,318 | 0,320 | 0,341 |
| MAE | utan matchning | 0,210 | 0,277 | 0,310 | 0,317 | 0,341 |

| utan platskarta − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,005 (−0,004 till 0,013) | 0,011 (−0,001 till 0,025) | −0,004 (−0,012 till 0,003) | 0,000 (−0,005 till 0,005) | 0,001 (−0,003 till 0,004) |
| CSI 5 | −0,006 (−0,050 till 0,035) | −0,008 (−0,021 till 0,003) | 0,021 (0,000 till 0,039) | 0,000 (−0,002 till 0,002) | −0,001 (−0,002 till 0,002) |
| kvot | 0,006 (−0,015 till 0,043) | 0,021 (−0,005 till 0,057) | 0,022 (0,004 till 0,044) * | 0,007 (−0,002 till 0,016) | −0,004 (−0,012 till 0,003) |
| MAE | 0,001 (−0,004 till 0,009) | 0,004 (−0,002 till 0,011) | 0,004 (0,001 till 0,009) * | 0,001 (−0,001 till 0,003) | −0,001 (−0,003 till 0,001) |

| utan matchning − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |
|---|---|---|---|---|---|
| CSI 1 | 0,006 (0,001 till 0,010) * | 0,003 (−0,000 till 0,007) | 0,001 (−0,003 till 0,005) | 0,002 (−0,001 till 0,006) | 0,002 (−0,001 till 0,004) |
| CSI 5 | 0,011 (0,003 till 0,021) * | −0,004 (−0,020 till 0,006) | 0,002 (0,000 till 0,004) | 0,002 (0,000 till 0,004) | 0,001 (0,000 till 0,003) |
| kvot | 0,005 (−0,002 till 0,011) | −0,002 (−0,009 till 0,004) | −0,000 (−0,010 till 0,006) | 0,004 (0,001 till 0,008) * | 0,004 (0,001 till 0,009) * |
| MAE | −0,002 (−0,004 till −0,001) * | −0,004 (−0,007 till −0,002) * | −0,004 (−0,007 till −0,002) * | −0,002 (−0,004 till −0,001) * | −0,002 (−0,002 till −0,001) * |

### Kvoten per kvart under den första timmen

Kvartarna efter utgåvan (+15 min är bilderna +5, +10 och +15 min). Mot p14 i mm per kvart i mätarens ruta (10 543 till 10 698 mätarkvartar per kvart); radarn är radarns egen kvart vid samma mätare.

| mot kvartsmätarna p14 | +15 min | +30 min | +45 min | +60 min |
|---|---|---|---|---|
| radarn | 0,912 (0,806 till 1,044) | 0,887 (0,776 till 1,019) | 0,855 (0,733 till 1,042) | 0,900 (0,788 till 1,071) |
| kedja | 0,891 (0,783 till 1,031) | 0,821 (0,729 till 0,935) | 0,853 (0,735 till 1,037) | 0,845 (0,726 till 1,005) |
| utan platskarta | 0,889 (0,777 till 1,033) | 0,825 (0,720 till 0,957) | 0,875 (0,736 till 1,111) | 0,865 (0,726 till 1,077) |
| utan matchning | 0,899 (0,792 till 1,034) | 0,829 (0,741 till 0,944) | 0,859 (0,744 till 1,039) | 0,852 (0,736 till 1,011) |
| utan platskarta − kedja | −0,002 (−0,011 till 0,011) | 0,004 (−0,012 till 0,028) | 0,022 (−0,007 till 0,083) | 0,020 (−0,008 till 0,077) |
| utan matchning − kedja | 0,008 (0,002 till 0,014) * | 0,008 (−0,004 till 0,016) | 0,006 (−0,000 till 0,010) | 0,007 (0,003 till 0,011) * |

| mot radarns kvart, p14-mätarnas rutor | +15 min | +30 min | +45 min | +60 min |
|---|---|---|---|---|
| kedja | 0,977 (0,945 till 1,009) | 0,926 (0,889 till 0,963) | 0,998 (0,883 till 1,120) | 0,939 (0,847 till 1,023) |
| utan platskarta | 0,975 (0,942 till 1,009) | 0,931 (0,889 till 0,971) | 1,024 (0,895 till 1,153) | 0,961 (0,859 till 1,048) |
| utan matchning | 0,986 (0,958 till 1,016) | 0,934 (0,895 till 0,976) | 1,005 (0,889 till 1,125) | 0,947 (0,858 till 1,027) |

| mot radarns kvart, hela fältet | +15 min | +30 min | +45 min | +60 min |
|---|---|---|---|---|
| kedja | 0,985 (0,974 till 0,994) | 0,977 (0,955 till 0,994) | 0,958 (0,930 till 0,981) | 0,949 (0,924 till 0,972) |
| utan platskarta | 0,976 (0,968 till 0,985) | 0,964 (0,952 till 0,976) | 0,952 (0,936 till 0,967) | 0,950 (0,933 till 0,965) |
| utan matchning | 0,984 (0,973 till 0,994) | 0,979 (0,957 till 0,996) | 0,960 (0,932 till 0,982) | 0,951 (0,926 till 0,972) |
| utan platskarta − kedja | −0,008 (−0,013 till −0,002) * | −0,013 (−0,026 till 0,004) | −0,006 (−0,023 till 0,016) | 0,001 (−0,016 till 0,022) |
| utan matchning − kedja | −0,000 (−0,001 till 0,001) | 0,002 (−0,000 till 0,004) | 0,002 (−0,000 till 0,004) | 0,001 (−0,001 till 0,003) |

Kedjan mot radarns kvart, uppdelat efter avståndet till täckningens rand vid utgåvan (`facit_a2t_rand.py`, inga intervall):

| | +15 min | +30 min | +45 min | +60 min | andel av radarns regn |
|---|---|---|---|---|---|
| inom 50 km från randen | 0,963 | 0,885 | 0,817 | 0,778 | 15 till 16 % |
| längre in | 0,989 | 0,995 | 0,985 | 0,980 | 84 till 85 % |

### Per dag vid +1 h mot mätarna

| dag | CSI 1 kedja | utan platskarta | utan matchning | persistens | kvot kedja | utan platskarta | utan matchning | persistens |
|---|---|---|---|---|---|---|---|---|
| 2020-02-10 | 0,205 | 0,190 | 0,184 | 0,191 | 0,86 | 0,85 | 0,87 | 1,09 |
| 2020-05-01 | 0,459 | 0,494 | 0,476 | 0,344 | 0,99 | 0,94 | 0,98 | 1,12 |
| 2020-07-24 | 0,356 | 0,359 | 0,356 | 0,248 | 0,98 | 0,99 | 0,98 | 0,90 |
| 2020-08-29 | 0,490 | 0,485 | 0,495 | 0,331 | 0,99 | 0,98 | 0,98 | 1,14 |
| 2020-10-07 | 0,295 | 0,292 | 0,312 | 0,228 | 1,20 | 1,22 | 1,22 | 1,57 |
| 2021-01-23 | 0,111 | 0,105 | 0,111 | 0,136 | 0,54 | 0,55 | 0,55 | 0,57 |
| 2021-05-11 | 0,384 | 0,382 | 0,387 | 0,394 | 1,75 | 2,13 | 1,76 | 1,69 |
| 2022-12-20 | 0,231 | 0,246 | 0,231 | 0,200 | 0,60 | 0,62 | 0,61 | 0,68 |
| 2023-01-04 | 0,433 | 0,444 | 0,434 | 0,293 | 0,85 | 0,85 | 0,86 | 0,85 |
| 2023-07-12 | 0,570 | 0,590 | 0,564 | 0,344 | 0,97 | 0,95 | 0,97 | 0,86 |
| 2023-11-22 | 0,309 | 0,320 | 0,306 | 0,183 | 0,81 | 0,79 | 0,81 | 0,78 |
| 2024-07-28 | 0,143 | 0,140 | 0,143 | 0,104 | 1,62 | 1,62 | 1,54 | 1,24 |
| 2024-09-26 | 0,511 | 0,489 | 0,522 | 0,324 | 0,73 | 0,69 | 0,74 | 0,70 |
| 2025-06-23 | 0,374 | 0,390 | 0,387 | 0,280 | 0,80 | 0,81 | 0,80 | 0,83 |
| 2025-10-24 | 0,430 | 0,455 | 0,450 | 0,436 | 0,68 | 0,67 | 0,69 | 0,75 |

Varianterna rör CSI 1 mm per dag med högst 0,035 (utan platskarta 2020-05-01). På två dagar där kedjan och persistensen ligger nära varandra byter skillnaden tecken: 2020-02-10 (kedjan 0,205 mot persistensens 0,191, båda varianterna under) och 2025-10-24 (kedjan 0,430 mot 0,436, båda varianterna över). Kvoterna per dag går från 0,54 till 1,75, och dagarna med de största mätarsummorna styr den sammanlagda kvoten; därför är intervallen för kvoten mot mätarna så breda (0,815 till 1,029 för kedjan vid +1 h).

## Svaret

**Minskar platskartan eller fördelningsmatchningen kedjans regn i mätarnas rutor vid +1 h?** Bara lite, och inte så att det syns säkert. Med platskartan avstängd stiger kvoten mot mätarna vid +1 h från 0,914 till 0,920 (+0,006, −0,015 till +0,043), med matchningen avstängd till 0,919 (+0,005, −0,002 till +0,011). Avståndet till 0,982 vid +2 h är 0,068, så platskartan förklarar cirka 9 % och matchningen cirka 7 % av det, ingen av dem med intervallet helt på ena sidan. Över hela fältet gör platskartan tvärtom kedjan något våtare de första 30 minuterna (utan den faller kvoten mot radarn med 0,008 vid +15 min, intervallet helt under noll). Per kvart mot p14 finns ingen kvart där platskartan tar bort regn säkert; matchningen tar bort 0,7 till 0,8 % i mätarnas rutor (+15 och +60 min med intervallet helt över noll), vilket stämmer med att den jämnar ut topparna.

**Var underskottet kommer ifrån.** Det mesta är facit, inte kedjan:

- Radarn själv har kvoten 0,941 mot mätarna vid samma mätartimmar som +1 h, men 0,961 vid +2 h. Kedjan i mätarnas rutor är 0,971 av radarn vid +1 h och 1,022 vid +2 h. Skillnaden mellan +1 h och +2 h är alltså till cirka en tredjedel radarns egen kvot för de målen och till två tredjedelar att kedjan råkar ligga över radarn vid +2 h; båda ligger långt inne i intervallen (kedjans kvot 0,815 till 1,029 vid +1 h och 0,869 till 1,138 vid +2 h). Kvoten 0,914 mot 0,982 är inte ett säkert mönster.
- Det kedjan förlorar under första timmen mot radarn är litet i mätarnas rutor (0,977 vid +15 min, 0,926 vid +30 min, 0,998 vid +45 min, 0,939 vid +60 min, brett) och över hela fältet en jämn förlust som växer med ledtiden (0,985, 0,977, 0,958, 0,949). Underskottet finns alltså inte redan vid +15 min; det växer.
- Förlusten över fältet sitter vid täckningens rand: inom 50 km från randen faller kvoten mot radarn till 0,778 vid +60 min, längre in bara till 0,980. Det är regn som flyttas ut ur området utan att något kommer in i stället (kedjan fyller inte utsidan, `inflow = 0`). Vid mätarna, som oftast ligger inne i området, väger det mindre.
- Mot p14 ser +30 min sämst ut för kedjan (0,821 mot radarns 0,887) i alla tre varianterna, alltså varken platskartan eller matchningen. Intervallet mot radarn i mätarnas rutor ligger helt under 1 där (0,889 till 0,963) men inte vid +45 min, så det kan vara slumpen i vilka kvartar som har stora mätarsummor; det är inget jag skulle bygga på.

**Vad kostar varianterna vid +2 till +5 h och i kartmåtten?** Utan platskartan blir kartmåtten sämre vid +1 h (CSI 1 mm −0,006 mot radarn och −0,004 mot A2T, FSS 1/10 −0,005 och −0,003, intervallen helt under noll) och vid +3 h, och kvoten mot mätarna högre vid +3 h (0,986 mot 0,964, intervallet helt över). Platskartan gör alltså nytta i kartorna och ska stå kvar. Utan matchningen blir kedjan något bättre överallt: CSI 1 mm +0,001 till +0,002, FSS 1/10 +0,001 till +0,002 och MAE −0,002 mot radarn och A2T vid alla ledtider, och mot mätarna CSI 1 mm +0,006 och CSI 5 mm +0,011 vid +1 h och MAE −0,002 till −0,004 vid alla ledtider, intervallen helt på den bättre sidan. Det är små vinster på träningsdagarna, men de pekar åt samma håll överallt. Det är en diagnos på träningen och inte en bedömning: ett system utan matchningen ska bedömas av projektionens domare på `validering` (där spärrarna för extremerna kan gå åt andra hållet, eftersom matchningen finns för att hålla fördelningen).

## Kostnaden

- `kedja_utan_platskarta` 90 till 134 s per dag (ingen uppvärmning), cirka 26 min för 15 dagar; `kedja_utan_matchning` 157 till cirka 200 s per dag, cirka 45 min; omkörningen av `kedja` för kvartarna 201 till 286 s per dag, cirka 50 min i två processer. Mycket fortare än de 1 h 45 min som 0005 tog, eftersom rörelsefälten redan låg i cachen.
- `summera` med varianterna cirka 25 min (fyra system, tre masker, två kartfacit och kvartarna), kontrollen utan varianter cirka 10 min, `facit_a2t_rand.py` under en minut. `uv run pytest` 7 min 40 s.
- Disk: 182 MB ny under `/data/projektion/facit_a2t/` (44 och 43 MB timsummor för varianterna, 95 MB kvartar, 1,7 MB prov). `/data` hade 4,4 GB ledigt efteråt.
- Minne: högst cirka 1 GB per process (summera), två processer i taget.

## Filerna

- `experiments/projektion/facit_a2t.py`: `--system`, `--prov` och kvartarna i steget `kedja`; `--varianter`, skillnaden mot kedjan och kvartstabellerna i steget `summera`. `kedja` räknas som förut (bitvis lika, och `facit_a2t.json` byte för byte lika).
- `experiments/projektion/facit_a2t_varianter_tabell.py` (nytt): tabellerna ovan.
- `experiments/projektion/facit_a2t_rand.py` (nytt): kvoten vid randen och inne i området.
- `experiments/projektion/results/facit_a2t_varianter.json` (nytt, 372 kB).
- Kvar okommitterad: `experiments/projektion/results/facit_a2t_kontroll.json` (kontrollkörningen, lika med `facit_a2t.json`); jag fick inte ta bort filer i den här sessionen, och den kan tas bort. `facit_insp.py` och `facit_a2t_prov.json` fanns inte längre.

## Nästa steg

1. **Underskottet vid +1 h behöver ingen egen rättelse.** Det är inte platskartan eller matchningen, och det mesta är radarns egen kvot mot mätarna för de målen plus slumpen mellan målen. Planeraren kan stryka idén om underskottet vid +1 h i `IDEER.md` och i stället se det som radarns underskott (A2T eller volymkorrektionen, mål 1 och 3).
2. **Inflödet vid randen**: kedjan tappar cirka 22 % av regnet inom 50 km från randen den första timmen. `model.Chain` har redan `inflow` (fyller utsidan från randen); `KedjaOm(inflow=...)` med några värden väljs på `traning` mot radarn och A2T (kvoten och FSS vid randen) och bedöms på `validering` med projektionens domare. Det rör främst kartmåtten, inte mätarna.
3. **Kedjan utan matchningen** gav små men samstämmiga vinster på träningsdagarna mot alla tre facit. Värt att köra `kedja_utan_matchning` i projektionens domare på `validering` (systemet finns redan i `SYSTEMS`), med blicken på spärrarna för extremerna (percentilerna och blockmaxet), innan något mer byggs på matchningen.
4. Platskartan står kvar: den hjälper kartmåtten vid +1 och +3 h och är inte orsaken till underskottet; att rampa in den långsammare har ingen grund i de här siffrorna.

Status: klar
