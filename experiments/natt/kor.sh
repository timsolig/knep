#!/usr/bin/env bash
# Bakgrundskörningen: Claude Code tar uppgifterna i ko.txt en i taget, var och en i en egen session,
# i ett eget arbetsträd på grenen natt/<datum>. Se experiments/natt/README.md.
#
#   experiments/natt/kor.sh                kör till 07:00 svensk tid
#   experiments/natt/kor.sh --till 05:30   sluta starta nya uppgifter 05:30
#   experiments/natt/kor.sh --timmar 8     sluta starta nya uppgifter om åtta timmar
#   experiments/natt/kor.sh --fran 3       börja med uppgift 3
#
# ko.txt: nr|kort namn|högst minuter|uppgift. Den sista uppgiften får alltid RESERV sekunder före --till.
#   experiments/natt/kor.sh --prov         bara ett kort prov av behörigheterna
#
# Stoppa efter pågående uppgift: touch ~/natt/STOPP. Stoppa direkt: pkill -INT -f experiments/natt/kor.sh.
set -uo pipefail

TILL=07:00
FRAN=1
PROV=0
while [ $# -gt 0 ]; do
  case $1 in
    --till) TILL=$2; shift 2 ;;
    --timmar) TILL=$(TZ=Europe/Stockholm date -d "+$2 hours" +%H:%M); shift 2 ;;
    --fran) FRAN=$2; shift 2 ;;
    --prov) PROV=1; shift ;;
    *) echo "okänt argument: $1" >&2; exit 2 ;;
  esac
done

KALLA=$(cd "$(dirname "$0")/../.." && pwd)          # utcheckningen som skriptet ligger i, normalt ~/knep
NATT=${NATT_DIR:-$HOME/natt}                         # arbetsträdet för natten, utanför /work
UPPGIFT_MAX=${UPPGIFT_MAX:-10800}                    # sekunder per uppgift, högst
VANTA_GRANS=${VANTA_GRANS:-1200}                     # sekunder att vänta när användningsgränsen är nådd
RESERV=${RESERV:-2700}                               # sekunder som hålls undan till den sista uppgiften i kön
DATUM=$(TZ=Europe/Stockholm date +%F)
GREN=${NATT_GREN:-natt/$DATUM}

exec 9>"$HOME/.natt.lock"
flock -n 9 || { echo "en bakgrundskörning pågår redan" >&2; exit 1; }
# uppdraget och experimenten använder sökvägarna från utvecklingscontainern; på Pi:n är de symlänkar
for d in /data /work; do
  [ -d "$d/" ] || { echo "$d saknas: se experiments/natt/README.md (sudo ln -s ...)" >&2; exit 1; }
done

# slutet som sekunder sedan epoken, svensk tid; ligger klockslaget redan bakom oss gäller det i morgon
slut=$(TZ=Europe/Stockholm date -d "$TILL" +%s)
[ "$slut" -le "$(date +%s)" ] && slut=$(TZ=Europe/Stockholm date -d "tomorrow $TILL" +%s)

logg() { echo "$(TZ=Europe/Stockholm date '+%F %H:%M:%S') $*" | tee -a "$NATT/natt.log" >&2; }

# arbetsträdet: samma commit som skriptet, egen gren
if [ ! -d "$NATT/.git" ] && [ ! -f "$NATT/.git" ]; then
  git -C "$KALLA" worktree prune
  if git -C "$KALLA" show-ref -q "refs/heads/$GREN"; then
    git -C "$KALLA" worktree add -q "$NATT" "$GREN" || exit 1
  else
    git -C "$KALLA" worktree add -q -b "$GREN" "$NATT" HEAD || exit 1
  fi
fi
cd "$NATT" || exit 1
[ "$(git branch --show-current)" = "$GREN" ] || { echo "$NATT står inte på $GREN; flytta eller ta bort arbetsträdet" >&2; exit 1; }
RAPPORTER=experiments/natt/rapporter/$DATUM
mkdir -p "$RAPPORTER/logg"
rm -f STOPP
logg "start: gren $GREN i $NATT, slutar starta nya uppgifter $(TZ=Europe/Stockholm date -d "@$slut" '+%a %H:%M')"
uv sync -q || { logg "uv sync misslyckades"; exit 1; }

# Ingen kan pusha härifrån: ingen inloggning för gh och en push-adress som inte finns.
# Driften följer main på GitHub, så det här är den viktigaste spärren.
export GH_CONFIG_DIR=$(mktemp -d) GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false
unset GH_TOKEN GITHUB_TOKEN
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=remote.origin.pushurl GIT_CONFIG_VALUE_0=ingen-push://avstangt-i-bakgrunden \
       GIT_CONFIG_KEY_1=credential.helper GIT_CONFIG_VALUE_1=
export GIT_AUTHOR_NAME="Claude (bakgrund)" GIT_AUTHOR_EMAIL=noreply@anthropic.com
export GIT_COMMITTER_NAME="Claude (bakgrund)" GIT_COMMITTER_EMAIL=noreply@anthropic.com

claude_kor() {  # $1 prompt, $2 loggfil, $3 sekunder
  timeout --signal=INT --kill-after=60 "$3" nice -n 15 ionice -c3 \
    claude -p "$1" -n "bakgrund $DATUM" \
      --permission-mode dontAsk --permission-prompts none \
      --settings "$NATT/experiments/natt/settings.json" \
      --add-dir /data \
      --output-format text </dev/null >>"$2" 2>&1
}

if [ "$PROV" = 1 ]; then
  f=$RAPPORTER/logg/prov.txt
  claude_kor "Det här är ett prov av bakgrundskörningens behörigheter, gör exakt detta och inget annat:
1. Kör: uv run python -c \"import knep, sys; print('python ok', sys.version.split()[0])\"
2. Kör: df -h /data
3. Försök köra: git push (det ska nekas; försök inte på något annat sätt).
4. Försök skapa filen deploy/prov.txt med texten prov (det ska nekas).
5. Skriv filen $RAPPORTER/prov.md med en rad per steg: vad som hände.
Svara sedan med en kort sammanfattning." "$f" 600
  logg "provet klart (kod $?), se $NATT/$f och $NATT/$RAPPORTER/prov.md"
  cat "$f"
  exit 0
fi

klar() { [ -f "$1" ] && grep -qiE '^Status: *klar' "$1"; }
SIST=$(grep -vE '^(#|$)' experiments/natt/ko.txt | tail -n 1 | cut -d'|' -f1)

while IFS='|' read -r nr namn minuter uppgift; do
  case $nr in ''|\#*) continue ;; esac
  [ "$nr" -lt "$FRAN" ] && continue
  rapport=$RAPPORTER/$nr-$namn.md
  if klar "$rapport"; then logg "uppgift $nr ($namn) är redan klar"; continue; fi
  forsok=0
  while true; do
    [ -f STOPP ] && { logg "STOPP hittad, slutar"; exit 0; }
    kvar=$(( slut - $(date +%s) ))
    [ "$kvar" -lt 900 ] && { logg "mindre än 15 min kvar till $TILL, startar inget nytt"; exit 0; }
    # de andra uppgifterna lämnar RESERV åt den sista, så att den alltid hinner
    [ "$nr" != "$SIST" ] && kvar=$(( kvar - RESERV ))
    [ "$kvar" -lt 900 ] && { logg "uppgift $nr ($namn): för lite tid kvar före reserven, går vidare"; break; }
    max=$(( ${minuter:-0} > 0 ? minuter * 60 : UPPGIFT_MAX ))
    tid=$(( kvar < max ? kvar : max ))
    forsok=$((forsok + 1))
    f=$RAPPORTER/logg/$nr-$namn.txt
    logg "uppgift $nr ($namn), försök $forsok, högst $((tid / 60)) min"
    prompt="$(cat experiments/natt/uppdrag.md)

---
I natt är datumet $DATUM, och rapporterna ligger i $RAPPORTER/. Du står i $NATT på grenen $GREN.
Din uppgift är nummer $nr ($namn):

$uppgift

Skriv rapporten till $rapport, med raden Status: sist. Du har högst $((tid / 60)) minuter; lämna tid att skriva rapporten och committa."
    [ "$forsok" -gt 1 ] && prompt="$prompt

Det här är försök $forsok. Läs $f och det som redan är gjort, och fortsätt därifrån."
    echo "===== $(date -u +%FT%TZ) försök $forsok =====" >>"$f"
    claude_kor "$prompt" "$f" "$tid"
    rc=$?
    # det som inte hann committas tas med, så att inget går förlorat
    if [ -n "$(git status --porcelain)" ]; then
      git add -A && git commit -q -m "Natt $DATUM: uppgift $nr ($namn), det som inte var committat när sessionen slutade" && logg "committade kvarvarande ändringar"
    fi
    if klar "$rapport"; then logg "uppgift $nr klar"; break; fi
    if tail -n 30 "$f" | grep -qiE 'usage limit|rate limit|limit reached|overloaded|529'; then
      logg "användningsgränsen eller överbelastning, väntar $((VANTA_GRANS / 60)) min"
      sleep "$VANTA_GRANS"
      continue
    fi
    if [ "$rc" = 124 ]; then logg "uppgift $nr nådde tidsgränsen"; break; fi
    if [ "$forsok" -ge 2 ]; then logg "uppgift $nr klarades inte på två försök (kod $rc), går vidare"; break; fi
    logg "uppgift $nr slutade utan Status: klar (kod $rc), försöker igen"
  done
done < experiments/natt/ko.txt
logg "kön är slut"
