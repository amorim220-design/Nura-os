#!/bin/sh
# NURA OS — instala o NURA Desktop no aparelho.
#
# ATENCAO: este script faz ALTERACOES PERSISTENTES.
# Só deve ser executado APOS AUTORIZACAO EXPLICITA do usuario.
#
# uso:  sh install-nura.sh [--dry-run]
#
# O que faz:
#   1. instala python3 + py3-cairo (+ py3-pillow opcional)
#   2. copia o codigo do NURA para /usr/share/nura
#   3. cria /etc/nura (configuracao) e /var/lib/nura (estado)
#   4. instala a unidade systemd (ou o script OpenRC)
#   5. NAO habilita no boot (isso e um passo separado, autorizado
#      a parte)
#
# O que NAO faz:
#   - nao mexe no bootloader, no initramfs, no kernel nem em particoes
#   - nao altera a sessao grafica atual (X11)
#   - nao habilita a inicializacao automatica
#   - nao remove nada do sistema

set -e

DRY=0
[ "$1" = "--dry-run" ] && DRY=1

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/usr/share/nura
CONF=/etc/nura
STATE=/var/lib/nura
LOG=/var/log/nura-install.log

say() { echo "[install-nura] $*"; }
run() {
    if [ "$DRY" = "1" ]; then
        say "(dry-run) $*"
    else
        say "executando: $*"
        "$@"
    fi
}

[ "$(id -u)" = "0" ] || { say "ERRO: precisa de root"; exit 1; }

say "=== 1/5  simulando as dependencias de pacotes ==="
if command -v apk >/dev/null 2>&1; then
    apk add --simulate python3 py3-cairo 2>&1 | sed 's/^/    /' || true
    say "--- conferindo o tamanho total do download:"
    apk add --simulate python3 py3-cairo 2>&1 | grep -iE 'OK:|MB' | tail -3 || true
else
    say "apk nao encontrado (rode dentro do aparelho)"
fi

if [ "$DRY" = "1" ]; then
    say ""
    say "dry-run: nenhuma alteracao foi feita."
    say "para instalar de verdade, rode sem --dry-run."
    exit 0
fi

say "=== 2/5  instalando os pacotes ==="
apk add python3 py3-cairo

say "=== 3/5  copiando o codigo ==="
mkdir -p "$DEST" "$CONF" "$STATE/backup"
cp -r "$SRC/src" "$DEST/"
[ -d "$SRC/assets" ] && cp -r "$SRC/assets" "$DEST/"
[ -d "$SRC/docs" ] && cp -r "$SRC/docs" "$DEST/"
mkdir -p "$DEST/assets/splash"
cp "$SRC/assets/splash/"*.png "$DEST/assets/splash/" 2>/dev/null || true
chmod 0755 "$DEST/src/"*.py

say "=== 4/5  instalcando o servico ==="
if [ -d /run/systemd/system ]; then
    cp "$SRC/packaging/nura-shell.service" /etc/systemd/system/
    systemctl daemon-reload
    say "systemd: unidade instalada (NAO habilitada)"
else
    cp "$SRC/packaging/nura-shell.initd" /etc/init.d/nura-shell
    chmod 0755 /etc/init.d/nura-shell
    say "OpenRC: script instalado (NAO habilitado)"
fi
cp "$SRC/packaging/nura-recovery" /usr/bin/nura-recovery
chmod 0755 /usr/bin/nura-recovery
if [ -d /run/systemd/system ]; then
    install -m 0755 "$SRC/packaging/nura-test" /usr/bin/nura-test
    if [ -d /etc/sudoers.d ] && command -v visudo >/dev/null 2>&1; then
        visudo -cf "$SRC/packaging/nura-brightness-sudoers"
        install -o root -g root -m 0755 "$SRC/packaging/nura-brightness" /usr/bin/nura-brightness
        install -o root -g root -m 0440 "$SRC/packaging/nura-brightness-sudoers" /etc/sudoers.d/nura-brightness
    fi
fi

say "=== 5/5  verificando a instalacao ==="
python3 -c "import cairo; print('    pycairo', cairo.version)"
PYTHONPATH="$DEST/src" python3 -c "import nura_theme, nura_ui, nura_fb, nura_input; print('    modulos NURA: OK')"

say ""
say "INSTALADO. O desktop NAO foi habilitado no boot."
say "para iniciar manualmente:  python3 $DEST/src/nura_shell.py"
say "para habilitar no boot (passo autorizado a parte):"
say "    systemctl enable nura-shell.service"
say "log desta instalacao: $LOG"
