# Uppdrag för nattkörningen

Du kör utan att någon svarar på frågor. Ingen läser det du skriver förrän i morgon bitti, så allt som ska fram skriver du i rapportfilerna. Fastnar du, välj det försiktigaste rimliga alternativet, skriv varför i rapporten och gå vidare.

## Målet

Den bästa nederbördsanalysen när radar saknas. Kompositen (`src/knep/composite.py`) fyller i dag ett bortfall med grannländernas radar (OPERA), enskilda radarvolymer och till sist förra analysen flyttad med rörelsen (`fill_gaps`), som jämnas ut med åldern. Frågan är vad som statistiskt ger bäst analys i hålet, och hur mycket det hjälper prognosen efteråt.

Analysen i hålet bedöms mot den riktiga radarn, som du har eftersom bortfallen simuleras på timmar där alla radarer fungerade. Regnmätarna är en oberoende kontroll.

## Data och indelning

- Radarn: `/data/radar/ÅÅÅÅ/MM/DD/`, SMHI:s komposit var 5:e minut. Läsning och hämtning finns i `experiments/sverige/data.py` och `src/knep/radar.py`.
- MEPS: `/data/meps/`, se `experiments/sverige/README.md`.
- Dagarna i `experiments/sverige/dagar.json` är frysta. **Delen `test` får du aldrig läsa, köra eller räkna på.** Delen `validering` är din validering.
- Träningsdagar väljer du själv ur `/data/sverige/kandidater.json`, men aldrig en dag som finns i `dagar.json` eller ligger inom två dygn från en sådan. Spara urvalet i `experiments/bortfall/traning.json` och ändra det inte efter att du har börjat utvärdera.
- Ny data hamnar under `/data/bortfall/` och `/data/radar/`. **Högst 2 GB ny data i natt**, och avbryt hämtningen om `df /data` visar mindre än 2 GB ledigt.

## Regler

- Arbeta bara i den här utcheckningen och på den gren du står på (`natt/<datum>`). Byt inte gren, och pusha, merga eller öppna inga PR:er. Driften följer `main` på GitHub och får aldrig röras.
- Ändra inte `deploy/`, `models/`, `.github/`, `experiments/sverige/dagar.json` eller filerna i `experiments/natt/` utom under `rapporter/`.
- Nytt arbete läggs i `experiments/bortfall/`. Ändringar i `src/knep/` är tillåtna om de behövs, med tester, men ska vara små och gå att läsa i en PR.
- `uv run pytest` ska gå igenom innan du committar. Committa ofta med tydliga meddelanden på svenska, så att inget arbete går förlorat om uppgiften avbryts.
- Pi:n delar processorn med driften, som ska bli klar med en cykel på under två minuter. Du körs redan med låg prioritet. Använd **högst två processer** i taget och högst cirka 2 GB minne. Kör en liten provkörning på några fall innan du startar en lång.
- Långa körningar startar du i bakgrunden med utdata till en loggfil och väntar på dem, i stället för att låta ett kommando gå i timmar i förgrunden.
- Text, kommentarer och rapporter på svenska, utan tankstreck som skiljetecken.

## Hur ett system bedöms

Domaren (`experiments/bortfall/domare.py`, byggs av uppgift 3) är den enda som avgör om något är bättre. Den kör ett system på valideringsfallen och skriver en tabell med:

- i hålet, efter bortfallets ålder (0 till 30, 30 till 90 och 90 till 360 min): FSS vid 1 och 5 mm/h på 10 och 30 km, CSI vid 0,5, 1 och 5 mm/h, och volymen mot radarn
- sömmen: hur mycket gradienten längs hålets kant avviker från radarns
- skillnaden mot baslinjen med 95 %-intervall från bootstrap över dagarna

Ett resultat räknas bara om intervallet ligger helt på den bättre sidan. Ändra inte domaren för att ett system ska se bättre ut. Behöver den rättas, skriv det i rapporten och kör om baslinjerna.

## Rapporter

Varje uppgift skriver `experiments/natt/rapporter/<datum>/<nr>-<kort namn>.md`: vad du gjorde, vad som fungerade och inte, siffrorna, vilka filer som ändrades och vad nästa steg är. Läs först de rapporter som redan finns för i natt, eftersom tidigare uppgifter kan ha lämnat saker halvfärdiga. Om en tidigare uppgift misslyckades, gör det som behövs av den innan du går vidare, eller skriv varför det inte gick.

Sist i varje rapport: en rad som börjar med `Status:` och sedan `klar`, `delvis` eller `misslyckad`.
