# 0023 bias-v1: träning och korsvalidering mot regnmätarna

Kort: Kartan närmar volymen 1 (stationsvis korsvalidering 1,027 mot 0,883 utan karta, per år 0,99 till 1,06 mot 0,88 till 0,89) och fler stationer hamnar inom 20 % (0,45 mot 0,33), men radarns övre kvantiler (q99, q99,5) blir sämre (1,20 och 1,18 mot 1,03 och 1,08 av mätarnas) och per år är andelen inom 20 % sämre 2023 och 2025; värd att döma i analysens domare, med förbehåll.

Säkerställd förbättring: nej (ingen domare på valideringen kördes)

## Vad som gjordes

- `experiments/analys/bias_v1.py` (nytt): `MaskadStore(Store)` omsluter `Store.pairs`. Hela paret läses en gång för alla stationer, och G och R sätts till NaN för alla dygn i `experiments/sverige/dagar.json` (alla delar, utan att skilja på dem) plus ett dygn före och efter, innan `bias.fit` och `bias.cross_validate` ser något. Dygnen skrivs aldrig ut eller loggas. `flush` ger fel, så lagret kan inte skrivas. `bias.py` är orörd.
- Bortmaskade timmar (2023-01-01 till 2025-12-31): **672** (av 26 304).
- **Felvärden i mätararkivet.** Provkörningen gav volym 0,08 efter korrektion. Orsaken är att 14 292 mätarvärden (sju stationer, 14 277 av dem exakt 720) är långt över det möjliga, medan radarns största timvärde är 76 mm. Omslutningen sätter paret till NaN där G > 100 mm på en timme (`G_MAX`). Utan detta är varje tal i `fit` och `cross_validate` meningslöst, så driftens `bias.Store`/`fit` bör få samma spärr innan ett släpp (ett eget litet val med test, ingen ändring gjord här). Värdet 720 har inte setts i radarn, så felet ligger i mätarsidan; vilka stationer det är utreddes inte.
- Stationsvis korsvalidering: 5 delar, frö 0, som `bias.cross_validate`, men med Rc sparat så att uppdelningarna går att räkna. Kontrollen mot `bias.cross_validate` ger identiskt `volym_efter` (1,02716).
- Korsvalidering per år: kartan tränad på de två andra åren (året maskat i `Store`), prövad på det tredje året på alla stationer. Det är alltså inte stationsvis, utan över tid.
- Rutnät: `/data/radar/2024/06/27/202406272230.tif`.
- Inget skrevs till `/data` (där fanns 1 335 MB ledigt, under gränsen) eller `/work/cache/bias`. Allt gick till `/dev/shm/bias_v1/`.

## Tid och minne

Provkörning 2024-06 till 2024-08: 10 s, 160 MB. Full körning 2023 till 2025 med fit, 5 delar, kontrollkörningen och tre årsvalideringar: 71 s, toppminne 438 MB. G och R är 26 304 timmar gånger 168 stationer, 18 MB per matris i float32, så inget behövde nedskalas.
## Tabeller

Alla från `/dev/shm/bias_v1/full/tabeller.md` (finns i sin helhet där under körningen; tabellerna nedan är de som behövs för domen). f = före (rå radar), e = efter (kartan och svansen). Volym = summa radar / summa mätare över stationerna, median och andel inom 20 % är över stationernas kvot (stationer med minst 50 mm). Kvantilerna är radarns kvot mot mätarnas, för våta timmar sammanslaget över stationer.

### Träning och stationsvis korsvalidering, hela perioden

| | volym f | volym e | median f | median e | ±20 % f | ±20 % e | q99 f / e | q99,5 f / e | q99,9 f / e | q99,95 f / e |
|---|---|---|---|---|---|---|---|---|---|---|
| träning (i urvalet) | 0,883 | 1,000 | 0,937 | 1,025 | 0,33 | 0,56 | 1,03 / 1,18 | 1,08 / 1,16 | 1,16 / 1,08 | 1,20 / 1,08 |
| korsvalidering (5 delar) | 0,883 | 1,027 | 0,937 | 1,033 | 0,33 | 0,45 | 1,03 / 1,20 | 1,08 / 1,18 | 1,16 / 1,11 | 1,20 / 1,11 |

168 stationer; mätarnas kvantiler är 4,3, 5,6, 10,0 och 12,2 mm. Svansexponenten γ blev −0,20, alltså vid gränsen (`TAIL_GAMMA`): den vill trycka ned radarns svans mer än det tillåtna. Efter nivåhöjningen ligger q99 och q99,5 över mätarna och bara q99,9 och q99,95 närmare.

### Korsvalidering per år (tränat på de andra två åren)

| prövat år | volym f / e | median f / e | ±20 % f / e | q99 f / e | q99,5 f / e | q99,9 f / e | q99,95 f / e |
|---|---|---|---|---|---|---|---|
| 2023 (165 st.) | 0,887 / 1,063 | 0,889 / 1,043 | 0,39 / 0,33 | 1,03 / 1,29 | 1,10 / 1,34 | 1,19 / 1,32 | 1,19 / 1,33 |
| 2024 (167) | 0,876 / 0,988 | 0,938 / 1,028 | 0,29 / 0,41 | 0,99 / 1,10 | 1,02 / 1,04 | 1,08 / 0,94 | 1,13 / 0,95 |
| 2025 (167) | 0,888 / 1,005 | 0,963 / 1,088 | 0,32 / 0,27 | 1,09 / 1,27 | 1,15 / 1,24 | 1,22 / 1,12 | 1,26 / 1,14 |

Volymen blir närmare 1 alla tre åren, men andelen inom 20 % bara 2024. Det ligger ett år av egen variation i det: vårmånaderna 2023 (volym f 0,84, e 0,88) och 2025 har mycket få stationer med 50 mm.

### Efter årstid och strålhöjd (stationsvis korsvalidering)

| urval | stationer | volym f / e | median f / e | ±20 % f / e | q99 f / e | q99,9 f / e |
|---|---|---|---|---|---|---|
| vinter (dec till feb) | 167 | 0,807 / 1,029 | 0,806 / 1,083 | 0,26 / 0,35 | 1,15 / 1,46 | 1,58 / 1,84 |
| vår (mar till maj) | 166 | 0,924 / 1,036 | 0,974 / 1,027 | 0,32 / 0,33 | 1,08 / 1,19 | 1,45 / 1,40 |
| sommar (jun till aug) | 168 | 0,980 / 1,024 | 0,982 / 1,007 | 0,28 / 0,37 | 1,04 / 1,06 | 1,21 / 1,02 |
| höst (sep till nov) | 168 | 0,815 / 1,025 | 0,831 / 1,026 | 0,28 / 0,43 | 1,01 / 1,27 | 1,12 / 1,18 |
| stråle under 1 km | 58 | 1,006 / 1,049 | 0,972 / 1,017 | 0,31 / 0,55 | 1,10 / 1,16 | 1,18 / 1,05 |
| stråle 1 till 2 km | 70 | 0,871 / 1,008 | 0,927 / 0,992 | 0,37 / 0,47 | 1,00 / 1,18 | 1,07 / 1,03 |
| stråle över 2 km | 40 | 0,754 / 1,033 | 0,804 / 1,179 | 0,30 / 0,25 | 0,99 / 1,33 | 1,22 / 1,36 |

Sammanfattning av mönstret: vinter och höst har den stora volymbristen (0,81) och den rättas, men kvantilerna (och i vinter också q99,9 = 1,84) hamnar långt över mätarna eftersom nivån höjs lika för alla intensiteter; över 2 km sjunker ±20 %-andelen (0,30 till 0,25) och medianen blir 1,18, så nivån är för hög där. Sommaren förändras lite och är oproblematisk. Hela månadstabellerna (träning, korsvalidering och per år) finns i `tabeller.md` under körningen; månadsvolymerna efter i korsvalideringen ligger mellan 0,99 och 1,03 mot 0,76 till 0,99 före.

### Faktorns spridning på kartan (K, nivåfaktorn där strålen når; mitt i månaden)

| | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | andel > 1,5 | andel < 0,7 |
|---|---|---|---|---|---|---|---|---|---|---|
| jan | 0,77 | 0,88 | 1,07 | 1,34 | 1,92 | 4,00 | 4,00 | 4,00 | 0,40 | 0,004 |
| apr | 0,70 | 0,81 | 0,95 | 1,17 | 1,82 | 4,00 | 4,00 | 4,00 | 0,33 | 0,012 |
| jul | 0,70 | 0,79 | 0,94 | 1,02 | 1,26 | 2,01 | 2,28 | 3,06 | 0,15 | 0,009 |
| okt | 0,80 | 0,93 | 1,09 | 1,27 | 1,70 | 3,39 | 4,00 | 4,00 | 0,33 | 0,000 |

Per strålhöjd (medelfaktor jan / jul): under 1 km 1,02 / 0,99; 1 till 2 km 1,24 / 1,02; 2 till 3 km 1,67 / 1,12; över 3 km 3,11 / 1,58 (74 891 celler, i januari är 99,8 % av dem över 1,5). Faktorn är störst i norr och i fjällkedjans lä: störst 4,00 (taket `LOGK_MAX`) vid ungefär 66,7 N, 16,1 E där strålen går på 4 km; tyngdpunkten för celler över 1,5 ligger vid 62,9 N, 16,6 E (jan) och 63,4 N, 16,6 E (jul). Restkartans log-spridning är p1 −0,34, p50 0,00, p99 +0,71. Minst 5 % av nätet i januari (p95 = 4,00) står alltså vid taket 4, och polynomets extrapolation där (få mätare, strålhöjd över 3 km) är inte prövad av korsvalideringen, som bara har stationer där det finns mätare. Domaren bör titta särskilt på norra Sverige och fjällen.

## Är kartan värd att döma?

Kriteriet var volymen närmare 1 och fler stationer inom 20 % utan att kvantilerna blir sämre. Det första och andra uppfylls i stationsvis korsvalidering (volym 1,027 mot 0,883, ±20 % 0,45 mot 0,33, median 1,03 mot 0,94), men kvantilerna q99 och q99,5 blir sämre (1,20 och 1,18 mot 1,03 och 1,08), mest i vinter, höst och över 2 km, och över tid (per år) håller förbättringen av ±20 % bara ett av tre år. Strikt tolkat uppfylls villkoret därför **inte**. Min bedömning ändå: kartan är värd att döma i analysens domare, eftersom volymbristen på 12 % är verklig och domaren mäter det som är viktigast för användningen (mängd, träff, falska ekon, terräng) på riktiga fält, där ett för högt q99 kanske inte spelar roll, men falska ekon och terräng kan bli sämre. Skulle domaren visa att falska ekon blir sämre är nästa steg att pröva en nivå som inte lyfter svagt eko (till exempel en `LOGK_MAX` på 2 och/eller en tak över strålhöjd 3 km), och att släppa spärren på γ (−0,2 är bunden).

## Så kör nästa uppgift kartan genom domaren

Kartan går in i A0 som ett nytt system i `experiments/analys/domare.py` (eller en egen fil som lägger till i `SYSTEMS`):

```python
class A0B(A0):
    """A0 med volymkorrektionen bias-v1 (karta ur /dev/shm/bias_v1/full/bias_v1.npz)."""
    namn = "A0B"
    def frames(self):
        if hasattr(self, "_frames"): return self._frames
        corr = bias.Correction.load(KARTA)           # mfb är av (ingen medelfältsfaktor)
        self.rd.sparse_motion()
        for k in range(len(self.rd.times)):          # rd.rain[k] är den råa SMHI-bilden, NaN utanför
            if k % 12 == 0: K = corr.factor(self.rd.times[k])   # faktorn ändras långsamt, räkna per timme
            self.rd.rain[k] = corr.tail(self.rd.rain[k] * K)
        return super().frames()                       # fill_gaps kör på de rättade bilderna
```

Korrektionen läggs alltså före `composite.fill_gaps`, på den råa SMHI-bilden (samma plats som i fit, som räknar på rå analys), och rutnätet måste vara detsamma som kartan (`beam.shape` == `rd.grid.shape`; kontrollera med assert). Kartan ska vara den med sha256 nedan. Kör sedan `uv run python experiments/analys/domare.py kor A0 A0B --del validering` och `tabell A0B --mot A0 --del validering`. Tiden är A0:s tid (en faktorbild per timme tillkommer, några tiotal millisekunder) per dygn. Observera:

1. Valideringsdygnen och testdygnen (och deras grannar) är bortmaskade ur kartans träning. Dygnen ligger dock på stationer som kartan har sett andra dagar (restkartan r(x) är inlärd vid stationerna). Domarens korsvalidering i block mot mätarna är därför inte stationsvis fri; tabellen här (stationsvis CV) visar att effekten bärs även utan det, men ±20 %-vinsten är då lägre (0,45 mot 0,56).
2. Valideringsdygn före 2023 ligger utanför kartans träningsår (och är då ett prov över tid); dygn 2023 till 2025 är bortmaskade, så ingen läcka.
3. Domen ska följa domarens regel (mängd eller träff bättre med intervallet på rätt sida, falska ekon och terräng inte sämre). Medelfältsfaktorn (`mfb`) ingår inte.

## Filer

- `experiments/analys/bias_v1.py` (nytt). Inga data och ingen karta i repot.
- Kartan: `/dev/shm/bias_v1/full/bias_v1.npz` (1 094 680 byte), sha256 `1d79d27eacb9d3e4578ddc0c87537b84bb8f540896f9e9a952b9a59a1d625373`. Den ligger på `/dev/shm` och försvinner vid omstart; kopiera den (några MB) vid behov, eller skapa den på nytt på 71 s med `uv run python experiments/analys/bias_v1.py --start 2023-01-01 --end 2025-12-31 --grid /data/radar/2024/06/27/202406272230.tif --out /dev/shm/bias_v1/full --years` (samma resultat, inget slumpmoment utöver frö 0).
- Tabellerna och `resultat.json` ligger kvar i `/dev/shm/bias_v1/full/` (`tabeller.md`, några tiotal kB). Provkörningens mapp `prov/` och hjälpskriptet `insp.py` är borttagna om det gick; annars kan de tas bort.

## Nästa steg

1. Lägg spärren G > 100 mm (eller liknande) i `Store.pairs`/driftens insamling som ett litet val med test, så att felvärdena (720 mm) inte kan förstöra en karta i drift. Utred vilka sju stationer som har dem.
2. Domaren: A0B mot A0 på valideringen enligt ovan.
3. Förbättringar att pröva om domen blir blandad: tak på K (4 är för högt för det som korsvalideringen inte kan pröva), lägre nivåhöjning där strålen går över 3 km, γ utanför −0,2, och korsvalidering med block över stationer i fjällen.
4. Ingenting släpps; släppet beslutar användaren.

Status: klar
