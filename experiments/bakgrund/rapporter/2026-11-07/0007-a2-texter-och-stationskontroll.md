# Uppgift 0007: sidans texter för A2 och kontrollen av mätarna per station och dygn (A2TS)

Kort: Sidans två texter för A2 och `INTRO` 5 är klara och syns bara när `levels.a2` har bilder (del 1, committad); kontrollen per station och dygn (A2TS: R 100 km, minst 8 kvartar eller 3 timmar våt mot torr radar och torra grannar, eller noll mot vått, aldrig "våt" över 400 m) hittar 65 % av de skadliga syntetiska dygnsfelen och kastar 9 av 4 527 riktiga stationsdygn på träningen och 6 av 2 515 på valideringen, men den godkänns inte mot A2T eftersom FSS 1 per kvart blir sämre med intervallet helt på fel sida (0,392 mot 0,392, −0,00013, −0,00021 till −0,00003), så valet lades inte i `src/`.

Uppgiften byggde på `MAL.md` (Användarens beslut 2026-11-07) och rapporterna 0002, 0004 och 0005 från 2026-11-07, som jag läste först. Domaren ändrades inte, och testdelen lästes aldrig. Allt urval gjordes på de 28 träningsdagarna (`domare.days("traning")`), och valideringen kördes bara för den frysta A2TS, en gång.

## Del 1: sidans texter för A2 (commit 8f560ba)

Ändringarna i `web/index.html`:

- **Förklaringen (`#intro`, avsnittet Analys)** har två versioner av meningen om A2. Utan A2 står den gamla texten kvar ("... 1 till 2,5 timmar efter timmen; den byggs fortfarande."). Med A2 står i stället: "**A2** rättas mot regnmätarna (A2T): A1:s mängd rättas både i stort och nära varje mätare, och svagt eko tas bort där mätarna är torra. Den blir klar först när mätarna har kommit, 1 till 2,5 timmar efter timmen, räknas om när fler mätare kommer in och finns bara som summa per kvart och timme, inte var femte minut."
- **5-minutersläget i fliken Analys:** kartan A2 säger "bara kvart och timme, välj 15 min eller 1 h" i stället för "inte klar än, mätarna kommer 1 till 2,5 h efter timmen". Vid 15 min och 1 h är texterna som förut.
- **Villkoret** är `hasA2(m)`: `levels.a2` finns och har minst en bild i `frames`, `frames15` eller `frames60`. Manifestet utan `--a2` har `levels.a2 = null`, och då är allt som förut. Förklaringens text byts i `introA2()`, som körs varje gång ett nytt manifest läses.
- **`INTRO` är 5.** För att sidan ska se ut som i dag utan A2 gäller 5 bara när A2 finns: utan A2 visas förklaringen automatiskt bara för den som har sett en version under 4 (som i dag), och när den stängs sparas 4. När ett manifest med A2 kommer och man har sett version 4 eller lägre öppnas förklaringen en gång till med den nya texten, och då sparas 5. De gamla villkoren för `#handelser` och `#verifiering` gäller fortfarande.

**Hur det prövades.** Jag körde två historiska cykler på träningsdagen 2020-07-24 (07 och 08 UTC) med och utan `--a2` (`experiments/analys/a2_cykel_prov.py --dag 2020-07-24 --fran 7 --till 8 --utan --ut /data/analys/sida_prov`, cirka 165 kB bilder). Manifestet utan valet har `levels.a2 = null` och manifestet med valet har `levels.a2` med `frames` tom, 8 kvartar i `frames15` och 2 timmar i `frames60`, alltså de två fall som `hasA2` skiljer på (null ger falskt, tom `frames` men bilder i `frames15` ger sant). Någon webbläsare eller JavaScript-motor fanns inte på Pi:n, och sessionen fick inte installera någon eller köra `/tmp`-sökvägar, så sidan kunde inte öppnas och ritas här. Jag kontrollerade i stället kodvägarna för hand (att `hasA2` och `live` finns innan de används, att `introA2` bara körs när ett nytt manifest har lästs, att den gamla texten är synlig från början så att sidan ser ut som i dag innan manifestet kommer), och att HTML:en går att tolka och att klamrarna i skriptet balanserar som före ändringen. **Kvar att göra innan `--a2` slås på:** öppna sidan lokalt med `python3 -m http.server -d web 8000` och `web/data` länkad till `/data/analys/sida_prov/med/out` (och `utan/out`) och se på fliken Analys i 5 min, 15 min och 1 h och på förklaringen.

## Del 2: kontrollen per station och dygn (A2TS)

### Regeln

`stationsdygn()` i `experiments/analys/a2.py` (och samma regel i `src/knep/analys/a2.py`). För varje dygn och upplösning (kvart och timme) räknas för varje station, bland de mätare systemet ser:

- **Våt mot torrt:** perioder där stationen visar minst 0,2 mm per kvart (0,5 mm per timme), radarn i stationens ruta högst 0,01 mm (0,02 mm) och alla grannar inom R km 0 mm, med minst 2 grannar.
- **Noll mot vått:** perioder där stationen visar 0 mm, radarn minst A_VAT och grannarnas median minst N_VAT.

Stationen kastas för hela dygnet, både kvart och timme, om den har minst N perioder av något av felen i någon upplösning. I korsvalideringen räknas kontrollen per grupp bara bland de mätare gruppen får se, så de mätare som domaren bedömer mot påverkar den aldrig.

**A2TS (fryst):** R = 100 km, N = 8 kvartar eller 3 timmar, A_VAT = 0,25 mm per kvart (1 mm per timme), N_VAT = 0,2 mm (0,5 mm), och "våt mot torrt" räknas aldrig över 400 m (skyddet). Resten som A2T.

### Hur trösklarna valdes (bara träningen)

Urvalsregeln skrevs och committades (f73ef00) innan resultaten på hela träningen lästes:

1. Diagnosen (`a2.py stationer`, alla mätare som i drift) för 24 varianter: N = 8/3, 12/4 eller 24/6, R = 75 eller 100 km, med och utan skydd över 400 m, och "noll mot vått" vid starkt regn (A_VAT 0,5 mm per kvart, N_VAT 0,3) eller svagare (`noll-los`, 0,25 och 0,2).
2. Tillåten: högst 0,3 % kastade riktiga stationsdygn, och i korsvalideringen på rena träningspunkter (`a2.py varianter_qcs`) summakvot per kvart och timme högst 0,0005 under A2T:s och mål högst 0,05 % över.
3. Bland de tillåtna den som hittar flest skadliga syntetiska fel.
4. Domaren på de tre träningsdagar som har A1 sparat; FSS 0,5 och 1 får inte sjunka mer än 0,001 mot A2T.

R = 50 km, som A2TK använde, gick inte: mätarna har i median bara 1 granne inom 50 km per kvart (8 till 13 % har minst 2), mot 3 inom 75 km och 5 inom 100 km (`experiments/analys/qcs_diag.py`). Provkörningen på tre dagar med 50 km hittade bara 18 % av felen. Därför prövades 75 och 100 km.

**Syntetiska fel som varar ett dygn** (`syntetiska_dygn`): 3 % av stationerna varje träningsdag, en tredjedel var: **fast** (fastnar på 0,5 mm per kvart och 2 mm per timme hela dygnet), **noll** (0 hela dygnet) och **för våt** (×3 i regn och 1,2 mm per timme, 0,3 mm per kvart, i 30 % av de torra perioderna). Felen läggs bara i indata; domaren och målet räknas mot de riktiga värdena. **Skadliga** är de där Σ|fel| över dygnets kvartar är minst 2 mm (en station som visar noll en torr dag gör ingen skada).

Diagnosen på 28 träningsdagar, 4 527 stationsdygn (`/data/analys/a2/stationer.json`):

| variant | kastade riktiga | andel | hittade skadliga | fast | noll | för våt |
|---|---|---|---|---|---|---|
| N=8/3 R=75 | 9 | 0,199 % | 55,2 % | 37/48 | 2/26 | 14/22 |
| N=8/3 R=75 noll-los | 13 | 0,287 % | 60,4 % | 37/48 | 7/26 | 14/22 |
| N=8/3 R=75 skydd400 | 7 | 0,155 % | 52,1 % | 35/48 | 2/26 | 13/22 |
| N=8/3 R=75 skydd400 noll-los | 11 | 0,243 % | 57,3 % | 35/48 | 7/26 | 13/22 |
| N=8/3 R=100 | 9 | 0,199 % | 62,5 % | 40/48 | 3/26 | 17/22 |
| N=8/3 R=100 noll-los | 12 | 0,265 % | 68,8 % | 40/48 | 9/26 | 17/22 |
| N=8/3 R=100 skydd400 | 6 | 0,133 % | 58,3 % | 38/48 | 3/26 | 15/22 |
| **N=8/3 R=100 skydd400 noll-los** | **9** | **0,199 %** | **64,6 %** | **38/48** | **9/26** | **15/22** |
| N=12/4 R=75 | 4 | 0,088 % | 50,0 % | 36/48 | 1/26 | 11/22 |
| N=12/4 R=75 noll-los | 5 | 0,110 % | 53,1 % | 36/48 | 4/26 | 11/22 |
| N=12/4 R=75 skydd400 | 4 | 0,088 % | 46,9 % | 34/48 | 1/26 | 10/22 |
| N=12/4 R=75 skydd400 noll-los | 5 | 0,110 % | 50,0 % | 34/48 | 4/26 | 10/22 |
| N=12/4 R=100 | 4 | 0,088 % | 55,2 % | 39/48 | 0/26 | 14/22 |
| N=12/4 R=100 noll-los | 5 | 0,110 % | 61,5 % | 39/48 | 6/26 | 14/22 |
| N=12/4 R=100 skydd400 | 3 | 0,066 % | 51,0 % | 37/48 | 0/26 | 12/22 |
| N=12/4 R=100 skydd400 noll-los | 4 | 0,088 % | 57,3 % | 37/48 | 6/26 | 12/22 |
| N=24/6 (alla åtta) | 1 | 0,022 % | 37,5 till 42,7 % | 31 till 35/48 | 0 till 3/26 | 5/22 |

Med de syntetiska felen kastade den valda varianten också 7 av 4 392 riktiga stationsdygn (0,16 %), och bland alla syntetiska (också de ofarliga) 44 av 56 fasta, 10 av 51 nollor och 18 av 28 för våta.

Korsvalideringen på rena träningspunkter, skillnad mot A2T (A2T: mål 0,0603947 per kvart och 0,187243 per timme, kvot 0,84770 och 0,94208), i detektionsordning:

| variant | upplösning | mål | kvot | MAE | CSI 1 | falskt alla / över 400 m / lovart | tillåten |
|---|---|---|---|---|---|---|---|
| N=8/3 R=100 noll-los | kvart | +0,031 % | −0,00050 | +0,000002 | −0,0001 | +0,0001 / +0,0004 / +0,0001 | nej (timmens kvot) |
| | timme | +0,040 % | **−0,00086** | −0,000009 | −0,0004 | +0,0000 / +0,0001 / +0,0000 | |
| **N=8/3 R=100 skydd400 noll-los** | kvart | +0,009 % | +0,00031 | +0,000014 | −0,0002 | +0,0001 / +0,0004 / +0,0001 | **ja** |
| | timme | −0,001 % | +0,00004 | +0,000001 | −0,0000 | +0,0000 / +0,0003 / +0,0000 | |
| N=8/3 R=100 | kvart | +0,011 % | **−0,00137** | −0,000036 | +0,0002 | −0,0000 / +0,0000 / +0,0000 | nej |
| | timme | +0,008 % | **−0,00171** | −0,000145 | −0,0005 | −0,0000 / −0,0001 / +0,0000 | |
| N=12/4 R=100 noll-los | kvart | +0,017 % | −0,00016 | +0,000004 | −0,0000 | +0,0001 / +0,0004 / +0,0001 | ja |
| | timme | +0,007 % | −0,00043 | −0,000028 | −0,0003 | +0,0000 / +0,0001 / +0,0000 | |
| N=8/3 R=75 noll-los | kvart | +0,018 % | +0,00042 | +0,000023 | −0,0006 | +0,0001 / +0,0004 / +0,0001 | ja |
| | timme | +0,040 % | −0,00006 | +0,000067 | −0,0001 | +0,0000 / +0,0003 / +0,0000 | |

(`/data/analys/a2/varianter_qcs_ren_*.json`; A2T:s rad är den från uppgift 0002, `varianter_qc_ren_*.json`, med samma funktion och samma data.) Varianterna med lägre träff än 60 % kördes inte i korsvalideringen, eftersom regeln väljer den med högst träff bland de tillåtna och den valda redan låg över dem. De som kastar för våta stationer över 400 m sänker summakvoten per timme, eftersom de stationerna (se nedan) är verkligt regn som radarn missar i terrängen; skyddet tar bort det.

**Domaren på tre träningsdagar** (2020-07-24, 2020-10-07, 2023-11-22, `a2.py kor_traning`, `/data/analys/domare/A2TSv7/` mot `A2T/`): FSS 0,5, 1 och 5 per kvart och per timme, alla delmängder, lika med A2T:s eller upp till +0,001 (timme, alla: FSS 1 0,614 mot 0,612). Kvot summa per timme, alla: 0,950 mot 0,954 (−0,004, −0,016 till +0,004). Steg 4 godkänt, och A2TS frystes (fb6ecde) innan valideringen kördes. (En avbruten körning av den fällda varianten ligger i `/data/analys/domare/A2TSv5/`, ett dygn, och används inte.)

### De stationsdygn A2TS kastar på träningen

9 av 4 527 (0,20 %), inga över 400 m:

| dag | station | kvartar | mätaren (mm) | radarn (mm) | våt mot torrt (kvart/timme) | noll mot vått (kvart/timme) |
|---|---|---|---|---|---|---|
| 2020-12-27 | 82360 | 96 | 13,4 | 25,1 | 0 / 0 | 15 / 0 |
| 2022-12-20 | 2222811 | 9 | 2,0 | 0,0 | 9 / 1 | 0 / 0 |
| 2022-12-20 | 22088020 | 40 | 10,6 | 0,3 | 9 / 0 | 0 / 0 |
| 2023-07-12 | 104580 | 96 | 3,8 | 23,7 | 0 / 0 | 8 / 3 |
| 2023-11-22 | 2222818 | 21 | 6,6 | 0,0 | 17 / 3 | 0 / 0 |
| 2024-04-14 | 2214807 | 81 | 162,7 | 0,0 | 39 / 3 | 0 / 0 |
| 2024-11-25 | 2222818 | 79 | 29,6 | 1,2 | 19 / 1 | 0 / 0 |
| 2024-12-19 | 159880 | 96 | 4,5 | 14,8 | 0 / 0 | 10 / 2 |
| 2024-12-19 | 22128142 | 12 | 2,4 | 0,5 | 9 / 0 | 0 / 0 |

- **2214807 den 2024-04-14** (162,7 mm mot radarns 0) är exemplet ur uppgiften och tas.
- Fem av de nio är stationer i nummerserierna 222… och 220…/221… (2222811, 2222818 två gånger, 22088020, 22128142), som 2214807. De rapporterar bara några av kvartarna och visar regn där radarn och grannarna inom 100 km är helt torra, i 9 till 19 kvartar. Det ser ut som samma slags fel.
- Tre är "noll mot vått" (82360 i december, 104580 i juli, 159880 i december): stationen visar 0 i 8 till 15 kvartar där radarn och grannarna har regn, och dygnssumman är en femtedel till hälften av radarns. I december kan det vara snö som mätaren inte fångar; i juli är det troligen ett stopp. I båda fallen är mätaren fel för A2.
- Varianterna utan skydd kastade dessutom 144310 (2020-07-24, 11,7 mm mot radarns 1,2), 133500 (2023-07-12, 22,5 mot 0,5) och 167710 (2025-10-24), alla över 400 m. Det är sannolikt verklig nederbörd i terrängen som radarn missar, och just det som inte får kastas.

### De stationsdygn A2TS kastar på valideringen

Efter domarens körning, bara som redovisning (`experiments/analys/qcs_validering.py`, alla mätare som i drift, `/data/analys/a2/stationer_validering.json`): 6 av 2 515 stationsdygn (0,24 %).

| dag | station | kvartar | mätaren (mm) | radarn (mm) | våt mot torrt (kvart/timme) | noll mot vått (kvart/timme) | över 400 m |
|---|---|---|---|---|---|---|---|
| 2019-03-17 | 81050 | 62 | 0,4 | 8,4 | 0 / 0 | 10 / 0 | nej |
| 2021-10-20 | 177930 | 96 | 1,4 | 16,4 | 0 / 0 | 5 / 3 | ja |
| 2023-11-04 | 22088018 | 38 | 7,6 | 5,4 | 17 / 1 | 0 / 0 | nej |
| 2024-06-28 | 22128050 | 14 | 2,8 | 0,4 | 8 / 0 | 0 / 0 | nej |
| 2024-07-13 | 52350 | 96 | 22,0 | 28,7 | 0 / 0 | 9 / 0 | nej |
| 2024-07-13 | 62260 | 95 | 23,0 | 29,2 | 0 / 0 | 8 / 1 | nej |

Fyra ser ut som fel (81050 och 177930 visar en tjugondel och en tiondel av radarns regn, och två stationer i 22-serien visar regn utan eko). 52350 och 62260 den 2024-07-13 har däremot nästan radarns dygnssumma och kastas för 8 och 9 nollor i kvartar med skurar; det är sannolikt verkliga mätare i ett skurfält där regnet missar dem ett par kvartar. Det är priset för den lösa varianten av "noll mot vått", och troligen också förklaringen till förlusten i FSS per kvart (de två dagar med störst förlust i FSS 1 per kvart är 2021-10-20 och 2024-07-13).

I korsvalideringen kastas ibland andra stationer än med alla mätare (färre grannar i varje grupp), så också 2020-12-15 och 2023-08-08 skiljer sig något från A2T. De sju dagar där ingen station kastas i någon grupp ger exakt A2T:s sparade rader (jämfört som JSON), så A2T:s rader under `/data/analys/domare/A2T/` är jämförbara och behövde inte köras om.

## Domarens tabeller på valideringen (16 dagar)

`uv run python experiments/analys/domare.py tabell A2TS --mot A2T` (och `--mot A1`, `--mot A0`). Skillnaden är i godhet (större är bättre) med 95 % från bootstrap över dagarna; fet text betyder att intervallet ligger helt på ena sidan. Hela tabellerna i `/data/analys/domare/tabell_A2TS_mot_{A2T,A1,A0}_validering.json`. A2TS kördes en gång, i två processer, cirka 30 min (35 till 108 s läsning och 197 till 294 s A2 och domaren per dag).

### A2TS mot A2T

Alla mått är lika med A2T:s på tre decimaler. Intervallet ligger helt på ena sidan bara i två mått, och båda är räknade med fyra eller fler decimaler här:

| delmängd | mått | A2TS | A2T | mot A2T (95 %) |
|---|---|---|---|---|
| kvart, alla | kvot summa | 0,8515 | 0,8509 | +0,0007 (−0,0000 till +0,0015) |
| kvart, alla | kvot > 1 mm | 0,552 | 0,552 | +0,0001 (−0,0001 till +0,0007) |
| kvart, alla | MAE (mm) | 0,065 | 0,065 | −0,0000 (−0,0000 till +0,0000) |
| kvart, alla | CSI 1 | 0,232 | 0,232 | −0,0000 (−0,0000 till +0,0000) |
| kvart, alla | FSS 0,5 | 0,540 | 0,540 | +0,0000 (−0,0000 till +0,0010) |
| kvart, alla | **FSS 1** | 0,392 | 0,392 | **−0,00013 (−0,00021 till −0,00003)** |
| kvart, alla | falskt vid torr mätare | 0,020 | 0,020 | +0,000 (−0,000 till +0,000) |
| kvart, alla | hopp, kvot mot mätarna | 0,882 | 0,882 | +0,000 (−0,000 till +0,001) |
| kvart, över 400 m | kvot summa | 0,576 | 0,575 | +0,001 (−0,001 till +0,002) |
| kvart, över 400 m | FSS 1 | 0,357 | 0,357 | +0,000 (+0,000 till +0,000) |
| kvart, över 400 m | falskt vid torr mätare | 0,012 | 0,012 | +0,000 (+0,000 till +0,000) |
| kvart, lovart | kvot summa | 0,705 | 0,705 | −0,000 (−0,000 till +0,000) |
| kvart, lovart | kvot > 10 mm | 0,274 | 0,274 | +0,000 (+0,000 till +0,000), en dag |
| timme, alla | kvot summa | 0,945 | 0,945 | +0,000 (−0,001 till +0,001) |
| timme, alla | MAE (mm) | 0,214 | 0,214 | −0,000 (−0,000 till +0,000) |
| timme, alla | CSI 1 | 0,470 | 0,470 | +0,000 (−0,000 till +0,001) |
| timme, alla | FSS 1 | 0,685 | 0,685 | +0,000 (−0,000 till +0,000) |
| timme, alla | falskt vid torr mätare | 0,009 | 0,009 | +0,000 (+0,000 till +0,000) |
| timme, över 400 m | kvot summa | 0,676 | 0,676 | +0,001 (−0,001 till +0,004) |
| timme, över 400 m | CSI 0,5 | 0,395 | 0,396 | −0,001 (−0,002 till +0,000) |
| timme, lovart | kvot summa | 0,821 | 0,821 | −0,000 (−0,000 till +0,000) |
| kartmåttet | rutor per dag | 47,25 | 47,19 | −0,06 (−0,19 till +0,00) |

Domarens dom mot A2T: inte bättre, och inga mått i dess lista över sämre (`"samre_i": []`). **Uppgiftens krav** är strängare: A2TS får inte bli sämre än A2T med intervallet helt på fel sida i något mått. FSS 1 per kvart är det, med −0,00013 (−0,00021 till −0,00003). Skillnaden är mycket liten (0,03 % av måttet), och intervallet är smalt mest för att 7 av 16 dagar är exakt lika, men regeln är skriven före och följs: **A2TS är inte godkänd.** Måttet på lovartsidan (kvot > 10 mm) ligger helt på den bättre sidan men är en enda dag och noll i skillnad.

### A2TS mot A1 och A0

| delmängd | mått | A2TS | A1 | A0 | mot A1 (95 %) | mot A0 (95 %) |
|---|---|---|---|---|---|---|
| kvart, alla | kvot summa | 0,851 | 0,824 | 0,825 | +0,032 (−0,051 till +0,111) | +0,031 (−0,053 till +0,109) |
| kvart, alla | MAE (mm) | 0,065 | 0,067 | 0,069 | +0,001 (−0,001 till +0,004) | **+0,004 (+0,002 till +0,006)** |
| kvart, alla | CSI 1 | 0,232 | 0,196 | 0,179 | **+0,036 (+0,013 till +0,055)** | **+0,053 (+0,024 till +0,075)** |
| kvart, alla | FSS 1 | 0,392 | 0,333 | 0,327 | **+0,059 (+0,028 till +0,080)** | **+0,065 (+0,034 till +0,085)** |
| kvart, alla | falskt vid torr mätare | 0,020 | 0,025 | 0,026 | **+0,005 (+0,004 till +0,007)** | **+0,006 (+0,004 till +0,008)** |
| kvart, över 400 m | kvot summa | 0,576 | 0,475 | 0,495 | **+0,191 (+0,090 till +0,275)** | +0,150 (−0,029 till +0,283) |
| kvart, över 400 m | FSS 1 | 0,357 | 0,261 | 0,252 | +0,096 (−0,002 till +0,160) | **+0,104 (+0,001 till +0,164)** |
| kvart, över 400 m | falskt vid torr mätare | 0,012 | 0,013 | 0,015 | **+0,002 (+0,000 till +0,003)** | +0,003 (−0,001 till +0,007) |
| kvart, lovart | kvot summa | 0,705 | 0,592 | 0,604 | **+0,174 (+0,057 till +0,253)** | **+0,155 (+0,042 till +0,243)** |
| kvart, lovart | FSS 1 | 0,379 | 0,277 | 0,264 | **+0,102 (+0,003 till +0,167)** | **+0,115 (+0,023 till +0,169)** |
| timme, alla | kvot summa | 0,945 | 0,889 | 0,890 | +0,061 (−0,018 till +0,142) | +0,060 (−0,018 till +0,142) |
| timme, alla | MAE (mm) | 0,214 | 0,228 | 0,233 | **+0,014 (+0,005 till +0,024)** | **+0,019 (+0,011 till +0,029)** |
| timme, alla | CSI 1 | 0,470 | 0,429 | 0,423 | **+0,041 (+0,018 till +0,064)** | **+0,047 (+0,024 till +0,071)** |
| timme, alla | FSS 1 | 0,685 | 0,635 | 0,634 | **+0,050 (+0,025 till +0,074)** | **+0,050 (+0,026 till +0,074)** |
| timme, alla | falskt vid torr mätare | 0,009 | 0,010 | 0,010 | +0,001 (−0,000 till +0,002) | **+0,002 (+0,000 till +0,003)** |
| timme, över 400 m | kvot summa | 0,676 | 0,505 | 0,524 | **+0,292 (+0,200 till +0,357)** | **+0,256 (+0,083 till +0,371)** |
| timme, över 400 m | CSI 1 | 0,370 | 0,259 | 0,248 | **+0,111 (+0,031 till +0,175)** | **+0,122 (+0,046 till +0,182)** |
| timme, över 400 m | falskt vid torr mätare | 0,008 | 0,007 | 0,009 | −0,000 (−0,003 till +0,002) | +0,001 (−0,002 till +0,006) |
| timme, lovart | kvot summa | 0,821 | 0,653 | 0,671 | **+0,230 (+0,088 till +0,327)** | **+0,202 (+0,052 till +0,310)** |
| timme, lovart | FSS 1 | 0,715 | 0,624 | 0,622 | **+0,091 (+0,009 till +0,150)** | **+0,093 (+0,011 till +0,150)** |
| timme, lovart | falskt vid torr mätare | 0,011 | 0,010 | 0,011 | −0,001 (−0,003 till +0,001) | +0,000 (−0,002 till +0,002) |
| kartmåttet | rutor per dag | 47,25 | 40,44 | 36,56 | −6,8 (−19,8 till +3,3) | −10,7 (−24,9 till +0,1) |

Domarens dom: **bättre mot A1** (13 mått, inget sämre) och **bättre mot A0** (15 mått, inget sämre), med samma mönster som A2T.

## Valet i src

**Inte gjort.** Uppgiften sade att valet läggs i `src/knep/analys/a2.py` bara om A2TS godkänns, och det gjorde den inte. Jag hade skrivit funktionen och en konstant i `src/` medan valideringen gick, men tog bort dem igen före commit; `src/` är oförändrat på grenen, och driften påverkas inte. Kontrollen finns kvar i experimentet (`experiments/analys/a2.py`, `FRYSTA["A2TS"]`) med tester (`tests/test_stationskontroll.py`), så att den kan prövas igen.

## Ändrade filer

- `web/index.html`: texterna för A2, `hasA2`, `introA2`, `INTRO` 5 (del 1).
- `experiments/analys/a2.py`: `QCS_STD`, `qcs_params`, `stationsfel`, `stationsdygn` (kontrollen), kontrollen i punktversionen (`_stationsdygn_punkter`, `_predict_day`) och fältversionen (`A2.falt`, `kastade_dygn`), `system_params` med nyckeln `QCS`, `syntetiska_dygn`, `VARIANTER_QCS`, kommandona `stationer`, `varianter_qcs` och `kor_traning` (`--variant`), och A2TS i `FRYSTA`.
- `experiments/analys/qcs_diag.py` (ny): grannarna per radie och de syntetiska felen.
- `experiments/analys/qcs_validering.py` (ny): de kastade stationsdygnen på valideringen (redovisning).
- `tests/test_stationskontroll.py` (ny, 4 tester: av som standard och inte i A2T; våt mot torrt, för få perioder, en verklig skur och noll mot vått; skyddet över 400 m; i fältet tas stationen bort för dygnet). `uv run pytest`: 199 passerade.
- Inget i `src/`, `deploy/`, `models/`, `.github/`, domaren, `dagar.json` eller `experiments/natt/`.

Ny data: `/data/analys/a2/stationer.json`, `stationer_validering.json` och `varianter_qcs_*.json` (under 1 MB), `/data/analys/domare/A2TS/`, `A2TSv5/` (ett dygn ur en avbruten körning), `A2TSv7/`, A2T:s tre träningsdagar och tabellerna (cirka 200 kB), `/data/analys/sida_prov/` (33 MB, cykelns cache och bilderna för prövningen av sidan; kan tas bort när sidan är prövad i en webbläsare). `df /data` visade 4,3 GB ledigt efteråt.

## Nästa steg

1. **Del 1 är klar för `--a2`.** Texterna syns först när driften har `--a2`. Innan Claude slår på det i `deploy/` (användarens beslut 1) bör sidan öppnas en gång i en webbläsare mot `/data/analys/sida_prov/med/out` och `utan/out` (se ovan), eftersom det inte gick här.
2. **A2T som andra facit i `verify.py` (beslut b)** kan göras utan kontrollen per station och dygn: A2TS ändrar A2T mycket lite (alla mått lika på tre decimaler) och skyddar mot de tydliga felen (2214807 och 22-serien), men godkändes inte. Planeraren väljer om (a) A2T tas som facit utan kontrollen nu, eller (b) en smalare variant väljs först. Min rekommendation är (a), och att kontrollen läggs till senare som avstängt val om en variant godkänns.
3. **En smalare variant** (om b): förlusten kommer troligen från den lösa "noll mot vått" (52350 och 62260 den 2024-07-13, verkliga mätare i skurar). Varianten med bara "våt mot torrt" och skyddet över 400 m, eller "noll mot vått" bara vid starkt regn (A_VAT 0,5 mm per kvart), är de naturliga kandidaterna. De väljs på träningen med samma regel; valideringen har nu setts fyra gånger för A2-familjen, så en ny bedömning bör göras tillsammans med nästa ändring av A2T.
4. Kontrollen av stationsnumren i 22-serien (2214807, 2222811, 2222818, 22088018, 22088020, 22128050, 22128142): de rapporterar bara en del av kvartarna och står för 7 av de 15 kastade stationsdygnen. En enkel regel per station (till exempel att bara använda dem när de rapporterar alla kvartar i timmen) kan vara ett billigare skydd.

Status: klar
