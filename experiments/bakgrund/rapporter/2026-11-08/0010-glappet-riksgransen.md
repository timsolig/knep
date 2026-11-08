# 0010 Glappet nordväst om Riksgränsen: SMHI:s nolla slår ut OPERA

Kort: Glappet är verkligt och systematiskt (SMHI 0 där OPERA har minst 0,1 mm/h i 59 % av rutbilderna där svensk stråle är över 2 km och 84 % över 4 km på 9 träningsdagar, mot cirka 25 % närmare radarerna), och regeln `composite.layer_far` med H = 2 km, vald på träningen, fyller bågen i fallet (rutan vid Narvik 0,000 till 0,39 till 0,65 mm/h) och höjer kvot våt per timme vid zonens mätare på valideringen från 0,729 till 0,802 (+0,095, +0,055 till +0,111), men domaren godkänner den inte mot A0 eftersom falska ekon blir fler (falskt vid torr mätare per timme 0,015 mot 0,011, −0,004, −0,005 till −0,003; rutor med eko i torra timmar 66,3 mot 60,8 per dag), och ingen av fem varianter (H 2, 3, 4 och tröskel 0,3 mm/h) godkänns ens på träningen; valet `--opera-fjarr` finns avstängt.

## Vad som gjordes

1. **Fallet** 2026-11-07 16:00 till 18:15 UTC återskapat med SMHI:s bilder ur SMHI:s arkiv och OPERA ur `openradar-archive` (`experiments/riksgransen/fall.py`).
2. **Frekvensen** på 9 träningsdagar med regn i norr, mot de svenska radarernas strålhöjd och avstånd, vid mätarna och kring Røst och Andøya (`frekvens.py`, `tabeller.py`).
3. **Regeln** `composite.far_zone(grid, h_km)` och `composite.layer_far(rain, source, extra, code, far, min_extra=0.1, mode="torr")` i `src/knep/analys/composite.py`, kopplad som valet `--opera-fjarr KM` i `cli.py` (kräver `--fallback`, av som standard). H valdes på träningen med en regel som skrevs i `frekvens.py` innan siffrorna sågs.
4. **Domaren** med systemet A0O (`a0o.py`), domarens A0 med OPERA enligt regeln, på de 6 valideringsdagar som har regn norr om 66 N. A0 räknades om ur samma bilder och blev bit för bit domarens befintliga dagfiler på alla 6 dagar.
5. **Efteråt, bara på träningen**: fem varianter genom domaren som underlag till nästa steg (`a0o.py trana`, `urval_tr.py`). Valideringen kördes inte igen.

### Dagarna

Valda på andelen rutor norr om 66 N där SMHI:s komposit har över 0,1 mm/h, en bild i timmen (`dagar.py`, beror inte på OPERA eller något resultat): träningsdagar med andel minst 0,06 (2020-02-10, 2020-07-24, 2021-04-05, 2022-12-20, 2023-08-02, 2024-07-28, 2024-09-26, 2024-11-25, 2024-12-19) och valideringsdagar med minst 0,02 (2019-03-08, 2019-03-17, 2020-05-10, 2021-10-05, 2021-10-20, 2023-11-04, 2025-07-29). **2023-11-04 föll bort**: arkivet har bara produkten `QIND_RATE` den dagen, ingen DBZH. Kvar är 6 valideringsdagar, över domarens krav på 5.

### OPERA i arkivet

Före 2024 har `openradar-archive` bara OPERA var 15:e minut och under ett annat namn (`OPERA@...@0@DBZH_QIND.h5`, float64 med gain och nodata under `dataset1/what`), från 2024 var 5:e minut som `DBZH.h5`. `sources.fetch_opera` och `read_opera` klarar bara det nya formatet (det räcker för drift). Experimentet läser båda (`zon.read_opera_any`) och hämtade var 15:e minut för alla dagar; varje 5-minutersbild i A0O får OPERA från närmaste kvart (högst 5 minuter bort). I drift finns OPERA var 5:e minut, så A0O är något sämre i tiden än drift skulle vara. Regeln läggs på A0:s bilder efter utfyllnaden; i drift kommer den före, vilket bara skiljer där SMHI saknar data i zonen (och där tar drift ändå OPERA).

## Fallet 2026-11-07

Rutan 68,3 till 68,7 N, 15,9 till 17,5 E (718 rutor, svensk stråle 3,2 till 5,6 km, 148 till 224 km från närmaste svenska radar):

| tid | SMHI 0 | SMHI NaN | glapp (SMHI 0, OPERA > 0,1) | A0 i dag, medel mm/h | med regeln H = 2, medel mm/h | våta rutor (≥ 0,1) före / efter |
|---|---|---|---|---|---|---|
| 16:00 | 718 | 0 | 679 | 0,000 | 0,585 | 0 / 679 |
| 16:15 | 718 | 0 | 663 | 0,000 | 0,456 | 0 / 663 |
| 16:30 | 718 | 0 | 703 | 0,000 | 0,511 | 0 / 703 |
| 16:45 | 718 | 0 | 718 | 0,000 | 0,496 | 0 / 718 |
| 17:00 | 718 | 0 | 718 | 0,000 | 0,386 | 0 / 718 |
| 17:15 | 718 | 0 | 695 | 0,000 | 0,358 | 0 / 695 |
| 17:30 | 718 | 0 | 693 | 0,000 | 0,474 | 0 / 693 |
| 17:45 | 718 | 0 | 657 | 0,000 | 0,544 | 0 / 657 |
| 18:00 | 718 | 0 | 717 | 0,000 | 0,628 | 0 / 717 |
| 18:15 | 712 | 0 | 712 | 0,011 | 0,648 | 6 / 718 |

I hela zonen (H = 2) ändrar regeln 9 600 till 10 400 rutor per bild. Norr om 66 N i fallet är SMHI 0 i 23 till 27 % av OPERA:s våta rutor inom 140 km från en svensk radar, 90 % vid 140 till 180 km och 100 % vid 180 till 220 km: Kiruna ser i stort sett inget bortom 180 km den dagen.

Kartor före och efter (SMHI, A0 i dag med OPERA bara där SMHI är NaN, A0 med regeln; rött är zonen, svart SMHI:s täckning): `/data/riksgransen/fall_1600_H2.png`, `fall_1700_H2.png`, `fall_1815_H2.png`. Bågen syns tydligt i mitten som en torr remsa innanför SMHI:s rand, och till höger hänger fältet ihop över randen.

## Frekvensen på träningen (9 dagar, OPERA var 15:e minut)

Mot strålhöjden (svenska radarer, 0,5°):

| strålhöjd (km) | rutbilder med OPERA ≥ 0,1 | varav SMHI 0 | andel | SMHI ≥ 0,1 | varav OPERA 0 | andel |
|---|---|---|---|---|---|---|
| 0 till 0,5 | 1778801 | 713878 | 0,40 | 940833 | 43916 | 0,05 |
| 0,5 till 1 | 5971338 | 1718207 | 0,29 | 3813724 | 184019 | 0,05 |
| 1 till 1,5 | 7880249 | 1946163 | 0,25 | 5798634 | 306671 | 0,05 |
| 1,5 till 2 | 6956749 | 1698242 | 0,24 | 5623851 | 304128 | 0,05 |
| 2 till 2,5 | 5562895 | 1505282 | 0,27 | 4528833 | 250103 | 0,06 |
| 2,5 till 3 | 4559588 | 1619521 | 0,36 | 3265912 | 171015 | 0,05 |
| 3 till 3,5 | 3948268 | 1953501 | 0,49 | 2176556 | 103684 | 0,05 |
| 3,5 till 4 | 3702865 | 2323252 | 0,63 | 1493529 | 73538 | 0,05 |
| 4 till 4,5 | 3613186 | 2683331 | 0,74 | 1004727 | 50875 | 0,05 |
| 4,5 till 5 | 3569322 | 2968894 | 0,83 | 651874 | 35652 | 0,05 |
| 5 till 5,5 | 3507265 | 3135616 | 0,89 | 406285 | 23938 | 0,06 |
| 5,5 till 6 | 1626771 | 1552933 | 0,95 | 81960 | 5308 | 0,06 |
| över 6 | 676090 | 624506 | 0,92 | 59386 | 5108 | 0,09 |

Mot avståndet till närmaste svenska radar:

| avstånd (km) | OPERA ≥ 0,1 | varav SMHI 0 | andel | SMHI ≥ 0,1 | varav OPERA 0 | andel |
|---|---|---|---|---|---|---|
| 0 till 20 | 1013919 | 463877 | 0,46 | 490343 | 25300 | 0,05 |
| 20 till 40 | 2640911 | 910205 | 0,34 | 1562573 | 101374 | 0,06 |
| 40 till 60 | 4062295 | 1061370 | 0,26 | 2738222 | 160266 | 0,06 |
| 60 till 80 | 5322661 | 1245442 | 0,23 | 3944866 | 207384 | 0,05 |
| 80 till 100 | 6072861 | 1438856 | 0,24 | 4817867 | 254135 | 0,05 |
| 100 till 120 | 5593722 | 1411112 | 0,25 | 4582506 | 241851 | 0,05 |
| 120 till 140 | 4991184 | 1500558 | 0,30 | 3866370 | 191713 | 0,05 |
| 140 till 160 | 4544648 | 1898276 | 0,42 | 2875031 | 126673 | 0,04 |
| 160 till 180 | 4401831 | 2494774 | 0,57 | 2055773 | 94821 | 0,05 |
| 180 till 200 | 4570884 | 3231944 | 0,71 | 1442584 | 71154 | 0,05 |
| 200 till 220 | 4831728 | 3987710 | 0,83 | 912429 | 48200 | 0,05 |
| 220 till 240 | 4725957 | 4264811 | 0,90 | 504274 | 30594 | 0,06 |

Glappet växer jämnt med strålhöjden från cirka 2,5 km (160 km). Omvänt (SMHI har regn, OPERA 0) är 5 % överallt, så det är inte ett allmänt avvikande OPERA. Även nära radarerna är SMHI 0 i en fjärdedel av OPERA:s våta rutor; det är svagt eko nära tröskeln och SMHI:s egen rensning, och därför sitter zonen långt ut.

### Regeln vald på träningen

Kandidater H = 2, 3 och 4 km; den minsta H där (a) SMHI är 0 i minst hälften av OPERA:s våta rutbilder i zonen och (b) mätaren har regn i minst hälften av de mätartimmar där regeln ändrar något (minst 20 timmar). Timmarna är medel av de fyra kvartsbilderna.

| H (km) | rutor i zonen | OPERA ≥ 0,1 | varav SMHI 0 (a) | mätartimmar i zonen | stationer | ändrade timmar | varav mätaren våt (b) | mätare mm / OPERA mm i ändrade | SMHI och OPERA torra, mätaren våt |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 152940 | 30185464 | 17832445 (0,59) | 7163 | 39 | 292 | 164 (0,56) | 0,69 | 4260 (0,14) |
| 3 | 100330 | 20062981 | 14707642 (0,73) | 1134 | 6 | 71 | 52 (0,73) | 1,49 | 807 (0,24) |
| 4 | 60850 | 12411848 | 10430889 (0,84) | 521 | 3 | 54 | 46 (0,85) | 1,85 | 368 (0,25) |

Som jämförelse, alla mätare (ingen zon): av 1 299 timmar där SMHI är 0 och OPERA våt har mätaren regn i 35 %. Regeln valde **H = 2, "torr"** ("max" gav högre MAE mot mätarna vid H = 2: 1,204 mot SMHI:s 0,788 i 534 timmar). Siffrorna visar redan risken: vid H = 2 är 44 % av de ändrade mätartimmarna torra, mot 27 % vid H = 3 och 15 % vid H = 4.

## Domaren: A0O (H = 2) mot A0 på valideringen

6 dagar, `domare.py tabell A0O --mot A0` (dagfilerna i `/data/analys/domare_v2/A0O/`, tabellen i `tabell_A0O_mot_A0_validering.json`). Utdrag; hela tabellen skrivs ut av kommandot.

| mått | A0O | A0 | skillnad i godhet (95 %) |
|---|---|---|---|
| kvart kvot våt | 0,689 | 0,676 | +0,018 (+0,007 till +0,029) |
| kvart FSS 0,5 | 0,518 | 0,515 | +0,003 (+0,000 till +0,005) |
| kvart CSI 1 | 0,232 | 0,236 | −0,004 (−0,007 till −0,002) |
| kvart falskt vid torr mätare | 0,032 | 0,028 | −0,004 (−0,005 till −0,003) |
| timme kvot våt | 0,813 | 0,798 | +0,019 (+0,008 till +0,026) |
| timme kvot >1 mm | 0,716 | 0,709 | +0,010 (+0,001 till +0,017) |
| timme MAE | 0,236 | 0,232 | −0,005 (−0,009 till −0,001) |
| timme CSI 1 | 0,415 | 0,419 | −0,004 (−0,007 till −0,001) |
| timme FSS 0,5 | 0,712 | 0,706 | +0,006 (+0,001 till +0,013) |
| timme falskt vid torr mätare | 0,015 | 0,011 | −0,004 (−0,005 till −0,003) |
| timme falskt där allt inom 25 km är torrt | 0,014 | 0,011 | −0,004 (−0,005 till −0,003) |
| timme över 400 m kvot våt | 0,530 | 0,476 | +0,106 (+0,051 till +0,132) |
| timme över 400 m FSS 0,5 | 0,521 | 0,468 | +0,052 (+0,002 till +0,103) |
| kvart över 400 m falskt vid torr mätare | 0,017 | 0,015 | −0,002 (−0,004 till −0,001) |
| kvart lovart falskt vid torr mätare | 0,025 | 0,020 | −0,005 (−0,010 till −0,001) |
| rutor med eko i över hälften av de torra timmarna, per dag | 66,3 | 60,8 | −5,5 (−12,0 till −1,0) |

Domen (kvot våt): **inte bättre**. Bättre i kvart kvot våt, kvart FSS 0,5, timme kvot våt, timme kvot >1 mm och timme FSS 0,5; sämre i falskt vid torr mätare och där allt inom 25 km är torrt (kvart och timme, kvart över 400 m och på lovartsidan) och i rutorna med eko under torra timmar. Den gamla regeln (kvot summa) ger samma dom.

### Bara zonens mätare (diagnostik, ändrar inte domens regel)

Zonen H = 2 har 36 svenska stationer på valideringsdagarna (cirka 850 mätartimmar per dag av cirka 3 250). Det räcker för underlag; Katterjåkk och Riksgränsen ligger knappt i den (strålen cirka 2,5 till 2,7 km), Abisko inte.

| mått (zonens mätare) | A0O | A0 | skillnad i godhet (95 %) |
|---|---|---|---|
| kvart kvot våt | 0,689 | 0,634 | +0,084 (+0,039 till +0,106) |
| kvart falskt vid torr mätare | 0,037 | 0,024 | −0,013 (−0,017 till −0,009) |
| kvart över 400 m kvot våt | 0,314 | 0,164 | +0,648 (+0,308 till +0,938) |
| timme kvot våt | 0,802 | 0,729 | +0,095 (+0,055 till +0,111) |
| timme kvot >1 mm | 0,803 | 0,766 | +0,048 (+0,005 till +0,064) |
| timme MAE | 0,236 | 0,218 | −0,018 (−0,033 till −0,006) |
| timme CSI 1 | 0,326 | 0,340 | −0,014 (−0,041 till −0,001) |
| timme FSS 0,5 | 0,621 | 0,588 | +0,033 (+0,008 till +0,059) |
| timme falskt vid torr mätare | 0,024 | 0,010 | −0,013 (−0,017 till −0,010) |

I zonen ger OPERA klart mer av det regn som SMHI missar (i fjällen över 400 m fördubblas kvoten per kvart, från 0,164 till 0,314), men falska ekon vid torra mätare blir mer än dubbelt så många per timme. Tabellen finns i `/data/riksgransen/domare_zon/tabell_A0O_mot_A0_validering.json`.

## Efteråt på träningen: fem varianter (bara underlag)

Samma domare på de 9 träningsdagarna (zonens mått med zonen för variantens H). Regeln skrevs i `urval_tr.py` innan siffrorna sågs: bland godkända väljs den med störst förbättring av kvot våt per timme i zonen.

| variant | H | min OPERA mm/h | godkänd | kvot våt timme, zonen (A0) skillnad (95 %) | falskt timme, zonen (A0) skillnad (95 %) | falskt timme, alla (A0) skillnad (95 %) | rutor per dag (A0) |
|---|---|---|---|---|---|---|---|
| H2 | 2 | 0,1 | nej | 0,789 (0,675) +0,156 (+0,083 till +0,299) | 0,0273 (0,0188) −0,0086 (−0,0168 till −0,0029) | 0,0124 (0,0103) −0,0020 (−0,0040 till −0,0007) | 61,1 (45,8) |
| H3 | 3 | 0,1 | nej | 0,438 (0,354) +0,214 (+0,125 till +0,368) | 0,0234 (0,0137) −0,0096 (−0,0233 till +0,0000) | 0,0107 (0,0103) −0,0003 (−0,0007 till +0,0000) | 46,8 (45,8) |
| H4 | 4 | 0,1 | nej | 0,231 (0,113) +0,715 (+0,467 till +2,060) | 0,0269 (0,0180) −0,0090 (−0,0262 till +0,0000) | 0,0105 (0,0103) −0,0001 (−0,0004 till +0,0000) | 45,8 (45,8) |
| H2t03 | 2 | 0,3 | nej | 0,771 (0,675) +0,132 (+0,054 till +0,277) | 0,0269 (0,0188) −0,0082 (−0,0164 till −0,0026) | 0,0123 (0,0103) −0,0019 (−0,0038 till −0,0006) | 57,4 (45,8) |
| H3t03 | 3 | 0,3 | nej | 0,406 (0,354) +0,138 (+0,063 till +0,271) | 0,0234 (0,0137) −0,0096 (−0,0233 till +0,0000) | 0,0107 (0,0103) −0,0003 (−0,0007 till +0,0000) | 46,3 (45,8) |

Ingen godkänns. Alla fälls av falskt vid torr mätare per kvart (alla mätare), H3 och H4 dessutom av FSS 1 per kvart över 400 m. Per timme med alla mätare är H3 och H4 nära neutrala (intervallen når 0), och kartmåttet är oförändrat för H4. Tröskeln 0,3 mm/h hjälper inte. Inget valdes.

Troliga orsaker, inte prövade: (1) OPERA bara var 15:e minut i arkivet, så en kvart i A0O bär OPERA som är upp till 5 minuter fel i tiden; per kvart kostar det träffar och ger eko vid torra kvartar. (2) Mätarnas underfångst av snö i fjällen i vinterfallen (svagt eko i OPERA, 0 mm i mätaren). (3) OPERA:s svaga eko i zonen är delvis verkligt men når inte marken (avdunstning under grunda moln).

## Røst och Andøya

Andelen bilder med OPERA-eko (≥ 0,1 mm/h) i ringar kring platserna, träningsdagarna:

| ring (km) | OPERA-eko | SMHI har data (rutbilder) | glapp i zonen H = 2 / 3 / 4 |
|---|---|---|---|
| Røst 0 till 10 | 0,760 | 0 | 0 |
| Røst 10 till 20 | 0,622 | 0 | 0 |
| Røst 20 till 40 | 0,48 till 0,54 | 0 | 0 |
| Røst 40 till 80 | 0,41 till 0,45 | 0 | 0 |
| Andøya 0 till 10 | 0,504 | 0 | 0 |
| Andøya 10 till 20 | 0,361 | 0 | 0 |
| Andøya 20 till 30 | 0,331 | 60590 | 22365 / 22365 / 22365 |
| Andøya 30 till 40 | 0,345 | 123670 | 57831 / 57831 / 57831 |
| Andøya 40 till 60 | 0,297 | 436294 | 153468 / 153468 / 153468 |
| Andøya 60 till 80 | 0,254 | 659850 | 186568 / 186568 / 185604 |

Røst ligger helt utanför SMHI:s täckning; regeln ändrar inget där (klottret finns redan i A0 via `layer`). Andøyas kärna (0 till 20 km, där ekot är tydligt förhöjt) ligger också utanför SMHI:s täckning. Från 20 km är OPERA:s ekofrekvens bara lite över omgivningen (0,33 mot 0,25 till 0,30), och där tar regeln in OPERA. Regeln tar alltså inte in klottret i kärnan, men en svag förhöjning 20 till 40 km från Andøya följer med. Masken för OPERA-radarerna (nästa idé i `IDEER.md`) behövs oavsett.

## Prognosens start (inte räknad)

Med regeln på skulle kedjans start ha regnet i bågen, så att nederbörd som kommer in från havet inte försvinner i bågen och dyker upp igen närmare Kiruna. Rörelsefältet skulle få spår över randen i stället för ett hål, och platskartan och fördelningsmatchningen skulle se mer svagt regn i zonen. Med de fler falska ekona skulle kedjan också föra fram svagt eko där mätarna är torra. Ingen prognos är räknad.

## Disk och tid

- `/data/riksgransen/`: 175 MB (OPERA-utsnitt var 15:e minut för 16 dagar, cirka 10 till 16 MB per dag som uint8 i `npz`; fallet 0,6 MB; kartor och dagfiler). Originalfilerna (cirka 1 till 1,8 MB var) raderades direkt efter utskärningen. Ledigt på `/data` 3,8 GB efteråt.
- Hämtningen: cirka 100 s per dag och process (1 anrop per sekund), två processer, cirka 20 minuter. A0O cirka 100 s per valideringsdag; fem varianter på träningen cirka 6,5 min per dag.

## Filer som ändrades

- `src/knep/analys/composite.py`: `far_zone` och `layer_far` (nya, används bara med valet).
- `src/knep/analys/__init__.py`: `bygg(..., opera_fjarr=None)` och `_analyses`; utan valet är flödet som förut (OPERA hämtas bara vid hål). Med valet hämtas OPERA varje cykel och `layer_far` läggs på efter `layer`; zonen räknas en gång per rutnät (`far_zone`).
- `src/knep/cli.py`: valet `--opera-fjarr KM` (av som standard; `deploy/` är inte ändrad).
- `tests/test_composite_far.py`: zonen täcker Narvik men inte Kiruna, Stockholm eller Røst; `layer_far` tar OPERA bara i zonen och bara där SMHI är torr; tom zon ändrar inget; `_analyses` utan valet är oförändrad och hämtar ingen OPERA utan hål, med valet tas OPERA i zonen.
- `experiments/riksgransen/`: `zon.py`, `fall.py`, `dagar.py`, `hamta.py`, `frekvens.py`, `tabeller.py`, `a0o.py`, `urval_tr.py`.

`uv run pytest`: 212 passerade, både före den första och före den sista commiten.

Säkerställd förbättring: nej

## Rekommendation

Slå **inte** på `--opera-fjarr` i drift nu. Domaren fäller den på valideringen och ingen variant klarar ens träningen; priset är fler falska ekon vid torra mätare. Det som talar för den är att glappet är verkligt och stort i fjällen och över Norge, och att det syns på sidan. Om användaren vill att sidan inte ska ha bågen kan valet slås på med H = 3 eller 4 för att se hur det ser ut (vid H = 4 är kartmåttet och falska ekon per timme nära oförändrade på träningen, men det är inte godkänt per kvart); det är ett beslut om sidans utseende, inte något domaren stöder.

## Nästa steg

1. Pröva regeln med OPERA var 5:e minut, bara på dagar från 2024 (arkivet har det då), för att skilja tidsfelet från verkliga falska ekon. Träningsdagarna 2024-07-28, 2024-09-26, 2024-11-25, 2024-12-19 och 2025-06-23, 2025-09-15, 2025-10-24 har 5-minutersbilder.
2. En villkorad regel: OPERA i zonen bara där SMHI har eko inom till exempel 20 km (glappet ligger vid randen av ett system som SMHI ser), eller bara med OPERA över 0,5 mm/h och sammanhängande yta. Väljs på träningen med domaren (`a0o.py trana`, `urval_tr.py`) och bedöms en gång på valideringen.
3. Masken kring OPERA-radarerna (Røst, Andøya) först, eftersom den rör samma del av A0.

Status: klar
