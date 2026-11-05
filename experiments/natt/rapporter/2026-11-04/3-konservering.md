# 3 Konserveringen: projektion och matchning

## Utgångsläget

Rapport 1 och 2 var klara (rapport 1 `delvis`, med S-PROG okörd; det behövdes inte här). Domarens baslinje `kedja` är kedjan utan MEPS-blandning, så det som kan bedömas med domaren i natt är kedjans egna steg. Ur rapport 2 är det som kedjan själv tappar:

1. **Den bilinjära flytten**: effekten 4 till 8 km −0,58, blockmaxets 90-percentil −0,14, ytan ≥ 20 mm/h −0,12, konstant från 15 min. Matchningen tar tillbaka percentilerna men inte formen.
2. **Inflödet över randen**: ytan ≥ 5 mm/h och volymen −0,26 till −0,30 vid 5 h.
3. MEPS-blandningen (den största förlusten av toppar efter 1 h) ingår inte i domarens system och prövades inte i natt; se Nästa steg.

Därför prövades flytten (interpolationen), rangordningen i matchningen och matchningsmålet.

## Vad som gjordes

Nya val i `model.Chain` (standardvärdena ger exakt driftens kedja, test i `tests/test_smoke.py`):

| val | vad |
|---|---|
| `interp="cubic"` | bikubisk flytt, klippt till [0, största värdet bland avgångspunktens 3 x 3 grannar], så att inga nya toppar uppstår |
| `interp="nearest"` | flytt med närmaste granne: analysens värden flyttas utan utjämning |
| `blend=w` | `w` gånger den valda flytten plus `1 − w` gånger den bilinjära |
| `ramp=(t0, t1)` | vikten för den valda flytten växer linjärt från 0 vid ledtiden t0 till `blend` vid t1 (minuter); före t0 är det den bilinjära flytten |
| `sharpen=s` | matchningen rangordnar efter `f + s (f − G₁,₅ f)` i stället för `f` (värdena kommer fortfarande ur målet) |

Matchningsmålet hela analysens fördelning (`target="analysis"`) fanns redan.

`experiments/projektion/konservering.py` har varianterna som system för domaren. De värms upp som `kedja_om`, men 30-minutersprognosen i platskartans tillstånd görs med variantens egen flytt och matchning, som den skulle göras i drift. Kontroll: `konservering:Referens` (inga val ändrade) ger **exakt** samma summor som `kedja_om` (`kons_kontroll.py`, största relativa skillnad 0,0 på 2023-07-12).

Urvalet gjordes i läget `snabb` (6 träningsdagar, 4 km, 48 utgåvor, cirka 5 min per variant med 2 processer), mot `kedja_om`. Valideringen (`validering_gles`, 16 dygn, 125 utgåvor, 2 km) bedömer finalisten mot `kedja`. Testdelen lästes inte.

## Sökningen på träningsdagarna (snabb)

Hela tabellen med alla mått finns i `experiments/projektion/resultat/konservering_snabb.md`. Skillnaden mot kedjan, negativt är bättre (|log kvot| för kons och form, poängen omvänd för FSS och CSI); `*` intervallet helt på den bättre sidan, `!` helt på den sämre.

| variant | q99,9 5 h | blockmax q90 1 h / 5 h | form 4–8 km 1 h / 5 h | FSS 5 mm/h 30 km 2 h / 5 h | CSI 5 mm/h 15 min / 2 h | CSI 1 mm/h 15 min | hopp 1 h | domen |
|---|---|---|---|---|---|---|---|---|
| `Bikubisk` | −0,015 | −0,004 / −0,005 | −0,53* / −0,48* | −0,005* / −0,001 | +0,009! / +0,001 | +0,007! | −0,001 | inte bättre (CSI, SEDI) |
| `Narmast` | −0,060 | −0,039 / −0,011 | −1,17* / −1,14* | −0,004 / −0,004* | +0,016! / +0,002! | +0,011! | −0,012* | inte bättre (CSI, SEDI) |
| `Bikubisk05` (halva) | −0,006 | −0,003 / −0,004 | −0,25* / −0,23* | −0,002* / −0,001 | +0,003! / +0,001 | +0,002! | 0,000 | inte bättre (CSI) |
| `Narmast05` | −0,011 | −0,031 / −0,014 | −0,51* / −0,49* | −0,002* / −0,002* | +0,006! / +0,001! | +0,003! | −0,004* | inte bättre (CSI) |
| `Narmast025` | −0,003 | −0,004 / −0,008 | −0,23* / −0,21* | −0,001* / −0,001 | +0,002! / 0,000 | +0,001! | −0,002* | inte bättre (CSI) |
| `Skarp1` | −0,082 | −0,001 / +0,001 | −0,86* / −0,86* | −0,009* / +0,003 | +0,043! / +0,008! | +0,047! | +0,022! | inte bättre (CSI, FSS 10 km, volym, hopp) |
| `Analys` | +0,050 | −0,003 / −0,007 | −0,01 / −0,08 | +0,012 / −0,002 | 0,000 / +0,003! | 0,000 | +0,004 | inte bättre (FSS, CSI, SEDI efter 1 h) |
| `BikubiskAnalys` | +0,005 | −0,008 / −0,017 | −0,55* / −0,59* | +0,007 / −0,004 | +0,009! / +0,004! | +0,007! | +0,003 | inte bättre |
| `NarmastRamp` (60→180 min) | −0,056 | 0 / −0,019 | 0 / −1,14* | −0,001 / −0,003* | 0 / +0,001! | 0 | −0,003* | inte bättre (CSI, SEDI vid 2 och 3 h) |
| **`NarmastRamp3`** (180→240 min) | −0,056 | 0 / −0,019 | 0 / −1,14* | 0 / −0,003* | 0 / 0 | 0 | −0,003* | inte bättre (ingen sämre cell, men ingen konservering säkert bättre på 6 dygn) |

(Skarp2, Skarp05, BikubiskSkarp1, BikubiskRamp och NarmastRamp2 avbröts, eftersom Skarp1 och Narmast05 redan visade riktningen.)

Det sökningen visar:

- **Den skarpa flytten tar tillbaka formen och topparna, men kostar CSI på pixelnivå de första timmarna.** Närmaste granne ger effekten 4 till 8 km −0,15 i stället för −1,32 vid 1 h (nästan radarns), 99,9-percentilen och blockmaxet något närmare radarn, FSS 5 och 10 mm/h något bättre på alla ledtider och mindre hopp mellan utgåvorna. Men CSI 5 mm/h blir 0,016 sämre vid 15 min och 0,002 vid 2 h, och CSI 1 mm/h (spärren) 0,011 sämre vid 15 min. Det är den dubbla straffningen: ett skarpt fält med lite lägesfel träffar färre rutor exakt än ett slätt fält, även när grannskapsmåtten (FSS) blir bättre. Kostnaden går mot 0 med ledtiden och är borta vid 5 h. Den bikubiska ligger mellan: hälften av formvinsten, ungefär hälften av CSI-kostnaden. Blandningen med den bilinjära skalar både vinsten och kostnaden ungefär linjärt (`Narmast05`, `Narmast025`), så det finns ingen vikt där CSI-kostnaden försvinner medan formen blir bättre. Vid samma formvinst kostar närmaste granne mindre CSI än den bikubiska (`Narmast05` mot `Bikubisk`).
- **Den skärpta rangordningen** (`Skarp1`) ger rätt form och percentiler men mycket sämre CSI (−0,04 vid 15 min), sämre FSS på 10 km de första timmarna, för liten yta ≥ 5 mm/h vid 5 h och större hopp. Den flyttar toppvärden till rutor där skärpningen säger att de borde vara, och det är oftast fel ruta.
- **Matchningen mot hela analysens fördelning** (`Analys`) tar tillbaka hälften av volymen och ytan ≥ 5 mm/h vid 5 h (−0,12 och −0,09 i |log kvot|), men ytan ≥ 10 mm/h blir för stor (+0,05 till +0,08 efter 2 h) och FSS, CSI och SEDI blir sämre från 1 h. Regnet som har lämnat området sätts in rumsligt fel, i det regn som redan finns. På 2 km i rapport 2 såg det neutralt ut för FSS vid 5 h; här är det sämre vid 1 till 3 h. Förkastad.
- **Rampen.** Eftersom CSI-kostnaden för närmaste granne är borta efter cirka 3 h, men vinsten i form, percentil och FSS finns kvar, prövades den bilinjära flytten de första timmarna och närmaste granne längre fram. Med rampen 60 till 180 min finns en liten CSI-kostnad kvar vid 2 och 3 h (+0,001, säker); med 180 till 240 min (`NarmastRamp3`) finns ingen cell på den sämre sidan, och vid 5 h är 99,9-percentilen 0,056 närmare radarn, blockmaxet 0,02 närmare, formen 4 till 8 km −0,28 i stället för −1,42 och FSS 5 och 10 mm/h 0,003 bättre (säkert). Upp till 3 h är den identisk med kedjan, så den ändrar inte platskartans tillstånd. `NarmastRamp3` valdes som finalist.

Observera att rampen 180 till 240 min är vald så att den inte kostar något vid 3 h, som domaren visar; vid 4 h (som domaren räknar men inte tar med i domen) är vikten 1. Se valideringen nedan för 4 h.

## Valideringen

`NarmastRamp3` i `validering_gles` (16 dygn, 125 utgåvor, 2 km) mot `kedja`, 78 min med 2 processer (40,8 s per prognos med konkurrens från driften). Tabellen ligger i `experiments/projektion/resultat/konservering_validering_gles.md`.

**Domen: inte bättre.** Ingen cell är sämre på domens ledtider (15 min till 5 h), men ingen konserveringscell är heller säkert bättre. Till 3 h är prognosen identisk med kedjan (skillnaden 0,000 överallt, utom hoppen som påverkas av den tidigare utgåvans 3 till 5 h).

Skillnaden mot kedjan vid 4 och 5 h med 95 %-intervall (negativt är bättre):

| mått | kedjan, 5 h | 4 h | 5 h |
|---|---|---|---|
| \|log kvot\| q99,9 | +0,04 | +0,039 (−0,044, +0,051) | −0,042 (−0,051, +0,052) |
| \|log kvot\| blockmax median | −0,06 | −0,030 (−0,056, −0,005) | −0,050 (−0,057, +0,025) |
| \|log kvot\| blockmax q90 | −0,08 | −0,031 (−0,059, +0,037) | −0,063 (−0,068, +0,058) |
| \|log kvot\| yta ≥ 5 mm/h | −0,26 | +0,011 (+0,003, +0,025) | +0,014 (+0,005, +0,030) |
| \|log kvot\| yta ≥ 20 mm/h | −0,13 | +0,044 (−0,030, +0,102) | +0,049 (−0,068, +0,103) |
| \|log kvot\| volym | −0,30 | 0,000 | 0,000 |
| FSS 5 mm/h 10 km | 0,084 | −0,002 (−0,002, −0,001) * | −0,001 (−0,002, 0,000) |
| CSI 5 mm/h | 0,027 | +0,0003 (säkert sämre, men under 0,001) ! | 0,000 |
| FSS 1 mm/h 30 km (spärr) | 0,370 | −0,002 * | −0,003 * |
| \|log kvot\| effekt 4 till 8 km (spärr) | −1,07 | −0,498 * | −0,544 * |

Hoppen (spärren, mot utgåvan 3 h före, så att den tidigare utgåvans 3 h 15 min till 5 h ingår): −0,000 *, −0,003 * och −0,003 * vid 15 min, 1 h och 2 h.

Vad valideringen säger:

- **Formen** vid 4 och 5 h blir nästan halverad i felet (effekten 4 till 8 km −0,53 i stället för −1,07 vid 5 h), med smalt intervall, och FSS 1 mm/h blir något bättre. Hoppen mellan utgåvorna blir något mindre. Det är det säkra resultatet.
- **Topparna per block** (blockmaxets median och 90-percentil) kommer 0,03 till 0,06 närmare radarn efter 4 h, men intervallet täcker 0 vid 5 h. 99,9-percentilen är bättre vid 5 h och sämre vid 4 h, med breda intervall. Konserveringen av toppvärdena är alltså inte säkert bättre.
- **Ytan över 5 mm/h** blir något sämre (0,011 och 0,014 längre från radarn, intervallet över 0 men under domens tolerans 0,01 vid den nedre gränsen, så det räknas inte som sämre). Närmaste granne behåller topparna men tappar lite av den måttliga ytan, eftersom rutor dupliceras och tappas i deformationen i stället för att smetas ut.
- **Vid 4 h**, som domaren räknar men inte tar med i domen, är CSI 5 mm/h säkert sämre med 0,0003. Hade 4 h varit med i domen hade varianten fått "inte bättre" även av det skälet. Rampen valdes på träningsdagarna för att undvika kostnaden vid 3 h; att 4 h inte ingår i domen var inte skälet, men det ska sägas.

Slutsatsen: den skarpa flytten löser formen, men den förlust av extremer som är kvar i kedjan (ytan och volymen vid långa ledtider, −0,26 och −0,30 vid 5 h) går inte att få tillbaka med flytten eller matchningen. Den är inflödet över randen och nybildning, som rapport 2 visade, och det kedjan inte har något att sätta där.

## Ablationerna

Rampen är en ablation i sig: `NarmastRamp3` är kedjan till 3 h, och skillnaden därefter är bara flytten. Stegen i sökningen visar vad som bär vad:

- Formen och blockmaxet: flytten (`Narmast`, `Bikubisk`), inte matchningen (`Skarp1` ger formen men förstör träffen).
- Volymen och ytan vid 5 h: bara matchningsmålet (`Analys`), och det kostar träffen.
- CSI-kostnaden: skärpan på pixelnivå de första 3 h, oavsett om den kommer från flytten eller rangordningen.

## Tiderna

Prognosen tar 4,54 s per utgåva på 4 km för `NarmastRamp3` mot 4,28 s för kedjan (+6 %, delvis konkurrens med driften): blandningen kräver en extra `remap` per steg (både den bilinjära och närmaste granne räknas i alla 60 steg; det går att begränsa till stegen efter t0). Matchningen dominerar tiden. Inget nytt beroende, och cykeln på Pi:n påverkas med någon sekund.

## Filer

- `src/knep/model.py`: `Chain(interp=, blend=, ramp=, sharpen=)`, `Chain.project`, `Chain.matched`, `cdf_match(…, sharpen=)`. Standardvärdena ger driftens kedja (testat).
- `src/knep/advect.py`: `warp` tar `order=3` (bikubiskt).
- `tests/test_smoke.py`: `test_chain_projection_options`.
- `experiments/projektion/konservering.py` (ny): varianterna och körningen.
- `experiments/projektion/kons_kontroll.py` (ny): kontrollen mot `kedja_om`.
- `experiments/projektion/kons_sammanfatt.py` (ny): tabellerna `resultat/konservering_<läge>.md`.
- Data: `/data/projektion/domare/snabb/konservering_*`, `/data/projektion/domare/validering_gles/konservering_NarmastRamp3`, loggarna `/data/projektion/logg/3-*.log`.

## Det som inte hanns med eller är svagt

- Urvalet gjordes på 6 träningsdagar på 4 km; steget med finalisterna på 2 km på fler träningsdagar hoppades över för att hinna med valideringen (ett uppvärmt system tar cirka 80 min i `validering_gles`). Med 6 dygn är intervallen för konserveringen breda, så valet bygger på riktningen och på att inga cellerna var sämre.
- Bara en finalist kördes på valideringen. Ablationen `Narmast` (närmaste granne på alla ledtider) och `Narmast05` finns bara på träningsdagarna.
- De prövningar som uppdraget föreslår men som inte gjordes: matchningsmålet lärt per ledtid (rapport 2 visade att radarns eget lagrangeska avtagande inte går att mäta på träningsdagarna, så ett lärt mål skulle i medel ligga nära den flyttade analysens; det som saknas är inflödet), konservering per objekt, skaluppdelning med återställd varians och rörelsefält med flera bilder. MEPS-blandningen, där rapport 2 fann den största förlusten av toppar efter 1 h, finns inte som system i domaren.
- Rampen har två parametrar valda för hand i tre steg (60–180, 30–120 avbruten, 180–240), inte med slumpsökning.

## Nästa steg

1. **Bedöm den sömlösa prognosen med domaren.** Den största förlusten av toppar och form ligger i MEPS-blandningen (rapport 2: ytan ≥ 20 mm/h −0,63 vid 1 h, effekten 4 till 8 km −2,5 vid 5 h). Det kräver ett system `somlos` i domaren (med `seamless.blend` och MEPS-rättningen som i `forlust.py`) och en baslinje för det. Pröva sedan att lägga kedjans små skalor ovanpå det blandade fältet, eller matcha det blandade fältet mot kedjans fördelning för topparna. Här borde närmaste granne efter 3 h hjälpa ännu mer, eftersom formen i blandningen tappas just efter 2 h.
2. **Inflödet över randen**: fyll rutorna vars avgångspunkt ligger utanför täckningen med MEPS eller OPERA i stället för 0. Matchningen mot hela analysen (`Analys`) visar att det inte går att ta tillbaka volymen genom att omfördela värdena inom fältet.
3. Om `NarmastRamp3` ska vidare: kör `Narmast` och `NarmastRamp` på valideringen som ablationer, och den på `validering` (varje timme) för hoppen med 1 h mellan utgåvorna. Det är en liten ändring i drift (`Chain(interp="nearest", ramp=(180, 240))`), men den slår inte baslinjen enligt domen, så den ska inte in.

Status: delvis
