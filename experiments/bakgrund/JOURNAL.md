# Journalen

Vad bakgrunden har kört, nyast först. Loopen skriver en post efter varje uppgift: när, vad, varför planeraren valde den, resultatet i en mening, statusen och en länk till rapporten. Planeraren bedömer utfallet i `IDEER.md` och prioriterar om i `MAL.md`.

## Uppgifter

<!-- nya poster här -->

### 0026 · 2026-11-13 22:04 · bias-v1-ton-summa · misslyckad
- Varför: Uppgift 0025 visade att bias-v1 fälls för att nivåfaktorn lyfter kvartar och timmar strax under regngränsen över den, och att tona K efter rutans bakåtblickande summa i stället för bildens intensitet angriper just den mekanismen.
- Resultat: ingen rapport skrevs (loggen på Pi:n: ~/.bakgrund/logg/0026-bias-v1-ton-summa.txt)
- Rapport: ingen, 0 min

### 0025 · 2026-11-12 00:05 · bias-v1-varianter · klar
- Varför: A0B (bias-v1) gav den största förbättringen av mängden i A0 som domaren har visat men fälldes av falska ekon och FSS 5, och båda felen pekar på bestämda delar av korrektionen (nivån lyfter svagt eko, svansen trycker ned toppen) som går att välja om på träningsdagarna.
- Resultat: Ingen av fyra varianter klarar domaren på de 28 träningsdagarna: alla förbättrar kvot våt per kvart (+0,078 till +0,137 mot A0) men falskt vid torr mätare blir sämre med intervallet helt på fel sida i alla (bäst A0B_k2: 0,024 mot 0,024, skillnad -0,000 (-0,001 till -0,000)), så ingen frystes och valideringen kördes inte.
- Rapport: [rapporter/2026-11-11/0025-bias-v1-varianter.md](rapporter/2026-11-11/0025-bias-v1-varianter.md), 88 min

### 0024 · 2026-11-11 22:34 · bias-v1-domare · klar
- Varför: Kartan bias-v1 är tränad och korsvaliderad utan valideringens dygn (uppgift 0023) och rättar volymbristen på 12 % vid mätarna, så nästa steg är att analysens domare avgör en gång på valideringen om A0 med kartan är bättre än A0 utan att falska ekon och terrängen blir sämre.
- Resultat: A0B fälls av domarens regel på alla 16 valideringsdygn: kvot våt i kvartar 0,793 mot 0,704 (+0,119, intervall +0,054 till +0,178) och FSS 0,5 och CSI 0,5 och 1 per timme blir bättre, men falska ekon blir sämre (kvart 0,031 mot 0,026, intervall helt på fel sida) och FSS 5 per timme faller (0,182 mot 0,302), så ingen säkerställd förbättring.
- Rapport: [rapporter/2026-11-11/0024-bias-v1-domare.md](rapporter/2026-11-11/0024-bias-v1-domare.md), 19 min

### 0023 · 2026-11-11 22:13 · bias-v1-trana-cv · klar
- Varför: Taken för kedjans delar är körda och ger bara tusendelar, medan underlaget för volymkorrektionen är komplett sedan 2026-11-10 och radarns egen kvot mot mätarna (0,941) är det största kända felet vid +1 h.
- Resultat: Kartan närmar volymen 1 (stationsvis korsvalidering 1,027 mot 0,883 utan karta, per år 0,99 till 1,06 mot 0,88 till 0,89) och fler stationer hamnar inom 20 % (0,45 mot 0,33), men radarns övre kvantiler (q99, q99,5) blir sämre (1,20 och 1,18 mot 1,03 och 1,08 av mätarnas) och per år är andelen inom 20 % sämre 2023 och 2025; värd att döma i analysens domare, med förbehåll.
- Rapport: [rapporter/2026-11-11/0023-bias-v1-trana-cv.md](rapporter/2026-11-11/0023-bias-v1-trana-cv.md), 10 min

### 0022 · 2026-11-11 02:36 · tak-rorelse-tid · klar
- Varför: Rumslig utjämning är vilande efter uppgift 0019 till 0021, och det största kvarvarande taket (lägesfel på 32 till 128 km, uppgift 0018) kan vara rörelse som ändras med ledtiden, vilket 0017:s tak med ett enda fält ur 5 h inte kunde skilja från en grov skattning.
- Resultat: Rörelse som ändras med ledtiden tar cirka 9 % av lägestaket vid 2 h (TakRorelseTid CSI 1 mm +0,007 [+0,002, +0,011] mot +0,078 för tillväxt 32 minus 128 km; TakRorelse1h +0,005 [+0,001, +0,010]); rörelsespåret läggs vilande.
- Rapport: [rapporter/2026-11-11/0022-tak-rorelse-tid.md](rapporter/2026-11-11/0022-tak-rorelse-tid.md), 35 min

### 0021 · 2026-11-11 01:58 · utjamning-matchning · klar
- Varför: Utjämningen efter osäkerhet är den enda kandidaten utan facit som ger csi1 cirka +0,02 och säkert lägre hopp, och den fälls av blockmax_q90 och q99,9, som är fördelningsmått som en fördelningsmatchning efter utjämningen ska återställa per konstruktion, vilket inte är prövat.
- Resultat: Matchning av den utjämnade prognosen mot kedjans fördelning kostar ingen extra tid och bevarar q99 och q99,9, men den frysta `M_hel_gol` ger på `traning` csi1 +0,016 till +0,008 och hopp −0,05 till −0,07 mot en säker försämring av blockmax_q50 (+0,02 till +0,04), fss1_30 och formen, så domaren säger inte bättre och valideringen kördes inte.
- Rapport: [rapporter/2026-11-11/0021-utjamning-matchning.md](rapporter/2026-11-11/0021-utjamning-matchning.md), 106 min

### 0020 · 2026-11-11 00:09 · utjamning-snabb-blockmax · delvis
- Varför: Utjämningen efter osäkerhet (uppgift 0019) är den enda kandidaten utan facit som både ger csi1 cirka +0,02 vid 1 till 5 h och gör hoppet säkert bättre, och den fälls bara av blockmaxet och tiden, som båda ser ut att gå att laga.
- Resultat: Den snabba utjämningen kostar cirka 5 till 6 s extra per utgåva på 2 km (mot cirka 19 s i 0019, målet 5 s nästan nått), men inget av de tre toppskydden (a, b, c) bevarar blockmax_q90 (+0,08 till +0,38 sämre i `snabb`); det frysta S_ab_b ger csi1 +0,031 till +0,020 och hopp −0,11 till −0,26 på `traning` men blockmax_q90 +0,09 till +0,13 och q99,9 säkert sämre, så den är inte redo för validering.
- Rapport: [rapporter/2026-11-10/0020-utjamning-snabb-blockmax.md](rapporter/2026-11-10/0020-utjamning-snabb-blockmax.md), 123 min

### 0019 · 2026-11-10 03:28 · utjamning-osakerhet · delvis
- Varför: Uppgift 0018 visade att två tredjedelar av kedjans största tak (tillväxt i block om 32 km) egentligen är lägesfel i skalan 32 till 128 km, och utjämning där kedjans läge är osäkert är den kandidat med störst återstående tak (CSI 1 mm +0,03 till +0,04 vid 1 till 3 h i efterhand) som går att få utan facit.
- Resultat: På 12 träningsdagar (2 km) ger den frysta utjämningen csi1 +0,018 till +0,025 och csi5 +0,008 till +0,013 vid 1 till 5 h och säkert lägre hopp (−0,07 till −0,17), men blockmax_q90 blir säkert sämre (+0,057 till +0,089), fss1_30 sämre vid 1 h och kostnaden är 36 s extra per utgåva på 2 km (mot 5 s-målet), så den klarar varken spärren eller tiden.
- Rapport: [rapporter/2026-11-10/0019-utjamning-osakerhet.md](rapporter/2026-11-10/0019-utjamning-osakerhet.md), 131 min

### 0018 · 2026-11-10 01:15 · tillvaxt-historik · klar
- Varför: Taket i uppgift 0017 visar att tillväxt och avtagande i stor skala är den enda del av kedjan med en stor möjlig vinst (CSI 1 mm +0,035 till +0,120), så nästa steg är att skilja tillväxt från läge i taket och pröva en kandidat utan facit.
- Resultat: Trenden ur A0:s blockmedel (64 km, dämpning 1 h) ger bara CSI 1 mm +0,008 [+0,006, +0,010] vid 1 h och FSS 1 mm +0,011 vid 2 h mot `kedja_om` (12 träningsdagar, 2 km; liknande på `snabb`), vilket är cirka en sjättedel av taket vid 64 km (+0,059), taket faller från +0,12 (32 km) via +0,076 (64 km) till +0,042 (128 km) CSI 1 mm vid 2 h, och hopp, csi5 och fss5_10 vid 15 till 60 min blir säkert sämre.
- Rapport: [rapporter/2026-11-09/0018-tillvaxt-historik.md](rapporter/2026-11-09/0018-tillvaxt-historik.md), 130 min

### 0017 · 2026-11-09 23:02 · tak-korning · klar
- Varför: Taket för kedjans delar (användarens beslut 9) är skrivet i tak.py men aldrig kört, och nu när Bash fungerar igen är det det som avgör vilka ändringar av prognosen som är värda att pröva med domaren.
- Resultat: Tillväxt och avtagande i block om 32 km har klart störst tak (CSI 1 mm +0,035 till +0,120 mot kedja_om, 11 till 18 procent av luckan till 1, intervallen helt över noll), utjämning vald i efterhand tar 2 till 6 procent (+0,010 till +0,044 vid 30 min till 3 h) men fast schema nästan inget, och rörelse (ett fält) och volym har inget tak (alla intervall innehåller noll).
- Rapport: [rapporter/2026-11-09/0017-tak-korning.md](rapporter/2026-11-09/0017-tak-korning.md), 56 min

### 0016 · 2026-11-08 23:42 · tak-skrivbord · klar
- Varför: Taket för kedjans delar (användarens beslut 9) har misslyckats två gånger för att Bash nekades, så den här delen görs med bara läsning och skrivning av filer och lämnar en färdig modul och körplan till nästa session som har skal.
- Resultat: `tak.py` med fem fuskvarianter (rörelse, mängd, tillväxt, fast och bästa utjämning) och en körplan är skrivna och genomlästa mot domaren men inte körda; inga siffror finns, och FSS 1 mm vid 10 och 40 km finns inte i domaren (närmaste är `fss1_30`, `fss5_10`).
- Rapport: [rapporter/2026-11-08/0016-tak-skrivbord.md](rapporter/2026-11-08/0016-tak-skrivbord.md), 3 min

### 0015 · 2026-11-08 22:37 · tak-kedjans-delar · misslyckad
- Varför: Användarens beslut 9 vill veta var de stora vinsterna i kedjan finns innan fler finjusteringar, och förra försöket (0014) avbröts efter 0 min utan att något prövades.
- Resultat: uppgiften kunde inte köras eftersom Bash nekades; ingen fuskvariant är byggd eller körd.
- Rapport: [rapporter/2026-11-08/0015-tak-kedjans-delar.md](rapporter/2026-11-08/0015-tak-kedjans-delar.md), 0 min

### 0014 · 2026-11-08 22:05 · tak-kedjans-delar · misslyckad
- Varför: Användarens beslut 9 vill veta var de stora vinsterna finns innan fler finjusteringar, och mål 2 har inget kvar som är redo att bedömas efter uppgift 0013.
- Resultat: ingen rapport skrevs (loggen på Pi:n: ~/.bakgrund/logg/0014-tak-kedjans-delar.txt)
- Rapport: ingen, 0 min

### 0013 · 2026-11-08 10:10 · kedja-utan-matchning-validering · klar
- Varför: Kedjan utan fördelningsmatchning var något bättre än kedjan på träningen och måste bedömas på valideringen före testdelen, medan fliken Verifiering väntar på en webbläsare och testdelen på disken.
- Resultat: kedjan utan matchning är redan dömd på valideringen (`validering_gles`, 16 dygn, 125 utgåvor, körd 2026-11-04 i natt 1) och domen är **inte bättre**: CSI och FSS blir 0,001 till 0,006 bättre, men blockmaxets 90-percentil är säkert sämre vid alla ledtider (+0,058 till +0,065 i |log kvot|, intervallen +0,033 till +0,094), formen 4 till 8 km säkert sämre (+0,042 till +0,053) och SEDI 10 mm/h säkert sämre vid 15 till 60 min; jag körde inte valideringen en gång till, utan räknade om tabellen ur de sparade summorna och ett dygn bit för bit lika med dagens kod. Inflödet vid randen var också redan valt och fällt i natt 1 (`Inflode25`); på träningen tar det tillbaka hälften av förlusten nära randen (kvoten mot radarn vid +60 min 0,897 mot kedjans 0,778).
- Rapport: [rapporter/2026-11-08/0013-kedja-utan-matchning-validering.md](rapporter/2026-11-08/0013-kedja-utan-matchning-validering.md), 73 min

### 0012 · 2026-11-08 08:54 · verifiering-flik-del1 · delvis
- Varför: Användarens beslut 8 är beställt och behöver ingen ny data, medan testdelen (beslut e) väntar eftersom /data har under 3 GB ledigt.
- Resultat: fliken Verifiering är omskriven med alla mått på en gång (ett litet diagram per mått, ledtiden +1 till +5 h som axel, en linje per modell, intervallet som band) i fyra grupper, med egen period från och till som räknas i sidan ur dygnens summor; `verify.py` skriver nu det som saknades för det (Tim-KNEP på de andras urval, timmarna och underlaget per dygn) utan att något befintligt tal ändras, och måtten ur dygnens summor stämmer med `verify.py` inom 0,00011 på provdatan; sidan är **inte** ritad eller körd, eftersom varken Playwright, en webbläsare eller node finns på Pi:n.
- Rapport: [rapporter/2026-11-08/0012-verifiering-flik-del1.md](rapporter/2026-11-08/0012-verifiering-flik-del1.md), 17 min

### 0011 · 2026-11-08 06:34 · f4-alla-traningsdagar · klar
- Varför: Användarens beslut d (F4 på alla 28 träningsdagar och klotterkartan som modellfil) är nästa beslut i ordningen nu när glappet vid Riksgränsen är avgjort, och det måste vara klart innan testdelen (beslut e) körs.
- Resultat: Klotterkartan byggs om bit för bit lika (sha256 535dd606…, 621 rutor, alla 28 träningsdagar) och ligger som modellfil i `/data/analys/filter/klotter-v1/` med släppet `klotter-v1` beskrivet, A0 och F4 har dagfiler med kvot våt på alla 28 träningsdagar, och där minskar F4 kartmåttet från 51,8 till 42,0 rutor per dag (+9,79, +7,82 till +11,93) och höjer FSS, men domaren fäller F4 mot A0 på träningen av kvot våt per timme över 400 m (0,48880 mot 0,48886, −0,000112, −0,000261 till −0,000012; 0,1 mm bort vid våta fjällmätare på fyra dagar), vilket är en varning inför testdelen.
- Rapport: [rapporter/2026-11-08/0011-f4-alla-traningsdagar.md](rapporter/2026-11-08/0011-f4-alla-traningsdagar.md), 133 min

### 0010 · 2026-11-08 04:18 · glappet-riksgransen · klar
- Varför: Användarens beslut 6 säger att glappet nordväst om Riksgränsen ska rättas direkt efter domarens kvot våt (klar i uppgift 0009) och före F4:s omträning och testdelen, så att testdelen körs på den rättade A0.
- Resultat: Glappet är verkligt och systematiskt (SMHI 0 där OPERA har minst 0,1 mm/h i 59 % av rutbilderna där svensk stråle är över 2 km och 84 % över 4 km på 9 träningsdagar, mot cirka 25 % närmare radarerna), och regeln `composite.layer_far` med H = 2 km, vald på träningen, fyller bågen i fallet (rutan vid Narvik 0,000 till 0,39 till 0,65 mm/h) och höjer kvot våt per timme vid zonens mätare på valideringen från 0,729 till 0,802 (+0,095, +0,055 till +0,111), men domaren godkänner den inte mot A0 eftersom falska ekon blir fler (falskt vid torr mätare per timme 0,015 mot 0,011, −0,004, −0,005 till −0,003; rutor med eko i torra timmar 66,3 mot 60,8 per dag), och ingen av fem varianter (H 2, 3, 4 och tröskel 0,3 mm/h) godkänns ens på träningen; valet `--opera-fjarr` finns avstängt.
- Rapport: [rapporter/2026-11-08/0010-glappet-riksgransen.md](rapporter/2026-11-08/0010-glappet-riksgransen.md), 123 min

### 0009 · 2026-11-08 00:02 · domare-vat-kvot · klar
- Varför: Användarens beslut c (analysens domare med kvoten för perioder då mätaren har regn, och baslinjerna omkörda) är nästa beslut i ordningen nu när a och b är klara, och den behövs innan F4 tränas om och testdelen körs.
- Resultat: Domaren har nu `kvot våt` (Σanalys/Σmätare där mätaren har regn) i stället för summakvoten i domens mängdgrupp, med den gamla regeln kvar bredvid. På hela valideringen (16 dagar) ändras ingen av de fyra domarna: A2T slår fortfarande A0 och A1 utan sämre mått (kvot våt per timme över 400 m 0,614 mot A0 0,467 och A1 0,455), F4 godkänns fortfarande mot A0 (bara FSS bättre, kvoterna exakt som A0), och A1 fälls fortfarande mot A0, nu av `kvot våt` per timme på lovartsidan (0,598 mot 0,609, −0,020, −0,038 till −0,002) i stället för av summakvoten per kvart och timme där.
- Rapport: [rapporter/2026-11-07/0009-domare-vat-kvot.md](rapporter/2026-11-07/0009-domare-vat-kvot.md), 175 min

### 0008 · 2026-11-07 21:04 · a2t-facit-i-verify · klar
- Varför: Användarens beslut b (A2T som andra facit i verifieringen) är nästa beslut i ordningen, beslut a är klart och `--a2` är på i drift, och rapporten 0005 visar att radarn som enda facit blåser upp Tim-KNEP:s försprång mot persistensen vid +1 h.
- Resultat: A2T:s timsumma sparas nu som tal i `cache/verif/a2t/` (senaste versionen skriver över), `score()` och `summary()` ger gruppen `a2t` i `Day` och `verif.json` med exakt samma radar- och mätartal som förut (prövat mot en körning utan A2T-filer), och fliken Verifiering visar Mot A2T bara när underlaget finns; i en provkörning på träningsdagen 2020-07-24 (3 utgåvor) är Tim-KNEP:s försprång mot persistensen vid +1 h för CSI 1 mm +0,305 mot radarn, +0,219 mot A2T och −0,006 mot mätarna.
- Rapport: [rapporter/2026-11-07/0008-a2t-facit-i-verify.md](rapporter/2026-11-07/0008-a2t-facit-i-verify.md), 21 min

### 0007 · 2026-11-07 17:53 · a2-texter-och-stationskontroll · klar
- Varför: Användaren har beslutat att A2T ska visas på sidan och bli facit i verifieringen, och sidans texter plus kontrollen av trasiga mätare per station och dygn är det första beslutet och det som A2T som facit kräver först.
- Resultat: Sidans två texter för A2 och `INTRO` 5 är klara och syns bara när `levels.a2` har bilder (del 1, committad); kontrollen per station och dygn (A2TS: R 100 km, minst 8 kvartar eller 3 timmar våt mot torr radar och torra grannar, eller noll mot vått, aldrig "våt" över 400 m) hittar 65 % av de skadliga syntetiska dygnsfelen och kastar 9 av 4 527 riktiga stationsdygn på träningen och 6 av 2 515 på valideringen, men den godkänns inte mot A2T eftersom FSS 1 per kvart blir sämre med intervallet helt på fel sida (0,392 mot 0,392, −0,00013, −0,00021 till −0,00003), så valet lades inte i `src/`.
- Rapport: [rapporter/2026-11-07/0007-a2-texter-och-stationskontroll.md](rapporter/2026-11-07/0007-a2-texter-och-stationskontroll.md), 141 min

### 0006 · 2026-11-07 15:30 · kedjans-underskott-1h · klar
- Varför: Uppgift 0005 visade att kedjan har för lite regn i mätarnas rutor vid +1 h och att försprånget mot persistensen mot mätarna är minst där, och att köra kedjan utan platskarta och utan fördelningsmatchning på de redan sparade analyserna pekar ut vilken del av kedjan som ska rättas.
- Resultat: varken platskartan eller fördelningsmatchningen förklarar underskottet; utan platskartan blir kedjans kvot mot mätarna vid +1 h 0,920 och utan matchningen 0,919 mot kedjans 0,914 (skillnad +0,006, 95 % −0,015 till +0,043, och +0,005, −0,002 till +0,011), alltså under en tiondel av avståndet till 0,98; det mesta av "underskottet" är att radarn själv har kvoten 0,941 mot mätarna just de målen (kedjan är 0,971 av radarn vid mätarna), och resten av förlusten under första timmen sitter vid täckningens rand (kvoten mot radarn 0,778 vid +60 min inom 50 km från randen, 0,980 inne i området).
- Rapport: [rapporter/2026-11-07/0006-kedjans-underskott-1h.md](rapporter/2026-11-07/0006-kedjans-underskott-1h.md), 108 min

### 0005 · 2026-11-07 13:39 · prognos-mot-a2t-facit · klar
- Varför: A2T finns nu i src och i cykeln, och att räkna kedjan och persistensen mot A2T i stället för radarn svarar både på varför Tim-KNEP är svag mot persistensen vid +1 h (mål 4) och på om A2T duger som facit i verifieringen (mål 1).
- Resultat: på 15 träningsdagar (90 utgåvor) slår kedjan persistensen vid alla ledtider mot alla tre facit, men försprånget vid +1 h krymper när radarn byts mot A2T (CSI 1 mm +0,257 till +0,196, FSS 1 mm/10 km +0,253 till +0,204, MAE −0,084 till −0,066 mm) och mest mot mätarna (CSI 1 mm +0,105, 95 % +0,066 till +0,136, mindre än vid +2 h med +0,142); klottermasken (F4) ändrar skillnaden med högst 0,01, så klottret ger persistensen nästan ingenting på de här dagarna.
- Rapport: [rapporter/2026-11-07/0005-prognos-mot-a2t-facit.md](rapporter/2026-11-07/0005-prognos-mot-a2t-facit.md), 143 min

### 0004 · 2026-11-07 11:14 · a2t-i-cykeln · klar
- Varför: A2T slår A0 och A1 och finns nu i src, men ingen cykel räknar den; ett avstängt val --a2 i cli.py gör att visa A2 på sidan blir ett beslut om en flagga, utan att valideringen behöver ses igen.
- Resultat: valet `--a2` (av som standard) räknar nu A2T i cykeln ur A1:s sparade timsummor och mätarna i `gauges.json`, fyller `a2/` och `levels.a2` med kvart och timme bakåt, ger samma fält som `a2.A2T.timme` direkt (`np.array_equal` i testerna, PNG byte för byte i hela cykeln), och kostade i en provkörning på träningsdagen 2020-07-24 2,9 till 5,0 s extra i de cykler som räknar en timme och cirka 11 MB på disk.
- Rapport: [rapporter/2026-11-07/0004-a2t-i-cykeln.md](rapporter/2026-11-07/0004-a2t-i-cykeln.md), 22 min

### 0003 · 2026-11-07 10:50 · a2t-till-src · klar
- Varför: A2T är den enda analysen som slår både A0 och A1 enligt domaren, och att flytta den till src som ett avstängt val är nästa steg mot facit och sidan utan att valideringen behöver ses igen.
- Resultat: A2T finns nu som en liten, avstängd modul i `src/knep/analys/a2.py` som ger bit för bit samma fält som experimentet (`np.array_equal`, största skillnad 0 mm per kvart och per timme) på 8 syntetiska fall och på alla 24 timmar och 96 kvartar för tre träningsdagar, domaren ger exakt samma tal på 2020-07-24, och en timme med sina fyra kvartar tar 1,1 till 1,3 s på hela rutnätet på Pi:n med cirka 57 MB extra minne.
- Rapport: [rapporter/2026-11-07/0003-a2t-till-src.md](rapporter/2026-11-07/0003-a2t-till-src.md), 33 min

### 0002 · 2026-11-07 10:15 · a2t-kontroll-matare · klar
- Varför: A2T är den första analysen som slår både A0 och A1, och kontrollen av mätarna är det som står kvar innan den kan bli facit i verifieringen och föreslås som avstängt val i src/.
- Resultat: Kontrollen jämför varje mätare med grannarna inom R km och med A2T:s bakgrund och kastar den bara när båda säger emot. Med valda T = 3 och R = 50 km per kvart och T = 2,5 och R = 50 km per timme kastas 0,09 % av kvartarna och 0,11 % av timmarna på träningen, och ingen över 400 m. A2TK slår fortfarande A1 och A0 enligt domaren, men den kan inte ersätta A2T. Mot A2T är den bättre i MAE men sämre med intervallet helt på fel sida i bland annat summakvoten (kvart 0,846 mot 0,851, −0,006, −0,009 till −0,002) och FSS 1 per kvart (0,389 mot 0,392, −0,003, −0,006 till −0,001), eftersom 9 av 10 kastade perioder är för våta mätare, alltså verkliga skurtoppar.
- Rapport: [rapporter/2026-11-07/0002-a2t-kontroll-matare.md](rapporter/2026-11-07/0002-a2t-kontroll-matare.md), 116 min

### 0001 · 2026-11-07 08:17 · a2-falska-ekon · klar
- Varför: A2 slår redan A0 i 15 mått och A1 i 14 och fälls mot A1 bara av falska ekon per kvart i terrängen, så att rätta det är den kortaste vägen till en analys som slår båda baslinjerna och till ett facit för verifieringen.
- Resultat: A2T (ingen uppskalning och tak över svagt eko under 0,125 mm per kvart) slår A1 enligt domaren på valideringen utan att något mått blir sämre, och tar bort det som fällde A2: falskt vid torr mätare per kvart över 400 m går från A2:s 0,016 till 0,0118 mot A1:s 0,0133 (+0,0015, +0,0005 till +0,0025) och på lovartsidan till 0,0144 mot 0,0155 (+0,0011, +0,0001 till +0,0023); priset är en lägre summakvot i terrängen per kvart än A2 (0,575 mot 0,632 över 400 m, fortfarande långt över A1:s 0,475).
- Rapport: [rapporter/2026-11-07/0001-a2-falska-ekon.md](rapporter/2026-11-07/0001-a2-falska-ekon.md), 128 min

## Före loopen

Bakgrundskörningarna med en fast kö (`experiments/natt/`).

| Datum | Område | Uppgifter | Utfallet |
|---|---|---|---|
| natten mot 2026-11-07 | analysen och prognosen | lovart, inflode, sammanfattning2 | se [rapporterna](../natt/rapporter/2026-11-07/) |
| 2026-11-06 | analysen | artefakter, domare, a2, filter, sammanfattning | Analysens domare finns. A1 är bättre än A0 per kvart och timme men fälls av underskottet på lovartsidan. [Rapporterna](../natt/rapporter/2026-11-06/) |
| 2026-11-05 | verifieringen och prognosen | verif-persistens, somlos-5h | `verify.py` räknar rätt; facit (radarn) är svagt i november. Somlos var en MEPS-blandning och är nerlagd. [Rapporterna](../natt/rapporter/2026-11-05/) |
| 2026-11-04 | prognosens konservering | domare, förlust, konservering, terräng, sammanfattning | Inget slog kedjan. `Inflode25` och `NarmastRamp3` är värda att bygga vidare på. [Sammanfattningen](../natt/rapporter/2026-11-04/6-sammanfattning.md) |
| 2026-11-03 | radarbortfall | inventering, bortfallsfall, domare, MEPS i hålet, inlärd blandning | Bortfallets domare och fallen finns. [Rapporterna](../natt/rapporter/2026-11-03/) |
