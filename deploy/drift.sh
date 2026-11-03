#!/usr/bin/env bash
# Driften: följer grenen main på GitHub och kör en prognoscykel var femte minut.
#
# Koden körs inte ur bilden utan ur en utcheckning per commit i $ROOT/releases, så en
# sammanslagning till main tas i drift av sig själv utan att containern byggs om:
#
#   1. Var femte minut frågar driften GitHub vilken commit main pekar på.
#   2. En ny commit checkas ut, får sin miljö (uv sync, snabbt ur cachen när uv.lock är
#      oförändrad) och sina låsta modeller, och provas med knep --help.
#   3. Går det bra byter "current" till den. Misslyckas den nya versionens första cykel går
#      driften tillbaka till den förra och provar commiten igen först efter en timme (felet
#      kan ha varit nätet), eller direkt när main ändras.
#
# Bara den här filen och Dockerfile ligger i bilden; de ändras sällan, och då behövs
# docker compose up -d --build. Allt annat följer main.
set -uo pipefail

REPO=${KNEP_REPO:-https://github.com/timsolig/knep.git}
BRANCH=${KNEP_BRANCH:-main}
ROOT=${KNEP_ROOT:-/srv/knep}
EVERY=${KNEP_EVERY:-300}          # sekunder mellan cyklerna
OFFSET=${KNEP_OFFSET:-120}        # cykeln startar så här långt efter femminutersbilden
KEEP=${KNEP_KEEP_RELEASES:-3}

export UV_CACHE_DIR=$ROOT/uv-cache UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PYTHON=${UV_PYTHON:-python3}
mkdir -p "$ROOT/releases" "$ROOT/cache" "$ROOT/out/data"
bad=$ROOT/releases/bad          # commits som inte fungerade: sha och tid
RETRY=${KNEP_RETRY:-3600}
touch "$bad"

log() { echo "$(date -u +%FT%TZ) drift: $*" >&2; }
current() { readlink "$ROOT/current" 2>/dev/null | xargs -r basename; }

prepare() {  # checka ut och installera en commit (miljön måste ligga på sin slutliga plats)
  local sha=$1 dir=$ROOT/releases/$1
  if [ ! -e "$dir/.ready" ]; then
    rm -rf "$dir"
    git init -q "$dir" && git -C "$dir" fetch -q --depth 1 "$REPO" "$sha" \
      && git -C "$dir" -c advice.detachedHead=false checkout -q FETCH_HEAD \
      && (cd "$dir" && uv sync -q --frozen --no-dev --no-editable) || return 1
  fi
  (cd "$dir" && .venv/bin/knep-models fetch >/dev/null && .venv/bin/knep --help >/dev/null) || return 1
  touch "$dir/.ready"
}

failed_recently() { awk -v s="$1" -v t="$(( $(date +%s) - RETRY ))" '$1 == s && $2 > t { f = 1 } END { exit !f }' "$bad"; }
mark_bad() { echo "$1 $(date +%s)" >>"$bad"; }

switch() { ln -sfn "releases/$1" "$ROOT/current.tmp" && mv -T "$ROOT/current.tmp" "$ROOT/current"; }

prune() {
  local keep; keep=$( (current; echo "$previous") | sort -u)
  ls -1t "$ROOT/releases" | grep -E '^[0-9a-f]{40}$' | tail -n +$((KEEP + 1)) | while read -r d; do
    grep -qx "$d" <<<"$keep" || rm -rf "${ROOT:?}/releases/$d"
  done
}

update() {
  local sha
  sha=$(git ls-remote "$REPO" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)
  [ -n "$sha" ] || { log "kunde inte fråga GitHub om $BRANCH"; return; }
  [ "$sha" = "$(current)" ] && return
  failed_recently "$sha" && return
  log "ny version ${sha:0:7}, installerar"
  if prepare "$sha"; then
    previous=$(current)
    switch "$sha"
    trial=1
    log "kör ${sha:0:7}"
    prune
  else
    log "${sha:0:7} gick inte att installera, behåller $(current | cut -c1-7)"
    mark_bad "$sha"
  fi
}

previous="" trial=0
update
[ -n "$(current)" ] || { log "ingen version att köra"; exit 1; }
[ -n "${KNEP_PREPARE_ONLY:-}" ] && exit 0  # för CI: bara installera

first=1
while true; do
  if (( ! first )); then
    now=$(date +%s)
    next=$(( now - now % EVERY + OFFSET ))
    (( next > now )) || next=$(( next + EVERY ))
    sleep $(( next - now ))
    update
  fi
  first=0

  (cd "$ROOT/current" && PATH=$ROOT/current/.venv/bin:$PATH deploy/cycle.sh "$ROOT")
  rc=$?
  if (( rc == 0 )); then
    trial=0
  elif (( trial )) && [ -n "$previous" ]; then
    log "första cykeln med $(current | cut -c1-7) misslyckades (kod $rc), tillbaka till ${previous:0:7}"
    mark_bad "$(current)"
    switch "$previous"
    previous="" trial=0
  fi
  [ -n "${KNEP_ONCE:-}" ] && exit "$rc"
done
