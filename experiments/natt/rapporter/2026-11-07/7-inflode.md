# 7 Inflödet utan överskott tidigt (Inflode25 med en platskarta som inte förstärker toppen)

Fortsättning på nästa steg 2 i `2026-11-04/6-sammanfattning.md`. `Inflode25` (`Chain(inflow=25 km / upplösningen)`) fälldes på valideringen bara av att ytan ≥ 10 och 20 mm/h blev cirka 0,02 för stor vid 15 och 30 min, där kedjans platskarta redan överskattar. Uppgiften var att göra en variant där platskartan inte förstärker de högsta intensiteterna, välja på träningsdagarna, frysa och bedöma på valideringen mot kedjan. Inflödet fylls bara från randvärdet (som i `Inflode25`); ingen vädermodell används. Testdagarna lästes inte och kördes inte.

## Vad jag gjorde

Två nya val i `model.Chain`, båda av som standard (driftens kedja är oförändrad, testat):

- `loc_top` (mm/h): en positiv korrektion ur platskartan lyfter en ruta högst till `max(m, loc_top)`, där `m` är den matchade bilden. Rutor över `loc_top` förstärks alltså inte, men kan fortfarande dämpas av en negativ korrektion, och svagt regn korrigeras som förut.
- `loc_rematch`: de korrigerade rutorna över 1 mm/h klipps rangvis mot matchningens mål (ingen ruta blir högre än målets värde med samma rang). Platskartan får då flytta och dämpa toppen men inte göra den högre än målet.

Logiken ligger i den nya metoden `Chain.located(m, db, tgt)`, som `run` nu anropar i stället för `m * 10 ** (db / 10)`; med båda valen av ger den exakt det gamla uttrycket.

Varianterna (i `experiments/projektion/konservering.py`, alla med inflödet 25 km):

| variant | val |
|---|---|
| `Inflode25Topp10` | `loc_top=10` |
| `Inflode25Topp5` | `loc_top=5` (avbruten, se nedan) |
| `Inflode25Rang` | `loc_rematch=True` |

## Valet på träningsdagarna (läget `snabb`, 6 dygn, 4 km, 48 utgåvor, mot `kedja_om`)

Hela tabellen: `/data/analys/7-snabb.md` (gjord med det nya `experiments/projektion/inflode_topp.py`, som skriver till en egen fil i stället för att skriva över `resultat/snabb.md`). Skillnad mot kedjan, negativt är bättre, 95 %-intervall ur 1000 bootstrapdragningar; `*` helt på den bättre sidan, `!` helt på den sämre.

| system | yta ≥ 10, 15 min | yta ≥ 10, 30 min | yta ≥ 20, 15 min | q99,9, 15 min | volym, 5 h | CSI 5, 30 min | SEDI 10, 15 min | dom |
|---|---|---|---|---|---|---|---|---|
| `Inflode25` | +0,036 (+0,005, +0,084) | +0,068 (−0,062, +0,118) | +0,073 (−0,085, +0,139) | +0,071 (−0,065, +0,128) | −0,051 (−0,095, +0,004) | −0,015 (−0,037, −0,001)* | −0,007 (−0,019, −0,000)* | inte bättre, inga sämre celler |
| `Inflode25Topp10` | −0,003 (−0,040, +0,048) | −0,011 (−0,093, +0,047) | −0,049 (−0,125, +0,078) | −0,000 (−0,066, +0,085) | −0,038 (−0,075, −0,006) | −0,014 (−0,036, −0,001)* | −0,004 (−0,017, +0,004) | inte bättre, inga sämre celler |
| `Inflode25Rang` | −0,000 (−0,040, +0,055) | −0,015 (−0,109, +0,071) | −0,008 (−0,097, +0,072) | +0,010 (−0,060, +0,107) | −0,033 (−0,071, +0,002) | −0,015 (−0,037, +0,001) | −0,004 (−0,017, +0,005) | inte bättre, **blockmax q90 sämre** vid 30 min, 2 h och 3 h |

Log kvoten själv för ytan ≥ 10 mm/h vid 15 min: kedjan +0,07, `Inflode25` +0,11, `Topp10` +0,07, `Rang` +0,07. Klippningen tar alltså bort precis det överskott som inflödet lade till, och ytan ≥ 20 mm/h går från +0,16 till +0,04. CSI 1 mm/h (spärren) är säkert bättre än kedjan på alla ledtider för alla tre. På 6 dygn är inga konserveringsceller säkert bättre för någon av dem, så domen på träningsdagarna är "inte bättre" även för `Inflode25`; valet gjordes därför på att inga celler är sämre och att de tidiga ytorna kommer ned till kedjans nivå.

**Valt och fryst: `Inflode25Topp10`** (`Chain(inflow=25 km / upplösningen, loc_top=10.0)`). `Rang` fälls av blockmaxet. `Topp5` avbröts efter `Rang` för att valideringen skulle hinna köras inom uppgiftens tid; den bedömdes alltså inte. Valet gjordes innan något av valideringen lästes.

## Valideringen (läget `validering_gles`, 2 km, mot `kedja`)

**Bara 7 av 16 valideringsdygn hann köras** (cirka 6,5 min per dygn och process, två processer; hela valideringen tar cirka 55 min och ryms inte i uppgiftens 58 min tillsammans med sökningen). Ordningen bestämdes innan körningen: först de 7 dygnen från maj till början av oktober, eftersom det är där ytorna ≥ 10 och 20 mm/h finns och där `Inflode25` fälldes, sedan resten. Körda: 2024-07-13, 2021-05-17, 2023-08-08, 2025-07-29, 2020-05-10, 2024-06-28, 2021-10-05. De övriga 9 (vinter, vår och sen höst) är inte körda, och domen nedan gäller bara de 7 dygnen. `Inflode25` och `kedja` bedömdes på samma 7 dygn ur de sparade summorna från 2026-11-04. Hela tabellen: `/data/analys/7-validering.md`.

Skillnad mot `kedja`, negativt är bättre, 95 %-intervall (1000 dragningar över de 7 dygnen):

| mått | ledtid | `Inflode25` | `Inflode25Topp10` |
|---|---|---|---|
| yta ≥ 10 mm/h | 15 min | +0,016 (+0,006, +0,024) | **−0,035 (−0,060, −0,020)*** |
| yta ≥ 10 mm/h | 30 min | +0,037 (+0,012, +0,049)! | −0,062 (−0,116, +0,019) |
| yta ≥ 20 mm/h | 30 min | +0,041 (+0,001, +0,060) | −0,146 (−0,362, +0,149) |
| q99,9 | 15 min | +0,012 (−0,000, +0,056) | −0,059 (−0,086, +0,043) |
| yta ≥ 5 mm/h | 3 h | −0,064 (−0,088, −0,023)* | −0,061 (−0,086, −0,018)* |
| volym | 2 h | −0,050 (−0,076, −0,019)* | −0,029 (−0,055, −0,002) |
| volym | 5 h | −0,083 (−0,134, −0,028)* | −0,076 (−0,130, −0,020)* |
| **blockmax q90** | 30 min | +0,000 (−0,003, +0,023) | **+0,067 (+0,014, +0,097)!** |
| **blockmax q90** | 1 h | +0,001 (−0,003, +0,003) | **+0,054 (+0,013, +0,089)!** |
| **blockmax q90** | 2 h | +0,001 (−0,002, +0,024) | **+0,067 (+0,018, +0,094)!** |
| CSI 5 mm/h | 15 min | −0,005 (−0,008, −0,002)* | −0,005 (−0,008, −0,001)* |
| CSI 1 mm/h | 2 h | −0,009 (−0,014, −0,003)* | −0,009 (−0,014, −0,003)* |
| FSS 1 mm/h 30 km | 2 h | −0,011 (−0,014, −0,004)* | −0,011 (−0,014, −0,004)* |
| form 4 till 8 km | 1 h | +0,001 (+0,000, +0,001) | +0,005 (+0,003, +0,006) |
| hopp | 1 h | −0,011 (−0,019, −0,004)* | −0,024 (−0,033, −0,011)* |

Log kvoten för blockmaxets 90-percentil: kedjan −0,11 vid 30 min, `Topp10` −0,16, och vid 2 h −0,11 mot −0,18.

**Domen: inte bättre.** `Inflode25Topp10` gör det den skulle: överskottet i ytan ≥ 10 mm/h vid 15 och 30 min är borta (vid 15 min nu säkert bättre än kedjan), inflödets vinster i volym och yta ≥ 5 mm/h efter 2 till 3 h är kvar, liksom de bättre spärrarna (CSI, FSS 1 mm/h, hoppen). Men klippningen tar bort toppen också där den behövs: blockmaxets 90-percentil, som kedjan redan underskattar, blir säkert sämre vid 30 min, 1 h och 2 h (+0,05 till +0,07). Den cellen fälls inte i `Inflode25`. Formen 4 till 8 km blir något sämre (+0,005) men under domens gräns 0,01. Slutsatsen är att platskartans överskott i ytan inte sitter i enstaka toppar som kan klippas bort utan i att den lyfter hela kärnor; en klippning vid 10 mm/h sänker även kärnornas max, som kedjan behöver.

På träningsdagarna (4 km, 6 dygn) syntes inte blockmaxets försämring för `Topp10`, bara för `Rang`. Skillnaden beror sannolikt på upplösningen: på 4 km slätas blockmaxet ut och klippningen märks mindre. Urvalet bör därför göras på 2 km för mått som rör toppen.

## Körtiden

Per utgåva på Pi:n (2 km, hela Sveriges rutnät, 60 steg till 5 h, två processer samtidigt och driften bredvid), ur domarens tider på de 7 valideringsdygnen:

| system | prognosen per utgåva | hela utgåvan i domaren (med uppvärmningen av platskartan) |
|---|---|---|
| `kedja` | (läses ur driftens sparade prognoser, 0,6 s) | 4,9 s |
| `Inflode25` | 19,1 s | 54 s |
| `Inflode25Topp10` | 16,9 s | 49 s |

Klippningen kostar inget mätbart (skillnaden mot `Inflode25` är brus från konkurrensen om processorn). Kedjans del ryms väl inom två minuter per cykel. På träningsdagarna (4 km) tog varje variant 5,6 min för 48 utgåvor med två processer.

## Filer

- `src/knep/prognos/model.py`: valen `loc_top` och `loc_rematch` och metoden `Chain.located`; standardvärdena ger driftens kedja.
- `tests/test_smoke.py`: `test_location_top_options` (av ger det gamla uttrycket, klippningen och den rangvisa klippningen).
- `experiments/projektion/konservering.py`: varianterna `Inflode25Topp5`, `Inflode25Topp10`, `Inflode25Rang`.
- `experiments/projektion/inflode_topp.py` (ny): domarens tabell till en egen fil, valfritt begränsad till körda dygn.
- Data: `/data/projektion/domare/snabb/konservering_Inflode25Topp10`, `..._Inflode25Rang`, `/data/projektion/domare/validering_gles/konservering_Inflode25Topp10`, tabellerna `/data/analys/7-*.md` (några MB).

## Nästa steg

1. Klippa ytan i stället för toppen: begränsa platskartans positiva korrektion där den ökar antalet rutor över 10 mm/h men låta den lyfta kärnans max (till exempel klippning bara utanför lokala maxima, eller `loc_top` relativt det lokala maxet i ett 8 km-block i stället för en fast nivå). Alternativt halvera platskartans positiva del de första 30 min, eftersom överskottet bara finns där.
2. `Inflode25Topp5` och `Inflode25Rang` är inte bedömda på valideringen; `Rang` fälldes redan på träningsdagarna av blockmaxet, så `Topp5` (som klipper mer) väntas bli sämre i blockmaxet än `Topp10` och är inte värd att köra.
3. Köra urvalet för toppmått på 2 km (ett läge `snabb2` med 6 träningsdygn på 2 km, cirka 20 min per variant), eftersom 4 km inte visade blockmaxets försämring.
4. De 9 valideringsdygn som inte hann köras för `Topp10` (domaren hoppar över klara dygn, så samma kommando fortsätter): `uv run python experiments/projektion/domare.py kör --läge validering_gles --system konservering:Inflode25Topp10 --procs 2`. Med den här domen är det bara värt det om nästa variant ska jämföras med `Topp10` på alla dygn.
5. Fyllning från OPERA i stället för randvärdet (andra observationer, ingen vädermodell) står kvar från sammanfattningen.

Driften ändras inte: valen `loc_top` och `loc_rematch` är av som standard och ger exakt driftens kedja (testat). `uv run pytest` gick igenom före commiten.

Varianten är gjord, vald på träningsdagarna, fryst och bedömd, men bara på 7 av 16 valideringsdygn, och den slår inte kedjan (blockmaxet sämre). Topp5 kördes inte färdigt.

Status: delvis
