# Veckans genomgång

Instruktionen för den schemalagda sessionen, en gång i veckan med Opus. Kön (`ko.py`, tjänsten `knep-ko`) räknar utan Claude resten av tiden; den här sessionen är den enda som tänker, så den ska vara kort och göra det som en maskin inte kan: välja vad som är värt att räkna.

## Läs, i den här ordningen

1. `/data/ko/SAMMANFATTNING.md` (skrivs av kön). Läs inte råa loggar om inte ett experiment slutade med fel.
2. `experiments/ko/SPAR.md`, reglerna och spåren.
3. De resultatfiler i `/data/ko/resultat/` som har domen bättre eller status fel.

## Gör

1. **Slå ihop det som visat en förbättring.** Användaren (2026-11-18): allt som har visat en förbättring får slås ihop utan att fråga, också att slå på ett val och att släppa en modell. Bättre betyder domarens regel på valideringen (`"battre": true`). Ett val som är bättre på valideringen slås på i `deploy/cycle.sh` i en egen PR. En ny modell (till exempel `bias-v1` eller F4:s karta) släpps med `deploy/release_model.sh` och låses i `models/models.json` när den är bättre på valideringen; användarens beslut går här före regeln i `CLAUDE.md` om ett fryst testset, så länge driften är avstängd. Driften är avstängd sedan 2026-11-11, så ingen publicering väntas in.
2. **Laga det som gick fel** (status fel eller tidsgräns): rätta experimentfilen eller koden, ta bort resultatfilen och låt kön köra om.
3. **Ompröva spåren enligt reglerna i `SPAR.md`**: budget, mättat, en tredjedel till andra spår, var fjärde vecka från grunden. Uppdatera tabellerna.
4. **Fyll på kön för minst en vecka** (Pi:n räknar cirka 150 processortimmar i veckan med tre kärnor). Kön blev tom på ett halvt dygn första veckan, så lägg hellre för mycket: varje kandidat på `snabb` och på `traning` (28 dagar ger säkrare intervall), och valideringen direkt efter med `"om_battre": [träningens id]`, så att den bara körs när träningen säger bättre. Prioritera kandidater med stort tak bakom sig framför finjusteringar. Bara en frusen kandidat körs på `validering`, en gång per spår och kandidat, med `"ref": "kedja_om"` för kedjans varianter. Testdelen körs aldrig. Skriv ny kod för ett nytt spår om det behövs, med test.
5. **Städa löpande** (användaren 2026-11-18: data och gammal dokumentation som inte längre är relevant får tas bort utan att fråga). Ta bort det som hör till stängda spår och inte behövs för en baslinje: dagfiler för fällda varianter under `/data/analys/domare_v2/` och `/data/projektion/domare/`, mellanresultat och bilder från experiment som är avgjorda, gamla loggar i `/data/ko/logg/`, och dokumentation som beskriver något som inte finns längre. Behåll alltid radararkivet (`/data/radar/`), mätarna (`/data/bortfall/matare/`, `/work/cache/bias/`), baslinjernas dagfiler (A0, A1, A2T, F4, `kedja`, `kedja_om`, `persistens`), rörelsecachen, modellerna, rapporterna och allt som kön har kvar att köra. Skriv i rapporten vad som togs bort och hur mycket plats det gav. Kön pausar själv under 1,5 GB ledigt.
6. **Committa** kön, koden och `SPAR.md` på en gren, `uv run pytest`, PR mot `main`, `gh pr merge --auto --merge --delete-branch`. Kön hämtar `main` själv mellan experimenten.
7. **Rapportera kort till användaren**: vad kön gav i veckan, vad som slogs ihop, vilka spår som stängdes eller öppnades och varför, och om något väntar på användaren.

## Experimentfilen

`experiments/ko/ko/<nummer>-<namn>.json`, se docstringen i `ko.py`. Namnet bestämmer ordningen. Ett system med parametrar får ett eget namn per variant (resultaten sparas per systemnamn), så att två varianter aldrig skriver över varandra. `max_min` är tidsgränsen för hela experimentet.

## Gränser

- Bara observationer i analysen och prognosen (principerna i `CLAUDE.md`).
- Ändra aldrig en domare för att ett system ska se bättre ut, och kör aldrig testdelen.
- Håll sessionen kort: läs sammanfattningen, inte loggarna.
- Repot är publikt. Före varje push: `git diff origin/main...HEAD` får inte innehålla något ur `~/.bakgrund/lokala-ord.txt` eller sökvägarna i `~/.bakgrund/lokala-spärrar.txt`, inget ur `extern/` och ingen nyckel ur `~/.config/eumetsat/`.
