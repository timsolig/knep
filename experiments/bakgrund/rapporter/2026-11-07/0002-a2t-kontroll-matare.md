# Uppgift 0002: kontrollen av regnmätarna i indata till A2T (A2TK)

Kort: Kontrollen jämför varje mätare med grannarna inom R km och med A2T:s bakgrund och kastar den bara när båda säger emot. Med valda T = 3 och R = 50 km per kvart och T = 2,5 och R = 50 km per timme kastas 0,09 % av kvartarna och 0,11 % av timmarna på träningen, och ingen över 400 m. A2TK slår fortfarande A1 och A0 enligt domaren, men den kan inte ersätta A2T. Mot A2T är den bättre i MAE men sämre med intervallet helt på fel sida i bland annat summakvoten (kvart 0,846 mot 0,851, −0,006, −0,009 till −0,002) och FSS 1 per kvart (0,389 mot 0,392, −0,003, −0,006 till −0,001), eftersom 9 av 10 kastade perioder är för våta mätare, alltså verkliga skurtoppar.

Uppgiften byggde på `experiments/bakgrund/rapporter/2026-11-07/0001-a2-falska-ekon.md` och `experiments/natt/rapporter/2026-11-06/3-a2.md`, som jag läste först. Domaren (`experiments/analys/domare.py`) ändrades inte. Testdelen lästes aldrig. Allt urval gjordes på de 28 träningsdagarna genom `domare.days("traning")`, och på valideringen kördes bara den frysta A2TK, en gång.

## Vad kontrollen gör

`kontroll()` i `experiments/analys/a2.py` verkar per period (kvart eller timme) och bara på de mätare som A2 får se som indata. I korsvalideringen är det mätarna utanför den bedömda gruppen och bufferten, så de mätare som domaren bedömer mot rörs aldrig.

- I kvadratrotsskala räknas e_n = √g minus en skattning ur grannarna inom `QC_R` km, utan mätaren själv. Skattningen är ett Gaussviktat medel med längden R/2, och mätaren behöver minst `QC_NMIN` = 2 grannar.
- Mot bakgrunden räknas e_b = (√g − √(k · A1)) / √(1 + C · (radaravstånd / 100 km)²), där k är kvoten i stor skala efter `K_SVAG`. Långt från radarn litar kontrollen alltså mindre på radarn.
- Spridningen σ är 1,4826 · MAD av e över periodens mätare där någon sida är våt, men minst `SO` (0,15 per kvart, 0,3 per timme).
- En mätare kastas för perioden om e_n och e_b har samma tecken och båda är över `QC_T` · σ. Det gäller både en mätare som är för torr mot både grannarna och radarn (0 i regn) och en som är för våt mot båda.
- **Terrängen:** med `QC_SKYDD400` kastas en för våt mätare aldrig över 400 m. Utan grannar kastas ingenting.
- En timmätare som kastas tas bort ur kvoten i stor skala (som också kvarten använder) och ur timmens OI. En kastad kvartsmätare tas bort ur kvartens OI och torrmask.

Kontrollen är av som standard (`QC_T` saknas eller är 0). Ett test visar att avstängd kontroll ger samma fält, och en jämförelse mot den committade `a2.py` (HEAD före ändringen) på syntetiska data med tre frön gav `np.array_equal` för A2 och A2T genom `domare.run_system` (kvart och timme). På träningen blev A2T:s mål precis som i uppgift 0001 (kvart 0,06039, timme 0,18724).

## Diagnosen på träningen (28 dagar, alla mätare som i drift, A2TK:s parametrar)

`a2.py kontroll --res kvart --qc 3 50 1` och `--res timme --qc 2.5 50 1`, `/data/analys/a2/kontroll_*.json`. Bakgrunden är A0 utan utfyllnad som i uppgift 3.

| | perioder | kastade | andel | över 400 m | lovart | för torra | för våta | stationer | stationer kastade fler än 3 dagar |
|---|---|---|---|---|---|---|---|---|---|
| kvart | 322 512 | 283 | 0,088 % | 0 av 41 689 | 4 av 26 930 (0,015 %) | 20 | 263 | 54 | 11 |
| timme | 91 629 | 104 | 0,114 % | 0 av 10 340 | 0 av 7 001 | 17 | 87 | 40 | 1 |

- **Inget kastas över 400 m**, inte heller utan skyddet. Skyddet gav exakt samma värden i alla varianter. De få kastningarna på lovartsidan ligger under 400 m.
- **Stationerna som kastas ofta.** Station 2214807 står för 76 av 283 kastade kvartar (13 % av sina 569 kvartar) och 20 av 104 kastade timmar. Den 2024-04-14 visar den i medel 2,0 mm per kvart i 81 kvartar medan radarn visar 0, vilket är ett tydligt fel som kontrollen tar. Stationen rapporterar dessutom bara våta kvartar. Grannarna 2214806 och 2214803 (samma nummerserie) kastas på 6 dagar var. Station 52350 kastas på 11 dagar men bara i 0,8 % av sina kvartar, vilket snarare ser ut som en plats där radarn ofta underskattar än som en trasig mätare.
- **9 av 10 kastade perioder är för våta**, och de flesta ligger i skurar där radarn och grannarna har mindre regn. Det är det som kostar på valideringen (se domen).

## Syntetiska fel

`a2.py varianter_qc --syntet 0.01`: i indata (aldrig i det som domaren bedömer mot) sattes cirka 1 % av mätarperioderna på träningen till ett fel, en tredjedel var: 0 i regn (en period med minst ekotröskeln, 0,125 mm per kvart och 0,5 mm per timme), ×5 i regn eller ett fast värde (0,5 mm per kvart, 2 mm per timme, på slumpade perioder). Andelen är räknad över alla gånger en mätarperiod används som indata i korsvalideringen. Mål med fel är målet mot de riktiga värdena.

| | mål ren | mål med fel | hittade 0 i regn | ×5 | fast värde | riktiga kastade |
|---|---|---|---|---|---|---|
| A2T, kvart | 0,0603947 | 0,0606750 | | | | |
| A2TK, bara kvartens kontroll | 0,0604007 | 0,0606706 | 3,6 % | 13,4 % | 3,3 % | 0,11 % |
| A2TK, kvart med timmens kontroll i kvoten | 0,0604045 | 0,0606160 | 3,4 % | 13,6 % | 3,3 % | 0,11 % |
| A2T, timme | 0,18724 | 0,18899 | | | | |
| A2TK, timme | 0,18711 | 0,18848 | 10,5 % | 19,5 % | 13,8 % | 0,10 % |

Kontrollen hittar bara en liten del av felen. Felen i lätt och måttligt regn ligger inom den naturliga spridningen per kvart (median σ_n cirka 0,26 √mm, och en typisk våt kvart är 0,2 mm). De fel som syns mest, ×5 i kraftigt regn och fasta värden där det är torrt, hittas oftare. Ändå tar kontrollen bort cirka 25 % av det som felen kostar i målet per kvart (från 0,000280 till 0,000212) och cirka 22 % per timme (från 0,00175 till 0,00137). Per kvart kommer nästan allt av det från timmens kontroll i kvoten.

Kontrollen som bara kastar för torra mätare (`QC_BARA_TORRA`, prövad efter valideringen och bara på träningen): T = 3 och R = 50 km kastar 0,009 % av kvartarna och hittar 3,6 % av nollorna i regn per kvart och 6,6 % per timme. Målet på rena data är som A2T:s (0,0603965 per kvart, 0,187226 per timme).

## Varianterna på träningen och urvalsregeln

Urvalsregeln skrevs och committades (37d75d1) innan varianterna lästes:

1. **Tillåten** är en variant som på de rena träningsdata (a) inte höjer falskt vid torr mätare över 400 m eller på lovartsidan mot A2T med mer än 0,0002, (b) har ett mål som är högst 0,5 % över A2T:s och (c) kastar högst 2 % av indata totalt, över 400 m och på lovartsidan.
2. Bland de tillåtna väljs den med **lägst mål med de syntetiska felen**.
3. Kontrollen tas med för upplösningen bara om den valda varianten har lägre mål med fel än A2T med samma fel.
4. Får båda upplösningarna kontroll, är A2TK kombinationen.

Mål = MAE · (1 + 0,5 · |ln kvot|), korsvaliderat som i `trana` (grupper om 100 km, buffert 25 km). Kastade är andelen av indata i korsvalideringen. Skyddet över 400 m ändrade ingenting i någon variant (raderna är identiska), så tabellen visar varje T och R en gång. `/data/analys/a2/varianter_qc_{ren,syntet}_{0,1}.json`.

**Kvart** (A2T: mål 0,0603947, falskt alla 0,0192, över 400 m 0,0131, lovart 0,0158, mål med fel 0,0606750)

| variant | mål ren | falskt över 400 m | lovart | kastade alla | över 400 m | lovart | mål med fel | hittade 0 | ×5 | fast |
|---|---|---|---|---|---|---|---|---|---|---|
| T=2 R=25 | 0,0604012 | 0,0131 | 0,0158 | 0,19 % | 0 | 0 | 0,0606752 | 6,7 % | 12,6 % | 0,6 % |
| T=2 R=50 | 0,0604044 | 0,0131 | 0,0158 | 0,30 % | 0 | 0,05 % | 0,0606750 | 8,2 % | 17,9 % | 4,7 % |
| T=2,5 R=25 | 0,0603987 | 0,0131 | 0,0158 | 0,12 % | 0 | 0 | 0,0606734 | 5,0 % | 11,3 % | 0,2 % |
| T=2,5 R=50 | 0,0604026 | 0,0131 | 0,0158 | 0,18 % | 0 | 0,03 % | 0,0606748 | 5,9 % | 15,6 % | 4,1 % |
| T=3 R=25 | 0,0603989 | 0,0131 | 0,0158 | 0,08 % | 0 | 0 | 0,0606742 | 3,0 % | 10,3 % | 0,1 % |
| **T=3 R=50** | 0,0604007 | 0,0131 | 0,0158 | 0,12 % | 0 | 0,01 % | **0,0606706** | 3,6 % | 13,4 % | 3,3 % |
| T=4 R=25 | 0,0603940 | 0,0131 | 0,0158 | 0,05 % | 0 | 0 | 0,0606737 | 1,6 % | 7,1 % | 0,0 % |
| T=4 R=50 | 0,0604022 | 0,0131 | 0,0158 | 0,07 % | 0 | 0 | 0,0606742 | 1,5 % | 8,7 % | 1,4 % |

**Timme** (A2T: mål 0,18724, falskt alla 0,0091, över 400 m 0,0095, lovart 0,0071, mål med fel 0,18899)

| variant | mål ren | falskt över 400 m | lovart | kastade alla | över 400 m | lovart | mål med fel | hittade 0 | ×5 | fast |
|---|---|---|---|---|---|---|---|---|---|---|
| T=2 R=25 | 0,18707 | 0,0095 | 0,0071 | 0,13 % | 0 | 0 | 0,18864 | 10,0 % | 11,3 % | 0,9 % |
| T=2 R=50 | 0,18720 | 0,0095 | 0,0071 | 0,19 % | 0 | 0,01 % | 0,18854 | 16,8 % | 23,5 % | 17,5 % |
| T=2,5 R=25 | 0,18715 | 0,0095 | 0,0071 | 0,08 % | 0 | 0 | 0,18872 | 6,9 % | 8,3 % | 0,3 % |
| **T=2,5 R=50** | 0,18711 | 0,0095 | 0,0071 | 0,11 % | 0 | 0 | **0,18848** | 10,5 % | 19,5 % | 13,8 % |
| T=3 R=25 | 0,18718 | 0,0095 | 0,0071 | 0,05 % | 0 | 0 | 0,18876 | 4,9 % | 5,9 % | 0,3 % |
| T=3 R=50 | 0,18715 | 0,0095 | 0,0071 | 0,06 % | 0 | 0 | 0,18854 | 6,6 % | 15,5 % | 10,7 % |
| T=4 R=25 | 0,18719 | 0,0095 | 0,0071 | 0,03 % | 0 | 0 | 0,18877 | 0,5 % | 4,1 % | 0,3 % |
| T=4 R=50 | 0,18717 | 0,0095 | 0,0071 | 0,03 % | 0 | 0 | 0,18860 | 2,0 % | 10,0 % | 3,8 % |

Alla varianter var tillåtna. Regeln gav T = 3 och R = 50 km per kvart och T = 2,5 och R = 50 km per timme, båda med lägre mål med fel än A2T, så A2TK är kombinationen. Skyddet över 400 m gav samma värden som utan, och vid lika valde jag skyddet, som är det försiktigare valet i terrängen. Den regeln för lika lades till när likheten syntes, men den ändrar inga siffror. A2TK frystes i `FRYSTA` och committades (54c5b9f) innan valideringen kördes. Skillnaderna i mål på rena data är mycket små (under 0,02 %), så valet bestämdes i praktiken av de syntetiska felen.

## Domarens tabeller på valideringen (16 dagar)

`uv run python experiments/analys/domare.py tabell A2TK --mot A2T` (och `--mot A1`, `--mot A0`). Skillnaden är i godhet (större är bättre), med 95 % från bootstrap över dagarna. Fet text betyder att intervallet ligger helt på en sida. Hela tabellerna ligger i `/data/analys/domare/tabell_A2TK_mot_{A2T,A1,A0}_validering.json`.

### A2TK mot A2T

| delmängd | mått | A2TK | A2T | mot A2T (95 %) |
|---|---|---|---|---|
| kvart, alla | kvot summa | 0,846 | 0,851 | **−0,006 (−0,009 till −0,002)** |
| kvart, alla | kvot > 1 mm | 0,546 | 0,552 | **−0,011 (−0,022 till −0,003)** |
| kvart, alla | MAE (mm) | 0,065 | 0,065 | **+0,000 (+0,000 till +0,000)** |
| kvart, alla | CSI 0,5 | 0,335 | 0,336 | −0,001 (−0,003 till +0,000) |
| kvart, alla | CSI 1 | 0,230 | 0,232 | **−0,001 (−0,003 till −0,000)** |
| kvart, alla | FSS 0,5 | 0,536 | 0,540 | **−0,004 (−0,009 till −0,000)** |
| kvart, alla | FSS 1 | 0,389 | 0,392 | **−0,003 (−0,006 till −0,001)** |
| kvart, alla | falskt vid torr mätare | 0,020 | 0,020 | +0,000 (+0,000 till +0,000) |
| kvart, alla | hopp, kvot mot mätarna | 0,876 | 0,882 | **−0,007 (−0,012 till −0,002)** |
| kvart, över 400 m | kvot summa | 0,574 | 0,575 | **−0,001 (−0,003 till −0,000)** |
| kvart, över 400 m | kvot > 1 mm | 0,439 | 0,442 | **−0,006 (−0,009 till −0,000)** |
| kvart, över 400 m | FSS 1 | 0,355 | 0,357 | −0,001 (−0,002 till +0,000) |
| kvart, över 400 m | falskt vid torr mätare | 0,012 | 0,012 | +0,000 (+0,000 till +0,000) |
| kvart, lovart | kvot summa | 0,704 | 0,705 | **−0,002 (−0,002 till −0,001)** |
| kvart, lovart | kvot > 1 mm | 0,440 | 0,442 | **−0,003 (−0,006 till −0,000)** |
| kvart, lovart | falskt vid torr mätare | 0,014 | 0,014 | +0,000 (+0,000 till +0,000) |
| timme, alla | kvot summa | 0,940 | 0,945 | **−0,005 (−0,009 till −0,002)** |
| timme, alla | kvot > 5 mm | 0,583 | 0,592 | **−0,015 (−0,039 till −0,003)** |
| timme, alla | MAE (mm) | 0,214 | 0,214 | **+0,000 (+0,000 till +0,001)** |
| timme, alla | CSI 1 | 0,469 | 0,470 | −0,001 (−0,002 till +0,000) |
| timme, alla | FSS 1 | 0,683 | 0,685 | **−0,001 (−0,003 till −0,000)** |
| timme, alla | FSS 5 | 0,372 | 0,376 | **−0,004 (−0,009 till −0,000)** |
| timme, alla | falskt vid torr mätare | 0,009 | 0,009 | +0,000 (+0,000 till +0,000) |
| timme, över 400 m | kvot summa | 0,675 | 0,676 | **−0,002 (−0,003 till −0,000)** |
| timme, över 400 m | CSI 5 | 0,300 | 0,281 | +0,019 (+0,000 till +0,064) |
| timme, lovart | kvot summa | 0,820 | 0,821 | **−0,002 (−0,004 till −0,000)** |
| kartmåttet | rutor per dag | 47,06 | 47,19 | +0,125 (−0,000 till +0,312) |

Domarens dom mot A2T: inte bättre. Bättre i MAE per kvart och per timme, och sämre i kvot summa och kvot > 1 mm per kvart och per timme över 400 m och på lovartsidan. Dessutom är flera andra mått sämre med intervallet helt under 0 (tabellen ovan).

### A2TK mot A1 och A0

| delmängd | mått | A2TK | A1 | A0 | mot A1 (95 %) | mot A0 (95 %) |
|---|---|---|---|---|---|---|
| kvart, alla | kvot summa | 0,846 | 0,824 | 0,825 | +0,026 (−0,055 till +0,103) | +0,025 (−0,057 till +0,101) |
| kvart, alla | MAE (mm) | 0,065 | 0,067 | 0,069 | +0,001 (−0,001 till +0,004) | **+0,004 (+0,002 till +0,006)** |
| kvart, alla | CSI 0,5 | 0,335 | 0,303 | | **+0,032 (+0,013 till +0,048)** | **bättre** |
| kvart, alla | CSI 1 | 0,230 | 0,196 | 0,179 | **+0,035 (+0,011 till +0,054)** | **+0,051 (+0,023 till +0,074)** |
| kvart, alla | FSS 1 | 0,389 | 0,333 | 0,327 | **+0,056 (+0,025 till +0,078)** | **+0,062 (+0,030 till +0,083)** |
| kvart, alla | falskt vid torr mätare | 0,020 | 0,025 | 0,026 | **+0,005 (+0,004 till +0,007)** | **+0,006 (+0,004 till +0,008)** |
| kvart, över 400 m | kvot summa | 0,574 | 0,475 | 0,495 | **+0,189 (+0,089 till +0,272)** | +0,148 (−0,029 till +0,280) |
| kvart, över 400 m | FSS 1 | 0,355 | 0,261 | 0,252 | +0,095 (−0,002 till +0,158) | **+0,103 (+0,001 till +0,162)** |
| kvart, över 400 m | falskt vid torr mätare | 0,012 | 0,013 | 0,015 | **+0,002 (+0,000 till +0,003)** | +0,003 (−0,001 till +0,007) |
| kvart, lovart | kvot summa | 0,704 | 0,592 | 0,604 | **+0,173 (+0,056 till +0,251)** | **+0,153 (+0,041 till +0,241)** |
| kvart, lovart | FSS 1 | 0,378 | 0,277 | 0,264 | **+0,101 (+0,003 till +0,165)** | **+0,114 (+0,023 till +0,167)** |
| kvart, lovart | falskt vid torr mätare | 0,014 | 0,016 | 0,016 | **+0,001 (+0,000 till +0,002)** | **+0,002 (+0,001 till +0,004)** |
| timme, alla | kvot summa | 0,940 | 0,889 | 0,890 | +0,055 (−0,022 till +0,135) | +0,054 (−0,022 till +0,134) |
| timme, alla | MAE (mm) | 0,214 | 0,228 | 0,233 | **+0,015 (+0,006 till +0,024)** | **+0,020 (+0,012 till +0,029)** |
| timme, alla | CSI 1 | 0,469 | 0,429 | 0,423 | **+0,040 (+0,018 till +0,063)** | **+0,047 (+0,023 till +0,069)** |
| timme, alla | FSS 1 | 0,683 | 0,635 | 0,634 | **+0,048 (+0,025 till +0,071)** | **+0,049 (+0,026 till +0,072)** |
| timme, alla | falskt vid torr mätare | 0,009 | 0,010 | 0,010 | +0,001 (−0,000 till +0,002) | **+0,002 (+0,000 till +0,003)** |
| timme, över 400 m | kvot summa | 0,675 | 0,505 | 0,524 | **+0,289 (+0,197 till +0,354)** | **+0,253 (+0,080 till +0,368)** |
| timme, över 400 m | CSI 1 | 0,370 | 0,259 | 0,248 | **+0,111 (+0,031 till +0,175)** | **+0,122 (+0,046 till +0,182)** |
| timme, över 400 m | falskt vid torr mätare | 0,008 | 0,007 | 0,009 | −0,000 (−0,003 till +0,002) | +0,001 (−0,002 till +0,006) |
| timme, lovart | kvot summa | 0,820 | 0,653 | 0,671 | **+0,228 (+0,087 till +0,325)** | **+0,200 (+0,051 till +0,308)** |
| timme, lovart | FSS 1 | 0,715 | 0,624 | 0,622 | **+0,090 (+0,009 till +0,150)** | **+0,093 (+0,011 till +0,150)** |
| timme, lovart | falskt vid torr mätare | 0,011 | 0,010 | 0,011 | −0,001 (−0,003 till +0,001) | +0,000 (−0,002 till +0,002) |
| kartmåttet | rutor per dag | 47,06 | 40,44 | 36,56 | −6,6 (−19,6 till +3,4) | −10,5 (−24,6 till +0,3) |

Domarens dom: **bättre mot A1** (14 mått, inget sämre) och **bättre mot A0** (17 mått, inget sämre), som för A2T.

## Domen

- **A2TK mot A1 och A0: bättre**, med samma mönster som A2T.
- **A2TK mot A2T: inte minst lika bra, så den ersätter inte A2T.** Regeln i uppgiften kräver att inget mått är sämre med intervallet helt på fel sida. A2TK är sämre i summakvoten (alla, över 400 m och lovart, kvart och timme), kvoten över 1 mm, FSS 0,5 och 1 och CSI 1 per kvart, FSS 1 och 5 per timme och hoppkvoten. Skillnaderna är små (0,001 till 0,006 i kvot och FSS), men bootstrapintervallen ligger helt under 0. Bara MAE är bättre.
- **Varför:** 9 av 10 kastade perioder på träningen är för våta mätare, alltså mätare med mer regn än både grannarna och radarn. På valideringen är det i huvudsak verkliga skurtoppar som radarn och de glesa grannarna underskattar. När de kastas förlorar A2 regn i de våtaste perioderna, så kvoten och FSS sjunker medan MAE blir lite bättre. Det är samma mekanism som domarens summakvot belönar (frågan om summakvoten står redan under Frågor till användaren). Skyddet över 400 m gjorde ingenting, eftersom inga för våta mätare kastades över 400 m. Förlusten i terrängen kommer i stället från mätare under 400 m som påverkar terrängen genom OI och kvoten.
- **Vad kontrollen ändå visar:** den hittar en verkligt trasig station (2214807, 2 mm per kvart utan radareko i 81 kvartar en dag) och tar bort 22 till 25 % av det som 1 % syntetiska fel kostar i målet, men den hittar bara 3 till 20 % av felen. De flesta fel som är rimliga i storlek kan inte skiljas från naturlig variation per kvart med grannar 25 till 50 km bort.

**Rekommendation:** A2T står kvar som utgångspunkt. A2TK tas inte vidare som den är. En kontroll som skyddar mot trasiga mätare utan att kasta skurtoppar bör vara mycket smalare: kasta en för våt mätare bara där radarn är helt torr (A1 = 0 i rutan och omgivningen) och grannarna är torra, och en för torr mätare där grannarna och radarn är tydligt våta. Lägg dessutom till en kontroll per station och dygn (som station 2214807), där en mätare som är för våt mot torr radar i många perioder kastas för hela dygnet. Varianten som bara kastar för torra mätare (`QC_BARA_TORRA`) är neutral på träningen men hittar få fel. Valideringen är nu sedd tre gånger för A2-familjen, så nästa variant bör väljas helt på träningen och bedömas en gång.

## Körtiderna

| steg | tid |
|---|---|
| varianterna, 17 per upplösning, rena data, två processer | cirka 22 min (timme 35 till 65 s, kvart 90 till 115 s per variant) |
| samma med syntetiska fel | cirka 22 min |
| kombinationen och varianten med bara för torra, ren och med fel | cirka 12 min |
| diagnosen med alla mätare, kvart och timme | cirka 2 min |
| A2TK genom domaren, 16 valideringsdagar, två processer | cirka 25 min (25 s läsning och 140 s för A2TK och domaren per dag) |

Kontrollen kostar lite: en valideringsdag tog 141 s för A2TK och domaren, mot 170 till 260 s för A2T i uppgift 0001, som då körde parallellt med en annan körning. Ny data: `/data/analys/domare/A2TK/` (cirka 80 kB), `varianter_qc_*.json` och `kontroll_*.json` (under 100 kB). `df /data` visade 4,9 GB ledigt efteråt.

## Ändrade filer

- `experiments/analys/a2.py`: `kontroll()` och `QC_STD`, kontrollen i punktversionen (`_predict_day`, `_kontroll_timme`) och fältversionen (`A2._kontroll`, `A2.falt`, med `kastade`), `mm_in` och `station` i `Punktdag`, de syntetiska felen (`syntetiska_fel`), kommandona `kontroll` och `varianter_qc` (`--qc`, `--ph`, `--syntet`, `--bara`), `QC_BARA_TORRA`, A2TK i `FRYSTA` och ändringar för timmen i `system_params` (nyckeln `timme`).
- `tests/test_analys_a2.py`: 3 nya tester (avstängd kontroll ger samma fält och A2, A2S och A2T har ingen kontroll; kontrollen kastar 0 i regn och en ensam topp men inte en mätare som radarn stöder, inte en topp över 400 m med skyddet och inte utan grannar; i fältet tas en mätare som visar 0 i regn bort per kvart och per timme). `uv run pytest` gav 175 godkända.
- Inget i `src/`, `deploy/`, `models/`, `.github/`, domaren, `experiments/sverige/dagar.json` eller `experiments/natt/` ändrades.

## Nästa steg

1. **En smalare kontroll** (se rekommendationen): för våt bara mot helt torr radar och torra grannar, och en kontroll per station och dygn. Väljs på träningen med de syntetiska felen och med kravet att summakvoten och FSS inte sjunker mot A2T på träningen.
2. **Kartmåttet per timme** (47,1 rutor per dag mot A0:s 36,6) är fortfarande det sämsta för A2T och A2TK.
3. **Mängden i terrängen tillbaka** (taket tar bort riktigt svagt regn i fjällen).
4. **A2T till `src/knep/analys/` som avstängt val**, med kontrollen som ett eget avstängt val när en variant håller mot A2T. Ett släpp eller att visa A2 på sidan beslutar användaren.

Status: klar
