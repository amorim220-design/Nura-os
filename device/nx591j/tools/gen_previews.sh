#!/bin/bash
# NURA OS — gera as previews visuais e salva em docs/previews/
set -e
BASE="/mnt/c/Users/Intel i5/Documents/Projeto Padrão/mainline/nura"
OUT="$BASE/docs/previews"
mkdir -p "$OUT"
cd "$BASE/tools"
python3 preview.py      --out "$OUT/01-area-de-trabalho.png" --bench 10
python3 preview_apps.py
for t in neon dark minimal gamer; do
  [ -f "/tmp/nura-theme-$t.png" ] && cp "/tmp/nura-theme-$t.png" "$OUT/03-tema-$t.png"
done
cp /tmp/nura-app-terminal.png "$OUT/02-nura-terminal.png" 2>/dev/null || true
cp /tmp/nura-start.png       "$OUT/04-nura-start.png"     2>/dev/null || true
echo "previews em: $OUT"
ls -la "$OUT"
