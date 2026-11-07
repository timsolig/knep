# Uppgift 0007: sidans texter för A2 och kontrollen av mätarna per station och dygn (A2TS)

(Under arbete. Urvalsregeln nedan skrevs och committades innan varianterna på hela träningen lästes.)

## Urvalsregeln för A2TS (skriven före resultaten)

Varianterna är `VARIANTER_QCS` i `experiments/analys/a2.py` (24 stycken: N = 8/3, 12/4 eller 24/6 perioder per kvart/timme, R = 75 eller 100 km, med och utan skydd över 400 m, och "noll mot vått" vid starkt eller svagare regn). Allt på de 28 träningsdagarna.

1. **Diagnosen** (`a2.py stationer`, alla mätare som i drift): kastade riktiga stationsdygn på rena data, och andelen hittade av de syntetiska dygnsfelen (3 % av stationerna per dag, en tredjedel var fast värde, noll, för våt), bland de skadliga (Σ|fel| över dygnet minst 2 mm i kvartarna).
2. **Tillåten** är en variant som kastar högst 0,3 % av de riktiga stationsdygnen på rena data, och som i korsvalideringen på rena träningspunkter (`a2.py varianter_qcs`) har en summakvot per kvart och per timme som inte är lägre än A2T:s med mer än 0,0005 och ett mål som är högst 0,05 % över A2T:s.
3. Bland de tillåtna väljs den som **hittar flest skadliga syntetiska fel**; inom 1 procentenhet väljs den som kastar färst riktiga stationsdygn, och sedan den med skydd över 400 m.
4. Den valda körs genom domaren på de tre träningsdagar som har A1:s fält sparat (`a2.py kor_traning`). Om FSS 0,5 eller 1 per kvart eller timme blir lägre än A2T:s med mer än 0,001 där, tas nästa variant i ordningen.
5. Bara den frysta varianten körs på valideringen, en gång.
