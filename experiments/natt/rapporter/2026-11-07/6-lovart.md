# Uppgift 6: A1:s underskott på lovartsidan

Kort: underskottet är ingen förlust av regn utan en utjämning av toppar i regn som rör sig fort. Valet `stay` i A1 (standard av) håller kvar den del av fältet som finns på samma plats i båda bilderna, antingen överallt (A1M) eller där lyftet är stort (A1L1). Ingen variant klarade regeln på träningen (5 dagar), så ingen frystes. A1L1 är på valideringen bättre än A0 utan något sämre mått, vilket A1 inte är, men sämre än A1 över 400 m och i falska ekon per kvart på lovartsidan.

## Före uppgiften

Rapporterna i `2026-11-06/` (1 till 5 och sammanfattningen) slutar alla med `Status: klar`. Uppgift 4 (filtret) gick i två försök; det första slutade som delvis, men det andra (F4) blev klart och godkänt. Inget som rör lovartsidan var halvfärdigt, så inget behövde göras om först.

## Diagnosen: var och varför

`experiments/analys/lovart.py diag --dag <dag>` läser A0 (domarens `Radardag` och `A0`) och A1:s sparade fält (`/data/analys/a2/a1falt`) och tittar på mätartimmarna på lovartsidan. De två dagarna är valideringsdagar; de används bara för att förstå felet, inte för att välja något. Utdata: `/data/analys/lovart/diag_<dag>.json`.

| | 2023-08-08 | 2021-10-20 |
|---|---|---|
| mätartimmar på lovartsidan | 681 | 182 |
| A0 / A1 / mätarna vid lovartmätarna (mm) | 212,2 / 196,9 / 313,5 | 84,1 / 76,9 / 81,1 |
| massan i hela lovartmasken, A1/A0 | 0,999 | 1,002 |
| massan i hela rutnätet, A1/A0 | 1,000 | 1,001 |
| vid lovartmätarna efter Gauss 2 px (4 km), A1/A0 | 0,996 | 1,003 |
| A1/A0 där A0 < 1 mm/h | 1,10 | 0,99 |
| A1/A0 där A0 > 3 mm per timme | 0,88 | 0,87 |
| A1/A0 vid fart 2 till 4 px per 5 min | 0,94 | 0,90 |
| A1/A0 vid fart under 2 px per 5 min | 1,0 | 1,0 |
| korrelation A0 t mot t + 15 min vid mätarna, på plats / längs rörelsen | 0,16 / 0,30 | 0,30 / 0,49 |
| andel fall där regnet står stilla bättre än det rör sig | 0,29 | 0,21 |

Slutsatserna:

1. **Inget regn flyttas bort från sluttningen.** Massan i lovartmasken och i hela rutnätet är densamma i A1 som i A0 inom 0,2 %, och efter en utjämning med 4 km är skillnaden vid mätarna borta (0,996 och 1,003). Underskottet är alltså inte en förskjutning nedströms utan en **utsmetning av topparna i rutans skala**: där A0 har en stark topp vid mätaren (över 3 mm/h) ger A1 12 till 14 % mindre, där A0 är svagt ger A1 lika mycket eller mer.
2. **Det händer där regnet rör sig fort** (2 till 8 px, 4 till 16 km, per 5 min). Vid långsam rörelse är A1 = A0. Interpoleringen är en utsmetning längs rörelsen med bredden av förflyttningen; en topp som är smalare än så sänks.
3. **Regnet vid lovartmätarna står inte stilla.** I 71 till 79 % av fallen stämmer bilden 15 min senare bättre med den förra flyttad längs rörelsen än på plats. Bilden av "orografisk nederbörd som står still men flyttas av interpoleringen" stämmer alltså bara för en mindre del av fallen.
4. **Underskottet sitter vid några få mätare där A0 är högre än mätaren.** 2021-10-20 kommer 5,5 av 7,2 mm från en station (74180, 173 m, i sydsvenska höjdområdet): A0 26,5, A1 21,0, mätaren 9,9 mm. 2023-08-08 är de tre största 180770 (A0 12,5, A1 7,1, mätaren 6,8), 123460 (9,6, 5,4, 13,3) och 180760 (22,1, 19,1, 9,7). Vid två av de tre ligger A1 närmare mätaren. MAE på lovartsidan är också bättre för A1 (+0,006, intervallet över 0, uppgift 2). Domarens summakvot belönar A0 här därför att radarn i stort är för torr på lovartsidan (kvoten 0,67): toppar som är för höga vid en mätare väger upp att andra mätare får för lite.

## Rättningen: valet `stay` i A1

`src/knep/analys/a1.py` har fått valet `stay` i `interval_mean` (standard `None`, som förut och bit för bit lika, vilket ett test kontrollerar). Med `stay` ligger andelen s per ruta av den del som finns på samma plats i båda bilderna, c = s · min(f0, f1), kvar på platsen, och bara resten (f0 − c och f1 − c) interpoleras längs rörelsen. En cell som flyttar sig långt har nästan ingen gemensam del och flyttas som förut; regn som står still smetas inte ut. Massan bevaras. Samtidigt delades funktionen i `paths` (förflyttningarna, bara rörelsen) och `interpolate` (fälten), så att flera varianter kan räknas på samma förflyttning; `stay_fraction(motion, terrain, k)` ger s = 1 − exp(−k · max(u·∇h, 0)) ur lyftet, som `Chain.stay` i prognosen (terrängen utjämnad med Gauss 2 px, vald i förväg och inte på data). Tre nya tester i `tests/test_a1.py`. Valet är inte kopplat till `cli.py`, eftersom ingen variant valdes (se nedan).

Varianterna, valda i förväg:

| namn | stay |
|---|---|
| A1 | av (drift) |
| A1M | s = 1 överallt: hela den gemensamma delen står still (ingen parameter) |
| A1L1 | s ur lyftet med k = 1 per m (s = 0,95 vid 3 m per 5 min) |
| A1L03 | s ur lyftet med k = 0,3 (bara 2020-02-10, se Körningen) |

`experiments/analys/lovart.py kor` räknar dem genom domaren (`domare.evaluate_fields`, summorna i `/data/analys/domare/<variant>/<dag>.json`) med kvart och timme ur intervallen ett i taget. Kontrollen: på 2021-10-20 ger strömmens A1 exakt samma fält som domarens sparade A1 (största skillnad 0,0, samma NaN) och samma summor (`lovart.py jamfor`).

## Valet på träningsdagarna

Regeln bestämdes innan resultaten lästes (`lovart.py valj`): bland varianterna som inte är sämre i något mått enligt domens regel, varken mot A0 eller mot A1, välj den med störst skillnad i godhet mot A1 för summakvoten per timme på lovartsidan.

Träningen hann bara 5 av de 28 dagarna (2020-02-10, 2020-07-24, 2021-01-23, 2022-12-20, 2023-07-12; se Körningen). Med kravet på 5 dagars underlag räknas de flesta måtten ändå. Tabellerna: `/data/analys/domare/tabell_{A1,A1M,A1L1}_mot_{A0,A1}_traning.json`.

| mått (skillnad i godhet, 95 %) | A1 − A0 | A1M − A1 | A1L1 − A1 | A1L1 − A0 |
|---|---|---|---|---|
| timme lovart, kvot summa | +0,003 (−0,006 till +0,024) | −0,005 (−0,013 till +0,003) | +0,017 (−0,000 till +0,032) | **+0,021 (+0,007 till +0,035)** |
| kvart lovart, kvot summa | +0,003 (−0,008 till +0,023) | −0,007 (−0,015 till +0,005) | +0,015 (−0,005 till +0,029) | +0,018 (−0,000 till +0,034) |
| timme över 400 m, kvot summa | −0,045 (−0,250 till +0,105) | +0,024 (−0,079 till +0,161) | **−0,032 (−0,067 till −0,005)** | −0,077 (−0,286 till +0,040) |
| kvart alla, CSI 0,5 | **+0,020** | **−0,010** | **−0,007** | **+0,014** |
| timme alla, MAE | **+0,007** | **−0,002** | **−0,001** | **+0,005** |
| kartmåttet (rutor per dag) | −4,8 (−14,0 till +1,6) | **+6,6 (+0,2 till +15,2)** | +4,6 (−0,0 till +10,6) | −0,2 (−4,2 till +3,8) |

Domen på träningen:

- **A1 mot A0: bättre**, inget sämre. På de här 5 dagarna har A1 inget underskott på lovartsidan (0,661 mot 0,659).
- **A1M**: bättre än A0, men mot A1 sämre i MAE över 400 m och på lovartsidan, CSI 0,5 på lovartsidan och CSI 0,5 och FSS 0,5 över 400 m. Den behåller ungefär hälften av A1:s vinst per kvart och ger färre rutor med eko under torra timmar än A1, men den rättar inte summakvoten på lovartsidan.
- **A1L1**: den enda som rättar summakvoten på lovartsidan (mot A0 med intervallet helt över 0), men mot A1 sämre i summakvoten och MAE över 400 m och i falska ekon per timme (båda måtten), och mot A0 sämre i FSS 1 över 400 m.
- **Valet: ingen variant klarar regeln**, så ingen frystes som ersättare till A1. Det försiktigaste är att A1 står kvar som den är och valet `stay` stannar av.

## Valideringen (16 dagar)

Eftersom ingen variant valdes finns inget fryst system att bedöma. Jag körde ändå **A1L1** genom domaren på valideringen, som information: den är den enda variant som på träningen rättade det uppgiften gäller (summakvoten på lovartsidan), och utan den siffran går det inte att säga om riktningen håller. A1M kördes inte på valideringen; tiden räckte till en variant. Tabellerna: `/data/analys/domare/tabell_A1L1_mot_{A0,A1}_validering.json` (A1 mot A0 räknades om ur samma filer och är identisk med uppgift 2).

| mått (skillnad i godhet, 95 %) | A1 − A0 | A1L1 − A0 | A1L1 − A1 |
|---|---|---|---|
| timme lovart, kvot summa (A0 0,671, A1 0,653, A1L1 0,677) | **−0,028 (−0,051 till −0,006)** | +0,009 (−0,005 till +0,026) | **+0,037 (+0,024 till +0,049)** |
| kvart lovart, kvot summa (0,604, 0,592, 0,613) | **−0,020 (−0,039 till −0,001)** | **+0,016 (+0,002 till +0,033)** | **+0,035 (+0,022 till +0,048)** |
| timme över 400 m, kvot summa (0,524, 0,505, 0,494) | −0,036 (−0,154 till +0,042) | −0,059 (−0,193 till +0,017) | **−0,022 (−0,042 till −0,005)** |
| timme lovart, MAE | **+0,006** | +0,004 (−0,001 till +0,008) | −0,002 (−0,006 till +0,001) |
| kvart alla, CSI 0,5 (0,287, 0,303, 0,301) | **+0,015** | **+0,013 (+0,007 till +0,021)** | −0,002 (−0,005 till +0,001) |
| kvart alla, CSI 1 (0,179, 0,196, 0,189) | **+0,017** | **+0,011 (+0,000 till +0,020)** | **−0,006 (−0,009 till −0,003)** |
| kvart alla, MAE | **+0,003** | **+0,002** | **−0,0007** |
| timme alla, MAE | **+0,005** | **+0,003** | **−0,002** |
| hopp per kvart, kvot mot mätarna (0,884, 0,809, 0,832; ingår inte i domen) | −0,089 (−0,109 till −0,003) | −0,061 (−0,077 till +0,024) | +0,029 (+0,023 till +0,034) |
| kartmåttet (36,6, 40,4, 37,2 rutor per dag) | −3,9 (−9,5 till +1,0) | −0,7 (−5,9 till +3,8) | **+3,2 (+1,1 till +5,9)** |

Domen på valideringen:

- **A1 mot A0: inte bättre** (sämre i summakvoten på lovartsidan, kvart och timme), som i uppgift 2.
- **A1L1 mot A0: bättre**, inget sämre. Bättre i MAE, CSI 0,5 och 1 och FSS 0,5 (kvart och timme), FSS 1 per kvart och CSI 5 per timme. Underskottet på lovartsidan är borta (kvart +0,016 med intervallet över 0, timme +0,009). Kartmåttet är nästan som A0:s (37,2 mot 36,6), så utsmetningen av klottret som A1 ger (40,4) försvinner till största delen.
- **A1L1 mot A1: inte bättre.** Bättre i summakvoten per kvart, kvoten över 1 mm per timme och FSS 0,5 per timme, och på lovartsidan (+0,037), men sämre i summakvoten över 400 m (kvart och timme), FSS 1 per kvart och FSS 0,5 per timme över 400 m och i falska ekon per kvart på lovartsidan (båda måtten). Av A1:s vinst per kvart mot A0 behåller A1L1 ungefär 60 till 87 %.

Vad det betyder: att hålla kvar den gemensamma delen där lyftet är stort tar bort underskottet på lovartsidan och gör A1 godkänd mot A0, men till priset av mindre regn över 400 m (där mätarnas mängd redan är dubbelt så stor som radarns) och fler falska ekon per kvart på lovartsidan. Det stämmer med diagnosen: det mesta regnet på lovartsidan rör sig, så att låta det stå still där lyftet är stort håller kvar också sådant som borde ha flyttats (falska ekon per kvart), och över 400 m sänks summan troligen därför att en del av det som hålls kvar är regn som i A1 hade flyttats in över mätarna högre upp. Det har jag inte hunnit kontrollera. Domen mot A1 är densamma på träningen och valideringen, så valet (ingen variant) står sig. Valideringen är nu sedd för A1L1; ett senare val mellan A1 och A1L1 ska därför göras på fler träningsdagar och bedömas på testdelen, inte på valideringen igen.

## Körningen

- Diagnosen: cirka 80 s per dag.
- Valideringen av A1L1: 16 dagar med en process på 50 min (3,4 min per dag).
- Varianterna: varje variant kostar cirka 2,3 min per dag med en process (förflyttningarna räknas en gång per rörelsefält och delas), plus cirka 1 min för att läsa bilderna och räkna A0. Med två processer och fyra varianter blev det 18 min per dag.
- **Två processer dog av minnet (kod 137).** Driftens process tar själv cirka 0,9 GB, och varje process med fyra varianter tog cirka 1,2 GB. Därefter körde jag bara en process åt gången, så att minnesbristen inte kunde drabba driften. Det är skälet till att träningen bara hann 5 dagar. Inget i driften påverkades såvitt jag kan se (driftens process fanns kvar under hela körningen).
- Ny data: summorna per dag (några kB per dag och variant) och två provfält i `/data/analys/lovart/` (cirka 30 MB). `/data/analys` är under 1 GB.
- `uv run pytest`: 166 godkända.

## A2 och filtret

A2 (uppgift 3) och filtret F4 (uppgift 4) slutade båda som klara. A2 räknas på A1:s fält och skulle bara ha körts om med rättningen om en variant hade valts. Eftersom ingen valdes kördes de inte om; det hade dessutom inte hunnits (A1-fälten för valideringen tar cirka 4 min per dag och variant). F4 verkar på A0 och berörs inte av A1:s interpolering.

## Ändrade filer

- `src/knep/analys/a1.py`: `paths`, `interpolate`, `stay_fraction` och valet `stay` i `interval_mean` (standard av, oförändrat resultat).
- `tests/test_a1.py`: tre nya tester (standard av är bit för bit som förut och en stillastående topp smetas ut utan valet men inte med; en cell som flyttar sig långt påverkas nästan inte och NaN är som förut; lyftet räknas bara uppför).
- `experiments/analys/lovart.py` (ny): `diag`, `kor`, `jamfor` och `valj`.
- Den här rapporten.

## Nästa steg

1. **Domaren och summakvoten på lovartsidan.** Underskottet är ingen förlust av regn utan en utjämning av toppar, och vid de mätare som bidrar mest ligger A1 närmare mätaren. Summakvoten belönar för höga toppar så länge radarn i stort är för torr. Ett mått för mängden som inte belönar det (till exempel kvoten bara för perioder där mätaren har regn, eller kvoten efter A2:s rättning i stor skala) bör beslutas för sig, och baslinjerna köras om. Det föreslogs redan i uppgift 5.
2. **Träningen på alla 28 dagar** med en process (cirka 3,5 min per dag och variant), så att valet inte vilar på 5 dagar. `lovart.py kor A1 A1M A1L1 --del traning` hoppar över de dagar som redan finns. Därefter avgör testdelen mellan A1 och A1L1, efter beslut av användaren.
3. **Ett snävare val**: stå stilla bara där regnet faktiskt står stilla, mätt på samma sätt som diagnosen (korrelationen på plats mot längs rörelsen över senaste kvarten), i stället för ur lyftet eller överallt. Diagnosen visar att det bara gäller 21 till 29 % av fallen på lovartsidan, så både A1M och A1L1 håller sannolikt kvar för mycket.
4. Om en variant väljs: koppla valet till `cli.py` (terrängen på radarns rutnät behövs för lyftet) och kör om A2 på dess fält.

Varför delvis: orsaken är funnen och rättningen finns som ett val med tester, men ingen variant blev godkänd mot A1, träningen hann bara 5 av 28 dagar, och A2 kördes inte om.

Status: delvis
