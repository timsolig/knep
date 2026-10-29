Sannolikhet för minst 5 och 10 mm/h per pixel, 5 till 120 min framåt.

- En gradient boosting-modell per tröskel (1, 5, 10, 20 mm/h; 5 och 10 används i drift), 150 iterationer, monotona i intensitetssärdragen, isoton omkalibrering per ledtidsintervall.
- Tränad på alla sex öppna fall i pysteps-data (FMI 2016 och 2017, MeteoSwiss 2015 och 2017, KNMI 2010, RMI 2021) med kedjans särdrag: glesa bilder till rörelsen (15 min mellanrum) och fördelningsmatchning mot den flyttade analysen.
- scikit-learn 1.9.1. Annan version: träna om enligt experiments/README.md.

Verifiering med ett fall utanför i taget (experiments/results/prob_ny_kedja.json), Brier skill score mot händelsens klimatologi:

| Tröskel | 15 min | 30 min | 60 min | Grannskap 30 km, 15 min |
|---|---|---|---|---|
| 5 mm/h | 0,32 | 0,14 | 0,02 | 0,22 |
| 10 mm/h | 0,18 | 0,02 | 0,00 | 0,12 |

Känd svaghet: för 10 mm/h vid 30 min är sannolikheterna för höga (0,23 motsvarar 0,12 observerat).
