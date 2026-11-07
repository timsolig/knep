# Journalen

Vad bakgrunden har kört, nyast först. Loopen skriver en post efter varje uppgift: när, vad, varför planeraren valde den, resultatet i en mening, statusen och en länk till rapporten. Planeraren bedömer utfallet i `IDEER.md` och prioriterar om i `MAL.md`.

## Uppgifter

<!-- nya poster här -->

### 0002 · 2026-11-07 10:15 · a2t-kontroll-matare · klar
- Varför: A2T är den första analysen som slår både A0 och A1, och kontrollen av mätarna är det som står kvar innan den kan bli facit i verifieringen och föreslås som avstängt val i src/.
- Resultat: Kontrollen jämför varje mätare med grannarna inom R km och med A2T:s bakgrund och kastar den bara när båda säger emot. Med valda T = 3 och R = 50 km per kvart och T = 2,5 och R = 50 km per timme kastas 0,09 % av kvartarna och 0,11 % av timmarna på träningen, och ingen över 400 m. A2TK slår fortfarande A1 och A0 enligt domaren, men den kan inte ersätta A2T. Mot A2T är den bättre i MAE men sämre med intervallet helt på fel sida i bland annat summakvoten (kvart 0,846 mot 0,851, −0,006, −0,009 till −0,002) och FSS 1 per kvart (0,389 mot 0,392, −0,003, −0,006 till −0,001), eftersom 9 av 10 kastade perioder är för våta mätare, alltså verkliga skurtoppar.
- Rapport: [rapporter/2026-11-07/0002-a2t-kontroll-matare.md](rapporter/2026-11-07/0002-a2t-kontroll-matare.md), 116 min

### 0001 · 2026-11-07 08:17 · a2-falska-ekon · klar
- Varför: A2 slår redan A0 i 15 mått och A1 i 14 och fälls mot A1 bara av falska ekon per kvart i terrängen, så att rätta det är den kortaste vägen till en analys som slår båda baslinjerna och till ett facit för verifieringen.
- Resultat: A2T (ingen uppskalning och tak över svagt eko under 0,125 mm per kvart) slår A1 enligt domaren på valideringen utan att något mått blir sämre, och tar bort det som fällde A2: falskt vid torr mätare per kvart över 400 m går från A2:s 0,016 till 0,0118 mot A1:s 0,0133 (+0,0015, +0,0005 till +0,0025) och på lovartsidan till 0,0144 mot 0,0155 (+0,0011, +0,0001 till +0,0023); priset är en lägre summakvot i terrängen per kvart än A2 (0,575 mot 0,632 över 400 m, fortfarande långt över A1:s 0,475).
- Rapport: [rapporter/2026-11-07/0001-a2-falska-ekon.md](rapporter/2026-11-07/0001-a2-falska-ekon.md), 128 min

## Före loopen

Bakgrundskörningarna med en fast kö (`experiments/natt/`).

| Datum | Område | Uppgifter | Utfallet |
|---|---|---|---|
| natten mot 2026-11-07 | analysen och prognosen | lovart, inflode, sammanfattning2 | se [rapporterna](../natt/rapporter/2026-11-07/) |
| 2026-11-06 | analysen | artefakter, domare, a2, filter, sammanfattning | Analysens domare finns. A1 är bättre än A0 per kvart och timme men fälls av underskottet på lovartsidan. [Rapporterna](../natt/rapporter/2026-11-06/) |
| 2026-11-05 | verifieringen och prognosen | verif-persistens, somlos-5h | `verify.py` räknar rätt; facit (radarn) är svagt i november. Somlos var en MEPS-blandning och är nerlagd. [Rapporterna](../natt/rapporter/2026-11-05/) |
| 2026-11-04 | prognosens konservering | domare, förlust, konservering, terräng, sammanfattning | Inget slog kedjan. `Inflode25` och `NarmastRamp3` är värda att bygga vidare på. [Sammanfattningen](../natt/rapporter/2026-11-04/6-sammanfattning.md) |
| 2026-11-03 | radarbortfall | inventering, bortfallsfall, domare, MEPS i hålet, inlärd blandning | Bortfallets domare och fallen finns. [Rapporterna](../natt/rapporter/2026-11-03/) |
