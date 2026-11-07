# Idéer

Kandidaterna som planeraren väljer från, ungefär i den ordning de ger mest nu. Varje idé har förväntad nytta, kostnad och risk. Det som är avgjort flyttas till **Avgjort** med en rad om utfallet och en länk till rapporten.

## Öppna

- **A2 utan falska ekon per kvart i terrängen** (mål 1). A2 slår A0 i 15 mått och A1 i 14, men fälls mot A1 av falska ekon per kvart vid torra mätare över 400 m (0,016 mot 0,013) och på lovartsidan (0,019 mot 0,016). Troligen lyfter kvoten i stor skala (över 1 i fjällen) svaga ekon och klotter över tröskeln. Varianter: skala inte upp svaga rutor (kvoten bara där A1 är över en tröskel), torrmasken även över svagt eko när alla mätare nära är torra, F4 på A0 innan. Väljs på träningspunkterna (`a2.py punkter`/`trana`), bedöms på valideringen med A1:s sparade fält (`/data/analys/a2/a1falt/`, 3 till 4 min per dag). Nytta stor (första analys som slår A1, och A2 behövs som facit), kostnad 3 till 4 h, risk att vinsten i mängden krymper. Valideringen är sedd för A2 en gång, så bara en eller två frysta varianter får bedömas där.
- **Kontroll av mätarna i A2** (mål 1). Innovationen mot grannarna och radarn (till exempel över 3 standardavvikelser kastas). Krävs innan A2 blir facit i verifieringen. Nytta medel, kostnad 1 till 2 h. Kan tas i samma uppgift som ovan om tiden räcker, annars nästa.
- **bias-v1** (mål 2). Radarn 2023 till 2025 hämtas om till `/work/cache/bias/` (klart cirka 2026-11-07). Kör `knep-bias fit --cv` när underlaget är komplett, granska, skriv rekommendationen. Släppet gör användaren. Kostnad några timmar processor. Kontrollera först att hämtningen är klar.
- **F4 tränad på alla 28 träningsdagar** (mål 1). Urvalet gjordes på 13. Krävs innan kartan föreslås som modellfil. Nytta medel (för verifieringen och Markbygden), kostnad 1 till 2 h.
- **Fast klotter från Markbygden** (65,4 N 20,6 E, upp till 118 mm/h i varje bild) ligger i A0 och i facit och gynnar persistensen. Kontrollera att F4:s karta tar det och vad det gör med verifieringen (`verify.py` med och utan filtret på några dygn). Nytta stor för verifieringen, kostnad liten.
- **Prognosen: klippa ytan i stället för toppen** (mål 3). `loc_top` relativt det lokala maxet i ett 8 km-block, eller halverad positiv platskorrektion de första 30 min. Urvalet för toppmått på 2 km (nytt läge `snabb2`), eftersom blockmaxets försämring inte syntes på 4 km. Nytta medel, kostnad 3 till 4 h, risk att det går som `Topp10`.
- **A1 eller A1L1 på de 13 träningsdagar som saknas** (mål 1). Bara om ett val mellan A1 och A1L1 behövs; A1 utan `stay` står sig. Nytta liten nu, kostnad cirka 1,5 h (en process).
- **Tim-KNEP vid +1 h** (mål 4). Mot radarn är CSI vid 0,1 mm som persistensen. MET Norge är sämre än persistens vid +1 h utan att något fel hittats i `compare.py`. Gör om med A2 som facit när den finns.
- **Molnmask från FCI** (mål 5). Väntar på EUMETSAT:s allmänna licens (se Frågor till användaren i `MAL.md`).
- **max_age vid bortfall** (mål 6). Kandidaterna bedöms på prognosen.

## Avgjort

- **A1 utan underskott på lovartsidan** (uppgift 6, natten mot 2026-11-07): underskottet är utjämning av toppar i regn som rör sig fort, inte förlust av regn, och syns inte på 15 träningsdagar. A1M, A1S och A1L1 prövades; ingen slog A1. A1 står kvar utan `stay`. Frågan om domarens summakvot står under Frågor till användaren. [Rapporten](../natt/rapporter/2026-11-07/sammanfattning.md)
- **Inflode25Topp10** (uppgift 7, natten mot 2026-11-07): tar bort överskottet i ytan ≥ 10 mm/h men gör blockmaxets 90-percentil säkert sämre vid 30 min till 2 h (7 valideringsdygn). Inte bättre än kedjan. [Rapporten](../natt/rapporter/2026-11-07/sammanfattning.md)
- **MEPS i blandningen** (somlos, MEPS i hålet): strider mot principen om bara observationer (användarens beslut 2026-11-06). Spåret är nerlagt; koden ligger i `experiments/meps/` för jämförelse.
