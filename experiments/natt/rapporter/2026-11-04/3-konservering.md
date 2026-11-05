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

(fylls i)

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

## Nästa steg

(fylls i)

Status: delvis
