# Idéer

Kandidaterna som planeraren väljer från, ungefär i den ordning de ger mest nu. Varje idé har förväntad nytta, kostnad och risk. Det som är avgjort flyttas till **Avgjort** med en rad om utfallet och en länk till rapporten.

## Öppna

- **Kontroll av mätarna i A2T** (mål 1). Innovationen mot grannarna (och mot radarn där den är säker) över en tröskel i standardavvikelser kastas ur indata, vald på träningen. Utan den sprider OI ett fel i en mätare upp till cirka 40 km. Krävs innan A2T blir facit i verifieringen eller flyttas till `src/`. Nytta medel till stor (det sista som står mellan A2T och ett förslag till användaren), kostnad 2 till 3 h, risk att kontrollen kastar riktigt terrängregn som radarn inte ser; därför ska andelen kastade över 400 m och på lovartsidan redovisas. Valideringen är sedd för A2-familjen två gånger, så bara en fryst variant.
- **Kartmåttet och timmens svaga eko i A2T** (mål 1). Kartmåttet (47,2 rutor per dag mot A0:s 36,6) är det sämsta som är kvar och styrs av timmen, där `K_SVAG`/`SVAG_TAK` inte verkar. Pröva taket även per timme (`K_SVAG` cirka 0,5 mm) och F4:s bilder under A1 och A2T. Nytta medel, kostnad 2 till 3 h, risk att timmens kvot i terrängen sjunker.
- **Mängden i terrängen tillbaka i A2T** (mål 1). Taket tar bort riktigt svagt regn i fjällen (kvoten över 400 m per kvart 0,632 till 0,575). Ett tak bara för svagt eko som står still (klotter) eller där strålen ligger lågt över terrängen. Nytta medel, kostnad 3 h, risk liten (A2T är baslinjen att slå).
- **A2T till `src/knep/analys/a2.py` som avstängt val** (mål 1). Efter kontrollen av mätarna. Fyllning av `a2` i manifestet och användning som facit beslutar användaren. Nytta stor på sikt, kostnad 2 h med tester.
- **bias-v1** (mål 2). Radarn 2023 till 2025 hämtas om till `/work/cache/bias/` (klart cirka 2026-11-07). Kör `knep-bias fit --cv` när underlaget är komplett, granska, skriv rekommendationen. Släppet gör användaren. Kostnad några timmar processor. Kontrollera först att hämtningen är klar.
- **F4 tränad på alla 28 träningsdagar** (mål 1). Urvalet gjordes på 13. Krävs innan kartan föreslås som modellfil. Nytta medel (för verifieringen och Markbygden), kostnad 1 till 2 h.
- **Fast klotter från Markbygden** (65,4 N 20,6 E, upp till 118 mm/h i varje bild) ligger i A0 och i facit och gynnar persistensen. Kontrollera att F4:s karta tar det och vad det gör med verifieringen (`verify.py` med och utan filtret på några dygn). Nytta stor för verifieringen, kostnad liten.
- **Prognosen: klippa ytan i stället för toppen** (mål 3). `loc_top` relativt det lokala maxet i ett 8 km-block, eller halverad positiv platskorrektion de första 30 min. Urvalet för toppmått på 2 km (nytt läge `snabb2`), eftersom blockmaxets försämring inte syntes på 4 km. Nytta medel, kostnad 3 till 4 h, risk att det går som `Topp10`.
- **A1 eller A1L1 på de 13 träningsdagar som saknas** (mål 1). Bara om ett val mellan A1 och A1L1 behövs; A1 utan `stay` står sig. Nytta liten nu, kostnad cirka 1,5 h (en process).
- **Tim-KNEP vid +1 h** (mål 4). Mot radarn är CSI vid 0,1 mm som persistensen. MET Norge är sämre än persistens vid +1 h utan att något fel hittats i `compare.py`. Gör om med A2 som facit när den finns.
- **Molnmask från FCI** (mål 5). Väntar på EUMETSAT:s allmänna licens (se Frågor till användaren i `MAL.md`).
- **max_age vid bortfall** (mål 6). Kandidaterna bedöms på prognosen.

## Avgjort

- **A2 utan falska ekon per kvart i terrängen** (uppgift 0001, 2026-11-07): A2T (ingen uppskalning och tak över svagt eko under 0,125 mm per kvart) slår både A0 och A1 enligt domaren på valideringen utan att något mått blir sämre; falskt per kvart över 400 m 0,0118 mot A1:s 0,0133. Priset är lägre kvot i terrängen per kvart än A2. Torrmasken över svagt eko (`TORR2`) gav inget. [Rapporten](rapporter/2026-11-07/0001-a2-falska-ekon.md)

- **A1 utan underskott på lovartsidan** (uppgift 6, natten mot 2026-11-07): underskottet är utjämning av toppar i regn som rör sig fort, inte förlust av regn, och syns inte på 15 träningsdagar. A1M, A1S och A1L1 prövades; ingen slog A1. A1 står kvar utan `stay`. Frågan om domarens summakvot står under Frågor till användaren. [Rapporten](../natt/rapporter/2026-11-07/sammanfattning.md)
- **Inflode25Topp10** (uppgift 7, natten mot 2026-11-07): tar bort överskottet i ytan ≥ 10 mm/h men gör blockmaxets 90-percentil säkert sämre vid 30 min till 2 h (7 valideringsdygn). Inte bättre än kedjan. [Rapporten](../natt/rapporter/2026-11-07/sammanfattning.md)
- **MEPS i blandningen** (somlos, MEPS i hålet): strider mot principen om bara observationer (användarens beslut 2026-11-06). Spåret är nerlagt; koden ligger i `experiments/meps/` för jämförelse.
