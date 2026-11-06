# Uppdrag för bakgrundskörningen: analysen

Du kör utan att någon svarar på frågor. Ingen läser det du skriver förrän körningen är slut, så allt som ska fram skriver du i rapportfilerna. Fastnar du, välj det försiktigaste rimliga alternativet, skriv varför i rapporten och gå vidare.

## Målet

Tim-KNEP delas i en **analys** och en **prognos** (`src/knep/analys/` och `src/knep/prognos/`). Analysen ska byggas i tre nivåer, som visas bredvid varandra i fliken Analys på sidan:

- **A0**, realtid: SMHI:s komposit med reserverna vid bortfall (`composite.py`, `sources.py`) och volymkorrektionen (`bias.py`). Det är kedjans start. I dag finns ingen egen kontroll av radarns artefakter: det SMHI inte har tagit bort följer med.
- **A1**, kvart och timme: varje 5-minutersintervall interpolerat längs rörelsen (`src/knep/analys/a1.py`), så att rörliga celler inte blir pärlband. Finns i drift.
- **A2**, rättad mot regnmätarna: klar 1 till 2,5 h efter timmen. Finns inte. Den ska bli facit i verifieringen i stället för rå radar, så den måste vara bevisat bättre än A0 och A1 mot mätare som den inte har sett.

Två problem ska lösas, i den här ordningen:

1. **En domare för analysen**, som avgör om en analys är bättre än en annan. Utan den kan inget av det andra bedömas.
2. **Radarns artefakter** (fast klotter, havsklotter, vindkraftverk, ekrar från en radar, solstrålar, isolerade prickar, anaprop) ska bort ur A0, **utan att den nederbörd som är bunden till terrängen försvinner**. Det är det svåra: ett fast eko ser ut som orografisk nederbörd. En klimatologisk mask som tar bort rutor som ofta är våta tar bort båda, och det får inte hända. Skilj dem åt med det som skiljer dem: klotter står still även när rörelsefältet säger att allt annat rör sig, har en egen textur och tidsvariation, finns när mätarna och satellitens molnmask säger torrt, och sitter på samma plats i alla väderlägen. Orografisk nederbörd hänger ihop med lyftet (vinden mot sluttningen) och med det övriga regnet.

pysteps och cheddar är bara referenser i tanken. Metoden är fri så länge den går att köra på Pi:n i varje cykel (A0) eller en gång i timmen (A2), utan GPU och utan nya beroenden. Det billiga föredras: klimatologier och kartor som räknas en gång och sparas, slutna former (minsta kvadrat, optimal interpolation med numpy och scipy), få parametrar.

## Data och indelning

- Radarn: `/data/radar/ÅÅÅÅ/MM/DD/`, SMHI:s komposit var 5:e minut, för de frysta dagarna och träningsdagarna. Läsning i `src/knep/analys/radar.py` och `experiments/sverige/data.py`.
- Regnmätarna: `/data/bortfall/matare/p7.npz` (timsumma) och `p14.npz` (kvartssumma) för dagarna i arkivet (station, lat, lon, tid, mm). Mätarnas timarkiv för alla stationer och år finns i volymkorrektionens lager, `/work/cache/bias/gauge_ÅÅÅÅMMDD.npz` (läs med `knep.analys.bias.Store`); det fylls fortfarande på och får bara läsas.
- MEPS: `/data/meps/`, se `experiments/sverige/README.md`.
- Höjdmodellen GLO-90 på radarns rutnät finns redan under `/data/projektion/` (uppgift 4 natten 2026-11-04, `experiments/projektion/terrang.py`).
- Satellitens molnmask: EUMETSAT:s öppna produkter får hämtas om de går att läsa utan konto; spara bara utsnitt på radarns rutnät.
- Dagarna i `experiments/sverige/dagar.json` är frysta. **Delen `test` får du aldrig läsa, köra eller räkna på**, inte heller mätarna för de dagarna. Delen `validering` är din validering. Träningsdagarna är `experiments/projektion/traning.json`. Allt som väljs eller tränas väljs på träningsdagarna, och valideringen bedömer.
- Ny data hamnar under `/data/analys/`. **Högst 1 GB ny data**, och avbryt om `df /data` visar mindre än 3 GB ledigt (driften och volymkorrektionen delar disken).

## Regler

- Arbeta bara i den här utcheckningen och på den gren du står på. Byt inte gren, och pusha, merga eller öppna inga PR:er. Driften följer `main` på GitHub och får aldrig röras.
- Ändra inte `deploy/`, `models/`, `.github/`, `experiments/sverige/dagar.json` eller filerna i `experiments/natt/` utom under `rapporter/`.
- Nytt arbete läggs i `experiments/analys/`. Ändringar i `src/knep/` är tillåtna om de behövs, med tester, men ska vara små och gå att läsa i en PR. Driften ska fungera som förut, så nya steg läggs till som val och standardvärdet ändras inte.
- `uv run pytest` ska gå igenom innan du committar. Committa ofta med tydliga meddelanden på svenska, så att inget arbete går förlorat om uppgiften avbryts.
- Pi:n delar processorn med driften. Du körs redan med låg prioritet. Använd **högst två processer** i taget och högst cirka 2 GB minne. Kör en liten provkörning innan du startar en lång. SMHI:s öppna data tillåter högst 40 anrop per 10 s från Pi:n, och driften behöver en del av dem: håll dig under 2 anrop per sekund.
- Långa körningar startar du i bakgrunden med utdata till en loggfil och väntar på dem, i stället för att låta ett kommando gå i timmar i förgrunden. Ge dem `timeout` på upp till 2 h.
- Text, kommentarer och rapporter på svenska, utan tankstreck som skiljetecken.

## Hur en analys bedöms

Domaren (`experiments/analys/domare.py`, byggs av uppgift 2) är den enda som avgör om något är bättre. En analys ger nederbörden per kvart och per timme på radarns rutnät för en dag. Domaren jämför mot regnmätarna med **korsvalidering**: mätarna delas i grupper efter plats (block, inte slumpvis, så att en grannmätare inte avslöjar svaret), och en analys som använder mätare (A2) får aldrig se gruppen den bedöms på. Analyser som inte använder mätare (A0, A1) bedöms på samma grupper. Domaren redovisar per upplösning (kvart och timme):

- **Mängden**: kvoten mot mätarna för summan och för timmar över 1, 5 och 10 mm, och MAE.
- **Träffen**: CSI och FSS mot mätarna vid 0,5, 1 och 5 mm.
- **Falska ekon**: andelen analyserat regn (över 0,5 mm per timme) vid mätare som är torra, särskilt där alla mätare inom 25 km är torra, och hur många rutor som har eko i mer än hälften av timmarna under torra timmar.
- **Terrängen**: samma mått för mätare över 400 m höjd och på lovartsidan av fjällen och sydsvenska höjdområdet för sig. Ett filter som tar bort artefakter får inte göra de här sämre.
- **Förändringen mellan kvartar**: att kvartarna i en timme inte hoppar mer än mätarnas.
- Skillnaden mot baslinjen A0 med 95 %-intervall från bootstrap över dagarna.

En analys räknas som bättre bara om mängden eller träffen blir bättre med intervallet helt på den bättre sidan, och falska ekon och terrängen inte blir sämre med intervallet helt på fel sida. Ändra inte domaren för att ett system ska se bättre ut. Behöver den rättas, skriv det i rapporten och kör om baslinjerna.

## Rapporter

Varje uppgift skriver `experiments/natt/rapporter/<datum>/<nr>-<kort namn>.md`: vad du gjorde, vad som fungerade och inte, siffrorna, vilka filer som ändrades och vad nästa steg är. Läs först de rapporter som redan finns för den här körningen, eftersom tidigare uppgifter kan ha lämnat saker halvfärdiga. Om en tidigare uppgift misslyckades, gör det som behövs av den innan du går vidare, eller skriv varför det inte gick.

Sist i varje rapport: en rad som börjar med `Status:` och sedan `klar`, `delvis` eller `misslyckad`.
