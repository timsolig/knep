# 0012 Fliken Verifiering, del 1 (beslut 8)

Kort: fliken Verifiering är omskriven med alla mått på en gång (ett litet diagram per mått, ledtiden +1 till +5 h som axel, en linje per modell, intervallet som band) i fyra grupper, med egen period från och till som räknas i sidan ur dygnens summor; `verify.py` skriver nu det som saknades för det (Tim-KNEP på de andras urval, timmarna och underlaget per dygn) utan att något befintligt tal ändras, och måtten ur dygnens summor stämmer med `verify.py` inom 0,00011 på provdatan; sidan är **inte** ritad eller körd, eftersom varken Playwright, en webbläsare eller node finns på Pi:n.

Säkerställd förbättring: nej (en beställd ändring av sidan, ingen dom).

## Vad som gjordes

### 1. `verify.py`: dygnens summor räcker nu för alla mått

Jag gick igenom vad sidan behöver för att räkna en period själv och jämförde med `_daily()`:

| Behövs för | Fanns i `daily` före | Nu |
| --- | --- | --- |
| POD, FAR, CSI, ETS och de andra måtten ur kontingenstabellen | `ct` per modell | oförändrat |
| bias, MAE, RMSE, korrelation, volymkvot | `c` per modell | oförändrat |
| FSS per tröskel och skala | `fss` per modell (inte mot mätarna) | oförändrat |
| antalet timmar per ledtid | saknades | `hours` per modell och dygn |
| **skillnaden mot Tim-KNEP** på samma urval | saknades (nycklarna `ours@modell` hoppades över) | `daily.pairs[facit][modell]` med `ct`, `c`, `fss`, `hours` |
| underlaget för perioden (utgåvor, timmar med facit, A2T:s mätare) | saknades | `daily.meta`: `issues`, `obs_hours`, `gauge_hours`, `a2t_hours`, `a2t_n`, `first`, `last` per dygn |

Mätarna per station och loppens ålder per dygn lade jag inte till: de är stora (hundratals stationer gånger 30 dygn) och behövs inte för måtten. För en egen period visar sidan dem för de senaste 30 dygnen och skriver det.

Ändringen är bara tillägg. `windows` räknas som förut, och de befintliga posterna i `daily` är desamma. Kontrollerat på två sätt:

- provdatan (`/data/verif_prov/2020-07-24`, bara läst): `summary()` på nytt till `/tmp/verif_prov_ny/data`. Perioderna 7 och 30 dygn är lika bit för bit med den gamla `verif.json`, och de befintliga dygnsposterna också. Filen växte från 183 673 till 189 755 byte med ett dygn. Med 30 dygn blir `daily` ungefär dubbelt så stort som förut, eftersom `pairs` är lika stort som modellerna (uppskattat under 1 MB okomprimerat; GitHub Pages skickar det komprimerat).
- måtten ur dygnens summor, så som sidan räknar dem, mot `verify.py`: största skillnaden på provdatan är 0,00011 (från avrundningen av summorna i `daily`, 3 decimaler för `c` och 2 för `fss`, och avrundningen till 4 decimaler i `windows`).

Testet `test_daily_sums_give_the_windows_numbers` i `tests/test_verify.py` gör samma sak på syntetiska data med 34 dygn, radarn, mätarna och A2T, persistensen och MET Norge på ett mindre urval och bara vissa dygn: för 7 och 30 dygn ger summan av dygnen samma timmar, utgåvor och timmar med facit som `windows`, och alla mått och alla skillnader mot Tim-KNEP inom 1e-4 till 4e-3 (FSS-summorna är avrundade till 2 decimaler). `uv run pytest`: 214 gick igenom.

### 2. Sidan (`web/index.html`)

**Valen.** Överst två rader: **Period** (7 dygn, 30 dygn, Egen, och datumfälten från och till) och **Facit** (mot radarn, mot regnmätarna, mot A2T när `a2t` finns). Valen Mått, Tröskel, Skala och Ledtid är borta. Tröskeln finns kvar som ett val inne i de två grupper där den behövs, med en rad om vad den gör. Datumfälten visar alltid perioden som syns; ändrar man dem blir perioden Egen. En egen period sparas inte mellan besöken (dygnen byts ut), 7 eller 30 dygn gör det.

**En rad överst** förklarar diagrammen: ledtiden +1 till +5 h längs axeln, timmen som slutar så många timmar efter utgåvan, en linje per modell, bandet är 90 %-intervallet, peka för värdena och tryck för dygn för dygn.

**Grupperna**, var och en ett kort med rubrik, en rad om vad den svarar på och modellernas färger:

1. **Träff och falsklarm** ("Kom regnet där modellen sa att det skulle komma, och hur ofta larmade den i onödan?"), tröskel 0,1 till 4 mm: POD, FAR, CSI, ETS och frekvensbias. Under "Fler mått för regn och torrt" (hopfällt) HSS, PSS, MCC och SEDI, så att inget mått från förut har försvunnit.
2. **Mängd och fel** ("Gav modellen rätt mängd regn, och hur stora är felen i millimeter?"): volymkvot, medelfel, medelabsolutfel, RMSE och korrelation.
3. **Form och läge** ("Har regnområdena rätt form och ungefär rätt plats?"), tröskel 0,5, 1 eller 4 mm: FSS på 4, 20 och 60 km, ett diagram per skala. Gruppen döljs mot mätarna, där FSS inte räknas, och "Så räknas det" säger varför.
4. **Skillnaden mot Tim-KNEP** (persistensen, MET Norge, SNOW och mot mätarna också radarn och A2T): modellen minus Tim-KNEP för CSI och ETS vid gruppens tröskel, FSS på 20 km och medelabsolutfelet, med intervallet som band för alla och en linje vid 0, och en tabell "Vem är säkert bättre, med hela 90 %-intervallet på ena sidan?" med Tim-KNEP, modellen eller osäkert per ledtid.

Varje litet diagram har en titel, en kort rad (till exempel "Högre är bättre." följt av måttets förklaring), y-axeln och ledtiderna. Peka (eller tryck) visar ett hårkors och en ruta med varje modells värde och intervall. Referenserna (persistensen, radarn, A2T) är streckade och utan band, som förut.

**Dygn för dygn.** Ett kort under grupperna visar måttet dygn för dygn för det diagram och den ledtid man senast tryckte i (diagrammet får en blå ram och ledtiden en ljus markering); från början CSI vid +1 h. För ett diagram i skillnadsgruppen visas skillnaden per dygn. Under diagrammet finns samma tal som en hopfälld tabell.

**Underlaget och Så räknas det** står kvar. För en egen period räknas utgåvor och timmar med facit ur `daily.meta`; kartan, mätarna och loppens ålder gäller de senaste 30 dygnen, och det står under kartan. "Så räknas det" har ett nytt stycke om egen period och en mening om att ledtiden är axeln.

**Mobil och dator.** Diagrammen ligger i ett rutnät med minst 240 px per kolumn: i 390 px bredd blir det en kolumn (innehållet är cirka 330 px brett), på en dator med 1080 px fyra kolumner. Diagrammen är 150 px höga (160 px under 700 px bredd) och låter sidan rulla lodrätt vid beröring (`touch-action: pan-y`).

### 3. Egen period och intervallet

Sidan räknar måtten ur dygnens summor med samma formler som `verify.dichotomous`, `continuous_scores` och `fss_scores` (portade rad för rad, med NaN där Python ger NaN). Intervallet räknas också, med samma metod som `verify._window`: 1000 dragningar av dygnen med återläggning, vikter per dygn, 90 % med närmaste rang, inget intervall om måttet saknas i hälften av dragningarna och inget alls under 3 dygn. Slumptalen kommer från en egen generator med fast frö, så samma period ger alltid samma intervall, men inte exakt samma gränser som Pi:ns numpy-dragningar. Jag valde det framför att utelämna intervallet, eftersom skillnadsgruppen och tabellen över vem som är säkert bättre inte säger något utan det, och metoden är densamma; sidan skriver att gränserna kan skilja något i sista decimalen. 7 och 30 dygn tas direkt ur `windows`, så de ger exakt samma tal som förut, intervallen inräknade. Uträkningen görs bara för det facit som visas och sparas tills perioden ändras.

### 4. Förklaringen

Stycket om Verifiering i `#intro` beskriver nu grupperna, ledtiden som axel, att man trycker för dygn för dygn och perioderna. `INTRO` är höjd från 6 till 7 (versionerna med och utan A2 och A2T följer med, som förut).

## Prövningen: sidan är inte ritad

Det finns ingen webbläsare och inget sätt att köra JavaScript på Pi:n: `playwright` saknas i miljön, `chromium`, `chromium-browser`, `firefox`, `node`, `deno`, `bun`, `qjs`, `gjs` och `java` finns inte, och inga JS-tolkar finns bland Python-paketen (`js2py`, `quickjs`, `dukpy`, `py_mini_racer`). `~/.cache/ms-playwright` gick inte att lista härifrån. Enligt uppdraget installerade jag ingenting. Det finns alltså **inga skärmbilder**, och skriptet är inte kört.

Det som är kontrollerat i stället:

- att datan räcker och att formlerna ger samma tal som `verify.py` (testet ovan och provdatan), räknat i Python med samma steg som sidan gör;
- en grov syntaxkontroll av skriptet (`/tmp/jscheck.py`, inte i repot): parenteser, klamrar, strängar, mallsträngar med `${}`, kommentarer och regex går jämnt ut i hela skriptet. Kontrollen godkänner den gamla sidan, hittar ett planterat fel, och godkänner den nya;
- att inga nya namn deklareras två gånger, att varje `$('id')` med fast id finns i sidan, och att inget av de borttagna valen (`verif-metric`, `verif-lead`, `verif-scale`, `verif-all`, `vf.metric`, `vf.lead`) används kvar;
- genomläsning av uträkningen mot `verify.py` (kvantilerna, vikterna, formen på tripplarna) och av ritningen.

Fel som bara syns när skriptet körs (ett namn som är fel stavat, en layout som inte ser ut som tänkt) kan alltså finnas kvar. Användaren ville att sidan provas i Playwright, också i 390 × 844, innan den slås ihop (beslut 8). **Rekommendation:** slå inte ihop ändringen av sidan förrän den har ritats i en webbläsare, på en dator med Playwright eller efter att disken har fått plats för Chromium (cirka 300 MB under `~/.cache`). Det som ska provas: `python3 -m http.server -d web 8000` med `web/data` pekande på `/tmp/verif_prov_ny/data` (provdatan omräknad med den nya `verify.py`, ett dygn, så Egen ger inga intervall) och gärna en syntetisk `verif.json` med 30 dygn; fliken i 1280 × 900 och 390 × 844; byta facit, tröskel, 7 och 30 dygn och Egen; trycka i ett diagram och se dygn för dygn; öppna Fler mått; jämföra Egen med samma dygn som 7 dygn (skattningarna ska bli desamma med 3 decimaler). Ändringen i `verify.py` påverkar inte det som sidan visar i dag och kan slås ihop för sig.

## Filer

- `src/knep/verify.py`: `_daily()` skriver också `hours` per modell, `pairs` och `meta`; `DAY_META`.
- `tests/test_verify.py`: `test_daily_sums_give_the_windows_numbers` och hjälpen `_scores_from_daily`.
- `web/index.html`: fliken Verifiering (HTML, CSS och skriptet), förklaringen och `INTRO = 7`.
- `CLAUDE.md`: beskrivningen av `verify.py` och fliken.

Commits: `8348b95` (verify.py och testet), `55af86e` (sidan), `d1a6215` (Fler mått ritas om när den öppnas, CLAUDE.md).

## Vad som återstår

- **Prövning i en webbläsare** (ovan), med skärmbilder i dator- och mobilformat, och rättning av det som syns där. Först då är del 1 klar enligt beslut 8.
- `daily` gäller de senaste 30 dygnen (`max(WINDOWS)`), medan `cache/verif/days/` behåller 35. En egen period kan alltså gå 30 dygn bakåt. Att ta med alla sparade dygn är en rad i `summary()`, men ändrar vilka dygn `daily` har i dag, så jag lät det vara; och för att perioden ska kunna växa mer än så måste `KEEP_DAYS` höjas, vilket är en fråga för användaren (disken).
- **Del 2, händelserna:** valet "Se verifiering för extremhändelser" någonstans i fliken, med prognosen (Tim-KNEP, persistensen och jämförelserna), analysen (A0, A1, A2T) och måtten framkörda för varje svensk händelse (Hans i augusti 2023, Johannes), fliken Händelser bort och de gamla utländska testfallen dolda. Det kräver framkörda fall och därmed disk (ledigt på `/data` är under 3 GB), och händelser på dagar i testdelen får bara köras efter testdelen (beslut 5). Diagrammen här (ledtiden som axel, en linje per modell) bör gå att återanvända för en händelse, med perioden satt till händelsens dygn.

Status: delvis
