# 2 Sömlös till 5 h i domaren (somlos)

Uppgiften var nattens uppgift 5 från 2026-11-04, som aldrig kördes: ett system `somlos` i domaren (kedjan blandad med MEPS rättad mot radarn), baslinjen mot `kedja` på valideringen, varianter som håller kvar topparna i blandningen, valda på träningsdagarna, finalisten bedömd mot `somlos`, och körtiden för hela kedjan med MEPS på Pi:n.

Rapport 1 i natt (verif-persistens) är `delvis` men gäller driftens verifiering, inte domaren, och lämnar inget halvfärdigt som den här uppgiften behöver.

## MEPS för dagarna

`experiments/projektion/meps_koll.py` (nytt) går igenom körningarna som behövs (var 6:e timme, 2,5 h fördröjning, som `data.CYCLE`):

- Träningsdagarna (28): MEPS finns för alla.
- Valideringen (16): 13 dygn kompletta. 2019-03-08 och 2019-03-17 saknar MEPS helt (MEPS låg 2019 på ett äldre rutnät, se `experiments/sverige/README.md`). 2024-06-28 saknar 18Z-körningen, som bara behövs för utgåvan kl 21.

Därför har domaren ett nytt läge **`validering_meps`**: som `validering_gles` (var 3:e timme, 2 km) men utan de två dygnen från 2019, alltså 14 dygn. Kl 21 den 2024-06-28 blir `somlos` kedjan (som i drift när MEPS inte går att hämta). Kedjan kördes om i läget (`kedja`, läser bara driftens sparade prognoser), så att båda jämförs på exakt samma dygn och utgåvor.

## Systemet somlos

`experiments/projektion/somlos.py`, klassen `Somlos`, gör det som `sommodell.blended(P, "rättad")` (form5h `sömlös`) och `forlust.py` gör:

- kedjan: driftens sparade prognoser i `/data/sverige/kedja` på 2 km; i läget `snabb` (4 km) kedjan körd om med uppvärmd platskarta (`KedjaSpar`, sparad i `/data/projektion/cache/somlos/4km/`, 6 MB)
- MEPS: körningen som fanns vid utgåvan, interpolerad mitt i varje kvart (`seamless.meps_at`), omprojicerad till radarns rutnät och på 4 km medlad 2 x 2
- rättningen (`seamless.assimilate`) varje hel timme från dygnets början till utgåvan, som verifieringen gör, eftersom domaren bara har utgåvor var 3:e timme; tillståndet börjar om varje dygn
- blandningen per kvart med ledtiden mitt i kvarten.

Varianterna ändrar bara blandningen (`blend_v`). Med standardvärdena är den exakt `seamless.blend` (`test_somlos.py`):

| val | vad |
|---|---|
| `t50_q` | egen viktkurva för fördelningen (kvantilerna) i stället för de små skalornas |
| `top_w`, `top_thr` | kedjans fördelning för de höga värdena: kedjans vikt i målfördelningen är minst `top_w` för kedjans värden över `top_thr` (övergång från `top_thr`/2 till 2·`top_thr`) |
| `fine_lam`, `fine_km` | kedjans små skalor (under `fine_km`) läggs till efter blandningen, gånger (1 − kedjans vikt) |
| `t50_fine`, `fine_km` | vikten per skala: tre skalor i stället för två, med en egen viktkurva för skalorna under `fine_km` |
| `t50_small`, `t50_large`, `shape` | viktkurvan |

Status: delvis
