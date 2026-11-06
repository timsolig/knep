# Idéer

Kandidaterna som planeraren väljer från, ungefär i den ordning de ger mest nu. Varje idé har förväntad nytta, kostnad och risk. Det som är avgjort flyttas till **Avgjort** med en rad om utfallet och en länk till rapporten.

## Öppna

- **A1 utan underskott på lovartsidan** (mål 1). A1 ger 2 till 3 % mindre regn på lovartsidan med intervallet helt på fel sida, mest 2023-08-08 och 2021-10-20; troligen flyttar interpoleringen regn som står still vid sluttningen. Kördes som uppgift 6 natten mot 2026-11-07 (`experiments/natt/rapporter/2026-11-07/6-lovart.md`); läs utfallet först. Nytta stor (A1 blir bättre än A0), kostnad 2 till 3 h.
- **A2 och artefaktfiltret** (mål 1). Första versionerna kördes 2026-11-06 (uppgift 3 och 4 i `experiments/natt/rapporter/2026-11-06/`). Fortsätt där de slutade.
- **Fast klotter från Markbygden** (65,4 N 20,6 E, upp till 118 mm/h i varje bild) ligger i A0 och i facit och gynnar persistensen. Filtret ska ta det; kontrollera också vad det gör med verifieringen. Nytta stor för verifieringen, kostnad liten om filtret finns.
- **bias-v1** (mål 2). Radarn 2023 till 2025 hämtas om till `/work/cache/bias/` (klart cirka 2026-11-07). Kör `knep-bias fit --cv` när underlaget är komplett, granska, skriv rekommendationen. Släppet gör användaren. Kostnad några timmar processor.
- **Inflode25 utan överskott tidigt** (mål 3). Platskartan ska inte förstärka de högsta intensiteterna. Kördes som uppgift 7 natten mot 2026-11-07 (`experiments/natt/rapporter/2026-11-07/7-inflode.md`); läs utfallet först.
- **Tim-KNEP vid +1 h** (mål 4). Mot radarn är CSI vid 0,1 mm som persistensen. MET Norge är sämre än persistens vid +1 h utan att något fel hittats i `compare.py`. Gör om med A2 som facit när den finns.
- **Molnmask från FCI** (mål 5). Väntar på EUMETSAT:s allmänna licens (se Frågor till användaren i `MAL.md`).
- **max_age vid bortfall** (mål 6). Kandidaterna bedöms på prognosen.

## Avgjort

- **MEPS i blandningen** (somlos, MEPS i hålet): strider mot principen om bara observationer (användarens beslut 2026-11-06). Spåret är nerlagt; koden ligger i `experiments/meps/` för jämförelse.
