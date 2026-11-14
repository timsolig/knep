# Uppgift 0027: bias-v1 tonad efter den bakåtblickande summan

Kort: Ingen av tre varianter (A0B_s15, A0B_s60, A0B_smin) klarar domaren på de 28 träningsdagarna: alla förbättrar kvot våt per kvart (+0,097, +0,085, +0,080 mot A0) men falskt vid torr mätare blir sämre med intervallet helt på fel sida per timme (och för s15 och s60 per kvart), så ingen frystes och valideringen kördes inte.

Säkerställd förbättring: nej

## Vad som gjordes (Läge A, skalet fungerade)

- Kartan `/dev/shm/bias_v1/full/bias_v1.npz` och A0:s 28 dagfiler fanns kvar och användes oförändrade. Sha256 kontrollerades inte på nytt. Inget skrevs till `/data`.
- Gränserna är domarens regngränser, `domare.ECHO`: 0,125 mm per kvart och 0,5 mm per timme (0,5 mm/h). Det är också den vanliga gränsen mellan regn och uppehåll, så tonen följer samma tröskel som domaren räknar falskt eko mot. Det är avsikten, men det betyder att tonen är nära tillpassad domaren och inte en fristående princip.
- `experiments/analys/a0b.py`: `A0B_summa` med `summa_vikt` (w = 0 under gränsen, 1 vid dubbla gränsen, linjärt i log däremellan). Summan är av de råa bilderna bakåt i tiden (NaN räknas som 0, mm/h per bild delat med 12, så 3 bilder för 15 min och 12 för 60 min; i dagens början finns färre bilder, vilket ger mindre summa). Den korrigerade bilden är r · K^w, utan svans, faktorn en gång per timme, samma frysta karta.
  - `A0B_s15`: 3 bilder, gräns 0,125 mm.
  - `A0B_s60`: 12 bilder, gräns 0,5 mm.
  - `A0B_smin`: minsta av de två vikterna (tredje varianten, vald efter de två eftersom s15 och s60 båda fälldes av falska ekon och min är den försiktigaste kombinationen). `A0B_smax` finns också i koden och i testerna men kördes inte.
- `tests/test_analys_a0b.py`: K = 1 ger exakt A0; summa under gränsen ger orört; summa vid dubbla gränsen ger r · K; mellanvärde ger r · K^w; max och min på en kort skur; tonen är kausal (framtida bilder ändrade, tidigare utdata lika). `uv run pytest`: 247 gick igenom.
- Provdag 2020-02-10 tog 85 s. Varje variant kördes på de 28 träningsdagarna med `a0b_kor.py` (s15 en process, s60 en process, smin två processer). Testdelen lästes, kördes och räknades aldrig. Valideringen kördes inte.

## Tabell mot A0, träningen (28 dagar)

A0: kvot våt kvart 0,687, timme 0,830; falskt kvart 0,024, timme 0,010; kartmått 51,8; FSS 5 timme 0,321. Skillnad i godhet med 95 %-intervall (bootstrap över dagarna), plus är bättre.

| mått | A0B_s15 | A0B_s60 | A0B_smin |
|---|---|---|---|
| kvot våt kvart (värde) | 0,756 | 0,748 | 0,744 |
| kvot våt kvart (skillnad) | +0,097 (+0,055 till +0,137) | +0,085 (+0,044 till +0,123) | +0,080 (+0,040 till +0,118) |
| kvot våt timme (skillnad) | +0,079 (+0,040 till +0,117) | +0,069 (+0,033 till +0,104) | +0,065 (+0,029 till +0,099) |
| kvot >1 mm kvart (skillnad) | +0,095 (+0,019 till +0,164) | +0,090 (+0,014 till +0,160) | +0,090 (+0,012 till +0,159) |
| CSI 0,5 timme (skillnad) | +0,006 (+0,003 till +0,010) | +0,003 (+0,001 till +0,006) | +0,002 (+0,000 till +0,004) |
| FSS 0,5 timme (skillnad) | +0,008 (+0,006 till +0,011) | +0,004 (+0,002 till +0,006) | +0,003 (+0,001 till +0,004) |
| falskt torr mätare kvart (skillnad) | -0,000 (-0,000 till -0,000) | -0,000 (-0,000 till -0,000) | -0,000 (-0,000 till +0,000) |
| falskt torr mätare timme (skillnad) | -0,001 (-0,001 till -0,000) | -0,000 (-0,001 till -0,000) | -0,000 (-0,000 till -0,000) |
| MAE kvart (skillnad) | -0,003 (-0,004 till -0,001) | -0,002 (-0,004 till -0,001) | -0,002 (-0,004 till -0,001) |
| MAE timme (skillnad) | -0,009 (-0,015 till -0,004) | -0,008 (-0,014 till -0,003) | -0,008 (-0,013 till -0,003) |
| kartmåttet (rutor/dag) | 54,4 (-2,6 (-11,6 till +4,1)) | 51,6 (+0,2 (-2,8 till +3,4)) | 51,2 (+0,6 (-1,2 till +3,1)) |
| FSS 5 timme (skillnad) | +0,004 (-0,032 till +0,036) | +0,005 (-0,030 till +0,036) | +0,005 (-0,030 till +0,036) |
| kvot >5 mm timme (skillnad) | +0,074 (-0,012 till +0,161) | +0,072 (-0,014 till +0,160) | +0,072 (-0,014 till +0,159) |
| över 400 m kvot våt kvart (skillnad, s15) | +0,193 (+0,118 till +0,281) | ej utdraget | ej utdraget |

Domens fält `battre`: `false` för alla tre. `samre_i` (intervallet helt på fel sida):

- s15: falskt vid torr mätare och inom 25 km torrt, kvart och timme; MAE över 400 m och lovart (kvart och timme).
- s60: falskt vid torr mätare kvart och timme, falskt inom 25 km torrt timme; MAE över 400 m och lovart; falskt över 400 m kvart.
- smin: falskt vid torr mätare och inom 25 km torrt timme; falskt över 400 m kvart; MAE över 400 m och lovart. Bara falskt per kvart (alla mätare) släpper, intervallet är -0,000 till +0,000.

Skillnaderna i falskt eko är små i absolut tal (några tusendelar), men intervallen över dagarna är smala, så domarens regel fäller dem ändå. Jag har inte rört regeln.

## Valet

Ingen variant frystes. Tonen på bakåtblickande summa minskar de falska ekona jämfört med tonen på bildens intensitet (0025: g0 -0,005 per kvart, k2 -0,000 till -0,001 per timme) och gör dem inom bruset per kvart i smin, men alltid på bekostnad av vinsten: kvot våt kvart faller i ordningen s15 +0,097, s60 +0,085, smin +0,080, och falska ekon per timme kvarstår, liksom MAE (som blir sämre över 400 m och i lovart i alla tre). Förbättringen och försämringen kommer från samma perioder: perioder vars summa ligger över gränsen och som K lyfter över den för mätaren.

## Tolkning

- Mekanismen från 0025 stämmer delvis: tonen på summan tar bort mer av de falska ekona än tonen på intensitet, men inte alla, eftersom perioder vars summa ligger vid eller över gränsen ändå lyfts med K. Där är ekot svagt och spritt över timmen och K > 1 ger fler rutor över 0,5 mm, medan mätaren är torr. Då är det inte tröskeln som är fel utan K själv i de rutorna: kartan skattar ett genomsnittligt underskott som inte gäller de enskilda rutorna med svagt eko som mätaren inte ser.
- Tonen bryter inte FSS 5 eller kvot >5 mm (intervallen rymmer 0, som i 0025), så den fällande effekten på valideringen i 0024 syns fortfarande inte på träningen.

## Rekommendation

Lägg bias-v1 vilande som nivåfaktor på bilden. Nästa och sista väg som är kvar enligt `IDEER.md` och 0025 är ett stödkrav på ekot (isolerat svagt eko lyfts inte, till exempel grannrutor med eko eller eko i mer än en bild) som nytt system, prövat på träningen med samma domare. Inget släpp och ingen fråga under Frågor till användaren i `MAL.md`, eftersom ingen variant godkändes.

## Filer

- Ändrade: `experiments/analys/a0b.py` (A0B_summa, A0B_s15, A0B_s60, A0B_smax, A0B_smin), `tests/test_analys_a0b.py`.
- Ny: denna rapport.
- Dagfiler i `/dev/shm/bias_v1/domare_tr/` (A0B_s15, A0B_s60, A0B_smin) försvinner vid omstart. Inget i `domare.py`, `src/`, `deploy/`, `models/` eller `/data` ändrades.

## Nästa steg

1. Stödkravet på ekot som nytt system, prövat på träningen med samma domare (om bias-v1 ska fortsätta).
2. Spärren mot mätarnas felvärden (720 mm) i `bias.Store` och insamlingen, som fortfarande saknas inför ett eventuellt släpp.

Status: klar
