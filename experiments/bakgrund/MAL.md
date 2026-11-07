# Målen för bakgrunden

Planeraren läser den här filen före varje uppgift. Användaren äger **Principer**. Planeraren får ändra **Prioriteringar** när resultaten säger att något annat är viktigare, och skriver då varför under **Ändringar**. Frågor som bara användaren kan avgöra står under **Frågor till användaren**.

## Principer

Ändras bara av användaren. De står också i `uppdrag.md` och gäller före prioriteringarna.

- Tim-KNEP bygger bara på observationer: radar, regnmätare och satellit. Ingen vädermodell i analysen eller prognosen; MEPS och SNOW finns bara som jämförelse. Kedjan går till 5 h.
- Domaren avgör, på valideringen, med intervall. Testdelen rörs aldrig.
- Inget släpps i drift utan användaren. Bakgrunden föreslår, användaren beslutar.

## Prioriteringar

1. **Analysen slår A0 och A1, och blir ett facit.** A2T slår både A0 och A1 enligt domaren på valideringen (2026-11-07). Det som återstår innan den kan föreslås: kontrollen av mätarna (ett fel i en mätare sprids annars upp till 40 km), sedan kartmåttet per timme och mängden i terrängen som taket tar bort, och därefter A2T som avstängt val i `src/`. A1:s underskott på lovartsidan visade sig vara utjämning av toppar, inte förlust av regn. Filtret F4 mot fast klotter (bland annat vindkraftsparker) är godkänt mot A0. A2 behövs också som facit i verifieringen, eftersom radarn bara ser en liten del av de våta mätartimmarna i november, och kräver då en kontroll av mätarna.
2. **Träningen av modellerna.** Volymkorrektionen `bias-v1`: när underlaget i `/work/cache/bias/` är komplett, kör `knep-bias fit --cv`, granska mot mätarna och skriv en rekommendation om släpp. Sedan platskartan och rörelsefältet, om domaren visar att de håller tillbaka prognosen.
3. **Prognosen tappar inte extremerna.** Kedjans konservering: `Inflode25` utan överskottet de första 30 minuterna (att klippa toppen, `Topp10`, fälldes av blockmaxet; nästa försök klipper ytan och väljs på 2 km), och närmaste granne efter 3 h (`NarmastRamp3`).
4. **Prognosen vid de korta ledtiderna.** Varför Tim-KNEP och MET Norge ligger nära eller under persistensen vid +1 h, med A2 som facit när den finns.
5. **Satelliten i analysen.** Molnmasken från MTG FCI som stöd för torrmasken och artefaktfiltret (eko där satelliten säger molnfritt). Hämta bara nordliga utsnitt.
6. **Robust vid radarbortfall.** Kandidaterna för `max_age` vid bortfall bedöms på prognosen.

## Frågor till användaren

- EUMETSAT: realtidslicensen verkar godkänd, men den allmänna licensen saknas fortfarande (2026-11-06). Arkivet går inte att hämta förrän den är godkänd.
- Analysens domare: summakvoten belönar för höga toppar vid enstaka mätare så länge radarn i stort är för torr (det fällde F1 och gav A1 dess "underskott" på lovartsidan). Ska den kompletteras, till exempel med kvoten för perioder då mätaren har regn, och baslinjerna köras om? Bakgrunden ändrar inte domaren utan ditt beslut. (2026-11-07)
- Testdelen: vill du att baslinjerna (A0, A1, kedjan) och F4 körs på testdelen? Kommandona och den lilla upplåsningen står i `experiments/natt/rapporter/2026-11-06/5-sammanfattning.md` och `2026-11-07/sammanfattning.md`. (2026-11-07)
- A2T (A2 utan uppskalning och med tak över svagt eko per kvart) slår både A0 och A1 enligt domaren på valideringen (`rapporter/2026-11-07/0001-a2-falska-ekon.md`). Rekommendationen är att först lägga till kontrollen av mätarna och sedan flytta den till `src/knep/analys/` som ett avstängt val; att visa den som A2 på sidan eller använda den som facit i verifieringen beslutar du. (2026-11-07)
- F4:s klotterkarta som modellfil (`--klotter`): godkänd av domaren mot A0 men med liten vinst vid mätarna. Rekommendationen är att träna om den på alla 28 träningsdagar och köra testdelen före ett släpp. (2026-11-07)

## Ändringar

- 2026-11-07 08:30: mål 1 skrivet om efter uppgift 0001: A2T slår A0 och A1, så målet är nu att göra A2T färdig som analys och facit (kontrollen av mätarna först). Ordningen är oförändrad; mål 2 (`bias-v1`) står näst i tur när A2T:s kontroll av mätarna är klar eller om underlaget i `/work/cache/bias/` visar sig komplett.

- 2026-11-07: mål 1 skrivet om efter natten mot 2026-11-07: A1:s underskott på lovartsidan är utjämning av toppar och inte ett fel att rätta, så A2 (som redan slår A0 och bara fälls mot A1 av falska ekon per kvart i terrängen) är nu det spår som närmast ger en analys som slår båda baslinjerna. Mål 3 fick utfallet för `Topp10`. Ordningen är oförändrad.
- 2026-11-06: första versionen, skriven av användaren och Claude när bakgrunden blev en loop som går dygnet runt.
