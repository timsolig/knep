#!/usr/bin/env bash
# Bakgrunden: Claude Code arbetar i knep på natten (FONSTER_START till FONSTER_SLUT), ett varv i taget.
#   1. Planeraren läser MAL.md, JOURNAL.md, IDEER.md och de senaste rapporterna, prioriterar om och skriver nasta.md.
#   2. Uppgiften körs i en egen session och skriver en rapport.
#   3. Loopen skriver posten i JOURNAL.md, pushar grenen bakgrund/<start> och håller en PR mot main öppen.
# Körs som tjänsten knep-bakgrund (systemd --user), se experiments/bakgrund/README.md.
#
# Paus efter pågående steg: touch ~/.bakgrund/STOPP (ta bort filen för att fortsätta).
# Stopp direkt: systemctl --user stop knep-bakgrund.
set -uo pipefail

REPO=${BAKGRUND_REPO:-$HOME/knep}          # huvudklonen; arbetsträdet delar dess .git
TRAD=${BAKGRUND_DIR:-$HOME/bakgrund}       # arbetsträdet där sessionerna arbetar
STATE=${BAKGRUND_STATE:-$HOME/.bakgrund}   # läget: logg, STOPP, SPARR, grenen, sessionernas loggar
INST=$(cd "$(dirname "$0")" && pwd)        # installerade kopior av loop.sh, settings.json och uppdrag.md
PLAN_MIN=${PLAN_MIN:-20}                   # minuter för planeringen
MAX_MIN=${UPPGIFT_MAX_MIN:-150}            # högsta tid för en uppgift
FONSTER_START=${FONSTER_START:-22}         # nya varv startar bara från den här timmen (svensk tid) ...
FONSTER_SLUT=${FONSTER_SLUT:-7}            # ... till den här, så att användningen dagtid räcker till användaren
FONSTER_MARGINAL=${FONSTER_MARGINAL:-60}   # minuter före fönstrets slut då inget nytt varv startar
MAX_PER_NATT=${MAX_PER_NATT:-3}            # högst så många uppgifter per natt
UPPGIFT_MODELL=${UPPGIFT_MODELL:-sonnet}   # modellen för uppgifterna; planeraren kör standardmodellen
VANTA_GRANS=${VANTA_GRANS:-1200}           # sekunder att vänta när användningsgränsen är nådd
B=experiments/bakgrund
TRAILER="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
mkdir -p "$STATE/logg"

nu() { TZ=Europe/Stockholm date '+%F %H:%M'; }
logg() { echo "$(TZ=Europe/Stockholm date '+%F %H:%M:%S') $*" | tee -a "$STATE/logg.txt" >&2; }
G() { git -C "$TRAD" -c user.name="Claude (bakgrund)" -c user.email=noreply@anthropic.com "$@"; }
gh_i() { (cd "$TRAD" && gh "$@"); }

exec 9>"$STATE/las"
flock -n 9 || { logg "en annan loop kör redan"; sleep 600; exit 1; }

# den gamla bakgrundskörningen (experiments/natt) får bli klar först
vantat=0
while [ "${BAKGRUND_VANTA_NATT:-1}" = 1 ] && { pgrep -f 'experiments/natt/kor.sh|natt-andra-delen/andra-delen.sh' >/dev/null || ! flock -n "$HOME/.natt.lock" true 2>/dev/null; }; do
  [ $vantat = 0 ] && logg "väntar på att den gamla bakgrundskörningen (experiments/natt) blir klar"
  vantat=1; sleep 300
done

for d in /data /work; do
  [ -d "$d/" ] || { logg "$d saknas, se experiments/natt/README.md"; sleep 3600; exit 1; }
done

# Sessionerna kan inte pusha: tom konfiguration för gh, inga inloggningar för git, ingen ssh och en push-adress som
# inte finns. Det är bara loopen själv som pushar, efter spärrarna i sparr().
TOM_GH=$(mktemp -d)
trap 'rm -rf "$TOM_GH"' EXIT
claude_kor() {  # $1 prompt, $2 loggfil, $3 sekunder, $4 modell (tomt: standard)
  ( cd "$TRAD" && env -u GH_TOKEN -u GITHUB_TOKEN -u SSH_AUTH_SOCK \
      GH_CONFIG_DIR="$TOM_GH" GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false GIT_SSH_COMMAND=/bin/false \
      GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=remote.origin.pushurl GIT_CONFIG_VALUE_0=ingen-push://avstangt-i-bakgrunden \
      GIT_CONFIG_KEY_1=credential.helper GIT_CONFIG_VALUE_1= \
      GIT_AUTHOR_NAME="Claude (bakgrund)" GIT_AUTHOR_EMAIL=noreply@anthropic.com \
      GIT_COMMITTER_NAME="Claude (bakgrund)" GIT_COMMITTER_EMAIL=noreply@anthropic.com \
      timeout --signal=INT --kill-after=60 "$3" nice -n 15 ionice -c3 \
      claude -p "$1" -n "bakgrund $(nu)" ${4:+--model "$4"} \
        --permission-mode dontAsk --permission-prompts none \
        --settings "$STATE/settings.json" --add-dir /data \
        --output-format text </dev/null >>"$2" 2>&1 )
}
# Sessionernas behörigheter: settings.json från repot plus lokala spärrar som inte ska stå i det publika repot
# (~/.bakgrund/lokala-spärrar.txt, en regel per rad, till exempel Read(~/knep/<katalog>/**)).
bygg_settings() {
  python3 - "$INST/settings.json" "$STATE/lokala-spärrar.txt" "$STATE/settings.json" <<'PY' || { logg "settings gick inte att bygga"; exit 1; }
import json, sys, pathlib
s = json.load(open(sys.argv[1]))
p = pathlib.Path(sys.argv[2])
if p.exists():
    s["permissions"]["deny"] += [r.strip() for r in p.read_text().splitlines() if r.strip() and not r.startswith("#")]
json.dump(s, open(sys.argv[3], "w"), indent=2, ensure_ascii=False)
PY
}
bygg_settings

gransen() { tail -n 30 "$1" 2>/dev/null | grep -qiE 'usage limit|rate limit|limit reached|overloaded|529'; }

commit_rester() {
  [ -n "$(G status --porcelain)" ] || return 0
  G add -A && G commit -q -m "Bakgrunden: $1, det som inte var committat när sessionen slutade" -m "$TRAILER" \
    && logg "committade kvarvarande ändringar ($1)"
}

nasta_nr() {
  local n
  n=$(grep -oE '^### [0-9]{4}' "$TRAD/$B/JOURNAL.md" 2>/dev/null | awk '{print $2+0}' | sort -n | tail -n 1)
  printf '%04d\n' $(( ${n:-0} + 1 ))
}

# En ny version av loop.sh, settings.json eller uppdrag.md på main installeras mellan två varv, och tjänsten startar om.
uppdatera() {
  git -C "$REPO" fetch -q origin 2>/dev/null || return 0
  local f andrat=0
  for f in loop.sh settings.json uppdrag.md; do
    git -C "$REPO" show "origin/main:$B/$f" > "$INST/.$f.ny" 2>/dev/null || { rm -f "$INST/.$f.ny"; continue; }
    if cmp -s "$INST/.$f.ny" "$INST/$f"; then rm -f "$INST/.$f.ny"; else mv "$INST/.$f.ny" "$INST/$f"; andrat=1; fi
  done
  if [ $andrat = 1 ]; then chmod +x "$INST/loop.sh"; logg "ny version från main installerad, startar om"; exit 0; fi
}

ny_gren() {  # $1 den gamla grenen, $2 hur dess PR slutade (MERGED, CLOSED eller tomt)
  local gammal=${1:-} hur=${2:-} namn g
  git -C "$REPO" fetch -q origin || { logg "fetch misslyckades"; return 1; }
  namn=bakgrund/$(TZ=Europe/Stockholm date +%F-%H%M)
  if [ ! -e "$TRAD/.git" ]; then
    git -C "$REPO" worktree prune
    git -C "$REPO" worktree add -q -b "$namn" "$TRAD" origin/main || return 1
  else
    commit_rester "före ny gren"
    G switch -q -c "$namn" origin/main || return 1
  fi
  if [ "$hur" = MERGED ]; then
    # det som hann committas efter att PR:en slogs ihop följer med
    G merge -q --no-edit "$gammal" || { G merge --abort; logg "resterna från $gammal gick inte att ta in"; }
  elif [ -n "$gammal" ]; then
    # PR:en stängdes utan att slås ihop: arbetet lämnas, men journalen, målen och idéerna följer med
    G checkout "$gammal" -- "$B/JOURNAL.md" "$B/MAL.md" "$B/IDEER.md" 2>/dev/null \
      && G commit -q -m "Bakgrunden: journalen, målen och idéerna från $gammal, vars PR stängdes" -m "$TRAILER"
  fi
  if [ -f "$STATE/ta-in" ]; then  # grenar som ska tas in en gång, till exempel en gammal bakgrundskörning
    while read -r g; do
      [ -n "$g" ] || continue
      if G merge -q --no-edit "$g"; then logg "tog in $g"; else G merge --abort; logg "kunde inte ta in $g"; fi
    done < "$STATE/ta-in"
    rm -f "$STATE/ta-in"
  fi
  echo "$namn" > "$STATE/gren"
  nasta_nr > "$STATE/gren-start"
  logg "ny gren $namn"
}

sakra_gren() {
  local gren hur
  gren=$(cat "$STATE/gren" 2>/dev/null)
  if [ -z "$gren" ] || [ ! -e "$TRAD/.git" ]; then ny_gren "" ""; return; fi
  [ "$(G branch --show-current)" = "$gren" ] || { logg "$TRAD står inte på $gren"; return 1; }
  hur=$(gh_i pr view "$gren" --json state -q .state 2>/dev/null)
  case $hur in
    MERGED|CLOSED) logg "PR:en för $gren är $hur"; ny_gren "$gren" "$hur" ;;
  esac
}

# Ingenting pushas som rör driften, reglerna eller hemligheter, som innehåller ett lokalt spärrat ord, eller som är stort. Då pausas loopen.
sparr() {
  local fel="" forb f
  G fetch -q origin 2>/dev/null
  forb=$(G diff --name-only origin/main...HEAD | grep -E '^(deploy/|models/|\.github/|experiments/sverige/dagar\.json$|experiments/bakgrund/(loop\.sh|settings\.json|uppdrag\.md|installera\.sh|status\.sh|knep-bakgrund\.service)$)')
  [ -n "$forb" ] && fel+="ändrar spärrade filer: $(echo $forb)"$'\n'
  # ord som aldrig får förekomma i det som läggs till, en per rad, bara på Pi:n (se README.md)
  if [ -s "$STATE/lokala-ord.txt" ] \
     && G diff origin/main...HEAD -U0 | grep -E '^\+' | grep -v '^+++' | grep -qiF -f <(grep -v '^$' "$STATE/lokala-ord.txt"); then
    fel+="innehåller ett ord från ~/.bakgrund/lokala-ord.txt"$'\n'
  fi
  if [ -s "$HOME/.config/eumetsat/credentials" ] \
     && G diff origin/main...HEAD | grep -qF -f <(grep -v '^$' "$HOME/.config/eumetsat/credentials"); then
    fel+="innehåller EUMETSAT-nyckeln"$'\n'
  fi
  while read -r f; do
    [ -f "$TRAD/$f" ] && [ "$(stat -c %s "$TRAD/$f")" -gt 5000000 ] && fel+="stor fil: $f"$'\n'
  done < <(G diff --name-only --diff-filter=AM origin/main...HEAD)
  [ -z "$fel" ] && return 0
  printf '%s' "$fel" > "$STATE/SPARR"
  logg "spärren: grenen pushas inte och loopen pausas tills ~/.bakgrund/SPARR tas bort: $(tr '\n' ' ' < "$STATE/SPARR")"
  return 1
}

pr_text() {
  local start gren repo
  start=$(cat "$STATE/gren-start" 2>/dev/null || echo 0001)
  gren=$(cat "$STATE/gren")
  repo=$(gh_i repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
  echo "Bakgrunden arbetar på den här grenen och uppdaterar PR:en efter varje uppgift. Den slår aldrig ihop den själv."
  echo "Målen och prioriteringarna: [MAL.md](https://github.com/$repo/blob/$gren/$B/MAL.md). Hela journalen: [JOURNAL.md](https://github.com/$repo/blob/$gren/$B/JOURNAL.md)."
  echo
  echo "## Uppgifter på grenen"
  echo
  awk -v s=$((10#$start)) '/^### [0-9][0-9][0-9][0-9]/{p=($2+0>=s)} /^## /{p=0} p' "$TRAD/$B/JOURNAL.md" \
    | sed "s#](rapporter/#](https://github.com/$repo/blob/$gren/$B/rapporter/#g" | head -c 60000
  echo
  echo "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
}

pusha() {
  local gren
  gren=$(cat "$STATE/gren")
  sparr || return 1
  G push -q -u origin "$gren" 2>>"$STATE/logg.txt" || { logg "push misslyckades"; return 1; }
  local nr
  nr=$(gh_i pr view "$gren" --json number,state -q 'select(.state=="OPEN").number' 2>/dev/null)
  if [ -n "$nr" ]; then
    # Via REST: gh pr edit fäller på GitHubs nedlagda Projects (classic) och uppdaterar ingenting.
    gh_i api -X PATCH "repos/{owner}/{repo}/pulls/$nr" -f body="$(pr_text)" >/dev/null 2>>"$STATE/logg.txt" \
      || logg "kunde inte uppdatera PR:en"
  else
    gh_i pr create --base main --head "$gren" --title "Bakgrunden: ${gren#bakgrund/}" --body "$(pr_text)" \
      >>"$STATE/logg.txt" 2>&1 && logg "öppnade en PR för $gren"
  fi
}

planprompt() {  # $1 PR:ens adress eller tomt
  cat "$INST/uppdrag.md"
  cat <<EOF

---
Du är **planeraren**. Klockan är $(nu). Du står i $TRAD på grenen $(cat "$STATE/gren")${1:+, och PR:en är $1}.
Du har högst $PLAN_MIN minuter. Kör inga långa beräkningar; läs, tänk och skriv.

1. Läs $B/MAL.md, $B/IDEER.md, de senaste posterna i $B/JOURNAL.md och rapporterna för de senaste uppgifterna (länkarna står i journalen).
2. Bedöm den senaste uppgiften: vad betyder resultatet för målen? Uppdatera $B/IDEER.md: stryk det som är avgjort (med en rad om utfallet), lägg till nya idéer med förväntad nytta, kostnad och risk, och ordna om efter vad som ger mest nu.
3. Prioritera om i $B/MAL.md om resultaten säger att något annat är viktigare nu. Ändra ordningen under Prioriteringar, lägg till eller ta bort mål, och skriv varför med datum under Ändringar. Avsnittet Principer ändrar du aldrig. Behövs ett beslut av användaren (till exempel ett släpp i drift, ny data som kostar, eller något som strider mot principerna), skriv frågan under Frågor till användaren och välj något annat att göra så länge.
4. Välj den uppgift som ger mest för målen nu och som går att göra klart och bedöma på högst $MAX_MIN minuter. Fortsätt hellre en halvfärdig uppgift än börja något nytt. Upprepa inte något som journalen visar redan är prövat, om du inte har ett nytt skäl.
5. Skriv $B/nasta.md i exakt det här formatet, och committa inte den filen:

namn: <kort namn, bara a-z, 0-9 och bindestreck>
minuter: <ett heltal, högst $MAX_MIN>
varför: <en mening om varför det här är nästa steg>
---
<uppgiften, skriven till en annan session som inte har sett något av det här: vad som ska göras, vilka filer och rapporter den bygger på, vilken domare och vilka dagar som bedömer, vad som räknas som klart och vad som ska stå i rapporten>

6. Committa $B/MAL.md och $B/IDEER.md om du ändrade dem.
EOF
}

uppgiftsprompt() {  # $1 försök
  cat "$INST/uppdrag.md"
  cat <<EOF

---
Du gör en **uppgift**. Klockan är $(nu). Du står i $TRAD på grenen $(cat "$STATE/gren").
Målen står i $B/MAL.md och journalen över tidigare uppgifter i $B/JOURNAL.md. Läs rapporterna som uppgiften bygger på innan du börjar.
Din uppgift är nummer $NR ($NAMN):

$UPPGIFT

Skriv rapporten till $RAPPORT. Den ska ha en rad som börjar med \`Kort:\` med resultatet i en mening (med siffrorna mot baslinjen om det finns några), och sist en rad som börjar med \`Status:\` och sedan \`klar\`, \`delvis\` eller \`misslyckad\`.
Du har högst $KVAR_MIN minuter; lämna tid att skriva rapporten och committa.
EOF
  [ "$1" -gt 1 ] && echo "
Det här är försök $1. Läs $RAPPORT om den finns, git log och det som redan är gjort, och fortsätt därifrån."
}

planera() {  # 0 om nasta.md finns och går att läsa; 2 om användningsgränsen var nådd
  local f n pr
  f="$STATE/logg/$(TZ=Europe/Stockholm date +%F)-planering.txt"
  n="$TRAD/$B/nasta.md"
  rm -f "$n"
  pr=$(gh_i pr view "$(cat "$STATE/gren")" --json url,state -q 'select(.state=="OPEN").url' 2>/dev/null)
  echo "===== $(date -u +%FT%TZ) planering =====" >>"$f"
  logg "planerar"
  claude_kor "$(planprompt "$pr")" "$f" $((PLAN_MIN * 60))
  commit_rester "planeringen"
  [ -f "$n" ] || { gransen "$f" && return 2; return 1; }
  NAMN=$(sed -n 's/^namn: *//p' "$n" | head -n 1 | tr -cd 'a-z0-9-' | cut -c1-40)
  MIN=$(sed -n 's/^minuter: *//p' "$n" | head -n 1 | tr -cd '0-9')
  VARFOR=$(sed -n 's/^varför: *//p' "$n" | head -n 1)
  UPPGIFT=$(sed '1,/^---$/d' "$n")
  NR=$(nasta_nr)
  cp "$n" "$STATE/logg/$NR-nasta.md"
  rm -f "$n"
  commit_rester "planeringen"
  [ -n "$NAMN" ] && [ -n "$MIN" ] && [ -n "$UPPGIFT" ] || return 1
  MIN=$((10#$MIN)); [ "$MIN" -gt "$MAX_MIN" ] && MIN=$MAX_MIN; [ "$MIN" -lt 15 ] && MIN=15
  logg "nästa: $NR $NAMN, högst $MIN min: $VARFOR"
  return 0
}

kor_uppgift() {
  local f forsok=0 slut
  DATUM=$(TZ=Europe/Stockholm date +%F)
  RAPPORT=$B/rapporter/$DATUM/$NR-$NAMN.md
  mkdir -p "$TRAD/$B/rapporter/$DATUM"
  f="$STATE/logg/$NR-$NAMN.txt"
  START=$(date +%s)
  slut=$((START + MIN * 60))
  while [ $forsok -lt 6 ]; do
    forsok=$((forsok + 1))
    KVAR_MIN=$(( (slut - $(date +%s)) / 60 ))
    [ "$KVAR_MIN" -lt 10 ] && break
    echo "===== $(date -u +%FT%TZ) försök $forsok =====" >>"$f"
    logg "uppgift $NR ($NAMN), försök $forsok, högst $KVAR_MIN min"
    claude_kor "$(uppgiftsprompt $forsok)" "$f" $((KVAR_MIN * 60)) "$UPPGIFT_MODELL"
    commit_rester "uppgift $NR ($NAMN)"
    grep -qiE '^Status:' "$TRAD/$RAPPORT" 2>/dev/null && break
    if gransen "$f"; then
      logg "användningsgränsen, väntar $((VANTA_GRANS / 60)) min"
      sleep "$VANTA_GRANS"; slut=$((slut + VANTA_GRANS)); continue
    fi
    break
  done
}

journal() {
  local j="$TRAD/$B/JOURNAL.md" status kort min rel post
  rel=${RAPPORT#$B/}
  if [ -f "$TRAD/$RAPPORT" ]; then
    status=$(grep -m1 -iE '^Status:' "$TRAD/$RAPPORT" | sed -E 's/^[Ss]tatus: *//; s/[*`]//g')
    kort=$(grep -m1 -E '^\**Kort:' "$TRAD/$RAPPORT" | sed -E 's/^\**Kort:\** *//')
  else
    status=misslyckad
    kort="ingen rapport skrevs (loggen på Pi:n: ~/.bakgrund/logg/$NR-$NAMN.txt)"
  fi
  STATUS=${status:-okänd}
  min=$(( ($(date +%s) - START) / 60 ))
  post="### $NR · $(nu) · $NAMN · $STATUS
- Varför: ${VARFOR:-}
- Resultat: ${kort:-(rapporten har ingen rad Kort:)}
- Rapport: [$rel]($rel), $min min"
  [ -f "$TRAD/$RAPPORT" ] || post="${post%%- Rapport:*}- Rapport: ingen, $min min"
  printf '%s\n' "$post" > "$STATE/post.md"
  if grep -q '<!-- nya poster här -->' "$j"; then
    awk -v f="$STATE/post.md" '{print} /<!-- nya poster här -->/ && !d {print ""; while ((getline l < f) > 0) print l; d=1}' "$j" > "$j.ny" && mv "$j.ny" "$j"
  else
    { echo; cat "$STATE/post.md"; } >> "$j"
  fi
  G add "$B/JOURNAL.md" && G commit -q -m "Bakgrunden: journalen för uppgift $NR ($NAMN), $STATUS" -m "$TRAILER"
  logg "uppgift $NR ($NAMN): $STATUS, $min min"
}

# Fönstret: nya varv bara på natten och högst MAX_PER_NATT per natt. En natt räknas från FONSTER_START;
# timmarna efter midnatt hör till natten som började dagen innan.
natt_nyckel() {
  local h; h=$((10#$(TZ=Europe/Stockholm date +%H)))
  if [ "$h" -lt "$FONSTER_SLUT" ]; then TZ=Europe/Stockholm date -d yesterday +%F; else TZ=Europe/Stockholm date +%F; fi
}
i_fonstret() {  # sant om ett nytt varv får starta nu
  local h m kvar
  h=$((10#$(TZ=Europe/Stockholm date +%H))); m=$((10#$(TZ=Europe/Stockholm date +%M)))
  if [ "$FONSTER_START" -gt "$FONSTER_SLUT" ]; then
    { [ "$h" -ge "$FONSTER_START" ] || [ "$h" -lt "$FONSTER_SLUT" ]; } || return 1
  else
    { [ "$h" -ge "$FONSTER_START" ] && [ "$h" -lt "$FONSTER_SLUT" ]; } || return 1
  fi
  kvar=$(( ((FONSTER_SLUT * 60 - (h * 60 + m)) % 1440 + 1440) % 1440 ))
  [ "$kvar" -ge "$FONSTER_MARGINAL" ]
}
varv_i_natt() { touch "$STATE/varv.txt"; awk -v k="$(natt_nyckel)" '$0 == k { n++ } END { print n + 0 }' "$STATE/varv.txt"; }
vanta_pa_fonstret() {
  local orsak=$1
  [ "${VANTAR:-}" = "$orsak" ] || logg "väntar: $orsak"
  VANTAR=$orsak
  sleep 300
}

pausa() {
  local orsak=STOPP
  [ -f "$STATE/SPARR" ] && orsak=SPARR
  [ "${PAUSAD:-}" = "$orsak" ] || logg "pausad: ~/.bakgrund/$orsak finns"
  PAUSAD=$orsak
  sleep 300
}

logg "loopen startar (installerad i $INST)"
plan_fel=0
snabba_fel=0
while :; do
  if [ -f "$STATE/STOPP" ] || [ -f "$STATE/SPARR" ]; then pausa; continue; fi
  [ -n "${PAUSAD:-}" ] && { logg "fortsätter"; PAUSAD=; }
  if ! i_fonstret; then vanta_pa_fonstret "utanför fönstret ${FONSTER_START}-${FONSTER_SLUT}"; continue; fi
  if [ "$(varv_i_natt)" -ge "$MAX_PER_NATT" ]; then vanta_pa_fonstret "$MAX_PER_NATT uppgifter klara i natt"; continue; fi
  [ -n "${VANTAR:-}" ] && { logg "fönstret öppet, fortsätter"; VANTAR=; }
  uppdatera
  sakra_gren || { logg "grenen gick inte att ordna, försöker igen om 30 min"; sleep 1800; continue; }
  [ "${BAKGRUND_UV_SYNC:-1}" = 1 ] && { (cd "$TRAD" && uv sync -q) || logg "uv sync misslyckades"; }
  commit_rester "före planeringen"

  planera; rc=$?
  if [ $rc = 2 ]; then logg "användningsgränsen under planeringen, väntar $((VANTA_GRANS / 60)) min"; sleep "$VANTA_GRANS"; continue; fi
  if [ $rc != 0 ]; then
    plan_fel=$((plan_fel + 1))
    v=$(( plan_fel >= 3 ? 3600 : 600 ))
    logg "planeringen gav ingen användbar nasta.md (gång $plan_fel), väntar $((v / 60)) min"
    sleep "$v"; continue
  fi
  plan_fel=0

  kor_uppgift
  journal
  # en uppgift som dör direkt räknas inte mot nattens tak
  if ! { [ "$STATUS" = misslyckad ] && [ $(( $(date +%s) - START )) -lt 300 ]; }; then natt_nyckel >> "$STATE/varv.txt"; fi
  pusha || logg "grenen pushades inte"

  # en uppgift som dör direkt flera gånger i rad (inloggningen, nätet) ska inte bränna varv
  if [ "$STATUS" = misslyckad ] && [ $(( $(date +%s) - START )) -lt 300 ]; then
    snabba_fel=$((snabba_fel + 1))
    v=$(( 30 * 2 ** (snabba_fel - 1) )); [ $v -gt 240 ] && v=240
    logg "uppgiften dog direkt ($snabba_fel gånger i rad), väntar $v min"
    sleep $((v * 60))
  else
    snabba_fel=0
  fi
done
