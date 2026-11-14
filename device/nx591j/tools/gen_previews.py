#!/usr/bin/env python3
"""NURA OS — gera as previews visuais e salva em docs/previews/"""

import os
import subprocess
import sys

BASE = "/mnt/c/Users/Intel i5/Documents/Projeto Padrão/mainline/nura"
OUT = os.path.join(BASE, "docs", "previews")
os.makedirs(OUT, exist_ok=True)

W = 1920
H = 1080


def novo_shell():
    sys.path.insert(0, os.path.join(BASE, "src"))
    from nura_shell import NuraShell
    mock = "/tmp/nura-prev-%d.mock" % os.getpid()
    with open(mock, "wb") as f:
        f.truncate(4352 * 1920)
    return NuraShell(mock=mock)


def salvar(sh, nome):
    sh.tick()
    sh.surface.write_to_png(os.path.join(OUT, nome))
    print("  %s" % nome)


def main():
    # 1) area de trabalho (Neon Blue)
    sh = novo_shell()
    sh.update_monitor()
    salvar(sh, "01-area-de-trabalho.png")
    sh.fb.close()

    # 2) cada app aberto, um de cada vez
    for key, nome in (("terminal", "02-nura-terminal.png"),
                      ("explorer", "02b-nura-explorer.png"),
                      ("control", "02c-nura-control-center.png"),
                      ("performance", "02d-nura-performance.png"),
                      ("games", "02e-nura-game-hub.png")):
        sh = novo_shell()
        sh.update_monitor()
        try:
            sh.open_app(key)
            for _ in range(6):
                sh.tick()
            salvar(sh, nome)
        except Exception as e:
            print("  [erro] %s: %s" % (key, e))
        sh.fb.close()

    # 3) menu Iniciar
    sh = novo_shell()
    sh.start_open = True
    try:
        import nura_start
        sh.start_app = nura_start.StartApp(shell=sh)
        sh.start_app.on_open()
    except Exception as e:
        print("  [erro] NURA Start: %s" % e)
    salvar(sh, "04-nura-start.png")
    sh.fb.close()

    # 4) teclado virtual
    sh = novo_shell()
    sh.open_keyboard()
    sh.keyboard.text = "nura"
    salvar(sh, "05-teclado-virtual.png")
    sh.fb.close()

    # 4b) teclado com SHIFT ligado (prova de que Shift+'-' = '_')
    sh = novo_shell()
    sh.open_keyboard()
    sh.keyboard.shift = True
    sh.keyboard._layout()
    salvar(sh, "05b-teclado-shift.png")
    sh.fb.close()

    # 4c) teclado com a camada 123 (simbolos + acentos pt-BR)
    sh = novo_shell()
    sh.open_keyboard()
    sh.keyboard.symbols = True
    sh.keyboard._layout()
    salvar(sh, "05c-teclado-123.png")
    sh.fb.close()

    # 5) temas
    for t in ("neon", "dark", "minimal", "gamer"):
        sh = novo_shell()
        sh.theme.reload(t)
        sh.bg_surface = None
        sh.update_monitor()
        salvar(sh, "03-tema-%s.png" % t)
        sh.fb.close()

    print("previews em: %s" % OUT)


if __name__ == "__main__":
    main()
