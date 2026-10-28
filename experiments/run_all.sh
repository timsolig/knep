#!/usr/bin/env bash
# Kör prognosgenereringen för alla sex fall i två parallella kedjor.
# Användning: experiments/run_all.sh <pysteps-data> <utkatalog>
set -uo pipefail
cd "$(dirname "$0")/.."
data=$1 out=$2
mkdir -p "$out"
chain() {
  for c in "$@"; do
    .venv/bin/python experiments/generate.py "$data" "$c" --out "$out" 2>&1 | grep -v "configuration file"
  done
}
chain knmi_20100826 fmi_20160928 mch_20170131 > "$out/log_a.txt" 2>&1 &
chain rmi_20210704 mch_20150515 fmi_20170509 > "$out/log_b.txt" 2>&1 &
wait
echo "alla fall klara"
