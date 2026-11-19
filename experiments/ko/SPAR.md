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
| lokal-forskjutning (nytt, tak) | dela lägestaket på 32 till 128 km i lokal förskjutning och nybildning, så att nästa spår väljs efter rätt del | lägestaket CSI 1 mm +0,078 vid 2 h (0017, 0018 minus 0022) | 2026-11-19 | 5 experiment, 1 vecka | i kön (0010 till 0012, 0040, 0041) |
| terrangkvot (nytt, tränad modell) | en kvot facit/kedja per ruta, ledtimme och vindriktning, lärd på 22 träningsdagar och bedömd på de 6 i snabb; projektets mål om nederbörd bunden till terrängen | del av tillväxttaket 32 km (+0,035 till +0,120), ren tillväxt i 128 km är +0,010 till +0,050 (0018) | 2026-11-19 | 12 experiment, 3 veckor | i kön (0020 till 0023) |
| bias-v1-filter (öppnat igen, nytt skäl) | bias-v1 fälldes bara av falska ekon; F4 tar bort klotter som korrektionen förstärker | kvot våt per kvart +0,12 (0024) | 2026-11-19 | 6 experiment, 2 veckor (sista budgeten för bias-v1) | i kön (0030, 0031) |

## Vilande eller stängda

| spår | varför | största säkra vinst | rapport |
|---|---|---|---|
| bias-v1 (ensam) | fyra försök fällda av falska ekon vid torra mätare; fortsätter bara som bias-v1-filter | kvot våt kvart +0,12 men spärren | uppgift 0024, 0025, 0027 |
| ringen vid Røst (OPERA) | villkorad mask finns avstängd (`--opera-ring villkor`), ingen dom vid svenska mätare möjlig; vilande tills den stora skivan behövs | | 0028, 0029 |
| tillväxt ur historiken | trenden ur blockmedlet gav +0,008 mot taket +0,059 (64 km) | CSI 1 mm +0,008 | 0018 |
| utjämning efter osäkerhet | fälld av blockmaxet i alla varianter | csi1 +0,02 på träningen | 0019 till 0021 |
| rörelse som ändras med ledtiden | 9 % av lägestaket | CSI 1 mm +0,007 | 0022 |
| kedjan utan fördelningsmatchning | inte bättre på valideringen | | 0013 |
| glappet vid Riksgränsen (domaren) | fälld på falska ekon; H = 3 är på efter användarens beslut | | 0010 |

## Omprövningar

### 2026-11-19, den första

Taken (0017, 0018, 0022) i CSI 1 mm vid 2 h mot `kedja_om`: tillväxt i block om 32 km +0,120, om 64 km +0,076, om 128 km +0,042; rörelse med ett fält 0, rörelse som ändras med ledtiden +0,007; utjämning vald i efterhand +0,044, med fast schema +0,003. Det mesta som är kvar är alltså **lägesfelet på 32 till 128 km (+0,078)**, som en stel rörelse inte förklarar, och **tillväxt i stor skala (+0,042)**. Hemtaget hittills: utjämningen gav +0,02 på träningen men fälldes av blockmaxet, trenden ur historiken +0,008; inget av det har gått igenom domaren.

Valet: (1) dela lägestaket med två tak (lokal förskjutning och nybildning), billigt och avgörande för vad som är värt en kandidat; (2) terrängkvoten som en tränad modell, eftersom den angriper både läge (regn som rörelsen flyttar bort från lovartsidan) och tillväxt (fjällen), och är projektets uttalade mål; (3) bias-v1 med F4, eftersom den största vinst som domaren någonsin har visat (+0,12 i mängd) bara fälldes av en spärr som F4 är byggt för. Utjämningen och rörelsen förblir vilande tills taken i (1) säger något annat. Satelliten (nybildning ur molnen) väljs om TakNybildning visar att nya celler är en stor del av lägestaket.
