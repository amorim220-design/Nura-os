#!/bin/bash
# NURA OS — contagem de asserções por suíte.
cd "$(dirname "$0")" || exit 1
TOTAL_OK=0
TOTAL_FALHA=0
printf "%-28s %8s %8s %8s\n" "SUITE" "OK" "FALHA" "TEMPO"
printf "%-28s %8s %8s %8s\n" "----------------------------" "--------" "--------" "--------"
for t in test_*.py; do
  ini=$(date +%s%N)
  out=$(python3 "$t" 2>&1)
  code=$?
  fim=$(date +%s%N)
  ok=$(printf '%s' "$out" | grep -c '\[ OK \]')
  fa=$(printf '%s' "$out" | grep -c '\[FALHA\]')
  ms=$(( (fim - ini) / 1000000 ))
  TOTAL_OK=$((TOTAL_OK + ok))
  TOTAL_FALHA=$((TOTAL_FALHA + fa))
  st="OK"
  [ "$code" -ne 0 ] && st="FALHOU"
  printf "%-28s %8s %8s %8s  %s\n" "$t" "$ok" "$fa" "${ms}ms" "$st"
done
printf "%-28s %8s %8s\n" "----------------------------" "--------" "--------"
printf "%-28s %8s %8s\n" "TOTAL" "$TOTAL_OK" "$TOTAL_FALHA"
[ "$TOTAL_FALHA" -eq 0 ] && echo "RESULTADO: TUDO OK" || echo "RESULTADO: HOUVE FALHAS"
