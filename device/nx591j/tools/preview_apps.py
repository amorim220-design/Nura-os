#!/usr/bin/env python3
"""NURA OS — gera previews visuais: area de trabalho, temas e apps.

uso: python3 preview_apps.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from nura_shell import NuraShell  # noqa: E402

MOCK = "/tmp/nura-preview-apps.mock"
OUT = "/tmp"


def novo():
    with open(MOCK, "wb") as f:
        f.truncate(4352 * 1920)
    return NuraShell(mock=MOCK)


def main():
    # 1) area de trabalho + um app aberto
    sh = novo()
    sh.open_app("terminal")
    sh.update_monitor()
    sh.tick()
    sh.surface.write_to_png(os.path.join(OUT, "nura-app-terminal.png"))
    print("[preview] nura-app-terminal.png")
    sh.fb.close()

    # 2) cada tema
    for t in ("neon", "dark", "minimal", "gamer"):
        sh = novo()
        sh.theme.reload(t)
        sh.bg_surface = None
        sh.update_monitor()
        sh.tick()
        sh.surface.write_to_png(os.path.join(OUT, "nura-theme-%s.png" % t))
        print("[preview] nura-theme-%s.png" % t)
        sh.fb.close()

    # 3) menu Iniciar (NURA Start)
    sh = novo()
    sh.start_open = True
    try:
        sh.start_app = __import__("nura_start").StartApp(shell=sh)
        sh.start_app.on_open()
    except Exception as e:
        print("[preview] NURA Start indisponivel: %s" % e)
    sh.tick()
    sh.surface.write_to_png(os.path.join(OUT, "nura-start.png"))
    print("[preview] nura-start.png")
    sh.fb.close()


if __name__ == "__main__":
    main()
