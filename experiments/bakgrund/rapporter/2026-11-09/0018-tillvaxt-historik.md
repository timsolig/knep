# 0018 tillväxt och avtagande ur historiken

(Delrapport efter del 1; del 2 fylls i därefter.)

## Disken

`df -m /data`: 2 553 MB ledigt vid starten (över 2 000 MB). Summorna är små.

## Del 1: taket vid 32, 64 och 128 km

`TakTillvaxt64` och `TakTillvaxt128` (ärver `TakTillvaxt`, `block_km` som klassvärde) kördes på `snabb` (6 dygn, 48 utgåvor, 4 km, två processer, 548 s respektive cirka 15 processorminuter). Hela tabellerna (med `persistens`) ligger i `/data/projektion/tak_tillvaxt_tabell.md`; siffrorna nedan är skillnaden mot `kedja_om`, positiv är bättre (domarens tabell visar csi och fss med omvänt tecken). Intervallen är 95 % från bootstrap över dygnen och ligger för csi1 och fss1_30 helt över noll i alla celler. Referensvärden för `kedja_om` står i 0017.

| mått | block | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|---|
| csi1 | 32 km | +0,035 | +0,065 | +0,104 | +0,120 | +0,117 | +0,097 |
| csi1 | 64 km | +0,019 [+0,013, +0,026] | +0,034 [+0,021, +0,050] | +0,059 [+0,043, +0,078] | +0,076 [+0,062, +0,092] | +0,079 [+0,068, +0,091] | +0,073 [+0,057, +0,089] |
| csi1 | 128 km | +0,010 [+0,007, +0,014] | +0,016 [+0,009, +0,026] | +0,030 [+0,019, +0,042] | +0,042 [+0,031, +0,054] | +0,048 [+0,038, +0,058] | +0,050 [+0,035, +0,066] |
| fss1_30 | 32 km | +0,013 | +0,040 | +0,099 | +0,169 | +0,195 | +0,200 |
| fss1_30 | 64 km | +0,009 [+0,006, +0,014] | +0,029 [+0,018, +0,048] | +0,075 [+0,049, +0,114] | +0,133 [+0,099, +0,180] | +0,160 [+0,127, +0,206] | +0,173 [+0,136, +0,222] |
| fss1_30 | 128 km | +0,006 [+0,003, +0,010] | +0,017 [+0,010, +0,029] | +0,044 [+0,027, +0,071] | +0,084 [+0,057, +0,120] | +0,106 [+0,081, +0,143] | +0,129 [+0,096, +0,175] |
| csi5 | 32 km | +0,051 | +0,078 | +0,098 | +0,106 | +0,092 | +0,065 |
| csi5 | 64 km | +0,029 | +0,045 | +0,050 | +0,058 | +0,060 | +0,044 |
| csi5 | 128 km | +0,019 | +0,025 | +0,023 | +0,030 | +0,036 | +0,029 |
| fss5_10 | 32 km | +0,044 | +0,099 | +0,162 | +0,217 | +0,218 | +0,165 |
| fss5_10 | 64 km | +0,029 | +0,062 | +0,092 | +0,132 | +0,151 | +0,119 |
| fss5_10 | 128 km | +0,020 | +0,037 | +0,046 | +0,073 | +0,094 | +0,082 |

Blockmax_q90 (skillnaden i |log kvot| mot radarn, negativ är bättre; sämre än `kedja_om` vid 120, 180, 300 min):

| block | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| 32 km | +0,054 | +0,036 | +0,004 | +0,173 (sämre) | +0,233 (sämre) | +0,371 (sämre) |
| 64 km | +0,040 | -0,002 | -0,048 | +0,079 | +0,138 (sämre) | +0,251 (sämre) |
| 128 km | +0,009 | +0,001 | -0,053 | -0,002 | +0,071 | +0,169 (sämre) |

**Andel av luckan till CSI 1** (1 − csi1 för `kedja_om`: 0,266, 0,425, 0,586, 0,729, 0,793, 0,854):

| block | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| 32 km | 13 % | 15 % | 18 % | 16 % | 15 % | 11 % |
| 64 km | 7 % | 8 % | 10 % | 10 % | 10 % | 9 % |
| 128 km | 4 % | 4 % | 5 % | 6 % | 6 % | 6 % |

Tolkning: taket faller ungefär till hälften för varje fördubbling av blocket (32 till 64 km: 55 till 65 % av taket kvar, 64 till 128 km: 50 till 65 %). Vid 128 km, där kvoten knappast kan rätta något lägesfel, återstår ändå 4 till 6 % av luckan, med intervallen helt över noll i csi1 och fss1_30 vid alla ledtider. Det är alltså sant tillväxt och avtagande i stor skala, men bara cirka en tredjedel av 32 km-taket; resten är massa som flyttas mellan block på 32 till 128 km, alltså lägesfel och bruset i facit. Blockmaxet slutar vara säkert sämre först vid 128 km för 120 till 180 min. Prognosens verkliga kvot ur historiken ska alltså förväntas ge en bråkdel av 4 till 6 % av luckan (CSI 1 mm några hundradelar vid 1 till 3 h).

## Del 2: kandidaten utan facit

(pågår: `experiments/projektion/tillvaxt.py`, varianterna `TV_t30_b32`, `TV_t60_b32`, `TV_t120_b32`, `TV_t60_b64` på `snabb`.)

## Filer

`experiments/projektion/tak.py` (klasserna `TakTillvaxt64`, `TakTillvaxt128`), `experiments/projektion/tillvaxt.py`, `experiments/projektion/tabell_0018.py`.

## Nästa steg

(fylls i)

Kort: (pågår)
Säkerställd förbättring: nej
Status: delvis
