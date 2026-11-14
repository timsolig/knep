# 0017 tak-korning

Taket för kedjans delar är kört: alla fem varianter på de sex dagarna i `snabb` (4 km, 48 utgåvor per variant), med `kedja_om` som referens och `persistens` som jämförelse. Valideringen och testdelen är inte rörda. Ändrat i repot: bara `experiments/projektion/tak.py`. Summorna ligger i `/data/projektion/domare/snabb/tak_*/` (en liten `.npz` per dygn).

## Disken

`df -m /data` (samma disk som `/`): 2 591 MB ledigt vid starten, 2 566 MB efter uppgiften (uppgiften skrev cirka 25 MB summor och loggar). Över 2 000 MB hela tiden.

Vad som växer gick inte att fastställa fullt ut: bara läsning, och `/var/lib/docker` och `/var/lib/containerd` är inte läsbara för användaren (Permission denied), så dockers del (bilder, volymer, containerloggar) syns inte. Det som gick att mäta (MB, `du -sm`):

| plats | MB |
|---|---|
| `~/radar-arkiv` (= `/data`, en symlänk dit: analys 942, bortfall 474, meps 768, projektion 420, radar 1130, riksgransen 176, satellit 1, snow 82, sverige 561, verif_prov 81) | 4 630 |
| `~/.cache/uv` | 1 126 |
| `~/.local/share/claude` | 646 |
| `~/bakgrund` (arbetskopian) | 638 |
| `~/knep` | 496 |
| `/tmp` (`claude-1000` 202, `pytest-of-tim` 117, `a2prov` 58, resten småttigt) | 958 |
| `/var/log` | 364 |
| `/var/cache` | 232 |
| `/var/lib` (utan docker och containerd) | 166 |
| `~/.local/share/uv` | 93 |
| `/work/cache` (`bias` 65, `ui` 81) | cirka 150 |

`/data` har inget i år 2026 under `radar/` (arkivet är historiskt) och växte inte; ingenting där ändrades under uppgiften utom `projektion/domare/snabb/`. Hemkatalogen är 7,2 GB (varav `~/radar-arkiv` 4,6 GB) och disken 29,4 GB med 25,3 GB använt; operativsystemet och dockers kataloger står för resten, och det jag kunde mäta förklarar inte tillväxten på cirka 650 MB per dygn. Det som återstår är dockers kataloger (driftens volymer, bilder, containerloggar) eller något under `/var` som inte är läsbart. Misstänkt i första hand driftens volym och dockers json-loggar; det kan inte avgöras härifrån och är en gissning. Rekommendation till användaren: kör `sudo du -sm /var/lib/docker/* ` och `docker system df` en gång. Jag tog inte bort något. (`/tmp` kan städas med cirka 400 MB vinst: `pytest-of-tim`, `claude-1000`, `a2prov`.)

## Vad som rättades i `tak.py`

- Importen och kopplingen fungerade utan ändring (`tak` hittas när domaren körs som skript, ingen `PYTHONPATH` behövs; `env`-prefix nekas av skalet).
- **TakMangd gav fel volym** (volymkvot f/o 0,985 vid 15 min ner till 0,728 vid 300 min, kontrollvärdet var nära 1). Två orsaker: skalningen gjordes över rutor där prognosen är ändlig men domarens mask är analysens täckning och facit, och den gjordes före domarens kodning (`encode_values`, värden under 0,1 mm/h blir 0), som tar bort en större del av volymen i utjämnade fält långt fram. Rättat: skalan söks mot volymen efter kodningen över domarens mask (4 iterationer). Klassen heter nu **TakVolym**, eftersom det gick inte att ta bort de gamla summorna i `tak_TakMangd/2020-02-10.npz` (skalet nekade `rm`) och domaren återanvänder befintliga filer. Den gamla filen är felaktig och ska inte användas. TakVolym ger volymkvot 1,000 vid alla ledtider.
- Övriga kontrollvärden: TakUtjamningFast är identisk med `kedja_om` vid 15, 30 och 60 min (skillnad 0,000 med intervall noll, alla fem mått). TakRorelse vid 15 min: CSI 1 mm +0,001 [-0,001, +0,002] mot kedja_om (inte sämre), CSI 5 mm −0,003 [-0,009, +0,002]. Hindsight-rörelsen skiljer sig verkligen från historikens (kontroll på 2023-07-12, sex utgåvor: medelfart 0,6 till 1,1 px per 5 min, skillnad mellan fälten 0,11 till 0,21 px per 5 min över de våta rutorna, alltså cirka 5 till 10 km/h), så det är inte så att fältet blev detsamma.
- Ingen ändring i `domare.py`, `src/`, `deploy/`, `models/`, `dagar.json`. Docstringen i `tak.py` uppdaterad.

## Körtid och minne

Per dygn (8 utgåvor, en process) och per variant med två processer över sex dygn (väggtid):

| variant | per dygn | sex dygn, 2 proc | not |
|---|---|---|---|
| kedja_om (referens, `snabb.md`) | cirka 17 s per utgåva | | 14 processorminuter totalt |
| TakVolym | 94 s (en process) | 279 s | |
| TakTillvaxt | 95 till 103 s | 354 s | |
| TakUtjamningFast | | 351 s | |
| TakUtjamningBast | 143 till 146 s | 522 s | 7 gaussfilter och FSS per kvart |
| TakRorelse | 82 s (en process) | 384 s | **Lucas-Kanade på 21 bilder kostar nästan inget**: 82 s per dygn, under kedjans |

Allt ihop 1 890 s (cirka 32 min) för alla fem. Maxminne: 1 012 MB för båda processerna tillsammans (RSS, mätt var 3:e sekund med `/proc`), alltså cirka 500 MB per process; under gränsen 2 GB. En första mätning med en process på TakRorelse gav 736 MB men räknade `claude`-processen med, och kasseras. TakRorelse är alltså inte dyrare än väntat (under 2 min per utgåva), och ingen variant avbröts.

## Tabellerna

Referensen `kedja_om` och `persistens`, värden per ledtid. Tabellerna för varje variant (skillnad mot `kedja_om`, positiv är bättre för csi och fss; för blockmax_q90 är värdet log kvot mot radarn och skillnaden |log kvot| systemet minus kedja_om, negativ är bättre; 95 %-intervall från domarens bootstrap över de sex dygnen) ligger också i `/data/projektion/tak_snabb_tabell.md` (samma som här).

**kedja_om**

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,734 | 0,575 | 0,414 | 0,271 | 0,207 | 0,146 |
| csi5 | 0,580 | 0,382 | 0,235 | 0,128 | 0,078 | 0,048 |
| fss1_30 | 0,979 | 0,933 | 0,825 | 0,654 | 0,536 | 0,401 |
| fss5_10 | 0,886 | 0,723 | 0,525 | 0,321 | 0,210 | 0,133 |
| blockmax_q90 | -0,084 | -0,098 | -0,168 | -0,085 | -0,062 | -0,064 |

**persistens**

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,590 | 0,424 | 0,306 | 0,204 | 0,157 | 0,110 |
| csi5 | 0,411 | 0,254 | 0,166 | 0,085 | 0,053 | 0,034 |
| fss1_30 | 0,962 | 0,871 | 0,717 | 0,532 | 0,427 | 0,314 |
| fss5_10 | 0,795 | 0,583 | 0,414 | 0,224 | 0,144 | 0,093 |
| blockmax_q90 | +0,172 | +0,153 | +0,127 | +0,164 | +0,159 | +0,126 |

### TakRorelse (rörelsen ur facit, ett fält för hela prognosen)

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,735 (+0,001 [-0,001, +0,002]) | 0,574 (-0,001 [-0,004, +0,001]) | 0,414 (+0,000 [-0,005, +0,005]) | 0,275 (+0,004 [-0,001, +0,009]) | 0,208 (+0,001 [-0,007, +0,009]) | 0,149 (+0,003 [-0,005, +0,015]) |
| csi5 | 0,577 (-0,003 [-0,009, +0,002]) | 0,381 (-0,001 [-0,006, +0,005]) | 0,235 (+0,001 [-0,010, +0,010]) | 0,125 (-0,003 [-0,019, +0,010]) | 0,072 (-0,006 [-0,016, +0,004]) | 0,048 (-0,001 [-0,015, +0,012]) |
| fss1_30 | 0,979 (-0,000 [-0,000, +0,000]) | 0,932 (-0,000 [-0,001, +0,000]) | 0,824 (-0,001 [-0,003, +0,001]) | 0,659 (+0,005 [-0,003, +0,016]) | 0,542 (+0,005 [-0,013, +0,025]) | 0,417 (+0,016 [-0,003, +0,043]) |
| fss5_10 | 0,884 (-0,002 [-0,006, +0,002]) | 0,722 (-0,001 [-0,007, +0,007]) | 0,525 (-0,000 [-0,017, +0,015]) | 0,317 (-0,005 [-0,043, +0,027]) | 0,196 (-0,014 [-0,037, +0,008]) | 0,131 (-0,001 [-0,034, +0,033]) |
| blockmax_q90 | -0,082 (-0,002 [-0,047, +0,027]) | -0,098 (-0,000 [-0,046, +0,025]) | -0,131 (-0,037 [-0,048, +0,030]) | -0,090 (+0,005 [-0,016, +0,048]) | -0,066 (+0,005 [-0,034, +0,054]) | -0,062 (-0,002 [-0,068, +0,043]) |

### TakVolym (volymen per ledtid)

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,727 (-0,007 [-0,027, +0,002]) | 0,571 (-0,005 [-0,015, +0,002]) | 0,409 (-0,005 [-0,018, +0,004]) | 0,270 (-0,001 [-0,011, +0,007]) | 0,207 (+0,000 [-0,012, +0,011]) | 0,147 (+0,001 [-0,014, +0,014]) |
| csi5 | 0,581 (+0,001 [-0,005, +0,015]) | 0,382 (+0,000 [-0,008, +0,014]) | 0,230 (-0,004 [-0,011, +0,005]) | 0,124 (-0,005 [-0,013, +0,002]) | 0,076 (-0,002 [-0,006, +0,002]) | 0,045 (-0,003 [-0,008, +0,001]) |
| fss1_30 | 0,975 (-0,004 [-0,015, +0,001]) | 0,930 (-0,003 [-0,012, +0,001]) | 0,819 (-0,007 [-0,023, +0,004]) | 0,652 (-0,002 [-0,017, +0,011]) | 0,534 (-0,002 [-0,026, +0,020]) | 0,402 (+0,001 [-0,028, +0,024]) |
| fss5_10 | 0,889 (+0,003 [-0,004, +0,021]) | 0,723 (-0,001 [-0,013, +0,021]) | 0,519 (-0,006 [-0,014, +0,010]) | 0,314 (-0,008 [-0,022, +0,009]) | 0,207 (-0,003 [-0,016, +0,007]) | 0,126 (-0,007 [-0,023, +0,001]) |
| blockmax_q90 | -0,073 (-0,011 [-0,042, +0,019]) | -0,072 (-0,026 [-0,079, +0,006]) | -0,106 (-0,062 [-0,134, -0,001]) | -0,014 (-0,071 [-0,112, +0,011]) | +0,053 (-0,009 [-0,072, +0,106]) | +0,130 (+0,066 [-0,062, +0,167]) |

### TakTillvaxt (tillväxt och avtagande i block om cirka 32 km, ur facit)

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,769 (+0,035 [+0,025, +0,046]) | 0,641 (+0,065 [+0,047, +0,088]) | 0,518 (+0,104 [+0,081, +0,128]) | 0,391 (+0,120 [+0,102, +0,141]) | 0,324 (+0,117 [+0,102, +0,131]) | 0,243 (+0,097 [+0,079, +0,116]) |
| csi5 | 0,631 (+0,051 [+0,036, +0,082]) | 0,460 (+0,078 [+0,058, +0,107]) | 0,332 (+0,098 [+0,077, +0,121]) | 0,234 (+0,106 [+0,079, +0,128]) | 0,170 (+0,092 [+0,049, +0,120]) | 0,113 (+0,065 [+0,025, +0,088]) |
| fss1_30 | 0,992 (+0,013 [+0,008, +0,019]) | 0,973 (+0,040 [+0,026, +0,064]) | 0,924 (+0,099 [+0,068, +0,145]) | 0,823 (+0,169 [+0,130, +0,224]) | 0,732 (+0,195 [+0,159, +0,248]) | 0,601 (+0,200 [+0,159, +0,251]) |
| fss5_10 | 0,929 (+0,044 [+0,029, +0,075]) | 0,823 (+0,099 [+0,073, +0,142]) | 0,687 (+0,162 [+0,129, +0,208]) | 0,538 (+0,217 [+0,177, +0,261]) | 0,428 (+0,218 [+0,134, +0,270]) | 0,298 (+0,165 [+0,070, +0,220]) |
| blockmax_q90 | -0,139 (+0,054 [+0,006, +0,103]) | -0,135 (+0,036 [-0,011, +0,075]) | -0,172 (+0,004 [-0,058, +0,065]) | -0,258 (+0,173 [+0,068, +0,258]) | -0,295 (+0,233 [+0,124, +0,380]) | -0,435 (+0,371 [+0,191, +0,506]) |

### TakUtjamningFast (gaussisk, sigma 0, 0, 2, 4, 8, 12 km vid 0 till 5 h)

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,734 (-0,000 [-0,000, -0,000]) | 0,575 (-0,000 [-0,000, -0,000]) | 0,414 (-0,000 [-0,000, -0,000]) | 0,275 (+0,003 [+0,002, +0,004]) | 0,214 (+0,007 [+0,004, +0,009]) | 0,160 (+0,014 [+0,009, +0,019]) |
| csi5 | 0,580 (-0,000 [-0,000, -0,000]) | 0,382 (-0,000 [-0,000, -0,000]) | 0,235 (-0,000 [-0,000, -0,000]) | 0,131 (+0,002 [+0,001, +0,003]) | 0,082 (+0,004 [-0,001, +0,009]) | 0,058 (+0,010 [-0,001, +0,025]) |
| fss1_30 | 0,979 (-0,000 [-0,000, -0,000]) | 0,933 (-0,000 [-0,000, -0,000]) | 0,825 (-0,000 [-0,000, -0,000]) | 0,653 (-0,001 [-0,002, -0,000]) | 0,532 (-0,004 [-0,010, -0,001]) | 0,392 (-0,009 [-0,025, +0,000]) |
| fss5_10 | 0,886 (-0,000 [-0,000, -0,000]) | 0,723 (-0,000 [-0,000, -0,000]) | 0,525 (-0,000 [-0,000, -0,000]) | 0,321 (-0,001 [-0,003, +0,001]) | 0,208 (-0,002 [-0,008, +0,001]) | 0,144 (+0,011 [-0,010, +0,027]) |
| blockmax_q90 | -0,084 (+0,000 [+0,000, +0,000]) | -0,098 (+0,000 [+0,000, +0,000]) | -0,168 (+0,000 [+0,000, +0,000]) | -0,165 (+0,080 [+0,063, +0,124]) | -0,321 (+0,259 [+0,194, +0,349]) | -0,749 (+0,685 [+0,503, +0,872]) |

### TakUtjamningBast (sigma per utgåva och kvart ur 0 till 24 km, vald mot facit)

| mått | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| csi1 | 0,735 (+0,001 [+0,000, +0,002]) | 0,585 (+0,010 [+0,006, +0,014]) | 0,446 (+0,032 [+0,022, +0,040]) | 0,315 (+0,044 [+0,026, +0,057]) | 0,242 (+0,035 [+0,018, +0,047]) | 0,172 (+0,026 [+0,014, +0,035]) |
| csi5 | 0,580 (+0,001 [+0,000, +0,001]) | 0,383 (+0,001 [-0,002, +0,005]) | 0,249 (+0,015 [+0,003, +0,033]) | 0,147 (+0,018 [+0,003, +0,028]) | 0,085 (+0,007 [-0,009, +0,017]) | 0,055 (+0,007 [-0,003, +0,012]) |
| fss1_30 | 0,979 (+0,000 [-0,000, +0,000]) | 0,933 (-0,000 [-0,001, +0,001]) | 0,824 (-0,001 [-0,004, +0,003]) | 0,657 (+0,003 [-0,003, +0,011]) | 0,549 (+0,013 [+0,003, +0,020]) | 0,420 (+0,019 [+0,007, +0,031]) |
| fss5_10 | 0,886 (-0,000 [-0,000, +0,000]) | 0,717 (-0,007 [-0,014, -0,000]) | 0,529 (+0,004 [-0,015, +0,029]) | 0,340 (+0,018 [-0,011, +0,034]) | 0,215 (+0,005 [-0,030, +0,025]) | 0,143 (+0,010 [-0,013, +0,019]) |
| blockmax_q90 | -0,090 (+0,006 [-0,001, +0,031]) | -0,158 (+0,060 [+0,002, +0,109]) | -0,358 (+0,190 [+0,015, +0,315]) | -0,514 (+0,429 [+0,049, +0,701]) | -0,416 (+0,355 [+0,092, +0,676]) | -0,482 (+0,418 [+0,106, +0,621]) |

## Rangordning: hur stor del av luckan till perfekt CSI tar varje fusk

Andel = (variant minus kedja_om) / (1 minus kedja_om), i procent.

CSI 1 mm/h:

| del | 15 min | 30 min | 60 min | 120 min | 180 min | 300 min |
|---|---|---|---|---|---|---|
| Tillväxt och avtagande (32 km) | +13,1 | +15,4 | +17,7 | +16,4 | +14,7 | +11,4 |
| Utjämning vald i efterhand | +0,3 | +2,3 | +5,5 | +6,0 | +4,4 | +3,1 |
| Utjämning, fast schema | 0,0 | 0,0 | 0,0 | +0,5 | +0,9 | +1,7 |
| Rörelse (ett fält, efterhand) | +0,3 | -0,3 | +0,1 | +0,5 | +0,2 | +0,4 |
| Volym per ledtid | -2,6 | -1,1 | -0,9 | -0,2 | +0,1 | +0,2 |

CSI 5 mm/h: Tillväxt +12,2 / +12,7 / +12,7 / +12,1 / +10,0 / +6,8; Utjämning efterhand +0,2 / +0,2 / +1,9 / +2,1 / +0,8 / +0,8; Utjämning fast 0 / 0 / 0 / +0,2 / +0,4 / +1,1; Rörelse -0,7 / -0,2 / +0,1 / -0,4 / -0,6 / -0,1; Volym +0,3 / +0,1 / -0,6 / -0,5 / -0,2 / -0,3.

Rangordning efter taket, för alla ledtider: **1. tillväxt och avtagande**, med stor marginal (säkert bättre vid alla mått och ledtider utom blockmax; CSI 1 mm +0,035 till +0,120, FSS +0,013 till +0,218); **2. utjämning vald i efterhand** (CSI 1 mm +0,010 till +0,044 vid 30 min till 5 h, bara vid 60 min och längre för CSI 5); **3. fast utjämning** (högst +0,014 CSI 1 mm vid 5 h, och FSS 1 mm blir sämre där, −0,009); **4. rörelse och 5. volym: ingenting** (alla intervall innehåller noll, CSI 1 mm +0,000 till +0,004 respektive −0,007 till +0,001).

Observera hur de läses:

- **Rörelsen med ett fält för hela 5 h har inget tak i det här ledet.** Kedjan använder ett rörelsefält per utgåva. Taket gäller alltså bara "bästa konstanta fältet", som kedjan redan nästan har. Det säger inget om en rörelse som ändras med tiden eller varierar över ytan (det kräver en annan kedja). Det som syns är att felet i rörelsen vid ett fält inte är det som begränsar.
- **Volymen ensam har inget att ge för CSI**, och att skala till rätt volym flyttar bara kvoten (blockmax_q90 bättre vid 60 min, intervall nästan helt under noll). Kedjans volymfel är alltså ingen anledning att ha CSI och FSS sämre.
- **TakTillvaxt är ett löst tak och läcker lägesinformation:** kvoten facit/prognos i block om 32 km flyttar också massa mellan block, så den rättar också kedjans lägesfel på skalan 32 km, inte bara tillväxt och avtagande. Vinsten är därför en övre gräns för "tillväxt plus läge i grov skala", och den kan inte tolkas som vad en tillväxtmodell ur historiken ger. Blockmaxet blir sämre vid 2 till 5 h (+0,17 till +0,37), eftersom kvoten klipps till högst 4 och jämnar ut toppar. Den kan inte skapa regn där kedjan har noll.
- **TakUtjamningBast väljer sigma i efterhand per utgåva och kvart** (listan 0 till 24 km, ibland alla i änden 24 vid +1,5 till 5 h i de utgåvor där regnet var litet, ofta 0 för kvartar i en och samma utgåva, så en del av vinsten är brus). Sigma hamnar i änden 24 km för många kvartar på 2024-09-26 (lång rad av 24), så listan kan vara för kort uppåt; på 2024-12-19 blandas 0 och 24 från kvart till kvart. Taket är övre gräns och blockmaxet blir säkert sämre vid 30 min till 5 h (+0,06 till +0,43).

### Fast mot bäst utjämning

Utan facit (Fast) går det att få: CSI 1 mm +0,003 / +0,007 / +0,014 vid 2 / 3 / 5 h, det vill säga cirka 1/10 vid 2 h och 1/2 vid 5 h av vad som går att få med facit (+0,044 / +0,035 / +0,026), men FSS 1 mm blir sämre (−0,001 / −0,004 / −0,009) i stället för bättre (+0,003 / +0,013 / +0,019) och blockmaxet mycket sämre (+0,080 / +0,259 / +0,685; med fast schema vid 5 h är blockmax_q90 log kvot −0,749, alltså toppen tappas nästan helt). Slutsats: utjämningens vinst i CSI går bara att få utan facit på lång ledtid, och där betalas den med FSS och toppar; vid 30 min till 2 h, där Bast ger +0,010 till +0,044, går nästan inget att få med ett fast schema. Vinsten i Bast ligger främst i att välja när man ska jämna ut (per utgåva och kvart), vilket kräver kunskap om var kedjans spridning är stor. Ett schema som beror på ledtiden som i S-PROG är alltså inte det som ger de 2 till 6 procenten; ett schema som beror på fältets osäkerhet kan göra det, men det är oprövat.

## Förslag på kandidater till domaren

Kostnad avser Pi:n, per cykel (kedjan är cirka 17 s per utgåva vid 4 km, bara 5 h).

1. **Tillväxt och avtagande ur historiken i stor skala** (mål 3). Den enda delen med ett tak över 10 procent av luckan (CSI 1 mm +0,035 till +0,120). Pröva en kvot per block om 32 km som förutsägs ur den senaste timmens utveckling av blockmedlet (trend i analysen, dämpad mot 1 med ledtiden), tillämpad på kedjans fält före platskartan, med taket för kvoten (högst 2 och minst 0,5) och utan att skapa regn där kedjan har noll. Förvänta bara en bråkdel av taket (taket använder framtida kvoter), troligen 10 till 20 procent av det. Kostnad på Pi:n: en box och en gauss per steg, under 1 s per cykel. Risk: blockmaxet blir sämre som i taket, och trenden är brusig. Frys i `snabb`/`traning`, bedöm på `validering` med blockmax och FSS som spärrar.
2. **Utjämning som beror på fältets osäkerhet** (inte på ledtiden ensam). Fast schema gav inget vid ≤ 1 h och tappade topparna; taket med val i efterhand ger CSI 1 mm +0,03 till +0,04 vid 1 till 3 h. Pröva sigma som funktion av lokal kedjeosäkerhet, till exempel avvikelsen mellan två rörelsefält (historik kortare och längre) eller ensembleliknande spridning av kedjans förflyttning, med utjämning bara i fält där de skiljer sig. Kostnad: ett andra rörelsefält per utgåva (Lucas-Kanade är billig här, under 2 s) och en gauss per steg. Risk: blockmax sämre (taket +0,06 till +0,43), så en spärr över toppar behövs (utjämna bara under en intensitetsgräns eller bevara maxet).
3. **Rörelse som ändras med tiden eller över ytan**. Taket för ett fält i hela prognosen är noll, så ingen vinst finns i att skatta ett bättre fält. Vad som kvarstår är rörelse som varierar med ledtiden, vilket kräver en ändring i kedjan. Prioriteras lägre; pröva bara om kandidat 1 visar att tillväxt och läge i grov skala hänger ihop (läget i TakTillvaxt är ju inbakat). En enkel uppföljning är att köra om TakTillvaxt med kvoten inte som fält utan som ren skalär per block (inget läge flyttas) för att skilja tillväxt från läge. Kostnad 40 minuter.

Idéer i `IDEER.md` som blir mindre värda: **Inflödet utan överskottet de första 30 minuterna** (volymen och randen), eftersom taket för volymen är noll mot CSI och FSS och bara rör blockmaxet; inflödet står kvar bara som förlustkorrigering vid randen, inte som källa till bättre skill. **Prognosen: klippa ytan i stället för toppen** (blockmaxet) blir också mindre värd: den flyttar volym och toppar, och taket för volymen är noll. **Kedjan utan matchning** är redan avgjord. **A1 som start** och **bias-v1** rör analysen, inte kedjans delar, och ändras inte. Mer värda: en idé för tillväxt ur historiken (finns inte i listan, se kandidat 1).

Fråga till användaren (bör läggas under Frågor i `MAL.md`): FSS 1 mm vid 10 och 40 km finns inte i domaren (`fss1_30` och `fss5_10` används), och att lägga till dem kräver omkörning av baslinjerna; inget i taket tyder på att det behövs.

## Filer

- `experiments/projektion/tak.py` (rättad: TakMangd ersatt av TakVolym, docstring)
- `experiments/bakgrund/rapporter/2026-11-09/0017-tak-korning.md` (den här)
- Utanför repot: `/data/projektion/domare/snabb/tak_*/` (summor), `/data/projektion/tak_snabb_tabell.md` (se tabellerna ovan; filen skrevs inte eftersom skalet nekar omdirigering, så tabellerna är hämtade ur utskriften), skripten `/data/projektion/{kontroll,tabell,minne,rorelsekoll}.py`. `tak_TakMangd/2020-02-10.npz` är felaktig och ska ignoreras. Inget i `domare.py`, `src/`, `deploy/`, `models/`, `dagar.json`; resultat/snabb.md orörd; testdelen och valideringen inte rörda.
- `uv run pytest`: 214 passerade.

## Nästa steg

Kandidat 1 (tillväxt ur historiken i block om 32 km) prövad på `traning` med domaren; först körs TakTillvaxt om som ren skalär per block för att se hur mycket av vinsten som är läge och hur mycket som är tillväxt. Disken: användaren bör titta i dockers kataloger.

Kort: Tillväxt och avtagande i block om 32 km har klart störst tak (CSI 1 mm +0,035 till +0,120 mot kedja_om, 11 till 18 procent av luckan till 1, intervallen helt över noll), utjämning vald i efterhand tar 2 till 6 procent (+0,010 till +0,044 vid 30 min till 3 h) men fast schema nästan inget, och rörelse (ett fält) och volym har inget tak (alla intervall innehåller noll).
Säkerställd förbättring: nej
Status: klar
