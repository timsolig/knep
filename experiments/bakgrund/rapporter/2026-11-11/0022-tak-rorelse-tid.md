# 0022 tak-rorelse-tid

Taket för rörelse som ändras med ledtiden, kört i `snabb` (6 dygn, 4 km, 48 utgåvor per system). Bara tak, inget system för drift, ingenting på valideringen eller testdelen. Ändrade filer: `experiments/projektion/tak_tid.py` (ny), `experiments/projektion/test_tak_tid.py` (ny, 3 test), `experiments/projektion/kor_shm.py` (`tak_TakRorelse` i `KEEP`). Inget i `src/`, inget skrevs till `/data` (`df /data` 1 633 MB ledigt före och efter, rörelsecachen orörd, 7 432 filer); summorna låg i `/dev/shm` och är nu tömda efter tabellen nedan.

## Vad som byggdes

- **TakRorelse1h**: kedjan med ett fält skattat ur facit-bilderna t till t + 1 h (Lucas-Kanade som `hindsight_motion`, 5 bilder var 15:e minut), som ersätter historikens fält i hela prognosen.
- **TakRorelseTid**: styckvis konstant rörelse per timme, fältet för timme k ur facit-bilderna t + (k−1) h till t + k h (`motion_window`). Valt sätt: kedjan körs som i drift (historikens fält, platskarta, matchning) och varje kvarts tre 5-minutersbilder flyttas sedan semi-lagrangesk med skillnaden mellan förskjutningen bakåt längs de styckvisa facitfälten och längs kedjans fält (`back_path`, `shift_forecast`; samma integrator för båda vägarna, 5-minutssteg, mittpunktsschema, ankomsttid först bakåt, skillnaden vid kvartens mittsteg). Prognosen hämtas i x + (dx_facit − dx_kedja) med bilinjär `cv2.remap`. Skälet: `Chain.run` tar bara ett fält, och det här behåller kedjans matchning och platskarta utan att skriva om den. Nackdelen är en extra bilinjär omsampling som jämnar ut fältet (se Form nedan), och att matchningen sker på kedjans plats, inte den flyttade. Med lika fält i alla timmar är skiftet exakt noll (test).
- Fallback om ett fönster saknar bilder (färre än 4 i följd): kedjans eget fält för den timmen.
- Test (`test_tak_tid.py`, syntetiskt): konstant rörelse ger prognosen oförändrad (max skillnad under 1e-4); en rörelse som byter riktning efter 1 h (0,5 px per steg höger, sedan vänster) ger ett eko som efter 12, 24 och 36 steg ligger vid +6, 0 och −6 px (inom en bildruta, skiftet räknas vid kvartens mittsteg); NaN stannar NaN.

Tid: en provkörning på 2023-07-12 tog 242 s för 8 utgåvor med 2 processer. Hela körningen (båda systemen, 6 dygn, 2 processer) tog cirka 25 min väggtid; TakRorelse1h 12 processorminuter (som kedjan, Lucas-Kanade på 5 bilder kostar nästan inget), TakRorelseTid 27 processorminuter, alltså cirka 19 s extra per utgåva på 4 km, mest `back_path` (20 vägar om upp till 60 steg, med 2 remap per steg) och omsamplingen. Minnet var cirka 500 MB per process (som i 0017, ej mätt på nytt).

## Tabeller

Skillnad mot `kedja_om` med 95 %-intervall (bootstrap över de 6 dygnen). För csi och fss är **+ bättre** (omvänt mot domarens egen utskrift, som orienterar negativt som bättre; jag har vänt tecknet för att stämma med 0017). För blockmax_q90 (|log kvot| mot radarn) och hopp är **negativt bättre**, som i domaren. `*` intervallet helt på bättre sidan. Absoluta värden för `kedja_om` (från 0017): csi1 0,734, 0,414, 0,271, 0,207, 0,146; csi5 0,580, 0,235, 0,128, 0,078, 0,048; fss1_30 0,979, 0,825, 0,654, 0,536, 0,401; fss5_10 0,886, 0,525, 0,321, 0,210, 0,133 (15 min, 1, 2, 3, 5 h).

**tak_TakRorelse** (ett fält ur facit 0 till 5 h, återkörd i samma tabell)

| mått | 15 min | 1 h | 2 h | 3 h | 5 h |
|---|---|---|---|---|---|
| csi1 | +0,001 [-0,001, +0,002] | +0,000 [-0,005, +0,005] | +0,004 [-0,001, +0,009] | +0,001 [-0,007, +0,009] | +0,003 [-0,005, +0,015] |
| csi5 | -0,003 [-0,009, +0,002] | +0,001 [-0,010, +0,010] | -0,003 [-0,019, +0,010] | -0,006 [-0,016, +0,004] | -0,001 [-0,015, +0,012] |
| fss1_30 | +0,000 [-0,000, +0,000] | -0,001 [-0,003, +0,001] | +0,005 [-0,003, +0,016] | +0,005 [-0,013, +0,025] | +0,016 [-0,003, +0,043] |
| fss5_10 | -0,002 [-0,006, +0,002] | +0,000 [-0,017, +0,015] | -0,005 [-0,043, +0,027] | -0,014 [-0,037, +0,008] | -0,001 [-0,034, +0,033] |
| blockmax_q90 | -0,002 [-0,047, +0,027] | -0,037 [-0,048, +0,030] | +0,005 [-0,016, +0,048] | +0,005 [-0,034, +0,054] | -0,002 [-0,068, +0,043] |
| hopp | +0,009 [-0,014, +0,025] | -0,000 [-0,024, +0,016] | -0,016 [-0,041, +0,001] | . | . |

**TakRorelse1h** (ett fält ur facit t till t + 1 h)

| mått | 15 min | 1 h | 2 h | 3 h | 5 h |
|---|---|---|---|---|---|
| csi1 | +0,001 [+0,000, +0,002]* | +0,006 [+0,003, +0,011]* | +0,005 [+0,001, +0,010]* | +0,002 [-0,003, +0,006] | +0,001 [-0,004, +0,006] |
| csi5 | +0,001 [-0,004, +0,006] | +0,001 [-0,006, +0,008] | -0,001 [-0,008, +0,006] | -0,002 [-0,004, +0,000] | -0,004 [-0,017, +0,004] |
| fss1_30 | +0,000 [-0,000, +0,000] | +0,005 [+0,002, +0,009]* | +0,008 [+0,001, +0,018]* | +0,006 [-0,003, +0,014] | +0,009 [-0,001, +0,019] |
| fss5_10 | +0,000 [-0,003, +0,005] | +0,002 [-0,010, +0,016] | +0,002 [-0,013, +0,022] | -0,004 [-0,011, +0,003] | -0,009 [-0,037, +0,008] |
| blockmax_q90 | -0,004 [-0,029, +0,025] | -0,034 [-0,037, +0,029] | -0,012 [-0,048, +0,031] | +0,005 [-0,023, +0,038] | -0,003 [-0,061, +0,037] |
| hopp | +0,004 [-0,003, +0,013] | +0,004 [-0,006, +0,016] | -0,004 [-0,021, +0,012] | . | . |

**TakRorelseTid** (ett fält per timme ur facit)

| mått | 15 min | 1 h | 2 h | 3 h | 5 h |
|---|---|---|---|---|---|
| csi1 | +0,002 [+0,001, +0,004]* | +0,010 [+0,006, +0,014]* | +0,007 [+0,002, +0,011]* | +0,003 [-0,005, +0,011] | -0,003 [-0,025, +0,013] |
| csi5 | +0,004 [+0,000, +0,008]* | +0,006 [-0,001, +0,014] | +0,003 [-0,005, +0,015] | -0,006 [-0,013, +0,001] | -0,009 [-0,032, +0,011] |
| fss1_30 | +0,000 [-0,001, +0,000] | +0,004 [+0,002, +0,008]* | +0,007 [+0,000, +0,014]* | +0,003 [-0,010, +0,020] | -0,003 [-0,045, +0,033] |
| fss5_10 | +0,000 [-0,003, +0,003] | +0,005 [-0,009, +0,020] | +0,005 [-0,015, +0,034] | -0,015 [-0,034, +0,000] | -0,023 [-0,079, +0,028] |
| blockmax_q90 | +0,046 [+0,013, +0,053] sämre | +0,067 [+0,039, +0,110] sämre | +0,065 [+0,032, +0,107] sämre | +0,077 [+0,038, +0,132] sämre | +0,114 [+0,034, +0,160] sämre |
| hopp | -0,002 [-0,024, +0,022] | -0,006 [-0,034, +0,027] | -0,006 [-0,034, +0,031] | . | . |

(Hopp finns bara för 15 min till 2 h i domaren.)

Form och blockmax för TakRorelseTid (utanför de begärda måtten men avgörande för tolkningen): form4_8 blir 0,46 till 0,81 sämre i |log kvot| (från −1,3 till −1,7…−2,1) och form8_16 0,25 till 0,50 sämre, alla med intervallet helt på fel sida; blockmax_q50 0,02 till 0,06 sämre. Det är den extra bilinjära omsamplingen som jämnar ut fältet, ett artefakt av sättet jag byggde TakRorelseTid på, inte av rörelsen. TakRorelse1h (enkelt byte av fält) har ingen sådan förlust (form4_8 +0,03 till +0,02, bara en cell `!`).

## Svar

**Hur stor del av lägestaket tar rörelse som ändras med ledtiden?** Lägestaket vid 2 h, tillväxt 32 km minus 128 km i CSI 1 mm, är +0,120 − 0,042 = +0,078 (0017, 0018). TakRorelseTid ger +0,007 [+0,002, +0,011] i samma mått, alltså cirka **9 %** av lägestaket (intervallets övre ände 14 %). Vid 3 h är den +0,003 (ej skild från noll) och vid 5 h 0 mot tillväxttakets +0,097. Rörelse som vrids eller accelererar mellan timmar är alltså inte förklaringen till lägesfelet i skalan 32 till 128 km, med den här metoden. FSS 5 mm 10 km, som tillväxten lyfter med +0,217 vid 2 h, rör sig inte alls (+0,005, intervall över noll).

**Är TakRorelse1h bättre än kedjan?** Ja men litet: CSI 1 mm +0,006 vid 1 h och +0,005 vid 2 h (båda med intervallet helt över noll), FSS 1 mm 30 km +0,005 och +0,008. Ingen effekt vid 3 till 5 h och inget för 5 mm. Historikens fält är alltså något sämre än ett fält ur nästa timme under första två timmarna, men skillnaden är en bråkdel av en CSI-enhet (0,005 till 0,008); historikens rörelse är inte dålig i den meningen. Fönstrets längd spelar liten roll: ett fält ur 0 till 5 h (TakRorelse, ingen säkerställd skillnad) är inte bättre än ett ur 0 till 1 h.

**Varning om TakRorelseTid:** att den inte är bättre än TakRorelse1h (1 h: +0,010 mot +0,006, 2 h: +0,007 mot +0,005) trots att den ser facit för varje timme tyder också på att rörelsen inte är flaskhalsen, men omsamplingens utjämning gör att jämförelsen i formmåtten inte går att tolka. En variant som flyttar före matchningen (och alltså behåller formen) skulle kräva ändringar i `Chain.run` (`src/`) och har inte provats.

## Rekommendation

Taket för `TakRorelseTid` är cirka 9 % av lägestaket vid 2 h och 0 vid 3 h, långt under halva. **Rörelsespåret läggs vilande**: ingen kandidat utan facit (vridande eller accelererande rörelse ur historikens fält, rörelse i flera skalor) är motiverad, eftersom inte ens facit-rörelsen per timme ger mer än +0,01 CSI. Det mesta av lägestaket (tillväxt 32 km minus 128 km, +0,078) är alltså inte rörelse som ändras med ledtiden utan något annat i skalan 32 till 128 km: sannolikt ny- och bortbildning i mellanskalan som tillväxtmåttet kan rätta med platsbunden kvot trots att 0018 visade att den största delen försvinner med större block, eller lägesfel som inte är en ren förskjutning (deformation, rotation, hastighet som varierar i rummet inom ett fönster om 15 minuter). Nästa steg enligt uppgiften: utjämning bara i tiden mellan utgåvor (`IDEER.md`). Ett möjligt komplement för den som vill stänga frågan helt: ett tak med rörelse per kvart och per rutnätscell (ett eget fält per 15 minuter ur facit) för att utesluta lokala förändringar, till ungefär samma kostnad som TakRorelseTid.

Kort: Rörelse som ändras med ledtiden tar cirka 9 % av lägestaket vid 2 h (TakRorelseTid CSI 1 mm +0,007 [+0,002, +0,011] mot +0,078 för tillväxt 32 minus 128 km; TakRorelse1h +0,005 [+0,001, +0,010]); rörelsespåret läggs vilande.
Säkerställd förbättring: nej
Status: klar
