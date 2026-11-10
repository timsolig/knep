# 0019 utjämning efter fältets osäkerhet

Skelett, fylls i efter varje del. Disken vid start: 2 470 MB ledigt på `/` (`/data` ligger på samma disk, över gränsen 2 000 MB).

## Plan

1. `experiments/projektion/utjamning.py`: klassen `Utjamning` (ärver `domare.KedjaOm`), sigma ur två rörelsefält (a) och ur två extrapoleringar från olika start (b), toppskydd max(utjämnat, α · original).
2. Provkörning, tid per utgåva.
3. Sökning i `snabb`, högst 4 varianter, frys.
4. Den frysta på `traning` (12 dagar som i 0018).

Kort: (inte klar)
Säkerställd förbättring: nej
Status: delvis
