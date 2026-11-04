# 4 MEPS i hålet: MEPS rättad mot radarn, och blandningar med den flyttade analysen

## Vad jag gjorde

1. Läste rapport 1 till 3. Alla tre är klara (Status: klar); fallen, mätarna, domaren och baslinjerna (`fylld`, `hal`, `utjamnad`, `facit`) finns, så inget behövde göras om.
2. Skrev `experiments/bortfall/meps_hal.py` med tre system för domaren och en sökning av vikterna på träningsfallen, och `tests/test_bortfall_meps_hal.py` (8 tester på syntetiska data).
3. Provkörde sökningen på 2 fall, körde den sedan på 56 träningsfall (de två längsta per träningsdag) i bakgrunden och frös vikterna i `experiments/bortfall/meps_vikter.json` (committat innan valideringen startade).
4. Körde domaren på valideringen (128 fall) för de tre systemen.

## Systemen

Allt står också i docstringen i `meps_hal.py`.

- **`meps_hal:Meps`**: hålet fylls med MEPS rättad mot radarn utanför hålet, med samma rättning som `knep.seamless`: läget med optiskt flöde (`estimate_shift`) och mängden med kvantilavbildning (`estimate_amount`/`apply_amount`), skattade på senaste radartimmen (medel av de senaste 12 bilderna) mot MEPS i timmens mitt, och utjämnade mellan bilderna med samma minne som i drift (`seamless._per_cycle`, nollställs när MEPS byter körning). Första skattningen görs på uppvärmningen, där hela fältet är riktig radar; under bortfallet maskas hålet. Lägesrättningen i hålet, där radarn saknas och flödet är noll, ersätts med ett gaussiskt viktat medel (sigma 50 km) av rättningen utanför. MEPS-timmarna tolkas som intensiteten mitt i timmen och interpoleras i tiden som `seamless.meps_at`, men bara med timmar som har börjat (det är vad domaren ger).
- **`meps_hal:Flytt`**: `composite.fill_gaps` exakt som `fylld`, men utan att släppa pixlarna efter 90 min (`max_age` oändlig). Den är byggstenen i blandningen och togs med i valideringen för att skilja vad MEPS tillför från vad det ger att inte släppa pixlarna.
- **`meps_hal:Blandning`**: den flyttade analysen (`Flytt`) och den rättade MEPS blandas per skala som i `seamless.blend`, med bortfallets ålder i stället för ledtiden: den flyttade analysens vikt är 1 / (1 + (ålder / t50) ^ form), med ett t50 för de små skalorna och ett för de stora (skalgräns gaussiskt 30 km), och sist får hålet en värdefördelning mellan de två fältens med de små skalornas vikt. Utanför hålet är fältet radarn, så den stora skalan vid kanten tar med riktig radar.
- Fall utan MEPS (2019, äldre rutnät; 16 av 128 valideringsfall) får `fylld` i `Meps` och `Blandning`, så att de inte straffas för data som saknas. `Flytt` kör sin egen väg även där.

## Valet av vikterna på träningen

Urvalet: de två längsta fallen med MEPS per träningsdag, 56 fall (alla åldersklasser får fall). Den flyttade analysen och den rättade MEPS räknas en gång per fall; varje kandidat bedöms med domarens egna summor (`domare.bild_sums`) på varannan bild. Poängen är medlet över de tre åldersklasserna av medlet av de fyra FSS och de tre CSI. Körtid 77 min med två processer. Resultaten per kandidat ligger i `experiments/bortfall/resultat/traning/meps_sok.json`.

| kandidat (t50 små / stora skalor, min) | poäng | 0–30: FSS 1 mm 30 km | FSS 5/30 | CSI 1 | 30–90: FSS 1/30 | FSS 5/30 | CSI 1 | vol | 90–360: FSS 1/30 | FSS 5/30 | CSI 1 | vol |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **360 / 900 (vald)** | 0,529 | 0,943 | 0,873 | 0,587 | 0,764 | 0,564 | 0,352 | 1,04 | 0,641 | 0,425 | 0,279 | 1,20 |
| 360 / 360 | 0,527 | 0,943 | 0,873 | 0,587 | 0,764 | 0,564 | 0,352 | 1,04 | 0,632 | 0,429 | 0,275 | 1,20 |
| bara flyttad (vikt 1) | 0,524 | 0,943 | 0,873 | 0,587 | 0,763 | 0,564 | 0,351 | 1,04 | 0,608 | 0,434 | 0,253 | 1,08 |
| 240 / 600 | 0,522 | 0,943 | 0,873 | 0,587 | 0,764 | 0,563 | 0,352 | 1,04 | 0,635 | 0,357 | 0,281 | 1,30 |
| 180 / 450 | 0,516 | 0,943 | 0,873 | 0,587 | 0,764 | 0,561 | 0,353 | 1,05 | 0,618 | 0,300 | 0,276 | 1,38 |
| 120 / 300 | 0,504 | 0,943 | 0,873 | 0,587 | 0,759 | 0,555 | 0,353 | 1,07 | 0,583 | 0,224 | 0,262 | 1,48 |
| 90 / 225 | 0,494 | 0,943 | 0,873 | 0,587 | 0,749 | 0,535 | 0,350 | 1,09 | 0,559 | 0,186 | 0,252 | 1,53 |
| 60 / 150 (som seamless) | 0,476 | 0,943 | 0,872 | 0,587 | 0,713 | 0,475 | 0,333 | 1,12 | 0,529 | 0,155 | 0,239 | 1,57 |
| 60 / 150 utan matchning | 0,484 | 0,943 | 0,869 | 0,588 | 0,738 | 0,459 | 0,347 | 1,07 | 0,557 | 0,182 | 0,253 | 1,45 |
| 60 / 150, form 5 | 0,472 | 0,943 | 0,873 | 0,587 | 0,705 | 0,474 | 0,330 | 1,13 | 0,513 | 0,141 | 0,232 | 1,60 |
| 30 / 75 | 0,431 | 0,931 | 0,852 | 0,577 | 0,610 | 0,281 | 0,276 | 1,16 | 0,495 | 0,140 | 0,224 | 1,60 |
| bara MEPS (vikt 0) | 0,241 | 0,572 | 0,128 | 0,237 | 0,473 | 0,100 | 0,197 | 1,18 | 0,482 | 0,138 | 0,217 | 1,60 |

(Alla kandidater med kvoten 1 och 2,5 mellan t50 finns i json-filen; tabellen visar ett urval.)

Det viktiga redan här: **MEPS rättad mot radarn är sämre än den flyttade analysen i alla åldersklasser, även 90 till 360 min**, och varje vikt på MEPS sänker FSS 5 mm. Poängen växer monotont med t50, och den valda kandidaten ger MEPS bara vikten 0,07 vid 90 min och 0,5 vid 6 h för de små skalorna. Den lilla vinsten mot bara flyttad (0,529 mot 0,524) kommer ur CSI och FSS 1 mm efter 90 min, medan FSS 5 mm och volymen blir sämre. Sökningens poäng väger dessutom inte in volymen, och MEPS drar volymen uppåt (1,20 mot 1,08).

VALIDERING

## Filer

- `experiments/bortfall/meps_hal.py` (nytt): systemen `Meps`, `Flytt`, `Blandning` och sökningen (`sok`)
- `experiments/bortfall/meps_vikter.json` (nytt, fryst före valideringen)
- `experiments/bortfall/resultat/traning/meps_sok.json` (nytt)
- `experiments/bortfall/resultat/validering/meps_hal_{Blandning,Meps,Flytt}.json` (nya)
- `tests/test_bortfall_meps_hal.py` (nytt, 8 tester)
- `experiments/natt/rapporter/2026-11-03/4-meps-i-halet.md`

Inga ändringar i `src/knep/` eller i domaren.

```sh
uv run python experiments/bortfall/meps_hal.py sok --processer 2 --logg /data/bortfall/logg/meps_sok.log
uv run python experiments/bortfall/domare.py kor meps_hal:Blandning meps_hal:Meps meps_hal:Flytt --processer 2 --logg /data/bortfall/logg/meps_validering.log
uv run python experiments/bortfall/domare.py tabell fylld hal meps_hal:Flytt meps_hal:Meps meps_hal:Blandning --mot fylld
```
