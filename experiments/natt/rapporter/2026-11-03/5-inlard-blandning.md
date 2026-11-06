# 5 Inlärd blandning: HistGradientBoosting per pixel i hålet

## Vad jag gjorde

1. Läste rapport 1 till 4. Alla är klara (Status: klar), så inget behövde göras om. Rapport 4 pekar ut `meps_hal:Flytt` (`fill_gaps` utan 90-minutersgräns) som det som ska slås efter 90 min; dess tydligaste fel är volymen (1,37).
2. Skrev `experiments/bortfall/inlard.py` (systemet `Inlard`, extraktion av särdrag och träning) och `tests/test_bortfall_inlard.py` (3 tester på syntetiska data).
3. Extraherade särdrag ur det längsta träningsfallet per träningsdag (28 fall, alla 360 min, varannan bild, högst 1500 slumpade pixlar per bild i hålet där radarn har data; 1,28 miljoner pixlar, 32 % våta). Tid: 12 min med två processer.
4. Tränade två modeller (204 s med två trådar), sparade dem i `/data/bortfall/modeller/inlard.pkl` (2,2 MB, med `inlard.json` som listar fallen) och frös dem innan valideringen. Inget är valt eller justerat på valideringen.
5. Provkörde på 3 valideringsfall och körde sedan domaren på alla 128.

## Systemet

Allt står också i docstringen i `inlard.py`.

- **Basen** per bild: den flyttade analysen (`meps_hal.Flytt`) och MEPS rättad mot radarn (`meps_hal.Rattning`, som `meps_hal.Meps`), alltså samma byggstenar som i uppgift 4.
- **Särdrag** per pixel i hålet (17): den flyttade analysen (log 1 + R) och den utjämnad på 10 och 30 km (normaliserad gaussfaltning där radarn utanför hålet är med, så att pixlar nära kanten ser grannskapet), MEPS rättad och utjämnad, bortfallets ålder, avståndet till hålets kant, avståndet till närmaste fungerande radar, tid på dygnet och årstid (sin och cos), medel och våt andel i en ring 60 km utanför hålet i samma bild, medlet av den flyttade analysen i hålet, och den sista riktiga radarbilden och medlet över uppvärmningstimmen på pixeln (stillastående, alltså ett mått på regn som sitter fast vid platsen). Saknade värden (MEPS för 2019, flyttad analys som har lämnat) ges som NaN, som HistGradientBoosting hanterar själv.
- **Höjden saknas.** Ingen öppen höjdmodell fanns lokalt (`/data` har bara radar, MEPS, SNOW och bortfallsdata), och jag valde att inte lägga tid och nedladdning på en i natt. De två stillastående särdragen ovan är en ersättning för det terrängbundna regnet, men ingen riktig.
- **Modellerna**: `HistGradientBoostingClassifier` för R ≥ 0,1 mm/h och `HistGradientBoostingRegressor` för log(1 + R) med kvadratfel; 300 iterationer, inlärningstakt 0,08, 31 löv, minst 200 pixlar per löv, tidigt stopp på 10 % (slog inte till; båda gick 300 varv).
- **Fördelningsmatchningen**: antalet våta pixlar i hålet är summan av sannolikheterna. De pixlarna väljs efter regressionens värde och får, i den ordningen, kvantilerna av de våta radarpixlarna i ringen 60 km utanför hålet i samma bild. Är ringen torr (färre än 20 våta) används regressionens egna värden.
- **Kanten**: i de yttersta 3 pixlarna (6 km) i hålet blandas fältet med ett gaussiskt utjämnat (sigma 2 pixlar) fält av hålet och radarn utanför, med vikten avtagande inåt.
- Körtid: ungefär som `Flytt` plus `Meps` (15 till 35 s per fall).

UTKAST: siffrorna fylls i när valideringen är klar.

Status: delvis
