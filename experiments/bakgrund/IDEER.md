# Idéer

Kandidaterna som planeraren väljer från, ungefär i den ordning de ger mest nu. Varje idé har förväntad nytta, kostnad och risk. Det som är avgjort flyttas till **Avgjort** med en rad om utfallet och en länk till rapporten.

## Öppna

- **En smalare kontroll av mätarna i A2T** (mål 1). A2TK fälldes mot A2T eftersom 9 av 10 kastade perioder var för våta mätare, alltså verkliga skurtoppar. Kasta en för våt mätare bara där A1 är helt torr i rutan och omgivningen och grannarna är torra, och en för torr mätare där grannarna och radarn är tydligt våta. Lägg till en kontroll per station och dygn (station 2214807: 2 mm per kvart utan eko i 81 kvartar 2024-04-14). Välj på träningen med `a2.py varianter_qc` och de syntetiska felen, med kravet att summakvoten och FSS inte sjunker mot A2T på träningen. Nytta medel (skydd för facit), kostnad 2 till 3 h, risk att den inte hittar mer än A2TK. Valideringen är sedd tre gånger för A2-familjen.
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

- **Kontrollen av mätarna i A2T, A2TK** (uppgift 0002, 2026-11-07): mot grannarna inom 50 km och bakgrunden, T = 3 per kvart och 2,5 per timme, kastar 0,1 % av perioderna och inget över 400 m. Den slår A1 och A0 men är sämre än A2T med intervallet helt på fel sida i summakvoten och FSS (kvart kvot 0,846 mot 0,851, FSS 1 0,389 mot 0,392); bättre bara i MAE. Den hittar 3 till 20 % av 1 % syntetiska fel och en trasig station. A2T står kvar. [Rapporten](rapporter/2026-11-07/0002-a2t-kontroll-matare.md)

- **A2 utan falska ekon per kvart i terrängen** (uppgift 0001, 2026-11-07): A2T (ingen uppskalning och tak över svagt eko under 0,125 mm per kvart) slår både A0 och A1 enligt domaren på valideringen utan att något mått blir sämre; falskt per kvart över 400 m 0,0118 mot A1:s 0,0133. Priset är lägre kvot i terrängen per kvart än A2. Torrmasken över svagt eko (`TORR2`) gav inget. [Rapporten](rapporter/2026-11-07/0001-a2-falska-ekon.md)

- **A1 utan underskott på lovartsidan** (uppgift 6, natten mot 2026-11-07): underskottet är utjämning av toppar i regn som rör sig fort, inte förlust av regn, och syns inte på 15 träningsdagar. A1M, A1S och A1L1 prövades; ingen slog A1. A1 står kvar utan `stay`. Frågan om domarens summakvot står under Frågor till användaren. [Rapporten](../natt/rapporter/2026-11-07/sammanfattning.md)
- **Inflode25Topp10** (uppgift 7, natten mot 2026-11-07): tar bort överskottet i ytan ≥ 10 mm/h men gör blockmaxets 90-percentil säkert sämre vid 30 min till 2 h (7 valideringsdygn). Inte bättre än kedjan. [Rapporten](../natt/rapporter/2026-11-07/sammanfattning.md)
- **MEPS i blandningen** (somlos, MEPS i hålet): strider mot principen om bara observationer (användarens beslut 2026-11-06). Spåret är nerlagt; koden ligger i `experiments/meps/` för jämförelse.
