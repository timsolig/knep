# Uppgift 0001: A2 utan falska ekon per kvart i terrängen

Kort: A2T (ingen uppskalning och tak över svagt eko under 0,125 mm per kvart) slår A1 enligt domaren på valideringen utan att något mått blir sämre, och tar bort det som fällde A2: falskt vid torr mätare per kvart över 400 m går från A2:s 0,016 till 0,0118 mot A1:s 0,0133 (+0,0015, +0,0005 till +0,0025) och på lovartsidan till 0,0144 mot 0,0155 (+0,0011, +0,0001 till +0,0023); priset är en lägre summakvot i terrängen per kvart än A2 (0,575 mot 0,632 över 400 m, fortfarande långt över A1:s 0,475).

Uppgiften byggde på `experiments/natt/rapporter/2026-11-06/3-a2.md` och `5-sammanfattning.md`, som jag läste först. Inget var halvfärdigt. Domaren (`experiments/analys/domare.py`) ändrades inte. Testdelen lästes aldrig: punkterna, terrängen och varianterna togs fram bara för `traning` (genom `domare.days`, som kontrollerar det), och valideringen kördes bara för de två frysta varianterna.

## Vad jag gjorde

1. **Terrängen på träningspunkterna** (`a2.py terrang`). Punkterna från uppgift 3 hade inte höjden eller lovartsidan. För de 28 träningsdagarna räknades höjden och domarens `lovart_mask` i mätarnas rutor, sparade i `/data/analys/a2/punkter_terr/` (116 kB). Rörelsen fanns i domarens cache för 15 av dagarna; för de 13 andra räknades den och sparades där som domaren gör (`/data/analys/domare/rorelse/`).
2. **Diagnosen** (`a2.py diagnos`, `/data/analys/a2/diagnos.json`) på träningspunkterna med samma korsvalidering som `a2.py trana`.
3. **Tre mekanismer som val i `a2.py`**, alla avstängda som standard:
   - `K_SVAG`: kvoten i stor skala gäller bara där A1 är minst `K_SVAG` mm, annars k = min(k, 1).
   - `SVAG_TAK` (med `K_SVAG`): där 0 < A1 < `K_SVAG` blir A2 högst A1, så att varken kvoten eller OI-tillskottet lyfter ett svagt eko. Där A1 är 0 får OI fortfarande lägga till regn (nederbörd under strålen).
   - `TORR2`, `R_TORR2`: torrmasken även över svagt eko, A2 = 0 där A1 är under `TORR2` och alla sedda mätare inom `R_TORR2` km är torra.
   Kontrollen av mätarna (innovationen mot grannarna) hann jag inte med.
4. **Valet på träningen** (`a2.py varianter`, 26 varianter för kvarten, `/data/analys/a2/varianter_0.json` och `varianter_1.json`). Två varianter frystes i `FRYSTA` i `a2.py` och committades innan valideringen kördes.
5. **Valideringen**: `a2.py kor --namn A2S` och `--namn A2T` på de 16 valideringsdagarna med A1:s sparade fält, och domarens tabeller mot A1, A0 och A2.

Varianterna ändrar **bara kvarten**. Timmen var inte sämre än A1 i falska ekon och är bit för bit som A2, vilket syns i tabellerna (skillnaden mot A2 är 0 för alla timmått och kartmåttet).

**Standard är oförändrad.** `svag_kvot`, `svag_tak` och den nya torrmasken gör ingenting när `K_SVAG` och `TORR2` är 0 eller saknas. Ett nytt test kontrollerar att PARAMS med de nya nycklarna avstängda ger samma fält, och en jämförelse mot den committade `a2.py` (HEAD före ändringen) på syntetiska data med tre frön gav `np.array_equal` för alla kvarts- och timfält. `A2` i `/data/analys/domare/A2/` är orörd.

## Diagnosen (träningen, 28 dagar)

Bakgrunden på träningspunkterna är A0 utan utfyllnad, som i uppgift 3. Ett falskt eko är A2 över 0,125 mm per kvart (0,5 mm per timme) vid en mätare som visar 0. Klasserna: bakgrunden är redan över tröskeln; bakgrunden är under men k · bakgrund är över (lyft av kvoten); k · bakgrund är under men A2 är över (lyft av OI). Klassen OI räknar också de få fall där bakgrunden var över tröskeln, k drog ner den och OI lyfte den igen (2 över 400 m), så klasserna överlappar något.

| | torra mätarperioder | falskt bakgrund | falskt A2 | A2 falskt: redan över | lyft av k | lyft av OI | bakgrund falskt som A2 tar bort |
|---|---|---|---|---|---|---|---|
| kvart, alla | 258 362 | 0,0239 | 0,0230 | 4 951 | 386 | 660 | 1 223 |
| kvart, över 400 m | 33 972 | 0,0158 | 0,0160 | 445 | 38 | 63 | 92 |
| kvart, lovart | 21 011 | 0,0188 | 0,0192 | 333 | 38 | 36 | 62 |
| timme, alla | 63 674 | 0,0102 | 0,0091 | 471 | 41 | 67 | 181 |
| timme, över 400 m | 7 192 | 0,0103 | 0,0095 | 56 | 3 | 9 | 18 |
| timme, lovart | 4 526 | 0,0084 | 0,0071 | 26 | 3 | 3 | 12 |

Det som syns:

- **De flesta falska ekona i A2 finns redan i bakgrunden** (82 % över 400 m per kvart). A2 tar bort en del av dem, men i terrängen per kvart lyfter A2 fler (99 över 400 m där bakgrunden var under tröskeln) än den tar bort (92), och nettot blir sämre. Per timme tar A2 bort fler än den lyfter, vilket stämmer med att timmen inte var sämre på valideringen.
- **Lyften kommer lika mycket från OI som från kvoten**: över 400 m 63 av OI och 38 av k, på lovartsidan 36 och 38. Bara en uppskalning av k räcker alltså inte.
- **Lyften sker nästan bara från svagt eko strax under tröskeln.** Av de lyfta kvartarna över 400 m hade 94 av 99 en bakgrund mellan 0,05 och 0,125 mm (median 0,104 mm), och ingen hade 0. Kvoten vid de lyfta var i median 1,18 (över 400 m) och 1,29 (lovart).
- **Torrmasken kan inte göra mycket i korsvalideringen**: en bedömd mätare har ingen sedd mätare inom 25 km, så masken verkar bara med en radie över bufferten, och då tar den också bort riktigt regn (se valet nedan).
- På valideringen var A2:s överskott mot bakgrunden större (0,016 mot A1:s 0,013) än på träningen (0,0160 mot A0:s 0,0158). Den troliga skillnaden är att A1 smetar ut ekot längs rörelsen och ger fler rutor med svagt eko strax under tröskeln än A0. Det talar för en variant som tar bort lyften helt, inte bara en del av dem.

## Valet på träningen

Mål = MAE · (1 + 0,5 · |ln kvot|) som i uppgift 3 (lägre är bättre). Falskt är andelen torra mätarkvartar med A2 över 0,125 mm. Samma korsvalidering som `trana` (grupper om 100 km, buffert 25 km). R är `R_TORR2` i km.

| variant | mål | MAE (mm) | kvot | CSI 0,5 | falskt alla | falskt över 400 m | falskt lovart |
|---|---|---|---|---|---|---|---|
| standard (A2) | 0,05906 | 0,05539 | 0,876 | 0,315 | 0,0230 | 0,0160 | 0,0192 |
| **K_SVAG=0,1 (A2S)** | **0,05939** | 0,05553 | 0,870 | 0,316 | 0,0220 | 0,0152 | 0,0183 |
| K_SVAG=0,125 | 0,05950 | 0,05556 | 0,868 | 0,317 | 0,0213 | 0,0146 | 0,0176 |
| K_SVAG=0,2 | 0,05977 | 0,05559 | 0,860 | 0,316 | 0,0212 | 0,0145 | 0,0174 |
| K_SVAG=0,3 | 0,05994 | 0,05551 | 0,852 | 0,313 | 0,0212 | 0,0145 | 0,0173 |
| K_SVAG=0,1 tak | 0,06012 | 0,05572 | 0,854 | 0,316 | 0,0210 | 0,0148 | 0,0178 |
| **K_SVAG=0,125 tak (A2T)** | **0,06039** | 0,05579 | 0,848 | 0,317 | 0,0192 | **0,0131** | **0,0158** |
| K_SVAG=0,2 tak | 0,06115 | 0,05595 | 0,830 | 0,316 | 0,0190 | 0,0130 | 0,0155 |
| K_SVAG=0,3 tak | 0,06168 | 0,05591 | 0,814 | 0,313 | 0,0190 | 0,0130 | 0,0155 |
| TORR2=0,1 R=30 | 0,05906 | 0,05539 | 0,876 | 0,315 | 0,0230 | 0,0160 | 0,0192 |
| TORR2=0,1 R=40 | 0,05906 | 0,05537 | 0,875 | 0,315 | 0,0230 | 0,0160 | 0,0192 |
| TORR2=0,1 R=80 | 0,05955 | 0,05509 | 0,850 | 0,315 | 0,0228 | 0,0160 | 0,0192 |
| TORR2=0,2 R=30 | 0,05906 | 0,05539 | 0,876 | 0,315 | 0,0229 | 0,0159 | 0,0192 |
| TORR2=0,2 R=40 | 0,05909 | 0,05537 | 0,874 | 0,315 | 0,0229 | 0,0159 | 0,0191 |
| TORR2=0,2 R=80 | 0,06058 | 0,05525 | 0,825 | 0,315 | 0,0202 | 0,0147 | 0,0170 |
| TORR2=0,3 R=30 | 0,05905 | 0,05538 | 0,876 | 0,315 | 0,0229 | 0,0158 | 0,0191 |
| TORR2=0,3 R=40 | 0,05910 | 0,05537 | 0,874 | 0,315 | 0,0228 | 0,0158 | 0,0191 |
| TORR2=0,3 R=80 | 0,06144 | 0,05539 | 0,804 | 0,315 | 0,0179 | 0,0133 | 0,0158 |
| K_SVAG=0,125 tak TORR2=0,1 R=40 | 0,06040 | 0,05576 | 0,847 | 0,317 | 0,0192 | 0,0131 | 0,0158 |
| K_SVAG=0,125 tak TORR2=0,1 R=80 | 0,06083 | 0,05549 | 0,825 | 0,317 | 0,0192 | 0,0131 | 0,0158 |
| K_SVAG=0,125 tak TORR2=0,2 R=40 | 0,06043 | 0,05577 | 0,846 | 0,317 | 0,0192 | 0,0130 | 0,0158 |
| K_SVAG=0,125 tak TORR2=0,2 R=80 | 0,06187 | 0,05565 | 0,800 | 0,317 | 0,0170 | 0,0121 | 0,0141 |
| K_SVAG=0,2 tak TORR2=0,1 R=40 | 0,06115 | 0,05592 | 0,829 | 0,316 | 0,0190 | 0,0130 | 0,0155 |
| K_SVAG=0,2 tak TORR2=0,1 R=80 | 0,06160 | 0,05565 | 0,808 | 0,316 | 0,0190 | 0,0130 | 0,0155 |
| K_SVAG=0,2 tak TORR2=0,2 R=40 | 0,06118 | 0,05593 | 0,829 | 0,316 | 0,0190 | 0,0129 | 0,0154 |
| K_SVAG=0,2 tak TORR2=0,2 R=80 | 0,06262 | 0,05583 | 0,784 | 0,316 | 0,0169 | 0,0121 | 0,0140 |

Underlaget: 258 362 torra mätarkvartar, 33 972 över 400 m och 21 011 på lovartsidan.

**Ingen variant sänker både målet och de falska ekona.** Varje variant som tar bort falska ekon sänker också summakvoten, eftersom de lyfta svaga ekona i medel bär regn (mätarna är oftare våta än torra där). Målet straffar kvoten, så valet kan inte bara vara den med lägst mål. Jag använde därför den här regeln, skriven och fryst innan valideringen kördes:

- **A2S**: den variant med lägst mål bland dem som sänker falskt både över 400 m och på lovartsidan. Det är `K_SVAG = 0,1` (målet +0,6 %, falskt över 400 m 0,0160 till 0,0152).
- **A2T**: den variant med lägst mål bland dem som sänker falskt över 400 m och på lovartsidan med minst 0,002, två tredjedelar av A2:s underskott mot A1 på valideringen (0,003) som uppgiften anger. Det är `K_SVAG = 0,125` med `SVAG_TAK` (målet +2,3 %, falskt över 400 m 0,0160 till 0,0131 och på lovartsidan 0,0192 till 0,0158).

Torrmasken över svagt eko (`TORR2`) gör inget med radien 30 eller 40 km och kostar mer i kvot än taket med 80 km, och kombinationerna gav nästan inget utöver taket. Den togs inte vidare. Att 0,002 hämtades ur valideringens siffror från uppgift 3 är en svaghet i regeln, men siffran stod i uppgiften och valideringen för varianterna var inte sedd.

## Domarens tabeller på valideringen (16 dagar)

Skillnaden är i godhet (större är bättre) med 95 % från bootstrap över dagarna (2 000 dragningar). Hela tabellerna i `/data/analys/domare/tabell_A2S_mot_{A1,A0,A2}_validering.json` och `tabell_A2T_mot_{A1,A0,A2}_validering.json`; utskrift med `uv run python experiments/analys/domare.py tabell A2T --mot A1` (och `--mot A0`, `--mot A2`).

### A2T

| delmängd | mått | A2T | A1 | A0 | A2 | mot A1 (95 %) | mot A0 (95 %) | mot A2 (95 %) |
|---|---|---|---|---|---|---|---|---|
| kvart, alla | kvot summa | 0,851 | 0,824 | 0,826 | 0,886 | +0,032 (−0,052 till +0,110) | +0,030 (−0,053 till +0,108) | **−0,040 (−0,054 till −0,029)** |
| kvart, alla | MAE (mm) | 0,0654 | 0,0667 | 0,0693 | 0,0642 | +0,0013 (−0,0009 till +0,0038) | **+0,0040 (+0,0019 till +0,0063)** | **−0,0011 (−0,0018 till −0,0005)** |
| kvart, alla | CSI 0,5 | 0,336 | 0,303 | 0,288 | 0,336 | **+0,033 (+0,013 till +0,050)** | **+0,048 (+0,030 till +0,064)** | −0,000 (−0,001 till +0,001) |
| kvart, alla | CSI 1 | 0,232 | 0,196 | 0,179 | 0,233 | **+0,036 (+0,013 till +0,055)** | **+0,053 (+0,024 till +0,075)** | −0,001 (−0,002 till +0,000) |
| kvart, alla | FSS 1 | 0,392 | 0,333 | 0,327 | 0,390 | **+0,059 (+0,029 till +0,080)** | **+0,065 (+0,034 till +0,085)** | **+0,002 (+0,001 till +0,003)** |
| kvart, alla | falskt vid torr mätare | 0,0199 | 0,0252 | 0,0259 | 0,0245 | **+0,0052 (+0,0036 till +0,0070)** | **+0,0060 (+0,0043 till +0,0078)** | **+0,0045 (+0,0032 till +0,0062)** |
| kvart, alla | falskt där allt inom 25 km är torrt | 0,0193 | 0,0245 | 0,0253 | 0,0237 | **+0,0052 (+0,0035 till +0,0069)** | **+0,0060 (+0,0042 till +0,0077)** | **+0,0044 (+0,0030 till +0,0060)** |
| kvart, alla | hopp, kvot mot mätarna | 0,882 | 0,809 | 0,884 | 0,888 | +0,087 (−0,004 till +0,164) | −0,002 (−0,078 till +0,080) | −0,007 (−0,016 till +0,000) |
| kvart, över 400 m | kvot summa | 0,575 | 0,475 | 0,495 | 0,632 | **+0,191 (+0,089 till +0,275)** | +0,150 (−0,029 till +0,282) | **−0,094 (−0,122 till −0,068)** |
| kvart, över 400 m | MAE (mm) | 0,0491 | 0,0483 | 0,0506 | 0,0476 | −0,0009 (−0,0029 till +0,0011) | +0,0015 (−0,0012 till +0,0046) | **−0,0015 (−0,0028 till −0,0005)** |
| kvart, över 400 m | CSI 0,5 | 0,241 | 0,175 | 0,154 | 0,239 | +0,066 (−0,001 till +0,121) | **+0,087 (+0,023 till +0,139)** | +0,002 (−0,005 till +0,008) |
| kvart, över 400 m | FSS 1 | 0,357 | 0,261 | 0,252 | 0,354 | +0,096 (−0,002 till +0,160) | **+0,105 (+0,001 till +0,164)** | +0,002 (−0,002 till +0,006) |
| kvart, över 400 m | falskt vid torr mätare | 0,0118 | 0,0133 | 0,0146 | 0,0160 | **+0,0015 (+0,0005 till +0,0025)** | +0,0027 (−0,0005 till +0,0074) | **+0,0042 (+0,0023 till +0,0066)** |
| kvart, över 400 m | falskt där allt inom 25 km är torrt | 0,0118 | 0,0132 | 0,0145 | 0,0160 | **+0,0014 (+0,0004 till +0,0025)** | +0,0027 (−0,0005 till +0,0073) | **+0,0043 (+0,0024 till +0,0066)** |
| kvart, lovart | kvot summa | 0,705 | 0,592 | 0,604 | 0,750 | **+0,174 (+0,058 till +0,253)** | **+0,155 (+0,042 till +0,243)** | **−0,062 (−0,083 till −0,033)** |
| kvart, lovart | MAE (mm) | 0,0688 | 0,0686 | 0,0709 | 0,0669 | −0,0002 (−0,0038 till +0,0031) | +0,0021 (−0,0015 till +0,0051) | **−0,0019 (−0,0040 till −0,0001)** |
| kvart, lovart | CSI 0,5 | 0,330 | 0,271 | 0,258 | 0,324 | +0,059 (−0,002 till +0,099) | **+0,072 (+0,011 till +0,106)** | **+0,006 (+0,003 till +0,008)** |
| kvart, lovart | FSS 1 | 0,379 | 0,277 | 0,264 | 0,375 | **+0,102 (+0,003 till +0,167)** | **+0,115 (+0,023 till +0,169)** | +0,004 (−0,002 till +0,007) |
| kvart, lovart | falskt vid torr mätare | 0,0144 | 0,0155 | 0,0164 | 0,0188 | **+0,0011 (+0,0001 till +0,0023)** | **+0,0020 (+0,0008 till +0,0040)** | **+0,0044 (+0,0022 till +0,0068)** |
| kvart, lovart | falskt där allt inom 25 km är torrt | 0,0144 | 0,0154 | 0,0164 | 0,0185 | +0,0010 (−0,0000 till +0,0023) | **+0,0020 (+0,0008 till +0,0040)** | **+0,0041 (+0,0021 till +0,0064)** |
| timme, alla | kvot summa | 0,945 | 0,889 | 0,890 | 0,945 | +0,060 (−0,018 till +0,142) | +0,060 (−0,018 till +0,141) | 0 |
| timme, alla | MAE (mm) | 0,214 | 0,228 | 0,233 | 0,214 | **+0,014 (+0,006 till +0,024)** | **+0,019 (+0,011 till +0,029)** | 0 |
| timme, alla | CSI 1 | 0,470 | 0,429 | 0,423 | 0,470 | **+0,041 (+0,018 till +0,064)** | **+0,047 (+0,024 till +0,071)** | 0 |
| timme, alla | FSS 1 | 0,685 | 0,635 | 0,634 | 0,685 | **+0,050 (+0,025 till +0,074)** | **+0,050 (+0,026 till +0,074)** | 0 |
| timme, alla | falskt vid torr mätare | 0,0087 | 0,0095 | 0,0104 | 0,0087 | +0,0008 (−0,0002 till +0,0018) | **+0,0016 (+0,0004 till +0,0029)** | 0 |
| timme, över 400 m | kvot summa | 0,676 | 0,505 | 0,524 | 0,676 | **+0,291 (+0,198 till +0,357)** | **+0,255 (+0,081 till +0,371)** | 0 |
| timme, över 400 m | CSI 1 | 0,370 | 0,259 | 0,248 | 0,370 | **+0,112 (+0,031 till +0,175)** | **+0,122 (+0,047 till +0,182)** | 0 |
| timme, över 400 m | FSS 1 | 0,551 | 0,432 | 0,429 | 0,551 | **+0,119 (+0,043 till +0,180)** | **+0,123 (+0,049 till +0,181)** | 0 |
| timme, över 400 m | falskt vid torr mätare | 0,0076 | 0,0073 | 0,0089 | 0,0076 | −0,0003 (−0,0026 till +0,0017) | +0,0013 (−0,0020 till +0,0056) | 0 |
| timme, lovart | kvot summa | 0,821 | 0,653 | 0,671 | 0,821 | **+0,230 (+0,089 till +0,327)** | **+0,202 (+0,052 till +0,310)** | 0 |
| timme, lovart | FSS 1 | 0,715 | 0,624 | 0,622 | 0,715 | **+0,091 (+0,009 till +0,150)** | **+0,093 (+0,011 till +0,150)** | 0 |
| timme, lovart | falskt vid torr mätare | 0,0110 | 0,0101 | 0,0113 | 0,0110 | −0,0009 (−0,0031 till +0,0009) | +0,0003 (−0,0018 till +0,0024) | 0 |
| kartmåttet | rutor per dag | 47,2 | 40,4 | 36,6 | 47,2 | −6,8 (−19,8 till +3,4) | −10,6 (−24,9 till +0,1) | 0 |

### A2S

| delmängd | mått | A2S | A1 | A0 | A2 | mot A1 (95 %) | mot A0 (95 %) | mot A2 (95 %) |
|---|---|---|---|---|---|---|---|---|
| kvart, alla | kvot summa | 0,878 | 0,824 | 0,826 | 0,886 | +0,063 (−0,026 till +0,143) | +0,062 (−0,025 till +0,141) | **−0,009 (−0,013 till −0,006)** |
| kvart, alla | MAE (mm) | 0,0647 | 0,0667 | 0,0693 | 0,0642 | +0,0020 (−0,0001 till +0,0043) | **+0,0047 (+0,0028 till +0,0068)** | **−0,0004 (−0,0007 till −0,0002)** |
| kvart, alla | CSI 1 | 0,232 | 0,196 | 0,179 | 0,233 | **+0,037 (+0,014 till +0,056)** | **+0,053 (+0,024 till +0,076)** | −0,001 (−0,002 till +0,000) |
| kvart, alla | FSS 1 | 0,392 | 0,333 | 0,327 | 0,390 | **+0,059 (+0,029 till +0,080)** | **+0,065 (+0,034 till +0,085)** | **+0,002 (+0,001 till +0,003)** |
| kvart, alla | falskt vid torr mätare | 0,0229 | 0,0252 | 0,0259 | 0,0245 | **+0,0022 (+0,0002 till +0,0042)** | **+0,0030 (+0,0010 till +0,0049)** | **+0,0015 (+0,0009 till +0,0023)** |
| kvart, över 400 m | kvot summa | 0,614 | 0,475 | 0,495 | 0,632 | **+0,256 (+0,148 till +0,341)** | **+0,215 (+0,032 till +0,352)** | **−0,029 (−0,039 till −0,017)** |
| kvart, över 400 m | MAE (mm) | 0,0482 | 0,0483 | 0,0506 | 0,0476 | +0,0000 (−0,0021 till +0,0023) | +0,0024 (−0,0003 till +0,0056) | **−0,0006 (−0,0011 till −0,0002)** |
| kvart, över 400 m | falskt vid torr mätare | 0,0145 | 0,0133 | 0,0146 | 0,0160 | −0,0012 (−0,0030 till +0,0004) | +0,0000 (−0,0034 till +0,0042) | **+0,0015 (+0,0007 till +0,0026)** |
| kvart, över 400 m | falskt där allt inom 25 km är torrt | 0,0145 | 0,0132 | 0,0145 | 0,0160 | −0,0013 (−0,0031 till +0,0003) | −0,0000 (−0,0035 till +0,0042) | **+0,0015 (+0,0007 till +0,0026)** |
| kvart, lovart | kvot summa | 0,736 | 0,592 | 0,604 | 0,750 | **+0,218 (+0,085 till +0,306)** | **+0,198 (+0,067 till +0,296)** | **−0,019 (−0,027 till −0,007)** |
| kvart, lovart | falskt vid torr mätare | 0,0170 | 0,0155 | 0,0164 | 0,0188 | −0,0015 (−0,0030 till +0,0000) | −0,0006 (−0,0019 till +0,0012) | **+0,0018 (+0,0004 till +0,0035)** |
| kvart, lovart | falskt där allt inom 25 km är torrt | 0,0168 | 0,0154 | 0,0164 | 0,0185 | −0,0014 (−0,0029 till +0,0001) | −0,0004 (−0,0017 till +0,0013) | **+0,0017 (+0,0004 till +0,0032)** |

Timmen och kartmåttet är för A2S desamma som för A2 och A2T (tabellen ovan). Den fulla tabellen för A2S finns i tabellfilerna.

## Domen

| system | mot A1 | mot A0 | mot A2 |
|---|---|---|---|
| **A2T** | **bättre**: 13 mått, inget sämre | **bättre**: 15 mått, inget sämre | inte bättre: sämre i summakvot och MAE per kvart över 400 m och på lovart |
| A2S | bättre (knappt): 13 mått, inget sämre | bättre: 15 mått, inget sämre | inte bättre: sämre i samma fyra mått |

- **A2T mot A1: bättre.** Bättre med intervallet helt på den bättre sidan i kvot > 1 mm, CSI 0,5, CSI 1, FSS 0,5 och FSS 1 per kvart och i kvot > 1 och 5 mm, MAE, CSI 0,5 och 1 och FSS 0,5, 1 och 5 per timme. Falska ekon per kvart är nu **bättre** än A1 med intervallet helt över 0 för alla mätare, över 400 m och på lovart, och inget mått för falska ekon eller terrängen är sämre. Kartmåttet är som för A2 (−6,8, −19,8 till +3,4) och räknas inte som sämre enligt regeln. Det är det enda som är kvar av A2:s problem med svagt eko, och det beror på timmen.
- **A2S mot A1: bättre, men på gränsen.** Inget mått är sämre, men falskt vid torr mätare per kvart på lovartsidan har övre gränsen +0,0000015 och över 400 m +0,0004. Ett par dagar till kunde ha fällt den. A2S halverar bara A2:s underskott mot A1.
- **Mot A2 är båda sämre i terrängens mängd per kvart.** Taket och gränsen för kvoten tar bort både klotter och riktigt svagt regn, så summakvoten per kvart över 400 m sjunker från 0,632 till 0,575 (A2T) och MAE ökar med 0,0015 mm. Det är priset för de falska ekona, och båda varianterna ligger ändå långt över A1 i kvoten.

**Rekommendation:** A2T är den första analysen som slår både A0 och A1 enligt domaren. Den bör ersätta A2 som utgångspunkt för det fortsatta arbetet. Inget i drift ändras; A2 finns inte i `src/`.

## Körtiderna

| steg | tid |
|---|---|
| terrängen på träningspunkterna, 28 dagar, två processer | cirka 25 min (20 till 35 s per dag med rörelsen i cachen, cirka 3 min utan) |
| diagnosen, kvart och timme | cirka 3 min |
| varianterna, 26 på träningspunkterna, två processer | cirka 20 min (90 till 135 s per variant) |
| A2S och A2T genom domaren, 16 dagar var, två processer samtidigt | cirka 65 min (30 till 60 s läsning och 170 till 260 s för A2 och domaren per dag) |

Ny data: `/data/analys/a2/punkter_terr/` (116 kB), `diagnos.json`, `varianter_*.json`, `/data/analys/domare/A2S/` och `A2T/` (80 kB var) och rörelsen för 13 träningsdagar i `/data/analys/domare/rorelse/` (några MB). Långt under 1 GB; `df /data` visade 4,9 GB ledigt efteråt.

## Ändrade filer

- `experiments/analys/a2.py`: `svag_kvot`, `svag_tak` och torrmasken över svagt eko (`K_SVAG`, `SVAG_TAK`, `TORR2`, `R_TORR2`, alla av som standard) i både punktversionen och fältversionen; `FRYSTA` med A2S och A2T och `system_params`; kommandona `terrang`, `diagnos` och `varianter`; `kor --namn` för varianterna.
- `tests/test_analys_a2.py`: 4 nya tester (avstängda val ger samma fält och de frysta varianterna rör inte timmen; kvoten skalar inte upp svagt eko; taket stoppar OI:s lyft men låter OI lägga till regn där A1 är 0; torrmasken över svagt eko tar bort bara när mätarna är torra). `uv run pytest` ger 172 godkända.
- Inget i `src/`, `deploy/`, `models/`, `.github/`, domaren eller `experiments/sverige/dagar.json` ändrades.

## Nästa steg

1. **Kontrollen av mätarna** innan A2T blir facit: en innovation d över 3 σ mot grannarna (eller mot radarn där den är säker) kastas, vald på träningen. Utan den sprider OI ett fel i en mätare upp till cirka 40 km.
2. **F4 under A2T**: kör A1 och A2T på F4:s bilder. Kartmåttet (47,2 rutor per dag mot A0:s 36,6) är det som fortfarande är sämst och styrs av timmen, där varianterna inte verkar. Ett tak över svagt eko också per timme (till exempel `K_SVAG` 0,5 mm) kan prövas på träningen, men timmens falska ekon är redan inte sämre än A1.
3. **Mängden i terrängen tillbaka**: taket tar bort riktigt svagt regn i fjällen. Ett tak som bara gäller svagt eko som står still (klotter) eller där radarns stråle är låg över terrängen kan ge tillbaka en del av A2:s kvot utan klottret.
4. **Flytta A2T till `src/knep/analys/a2.py` som ett avstängt val** när kontrollen av mätarna finns och gärna efter F4-steget, och fyll `a2` i manifestet först efter användarens beslut. Tiden är som A2 (2,6 till 2,8 s per timme med fyra kvartar), eftersom varianten bara lägger till några jämförelser.
5. Testdelen för A2T, om användaren vill (kommandot `a2.py kor --namn A2T` kontrollerar i dag att dagen hör till valideringen och skulle behöva en liten upplåsning).

Status: klar
