# Målen för bakgrunden

Planeraren läser den här filen före varje uppgift. Användaren äger **Principer**. Planeraren får ändra **Prioriteringar** när resultaten säger att något annat är viktigare, och skriver då varför under **Ändringar**. Frågor som bara användaren kan avgöra står under **Frågor till användaren**.

## Principer

Ändras bara av användaren. De står också i `uppdrag.md` och gäller före prioriteringarna.

- Tim-KNEP bygger bara på observationer: radar, regnmätare och satellit. Ingen vädermodell i analysen eller prognosen; MEPS och SNOW finns bara som jämförelse. Kedjan går till 5 h.
- Domaren avgör, på valideringen, med intervall. Testdelen rörs aldrig.
- Inget släpps i drift utan användaren. Bakgrunden föreslår, användaren beslutar.

## Prioriteringar

1. **Analysen slår A0.** A1 är bättre per kvart och timme men fälls av underskottet på lovartsidan. Rätta det, bygg A2 mot mätarna och filtret mot artefakterna (bland annat fast klotter från vindkraftsparker) tills något säkert slår A0 utan att terrängen blir sämre. A2 behövs också som facit i verifieringen, eftersom radarn bara ser en liten del av de våta mätartimmarna i november.
2. **Träningen av modellerna.** Volymkorrektionen `bias-v1`: när underlaget i `/work/cache/bias/` är komplett, kör `knep-bias fit --cv`, granska mot mätarna och skriv en rekommendation om släpp. Sedan platskartan och rörelsefältet, om domaren visar att de håller tillbaka prognosen.
3. **Prognosen tappar inte extremerna.** Kedjans konservering: `Inflode25` utan överskottet de första 30 minuterna, och närmaste granne efter 3 h (`NarmastRamp3`).
4. **Prognosen vid de korta ledtiderna.** Varför Tim-KNEP och MET Norge ligger nära eller under persistensen vid +1 h, med A2 som facit när den finns.
5. **Satelliten i analysen.** Molnmasken från MTG FCI som stöd för torrmasken och artefaktfiltret (eko där satelliten säger molnfritt). Hämta bara nordliga utsnitt.
6. **Robust vid radarbortfall.** Kandidaterna för `max_age` vid bortfall bedöms på prognosen.

## Frågor till användaren

- EUMETSAT: realtidslicensen verkar godkänd, men den allmänna licensen saknas fortfarande (2026-11-06). Arkivet går inte att hämta förrän den är godkänd.

## Ändringar

- 2026-11-06: första versionen, skriven av användaren och Claude när bakgrunden blev en loop som går dygnet runt.
