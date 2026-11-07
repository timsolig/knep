# Uppgift 6: A1:s underskott på lovartsidan

(utkast, fylls i under körningen)

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
4. **Underskottet sitter vid några få mätare där A0 är högre än mätaren.** 2021-10-20 kommer 5,5 av 7,2 mm från en station (74180, 173 m, Småland): A0 26,5, A1 21,0, mätaren 9,9 mm. 2023-08-08 är de tre största 180770 (A0 12,5, A1 7,1, mätaren 6,8), 123460 (9,6, 5,4, 13,3) och 180760 (22,1, 19,1, 9,7). Vid två av de tre ligger A1 närmare mätaren. MAE på lovartsidan är också bättre för A1 (+0,006, intervallet över 0, uppgift 2). Domarens summakvot belönar A0 här därför att radarn i stort är för torr på lovartsidan (kvoten 0,67): toppar som är för höga vid en mätare väger upp att andra mätare får för lite.

STATUS_UTKAST
