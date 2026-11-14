#!/bin/bash
# NURA OS — roda toda a suite de testes isolados.
# uso: bash run_tests.sh
cd "$(dirname "$0")" || exit 1
TOTAL=0
FALHAS=0
for t in test_*.py; do
  echo "############################################################"
  echo "### $t"
  echo "############################################################"
  out=$(python3 "$t" 2>&1)
  code=$?
  TOTAL=$((TOTAL+1))
  if [ $code -eq 0 ]; then
    echo "$out" | tail -4
    echo ">>> $t: OK"
  else
    FALHAS=$((FALHAS+1))
    echo "$out" | tail -30
    echo ">>> $t: FALHOU (exit=$code)"
  fi
  echo
done
echo "============================================================"
echo "suites: $TOTAL | falhas: $FALHAS"
[ $FALHAS -eq 0 ] && echo "TUDO OK" || echo "HOUVE FALHAS"
exit $FALHAS
