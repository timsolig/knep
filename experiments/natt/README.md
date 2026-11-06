# Nattkörningen

Claude Code arbetar igenom `ko.txt` under natten. Varje uppgift är en egen session (`claude -p`) som läser `uppdrag.md`, gör uppgiften, skriver en rapport och committar. Allt sker i ett eget arbetsträd, `~/natt`, på grenen `natt/<datum>`. Utvecklingsklonen i `/work` och driften påverkas inte.

## Starta

Från datorn, logga in på Pi:n och gå in i containern:

```sh
ssh pi                        # eller hur du nu når Pi:n
docker exec -it knep-dev bash
```

I containern, en gång per natt:

```sh
cd /work
git switch natt-forberedelse   # tills experiments/natt är mergad; sedan main
experiments/natt/kor.sh --prov          # valfritt: en minut, provar behörigheterna
tmux new -d -s natt 'experiments/natt/kor.sh --till 07:00'
```

Nu kör natten i tmux i containern. Du kan stänga terminalen, logga ut från Pi:n och stänga av datorn. Containern körs på Pi:n med `restart: unless-stopped`, så det enda som stoppar natten är att Pi:n eller containern startas om.

Startas den om, kör samma kommando igen. Uppgifter med `Status: klar` i sin rapport hoppas över.

## Titta på den

```sh
docker exec -it knep-dev bash
experiments/natt/status.sh         # vad som pågår, rapporterna och commitarna
tmux attach -t natt                # titta direkt; lämna med Ctrl-b och sedan d
tail -f ~/natt/natt.log
```

Loggen för varje uppgift: `~/natt/experiments/natt/rapporter/<datum>/logg/`.

## Stoppa

- Efter pågående uppgift: `touch ~/natt/STOPP`
- Direkt: `tmux kill-session -t natt`

## På morgonen

1. `experiments/natt/status.sh`, och läs `~/natt/experiments/natt/rapporter/<datum>/sammanfattning.md`.
2. Grenen `natt/<datum>` finns i `/work` också (arbetsträdet delar repot): `git log main..natt/<datum>`.
3. Vill du ta in något: kör testdelen själv med kommandona i sammanfattningen, och öppna en PR från grenen. Natten pushar aldrig.
4. Ta bort arbetsträdet när du är klar: `git worktree remove ~/natt`. Grenen finns kvar.

## Skydden

- Nattsessionen kan inte pusha: `kor.sh` tar bort inloggningen för `gh`, stänger av git:s inloggningar och sätter en push-adress som inte finns. Det är viktigt eftersom driften följer `main` på GitHub.
- `settings.json` tillåter bara det som behövs, och `--permission-mode dontAsk --permission-prompts none` nekar allt annat utan att fråga, så att ingenting kan fastna på en fråga.
- Allt körs med `nice` och `ionice`, och uppdraget säger högst två processer och 2 GB minne, så att driften blir klar med sina cykler.
- Testdelen i `experiments/sverige/dagar.json` är spärrad. Den kör du själv.
- Nås användningsgränsen för Claude väntar skriptet 20 min och försöker igen. Den sista uppgiften startas senast 15 min före `--till`.

## Ändra natten

Uppgifterna står i `ko.txt` (en per rad) och reglerna i `uppdrag.md`. Ändra dem i `/work`, committa, och starta. Ett arbetsträd som redan finns från samma datum uppdateras inte. Ta bort det först med `git worktree remove ~/natt`, eller kör med `NATT_GREN=natt/<datum>-2 NATT_DIR=~/natt2`.
