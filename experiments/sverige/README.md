# Svenska fall 0 till 5 h: kedjan, MEPS och den sömlösa modellen

Syftet är att förlänga prognosen till 5 h och mäta det mot radarn på svenska dagar. Kedjan, som slår KNEP-proxyn de första timmarna (`experiments/README.md`), förlängs och blandas med MEPS, som rättas mot radarn löpande (`src/knep/seamless.py`).

## Data

- **Radar**: SMHI:s komposit var 5:e minut ur det öppna arkivet, i `/data/radar/ÅÅÅÅ/MM/DD/`, cirka 19 MB per dygn.
- **MEPS**: MetCoOps deterministiska körningar ur MET Norges arkiv (`meps25epsarchive`), ett utsnitt över radarns rutnät med timsummor 0 till 14 h, i `/data/meps/`, cirka 2 MB per körning. Arkivet har körningarna 00, 06, 12 och 18 alla år (2023 även var 3:e timme), med filnamnet `meps_det_2_5km` till 2023 och `meps_det_sfc` från 2024. Verifieringen använder bara körningarna var 6:e timme, så att alla år behandlas lika; i drift finns de var 3:e timme, så MEPS är där i medel 1,5 h färskare än här. En körning räknas som tillgänglig 2,5 h efter körtiden (i realtid kom 18Z-körningen 20:20). 2019 ligger MEPS på ett äldre, mindre rutnät; de två dagarna därifrån har bara kedjans prognoser och räknas inte i jämförelserna med MEPS.

MNWC, som uppdateras varje timme, finns inte som öppen data hos MET Norge, FMI eller SMHI. MET Nordic (`met_forecast_1_0km_nordic`) uppdateras varje timme, men arkivet har bara fyra körningar per dygn, och den är redan efterbearbetad med MET:s egen nowcast.

## Dagarna

`data.py kandidater` provar radarn kl 00, 06, 12 och 18 var 3:e dag 2019 till 2025 och räknar den våta ytan (minst 0,5 mm/h) och ytan med kraftigt regn (minst 5 mm/h; enstaka toppar är ofta klotter). `data.py urval` väljer sex dagar per årstid, de med störst våt yta (på sommaren hälften efter ytan med kraftigt regn), plus Hans 2023 (7 och 8 augusti) och skyfallet i Gävle 2021 (17 augusti). Var tredje dag i datumordning och de namngivna går till testdelen, resten till valideringsdelen. Indelningen bestäms av datumet och fryses i `dagar.json`.

Inställningar och vikter väljs bara på valideringsdelen. Testdelen körs en gång, i slutet.

## Körning

```sh
python experiments/sverige/data.py kandidater && python experiments/sverige/data.py urval
python experiments/sverige/data.py radar && python experiments/sverige/data.py meps
for i in 0 1 2; do python experiments/sverige/kedja.py --shard $i/3 & done; wait
python experiments/sverige/verify5h.py --part validering --system kedja meps persistens meps_rättad sömlös
```

`kedja.py` kör kedjan var 5:e minut genom dygnet som i drift, så att platskartan har sitt tillstånd, och sparar 5 h-prognosen varje hel timme som 20 kvartsmedel. Med extrapoleringen i OpenCV (`src/knep/advect.py`) tar ett dygn cirka en halvtimme på Pi:n.

## Mått

Per kvart 15 min till 5 h och per timme 1 till 5: CSI vid 0,5, 1 och 5 mm/h, FSS vid 1 och 5 mm/h på 10, 30 och 90 km, och volymen mot radarn. Alla system jämförs på samma pixlar: där radarn har data och kedjans prognos finns.

## Resultat

Se `resultat.md`.
