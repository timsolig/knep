# Sammanfattning av natten 2026-11-06 (analysen)

Hela sammanfattningen, med domarens tabeller mot A0, rekommendationen för drift, körtiderna, det som återstår och kommandona för testdelen, står i [5-sammanfattning.md](5-sammanfattning.md). Den här filen är bara en hänvisning, så att texten inte finns i två versioner.

I korthet:

- **Domaren** (`experiments/analys/domare.py`) finns. Den korsvaliderar i block mot regnmätarna, och baslinjerna A0 och A1 är körda på valideringen (16 dagar).
- **A1 är inte bättre än A0.** Träffen per kvart blir bättre, men A1 ger 2 till 3 % mindre regn på lovartsidan, med intervallet på fel sida.
- **A2 är bättre än A0 men inte än A1.** Den ger mycket mer i terrängen (summakvoten över 400 m går från 0,52 till 0,68), men har fler falska ekon per kvart i terrängen än A1.
- **Filtret F4 är bättre än A0, men bara marginellt vid mätarna.** Det minskar kartmåttet för fast klotter från 36,6 till 27,6 rutor per dag och rör inte terrängen.
- **Rekommendationen:** driften går som i dag. Slå på `--klotter` först när kartan har släppts som modellfil (det ska användaren godkänna) och testdelen har körts.

Den här filen och `5-sammanfattning.md` är inte committade, eftersom git nekades av behörigheterna (se 5-sammanfattning.md).

Status: delvis
