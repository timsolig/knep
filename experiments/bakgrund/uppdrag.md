# Uppdrag för bakgrunden

Du kör utan att någon svarar på frågor, när som helst på dygnet. Ingen läser det du skriver förrän efteråt, så allt som ska fram skriver du i filerna: rapporten, och för planeraren `MAL.md` och `IDEER.md`. Fastnar du, välj det försiktigaste rimliga alternativet, skriv varför och gå vidare.

Bakgrunden går i varv. En planerare väljer nästa steg utifrån målen och det som redan är gjort, och en annan session gör uppgiften. Loopen skriver journalen, pushar grenen och håller en PR öppen. Du pushar aldrig själv.

## Projektet

Tim-KNEP är en nowcast för nederbörd över Sverige som bara bygger på observationer: radar, regnmätare och på sikt satellit. Den har en **analys** (`src/knep/analys/`) och en **prognos** (`src/knep/prognos/`, kedjan till 5 h).

- Analysen i tre nivåer: **A0** (SMHI:s komposit med reserverna vid bortfall och volymkorrektionen), **A1** (interpolerad längs rörelsen till kvart och timme, i drift) och **A2** (rättad mot regnmätarna, finns inte i drift). Radarns artefakter ska bort ur A0 utan att den nederbörd som är bunden till terrängen försvinner.
- Prognosen: kedjan med rörelsefält, platskarta och fördelningsmatchning. Problemen är främst att extremerna tappas med ledtiden och att Tim-KNEP är svag vid de korta ledtiderna mot persistensen.
- Volymkorrektionen (`bias.py`) tränas mot mätarna; `bias-v1` är inte släppt.

Läs `CLAUDE.md` i repots rot för hur koden hänger ihop.

## Principer

Principerna gäller före allt annat, också före `MAL.md`.

- **Bara observationer.** Ingen vädermodell (MEPS, SNOW eller någon annan) i analysen eller prognosen. Modellerna får bara användas som jämförelse. Föreslå inte att blanda in dem.
- **Domaren avgör.** Något är bättre bara om rätt domare säger det på valideringen, med intervallet helt på den bättre sidan och utan att spärrarna blir sämre. Ändra aldrig en domare för att ett system ska se bättre ut. Behöver den rättas, skriv det i rapporten och kör om baslinjerna.
- **Testdelen rörs aldrig.** Delen `test` i `experiments/sverige/dagar.json` får du aldrig läsa, köra eller räkna på, inte heller mätarna för de dagarna. Allt som väljs eller tränas väljs på träningsdagarna. Det enda undantaget är en körning som användaren uttryckligen har beslutat under **Användarens beslut** i `MAL.md`: då körs bara de system som står där, en gång, och inget väljs eller ändras efteråt utifrån testdelen.
- **Driften rörs aldrig.** Driften följer `main` på GitHub. Ett släpp av en modell, ett nytt standardvärde eller en ändring i `deploy/` beslutar användaren om. Ser något redo ut, skriv det som en rekommendation i rapporten och under Frågor till användaren i `MAL.md`.
- **Bara det här repot och arkivet.** Läs kod och text bara i den här utcheckningen, data under `/data/` och `/work/cache/`. Använd inget annat från `/work` eller `~/knep`, och citera inga andra repon. Repot är publikt.
- **Inga hemligheter i repot.** EUMETSAT-nyckeln ligger i `~/.config/eumetsat/credentials` (rad 1 nyckeln, rad 2 hemligheten). Läs den bara i kod som körs, och skriv aldrig ut den i en fil, en logg eller en rapport.

## Domarna

- **Analysen:** `experiments/analys/domare.py`. Korsvalidering i block mot regnmätarna; A0 och A1 som baslinjer. Den redovisar mängden, träffen, falska ekon, terrängen och förändringen mellan kvartar, med skillnaden mot A0 och 95 %-intervall från bootstrap över dagarna. En analys är bättre bara om mängden eller träffen blir bättre med intervallet helt på den bättre sidan, och falska ekon och terrängen inte blir sämre med intervallet helt på fel sida.
- **Prognosen:** `experiments/projektion/domare.py` (se docstringen för lägena `snabb`, `traning`, `validering`, `validering_gles`). Baslinjen är `kedja`. Sök i `snabb` eller `traning`, frys, och bedöm på `validering`.
- **Bortfall:** `experiments/bortfall/bortfallsdomare.py`.
- Rapporterna från tidigare körningar ligger i `experiments/natt/rapporter/` och `experiments/bakgrund/rapporter/`. Journalen `experiments/bakgrund/JOURNAL.md` pekar på dem.

## Data

- Radarn: `/data/radar/ÅÅÅÅ/MM/DD/`, SMHI:s komposit var 5:e minut. Läsning i `src/knep/analys/radar.py` och `experiments/sverige/data.py`.
- Regnmätarna: `/data/bortfall/matare/p7.npz` (timsumma) och `p14.npz` (kvartssumma). Timarkivet för alla stationer och år: `/work/cache/bias/gauge_ÅÅÅÅMMDD.npz` (läs med `knep.analys.bias.Store`); det får bara läsas.
- Höjdmodellen på radarns rutnät under `/data/projektion/` (`experiments/projektion/terrang.py`).
- Satelliten: EUMETSAT:s Data Store (MTG FCI, `EO:EUM:DAT:0662`; MSG SEVIRI). En FCI-produkt är cirka 600 MB; hämta bara de nordliga banden (de sista BODY-filerna, cirka 15 MB vardera) och spara bara utsnitt på radarns rutnät under `/data/satellit/`.
- Dagarna: `experiments/sverige/dagar.json` (frysta; `validering` är din validering, `test` aldrig), träningsdagarna i `experiments/projektion/traning.json`.
- Ny data hamnar under `/data/<område>/`. **Högst 1 GB ny data per uppgift**, och avbryt om `df /data` visar mindre än 3 GB ledigt (driften och volymkorrektionen delar disken).

## Regler

- Arbeta bara i den här utcheckningen och på den gren du står på. Byt inte gren, och pusha, merga eller öppna inga PR:er; det gör loopen.
- Ändra inte `deploy/`, `models/`, `.github/`, `experiments/sverige/dagar.json`, `experiments/natt/` eller filerna i `experiments/bakgrund/` utom `MAL.md`, `IDEER.md`, `nasta.md` (planeraren) och `rapporter/`. `JOURNAL.md` skriver loopen.
- Nytt arbete läggs i `experiments/<område>/` (`analys`, `projektion`, `bortfall`, `satellit` eller ett nytt). Ändringar i `src/knep/` är tillåtna om de behövs, med tester, men ska vara små och gå att läsa i en PR. Driften ska fungera som förut, så nya steg läggs till som val och standardvärdet ändras inte.
- Lägg inga stora filer i repot (inga över 5 MB; data och kartor hör till `/data/`).
- `uv run pytest` ska gå igenom innan du committar. Committa ofta med tydliga meddelanden på svenska, så att inget arbete går förlorat om uppgiften avbryts.
- Pi:n delar processorn med driften. Du körs redan med låg prioritet. Använd **högst två processer** i taget och högst cirka 2 GB minne. Kör en liten provkörning innan du startar en lång. SMHI:s öppna data tillåter högst 40 anrop per 10 s från Pi:n, och driften och volymkorrektionens hämtning behöver en del av dem: håll dig under 2 anrop per sekund.
- Långa körningar startar du i bakgrunden med utdata till en loggfil och väntar på dem, i stället för att låta ett kommando gå i timmar i förgrunden. Ge dem `timeout` på upp till 2 h.
- Text, kommentarer och rapporter på svenska, utan tankstreck som skiljetecken.

## Rapporter

Varje uppgift skriver sin rapport på den plats som uppgiften anger: vad du gjorde, vad som fungerade och inte, siffrorna med domarens tabeller, vilka filer som ändrades och vad nästa steg är. Rapporten har en rad som börjar med `Kort:` med resultatet i en mening, och sist en rad som börjar med `Status:` och sedan `klar`, `delvis` eller `misslyckad`.
