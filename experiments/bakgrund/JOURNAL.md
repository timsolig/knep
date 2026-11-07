# Journalen

Vad bakgrunden har kört, nyast först. Loopen skriver en post efter varje uppgift: när, vad, varför planeraren valde den, resultatet i en mening, statusen och en länk till rapporten. Planeraren bedömer utfallet i `IDEER.md` och prioriterar om i `MAL.md`.

## Uppgifter

<!-- nya poster här -->

### 0006 · 2026-11-07 15:30 · kedjans-underskott-1h · klar
- Varför: Uppgift 0005 visade att kedjan har för lite regn i mätarnas rutor vid +1 h och att försprånget mot persistensen mot mätarna är minst där, och att köra kedjan utan platskarta och utan fördelningsmatchning på de redan sparade analyserna pekar ut vilken del av kedjan som ska rättas.
- Resultat: varken platskartan eller fördelningsmatchningen förklarar underskottet; utan platskartan blir kedjans kvot mot mätarna vid +1 h 0,920 och utan matchningen 0,919 mot kedjans 0,914 (skillnad +0,006, 95 % −0,015 till +0,043, och +0,005, −0,002 till +0,011), alltså under en tiondel av avståndet till 0,98; det mesta av "underskottet" är att radarn själv har kvoten 0,941 mot mätarna just de målen (kedjan är 0,971 av radarn vid mätarna), och resten av förlusten under första timmen sitter vid täckningens rand (kvoten mot radarn 0,778 vid +60 min inom 50 km från randen, 0,980 inne i området).
- Rapport: [rapporter/2026-11-07/0006-kedjans-underskott-1h.md](rapporter/2026-11-07/0006-kedjans-underskott-1h.md), 108 min

### 0005 · 2026-11-07 13:39 · prognos-mot-a2t-facit · klar
- Varför: A2T finns nu i src och i cykeln, och att räkna kedjan och persistensen mot A2T i stället för radarn svarar både på varför Tim-KNEP är svag mot persistensen vid +1 h (mål 4) och på om A2T duger som facit i verifieringen (mål 1).
- Resultat: på 15 träningsdagar (90 utgåvor) slår kedjan persistensen vid alla ledtider mot alla tre facit, men försprånget vid +1 h krymper när radarn byts mot A2T (CSI 1 mm +0,257 till +0,196, FSS 1 mm/10 km +0,253 till +0,204, MAE −0,084 till −0,066 mm) och mest mot mätarna (CSI 1 mm +0,105, 95 % +0,066 till +0,136, mindre än vid +2 h med +0,142); klottermasken (F4) ändrar skillnaden med högst 0,01, så klottret ger persistensen nästan ingenting på de här dagarna.
- Rapport: [rapporter/2026-11-07/0005-prognos-mot-a2t-facit.md](rapporter/2026-11-07/0005-prognos-mot-a2t-facit.md), 143 min

### 0004 · 2026-11-07 11:14 · a2t-i-cykeln · klar
- Varför: A2T slår A0 och A1 och finns nu i src, men ingen cykel räknar den; ett avstängt val --a2 i cli.py gör att visa A2 på sidan blir ett beslut om en flagga, utan att valideringen behöver ses igen.
- Resultat: valet `--a2` (av som standard) räknar nu A2T i cykeln ur A1:s sparade timsummor och mätarna i `gauges.json`, fyller `a2/` och `levels.a2` med kvart och timme bakåt, ger samma fält som `a2.A2T.timme` direkt (`np.array_equal` i testerna, PNG byte för byte i hela cykeln), och kostade i en provkörning på träningsdagen 2020-07-24 2,9 till 5,0 s extra i de cykler som räknar en timme och cirka 11 MB på disk.
- Rapport: [rapporter/2026-11-07/0004-a2t-i-cykeln.md](rapporter/2026-11-07/0004-a2t-i-cykeln.md), 22 min

### 0003 · 2026-11-07 10:50 · a2t-till-src · klar
- Varför: A2T är den enda analysen som slår både A0 och A1 enligt domaren, och att flytta den till src som ett avstängt val är nästa steg mot facit och sidan utan att valideringen behöver ses igen.
- Resultat: A2T finns nu som en liten, avstängd modul i `src/knep/analys/a2.py` som ger bit för bit samma fält som experimentet (`np.array_equal`, största skillnad 0 mm per kvart och per timme) på 8 syntetiska fall och på alla 24 timmar och 96 kvartar för tre träningsdagar, domaren ger exakt samma tal på 2020-07-24, och en timme med sina fyra kvartar tar 1,1 till 1,3 s på hela rutnätet på Pi:n med cirka 57 MB extra minne.
- Rapport: [rapporter/2026-11-07/0003-a2t-till-src.md](rapporter/2026-11-07/0003-a2t-till-src.md), 33 min

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
