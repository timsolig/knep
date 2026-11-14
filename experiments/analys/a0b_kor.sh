#!/bin/bash
# Kör varianterna på träningen: a0b_kor.sh BIT "SYSTEM SYSTEM ..." DEL UT
bit=$1; systems=$2; del=$3; ut=$4
for s in $systems; do
  timeout 7200 uv run python experiments/analys/a0b.py kor "$s" --del "$del" --bit "$bit" --ut "$ut"
done
