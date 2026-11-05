# 6 Sammanfattning av natten 2026-11-04

Målet var att projektionen ska konservera nederbörden över ledtiderna, så att extremerna inte tappas på långa ledtider. **Inget system slog driftens kedja i domaren i natt, och rekommendationen är att driften inte ändras.** Det viktigaste resultatet är diagnosen (var extremerna tappas) och två delresultat som är värda att bygga vidare på: inflödet över randen (`Inflode25`) och närmaste granne efter 3 h (`NarmastRamp3`).

Uppdraget nämner både `sammanfattning.md` och `6-sammanfattning.md`; jag skrev bara den senare (den här filen), som uppgiftsraden anger.

## Rapporterna och deras status

| nr | uppgift | status | kort |
|---|---|---|---|
| 1 | domaren | delvis | `domare.py` med tester, baslinjerna i `validering_gles` (var 3:e timme, 125 utgåvor, 16 dygn). S-PROG och timläget `validering` kördes inte. |
| 2 | förlusten | klar | kedjan steg för steg på alla 28 träningsdygn |
| 3 | konserveringen | delvis | flytten, rangordningen, matchningsmålet och inflödet; `NarmastRamp3`, `Inflode25` och `Inflode75` på valideringen, ingen bättre |
| 4 | terrängen | delvis | GLO-90 till radarns rutnät, stillastående och rörlig del; `Lyft` på 6 av 16 valideringsdygn, inte bättre |
| 5 | sömlös till 5 h | **kördes inte** | ingen rapport och ingen logg finns; uppgiften startades aldrig (troligen slut på nattens tid före reserven till sammanfattningen). Den sömlösa blandningen är alltså inte bedömd med domaren, och körtiden för hela kedjan med MEPS på Pi:n är inte mätt. Jag gjorde inte uppgift 5 här: den behöver ett nytt system i domaren och cirka 2 h, och sammanfattningen har 40 min. |

## Vad som prövades

- **Domaren** (rapport 1): konservering (percentiler, ytor, volym, blockmax), träff (FSS, CSI, SEDI för 5 och 10 mm/h), spärrar (FSS och CSI 1 mm/h, formen 4 till 8 och 8 till 16 km, hoppen) och bootstrap över dygnen. Domen räknar en skillnad i log kvot bara om intervallet ligger minst 0,01 från 0.
- **Baslinjerna**: persistens, pysteps (tätt Lucas-Kanade), kedjan utan fördelningsmatchning, kedjan utan platskarta.
- **Flytten** (rapport 3): bikubisk med klippning, närmaste granne, blandningar med den bilinjära och en ramp över ledtiden; skärpt rangordning i matchningen; matchning mot hela analysens fördelning.
- **Inflödet över randen** (rapport 3, försök 2): utsidan av täckningen fylls från randvärdena med avtagande exp(−avstånd/L), L = 25, 75, 250 km.
- **Terrängen** (rapport 4): en andel av fältet står still, styrd av lyftet (rörelsen gånger höjdgradienten) eller av platskartans fel; variant med matchningens mål ur det odelade fältet (`LyftHel`, bara träningsdagarna).

Allt valdes på träningsdagarna (oftast läget `snabb`, 6 dygn på 4 km) och bedömdes på valideringen. Testdelen lästes inte av någon uppgift.

## Var extremerna tappas (rapport 2, 28 träningsdygn)

I ordning efter storlek:

1. **MEPS-blandningen i den sömlösa prognosen, från 1 h**: ytan ≥ 20 mm/h −0,63 vid 1 h och −1,1 vid 2 h, 99,9-percentilen −0,31 vid 1 h och −0,5 efter 2 h, blockmaxets 90-percentil −0,77 vid 5 h, effekten 4 till 8 km −2,5 vid 5 h (sömlös totalt −3,4, som −3,6 i `form_validering.md`). Samtidigt +0,32 i volym vid 5 h och klart bättre träff efter 2 h. Det är förlust av toppar och form, inte av mängd.
2. **Regn som kommer in över täckningens rand**, växer med ledtiden: ytan ≥ 5 mm/h −0,07 vid 1 h, −0,17 vid 2 h, −0,30 vid 5 h; volymen −0,26 vid 5 h. Det är hela kedjans förlust av yta och volym.
3. **Den bilinjära flytten**, konstant från 15 min: effekten 4 till 8 km −0,58, blockmaxets 90-percentil −0,14, ytan ≥ 20 mm/h −0,12. Matchningen tar tillbaka percentilerna men bara 10 % av formen och 60 % av blockmaxet.
4. Kvartsmedlet av flyttade bilder och lägesfel, konstant (blockmax −0,09 till −0,12 även med närmaste granne).
5. Radarns eget avtagande i lagrangeska koordinater: inte mätbart (intervallen täcker 0). Deformationen: högst cirka 2 % av ytan. Extremmodellen ändrar inte fältet (bara sannolikheter), platskartan lägger till något.

Kedjan själv (utan MEPS) har alltså rätt percentiler bland de våta rutorna, men tappar **yta och volym** med ledtiden (ytan ≥ 5 mm/h −0,26, volymen −0,30 vid 5 h på valideringen) och **formen** från första steget (−0,67 vid 15 min, −1,07 vid 5 h).

## Alla system mot kedjan på valideringen

Läget `validering_gles` (16 dygn, 125 utgåvor, 2 km; `Lyft` bara 6 dygn och då jämförd med kedjan på samma dygn). Skillnad mot `kedja`, negativt är bättre, med 95 %-intervall ur 1000 bootstrapdragningar över dygnen. `*` intervallet helt på den bättre sidan, `!` helt på den sämre (för log kvot minst 0,01 från 0). Hela tabellen med 14 mått och fyra ledtider per system: `experiments/projektion/resultat/sammanfattning.md` (gjord i natt av `experiments/projektion/sammanfatt.py`, bara ur de sparade summorna).

### Konserveringen (|log kvot| mot radarn, system − kedjan)

| system | yta ≥ 5, 2 h | yta ≥ 5, 5 h | yta ≥ 10, 15 min | volym, 5 h | q99,9, 5 h | blockmax q90, 5 h |
|---|---|---|---|---|---|---|
| persistens | +0,030 (−0,081, +0,190) | −0,103 (−0,325, +0,064) | +0,103 (+0,056, +0,188)! | −0,271 (−0,395, −0,164)* | +0,177 (+0,013, +0,255)! | +0,174 (+0,050, +0,304)! |
| pysteps | +0,080 (+0,009, +0,184) | +0,054 (−0,010, +0,155) | −0,119 (−0,184, −0,044)* | +0,020 (−0,016, +0,065) | −0,015 (−0,096, +0,145) | +0,092 (+0,047, +0,109)! |
| utan matchning | +0,024 (+0,011, +0,043)! | +0,024 (+0,008, +0,054) | −0,062 (−0,113, −0,035)* | +0,000 (−0,001, +0,002) | −0,011 (−0,104, +0,127) | +0,062 (+0,034, +0,093)! |
| utan platskarta | +0,043 (+0,009, +0,089) | +0,019 (+0,001, +0,046) | −0,075 (−0,148, −0,040)* | +0,004 (−0,004, +0,012) | +0,005 (−0,022, +0,039) | +0,027 (−0,005, +0,037) |
| NarmastRamp3 | 0,000 | +0,014 (+0,005, +0,030) | 0,000 | +0,000 (−0,001, +0,001) | −0,042 (−0,051, +0,052) | −0,063 (−0,068, +0,058) |
| Inflode25 | −0,051 (−0,067, +0,007) | −0,078 (−0,110, −0,036)* | +0,019 (+0,010, +0,030)! | −0,055 (−0,091, −0,022)* | +0,116 (−0,035, +0,304) | −0,001 (−0,024, +0,008) |
| Inflode75 | −0,078 (−0,097, +0,041) | −0,152 (−0,200, −0,050)* | +0,019 (+0,011, +0,030)! | −0,105 (−0,174, −0,039)* | +0,323 (−0,027, +0,669) | −0,007 (−0,032, +0,013) |
| Lyft (6 dygn) | +0,022 (+0,014, +0,029)! | +0,033 (+0,026, +0,047)! | −0,001 (−0,005, +0,001) | +0,017 (+0,014, +0,020)! | −0,006 (−0,030, +0,033) | +0,021 (+0,006, +0,046) |

Persistensens volym ser bättre ut eftersom den inte flyttar något ut ur området; den är sämre i allt annat.

### Träffen för det kraftiga (kedjan − system, negativt är bättre)

| system | FSS 5 mm/h 30 km, 1 h | FSS 5 mm/h 30 km, 2 h | CSI 5 mm/h, 15 min | CSI 5 mm/h, 1 h | SEDI 10 mm/h, 15 min | SEDI 10 mm/h, 5 h |
|---|---|---|---|---|---|---|
| persistens | +0,167 (+0,096, +0,240)! | +0,121 (+0,040, +0,185)! | +0,192 (+0,171, +0,211)! | +0,078 (+0,050, +0,103)! | +0,093 (+0,067, +0,120)! | −0,160 (−0,292, −0,065)* |
| pysteps | +0,022 (+0,001, +0,057)! | +0,031 (+0,010, +0,073)! | +0,000 (−0,005, +0,009) | +0,010 (+0,001, +0,022)! | +0,010 (+0,004, +0,026)! | +0,020 (−0,025, +0,063) |
| utan matchning | −0,001 (−0,001, −0,000)* | −0,002 (−0,004, −0,001)* | −0,003 (−0,004, −0,002)* | −0,001 (−0,001, −0,000)* | +0,004 (+0,002, +0,009)! | −0,002 (−0,005, +0,003) |
| utan platskarta | +0,016 (−0,001, +0,045) | +0,008 (−0,001, +0,024) | +0,006 (+0,002, +0,012)! | +0,009 (+0,002, +0,018)! | +0,008 (+0,005, +0,017)! | −0,003 (−0,010, +0,008) |
| NarmastRamp3 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | −0,002 (−0,009, +0,001) |
| Inflode25 | −0,008 (−0,026, +0,005) | −0,014 (−0,032, +0,002) | −0,004 (−0,005, −0,001)* | −0,006 (−0,012, −0,001)* | −0,004 (−0,009, −0,002)* | −0,022 (−0,040, +0,004) |
| Inflode75 | −0,008 (−0,026, +0,006) | −0,016 (−0,034, +0,001) | −0,004 (−0,006, −0,001)* | −0,007 (−0,013, −0,001)* | −0,005 (−0,009, −0,002)* | −0,064 (−0,113, +0,010) |
| Lyft (6 dygn) | −0,002 (−0,004, −0,001)* | −0,001 (−0,002, +0,001) | +0,001 (−0,001, +0,002) | −0,001 (−0,001, +0,000) | +0,001 (+0,000, +0,002)! | −0,001 (−0,006, +0,022) |

### Spärrarna

| system | FSS 1 mm/h 30 km, 2 h | CSI 1 mm/h, 1 h | form 4 till 8 km, 1 h | form 4 till 8 km, 5 h | hopp, 1 h |
|---|---|---|---|---|---|
| persistens | +0,142 (+0,100, +0,174)! | +0,116 (+0,099, +0,133)! | −0,403 (−0,488, −0,324)* | −0,765 (−0,989, −0,595)* | +0,115 (+0,057, +0,163)! |
| pysteps | +0,018 (+0,007, +0,032)! | +0,012 (+0,006, +0,018)! | +0,044 (+0,035, +0,056)! | +0,015 (−0,023, +0,047) | −0,012 (−0,025, +0,004) |
| utan matchning | −0,002 (−0,002, −0,001)* | −0,002 (−0,002, −0,001)* | +0,051 (+0,045, +0,055)! | +0,042 (+0,035, +0,048)! | −0,019 (−0,022, −0,017)* |
| utan platskarta | +0,000 (−0,002, +0,003) | +0,004 (+0,002, +0,008)! | −0,002 (−0,006, +0,002) | −0,001 (−0,004, +0,002) | −0,011 (−0,016, −0,007)* |
| NarmastRamp3 | 0,000 | 0,000 | 0,000 | −0,544 (−0,581, −0,515)* | −0,003 (−0,003, −0,002)* |
| Inflode25 | −0,007 (−0,010, −0,002)* | −0,003 (−0,005, −0,001)* | +0,000 (+0,000, +0,001) | +0,002 (−0,001, +0,004) | −0,005 (−0,010, +0,000) |
| Inflode75 | −0,007 (−0,011, −0,002)* | −0,003 (−0,006, −0,001)* | +0,000 (+0,000, +0,001) | −0,002 (−0,007, +0,001) | −0,001 (−0,009, +0,006) |
| Lyft (6 dygn) | −0,002 (−0,004, +0,000) | −0,001 (−0,002, −0,001)* | −0,061 (−0,114, −0,011)* | +0,002 (−0,015, +0,012) | −0,002 (−0,004, −0,001)* |

Hoppen i `validering_gles` jämför utgåvor 3 h isär och finns därför bara till 2 h.

### Domarna

| system | dom | det som fäller (sämre celler) | körtid för valideringen, 2 processer |
|---|---|---|---|
| persistens | inte bättre | det mesta | 3,6 min |
| pysteps | inte bättre | blockmaxet, FSS och CSI från 1 h, formen | 27,6 min |
| kedjan utan matchning | inte bättre | blockmaxet, formen, SEDI tidigt | 52,1 min |
| kedjan utan platskarta | inte bättre | CSI, SEDI och FSS de första timmarna | 28,5 min |
| `NarmastRamp3` | inte bättre | inga sämre celler, men ingen konservering säkert bättre | 78 min |
| `Inflode25` | inte bättre | bara ytan ≥ 10 mm/h vid 15 och 30 min och ytan ≥ 20 mm/h vid 30 min (+0,02); säkert bättre volym från 2 h, yta ≥ 5 mm/h från 3 h, CSI 5 mm/h och alla spärrar | 57 min |
| `Inflode75` | inte bättre | samma tre celler; mer volym tillbaka, men q99,9 för hög vid 5 h (+0,32, inte säkert) | 70 min |
| `Lyft` (6 dygn) | inte bättre | ytan ≥ 5 och 10 mm/h och volymen efter 2 till 3 h | 23 min (6 dygn) |
| S-PROG | **inte körd** | | |
| `LyftHel` | bara träningsdagarna, inte bättre (FSS 10 mm/h 10 km vid 30 min) | | |

## Rekommendationen

**Ändra inte driften.** Inget system är bättre enligt domaren, och reglerna tillåter bara att en ny modell ersätter baslinjen om den slår den. Alla nya val i `model.Chain` har standardvärden som ger exakt driftens kedja (testat), så grenen kan tas in för valen och verktygen utan att något ändras i drift.

Det som är närmast och bör drivas vidare, i den här ordningen:

1. **`Inflode25`** (`Chain(inflow=25 km / upplösningen)`, alltså `inflow=12.5` pixlar på 2 km). Det är nattens enda system med säkert bättre konservering på valideringen (volymen −0,055 och ytan ≥ 5 mm/h −0,078 i |log kvot| vid 5 h) och samtidigt säkert bättre CSI 5 mm/h och spärrar. Det fälls bara av att ytan ≥ 10 och 20 mm/h blir 0,02 för stor de första 30 min, där kedjans platskarta redan överskattar (kedjan +0,13 vid 15 min, utan platskarta +0,06). Skälet att rekommendera den som nästa kandidat är att den angriper förlust nummer 2 i rapport 2, den enda i kedjan som växer med ledtiden.
2. **`NarmastRamp3`** (`Chain(interp="nearest", ramp=(180, 240))`): halverar formfelet vid 5 h (−0,54) utan sämre celler på domens ledtider, men vid 4 h, som domen inte räknar, är CSI 5 mm/h sämre med 0,0003. Den är värdefull mest i den sömlösa prognosen, där formen tappas efter 2 h.
3. Terrängdelningen (`Lyft`, `LyftHel`) ger lite träff den första timmen men ingen konservering; den håller inte kvar fler extremer än kedjan.

## Körtiden

- Kedjan på hela Sveriges rutnät på 2 km (887 x 471 rutor), 60 steg till 5 h, med driften som konkurrent: cirka 22 s per utgåva (`kedja_om`, rapport 1), varav fördelningsmatchningen i varje steg är det mesta. `Inflode25` 19,1 s per utgåva (avståndsfältet kostar några tiondels sekunder, skillnaden mot kedjan är brus), `Lyft` 20,5 s, `NarmastRamp3` 40,8 s på 2 km i valideringen men bara +6 % mot kedjan när de mättes sida vid sida på 4 km (4,54 mot 4,28 s); det höga värdet på 2 km beror troligen på konkurrensen från driften under den körningen och är inte utrett.
- Alla ryms inom två minuter per cykel för kedjans del. **Hela cykeln med MEPS-blandningen och rendering är inte mätt i natt** (det var uppgift 5).
- Domaren: ett system utan uppvärmning tar cirka 30 min i `validering_gles`, ett uppvärmt 50 till 80 min; timläget `validering` uppskattningsvis 2 till 3 h per uppvärmt system, alltså över målet på 45 min (rapport 1).
- Sammanfattningens tabell: under en minut, bara ur sparade summor.

## Vad som återstår

1. **Uppgift 5 i sin helhet**: ett system `somlos` i domaren (MEPS-rättningen och `seamless.blend` som i `forlust.py`), baslinjen för det, och varianter som håller kvar topparna i blandningen (matcha det blandade fältet mot kedjans fördelning för topparna, lägg tillbaka kedjans små skalor, vikten per skala). Det är där den största förlusten av toppar ligger. Mät hela cykeln på Pi:n.
2. **Inflödet utan överskott tidigt**: `Inflode25` med en platskarta som inte förstärker de högsta intensiteterna (klippt uppåt, eller korrektionen matchad tillbaka mot målets fördelning), först på träningsdagarna. Sedan fyllning från MEPS eller OPERA i stället för randvärdet.
3. `LyftHel` på hela valideringen och i kombination med inflödet; slumpsökning över terrängparametrarna.
4. S-PROG som baslinje, `kedja` och `persistens` i timläget `validering`, finalisterna på 2 km och fler träningsdagar (steget hoppades över i uppgift 3 och 4).
5. Bakgrundskörningar behöver `timeout` upp till 2 h; flera uppgifter förlorade tid på gränsen 10 min.

## Kommandon för testdelen (inte körda)

Det rekommenderade systemet är driftens kedja, oförändrad, så det finns inget nytt system att släppa på testdelen i dag. Testdelen ska användas först när en kandidat har gått igenom domen på valideringen. Domaren vägrar med avsikt testdagarna (`mode_days` stoppar), och nattens behörigheter nekar `--part test`, så det här görs av en människa. För att bedöma kedjan och den närmaste kandidaten `Inflode25` på testdelen, från repots rot:

1. Lägg till läget i `experiments/projektion/domare.py`, i `LÄGEN`:
   ```python
   "test": dict(days=lambda: [d["day"] for d in load_days("test")], res=2,
                hours=lambda d: [h for h in _chain_hours(d) if h % 3 == 0], ref="kedja"),
   ```
   och i `mode_days` gör kontrollen villkorlig: `if mode != "test": assert not test & set(days), ...`.
2. Driftens kedja för testdagarna, om de inte redan finns i `/data/sverige/kedja/` (två processer):
   ```
   uv run python experiments/sverige/kedja.py --part test --shard 0/2
   uv run python experiments/sverige/kedja.py --part test --shard 1/2
   ```
3. Domaren på testdelen (baslinjen läser bara driftens filer; kandidaten värms upp, cirka 1 h):
   ```
   uv run python experiments/projektion/domare.py kör --läge test --system kedja --procs 2
   uv run python experiments/projektion/domare.py kör --läge test --system konservering:Inflode25 --procs 2
   uv run python experiments/projektion/domare.py tabell --läge test --system konservering:Inflode25 --ref kedja
   ```
   Tabellen hamnar i `experiments/projektion/resultat/test.md`.

## Filer i den här uppgiften

- `experiments/projektion/sammanfatt.py` (ny): tabellen över alla system mot kedjan med intervall, ur domarens sparade summor.
- `experiments/projektion/resultat/sammanfattning.md` (ny): resultatet, 1000 bootstrapdragningar.
- Den här rapporten. Inga ändringar i `src/knep/`, ingen ny data under `/data` (3,0 GB ledigt).
- `uv run pytest`: 79 gick igenom (122 s). Allt är committat utom loggfilen `logg/6-sammanfattning.txt`, som körskriptet skriver under sessionen och committar själv efteråt, som för de andra uppgifterna.

Status: klar
