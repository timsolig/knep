# 0025 Varianter av bias-v1 (A0B_g0, A0B_ton, A0B_ton2, A0B_k2) på träningsdagarna

Kort: Ingen av fyra varianter klarar domaren på de 28 träningsdagarna: alla förbättrar kvot våt per kvart (+0,078 till +0,137 mot A0) men falskt vid torr mätare blir sämre med intervallet helt på fel sida i alla (bäst A0B_k2: 0,024 mot 0,024, skillnad -0,000 (-0,001 till -0,000)), så ingen frystes och valideringen kördes inte.

Säkerställd förbättring: nej

## Vad som gjordes

- Kartan `/dev/shm/bias_v1/full/bias_v1.npz` fanns kvar och användes oförändrad. Sha256 kontrollerades inte på nytt (filen är samma som i 0024 och rördes inte).
- `experiments/analys/a0b.py`: fyra nya system i `domare.SYSTEMS`, alla på samma karta, utan svans och utan medelfältsfaktor, faktorn en gång per timme som i A0B:
  - `A0B_g0`: nivåfaktorn K, ingen svans (γ = 0).
  - `A0B_ton`: R · K^w, w = 0 under 0,3 mm/h, 1 över 1 mm/h, linjärt i log R däremellan. Eko under 0,3 mm/h är exakt orört.
  - `A0B_ton2`: som ovan med tröskelparet 0,5 till 2 mm/h (andra och sista tröskelparet).
  - `A0B_k2`: K klippt vid 2 ovanpå `A0B_ton2` (den variant av g0, ton och ton2 med minst falska ekon på träningen, valet gjort efter att de tre var körda).
  Fem varianter var gränsen; fyra gjordes. Skälet till att inte fler provades: se tolkningen nedan.
- `tests/test_analys_a0b.py`: test per variant (g0 struntar i svansen och K = 1 ger exakt A0; ton lämnar eko under 0,3 orört, ger K över 1 och mellanvärden däremellan, K = 1 ger exakt A0; ton2 orört under 0,5; k2 klipper vid 2, tonar och ger 1,5 när K = 1,5). `uv run pytest`: 241 gick igenom.
- `experiments/analys/a0b_kor.py` (nytt): kör en variant per process (domaren delar annars A0-bilder mellan system i samma anrop, vilket vore fel här) över `--bit`.
- A0:s dagfiler för de 28 träningsdagarna och de 16 valideringsdagarna kopierades (bara läst från `/data/analys/domare_v2/A0/`) till `/dev/shm/bias_v1/domare_tr/A0/` och `domare_va/A0/`. Inget skrevs till `/data`. Varje variant tog 12 till 15 minuter med två processer (`--bit 0/2`, `--bit 1/2`); provdag 2020-02-10 tog 57 s.
- Testdelen lästes, kördes och räknades aldrig. Valideringen kördes inte.

## Sammanfattande tabell, träningen (28 dagar), A0 mot varianterna

A0: kvot våt kvart 0,687, timme 0,830; falskt kvart 0,024, timme 0,010; kartmått 51,8; FSS 5 timme 0,321; kvot >5 mm timme 0,581; över 400 m kvot våt kvart 0,413, timme 0,489; lovart kvot våt kvart 0,611, timme 0,677.

Skillnaden mot A0 i godhet med 95 %-intervall, plus är bättre.

| mått | A0B_g0 | A0B_ton | A0B_ton2 | A0B_k2 |
|---|---|---|---|---|
| kvot våt kvart (värde) | 0,788 | 0,765 | 0,747 | 0,742 |
| kvot våt kvart (skillnad) | +0,137 (+0,091 till +0,183) | +0,108 (+0,064 till +0,149) | +0,084 (+0,044 till +0,122) | +0,078 (+0,039 till +0,113) |
| kvot våt timme (värde) | 0,933 | 0,908 | 0,890 | 0,886 |
| kvot våt timme (skillnad) | +0,117 (+0,062 till +0,159) | +0,090 (+0,048 till +0,128) | +0,069 (+0,033 till +0,104) | +0,065 (+0,029 till +0,097) |
| falskt torr mätare kvart | 0,029 | 0,025 | 0,024 | 0,024 |
| falskt kvart (skillnad) | -0,005 (-0,007 till -0,003) | -0,002 (-0,002 till -0,001) | -0,001 (-0,001 till -0,000) | -0,000 (-0,001 till -0,000) |
| falskt torr mätare timme | 0,013 | 0,012 | 0,011 | 0,011 |
| falskt timme (skillnad) | -0,003 (-0,004 till -0,002) | -0,001 (-0,002 till -0,001) | -0,001 (-0,001 till -0,000) | -0,001 (-0,001 till -0,000) |
| kartmåttet (rutor/dag) | 66,9 | 57,8 | 53,8 | 53,8 |
| kartmåttet (skillnad) | -15,1 (-41,1 till +3,3) | -6,0 (-20,6 till +5,5) | -2,0 (-8,9 till +3,8) | -2,0 (-8,9 till +3,8) |
| FSS 5 timme | 0,325 | 0,325 | 0,325 | 0,328 |
| FSS 5 timme (skillnad) | +0,004 (-0,033 till +0,036) | +0,004 (-0,032 till +0,036) | +0,004 (-0,032 till +0,035) | +0,007 (-0,028 till +0,037) |
| kvot >5 mm timme | 0,628 | 0,626 | 0,624 | 0,624 |
| kvot >5 mm timme (skillnad) | +0,076 (-0,009 till +0,165) | +0,075 (-0,011 till +0,162) | +0,071 (-0,013 till +0,157) | +0,071 (-0,013 till +0,157) |
| över 400 m kvot våt kvart (skillnad) | +0,281 (+0,196 till +0,376) | +0,223 (+0,146 till +0,312) | +0,164 (+0,097 till +0,244) | +0,129 (+0,077 till +0,193) |
| över 400 m kvot våt timme (skillnad) | +0,264 (+0,189 till +0,346) | +0,208 (+0,138 till +0,285) | +0,154 (+0,092 till +0,223) | +0,129 (+0,079 till +0,187) |
| över 400 m falskt kvart (skillnad) | -0,006 (-0,008 till -0,004) | -0,003 (-0,004 till -0,001) | -0,001 (-0,002 till -0,001) | -0,001 (-0,002 till -0,000) |
| över 400 m falskt timme (skillnad) | -0,003 (-0,007 till -0,001) | -0,002 (-0,004 till -0,000) | -0,001 (-0,002 till +0,000) | -0,001 (-0,002 till +0,001) |
| över 400 m MAE kvart (skillnad) | -0,004 (-0,006 till -0,002) | -0,003 (-0,005 till -0,001) | -0,003 (-0,004 till -0,001) | -0,002 (-0,003 till -0,001) |
| lovart kvot våt kvart (skillnad) | +0,197 (+0,124 till +0,296) | +0,163 (+0,093 till +0,254) | +0,131 (+0,069 till +0,215) | +0,104 (+0,055 till +0,164) |
| lovart kvot våt timme (skillnad) | +0,194 (+0,130 till +0,284) | +0,163 (+0,102 till +0,247) | +0,133 (+0,079 till +0,206) | +0,110 (+0,066 till +0,164) |
| lovart falskt kvart (skillnad) | -0,005 (-0,009 till -0,002) | -0,002 (-0,003 till -0,000) | -0,001 (-0,002 till -0,000) | -0,001 (-0,001 till -0,000) |
| lovart falskt timme (skillnad) | -0,001 (-0,003 till +0,001) | -0,001 (-0,002 till +0,001) | -0,000 (-0,001 till +0,001) | -0,000 (-0,001 till +0,001) |
| CSI 0,5 timme (skillnad) | +0,019 (+0,011 till +0,027) | +0,009 (+0,005 till +0,015) | +0,005 (+0,002 till +0,008) | +0,005 (+0,002 till +0,008) |
| FSS 0,5 timme (skillnad) | +0,024 (+0,017 till +0,033) | +0,013 (+0,009 till +0,018) | +0,007 (+0,005 till +0,010) | +0,007 (+0,005 till +0,010) |
| MAE kvart (skillnad) | -0,003 (-0,005 till -0,002) | -0,003 (-0,005 till -0,002) | -0,003 (-0,004 till -0,001) | -0,002 (-0,004 till -0,001) |

Domens fält i domarens utskrift (`battre`), alla fyra: `false`. `battre_i` är lika för alla: kvot våt kvart och timme, kvot >1 mm kvart och timme, FSS 0,5 kvart, CSI 0,5 och 1 och FSS 0,5 och 1 per timme. `samre_i` (intervallet helt på fel sida):

- g0 och ton: falskt vid torr mätare och falskt inom 25 km torrt i kvart och timme, i alla delmängder utom lovart timme, samt MAE över 400 m och lovart.
- ton2 och k2: falskt kvart (alla, över 400 m, lovart) och falskt timme (alla; över 400 m och lovart är nu inom bruset), samt MAE kvart (över 400 m, lovart), timme över 400 m och lovart.

Hela domarutskrifterna sparades inte som filer (de skrevs till terminalen); dagfilerna och tabellerna kan räknas om ur `/dev/shm/bias_v1/domare_tr/` så länge de finns.

## Valet

Ingen variant frystes: ingen klarar regeln att falska ekon och terrängen inte får bli sämre med intervallet helt på fel sida. Närmast är `A0B_k2` och `A0B_ton2`: falskt vid torr mätare är där -0,000 till -0,001, och intervallen ligger fortfarande helt under 0 (kvart alla mätare). Förbättringen av kvot våt krymper i samma takt som de falska ekona (g0 +0,137 till k2 +0,078). Valideringen kördes därför inte, och bias-familjen har fortfarande bara setts en gång på valideringen (i 0024).

## Tolkning

- Svansen (γ = -0,2) var inte det som fällde A0B på träningen: FSS 5 per timme och kvot >5 mm skiljer sig inte från A0 i någon variant, med eller utan svans (intervallen rymmer 0). På träningen finns inget som tyder på att svansen trycker ned de starka intensiteterna; valideringens FSS 5-fall i 0024 (0,182 mot 0,302) syns inte här. Det kan bero på få dagar med kraftigt regn (kvot >10 mm har bara 3 till 12 dagar), men något mer säger siffrorna inte.
- Falska ekon är inte ett tröskelproblem under 0,3 till 0,5 mm/h som tonen antog: också med eko under 0,5 mm/h orört och full effekt först vid 2 mm/h blir falsklarmen fler. Mekanismen är att K lyfter eko som ligger strax under mätarens tröskel över den (och eko i torra timmar där mätaren sett inget alls). Tonen minskar falska ekon i samma proportion som den minskar vinsten i kvot våt, så avvägningen mellan mängd och falska ekon går inte att lösa med en tonad nivåfaktor ensam. Det är den bärande slutsatsen.
- K-taket vid 2 (k2) gav nästan ingenting utöver ton2: över 400 m minskade vinsten i kvot våt (+0,164 till +0,129) mer än falsklarmen.
- En variant som skulle kunna lösa avvägningen: ett villkor i själva korrektionen som kräver stöd för ekot (till exempel att grannrutor också har eko, eller att ekot varat mer än en bild) innan K läggs på, eller en torrmask som släpper K helt i rutor där ekot är svagt och isolerat. Det är ett nytt system, inte en variant av hur kartan läggs på, och provades inte.

## Rekommendation om släpp

Släpp inte. Ingen variant går igenom på träningen, och ingen fråga läggs under Frågor till användaren i `MAL.md`. Ett släpp kräver dessutom testdelen och användarens beslut, och före ett släpp måste spärren mot mätarnas felvärden (över 100 mm per timme, exakt 720 mm i arkivet) finnas i `bias.Store` och driftens insamling.

## Filer

- Ändrade: `experiments/analys/a0b.py` (varianterna), `tests/test_analys_a0b.py` (tester).
- Nya: `experiments/analys/a0b_kor.py`, denna rapport.
- Inget i `domare.py`, `src/`, `deploy/`, `models/` ändrades, och inget skrevs i `/data`. Dagfilerna ligger i `/dev/shm/bias_v1/domare_tr/` (A0, A0B_g0, A0B_ton, A0B_ton2, A0B_k2) och `domare_va/A0/` och försvinner vid omstart.

## Nästa steg

1. Spärren för mätarfelen i `bias.Store` och insamlingen (liten ändring med test), som fortfarande saknas.
2. Om bias-v1 ska fortsätta: en stödkrav på ekot (isolerat svagt eko får inte lyftas) som nytt system, prövat på träningen med samma domare. Tonad nivå räcker inte.
3. Alternativt flytta volymkorrektionens mål från kvot våt till de starka intensiteterna, där falska ekon inte spelar roll, till exempel bara K över 2 mm/h (ton2 med hi nära lo), och acceptera att mängden över svagt eko då inte rättas.

Status: klar
