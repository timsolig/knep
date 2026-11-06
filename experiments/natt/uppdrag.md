# Uppdrag för nattkörningen

Du kör utan att någon svarar på frågor. Ingen läser det du skriver förrän i morgon bitti, så allt som ska fram skriver du i rapportfilerna. Fastnar du, välj det försiktigaste rimliga alternativet, skriv varför i rapporten och gå vidare.

## Målet

Projektionen ska konservera nederbörden över ledtiderna, så att extremvärdena inte tappas på längre ledtider.

Kedjan (`src/knep/model.py`, `Chain.run`) flyttar i dag analysen med Lucas-Kanade och semi-Lagrangesk extrapolering (`advect.py`, samma schema som pysteps). Varje bild matchas mot fördelningen hos analysen flyttad med närmaste granne, platskartan läggs på, och för de första 2 h lägger extremmodellen till sina sannolikheter. Efter det blandar `seamless.py` in MEPS rättad mot radarn, med en vikt som avtar med ledtiden. Kvantilerna blandas med samma vikt.

Det vi vet: ytan över 5 mm/h krymper till ungefär 0,8 av radarns vid 60 min (`experiments/README.md`). I den sömlösa prognosen faller effekten i bandet 4 till 8 km till ungefär −3,6 i log kvot vid 5 h (`experiments/sverige/form_validering.md`, i `/work`; kopiera den om du behöver den). Frågan för natten är var extremerna försvinner, i vilket steg och vid vilken ledtid, och vilken projektion, matchning eller blandning som håller kvar dem utan att träffsäkerheten blir sämre.

pysteps är bara referens. Metoden är fri så länge den går att köra på Pi:n: hela Sverige, en cykel klar på under två minuter, ingen GPU. Det billiga föredras: mellanled som sparas och återanvänds, vikter i sluten form (minsta kvadrat), få parametrar med slumpsökning och successiv halvering (först på 4 km och ett urval träningsdagar, sedan finalisterna på 2 km), och HistGradientBoosting med slumpade pixlar och två trådar när det behöver vara olinjärt. Lägg inte till nya beroenden.

## Data och indelning

- Radarn: `/data/radar/ÅÅÅÅ/MM/DD/`, SMHI:s komposit var 5:e minut. Läsning finns i `experiments/sverige/data.py` och `src/knep/radar.py`.
- MEPS: `/data/meps/`, se `experiments/sverige/README.md`.
- Kedjans prognoser i drift för valideringsdagarna finns redan i `/data/sverige/kedja/` (`experiments/sverige/kedja.py`). Använd dem som baslinje där formatet räcker.
- Dagarna i `experiments/sverige/dagar.json` är frysta. **Delen `test` får du aldrig läsa, köra eller räkna på.** Delen `validering` är din validering.
- Träningsdagarna är gårdagens 28 dagar: `git show natt/2026-11-03:experiments/bortfall/traning.json`. Radarn för dem finns redan i `/data/radar/`. Kopiera listan till `experiments/projektion/traning.json` och ändra den inte. Allt som väljs eller tränas (parametrar, vikter, modeller) väljs på träningsdagarna. Valideringen bedömer.
- Höjdmodellen: Copernicus GLO-90 är öppen. Läs den med rasterio direkt från nätet (`/vsicurl/` mot de öppna COG-filerna, med översiktsnivåerna eller fönster), skala ned till radarns rutnät och spara bara resultatet, några MB, under `/data/projektion/`. Spara aldrig hela rutor på disken.
- Ny data hamnar under `/data/projektion/`. **Högst 1 GB ny data i natt**, och avbryt om `df /data` visar mindre än 2 GB ledigt.

## Regler

- Arbeta bara i den här utcheckningen och på den gren du står på (`natt/<datum>`). Byt inte gren, och pusha, merga eller öppna inga PR:er. Driften följer `main` på GitHub och får aldrig röras.
- Ändra inte `deploy/`, `models/`, `.github/`, `experiments/sverige/dagar.json` eller filerna i `experiments/natt/` utom under `rapporter/`.
- Nytt arbete läggs i `experiments/projektion/`. Ändringar i `src/knep/` är tillåtna om de behövs, med tester, men ska vara små och gå att läsa i en PR. Kedjan i drift ska fortsätta fungera som förut, så nya varianter läggs till som val och standardvärdet ändras inte.
- `uv run pytest` ska gå igenom innan du committar. Committa ofta med tydliga meddelanden på svenska, så att inget arbete går förlorat om uppgiften avbryts.
- Pi:n delar processorn med driften. Du körs redan med låg prioritet. Använd **högst två processer** i taget och högst cirka 2 GB minne. Kör en liten provkörning innan du startar en lång.
- Långa körningar startar du i bakgrunden med utdata till en loggfil och väntar på dem, i stället för att låta ett kommando gå i timmar i förgrunden.
- Text, kommentarer och rapporter på svenska, utan tankstreck som skiljetecken.

## Hur ett system bedöms

Domaren (`experiments/projektion/domare.py`, byggs av uppgift 1) är den enda som avgör om något är bättre. Ett system ger prognoser i mm/h per kvart, från 15 min till 5 h, för ett antal utgåvetider per dag. Domaren jämför mot radarn på de rutor där radarn har data, och redovisar per ledtid (minst 15 min, 30 min, 1, 2, 3 och 5 h):

- **Konserveringen**: kvoten mot radarn för 99- och 99,9-percentilen av de våta rutorna, för ytan över 5, 10 och 20 mm/h, och för volymen; dessutom fördelningen av maxvärdet i block om 30 km.
- **Träffen för det kraftiga**: FSS vid 5 och 10 mm/h på 10 och 30 km, CSI vid 5 mm/h och SEDI vid 5 och 10 mm/h.
- **Spärrarna**: FSS vid 1 mm/h på 30 km, CSI vid 1 mm/h, formen (effekten i banden 4 till 8 och 8 till 16 km, `experiments/sverige/form.py`) och hoppen mellan utgåvor för samma giltighetstid (`form.jump`).
- Skillnaden mot baslinjen `kedja` (driften) med 95 %-intervall från bootstrap över dagarna.

Ett system räknas som bättre bara om konserveringen blir bättre (|log kvot| mindre, intervallet helt på den bättre sidan) och FSS eller CSI för det kraftiga inte blir sämre, samtidigt som ingen spärr blir sämre med intervallet helt på fel sida. Att bara blåsa upp topparna ger rätt percentiler men sämre FSS och falsklarm, och det ska domaren visa. Ändra inte domaren för att ett system ska se bättre ut. Behöver den rättas, skriv det i rapporten och kör om baslinjerna.

## Rapporter

Varje uppgift skriver `experiments/natt/rapporter/<datum>/<nr>-<kort namn>.md`: vad du gjorde, vad som fungerade och inte, siffrorna, vilka filer som ändrades och vad nästa steg är. Läs först de rapporter som redan finns för i natt, eftersom tidigare uppgifter kan ha lämnat saker halvfärdiga. Om en tidigare uppgift misslyckades, gör det som behövs av den innan du går vidare, eller skriv varför det inte gick.

Sist i varje rapport: en rad som börjar med `Status:` och sedan `klar`, `delvis` eller `misslyckad`.
