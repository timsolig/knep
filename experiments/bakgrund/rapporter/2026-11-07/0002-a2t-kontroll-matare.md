# Uppgift 0002: kontrollen av regnmätarna i indata till A2T (A2TK)

(Utkast; skrivet innan varianterna på träningen var lästa och innan valideringen kördes.)

## Urvalsregeln (skriven innan varianterna lästes)

Varianterna är kontrollen med T (2, 2,5, 3, 4), R (25, 50 km) och skyddet över 400 m av eller på, för kvarten och timmen var för sig, ovanpå A2T, med samma korsvalidering som `a2.py trana` (grupper om 100 km, buffert 25 km). Varje variant körs på rena träningspunkter och med syntetiska fel i 1 % av mätarperioderna i indata.

För varje upplösning för sig:

1. **Tillåten** är en variant som på de rena träningsdata (a) inte höjer falskt vid torr mätare över 400 m eller på lovartsidan mot A2T med mer än 0,0002, (b) har ett mål som är högst 0,5 % över A2T:s och (c) kastar högst 2 % av indata totalt, över 400 m och på lovartsidan.
2. Bland de tillåtna väljs den med **lägst mål med de syntetiska felen**.
3. Kontrollen tas med för upplösningen bara om den valda varianten har lägre mål med de syntetiska felen än A2T med samma fel. Annars får upplösningen ingen kontroll.
4. Får både kvarten och timmen kontroll, är A2TK kombinationen (timmens kontroll gäller då också timmätarna i kvartens kvot). Kombinationen körs på träningen och redovisas, men ändrar inte valet.

En enda variant frysts som A2TK i `FRYSTA` och committas innan valideringen körs.
