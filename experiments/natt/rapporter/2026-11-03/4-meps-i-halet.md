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

| kandidat (t50 små / stora skalor, min) | poäng | 0 till 30 min: FSS 1 mm 30 km | FSS 5/30 | CSI 1 | 30 till 90: FSS 1/30 | FSS 5/30 | CSI 1 | vol | 90 till 360: FSS 1/30 | FSS 5/30 | CSI 1 | vol |
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

## Valideringen (domaren, 128 fall, 16 dagar)

Körtid med två processer: Blandning 32 min, Meps 14 min, Flytt 27 min. Domaren och baslinjerna är oförändrade (baslinjernas json från uppgift 3). Skillnad mot `fylld` (driften) med 95 %-intervall från bootstrap över dagarna; **fetstil** är domens bättre eller sämre. Hela tabellen: kommandot sist i rapporten.

### Ålder 0 till 30 min

| system | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm |
|---|---|---|---|---|---|---|---|---|---|
| fylld | 0,896 | 0,948 | 0,765 | 0,880 | 0,682 | 0,620 | 0,360 | 1,000 | 0,120 |
| Flytt | lika med fylld | | | | | | | | |
| Blandning | 0,896 | 0,948 | 0,765 | 0,880 | 0,682 | 0,620 | 0,360 | 1,000 | 0,120 |
| Meps | 0,584 | 0,660 | 0,265 | 0,371 | 0,401 | 0,336 | 0,096 | 1,048 | 0,189 |
| Meps − fylld | −0,311 [−0,371; −0,263] **sämre** | −0,289 [−0,356; −0,233] **sämre** | −0,500 [−0,567; −0,423] **sämre** | −0,509 [−0,592; −0,418] **sämre** | −0,281 [−0,323; −0,238] **sämre** | −0,283 [−0,320; −0,246] **sämre** | −0,263 [−0,305; −0,205] **sämre** | 0,048 [−0,012; 0,244] | 0,070 [0,047; 0,094] **sämre** |

### Ålder 30 till 90 min

| system | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm |
|---|---|---|---|---|---|---|---|---|---|
| fylld | 0,727 | 0,818 | 0,501 | 0,680 | 0,516 | 0,440 | 0,199 | 1,123 | 0,141 |
| Flytt | lika med fylld | | | | | | | | |
| Blandning | 0,727 | 0,818 | 0,501 | 0,680 | 0,517 | 0,441 | 0,199 | 1,124 | 0,141 |
| Meps | 0,553 | 0,626 | 0,275 | 0,372 | 0,382 | 0,316 | 0,105 | 1,199 | 0,207 |
| Meps − fylld | −0,174 [−0,211; −0,141] **sämre** | −0,192 [−0,229; −0,155] **sämre** | −0,227 [−0,279; −0,140] **sämre** | −0,308 [−0,365; −0,197] **sämre** | −0,134 [−0,169; −0,102] **sämre** | −0,124 [−0,160; −0,089] **sämre** | −0,094 [−0,147; −0,047] **sämre** | 0,076 [−0,154; 0,441] | 0,066 [0,033; 0,109] **sämre** |

Blandning − fylld de första 90 min: skillnaderna är högst 0,001, och domen ger formellt **bättre** för CSI 0,5 och 1, sömmen (0 till 30 min) och MAE mot mätarna (30 till 90 min), eftersom intervallen blir mycket smala när två system nästan är lika. Det är ingen verklig förbättring och ska inte läsas som en.

### Ålder 90 till 360 min (där driften inte har något)

| system | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm | MAE kvart | MAE timme |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fylld | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0,128 | 0,208 | 0,815 |
| Flytt | 0,632 | 0,728 | 0,380 | 0,493 | 0,424 | 0,365 | 0,161 | 1,366 | 0,128 | 0,197 | 0,741 |
| Blandning | 0,635 | 0,729 | 0,373 | 0,482 | 0,431 | 0,369 | 0,159 | 1,242 | 0,129 | 0,200 | 0,734 |
| Meps | 0,538 | 0,614 | 0,244 | 0,326 | 0,365 | 0,303 | 0,099 | 1,122 | 0,178 | 0,203 | 0,768 |
| (radarn mot mätarna) | | | | | | | | | | 0,152 | 0,575 |
| Flytt − fylld | 0,632 [0,550; 0,688] **bättre** | 0,728 [0,650; 0,775] **bättre** | 0,380 [0,187; 0,461] **bättre** | 0,493 [0,270; 0,540] **bättre** | 0,424 [0,354; 0,493] **bättre** | 0,365 [0,288; 0,424] **bättre** | 0,161 [0,063; 0,238] **bättre** | −0,634 [−0,992; −0,166] **bättre** | −0,000 [−0,016; 0,012] | −0,010 [−0,026; 0,019] | −0,074 [−0,127; 0,035] |
| Blandning − fylld | 0,635 [0,544; 0,693] **bättre** | 0,729 [0,641; 0,779] **bättre** | 0,373 [0,169; 0,463] **bättre** | 0,482 [0,249; 0,541] **bättre** | 0,431 [0,353; 0,506] **bättre** | 0,369 [0,283; 0,431] **bättre** | 0,159 [0,055; 0,238] **bättre** | −0,758 [−0,988; −0,498] **bättre** | 0,001 [−0,015; 0,013] | −0,008 [−0,021; 0,018] | −0,081 [−0,140; 0,026] |
| Meps − fylld | 0,538 [0,371; 0,607] **bättre** | 0,614 [0,435; 0,686] **bättre** | 0,244 [0,088; 0,345] **bättre** | 0,326 [0,116; 0,457] **bättre** | 0,365 [0,250; 0,441] **bättre** | 0,303 [0,183; 0,362] **bättre** | 0,099 [0,032; 0,148] **bättre** | −0,878 [−0,991; −0,501] **bättre** | 0,049 [0,021; 0,082] **sämre** | −0,005 [−0,015; 0,009] | −0,047 [−0,092; 0,066] |

Mot `Flytt` i stället för `fylld` (samma bootstrap), 90 till 360 min:

| | FSS 1 mm 10 km | FSS 1 mm 30 km | FSS 5 mm 10 km | FSS 5 mm 30 km | CSI 0,5 | CSI 1 | CSI 5 | volym | söm |
|---|---|---|---|---|---|---|---|---|---|
| Blandning − Flytt | 0,003 [−0,015; 0,013] | 0,002 [−0,020; 0,013] | −0,006 [−0,019; 0,010] | −0,011 [−0,025; 0,002] | 0,007 [−0,009; 0,020] | 0,004 [−0,010; 0,012] | −0,002 [−0,009; 0,008] | −0,124 [−0,360; 0,128] | 0,001 [−0,004; 0,004] |
| Meps − Flytt | −0,094 [−0,201; −0,051] **sämre** | −0,113 [−0,235; −0,068] **sämre** | −0,135 [−0,186; −0,007] **sämre** | −0,167 [−0,234; −0,035] **sämre** | −0,059 [−0,124; −0,021] **sämre** | −0,062 [−0,131; −0,028] **sämre** | −0,062 [−0,103; 0,006] | −0,244 [−0,674; 0,425] | 0,049 [0,027; 0,077] **sämre** |

## Vad siffrorna säger

- **MEPS rättad mot radarn är inte en bra analys i hålet.** Den är sämre än driften i alla mått de första 90 min (FSS 5 mm på 30 km 0,37 mot 0,88 de första 30 min) och sämre än den flyttade analysen även efter 90 min, och den ger en kantigare söm. Rättningen håller volymen ungefär rätt (1,05 till 1,20), men läget och strukturen är fel på de här skalorna. Mot ingenting alls (driften efter 90 min) är den förstås bättre.
- **Det som ger vinsten efter 90 min är att inte släppa den flyttade analysen.** `Flytt` (samma `fill_gaps` med `max_age` oändlig) slår driften kraftigt efter 90 min (FSS 1 mm på 30 km 0,73, CSI 1 mm 0,37) och är identisk med driften före. Det är en ändring av en parameter i `composite.fill_gaps` och det största enskilda fyndet i uppgiften. Volymen blir dock för stor (1,37): regn utanför hålet förs in och regnet i hålet dör inte ut.
- **Blandningen med MEPS är inte säkert bättre än `Flytt`** i något mått (alla intervall mot `Flytt` korsar 0). Punkterna tyder på att MEPS drar ner volymfelet (1,24 mot 1,37) och höjer CSI lite, men sänker FSS 5 mm lite. Vikterna som valdes på träningen ger MEPS mycket liten vikt (0,07 vid 90 min, 0,5 vid 6 h för de små skalorna), och sökningen visade att poängen växte ju mindre MEPS fick vara med.
- **Mätarna** pekar åt samma håll men är inte avgörande: efter 90 min har Blandning och Flytt lägre MAE per timme än driften (0,73 och 0,74 mot 0,82 mm), med intervall som korsar 0.
- Sammantaget: av de här systemen är `Flytt` eller `Blandning` bäst, och de är lika bra enligt domaren. Det enklaste att föra vidare är `Flytt`; MEPS behövs inte för den vinsten.

## Vad som inte är gjort, och begränsningar

- **Prognosen efteråt** (kedjan när radarn kommer tillbaka) är inte mätt; domaren mäter den inte än (rapport 3), och det är uppgift 6.
- Ingen ändring i `src/knep/composite.py`. Att höja `max_age` i driften vore ett litet ingrepp, men det ska prövas med prognosen efteråt och kvaliteten (`exp(−ålder/30)`) i kartan först, och det rör driften när det mergas. Förslag till uppgift 6: jämför `fylld` och `meps_hal:Flytt` även på prognosen efteråt.
- Volymen i den långa flyttade analysen (1,37) är det tydligaste felet kvar. En rättning av mängden i hålet mot radarn utanför (som kvantilavbildningen gör för MEPS) eller en avklingning med åldern är naturliga nästa försök, och kandidater till uppgift 5:s inlärda blandning.
- MEPS-rättningen är `seamless.py` som den är, med ledtid 0 (full lägesrättning). Jag provade inte andra rättningar (till exempel ett större fönster för kvantilerna eller en ren volymfaktor); med tanke på hur långt efter MEPS ligger i läge är det inte troligt att det vänder resultatet.
- Urvalet för sökningen var 56 av 223 träningsfall (de två längsta per dag) och varannan bild, för att hinnas med.
- 16 valideringsfall (2019) saknar MEPS och får `fylld` i Meps och Blandning, men den långa flyttade analysen i Flytt. Efter 90 min gynnar det Flytt något i jämförelsen med Blandning.
- Provkörningens fil `experiments/bortfall/resultat/traning/meps_sok_prov2.json` är inaktuell (andra kandidater) och ligger kvar ocommittad.

## Nästa steg

1. Uppgift 5 (inlärd blandning): använd `meps_hal:Flytt` som baslinje vid sidan av `fylld`, eftersom det är den som ska slås efter 90 min. MEPS kan vara ett särdrag, men inte mer än så enligt den här uppgiften.
2. Uppgift 6: prognosen efteråt för `fylld`, `Flytt` och `Blandning`.
3. Om `Flytt` håller även på prognosen: en liten PR som höjer `max_age` i `fill_gaps` i drift, med test.

## Filer

- `experiments/bortfall/meps_hal.py` (nytt): systemen `Meps`, `Flytt`, `Blandning` och sökningen (`sok`)
- `experiments/bortfall/meps_vikter.json` (nytt, fryst före valideringen)
- `experiments/bortfall/resultat/traning/meps_sok.json` (nytt)
- `experiments/bortfall/resultat/validering/meps_hal_{Blandning,Meps,Flytt}.json` (nya)
- `tests/test_bortfall_meps_hal.py` (nytt, 8 tester)
- `experiments/natt/rapporter/2026-11-03/4-meps-i-halet.md`

Inga ändringar i `src/knep/` eller i domaren. `uv run pytest`: 97 passerade.

```sh
uv run python experiments/bortfall/meps_hal.py sok --processer 2 --logg /data/bortfall/logg/meps_sok.log
uv run python experiments/bortfall/domare.py kor meps_hal:Blandning meps_hal:Meps meps_hal:Flytt --processer 2 --logg /data/bortfall/logg/meps_validering.log
uv run python experiments/bortfall/domare.py tabell fylld hal meps_hal:Flytt meps_hal:Meps meps_hal:Blandning --mot fylld
```

Status: klar
