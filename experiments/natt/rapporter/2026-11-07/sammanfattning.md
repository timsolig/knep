# Sammanfattning av natten 2026-11-07 (uppgift 6 och 7)

Kvällens del (domaren, A1 och A2 mot A0, filtret F4 och kommandona för testdelen för dem) står i [../2026-11-06/sammanfattning.md](../2026-11-06/sammanfattning.md) och dess fullständiga version `../2026-11-06/5-sammanfattning.md`. Den här filen gäller bara natten 2026-11-07: uppgift 6 ([6-lovart.md](6-lovart.md)) och uppgift 7 ([7-inflode.md](7-inflode.md)). Båda slutade som **delvis**. Testdelen lästes inte och kördes inte av någon uppgift.

## Kort

- **Uppgift 6 (A1:s underskott på lovartsidan):** underskottet är ingen förlust av regn utan en utjämning av toppar i regn som rör sig fort, och det finns inte på träningsdagarna (15 av 28). Tre varianter av valet `stay` i A1 prövades (A1M, A1L1, A1S). **Ingen klarade regeln mot A1**, så ingen frystes och A1 står kvar som i drift.
- **Uppgift 7 (inflödet utan överskott tidigt):** `Inflode25Topp10` (platskartan lyfter inte en ruta över 10 mm/h) valdes på träningsdagarna och bedömdes på 7 av 16 valideringsdygn. Överskottet i ytan ≥ 10 mm/h är borta, men **blockmaxets 90-percentil blir säkert sämre** vid 30 min, 1 h och 2 h. Domen: inte bättre än kedjan.
- **Rekommendationen:** driften ändras inte. Valen `stay` (A1), `loc_top` och `loc_rematch` (kedjan) finns i koden med standard av och ger bit för bit samma resultat som förut (testat).

## Uppgift 6: A1 på lovartsidan

### Diagnosen (två valideringsdagar, bara för att förstå felet)

| | 2023-08-08 | 2021-10-20 |
|---|---|---|
| massan i lovartmasken, A1/A0 | 0,999 | 1,002 |
| vid lovartmätarna efter Gauss 4 km, A1/A0 | 0,996 | 1,003 |
| A1/A0 där A0 > 3 mm per timme | 0,88 | 0,87 |
| A1/A0 vid fart 2 till 4 px per 5 min | 0,94 | 0,90 |
| andel fall där regnet står stilla bättre än det rör sig | 0,29 | 0,21 |

Inget regn flyttas bort från sluttningen; A1 sänker smala toppar där regnet rör sig fort. Underskottet kommer från några få mätare där A0 redan ligger över mätaren (2021-10-20: 5,5 av 7,2 mm från station 74180, A0 26,5, A1 21,0, mätaren 9,9 mm). Summakvoten belönar då A0, eftersom radarn i stort är för torr på lovartsidan.

### Träningen, 15 dagar (försök 2, det som gäller)

Skillnad i godhet, 95 %-intervall ur bootstrap över dagarna; fet stil när intervallet är helt på ena sidan.

| mått | A1 − A0 | A1S − A1 | A1L1 − A1 | A1L1 − A0 |
|---|---|---|---|---|
| timme lovart, kvot summa (A0 0,733, A1 0,731) | −0,004 (−0,015 till +0,007) | +0,001 (−0,000 till +0,002) | **+0,031 (+0,017 till +0,049)** | **+0,027 (+0,012 till +0,047)** |
| kvart lovart, kvot summa | +0,005 (−0,004 till +0,016) | −0,000 | **+0,025 (+0,010 till +0,043)** | **+0,030 (+0,014 till +0,051)** |
| timme över 400 m, kvot summa | −0,002 (−0,090 till +0,062) | +0,002 (−0,004 till +0,012) | **−0,034 (−0,058 till −0,012)** | −0,036 (−0,126 till +0,021) |
| timme över 400 m, kvot över 1 mm | | **−0,003 (−0,008 till −0,000)** | **sämre** | |
| timme över 400 m, FSS 0,5 | | **−0,0002 (−0,0005 till −0,0000)** | **sämre** | |
| kvart alla, CSI 0,5 | **+0,012** | −0,000 | **−0,004** | **+0,007** |
| timme alla, CSI 0,5 | **+0,008** | +0,000 | **−0,003** | +0,005 (−0,001 till +0,011) |
| kartmåttet (A0 54,2, A1 57,0 rutor per dag) | −2,8 (−6,8 till +1,1) | **+2,3 (+0,7 till +4,2)** | **+2,5 (+0,4 till +5,1)** | −0,3 |

Domen på träningen: A1 är bättre än A0 utan sämre mått och har inget underskott på lovartsidan. A1S gör nästan ingenting. A1L1 höjer kvoten på lovartsidan men är sämre än A1 över 400 m, i MAE på lovartsidan och i falska ekon per kvart. **Ingen variant valdes.** (Försök 1 på 5 dagar gav samma dom; A1M var sämre än A1 i sex mått och kördes inte vidare.)

### Valideringen, 16 dagar (bara A1L1, som information från försök 1)

| mått | A1 − A0 | A1L1 − A0 | A1L1 − A1 |
|---|---|---|---|
| timme lovart, kvot summa (A0 0,671, A1 0,653, A1L1 0,677) | **−0,028 (−0,051 till −0,006)** | +0,009 (−0,005 till +0,026) | **+0,037 (+0,024 till +0,049)** |
| kvart lovart, kvot summa (0,604, 0,592, 0,613) | **−0,020 (−0,039 till −0,001)** | **+0,016 (+0,002 till +0,033)** | **+0,035 (+0,022 till +0,048)** |
| timme över 400 m, kvot summa (0,524, 0,505, 0,494) | −0,036 (−0,154 till +0,042) | −0,059 (−0,193 till +0,017) | **−0,022 (−0,042 till −0,005)** |
| kvart alla, CSI 0,5 (0,287, 0,303, 0,301) | **+0,015** | **+0,013 (+0,007 till +0,021)** | −0,002 (−0,005 till +0,001) |
| kvart alla, CSI 1 (0,179, 0,196, 0,189) | **+0,017** | **+0,011 (+0,000 till +0,020)** | **−0,006 (−0,009 till −0,003)** |
| timme alla, MAE | **+0,005** | **+0,003** | **−0,002** |
| kartmåttet (36,6, 40,4, 37,2 rutor per dag) | −3,9 (−9,5 till +1,0) | −0,7 (−5,9 till +3,8) | **+3,2 (+1,1 till +5,9)** |

A1L1 är bättre än A0 utan sämre mått (det är A1 inte på valideringen), men inte bättre än A1: sämre över 400 m och i falska ekon per kvart på lovartsidan. Valideringen är nu sedd för A1L1, så ett senare val mellan A1 och A1L1 ska göras på fler träningsdagar och bedömas på testdelen.

Tabellerna: `/data/analys/domare/tabell_{A1,A1S,A1L1}_mot_{A0,A1}_traning.json` och `tabell_A1L1_mot_{A0,A1}_validering.json`.

## Uppgift 7: Inflode25 med en platskarta som inte förstärker toppen

### Valet på träningsdagarna (läget `snabb`, 6 dygn, 4 km, mot `kedja_om`)

Skillnad mot kedjan, negativt är bättre; `*` helt på den bättre sidan.

| system | yta ≥ 10, 15 min | yta ≥ 20, 15 min | volym, 5 h | CSI 5, 30 min | dom |
|---|---|---|---|---|---|
| `Inflode25` | +0,036 (+0,005, +0,084) | +0,073 (−0,085, +0,139) | −0,051 (−0,095, +0,004) | −0,015 (−0,037, −0,001)* | inte bättre, inga sämre celler |
| `Inflode25Topp10` | −0,003 (−0,040, +0,048) | −0,049 (−0,125, +0,078) | −0,038 (−0,075, −0,006) | −0,014 (−0,036, −0,001)* | inte bättre, inga sämre celler |
| `Inflode25Rang` | −0,000 (−0,040, +0,055) | −0,008 (−0,097, +0,072) | −0,033 (−0,071, +0,002) | −0,015 (−0,037, +0,001) | blockmax q90 sämre |

`Inflode25Topp10` frystes. `Inflode25Topp5` avbröts och är inte bedömd.

### Valideringen (läget `validering_gles`, 2 km, 7 av 16 dygn, maj till oktober, mot `kedja`)

| mått | ledtid | `Inflode25` | `Inflode25Topp10` |
|---|---|---|---|
| yta ≥ 10 mm/h | 15 min | +0,016 (+0,006, +0,024) | **−0,035 (−0,060, −0,020)*** |
| yta ≥ 10 mm/h | 30 min | +0,037 (+0,012, +0,049)! | −0,062 (−0,116, +0,019) |
| yta ≥ 5 mm/h | 3 h | −0,064 (−0,088, −0,023)* | −0,061 (−0,086, −0,018)* |
| volym | 5 h | −0,083 (−0,134, −0,028)* | −0,076 (−0,130, −0,020)* |
| **blockmax q90** | 30 min | +0,000 (−0,003, +0,023) | **+0,067 (+0,014, +0,097)!** |
| **blockmax q90** | 1 h | +0,001 (−0,003, +0,003) | **+0,054 (+0,013, +0,089)!** |
| **blockmax q90** | 2 h | +0,001 (−0,002, +0,024) | **+0,067 (+0,018, +0,094)!** |
| CSI 1 mm/h | 2 h | −0,009 (−0,014, −0,003)* | −0,009 (−0,014, −0,003)* |
| FSS 1 mm/h 30 km | 2 h | −0,011 (−0,014, −0,004)* | −0,011 (−0,014, −0,004)* |
| hopp | 1 h | −0,011 (−0,019, −0,004)* | −0,024 (−0,033, −0,011)* |

Domen: **inte bättre.** Klippningen tar bort överskottet i ytan men sänker också kärnornas max, som kedjan redan underskattar. På 4 km (träningen) syntes inte blockmaxets försämring; urval för toppmått bör göras på 2 km. Domen gäller bara 7 dygn. Hela tabellerna: `/data/analys/7-snabb.md` och `/data/analys/7-validering.md`.

## Rekommendation för drift

1. **Driften går som i dag.** Inget från natten ska kopplas in.
2. **A1 står kvar utan `stay`.** Underskottet på lovartsidan finns inte på träningen och kommer från toppar i A0 som är för höga vid några mätare på två valideringsdagar. A1L1 rättar kvoten på lovartsidan men gör A1 sämre över 400 m och ger fler falska ekon; A1S gör nästan ingenting. Det betyder också att det som 2026-11-06 angav som skäl att inte låta A1 ersätta A0 (underskottet) är svagare än det såg ut: på 15 träningsdagar är A1 bättre än A0 utan sämre mått. Beslutet om A1 som start för prognosen bör ändå vänta på testdelen och på frågan om domarens summakvot (nedan).
3. **Kedjan står kvar utan `loc_top` och `loc_rematch`.** `Inflode25Topp10` är sämre i blockmaxet. Den närmaste kandidaten på prognossidan är fortfarande `Inflode25` från 2026-11-04, som inte heller är godkänd.
4. Rekommendationerna från 2026-11-06 gäller oförändrat (F4 slås på först när användaren har godkänt en modellfil och testdelen har körts; A2 är inte redo som facit).

## Körtiderna på Pi:n

| steg | tid |
|---|---|
| diagnosen på lovartsidan (`lovart.py diag`) | cirka 80 s per dag |
| A1-varianterna genom domaren (`lovart.py kor`) | cirka 2,3 till 2,5 min per dag och variant med en process, plus cirka 1 min för A0; A1 och A1S tillsammans cirka 6 min per dag och process |
| A1L1 på 16 valideringsdagar | 50 min med en process (3,4 min per dag) |
| minnet | cirka 1,2 GB per process med fyra varianter; två sådana dog av minnesbrist (kod 137) bredvid driften (cirka 0,9 GB) |
| prognosen per utgåva, 2 km, 5 h | kedjan 0,6 s (läses ur driften), `Inflode25` 19,1 s, `Inflode25Topp10` 16,9 s |
| hela utgåvan i prognosdomaren | kedjan 4,9 s, `Inflode25` 54 s, `Topp10` 49 s |
| träningen i läget `snabb` | 5,6 min per variant (48 utgåvor, två processer) |
| valideringen `validering_gles` | cirka 6,5 min per dygn och process |
| `uv run pytest` | 168 godkända på 2 min 20 s |

Disken: `/data/analys` tar 785 MB (gränsen 1 GB), och `/data` har 5,1 GB ledigt.

## Det som återstår

1. **Domarens summakvot** (från både 2026-11-06 och uppgift 6): den belönar för höga toppar vid enstaka mätare så länge radarn i stort är för torr. Ett mått som inte gör det (kvoten för perioder då mätaren har regn, eller efter A2:s rättning i stor skala) ska beslutas för sig, och baslinjerna A0, A1 och A2 köras om. Det avgör om A1:s "underskott" på valideringen alls är ett fel.
2. **De 13 träningsdagar som saknas** för A0, A1, A1S och A1L1: `uv run python experiments/analys/lovart.py kor A0 A1 A1S A1L1 --del traning` (hoppar över klara dagar, cirka 6 min per dag och process; högst en process med alla fyra varianter, för minnets skull).
3. **Prognosen: klippa ytan i stället för toppen**, till exempel `loc_top` relativt det lokala maxet i ett 8 km-block, eller halverad positiv platskorrektion de första 30 min. Urvalet för toppmått på 2 km (ett läge `snabb2`).
4. **De 9 valideringsdygn** som inte kördes för `Inflode25Topp10`: `uv run python experiments/projektion/domare.py kör --läge validering_gles --system konservering:Inflode25Topp10 --procs 2`. Bara värt det om en ny variant ska jämföras med den på alla dygn.
5. Från 2026-11-06 står kvar: satellitens molnmask (nätet var spärrat), F4 på alla 28 träningsdagar och som modellfil, filtret under A1 och A2, kontroll av mätarna i A2, ekrarna, och att rörelsen räknas var 15:e minut i domaren men var 5:e i drift.
6. Bakgrundskörningar nekades i delar av natten; uppgifterna förlorade tid på att köra i förgrunden en dag i taget.

## Kommandon för testdelen (körs inte i natt)

Det rekommenderade är driften oförändrad, så det som ska köras på testdelen är baslinjerna: A0 och A1 i analysen och kedjan i prognosen. Kommandona för A0, A1, A2 och F4 står i `../2026-11-06/5-sammanfattning.md` (avsnittet "Kommandon för testdelen") och för kedjan i `../2026-11-04/6-sammanfattning.md` (samma avsnitt). Båda kräver en liten ändring som låser upp testdelen, och den görs **bara när användaren beslutar det**:

- Analysen: i `experiments/analys/domare.py`, `days()`, lägg till `elif part == "test": return sorted(test)` före `else` och flytta `assert not test & set(out)` in i de två andra grenarna; lägg till `"test"` i `choices` för `--del` i `domare.py`.
- Prognosen: läget `test` i `LÄGEN` i `experiments/projektion/domare.py` och en villkorlig kontroll i `mode_days`, som i `2026-11-04/6-sammanfattning.md`.

Det rekommenderade, från repots rot, med högst två processer, var för sig i bakgrunden med logg och `timeout`:

    # analysen: A0 och A1 som i drift (cirka 2 h för 16 dagar med två processer)
    timeout 2h uv run python experiments/analys/domare.py kor A0 A1 --del test --bit 0/2 > logg_test_0.txt 2>&1 &
    timeout 2h uv run python experiments/analys/domare.py kor A0 A1 --del test --bit 1/2 > logg_test_1.txt 2>&1 &
    uv run python experiments/analys/domare.py tabell A1 --mot A0 --del test

    # prognosen: driftens kedja (efter läget test)
    uv run python experiments/sverige/kedja.py --part test --shard 0/2
    uv run python experiments/sverige/kedja.py --part test --shard 1/2
    uv run python experiments/projektion/domare.py kör --läge test --system kedja --procs 2

Om användaren vill bedöma natten närmaste kandidat i analysen, A1L1 mot A1 (inte rekommenderad, men valideringen är redan sedd för den), krävs också att `"test"` läggs till i `choices` för `--del` i `experiments/analys/lovart.py` (rad 278) och att assertionen i `cmd_kor` (rad 172, som bara tillåter validering och träning) tar med testdagarna:

    timeout 2h uv run python experiments/analys/lovart.py kor A1L1 --del test --bit 0/2 > logg_a1l1_0.txt 2>&1 &
    timeout 2h uv run python experiments/analys/lovart.py kor A1L1 --del test --bit 1/2 > logg_a1l1_1.txt 2>&1 &
    uv run python experiments/analys/domare.py tabell A1L1 --mot A1 --del test
    uv run python experiments/analys/domare.py tabell A1L1 --mot A0 --del test

`Inflode25Topp10` ska inte köras på testdelen; den är redan fälld på valideringen. Tabellerna hamnar i `/data/analys/domare/tabell_<system>_mot_<bas>_test.json` och `experiments/projektion/resultat/test.md`. Ingen parameter, tröskel eller variant får ändras efter att testet har körts.

Status: klar
