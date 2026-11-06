# Uppgift 2: domaren för analysen

Uppgift 1 (artefakterna) var klar enligt sin rapport, så inget behövde göras om före den här uppgiften.

## Vad jag gjorde

`experiments/analys/domare.py` är domaren, med tester i `tests/test_analys_domare.py` (11 tester på syntetiska data). Kommandona:

    uv run python experiments/analys/domare.py kor A0 A1 [--del validering] [--dag ÅÅÅÅ-MM-DD] [--bit 0/2]
    uv run python experiments/analys/domare.py tabell A1 --mot A0

### Gränssnittet

Ett system är en klass med `namn`, `matare` (True om det använder regnmätarna) och `falt(dag, matare) -> (kvart, timme)`. Fälten är nederbörden i mm per kvart, (96, H, W), och per timme, (24, H, W), på radarns rutnät, med NaN där analysen saknar data. Kvart k slutar 00:15 + 15k min och timme h slutar 01:00 + h timmar (UTC), som mätarnas tidsstämplar (de anger periodens slut, som i `bias.py` och bortfallsdomaren). `dag` (klassen `Dag`) har mätarna för dagen, höjden och lovartmasken; `matare` är `None` för system utan mätare och annars de mätare systemet får se.

### Korsvalideringen

- Rutnätet delas i block om 100 km (50 rutor). Varje block hör till en av fem grupper, grupp = (blockrad + 2 · blockkolumn) mod 5, så att två block som gränsar till varandra aldrig hör till samma grupp. Det ger 30 till 50 mätare per grupp.
- Ett system med mätare körs en gång per grupp k och får bara mätarna utanför gruppen **och mer än 25 km från den** (`Dag.training`), så att en grannmätare på andra sidan blockgränsen inte avslöjar svaret.
- Fältet som bedöms sätts ihop ruta för ruta: rutorna i grupp k tas ur körningen som inte såg grupp k (`run_system`). Alla mått räknas sedan på det sammansatta fältet, även kartmåttet för falska ekon.
- System utan mätare (A0, A1) körs en gång, och det sammansatta fältet är då fältet självt. De bedöms alltså på samma mätare och grupper.
- Testet `test_cross_validation_hides_the_judged_group` kontrollerar med ett spionsystem att ingen körning ser en mätare i gruppen eller inom 25 km från den, och att varje grupps rutor kommer ur rätt körning.

### Måtten

Per dag sparas summor (antal, summor, träffar, missar, falsklarm, FSS-termer, hopp) per upplösning och delmängd i `/data/analys/domare/<system>/<dag>.json`. Måtten för flera dagar och för varje bootstrapdragning räknas ur summorna, så att dagar med mycket regn väger som de ska.

- **Mängden**: kvoten summa(analys) / summa(mätare); samma kvot för perioder där mätaren har över 1, 5 och 10 mm; MAE i mm per period.
- **Träffen**: CSI vid 0,5, 1 och 5 mm per period i mätarens ruta. FSS mot punkterna: P är andelen rutor över tröskeln i ett fönster om 11 × 11 rutor (22 km) kring mätaren, O är 0 eller 1 för mätaren, och FSS = 1 − Σ(P − O)² / (ΣP² + ΣO²).
- **Falska ekon**: andelen perioder med analyserat regn (över 0,5 mm per timme, för kvarten 0,125 mm, alltså samma intensitet) vid mätare som visar 0 mm, och samma där alla mätare inom 25 km visar 0 mm. Dessutom per dag antalet rutor med eko (över 0,5 mm) i mer än hälften av de torra timmarna, för rutor med minst 6 torra timmar (torr = minst en p7-mätare inom 25 km, och alla visar 0).
- **Terrängen**: alla mått ovan för mätare över 400 m (GLO-90 i mätarens ruta) och för mätartimmar på lovartsidan. Lovart är när rörelsen uppför den utjämnade terrängen (Gauss 10 km) är minst 3 m per 5 min, och rutan ligger i fjällen (höjden utjämnad med Gauss 20 km över 300 m) eller på sydsvenska höjdområdet (lat 56,5 till 58,5, lon 13,3 till 16,2, utjämnad höjd över 120 m). Rörelsen är timmens medel av kedjans rörelsefält ur radarn; det är samma för alla system, så delmängden beror inte på systemet.
- **Hoppen mellan kvartarna**: för timmar där mätaren har alla fyra kvartarna och någon av mätaren och analysen har regn, Σ|kvart(k) − kvart(k − 1)| för analysen delat med samma summa för mätaren. 1 betyder att analysen hoppar lika mycket som mätaren.
- **Skillnaden mot en baslinje**: dagarna dras med återläggning 2000 gånger med fast frö, summorna läggs ihop och måtten räknas om för båda systemen på samma dragning. Skillnaden redovisas som skillnad i *godhet*, där större alltid är bättre: +Δ för CSI och FSS, −Δ för MAE och falska ekon, och för kvoterna −(|ln kvot| − |ln kvot_bas|), så att det är avståndet till 1 som räknas. 95 %-intervallet är 2,5 och 97,5 percentilerna.
- **Domen** (`verdict`): bättre bara om något mått för mängd eller träff (kvart eller timme, alla mätare) har intervallet helt över 0, och inget mått för falska ekon (alla mätare och kartmåttet) eller för mängd, träff och falska ekon i terrängens delmängder har intervallet helt under 0. Hoppen redovisas men ingår inte i domen, eftersom uppdraget bara kräver att de inte är större än mätarnas.

### Mätarna

`p7.npz` (timme) och `p14.npz` (kvart) filtreras på dagens perioder direkt när filen läses. **Båda har orimliga värden** (största värde 498 071 mm), så värden under 0 eller över 100 mm per timme och 60 mm per kvart tas bort. Bortfallsdomaren använder 60 och 30 mm; skillnaden påverkar bara de extremt få värdena där emellan. Mätarnas tid räknas om till period och en rad per station och period behålls.

### Baslinjerna

`Radardag` läser dagens bilder från 23:30 dagen före till 24:00 och räknar kedjans rörelsefält (`motion_field` på bilderna t − 30, t − 15 och t, steg 4, som `Chain` med gap 3) **var 15:e minut** i stället för var 5:e minut som i drift, för att hinna. Rörelsen sparas glest (var 4:e ruta, float16) i `/data/analys/domare/rorelse/` och interpoleras bilinjärt upp, vilket är samma sak som kedjan gör med steg 4. Ett intervall använder senaste rörelsefältet, som drift.

- **A0**: SMHI:s komposit med den lagrangeska utfyllnaden vid bortfall (`composite.fill_gaps`, utan reserverna OPERA och volymer, som drift utan `--fallback`) och utan volymkorrektion, eftersom bias-v1 inte är släppt. Varje bild gäller de fem minuterna före den.
- **A1**: `knep.analys.a1.interval_mean` på A0:s bilder längs rörelsen, en tid per minut.
- Kvart och timme är medlet av intervallen gånger periodens längd, om minst två tredjedelar av intervallen har data.

Provkörningen på 2023-08-08 tog 2 min för A0 och 5 min för A1 med en process. Den ingår i valideringen (2023-08-08 är en valideringsdag).

(resultaten fylls i)

Status: delvis
