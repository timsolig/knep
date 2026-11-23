# Spåren

Ett spår är en idé om var vinsten finns (till exempel "utjämning efter osäkerhet" eller "ringen vid Røst"). Varje experiment i kön hör till ett spår (`"spar"` i experimentfilen). Veckans genomgång (`vecka.md`) håller den här filen aktuell; användaren äger reglerna.

## Reglerna för att ompröva vägar

Syftet är att kön inte ska justera små saker inom en idé i veckor och sluta med en marginell förbättring.

1. **Varje spår har en budget**: högst 12 experiment eller 3 veckor, det som kommer först. När budgeten är slut stängs spåret, eller så skrivs ett nytt skäl här (inte "en variant till") och en ny budget, högst en gång per spår.
2. **Mättat spår stängs**: sammanfattningen markerar ett spår som mättat när det har minst sex experiment och de tre senaste inte har höjt den största säkra vinsten med minst 20 % (och minst 0,005). Ett mättat spår får inga nya experiment, bara ett slutligt på valideringen om det har en frusen kandidat.
3. **Minst en tredjedel av köns tid går till andra spår än det bästa**, och varje vecka läggs minst ett experiment i ett spår som är nytt eller vilande.
4. **Var fjärde vecka görs en omprövning från grunden**: läs taken (uppgifterna 0017, 0018 och 0022 och senare tak), räkna hur mycket av varje tak som spåren har tagit hem, och lägg nästa veckas kö efter det största tak som är kvar, inte efter det spår som senast gav något. Skriv omprövningen under **Omprövningar** nedan.
5. **En förbättring räknas i storlek, inte bara i dom**: "bättre" enligt domaren med en säker vinst under 0,005 i huvudmåttet är en finjustering. Två finjusteringar i rad i samma spår räknas som mättat.

## Aktiva

Taken (`"tak": true`) är diagnoser som ser facit; deras säkra vinst är svaret, och de slås aldrig på.

| spår | idé | tak (källa) | startad | budget kvar | läge |
|---|---|---|---|---|---|
| sammanslagning-lard (nytt, användarens beställning 2026-11-23) | gradient boosting ur radarn, omgivningen, avståndet, höjden och årstiden, ensam eller som bakgrund till OI | A2T:s OI förutsätter normalfördelade fel och en fast korrelation; nederbörden har nollor, skevhet, intensitetsberoende fel och vädrets korrelation | 2026-11-23 | 3 till 4 varianter och valideringar på villkor, 3 veckor | i kön (0410 till 0441) |
| sammanslagning-cm (nytt, användarens beställning 2026-11-23) | conditional merging: radarns form, mätarnas nivå, L 20, 40, 80 km och som kvot | A2T:s OI förutsätter normalfördelade fel och en fast korrelation; nederbörden har nollor, skevhet, intensitetsberoende fel och vädrets korrelation | 2026-11-23 | 3 till 4 varianter och valideringar på villkor, 3 veckor | i kön (0410 till 0441) |
| sammanslagning-korrelation (nytt, användarens beställning 2026-11-23) | OI med korrelationslängden ur radarfältet och bakgrundsfel som växer med intensiteten | A2T:s OI förutsätter normalfördelade fel och en fast korrelation; nederbörden har nollor, skevhet, intensitetsberoende fel och vädrets korrelation | 2026-11-23 | 3 till 4 varianter och valideringar på villkor, 3 veckor | i kön (0410 till 0441) |
| sammanslagning-tvasteg (nytt, användarens beställning 2026-11-23) | först om det regnar (indikator), sedan hur mycket | A2T:s OI förutsätter normalfördelade fel och en fast korrelation; nederbörden har nollor, skevhet, intensitetsberoende fel och vädrets korrelation | 2026-11-23 | 3 till 4 varianter och valideringar på villkor, 3 veckor | i kön (0410 till 0441) |
| opera-analys (nytt) | OPERA i glappet vid Riksgränsen med ringmasken mot OPERA:s eget klotter och med nivån matchad mot SMHI; A0O fälldes bara av falska ekon | glappet: SMHI 0 där OPERA har regn i 59 % av rutbilderna med stråle över 2 km (0010) | 2026-11-23 | 6 experiment (3 och 3 valideringar på villkor), 2 veckor | i kön (0340 till 0352) |
| ensemble-rorelse (nytt, en annan metod) | kedjan med flera rörelsefält, medelvärdet för läget och kedjans fördelning för värdena, så att topparna inte planas ut som med utjämningen | lokal förskjutning CSI 1 mm upp till +0,10 vid 1 h (0010) | 2026-11-23 | 7 experiment, 3 veckor | i kön (0360 till 0381) |
| opera-bortfall (ur kallor-bortfall; 0300 och 0301 fällda av söm, volym och mätarna, nu med nivå och mjuk kant) | vid radarbortfall driftens utfyllnad de första 30 eller 60 minuterna, sedan OPERA | OPERA i hålet: FSS 1 mm 30 km +0,63 vid 90 till 360 min (säkert, på träningen och valideringen), men sämre vid 0 till 30 min | 2026-11-22 | 4 experiment, 2 veckor | i kön (0300, 0301, 0310, 0311) |

## Vilande eller stängda

| spår | varför | största säkra vinst | rapport |
|---|---|---|---|
| rorelse-lokal | stängt 2026-11-22, mättat: IDW-varianterna ger CSI +0,006 till +0,009 och sämre hopp, Farnebäck har 60 mått säkert sämre; taket för lokal förskjutning nås inte med rörelse ur historiken | +0,009 | kön 0110 till 0135 |
| kallor-analys | stängt 2026-11-22: satellitens torrmask tar bort riktigt regn i fjällen och på lovartsidan (kvot våt över 400 m och på lovartsidan säkert sämre), A0OS har fortfarande fler falska ekon | +0,0002 | kön 0210 till 0232 |
| kallor-bortfall | avgjort 2026-11-22: satelliten och mätarnas kvot gör ingen skillnad (kvoten troligen aldrig aktiv, se FylldM), OPERA är den stora vinsten och fortsätter som opera-bortfall | FSS 1 mm 30 km +0,63 (OPERA, 90 till 360 min) | kön 0220 till 0245 |
| lokal-forskjutning (tak) | klart: förskjutning dominerar till 2 h, nybildning efter 2 h | | kön 0010 till 0141 |
| terrangkvot | stängt 2026-11-20: kvoten per ruta, ledtimme och riktning ger CSI ±0,004 och säkert sämre toppar; kedjan har inget systematiskt fel per plats att lära | CSI 1 mm +0,004 | kön 0020 till 0023 |
| bias-v1-filter | stängt 2026-11-20 (sista budgeten för bias-v1): med F4 efter är falska ekon fortfarande säkert sämre | kvot våt per kvart +0,039 | kön 0030, 0031 |
| bias-v1 (ensam) | fyra försök fällda av falska ekon vid torra mätare; fortsätter bara som bias-v1-filter | kvot våt kvart +0,12 men spärren | uppgift 0024, 0025, 0027 |
| ringen vid Røst (OPERA) | villkorad mask finns avstängd (`--opera-ring villkor`), ingen dom vid svenska mätare möjlig; vilande tills den stora skivan behövs | | 0028, 0029 |
| tillväxt ur historiken | trenden ur blockmedlet gav +0,008 mot taket +0,059 (64 km) | CSI 1 mm +0,008 | 0018 |
| utjämning efter osäkerhet | fälld av blockmaxet i alla varianter | csi1 +0,02 på träningen | 0019 till 0021 |
| rörelse som ändras med ledtiden | 9 % av lägestaket | CSI 1 mm +0,007 | 0022 |
| kedjan utan fördelningsmatchning | inte bättre på valideringen | | 0013 |
| glappet vid Riksgränsen (domaren) | fälld på falska ekon; H = 3 är på efter användarens beslut | | 0010 |

## Omprövningar

### 2026-11-23, sammanslagningen

Användaren: optimal interpolation passar dåligt för nederbörd; pröva fyra andra vägar och iterera över varianter i varje. Fyra spår samtidigt, mot A2T och inte mot A0, så att bara det som slår den bästa analysen räknas. Veckans genomgång itererar inom det spår som visar störst säker vinst, men reglerna gäller: budget per spår och en tredjedel till de andra.

### 2026-11-23, tillägg

Användaren: bredda, inte bara en metod. Tre olika slags försök i kön samtidigt: hur OPERA fogas in vid bortfall (nivå och kant), OPERA i analysens glapp utan dess eget klotter, och en ensemble av kedjan över rörelsefälten. Principerna från en genomgång av hur andra kombinerar källor: vikta och rätta nivån mellan källorna innan de blandas, och ta bort klotter med oberoende data. Nästa vecka: fler observationer (grannländernas öppna stationsnät) i A2T, och en modell för var nya celler uppstår.

### 2026-11-22, veckans genomgång

Köns körskript hade inte startats om efter att `ko.py` ändrades, så domen för bortfallsdomaren saknades och `om_battre` ignorerades: valideringen kördes för alla kandidater i rorelse-lokal och kallor, inte bara de som var bättre på träningen. Ingen av dem var bättre på träningen, så inget valdes på valideringen, men valideringen är sedd en gång extra för de spåren. Körskriptet startar nu om sig självt när `ko.py` ändras. Det stora resultatet är OPERA vid radarbortfall. Nästa nya spår är nybildning ur satelliten (taket för nybildning är störst efter 2 h), som kräver en modell för var nya celler uppstår; det väljs nästa vecka.

### 2026-11-20, andra källor

Användaren beställde tio experiment med andra källor i analyssteget, med målet robusthet när radarn saknas och ett bättre analyssteg. Satellitens molnmask från MSG (SEVIRI, sedan 2004) hämtas och projiceras till SMHI:s rutnät (`experiments/kallor/satellit.py`, orienteringen kontrollerad mot land och hav en klar dag; norr om cirka 66 N beräknas ingen mask). OPERA finns i EUMETNET:s arkiv sedan 2012. Fyra experiment på analysens domare och sex på bortfallsdomaren; valideringen körs bara för det som är bättre på träningen. Strålhöjden (sannolikheten att strålen går över nederbörden) är redan med genom A0O:s zon; FCI och blixtar från MTG finns bara från 2025 och väljs inte nu.

### 2026-11-20, efter taken

Taken delade lägestaket: **lokal förskjutning** ger CSI 1 mm +0,045 / +0,101 / +0,087 vid 15 min / 1 h / 2 h och faller sedan, **nybildning** +0,036 / +0,087 / +0,121 / +0,149 vid 1 / 2 / 3 / 5 h. Kedjans täta fält görs med 20 grannar och potensen 0,5, nästan stelt, så spåret rorelse-lokal prövar fält som följer de lokala vektorerna. Nästa spår efter det är **nybildning ur satelliten** (molnmasken från MSG finns från 2004 och går att hämta), som har det största taket efter 2 h men kräver att datat hämtas och skärs till Skandinavien först.

### 2026-11-19, den första

Taken (0017, 0018, 0022) i CSI 1 mm vid 2 h mot `kedja_om`: tillväxt i block om 32 km +0,120, om 64 km +0,076, om 128 km +0,042; rörelse med ett fält 0, rörelse som ändras med ledtiden +0,007; utjämning vald i efterhand +0,044, med fast schema +0,003. Det mesta som är kvar är alltså **lägesfelet på 32 till 128 km (+0,078)**, som en stel rörelse inte förklarar, och **tillväxt i stor skala (+0,042)**. Hemtaget hittills: utjämningen gav +0,02 på träningen men fälldes av blockmaxet, trenden ur historiken +0,008; inget av det har gått igenom domaren.

Valet: (1) dela lägestaket med två tak (lokal förskjutning och nybildning), billigt och avgörande för vad som är värt en kandidat; (2) terrängkvoten som en tränad modell, eftersom den angriper både läge (regn som rörelsen flyttar bort från lovartsidan) och tillväxt (fjällen), och är projektets uttalade mål; (3) bias-v1 med F4, eftersom den största vinst som domaren någonsin har visat (+0,12 i mängd) bara fälldes av en spärr som F4 är byggt för. Utjämningen och rörelsen förblir vilande tills taken i (1) säger något annat. Satelliten (nybildning ur molnen) väljs om TakNybildning visar att nya celler är en stor del av lägestaket.
