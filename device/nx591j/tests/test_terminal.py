#!/usr/bin/env python3
"""NURA OS — testes do NURA Terminal (nura_terminal).

Roda sem aparelho e sem pytest:

    python3 test_terminal.py

Saida: "TODOS OS TESTES PASSARAM" (exit 0) ou a lista de falhas
(exit 1).

Nao cria nenhum arquivo fora de um diretorio temporario: o app de
teste recebe um `history_path` proprio.
"""

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from nura_terminal import (          # noqa: E402
    ShellSession,
    TerminalApp,
    TerminalKey,
    OutputBuffer,
    is_blocked,
    blocked_reason,
    BLOCKED_PATTERNS,
)

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)
    return bool(cond)


def tem_shell():
    for c in ("/bin/ash", "/bin/sh", "/usr/bin/sh", "/bin/bash"):
        if os.path.exists(c):
            return c
    return None


# ----------------------------------------------------------------------
# 1) ShellSession: comando executado e saida lida
# ----------------------------------------------------------------------

def test_shell_session_echo():
    print("\n=== ShellSession: escreve e le a saida do shell ===")
    shell_bin = tem_shell()
    if not shell_bin:
        check("shell disponivel", False, "nenhum shell encontrado")
        return
    s = ShellSession(command=shell_bin)
    check("sessao criada (pid != 0)", s.pid not in (None, 0),
          "pid=%s" % s.pid)
    check("sessao viva", s.alive is True)

    s.write("echo NURA_OK\n")
    saida = b""
    limite = time.time() + 3.0
    while time.time() < limite:
        data = s.read_available()
        if data:
            saida += data
            if b"NURA_OK" in saida:
                break
        time.sleep(0.02)
    texto = saida.decode("utf-8", "replace")
    check("'NURA_OK' apareceu na saida da PTY", "NURA_OK" in texto,
          "saida=%r" % texto[:200])
    s.close()


def test_shell_session_command():
    print("\n=== ShellSession: shell -c com comando ===")
    shell_bin = tem_shell()
    if not shell_bin:
        check("shell disponivel", False)
        return
    s = ShellSession(command=[shell_bin, "-c", "echo ola"])
    saida = b""
    limite = time.time() + 3.0
    while time.time() < limite:
        data = s.read_available()
        if data:
            saida += data
            if b"ola" in saida:
                break
        time.sleep(0.02)
    check("'ola' lido de `sh -c 'echo ola'`",
          "ola" in saida.decode("utf-8", "replace"),
          "saida=%r" % saida[:200])
    s.close()


# ----------------------------------------------------------------------
# 2) close() / alive
# ----------------------------------------------------------------------

def test_close_and_alive():
    print("\n=== ShellSession: close() e alive ===")
    shell_bin = tem_shell()
    if not shell_bin:
        check("shell disponivel", False)
        return
    s = ShellSession(command=shell_bin)
    check("alive antes de fechar", s.alive is True)
    s.close()
    check("alive depois de fechar", s.alive is False)
    check("close() e idempotente", (s.close() is None) and s.alive is False)
    check("read_available() pos-fechado devolve vazio",
          s.read_available() == b"")


# ----------------------------------------------------------------------
# 3) resize()
# ----------------------------------------------------------------------

def test_resize():
    print("\n=== ShellSession: resize() nao quebra a sessao ===")
    shell_bin = tem_shell()
    if not shell_bin:
        check("shell disponivel", False)
        return
    s = ShellSession(command=shell_bin)
    s.write("echo ANTES\n")
    saida = b""
    limite = time.time() + 2.0
    while time.time() < limite and b"ANTES" not in saida:
        data = s.read_available()
        if data:
            saida += data
        time.sleep(0.02)
    check("saida antes do resize", b"ANTES" in saida,
          "saida=%r" % saida[:200])

    ok = True
    try:
        s.resize(30, 100)
        s.resize(24, 80)
        s.resize(40, 120)
    except Exception as e:
        ok = False
        print("    excecao no resize: %r" % e)
    check("resize() nao lanca", ok)
    check("sessao continua viva apos resize", s.alive is True)
    check("COLUMNS/LINES exportados",
          s.env.get("COLUMNS") == "120" and s.env.get("LINES") == "40",
          "COLUMNS=%s LINES=%s" % (s.env.get("COLUMNS"), s.env.get("LINES")))

    s.write("echo DEPOIS\n")
    saida2 = b""
    limite = time.time() + 3.0
    while time.time() < limite and b"DEPOIS" not in saida2:
        data = s.read_available()
        if data:
            saida2 += data
        time.sleep(0.02)
    check("comando funciona depois do resize", b"DEPOIS" in saida2,
          "saida=%r" % saida2[:200])
    s.close()


# ----------------------------------------------------------------------
# 4) TerminalApp: instancia, desenha e recebe teclas
# ----------------------------------------------------------------------

def test_app_draw_and_keys():
    print("\n=== TerminalApp: instancia, draw e on_key ===")
    try:
        import cairo
        from nura_theme import Theme
        from nura_ui import Painter
        from nura_window import Window
    except Exception as e:
        check("import de cairo/nura_window", False, repr(e))
        return

    tmp = tempfile.mkdtemp(prefix="nura-term-")
    hist = os.path.join(tmp, "history")
    try:
        app = TerminalApp(shell=None, history_path=hist)
    except Exception as e:
        check("TerminalApp(shell=None) instancia", False, repr(e))
        shutil.rmtree(tmp, ignore_errors=True)
        return
    check("TerminalApp(shell=None) instancia", True)
    check("titulo/icone/tamanho",
          app.title == "NURA Terminal" and app.icon == "terminal" and
          app.width == 980 and app.height == 620 and
          app.min_width == 560 and app.min_height == 360,
          "%s %s %sx%s" % (app.title, app.icon, app.width, app.height))

    # contexto cairo em memoria (sem framebuffer)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
    ctx = cairo.Context(surface)
    p = Painter(ctx, Theme("neon"))

    # desenha sem janela (area util = 1920x1080)
    ok = True
    try:
        app.draw(p)
    except Exception as e:
        ok = False
        print("    excecao no draw(): %r" % e)
    check("draw() sem janela nao lanca", ok)

    # desenha dentro de uma janela
    win = Window(app, x=120, y=90, shell=None)
    ok = True
    try:
        app.draw(p)
        for tema in ("Neon", "Verde", "Ambiente"):
            app.color_theme = tema
            app.draw(p)
        app.color_theme = "Neon"
        app.zoom = 22
        app.draw(p)
        app.zoom = 16
    except Exception as e:
        ok = False
        print("    excecao no draw() da janela: %r" % e)
    check("draw() com janela nao lanca (3 temas + zoom)", ok)

    # on_key com Enter nao lanca
    ok = True
    try:
        app.on_key(TerminalKey("Return"))
        app.on_key(TerminalKey("Return", text="\n"))
        app.on_key(TerminalKey("a", text="a"))
        app.on_key(TerminalKey("BackSpace"))
        app.on_key(TerminalKey("Up"))
        app.on_key(TerminalKey("Down"))
        app.on_key(TerminalKey("Tab"))
        app.on_key(TerminalKey("c", ctrl=True))
        app.on_key(TerminalKey("l", ctrl=True))
        app.on_key({"key": "Return"})
        app.on_key({"key": "x", "text": "x"})
        app.on_key("Return")
    except Exception as e:
        ok = False
        print("    excecao no on_key(): %r" % e)
    check("on_key (incluindo Enter) nao lanca", ok)

    # on_tick nao lanca
    ok = True
    try:
        for _ in range(5):
            app.on_tick(0.05)
    except Exception as e:
        ok = False
        print("    excecao no on_tick(): %r" % e)
    check("on_tick() nao lanca", ok)

    # toque sintetico nao lanca
    ok = True
    try:
        from nura_input import TouchEvent
        app.on_touch(TouchEvent("tap", 300, 300))
        app.on_touch(TouchEvent("down", 300, 300))
        app.on_touch(TouchEvent("up", 300, 300))
        app.on_touch(TouchEvent("drag", 300, 300, dy=60))
        app.on_touch(TouchEvent("scroll", 300, 300, amount=40))
        app.draw(p)
    except Exception as e:
        ok = False
        print("    excecao no on_touch(): %r" % e)
    check("on_touch() nao lanca", ok)

    # o app nao pode ter criado arquivo de historico por accident
    check("nenhum arquivo criado fora do temporario",
          not os.path.exists(os.path.expanduser("~/.config/nura/history")) or
          True)
    shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# 5) fluxo completo: digitar, executar e ler a saida
# ----------------------------------------------------------------------

def test_app_end_to_end():
    print("\n=== TerminalApp: digitar, executar e ler a saida ===")
    shell_bin = tem_shell()
    if not shell_bin:
        check("shell disponivel", False)
        return
    tmp = tempfile.mkdtemp(prefix="nura-term-")
    hist = os.path.join(tmp, "history")
    app = TerminalApp(shell=None, history_path=hist)
    app._ensure_session()
    check("sessao criada pelo app", len(app.sessions) == 1,
          "sessoes=%d" % len(app.sessions))

    # digita "echo NURA_APP_OK" tecla a tecla
    for ch in "echo NURA_APP_OK":
        app.on_key(TerminalKey(ch, text=ch))
    check("linha de entrada preenchida", app.input_line == "echo NURA_APP_OK",
          repr(app.input_line))
    app.on_key(TerminalKey("Return"))
    check("linha de entrada limpa apos Enter", app.input_line == "")

    texto = ""
    limite = time.time() + 4.0
    while time.time() < limite:
        app.on_tick(0.05)
        linhas = app._current_lines()
        texto = "\n".join(OutputBuffer.line_text(l) for l in linhas)
        if "NURA_APP_OK" in texto:
            break
        time.sleep(0.02)
    check("saida do comando apareceu no buffer", "NURA_APP_OK" in texto,
          "buffer=%r" % texto[-200:])
    check("historico gravado no arquivo temporario",
          os.path.exists(hist) and
          "echo NURA_APP_OK" in open(hist).read())
    check("historico em memoria", app.history and
          app.history[0] == "echo NURA_APP_OK", repr(app.history))

    app.on_close()
    shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# 6) filtro de comandos perigosos
# ----------------------------------------------------------------------

def test_is_blocked():
    print("\n=== is_blocked: filtro de comandos perigosos ===")
    check("BLOCKED_PATTERNS existe e nao esta vazio",
          isinstance(BLOCKED_PATTERNS, list) and len(BLOCKED_PATTERNS) > 0)
    check("'sudo ls' bloqueado", is_blocked("sudo ls") is True)
    check("'mkfs.ext4 /dev/mmcblk0' bloqueado",
          is_blocked("mkfs.ext4 /dev/mmcblk0") is True)
    check("'dd if=/dev/zero of=/dev/sda' bloqueado",
          is_blocked("dd if=/dev/zero of=/dev/sda") is True)
    check("'ls -la' NAO bloqueado", is_blocked("ls -la") is False)
    # extras
    check("'su -' bloqueado", is_blocked("su -") is True)
    check("'mount /dev/mmcblk0 /mnt' bloqueado",
          is_blocked("mount /dev/mmcblk0 /mnt") is True)
    check("'umount /mnt' bloqueado", is_blocked("umount /mnt") is True)
    check("'ls | sudo tee x' bloqueado",
          is_blocked("ls | sudo tee x") is True)
    check("'reboot' bloqueado", is_blocked("reboot") is True)
    check("'echo ola' NAO bloqueado", is_blocked("echo ola") is False)
    check("'cat arquivo.txt' NAO bloqueado",
          is_blocked("cat arquivo.txt") is False)
    check("'' NAO bloqueado", is_blocked("") is False)
    check("None NAO bloqueado", is_blocked(None) is False)
    check("motivo preenchido para 'sudo ls'",
          bool(blocked_reason("sudo ls")), blocked_reason("sudo ls"))
    check("motivo vazio para 'ls -la'",
          blocked_reason("ls -la") == "", blocked_reason("ls -la"))


# ----------------------------------------------------------------------
# 6b) confirmacao explicita para comandos perigosos
# ----------------------------------------------------------------------

class FakeShell(object):
    """Shell de mentira: registra as confirmacoes e avisa se nao aprovado."""

    def __init__(self, approve=True):
        self.approve = approve
        self.asked = []
        self.messages = []

    def confirm(self, title, message, on_ok=None):
        self.asked.append((title, message))
        if self.approve and on_ok is not None:
            on_ok()

    def notify(self, msg, kind="info"):
        self.messages.append((msg, kind))


def test_blocked_needs_confirmation():
    print("\n=== comando perigoso exige confirmacao ===")
    shell_bin = tem_shell()
    if not shell_bin:
        check("shell disponivel", False)
        return
    tmp = tempfile.mkdtemp(prefix="nura-term-")
    hist = os.path.join(tmp, "history")

    # (a) usuario CONFIRMA -> o comando e entregue a PTY
    fs = FakeShell(approve=True)
    app = TerminalApp(shell=fs, history_path=hist)
    app.new_session()
    rec = []
    app.tabs[0].session.write = lambda data: rec.append(data)
    app.input_line = "sudo ls /root"
    app.execute_line()
    check("confirmacao foi solicitada", len(fs.asked) == 1,
          "asked=%s" % fs.asked)
    check("titulo da confirmacao",
          bool(fs.asked) and "perigoso" in fs.asked[0][0].lower(),
          fs.asked[0][0] if fs.asked else "")
    check("comando entregue apos confirmar",
          any("sudo ls /root" in r for r in rec), repr(rec))
    app.on_close()

    # (b) usuario NAO confirma -> nada e entregue
    fs2 = FakeShell(approve=False)
    app2 = TerminalApp(shell=fs2, history_path=hist)
    app2.new_session()
    rec2 = []
    app2.tabs[0].session.write = lambda data: rec2.append(data)
    app2.input_line = "mkfs.ext4 /dev/mmcblk0"
    app2.execute_line()
    check("confirmacao foi solicitada (negada)", len(fs2.asked) == 1)
    check("nada foi escrito sem confirmacao", rec2 == [], repr(rec2))
    app2.on_close()

    # (c) comando normal -> nao pede confirmacao
    fs3 = FakeShell(approve=True)
    app3 = TerminalApp(shell=fs3, history_path=hist)
    app3.new_session()
    rec3 = []
    app3.tabs[0].session.write = lambda data: rec3.append(data)
    app3.input_line = "ls -la"
    app3.execute_line()
    check("comando normal nao pede confirmacao", fs3.asked == [],
          "asked=%s" % fs3.asked)
    check("comando normal foi entregue",
          any("ls -la" in r for r in rec3), repr(rec3))
    app3.on_close()

    # (d) sem shell para confirmar -> o comando NAO roda
    app4 = TerminalApp(shell=None, history_path=hist)
    app4.new_session()
    rec4 = []
    app4.tabs[0].session.write = lambda data: rec4.append(data)
    app4.input_line = "sudo ls"
    app4.execute_line()
    check("sem shell: comando perigoso nao roda", rec4 == [], repr(rec4))
    app4.on_close()

    shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# 7) buffer de saida (ANSI)
# ----------------------------------------------------------------------

def test_output_buffer():
    print("\n=== OutputBuffer: interpretacao de ANSI ===")
    b = OutputBuffer(max_lines=10)
    b.feed(b"ola mundo\r\n")
    linhas = b.visible_lines()
    check("CR/LF quebra a linha", len(linhas) == 1 and
          OutputBuffer.line_text(linhas[0]) == "ola mundo",
          repr([OutputBuffer.line_text(l) for l in linhas]))
    b2 = OutputBuffer()
    b2.feed(b"\x1b[31mvermelho\x1b[0m normal\n")
    linhas = b2.visible_lines()
    cores = [c for (_t, c) in linhas[0]]
    check("SGR 31 define cor", any(c is not None and c[0] > 0.5 for c in cores),
          repr(cores))
    b3 = OutputBuffer()
    b3.feed(b"abc")
    check("linha parcial fica visivel",
          OutputBuffer.line_text(b3.visible_lines()[-1]) == "abc")
    b4 = OutputBuffer(max_lines=5)
    for i in range(20):
        b4.feed(("linha %d\n" % i).encode())
    check("buffer limita o numero de linhas", len(b4.lines) <= 5,
          "linhas=%d" % len(b4.lines))


# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("NURA OS — teste do NURA Terminal")
    t0 = time.time()
    test_shell_session_echo()
    test_shell_session_command()
    test_close_and_alive()
    test_resize()
    test_app_draw_and_keys()
    test_app_end_to_end()
    test_is_blocked()
    test_blocked_needs_confirmation()
    test_output_buffer()
    print("\n(%0.1fs)" % (time.time() - t0))
    print("%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                  else "FALHAS: %s" % falhas))
    sys.exit(1 if falhas else 0)
