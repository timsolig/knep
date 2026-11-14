# 0024 A0B (A0 med volymkorrektionen bias-v1) mot A0 i analysens domare

Kort: A0B fälls av domarens regel på alla 16 valideringsdygn: kvot våt i kvartar 0,793 mot 0,704 (+0,119, intervall +0,054 till +0,178) och FSS 0,5 och CSI 0,5 och 1 per timme blir bättre, men falska ekon blir sämre (kvart 0,031 mot 0,026, intervall helt på fel sida) och FSS 5 per timme faller (0,182 mot 0,302), så ingen säkerställd förbättring.

Säkerställd förbättring: nej

## Vad som gjordes

- Disken: `/data` hade 1 332 MB ledigt (under gränsen), så inget skrevs dit. Allt nytt ligger i `/dev/shm/bias_v1/` (1 892 MB ledigt). `a0b.py` vägrar `--ut` under `/data`.
- Kartan `/dev/shm/bias_v1/full/bias_v1.npz` fanns kvar och hade rätt sha256 (`1d79d27eacb9d3e4578ddc0c87537b84bb8f540896f9e9a952b9a59a1d625373`); den skapades inte om.
- `experiments/analys/a0b.py` (nytt): `A0B(domare.A0)`, registrerad i `domare.SYSTEMS`, med egen `kor` och `tabell` som sätter `--ut`. Faktorn `corr.factor(t)` räknas var 12:e bild (en gång per timme) och `corr.tail` läggs på, på den råa SMHI-bilden före `composite.fill_gaps`, utan medelfältsfaktor. `assert corr.beam.shape == rd.grid.shape`. `domare.py` är orörd.
- `tests/test_analys_a0b.py` (nytt): faktor 1 och ingen svans ger exakt A0 (`array_equal`), faktor 2 dubblar bilden där det finns eko, och systemet är registrerat.
- A0:s dagfiler för de 16 valideringsdygnen kopierades från `/data/analys/domare_v2/A0/` (bara läst) till `/dev/shm/bias_v1/domare/A0/`; A0 kördes inte om. Rörelsefälten för alla 16 dygn fanns redan i `/data/analys/domare/rorelse/`, så inget skrevs dit.
- Körning: provdygn 2019-03-08, 50 s. Alla 16 dygn kördes med `--bit 0/2` och `--bit 1/2` samtidigt, klara på cirka 7 minuter, alltså inte i närheten av tidsgränsen. Domen gäller därför alla 16 valideringsdygn (inte ofullständig). Minnet mättes inte (`/usr/bin/time` var inte tillåtet); A0 och A0B har samma bildstapel (en dag, float32), så det är A0:s minne plus en faktorbild.
- Testdelen lästes, kördes och räknades aldrig (`domare.days("validering")`).

## Domarens tabell, A0B mot A0 (16 dagar, 95 %-intervall från bootstrap över dagarna)

Skillnaden är i godhet (plus = A0B bättre). Mängden redovisas med kvot våt (domarens mått) och kvot summa (den gamla) bredvid.

### Kvart, alla mätare

| mått | A0B | A0 | skillnad i godhet |
|---|---|---|---|
| kvot summa | 0,926 | 0,825 | +0,115 (-0,006 till +0,161) |
| kvot våt | 0,793 | 0,704 | +0,119 (+0,054 till +0,178) |
| kvot >1 mm | 0,438 | 0,468 | -0,066 (-0,119 till +0,069) |
| kvot >5 mm | 0,266 | 0,349 | -0,270 (-0,351 till -0,098) |
| kvot >10 mm | 0,196 | 0,235 | -0,179 (-0,212 till -0,106) |
| MAE | 0,072 | 0,069 | -0,003 (-0,005 till +0,000) |
| CSI 0,5 / 1 / 5 | 0,300 / 0,160 / 0,039 | 0,287 / 0,179 / 0,060 | +0,012 (-0,003 till +0,027) / -0,018 (-0,031 till -0,000) / -0,021 (-0,036 till +0,007) |
| FSS 0,5 / 1 / 5 | 0,512 / 0,313 / 0,024 | 0,481 / 0,327 / 0,077 | +0,030 (+0,010 till +0,057) / -0,014 (-0,036 till +0,022) / -0,053 (-0,070 till -0,000) |
| falskt vid torr mätare | 0,031 | 0,026 | -0,005 (-0,007 till -0,003) |
| falskt, allt inom 25 km torrt | 0,030 | 0,025 | -0,005 (-0,007 till -0,003) |
| hopp, kvot mot mätarna | 0,936 | 0,884 | +0,057 (-0,115 till +0,092) |

### Timme, alla mätare

| mått | A0B | A0 | skillnad i godhet |
|---|---|---|---|
| kvot summa | 0,977 | 0,890 | +0,093 (-0,118 till +0,125) |
| kvot våt | 0,923 | 0,841 | +0,093 (-0,020 till +0,138) |
| kvot >1 mm | 0,762 | 0,716 | +0,062 (-0,016 till +0,140) |
| kvot >5 mm | 0,415 | 0,499 | -0,185 (-0,227 till +0,049) |
| kvot >10 mm | 0,351 | 0,487 | -0,327 (-0,397 till -0,081) |
| MAE | 0,243 | 0,233 | -0,010 (-0,022 till +0,001) |
| CSI 0,5 / 1 / 5 | 0,548 / 0,446 / 0,094 | 0,520 / 0,423 / 0,160 | +0,028 (+0,009 till +0,048) / +0,023 (+0,003 till +0,051) / -0,066 (-0,093 till -0,006) |
| FSS 0,5 / 1 / 5 | 0,751 / 0,662 / 0,182 | 0,723 / 0,634 / 0,302 | +0,029 (+0,011 till +0,048) / +0,027 (+0,006 till +0,056) / -0,120 (-0,142 till -0,011) |
| falskt vid torr mätare | 0,012 | 0,010 | -0,002 (-0,003 till -0,001) |
| falskt, allt inom 25 km torrt | 0,011 | 0,010 | -0,002 (-0,003 till -0,001) |

### Terrängen

Mätare över 400 m (fjäll och höglänt):

| mått | kvart A0B / A0 | skillnad | timme A0B / A0 | skillnad |
|---|---|---|---|---|
| kvot summa | 0,651 / 0,495 | +0,274 (+0,167 till +0,400) | 0,657 / 0,524 | +0,227 (+0,122 till +0,360) |
| kvot våt | 0,492 / 0,366 | +0,296 (+0,191 till +0,427) | 0,585 / 0,467 | +0,225 (+0,120 till +0,368) |
| CSI 0,5 | 0,204 / 0,154 | +0,050 (+0,025 till +0,085) | 0,354 / 0,302 | +0,052 (+0,023 till +0,072) |
| CSI 1 | 0,154 / 0,171 | -0,017 (-0,041 till +0,027) | 0,312 / 0,248 | +0,064 (+0,018 till +0,121) |
| FSS 0,5 | 0,368 / 0,269 | +0,099 (+0,061 till +0,166) | 0,568 / 0,474 | +0,093 (+0,066 till +0,121) |
| FSS 1 | 0,303 / 0,252 | +0,051 (+0,002 till +0,233) | 0,520 / 0,429 | +0,092 (+0,057 till +0,136) |
| FSS 5 | 0,021 / 0,054 | -0,034 (-0,039 till +0,000) | 0,277 / 0,284 | -0,008 (-0,047 till +0,272) |
| falskt vid torr mätare | 0,021 / 0,015 | -0,007 (-0,010 till -0,004) | 0,012 / 0,009 | -0,003 (-0,005 till -0,001) |

Lovartsidan:

| mått | kvart A0B / A0 | skillnad | timme A0B / A0 | skillnad |
|---|---|---|---|---|
| kvot våt | 0,569 / 0,499 | +0,131 (+0,039 till +0,244) | 0,703 / 0,609 | +0,143 (+0,052 till +0,245) |
| CSI 0,5 | 0,277 / 0,258 | +0,020 (-0,010 till +0,036) | 0,519 / 0,472 | +0,047 (+0,019 till +0,066) |
| FSS 0,5 | 0,479 / 0,418 | +0,060 (+0,019 till +0,086) | 0,719 / 0,661 | +0,058 (+0,034 till +0,075) |
| FSS 1 | 0,270 / 0,264 | +0,006 (-0,034 till +0,022) | 0,677 / 0,622 | +0,055 (+0,009 till +0,089) |
| FSS 5 | 0,039 / 0,090 | -0,052 (-0,065 till +0,000) | 0,146 / 0,222 | -0,076 (-0,134 till -0,022) |
| falskt vid torr mätare | 0,022 / 0,016 | -0,006 (-0,010 till -0,003) | 0,015 / 0,011 | -0,004 (-0,009 till -0,000) |

### Kartmåttet

Rutor med eko (över 0,5 mm) i mer än hälften av de torra timmarna, per dag: A0B 50,4 mot A0 36,6, skillnad -13,8 (-37,1 till -0,8), alltså sämre med intervallet helt på fel sida.

## Domen enligt domarens regel

**Inte bättre.** Kvot våt i kvartar och CSI och FSS 0,5 och 1 per timme blir bättre med intervallet helt på rätt sida (mängd eller träff räcker som villkor), men spärrarna bryts: falska ekon blir sämre med intervallet helt på fel sida i kvart och timme, i alla tre delmängderna, rutor med eko under torra timmar blir fler, och timme lovart FSS 5 blir sämre. Den gamla regeln (kvot summa) och domen utan underlagskravet ger samma slutsats. Domens fullständiga lista finns i `/dev/shm/bias_v1/domare/tabell_A0B_mot_A0_validering.json` (försvinner vid omstart; listan ovan är den som behövs).

Det som ligger bakom: nivåhöjningen lyfter svagt eko lika mycket som starkt, så fler rutor passerar 0,5 mm (falska ekon, torra rutor) och träffen vid låga trösklar förbättras. Samtidigt blir de kraftiga intensiteterna sämre i FSS 5 och kvot >5 och >10 mm. Kvoterna över 5 och 10 mm är långt under 1 också för A0 och blir ännu lägre; det visar att volymkorrektionen som nivå inte tar bort radarns tillplattade toppar, och att svansen (γ vid gränsen −0,2) inte räcker eller verkar åt fel håll när nivån höjs före den.

## Norra Sverige och fjällen

Domaren kan inte dela upp efter region; delmängderna är bara alla, över 400 m och lovart. Över 400 m (där kartan höjer mest) blir mängd och träff vid låga trösklar bäst (kvot våt +0,296 kvart, CSI 0,5 +0,050, FSS 0,5 +0,099) men falska ekon är sämre (kvart -0,007, tim -0,003 och intervallen helt på fel sida), och FSS 5 per kvart är sämre. Hur kartan beter sig norr om cirka 66 N (där K står vid taket 4 och strålen går över 3 km) kan alltså inte särskiljas, bara att det inte syns som någon förbättring av FSS 5 eller kvoten över 5 mm i höjdmängden. Valideringsdygnen är få i norr; att dela upp domaren efter latitud vore en ändring av domaren och görs inte här. Om det behövs kan en egen kontroll göra det på dagfilerna först när de sparar per ruta, vilket de inte gör.

## Vad som bör väljas på träningen i en senare uppgift (ingenting kört på valideringen)

Fällande: falska ekon och torra rutor (nivån höjer svagt eko), samt FSS 5 och kvot över 5 mm. I ordning efter hur mycket de sannolikt hjälper:

1. En nivåhöjning som inte lyfter svagt eko (till exempel faktorn K tonad mot 1 under en tröskel, eller nivå och svans som en sammanhängande funktion av intensiteten i stället för två steg), eftersom falska ekon är det som fäller. Pröva på träningsdagarna i domaren.
2. Tak på K lägre än 4 (till exempel 2) och lägre nivåhöjning över 3 km strålhöjd, där korsvalideringen inte kan pröva kartan; de bidrar till de falska ekona och till de dåliga kvoterna över 400 m.
3. γ utanför −0,2 (släpp spärren), så att svansen kan trycka ned radarns toppar mer efter nivån; i 0023 var γ bunden vid gränsen.
Välj varianten på träningsdagarna (`domare.py kor ... --del traning`) med samma domare, frys, och döm en gång på valideringen.

## Rekommendation om släpp

Släpp inte. A0B är fälld, så ingen fråga om släpp läggs under Frågor till användaren i `MAL.md`. Ett släpp kräver dessutom testdelen och användarens beslut. Före något släpp måste spärren mot mätarnas felvärden (över 100 mm per timme, i arkivet 14 277 värden på exakt 720 mm) finnas i `bias.Store` och driftens insamling, annars förstör felvärdena kartan (volym 0,08 i 0023:s provkörning).

## Filer

- `experiments/analys/a0b.py` (nytt), `tests/test_analys_a0b.py` (nytt), denna rapport. Inget i `domare.py`, `src/`, `deploy/` eller `models/` ändrades, och inga data lades i repot eller i `/data`.
- Dagfilerna och tabellen ligger i `/dev/shm/bias_v1/domare/` (A0B, A0, `tabell_A0B_mot_A0_validering.json`) och försvinner vid omstart.
- `uv run pytest`: 235 gick igenom.

## Nästa steg

1. Spärren för mätarfelen i `bias.Store`/insamlingen (liten ändring med test).
2. Variantsökning på träningsdagarna enligt ovan, med nivå som inte lyfter svagt eko som första variant, sedan en dom på valideringen.
3. Eventuellt en regionuppdelning (norr/fjäll) i domaren, som en ändring planeraren beslutar om.

Status: klar
