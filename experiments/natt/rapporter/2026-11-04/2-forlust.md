# 2 Förlusten: var extremerna försvinner i kedjan

## Vad som gjordes

`experiments/projektion/forlust.py` kör kedjan steg för steg på **alla 28 träningsdygn** (2 km, utgåvorna kl 03, 11 och 17, 84 utgåvor) och bedömer varje mellanled som ett eget system med domarens summor (`domare.Acc`) mot radarns kvartsmedel, på domarens rutor, vid 15 och 30 min, 1, 2, 3 och 5 h. Intervallen är 95 % ur bootstrap över dygnen (1000 dragningar). Hela tabellen finns i `experiments/projektion/resultat/forlust.md`. Valideringen och testdelen lästes inte.

Stegen:

| steg | vad det är |
|---|---|
| `persistens` | analysen oförändrad |
| `nn` | analysen flyttad med närmaste granne (kedjans mål för matchningen): värdena bevaras, bara randen och deformationen ändrar fördelningen |
| `bilinjar` | kedjans bilinjära semi-Lagrangeska flytt |
| `matchad_analys` | `bilinjar` matchad mot hela analysens fördelning (som `Chain(target="analysis")`) |
| `matchad` | `bilinjar` matchad mot `nn` (kedjans steg 3) |
| `platskarta` | `matchad` med platskartan, det vill säga kedjan som den körs (utan extremmodell) |
| `somlos` | `platskarta` blandad med MEPS rättad mot radarn (`seamless.blend` med `Params()`, som `sommodell` "sömlös") |
| `nn_inre`, `bilinjar_inre`, `matchad_inre` | samma, men bara på de rutor vars avgångspunkt låg inom täckningen vid utgåvan (inget har kommit in över randen) |

Uppdelningen: radarn mot `nn_inre` är radarns eget avtagande i lagrangeska koordinater (med kedjans rörelse, utan randen); `nn` mot `nn_inre` är det som kommer in över randen och som ingen extrapolering har; `bilinjar` mot `nn` är den numeriska utjämningen; resten är matchningen, platskartan och blandningen. Rörelsefältets deformation mäts som Jacobianen för avgångspunkterna (källyta per målruta) där `nn` ≥ 5 mm/h.

Kontroll: `experiments/projektion/forlust_kontroll.py` visar att steget `platskarta` är **identiskt** med `domare.KedjaOm` (kedjan i `model.Chain.run` med uppvärmd platskarta), största skillnad 0,0 mm/h vid 15 min, 1 h och 5 h (2023-07-12 11 UTC).

**Extremmodellen** ingår inte som steg. I drift anropas `extremes.apply` utan `rescale`, och då returneras fältet orört (`src/knep/extremes.py:179`); den ger bara sannolikheter. Dess bidrag till konserveringen av fältet är alltså 0 per konstruktion. `models/extremes.pkl` finns inte heller i utcheckningen.

## Siffrorna: stegens bidrag

Ändringen i log kvot mot radarn från föregående steg (negativt = förlust av yta eller topp). Intervall inom parentes där det behövs för slutsatsen.

### Ytan ≥ 5 mm/h

| bidrag | 15 min | 1 h | 2 h | 5 h |
|---|---|---|---|---|
| radarns eget lagrangeska avtagande | −0,01 | −0,02 (−0,08, +0,04) | +0,06 (−0,06, +0,17) | +0,12 (−0,09, +0,35) |
| in över randen | −0,02 | −0,07 (−0,11, −0,03) | −0,17 (−0,26, −0,09) | −0,30 (−0,40, −0,22) |
| bilinjär flytt | −0,02 | −0,03 | −0,03 | −0,03 |
| matchning mot nn | +0,05 | +0,05 | +0,05 | +0,05 |
| platskartan | +0,05 | +0,04 | +0,02 | +0,05 |
| MEPS-blandningen | 0,00 | −0,19 (−0,31, −0,09) | −0,22 (−0,67, +0,03) | −0,18 (−0,67, +0,08) |
| **kedjan totalt** (`platskarta`) | +0,05 | −0,03 | −0,08 | −0,11 |
| **sömlös totalt** | +0,04 | −0,21 | −0,30 | −0,29 |

### Ytan ≥ 20 mm/h

| bidrag | 15 min | 1 h | 2 h | 5 h |
|---|---|---|---|---|
| radarns eget lagrangeska avtagande | −0,11 (−0,38, +0,07) | −0,07 | +0,09 | −0,07 (−0,48, +0,54) |
| in över randen | −0,10 | −0,15 | −0,30 | −0,18 |
| bilinjär flytt | −0,12 | −0,11 | −0,13 | −0,14 |
| matchning mot nn | +0,21 | +0,20 | +0,21 | +0,22 |
| MEPS-blandningen | −0,01 | −0,63 (−0,85, −0,48) | −1,10 (−2,21, −0,63) | −0,68 |

### Volymen

| bidrag | 15 min | 1 h | 2 h | 5 h |
|---|---|---|---|---|
| radarns eget lagrangeska avtagande | −0,04 | −0,03 | −0,01 | +0,07 (−0,02, +0,18) |
| in över randen | −0,01 | −0,04 | −0,10 | −0,26 (−0,32, −0,22) |
| bilinjär flytt, matchning | 0,00 | 0,00 | 0,00 | 0,00 |
| platskartan | +0,01 | +0,01 | 0,00 | +0,01 |
| MEPS-blandningen | 0,00 | +0,05 | +0,16 | +0,32 (+0,22, +0,39) |

### 99,9-percentilen, blockmaxets 90-percentil (30 km) och formen 4 till 8 km

| bidrag | mått | 15 min | 1 h | 2 h | 5 h |
|---|---|---|---|---|---|
| bilinjär flytt | q99,9 | −0,07 | −0,07 | −0,07 | −0,07 |
| | blockmax q90 | −0,14 | −0,14 | −0,13 | −0,14 |
| | form 4–8 | −0,57 | −0,59 | −0,60 | −0,58 |
| matchning mot nn | q99,9 | +0,12 | +0,12 | +0,12 | +0,12 |
| | blockmax q90 | +0,08 | +0,08 | +0,09 | +0,09 |
| | form 4–8 | +0,06 | +0,06 | +0,06 | +0,05 |
| radarns eget avtagande (nn_inre) | blockmax q90 | −0,09 | −0,12 | −0,11 | −0,06 |
| MEPS-blandningen | q99,9 | −0,01 | −0,31 | −0,47 | −0,51 |
| | blockmax q90 | 0,00 | −0,20 | −0,53 | −0,77 |
| | form 4–8 | −0,01 | −0,50 | −1,48 | −2,54 |
| | form 8–16 | −0,01 | −0,43 | −1,05 | −1,51 |

Formen för kedjan (`platskarta`) är −0,69 vid 15 min och −0,84 vid 5 h i bandet 4 till 8 km; den sömlösa −3,39 vid 5 h, vilket stämmer med −3,6 i `form_validering.md`.

### Deformationen

Medel av Jacobianen där `nn` ≥ 5 mm/h: 1,003 vid 15 min, 1,015 vid 1 h, 1,032 vid 2 h, 1,088 vid 5 h (medel av log J +0,02 vid 5 h). Rörelsefältet drar alltså ihop de kraftiga områdena något, men det motsvarar högst cirka 2 % av ytan.

### Träffen per steg (för att se vad stegen kostar eller ger)

FSS 5 mm/h på 30 km: `nn` 0,636 vid 1 h och 0,122 vid 5 h, `bilinjar` 0,633 och 0,120, `matchad` 0,633 och 0,121, `platskarta` 0,636 och 0,124, `somlos` 0,617 och 0,218. CSI 5 mm/h vid 5 h: kedjan 0,021, sömlös 0,053. `matchad_analys` ger FSS 0,132 vid 5 h mot 0,121 för `matchad`. Blandningen med MEPS kostar alltså lite vid 1 h (−0,02 i FSS) och ger mycket efter 2 h.

## Rangordningen: var förlusten uppstår

1. **MEPS-blandningen, från 1 h.** Den största förlusten av toppar och form i den sömlösa prognosen: ytan ≥ 20 mm/h −0,63 vid 1 h och −1,1 vid 2 h, 99,9-percentilen −0,31 vid 1 h och −0,5 efter 2 h, blockmaxets 90-percentil −0,20 vid 1 h och −0,77 vid 5 h, effekten 4 till 8 km −0,5 vid 1 h och −2,5 vid 5 h. Samtidigt lägger den till volym (+0,32 vid 5 h, så att den sömlösa har +0,14 för mycket) och ger träffen efter 2 h. Det är alltså inte kedjans projektion som tappar formen efter 1 h, utan blandningen: det blandade fältet är utjämnat (MEPS små skalor och vikten 1 − ws för de små skalorna) och matchningen mot den viktade fördelningen tar inte tillbaka strukturen. Kvantilerna blandas också mot MEPS, vars topp är lägre. Detta är förlust av toppar, inte av yta: ytan ≥ 1 mm/h och volymen ökar.
2. **Regn som kommer in över randen, växer med ledtiden.** Ytan ≥ 5 mm/h −0,07 vid 1 h, −0,17 vid 2 h, −0,30 vid 5 h; volymen −0,04, −0,10, −0,26; antalet våta block om 30 km −0,24 vid 5 h. Det är hela kedjans förlust av volym och yta (resten av stegen summerar till nära 0 eller plus). I kedjan syns samma sak som att matchningens mål saknar det som lämnat området: mot hela analysens fördelning (`matchad_analys`) blir ytan ≥ 5 mm/h −0,01 vid 5 h i stället för −0,16, och volymen −0,06 i stället för −0,19, med något bättre FSS 5 mm/h (+0,01) vid 5 h. Det som lämnar området ersätter alltså ungefär hälften av det som kommer in, men rumsligt fel.
3. **Den bilinjära flytten, konstant från 15 min.** Effekten 4 till 8 km −0,58, blockmaxets 90-percentil −0,14, ytan ≥ 20 mm/h −0,12, 99,9-percentilen −0,07. Den beror inte på ledtiden, eftersom schemat interpolerar ursprungsfältet en gång per steg (ingen ackumulering). Matchningen tar tillbaka percentilerna och ytan (och lite mer: +0,12 för q99,9, +0,21 för ytan ≥ 20) men bara 10 % av formen (+0,06) och 60 % av blockmaxet (+0,08), eftersom rangordningen kommer från det utsmetade fältet: topparna hamnar på för många rutor med något lägre värde i stället för på få med det rätta.
4. **Utjämning inom kvarten och lägesfel, konstant.** Även `nn`, som bevarar värdena, ligger 0,09 till 0,12 under radarn i blockmaxets 90-percentil från 15 min och −0,18 i formen 4 till 8 km. Det ökar inte med ledtiden, så det är inte ett avtagande. Det troliga är att kvartsmedlet av tre flyttade bilder smetar ut topparna mer än radarns eget kvartsmedel gör (där cellerna utvecklas på plats), och närmaste granne som duplicerar rutor. Persistensen (en enda bild, inget medel) ligger i stället 0,27 över radarn.
5. **Radarns eget lagrangeska avtagande: inte mätbart.** På de inre rutorna är ytan ≥ 5 mm/h hos radarn mot den flyttade analysen −0,02 vid 1 h och +0,12 vid 5 h, ytan ≥ 20 mm/h −0,07 vid 1 h och 5 h, och volymen ±0,03 till 2 h, alla med intervall som täcker 0. Radarns extremer avtar alltså inte i genomsnitt i lagrangeska koordinater på träningsdygnen; cellerna som dör ersätts av nya. Det betyder att en projektion som håller ytan och topparna konstanta i lagrangeska koordinater inte blåser upp något i medel, men den vet inte var de nya cellerna kommer.
6. **Deformationen av rörelsefältet: liten.** Högst cirka 2 % av ytan vid 5 h.
7. **Platskartan** lägger till (+0,05 i ytan ≥ 5 mm/h, +0,01 i volym) och **extremmodellen** ändrar inte fältet.

## Vad nästa uppgift kan bygga på

- Det som har störst effekt på extremerna efter 1 h är blandningen med MEPS. Två billiga ändringar att pröva på träningsdagarna: (a) matcha det blandade fältet mot kedjans fördelning (eller en fördelning där topparna följer kedjan och mängden MEPS) i stället för den viktade, (b) lägga tillbaka kedjans små skalor ovanpå det blandade fältet, eller välja vikten per skala så att formen hålls. Spärren är FSS och CSI efter 2 h, där MEPS ger mest.
- Inflödet över randen: kedjan har inget att sätta där. Matchning mot hela analysens fördelning (`target="analysis"`, finns redan som val) kompenserar halva volym- och ytförlusten på 5 h utan att FSS blir sämre på träningsdagarna; det bör bedömas av domaren på valideringen. Bättre vore att fylla randen med MEPS eller OPERA där radarn saknas uppströms.
- Den bilinjära flytten: en flytt som inte interpolerar (närmaste granne med kvartsmedel, eller kubisk med klippning) eller en matchning som också återställer rumslig struktur (rangordning efter ett skärpt fält) kan ta tillbaka blockmaxet och formen 4 till 8 km. Den förlusten är konstant och redan full vid 15 min.

## Det som är svagt

- Tre utgåvor per dygn (03, 11, 17) i stället för var 3:e timme, för att hinna på natten (cirka 40 s per utgåva och process, 224 s per dygn, 50 min med 2 processer). Intervallen är breda för ytan ≥ 20 mm/h och efter 2 h.
- MEPS-rättningen assimileras en gång per utgåva (som i `sommodell`), inte var 5:e minut som i drift, och blandningen görs på kvartsmedel. Det är samma förenkling som i `experiments/sverige`.
- Stegen kodas inte genom värdefilen som i domaren; det ger cirka 1 % skillnad i medelintensitet och samma för alla steg.
- Formen (spektrum) räknades bara för `nn`, `bilinjar`, `matchad`, `platskarta` och `somlos`; för de andra står den som saknad.
- "In över randen" räknas med täckningen vid utgåvan och kedjans rörelse; där rörelsen är fel blandas lite lägesfel in i den delen.

## Filer

- `experiments/projektion/forlust.py` (ny): körningen och tabellen
- `experiments/projektion/forlust_kontroll.py` (ny): kontrollen mot kedjan
- `experiments/projektion/resultat/forlust.md` (ny): hela tabellen med intervall
- Data: `/data/projektion/forlust/` (28 filer, 3,4 MB), rörelsefälten för träningsdagarna i `/data/projektion/cache/rorelse/2km/`
- Inga ändringar i `src/knep/`. `uv run pytest`: 76 gick igenom.

Status: klar
