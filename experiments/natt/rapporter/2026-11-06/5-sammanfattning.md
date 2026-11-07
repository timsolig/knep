# Uppgift 5: sammanfattning av natten 2026-11-06 (analysen)

Före uppgiften fanns rapporterna 1 till 4, alla med `Status: klar` (uppgift 3 och 4 i två försök). Inget var halvfärdigt. Den här uppgiften har inte kört något nytt mot data: siffrorna nedan är tagna ur rapporterna 1 till 4, som citerar domarens tabellfiler i `/data/analys/domare/tabell_*_validering.json`. Jag har inte kunnat läsa tabellfilerna själv i den här uppgiften (kommandot nekades av behörigheterna), så siffrorna är kontrollerade mot rapporterna och inte mot filerna en gång till. `sammanfattning.md`, med namnet som uppdraget anger, hänvisar hit och har ett kort sammandrag.

## Vad uppgift 1 till 4 kom fram till

**1. Inventeringen av artefakterna** (`experiments/analys/artefakter.py`, `karta.py`, `bild.py`). 44 dagar (28 träning och 16 validering), per ruta och bild för bild.

- Det värsta klottret är tydligt och står kvar på valideringsdagarna. Det har eko i 45 till 77 % av bilderna (medel 17 %) och under torra timmar i 30 till 57 % (medel 5 %). Det är isolerat, kantigt och finns i alla väderlägen. Det mesta sitter vid vindkraftsparker i Jämtland, Västernorrland och Västerbotten, vid radarplatserna och i några fasta ekrar.
- **Stillheten mot rörelsefältet skiljer inte klotter från orografi.** Den möjliga orografin har `euler_lagr` 0,68 och fjällen i allmänhet 0,87. Det som skiljer är torrt vid mätarna (`f_torr` 0,04 mot 0,3 till 0,57), isolering (0,01 mot 0,1 till 0,5), textur (2,6 mot 7 till 26) och lyftet (1,7 mot 0,5 till 1,15).
- Solstrålarna är tydliga bild för bild, men bara när solen står mellan cirka −1 och +1° (20 till 26 % av ekrarna mot 1,9 % av en slump). Fasta ekrar finns: sebaa 134° syns på 34 av 44 dagar. Varken havsklotter eller anaprop gick att påvisa. De kantiga ekona vid torra mätare har sin topp mitt på dagen, så det är sommarskurar. Torra mätare i en enskild bild är alltså ett dåligt test för klotter.
- En typisk vindkraftsruta är ren. Förteckningen över verk duger inte som mask.

**2. Domaren** (`experiments/analys/domare.py`, 12 tester). Mätarna delas i block om 100 km i fem grupper, och en buffert på 25 km skyddar mot grannmätare. Domaren mäter mängd, träff, falska ekon och kartmåttet, terrängen (över 400 m och lovart) och hoppen mellan kvartarna. Bootstrap görs över dagarna med 2 000 dragningar. Ett mått bedöms bara om underlaget kommer från minst 5 dagar; den regeln lades till under körningen och gäller alla system lika. Baslinjerna A0 och A1 är körda på valideringen.

**3. A2** (`experiments/analys/a2.py`, 4 tester). A2 rättar A1 med en kvot i stor skala, gör optimal interpolation i kvadratrotsskala och har en torrmask. Parametrarna är valda och frysta på träningsdagarna med samma korsvalidering. Mot A0 är A2 bättre, men inte mot A1. Det som fäller A2 är falska ekon per kvart i terrängen.

**4. Filtret** (`experiments/analys/filter.py`, `src/knep/analys/klotter.py`). Först väljs en karta över misstänkta rutor på träningsdagarna. I varje bild tas ekot sedan bort på kartans rutor bara när omgivningen inom 42 km är torr, så regn som hänger ihop med annat regn får stå kvar. Till det kommer ett test för ekrar och solstrålar. F0 (bara ekrar) gjorde ingenting som syns. F1 (kartan med utvidgning) föll på summakvoten över 400 m. **F4 (kartan utan utvidgning)** valdes på träningen och godkändes av domaren på valideringen. Kartdelen ligger i `src/` som valet `--klotter`, och det är av som standard.

## Domarens tabeller mot A0 (validering, 16 dagar)

Skillnaden anges i godhet, där större alltid är bättre, med 95 % ur bootstrap över dagarna. **Fet** betyder att intervallet ligger helt på ena sidan.

### Domen

| system | mot A0 | det som avgör |
|---|---|---|
| A1 | **inte bättre** | bättre i MAE, CSI 0,5 och 1 och FSS 0,5 (kvart och timme), men sämre i summakvoten på lovartsidan (kvart och timme) |
| A2 | **bättre** | bättre i 15 mått, inget sämre (mot A1: inte bättre, sämre i falska ekon per kvart över 400 m och på lovartsidan) |
| F0 | varken bättre eller sämre | inget mått har intervallet på någon sida |
| F1 | inte bättre | sämre i summakvoten över 400 m (kvart och timme), annars bättre |
| F4 | **bättre** (marginellt) | bättre i FSS 0,5, 1 och 5, inget sämre; kartmåttet +9,0 |

### Timme, alla mätare

| mått | A0 | A1 | A2 | F4 | A1 − A0 | A2 − A0 |
|---|---|---|---|---|---|---|
| kvot summa | 0,890 | 0,889 | 0,945 | 0,890 | −0,001 (−0,007 till +0,006) | +0,060 (−0,018 till +0,141) |
| kvot > 1 mm | 0,716 | 0,714 | 0,797 | | −0,004 (−0,012 till +0,006) | **+0,106 (+0,014 till +0,179)** |
| kvot > 5 mm | 0,499 | 0,494 | 0,592 | | −0,009 (−0,030 till +0,031) | **+0,170 (+0,118 till +0,191)** |
| MAE (mm) | 0,233 | 0,228 | 0,214 | 0,233 | **+0,005 (+0,003 till +0,007)** | **+0,019 (+0,011 till +0,029)** |
| CSI 0,5 | 0,520 | 0,528 | 0,576 | | **+0,008 (+0,005 till +0,013)** | **+0,057 (+0,037 till +0,075)** |
| CSI 1 | 0,423 | 0,429 | 0,470 | | **+0,006 (+0,002 till +0,012)** | **+0,047 (+0,024 till +0,071)** |
| CSI 5 | 0,160 | 0,169 | 0,216 | | +0,009 (−0,005 till +0,036) | **+0,056 (+0,012 till +0,082)** |
| FSS 1 | 0,634 | 0,635 | 0,685 | 0,634 | +0,001 (−0,001 till +0,002) | **+0,050 (+0,026 till +0,074)** |
| falskt vid torr mätare | 0,010 | 0,010 | 0,009 | 0,010 | +0,001 (+0,000 till +0,001) | +0,002 (+0,000 till +0,003) |

För F4 mot A0 per timme: FSS 1 är **+0,00001 (+0,000005 till +0,000015)**, och summakvoten, MAE och falska ekon är oförändrade (0 till 0).

### Kvart, alla mätare

| mått | A0 | A1 | A2 | A1 − A0 | A2 − A0 |
|---|---|---|---|---|---|
| kvot summa | 0,825 | 0,824 | 0,886 | −0,001 (−0,008 till +0,004) | +0,071 (−0,018 till +0,152) |
| MAE (mm) | 0,069 | 0,067 | 0,064 | **+0,003 (+0,002 till +0,004)** | **+0,005 (+0,003 till +0,007)** |
| CSI 0,5 | 0,287 | 0,303 | 0,336 | **+0,015 (+0,009 till +0,023)** | **+0,049 (+0,031 till +0,063)** |
| CSI 1 | 0,179 | 0,196 | 0,233 | **+0,017 (+0,006 till +0,027)** | **+0,054 (+0,025 till +0,076)** |
| FSS 1 | 0,327 | 0,333 | 0,390 | +0,006 (−0,000 till +0,012) | **+0,063 (+0,032 till +0,083)** |
| falskt vid torr mätare | 0,026 | 0,025 | 0,024 | +0,001 (+0,000 till +0,001) | +0,001 (−0,001 till +0,004) |
| hopp, kvot mot mätarna | 0,884 | 0,809 | 0,888 | (redovisas, ingår inte i domen) | |

### Terrängen

| delmängd, mått | A0 | A1 | A2 | F4 | A1 − A0 | A2 − A0 | F4 − A0 |
|---|---|---|---|---|---|---|---|
| timme > 400 m, kvot summa | 0,524 | 0,505 | 0,676 | 0,524 | −0,036 (−0,154 till +0,042) | **+0,255 (+0,081 till +0,371)** | −0,0001 (−0,0001 till +0,0000) |
| timme > 400 m, FSS 1 | 0,429 | 0,432 | 0,551 | 0,429 | | **+0,123 (+0,049 till +0,181)** | **+0,00002** |
| timme lovart, kvot summa | 0,671 | 0,653 | 0,821 | 0,671 | **−0,028 (−0,051 till −0,006)** | **+0,202 (+0,052 till +0,310)** | −0,0001 (−0,0003 till +0,0000) |
| kvart lovart, kvot summa | 0,604 | 0,592 | 0,750 | | **−0,020 (−0,039 till −0,001)** | **+0,217 (+0,076 till +0,322)** | |
| kvart > 400 m, falskt vid torr mätare | 0,015 | 0,013 | 0,016 | | | −0,001 (−0,006 till +0,003) | |

### Kartmåttet

Kartmåttet är antalet rutor per dag med eko i mer än hälften av de torra timmarna.

| | A0 | A1 | A2 | F1 | F4 |
|---|---|---|---|---|---|
| rutor per dag | 36,6 | 40,4 | 47,2 | 24,1 | **27,6** |
| skillnad mot A0 | | −3,9 (−9,5 till +1,0) | −10,6 (−24,9 till +0,1) | **+12,5 (+8,1 till +17,6)** | **+9,0 (+5,9 till +12,5)** |

## Vad siffrorna säger

- **Radarn tappar mest i fjällen.** Över 400 m ger den hälften av mätarnas mängd, och på lovartsidan två tredjedelar. Där har A2 mest att vinna, och det är där den vinner mest (+0,2 till +0,25 i summakvoten).
- **A1 flyttar regn som står still vid sluttningen.** Det ger 2 till 3 % mindre regn på lovartsidan, med intervallet på fel sida. Det är precis den fälla som uppdraget varnar för. A1 ger ändå bättre träff per kvart.
- **A1 och A2 smetar ut och skalar upp klottret** (kartmåttet 36,6, sedan 40,4 och 47,2). Filtret bör alltså verka på A0 innan A1 och A2 räknas.
- **F4 tar bort fast klotter mellan mätarna** (en fjärdedel av kartmåttet) utan att röra terrängen, men vid mätarna syns det nästan inte. Domaren kan bara se klotter där det finns mätare, och domen bygger på FSS-vinster på 10⁻⁵.

## Rekommendation för drift

1. **Låt driften gå som i dag.** Ingen standard ändras, och inget i den här körningen kräver det.
2. **Klotterfiltret F4 (`--klotter`) bör slås på, men först när du har godkänt det.** Kartan är en tränad fil och måste därför släppas i GitHub Releases och låsas i `models/models.json` (via `deploy/release_model.sh`). Det är en ny modellversion, och enligt CLAUDE.md ska användaren tillfrågas först. Skälen för: F4 är det enda filtret som domaren godkänner, terrängen rörs inte (alla mått över 400 m och på lovartsidan är oförändrade) och det kostar 0,05 s per bild. Skälen för försiktighet: vinsten vid mätarna är försumbar, valideringen var redan sedd när F4 lades till (för F0 och F1 i försök 1), och urvalet på träningen gjordes på 13 av 28 dagar. **Kör testdelen (kommandona nedan) innan filtret slås på.**
3. **A1 bör stå kvar som i dag i fliken Analys** (den finns redan i drift). Den bör inte ersätta A0 som start för prognosen förrän underskottet på lovartsidan är rättat, till exempel med en mindre rörelse där lyftet är stort, som `Chain.stay` gör.
4. **A2 är inte redo att bli facit i verifieringen.** Den slår A0 men inte A1, och mätarna saknar kontroll mot grannarna. A2 kan visas som A2 i fliken Analys först när den slår A1 enligt domaren.

## Körtiderna på Pi:n

| steg | tid |
|---|---|
| inventeringen per dag (`artefakter.py`) | några minuter per dag; bild för bild cirka 2,5 min per dag med två processer |
| domaren, A0 + A1 på 16 valideringsdagar | cirka 1 h 45 min med två processer (11 till 19 min per dag och process, A1 8 till 14 min) |
| A2, en timme och dess fyra kvartar på hela rutnätet | 2,6 till 2,8 s (ryms en gång i timmen) |
| A2 genom domaren | 3 till 4 min per dag (fem grupper) |
| A2:s träning, kvarten | cirka 15 min |
| F4, `klotter.rensa` | cirka 0,05 s per bild, under 1 s per cykel |
| F0 / F1 inklusive ekrar | cirka 0,1 / 0,15 s per bild |
| domaren med F4 | 66 till 90 s per dag |
| `uv run pytest` | 163 godkända på 2 min 20 s |

Disken: allt under `/data/analys` tar 728 MB (gränsen är 1 GB), och `/` (där `/data` ligger) har 5,3 GB ledigt.

## Det som återstår

1. **Domaren**: summakvoten belönar överskott där analysen är för torr (över 400 m är kvoten 0,5), och det fällde F1. Ett mått som kvoten för perioder där mätaren har regn bör övervägas. Det ska i så fall beslutas för sig, och baslinjerna A0, A1 och A2 ska köras om. Domaren behöver också ett mått som ser klotter mellan mätarna och ingår i domen, till exempel kartmåttet eller satellitens molnmask.
2. **Satellitens molnmask** hämtades inte, eftersom nätet var spärrat för körningen. Utan den kan anaprop och torrheten mellan mätarna inte avgöras.
3. **F4 tränas om på alla 28 träningsdagar** (urvalet gjordes på 13) och släpps som modellfil, om du godkänner det.
4. **Filtret under A1 och A2**: kör A1 och A2 på F4:s bilder. Det bör minska de falska ekona per kvart i terrängen, som fällde A2 mot A1.
5. **A1 i terrängen**: mindre rörelse där lyftet är stort.
6. **A2**: kontroll av mätarna (innovationen mot grannarna och radarn), radarns kvalitet i σ_b och mindre uppskalning av svaga ekon som står still.
7. **Ekrarna**: testet slår till för sällan. Nästa försök är en lägre tröskel inne i de fasta sektorerna.
8. Rörelsen räknas var 15:e minut i domaren och var 5:e minut i drift, så A1 i domaren är inte exakt A1 i drift.

## Kommandon för testdelen (körs inte i natt)

Koden spärrar testdelen avsiktligt: `domare.days()` kastar ett fel för allt annat än `validering` och `traning`, `--del` i `domare.py` och `filter.py` har bara de två valen, och `a2.py` läser bara `validering`. För att köra testet krävs därför en liten ändring. Den görs **först när användaren beslutar det**, och den ska inte ändra något som väljs:

1. I `experiments/analys/domare.py`, `days()`, lägg till grenen `elif part == "test": return sorted(test)` före `else`, och flytta `assert not test & set(out)` in i de två andra grenarna. Lägg sedan till `"test"` i `choices` för `--del` i `domare.py` och `filter.py`.
2. I `experiments/analys/a2.py`: lägg till `--del` och använd den i stället för `"validering"` i `cmd_a1falt` och `cmd_kor`, inklusive assertionen på rad 451.

Därefter, med högst två processer och var för sig i bakgrunden med logg och `timeout`:

    # baslinjerna och A1 (A1 tar längst tid; cirka 2 h för 16 dagar med två processer)
    timeout 2h uv run python experiments/analys/domare.py kor A0 A1 --del test --bit 0/2 > logg_test_0.txt 2>&1 &
    timeout 2h uv run python experiments/analys/domare.py kor A0 A1 --del test --bit 1/2 > logg_test_1.txt 2>&1 &

    # det rekommenderade filtret F4 (kartan finns i /data/analys/filter/karta.npz, tränad på träningsdagarna; räknas inte om)
    uv run python experiments/analys/filter.py kor F4 --del test --dagar <testdagarna ur dagar.json>
    uv run python experiments/analys/filter.py tabell F4 --mot A0 --del test

    # A2 med de frysta parametrarna (PARAMS i a2.py), på A1:s fält
    uv run python experiments/analys/a2.py a1falt --del test --bit 0/2   (och --bit 1/2)
    uv run python experiments/analys/a2.py kor --del test --bit 0/2      (och --bit 1/2)
    uv run python experiments/analys/domare.py tabell A2 --mot A0 --del test
    uv run python experiments/analys/domare.py tabell A2 --mot A1 --del test
    uv run python experiments/analys/domare.py tabell A1 --mot A0 --del test

Tabellerna hamnar i `/data/analys/domare/tabell_<system>_mot_<bas>_test.json`. Ingen parameter, tröskel eller karta får ändras efter att testet har körts.

Driften med filtret, efter att kartan har släppts och låsts (en historisk cykel som prov):

    uv run python experiments/analys/filter.py karta_drift      # skriver /data/analys/filter/klotter_f4.npz
    uv run knep --time 2026-07-14T15:30 --out web/data --klotter /data/analys/filter/klotter_f4.npz

## Kontrollen i den här uppgiften

- `uv run pytest`: **163 godkända** (2 min 20 s).
- Ändringarna i `src/` mot `main` är små: `src/knep/analys/__init__.py` (+13), `src/knep/analys/klotter.py` (ny, 49 rader) och `src/knep/cli.py` (+4). Valet är av som standard, och ett test kontrollerar det.
- **Inget i den här uppgiften är committat.** Allt arbete i uppgift 1 till 4 var committat när uppgiften började: det enda som inte var spårat var loggfilen `logg/5-sammanfattning.txt`. När pytest hade gått igenom nekades alla skalkommandon av behörigheterna, även `git add`. Därför ligger `5-sammanfattning.md`, `sammanfattning.md` och `logg/5-sammanfattning.txt` ospårade i utcheckningen. Så committar du dem:

      git add experiments/natt/rapporter/2026-11-06
      git commit -m "Natt 2026-11-06: sammanfattningen av uppgift 1 till 4 (uppgift 5)"

  Inget pushades, och ingen PR öppnades.

## Ändrade filer

- `experiments/natt/rapporter/2026-11-06/5-sammanfattning.md` (den här rapporten) och `sammanfattning.md` (en hänvisning hit med ett kort sammandrag, under namnet som uppdraget anger).

Rapporten är skriven och pytest går igenom, men commiten kunde inte göras (se Kontrollen ovan).

Status: delvis
