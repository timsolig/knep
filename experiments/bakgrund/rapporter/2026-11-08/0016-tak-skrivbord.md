# 0016 tak-skrivbord

Bash fungerade för de två första anropen (`df -h /data`: 3,2 GB ledigt på `/`, där `/data` ligger; en kommandorad med `wc`, `grep` och `head`) och nekades sedan ("don't ask"). Jag försökte inte igen. Därför är `tak.py` **inte körd, inte importerad och inte ens syntaxkontrollerad**; jag har bara läst den mot domaren. Inget är committat (git kräver Bash); loopen committar.

## Vad jag gjorde

Läste `experiments/projektion/domare.py` (hela), `src/knep/prognos/model.py` (hela), `traning.json`, `somlos.py` (för konventionen för system i egna filer), `test_domare.py`, `resultat/snabb.md` och rapport 0015. Skrev `experiments/projektion/tak.py` med fem fuskvarianter. Ändrade inte `domare.py`, `src/`, `deploy/`, `models/` eller `dagar.json`; läste inte testdelen; skrev ingen data.

pytest: `pyproject.toml` har ingen `testpaths` eller `python_files`, så pytest samlar bara `test_*.py`, och `tak.py` heter inte så. Dessutom körs inget vid import utöver definitioner (och domarens egen import). Ingen testfil är tillagd.

## Fuskvarianterna och var de kopplas in

Alla ärver `domare.KedjaOm` (kedjan körd om här med platskartans tillstånd uppvärmt, som baslinjen `kedja_om`), så de skiljer sig från baslinjen bara i den del som får facit. Facit är `ctx.quarter(t + k·15 min)` för k = 1..20, exakt det domaren mäter mot (`facit()` i `tak.py`). Domaren hittar dem via `modul:Klass` (`make_system`), och summorna hamnar i `/data/projektion/domare/<läge>/tak_<Klass>/<dag>.npz`.

| system (`--system`) | vad som fuskas | var det kopplas in |
|---|---|---|
| `tak:TakRorelse` | rörelsefältet | `hindsight_motion`: Lucas-Kanade (som `Ctx.motion`) på radarbilderna `t, t+15, ..., t+300 min` (stannar vid första saknade bild, minst 4 bilder annars historikens fält), tätat med `model.dense_motion` och delat med `motion_gap`. Skickas som `motion=` till `Chain.run`. Platskartans uppvärmning (`observe`) använder fortfarande historikens rörelse |
| `tak:TakMangd` | volymen | efter kedjan: fält k gånger summa(facit)/summa(prognos) över rutorna där båda finns, per ledtid |
| `tak:TakTillvaxt` | tillväxt och avtagande i stor skala | efter kedjan: fält k gånger `block_ratio` (box 32 km, kvot (mo+0,02)/(mf+0,02), klippt till [1/4, 4], utjämnad med sigma = blocket/4). Regn som kedjan inte har alls kan inte växa fram |
| `tak:TakUtjamningFast` | utjämning, fast schema | efter kedjan: `smooth` (gaussisk, NaN-säker) med sigma 0, 0, 2, 4, 8, 12 km vid 0, 1, 2, 3, 4, 5 h, linjärt emellan |
| `tak:TakUtjamningBast` | utjämning, vald i efterhand | efter kedjan: sigma per utgåva och kvart ur 0, 2, 4, 8, 12, 16, 24 km, den som ger högst FSS (1 mm/h, fönster 10 km) mot facit. Skriver ut valda sigman per utgåva |

Namnen i uppgiften (`tak_rorelse` med flera) kan inte användas rakt av: domaren sätter katalognamnet till `modul_Klass`. Tabellerna kallas därför `tak_TakRorelse`, `tak_TakMangd`, `tak_TakTillvaxt`, `tak_TakUtjamningFast`, `tak_TakUtjamningBast`.

## Körplan

Alla kommandon körs från repots rot. Först (en gång) en kontroll att baslinjens summor finns; annars körs de först (14 processorminuter, `snabb.md` visar 48 utgåvor):

```
ls /data/projektion/domare/snabb/kedja_om | head
df -h /data        # avbryt om mindre än 3 GB ledigt
# bara om kedja_om saknas:
timeout 7200 uv run python experiments/projektion/domare.py kör --läge snabb --system kedja_om --procs 2
```

**Provkörning, en dag, en process** (2020-02-10 är första dagen i `snabb`; resultatet återanvänds av den fulla körningen, så det går inte till spillo). Börja med den billigaste varianten som visar att importen och kopplingen fungerar, sedan den dyraste:

```
cd experiments/projektion
timeout 1800 python domare.py kör --läge snabb --system tak:TakMangd --dagar 2020-02-10 --procs 1
timeout 1800 python domare.py kör --läge snabb --system tak:TakRorelse --dagar 2020-02-10 --procs 1
```

Förväntat: en rad `tak_TakMangd snabb 2020-02-10: 8 utgåvor på ~100-150 s`, `tak_TakRorelse` ungefär 2 till 5 min (8 utgåvor, kedjan ~17 s per utgåva enligt 14 processorminuter på 48 utgåvor, plus Lucas-Kanade på 21 bilder). En tabell med intervall går inte på en dag (bootstrap över ett dygn), så titta direkt på summorna:

```
python - <<'EOF'
import numpy as np, domare as D
a = dict(np.load("/data/projektion/domare/snabb/tak_TakMangd/2020-02-10.npz"))
b = dict(np.load("/data/projektion/domare/snabb/kedja_om/2020-02-10.npz"))
print("TakMangd volym f/o per ledtid:", a["vol"][:,0]/a["vol"][:,1])   # ska vara nära 1 (kodningen runt värdefilen ger små avvikelser)
print("kedja_om volym f/o:           ", b["vol"][:,0]/b["vol"][:,1])
EOF
```

**De sex dagarna i `snabb`, två processer** (en process per dygn, `--procs 2`; kör ett system i taget i bakgrunden med loggfil):

```
cd experiments/projektion
nohup timeout 7200 python domare.py kör --läge snabb --procs 2 --system \
  tak:TakMangd tak:TakTillvaxt tak:TakUtjamningFast tak:TakUtjamningBast tak:TakRorelse \
  > /data/projektion/tak_snabb.log 2>&1 &
```

Väntad tid (skattad ur `snabb.md`: kedja_om 14 processorminuter för 48 utgåvor, persistens 2): de fyra efterkedjevarianterna kostar kedjan plus lite (TakMangd och TakUtjamningFast under en sekund extra per utgåva, TakTillvaxt och TakUtjamningBast några sekunder: 20 box- eller 7·20 gaussfilter och FSS på 4 km), alltså 14 till 18 processorminuter vardera; TakRorelse 14 plus Lucas-Kanade (skattat 5 till 15 processorminuter). Totalt ungefär 75 till 90 processorminuter, med två processer 40 till 50 minuters väntan. Minne: framtida bilder cachas (`Ctx.frames` rensas bara före t − 2 h), så upp till ~85 bilder på 4 km per process, skattat 300 till 600 MB per process, alltså under 2 GB med två. Mät maxminnet (`/usr/bin/time -v`) vid provkörningen av TakRorelse. Ingen ny data skrivs utöver summorna (en liten `.npz` per dygn och system, några MB totalt) och loggen under `/data/projektion/`; ingenting i repot.

**Tabellen.** `domare.py tabell` skriver över den incheckade `experiments/projektion/resultat/snabb.md`; kör den därför inte, eller återställ filen efteråt (`git checkout experiments/projektion/resultat/snabb.md`). Använd i stället:

```
cd experiments/projektion
python - <<'EOF' > /data/projektion/tak_snabb_tabell.md
import numpy as np, domare as D
days = D.mode_days("snabb")
ref = D.load("snabb", "kedja_om", days)
days = [d for d in days if ref[d]["issues"] > 0]
rows = ["csi1", "csi5", "fss1_30", "fss5_10", "blockmax_q90"]
for s in ["tak_TakRorelse", "tak_TakMangd", "tak_TakTillvaxt", "tak_TakUtjamningFast", "tak_TakUtjamningBast"]:
    sd = D.load("snabb", s, days)
    c = D.compare(sd, ref, days, nboot=1000)
    print(f"\n## {s}\n\n| mått | " + " | ".join(f"{D.LEADS[D.LEADS.index(k)]*15} min" for k in D.SHOW) + " |\n|---|" + "---|"*len(D.SHOW))
    for k in rows:
        r, cells = c[k], []
        for l in D.SHOW:
            i = D.LEADS.index(l)
            d, lo, hi = r["diff"][i], r["lo"][i], r["hi"][i]
            if r["kind"] in ("träff", "spärr+"):      # domaren: baslinje minus system; vänd så att + är bättre
                d, lo, hi = -d, -hi, -lo
            cells.append(f"{r['system'][i]:+.3f} ({d:+.3f} [{lo:+.3f}, {hi:+.3f}])")
        print(f"| {k} | " + " | ".join(cells) + " |")
EOF
```

Tabellen ska se ut så, en per variant, ledtiderna 15, 30, 60, 120, 180 och 300 min (domarens `SHOW`):

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | värde (skillnad mot kedja_om [lo, hi]) | | | | | |
| csi5 | | | | | | |
| fss1_30 | | | | | | |
| fss5_10 | | | | | | |
| blockmax_q90 | (log kvot mot radarn, och skillnaden i \|log kvot\|, negativ är bättre) | | | | | |

För csi och fss är skillnaden systemet minus kedja_om (positiv är bättre) med 95 %-intervall från bootstrap över de sex dygnen (domarens `compare`, fast frö). För blockmax_q90 är skillnaden \|log kvot\| för systemet minus kedja_om (negativ är bättre), som domaren redovisar den. Tillägg som tabellen bör ha: kedja_om:s egna värden (`snabb.md`) och `persistens` som jämförelse, samt skillnaden mot kedja_om i procent av luckan till perfekt (CSI 1) för att se vilken del som har mest att ge.

**Avvikelse från uppgiften:** "FSS 1 mm vid 10 och 40 km" finns inte i domaren. `FSS_CASES` är (1 mm/h, 30 km), (5, 10), (5, 30), (10, 10), (10, 30), och summorna har bara de fallen. Jag tar `fss1_30` (1 mm/h) och `fss5_10` som närmaste. Vill man ha exakt 1 mm/h vid 10 och 40 km måste `FSS_CASES` utökas i `domare.py` (det ändrar summornas form, så baslinjerna måste köras om) eller fås fram i en egen körning; jag rörde inte domaren. Det är en fråga till användaren om det är värt det.

## Det jag är osäker på

I fallande ordning av hur troligt det är att det är fel (alla ställen står i `tak.py`):

1. `hindsight_motion`: Lucas-Kanade på 21 bilder (var 15:e minut över 5 h). Jag utgår från att pysteps tar bilderna parvis i följd och ger förflyttning per bildsteg (så att `/ motion_gap` stämmer, som i `Ctx.motion`), men har inte provat det på så lång serie. Risker: långsam, för få vektorer sent i serien (regnet har ändrat sig, så tätningen domineras av de första paren), eller att `dense_motion` får tom `xy` (då blir fältet noll, och det är fel nedåt, inte uppåt). Kontrollera körtiden per utgåva och farten i fältet mot `ctx.motion(t)`.
2. `facit()` och `ctx.quarter` över dygnsgränsen: för utgåvor sent på dygnet pekar `t + k·15 min` in i nästa dygn. `radar_path` ska ge rätt fil oavsett dygn och finns arkivet inte blir kvarten NaN, som domaren också hoppar över, men jag har inte sett `radar_path`. Syns det att `TakMangd` inte får volym 1 för de sena kvartarna är det därför.
3. Att `ctx.frames` växer med framtida bilder (minne, se körplanen). `ctx.forget` städar bara bakåt.
4. `block_ratio`: valen `eps = 0,02`, tak 4 och utjämningen sigma = block/4 är mina egna. Fönstret är `round(32 / res) | 1`, alltså 9 pixlar (36 km) på 4 km och 17 (34 km) på 2 km. `D._box` är domarens privata hjälpfunktion; byter den namn går modulen sönder.
5. `TakUtjamningBast`: fönstret för kriteriet blir `round(10/4) | 1 = 3` pixlar (12 km) på 4 km. Valet per utgåva och kvart ger ett övre tak som utnyttjar bruset; jämför med `TakUtjamningFast` för att se hur mycket som är bruset. Kriteriet (FSS 1 mm/h) gynnar jämna fält och straffar toppar; blockmax_q90 visar kostnaden. Sigman skrivs till loggen: ligger valen alltid i änden av listan (0 eller 24) är listan fel.
6. `from domare import ...` som `D` när domaren körs som skript: modulen laddas då en andra gång under namnet `domare`. `somlos.py` gör likadant, så det bör gå, men `D.KedjaOm` är då inte samma klass som `__main__.KedjaOm` (inget i domaren kontrollerar det utom `isinstance(system, Kedja)`, som inte gäller här).
7. Kodningen: domaren kör `render.encode_values`/`decode_values` på alla system utom `Kedja`. `TakMangd` får därför inte exakt volym 1.
8. Siffrorna i körtidsskattningen (särskilt TakRorelse och minnet) är gissningar ur `snabb.md`.
9. `kedja_om` i läge `snabb` finns antagligen redan (tabellen `snabb.md` bygger på den), men jag har inte kunnat lista katalogen.

Förväntade kontrollvärden vid provkörningen: `TakUtjamningFast` ska vara identisk med `kedja_om` vid 15, 30 och 60 min (sigma 0); `TakMangd` ska ha volymkvot nära 1; `TakTillvaxt` ska ha volym nära 1 men inte exakt; `TakRorelse` ska vara minst lika bra som `kedja_om` vid 15 min (annars är rörelsen fel skattad). Avviker något av det är det kod, inte resultat.

## Filer

- `experiments/projektion/tak.py` (ny, inte körd)
- `experiments/bakgrund/rapporter/2026-11-08/0016-tak-skrivbord.md` (den här)

Inget annat ändrat, ingen testfil, ingen data.

## Nästa steg

Nästa session med Bash: kör provkörningarna ovan (en dag, TakMangd och TakRorelse), åtgärda fel i `tak.py`, kör de sex dagarna i `snabb`, bygg tabellen med skriptet ovan och skriv rangordningen: vilken del av kedjan har mest att ge (CSI 1 och 5 mm per ledtid). Fråga användaren om FSS 1 mm vid 10 och 40 km ska läggas till i `FSS_CASES`. Start från A2T (del 2) görs efteråt med ett annat facit.

Kort: `tak.py` med fem fuskvarianter (rörelse, mängd, tillväxt, fast och bästa utjämning) och en körplan är skrivna och genomlästa mot domaren men inte körda; inga siffror finns, och FSS 1 mm vid 10 och 40 km finns inte i domaren (närmaste är `fss1_30`, `fss5_10`).
Säkerställd förbättring: nej
Status: klar
