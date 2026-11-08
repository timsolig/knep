# Bakgrunden

Claude Code arbetar i knep på natten, utan att någon svarar på frågor. Nya varv startar bara 22 till 07 svensk tid (inte under sista timmen), högst tre uppgifter per natt, högst 150 min per uppgift, och uppgifterna körs med Sonnet medan planeraren kör standardmodellen, så att användningen dagtid räcker till användaren (`FONSTER_START`, `FONSTER_SLUT`, `MAX_PER_NATT`, `UPPGIFT_MAX_MIN`, `UPPGIFT_MODELL` i `loop.sh`). Natten räknas i `~/.bakgrund/varv.txt`. Den väljer själv vad som ska göras härnäst utifrån målen och det som redan är gjort, och lämnar resultatet som en PR. Den ersätter den fasta kön i `experiments/natt/`.

## Ett varv

1. **Planeringen** (högst 20 min): en session läser `MAL.md`, `IDEER.md`, journalen och de senaste rapporterna. Den bedömer den senaste uppgiften, prioriterar om och skriver nästa uppgift till `nasta.md`.
2. **Uppgiften** (högst 4 h): en ny session gör uppgiften enligt `uppdrag.md` och skriver en rapport under `rapporter/<datum>/<nr>-<namn>.md`, med en rad `Kort:` och sist `Status:`.
3. **Journalen och PR:en**: loopen lägger en post i `JOURNAL.md`, kontrollerar grenen, pushar den och öppnar eller uppdaterar PR:en mot `main`.

Allt sker i arbetsträdet `~/bakgrund` på grenen `bakgrund/<start>`. När PR:en slås ihop eller stängs börjar loopen en ny gren från `main`. Loopen slår aldrig ihop något själv.

## Filerna

| Fil | Vem ändrar den |
|---|---|
| `MAL.md` | Principerna: bara användaren. Prioriteringarna: planeraren, med motivering under Ändringar. |
| `IDEER.md` | Planeraren, och vem som helst som har en idé. |
| `JOURNAL.md` | Loopen. |
| `uppdrag.md`, `loop.sh`, `settings.json` | Bara via en PR från användaren eller en interaktiv session. Loopen installerar en ny version från `origin/main` mellan två varv och startar om. |

Vill du styra om: ändra `MAL.md` eller `IDEER.md` på grenen eller i `main`.

## Installera

En gång, från en utcheckning av `main`:

```sh
experiments/bakgrund/installera.sh
sudo loginctl enable-linger $USER     # om skriptet säger det, så att tjänsten går utan inloggning
```

Det installerar `loop.sh`, `settings.json` och `uppdrag.md` i `~/.local/share/knep-bakgrund/` och tjänsten `knep-bakgrund` (systemd för användaren). Kör en bakgrundskörning från `experiments/natt/` väntar loopen tills den är klar.

Det som inte ska stå i det publika repot läggs bara på Pi:n:

- `~/.bakgrund/lokala-spärrar.txt`: extra regler för sessionernas `deny`, en per rad.
- `~/.bakgrund/lokala-ord.txt`: ord som aldrig får förekomma i det som pushas, en per rad.
- `~/.bakgrund/ta-in`: grenar som ska tas in en gång när nästa gren börjar.

## Titta på den

```sh
experiments/bakgrund/status.sh
tail -f ~/.bakgrund/logg.txt
journalctl --user -u knep-bakgrund -f
```

Sessionernas utdata ligger i `~/.bakgrund/logg/` på Pi:n och pushas inte.

## Pausa och stoppa

- Paus efter pågående steg: `touch ~/.bakgrund/STOPP`. Fortsätt: `rm ~/.bakgrund/STOPP`.
- Stopp direkt: `systemctl --user stop knep-bakgrund`. Start: `systemctl --user start knep-bakgrund`.
- Hittar spärren något som inte får pushas skriver den orsaken i `~/.bakgrund/SPARR` och pausar. Rätta grenen och ta bort filen.

## Skydden

- Sessionerna kan inte pusha: ingen inloggning för `gh` eller git, ingen ssh och en push-adress som inte finns, och `settings.json` nekar `git push`, `gh`, `docker` och `systemctl`. Bara loopen pushar, och bara grenen `bakgrund/...`.
- Före varje push stoppar spärren grenen om den ändrar `deploy/`, `models/`, `.github/`, de frysta dagarna eller bakgrundens egna regler, om den innehåller EUMETSAT-nyckeln eller ett lokalt spärrat ord, eller om den lägger till en fil över 5 MB.
- Allt körs med `nice` och `ionice`, och uppdraget säger högst två processer och 2 GB minne, så att driften blir klar med sina cykler.
- Nås användningsgränsen för Claude väntar loopen 20 min och försöker igen. Dör uppgifterna direkt flera gånger i rad väntar den allt längre, upp till 4 h.
