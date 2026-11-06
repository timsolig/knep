# Bakgrundskörningen

Claude Code arbetar igenom `ko.txt` utan att någon svarar på frågor, när som helst på dygnet. Varje uppgift är en egen session (`claude -p`) som läser `uppdrag.md`, gör uppgiften, skriver en rapport och committar. Allt sker i ett eget arbetsträd, `~/natt`, på grenen `natt/<datum>`. Utvecklingsklonen i `~/knep` och driften påverkas inte. (Katalogen och grenarna heter fortfarande `natt`.)

## En gång: sökvägarna

Experimenten och uppdraget använder `/work` för repot och `/data` för arkivet, som i den gamla utvecklingscontainern. På Pi:n är det symlänkar:

```sh
sudo ln -s ~/knep /work
sudo ln -s ~/radar-arkiv /data
```

## Starta

På Pi:n, från en utcheckning av den commit som körningen ska utgå från:

```sh
cd ~/knep
experiments/natt/kor.sh --prov                                  # valfritt: en minut, provar behörigheterna
setsid nohup experiments/natt/kor.sh --timmar 8 >/dev/null 2>&1 &   # åtta timmar från nu
```

`--till 07:00` slutar i stället vid ett klockslag (svensk tid). Körningen fortsätter när terminalen stängs. Startas Pi:n om, kör samma kommando igen: uppgifter med `Status: klar` i sin rapport hoppas över.

## Titta på den

```sh
experiments/natt/status.sh         # vad som pågår, rapporterna och commitarna
tail -f ~/natt/natt.log
```

Loggen för varje uppgift: `~/natt/experiments/natt/rapporter/<datum>/logg/`.

## Stoppa

- Efter pågående uppgift: `touch ~/natt/STOPP`
- Direkt: `pkill -INT -f experiments/natt/kor.sh` och sedan `pkill -INT -f "claude -p"`

## Efteråt

1. `experiments/natt/status.sh`, och läs `~/natt/experiments/natt/rapporter/<datum>/sammanfattning.md`.
2. Grenen `natt/<datum>` finns i `~/knep` också (arbetsträdet delar repot): `git log main..natt/<datum>`.
3. Vill du ta in något: kör testdelen själv med kommandona i sammanfattningen, och öppna en PR från grenen. Körningen pushar aldrig.
4. Ta bort arbetsträdet när du är klar: `git worktree remove ~/natt`. Grenen finns kvar.

## Skydden

- Sessionen kan inte pusha: `kor.sh` ger den en tom konfiguration för `gh` (din egen inloggning rörs inte), stänger av git:s inloggningar och sätter en push-adress som inte finns, och `settings.json` nekar `git push`, `gh` och `docker`. Det är viktigt eftersom driften följer `main` på GitHub.
- `settings.json` tillåter bara det som behövs, och `--permission-mode dontAsk --permission-prompts none` nekar allt annat utan att fråga, så att ingenting kan fastna på en fråga.
- Allt körs med `nice` och `ionice`, och uppdraget säger högst två processer och 2 GB minne, så att driften blir klar med sina cykler.
- Testdelen i `experiments/sverige/dagar.json` är spärrad. Den kör du själv.
- Nås användningsgränsen för Claude väntar skriptet 20 min och försöker igen. Den sista uppgiften startas senast 15 min före slutet.

## Ändra körningen

Uppgifterna står i `ko.txt` (en per rad) och reglerna i `uppdrag.md`. Ändra dem på en gren, ta in dem via PR, och starta från `main`. Ett arbetsträd som redan finns från samma datum uppdateras inte. Ta bort det först med `git worktree remove ~/natt`, eller kör med `NATT_GREN=natt/<datum>-2 NATT_DIR=~/natt2`.
