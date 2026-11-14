#!/usr/bin/env python3
"""NURA OS — testes do NURA Game Hub.

Roda SEM o aparelho e SEM pytest:

    python3 test_gamehub.py

Saida: "TODOS OS TESTES PASSARAM" (exit 0) ou a lista de falhas (exit 1).

Todos os testes usam arvores de arquivos falsas em diretorios
temporarios: nenhum arquivo do sistema e tocado e nada e criado no
disco (a propria verificacao disso faz parte dos testes).
"""

import os
import random
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import cairo  # noqa: E402

from nura_theme import Theme  # noqa: E402
from nura_ui import Painter  # noqa: E402
from nura_window import Window  # noqa: E402
from nura_input import TouchEvent  # noqa: E402

import nura_gamehub as GH  # noqa: E402
from nura_gamehub import GameEntry, GameHub  # noqa: E402

falhas = []

#: PATH "limpo" usado nos testes (o do host pode estar no Windows via /mnt,
#: o que deixa a busca de binarios lentissima)
LINUX_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)
    return bool(cond)


def snapshot(base):
    """Lista de caminhos (relativos) de uma arvore — para comparar."""
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for n in sorted(filenames):
            p = os.path.join(dirpath, n)
            try:
                st = os.stat(p)
                out.append((os.path.relpath(p, base), st.st_size))
            except OSError:
                out.append((os.path.relpath(p, base), -1))
        for n in sorted(dirnames):
            out.append((os.path.relpath(os.path.join(dirpath, n), base) + "/",
                        -2))
    return sorted(out)


def write(path, content):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w") as f:
        f.write(content)


def make_exec(path):
    with open(path, "w") as f:
        f.write("#!/bin/sh\nexit 0\n")
    os.chmod(path, 0o755)
    return path


class FakeShell(object):
    """Shell falso: registra o que o app pede, nao executa nada."""

    def __init__(self):
        self.theme = Theme("neon")
        self.launched = []
        self.confirmed = []
        self.notifications = []
        self.fullscreen = None

    def notify(self, msg, kind="info"):
        self.notifications.append((msg, kind))

    def confirm(self, title, message, on_ok=None):
        self.confirmed.append((title, message))
        if on_ok is not None:
            on_ok()

    def launch(self, cmd):
        self.launched.append(cmd)

    def set_fullscreen(self, flag):
        self.fullscreen = bool(flag)


class ShellSemFullscreen(object):
    """Shell SEM set_fullscreen — o app nao pode quebrar com ele."""

    def __init__(self):
        self.theme = Theme("neon")
        self.launched = []
        self.confirmed = []
        self.notifications = []

    def notify(self, msg, kind="info"):
        self.notifications.append((msg, kind))

    def confirm(self, title, message, on_ok=None):
        self.confirmed.append((title, message))
        if on_ok is not None:
            on_ok()

    def launch(self, cmd):
        self.launched.append(cmd)


# ----------------------------------------------------------------------
# 1) scan_games
# ----------------------------------------------------------------------

def test_scan_games(tmp):
    print("\n=== scan_games (arquivos .desktop falsos) ===")
    apps = os.path.join(tmp, "applications")
    os.makedirs(apps)
    write(os.path.join(apps, "fakegame.desktop"),
          "[Desktop Entry]\nType=Application\nName=Fake Game\n"
          "Exec=/bin/true\nIcon=gamepad\nCategories=Game;ArcadeGame;\n")
    write(os.path.join(apps, "missinggame.desktop"),
          "[Desktop Entry]\nType=Application\nName=Missing Game\n"
          "Exec=nao-existe-xyz-123\nCategories=Game;\n")
    write(os.path.join(apps, "util.desktop"),
          "[Desktop Entry]\nType=Application\nName=Bloco de Notas\n"
          "Exec=notepad\nCategories=Utility;TextEditor;\n")

    before = snapshot(tmp)
    games = GH.scan_games(dirs=[apps])
    after = snapshot(tmp)

    names = [g.name for g in games]
    check("achou os 2 jogos declarados como Game",
          len(games) == 2, "achou %r" % (names,))
    check("'Fake Game' esta na lista", "Fake Game" in names, "%r" % names)
    check("categoria Utility nao entra na biblioteca",
          "Bloco de Notas" not in names, "%r" % names)

    fg = [g for g in games if g.name == "Fake Game"]
    check("Exec existente => jogavel", fg and fg[0].playable)
    check("Exec existente => launch_cmd preenchido",
          fg and fg[0].launch_cmd and "true" in fg[0].launch_cmd)
    check("kind == 'jogo'", fg and fg[0].kind == "jogo")
    check("plataforma derivada das categorias",
          fg and fg[0].platform == "Arcade", fg[0].platform)

    mg = [g for g in games if g.name == "Missing Game"]
    check("jogo sem executavel fica nao jogavel", mg and not mg[0].playable)
    check("jogo sem executavel tem motivo",
          mg and bool(mg[0].reason), mg[0].reason if mg else "")
    check("motivo cita o executavel ausente",
          mg and "nao-existe-xyz-123" in mg[0].reason,
          mg[0].reason if mg else "")

    check("scan_games NAO criou nada no disco", before == after,
          "%r != %r" % (before, after))


# ----------------------------------------------------------------------
# 2) scan_emulators
# ----------------------------------------------------------------------

def test_scan_emulators(tmp):
    print("\n=== scan_emulators (PATH real + emulador falso) ===")
    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir)
    fake = make_exec(os.path.join(bindir, "retroarch"))

    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = bindir + os.pathsep + LINUX_PATH
    try:
        emu = GH.scan_emulators()
        names = [e["name"] for e in emu]
        check("emulador falso (retroarch) detectado pelo PATH",
              "retroarch" in names, "%r" % names)
        check("cmd aponta para o binario real",
              any(e["cmd"] == fake for e in emu), "%r" % emu)
        check("todo emulador listado esta instalado=True",
              all(e["installed"] is True for e in emu))
        check("cada dict tem name/cmd/installed",
              all(set(["name", "cmd", "installed"]).issubset(e.keys())
                  for e in emu))

        cat = GH.emulator_catalog()
        check("catalogo lista os emuladores conhecidos",
              len(cat) >= 10, "%d" % len(cat))
        ausentes = [e for e in cat if not e["installed"]]
        check("emuladores ausentes marcados como nao instalados",
              all(e["cmd"] is None for e in ausentes))
    finally:
        os.environ["PATH"] = old_path


# ----------------------------------------------------------------------
# 3) scan_roms
# ----------------------------------------------------------------------

def test_scan_roms(tmp):
    print("\n=== scan_roms (arquivos de ROM falsos) ===")
    roms = os.path.join(tmp, "ROMs")
    os.makedirs(roms)
    with open(os.path.join(roms, "Zelda.gba"), "wb") as f:
        f.write(b"\x00" * 2048)
    sub = os.path.join(roms, "sub")
    os.makedirs(sub)
    with open(os.path.join(sub, "Mario.gba"), "wb") as f:
        f.write(b"\x00" * 1024)
    write(os.path.join(roms, "notas.txt"), "isto nao e uma rom\n")

    before = snapshot(tmp)
    found = GH.scan_roms(dirs=[roms])
    after = snapshot(tmp)

    names = [r.name for r in found]
    check("achou as 2 ROMs (.gba)", len(found) == 2, "%r" % names)
    check("'Zelda' encontrada", "Zelda" in names, "%r" % names)
    check("'Mario' encontrada (subpasta)", "Mario" in names, "%r" % names)
    check("arquivo que nao e ROM ignorado", "notas" not in names)
    check("kind == 'rom'", all(r.kind == "rom" for r in found))
    check("tamanho calculado", all(r.size_bytes > 0 for r in found))
    check("plataforma por extensao",
          all(r.platform == "Game Boy Advance" for r in found))
    check("scan_roms NAO criou nada no disco", before == after)

    # com um emulador instalado a ROM vira jogavel
    bindir = os.path.join(tmp, "bin2")
    os.makedirs(bindir)
    fake_mgba = make_exec(os.path.join(bindir, "mgba"))
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = bindir + os.pathsep + LINUX_PATH
    try:
        found2 = GH.scan_roms(dirs=[roms])
        check("com emulador instalado a ROM fica jogavel",
              found2 and all(r.playable for r in found2))
        check("launch_cmd usa o emulador encontrado",
              found2 and all(r.launch_cmd and r.launch_cmd.startswith(
                  fake_mgba) for r in found2),
              found2[0].launch_cmd if found2 else "")
    finally:
        os.environ["PATH"] = old_path


# ----------------------------------------------------------------------
# 4) scan_roms nao cria diretorio
# ----------------------------------------------------------------------

def test_scan_roms_nao_cria(tmp):
    print("\n=== scan_roms nao cria pastas ===")
    alvo = os.path.join(tmp, "NaoExiste", "ROMs")
    check("a pasta alvo nao existe antes", not os.path.exists(alvo))
    GH.scan_roms(dirs=[alvo])
    GH.scan_roms(dirs=[os.path.join(tmp, "NaoExiste")])
    check("scan_roms NAO criou a pasta de ROMs", not os.path.exists(alvo),
          "agora existe: %s" % alvo)
    check("scan_roms NAO criou o diretorio pai",
          not os.path.exists(os.path.join(tmp, "NaoExiste")))


# ----------------------------------------------------------------------
# 5) scan_controllers
# ----------------------------------------------------------------------

def test_scan_controllers(tmp):
    print("\n=== scan_controllers (proc/dev falsos) ===")
    proc = os.path.join(tmp, "proc", "bus", "input")
    os.makedirs(proc)
    dev = os.path.join(tmp, "dev", "input")
    os.makedirs(dev)
    write(os.path.join(dev, "event3"), "")
    write(os.path.join(proc, "devices"),
          "I: Bus=0018 Vendor=0000 Product=0000 Version=0000\n"
          "N: Name=\"Test Gamepad\"\n"
          "H: Handlers=event3 js0\n"
          "B: PROP=0\n"
          "B: ABS=0\n"
          "\n"
          "I: Bus=0011 Vendor=0002 Product=0000 Version=0000\n"
          "N: Name=\"Touchscreen\"\n"
          "H: Handlers=event1\n")

    ctrls = GH.scan_controllers(proc_path=os.path.join(proc, "devices"),
                                dev_dir=dev)
    check("somente o joystick foi listado (touchscreen ignorado)",
          len(ctrls) == 1, "%r" % ctrls)
    if ctrls:
        c = ctrls[0]
        check("nome do controle lido do procfs",
              c["name"] == "Test Gamepad", c["name"])
        check("device aponta para o eventN",
              c["device"].endswith("event3"), c["device"])
        check("present=True quando o device existe", c["present"] is True)
        check("jsN tambem registrado", c["js"].endswith("js0"), c["js"])
    check("campos name/device/present presentes",
          all(set(["name", "device", "present"]).issubset(c.keys())
              for c in ctrls))

    # device ausente => present=False
    os.remove(os.path.join(dev, "event3"))
    ctrls2 = GH.scan_controllers(proc_path=os.path.join(proc, "devices"),
                                 dev_dir=dev)
    check("device ausente => present=False",
          ctrls2 and ctrls2[0]["present"] is False)

    # /dev/input/js* tambem e detectado (proc sem joystick)
    dev2 = os.path.join(tmp, "dev2", "input")
    os.makedirs(dev2)
    write(os.path.join(dev2, "js0"), "")
    proc2 = os.path.join(tmp, "proc2")
    os.makedirs(proc2)
    write(os.path.join(proc2, "devices"),
          "I: Bus=0011 Vendor=0002 Product=0000 Version=0000\n"
          "N: Name=\"Touchscreen\"\n"
          "H: Handlers=event1\n")
    ctrls3 = GH.scan_controllers(proc_path=os.path.join(proc2, "devices"),
                                 dev_dir=dev2)
    check("js0 encontrado pela varredura de /dev/input",
          any(c["device"].endswith("js0") for c in ctrls3), "%r" % ctrls3)


# ----------------------------------------------------------------------
# 6) graphics_status
# ----------------------------------------------------------------------

def test_graphics_status():
    print("\n=== graphics_status ===")
    g = GH.graphics_status()
    check("devolve um dict", isinstance(g, dict))
    check("'accel' e booleano", isinstance(g.get("accel"), bool),
          repr(g.get("accel")))
    check("'gl' e booleano", isinstance(g.get("gl"), bool))
    check("'drm' e lista", isinstance(g.get("drm"), list))
    check("'note' e texto nao vazio",
          isinstance(g.get("note"), str) and g["note"], repr(g.get("note")))
    check("nota coerente com a aceleracao",
          g["accel"] or g["note"].startswith(GH.NO_ACCEL_NOTE), g["note"])
    check("nota honesta quando nao ha GPU/OpenGL",
          (not g["accel"]) or "aceleracao 3D" in g["note"], g["note"])
    check("'drm' traz os conectores reais",
          all(set(["card", "connector"]).issubset(d.keys())
              for d in g["drm"]))


# ----------------------------------------------------------------------
# 7) GameHub: instancia, draw, toques
# ----------------------------------------------------------------------

def test_hub(tmp):
    print("\n=== GameHub: instancia, desenho e toques ===")
    shell = FakeShell()
    hub = GameHub(shell=shell)
    check("titulo", hub.title == "NURA Game Hub", hub.title)
    check("icone", hub.icon == "gamepad", hub.icon)
    check("tamanho minimo", (hub.width, hub.height) == (1080, 680))
    check("tamanho minimo da janela",
          (hub.min_width, hub.min_height) == (640, 440))

    hub.game_dirs = [os.path.join(tmp, "applications")]
    hub.rom_dirs = [os.path.join(tmp, "ROMs")]
    hub.refresh()
    check("refresh achou os 2 jogos falsos", len(hub.entries) == 2,
          "%r" % [e.name for e in hub.entries])
    check("refresh achou as 2 ROMs", len(hub.roms) == 2,
          "%r" % [e.name for e in hub.roms])

    before = snapshot(tmp)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
    ctx = cairo.Context(surf)
    p = Painter(ctx, shell.theme)

    ok = True
    try:
        hub.draw(p)
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao no draw: %r" % (e,))
    check("draw() em 1920x1080 sem janela nao levanta excecao", ok)

    win = Window(hub, x=120, y=90, shell=shell)
    ok = True
    try:
        for tab in range(4):
            hub.tab = tab
            hub.draw(p)
            hub.on_tick(0.016)
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao ao desenhar as abas: %r" % (e,))
    check("draw() das 4 abas nao levanta excecao", ok)

    # sem aceleracao 3D (estado real do aparelho) e sem nenhum jogo
    hub.gfx = {"accel": False, "gl": False, "drm": [],
               "note": GH.NO_ACCEL_NOTE}
    ok = True
    try:
        for tab in range(4):
            hub.tab = tab
            hub.draw(p)
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao no aviso de aceleracao: %r" % (e,))
    check("draw() com o aviso 'sem aceleracao 3D' nao levanta excecao", ok)

    hub.entries = []
    hub.roms = []
    ok = True
    try:
        hub.tab = 0
        hub.draw(p)
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao no estado vazio: %r" % (e,))
    check("draw() do estado vazio ('Nenhum jogo instalado') nao levanta "
          "excecao", ok)

    # instancia sem shell nenhum
    hub_solo = GameHub()
    ok = True
    try:
        hub_solo.draw(p)
        hub_solo.on_touch(TouchEvent("tap", 100, 100))
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao sem shell: %r" % (e,))
    check("GameHub sem shell instancia e desenha sem excecao", ok)

    # a busca de ROMs e adiada: a janela abre na hora
    hub3 = GameHub(shell=shell)
    hub3.game_dirs = [os.path.join(tmp, "applications")]
    hub3.rom_dirs = [os.path.join(tmp, "ROMs")]
    hub3.on_open()
    check("on_open abre sem esperar a busca de ROMs", hub3.roms == [],
          "%r" % [r.name for r in hub3.roms])
    hub3._open_time = time.time() - 10.0
    hub3.on_tick(0.016)
    check("a busca de ROMs acontece no tick seguinte", len(hub3.roms) == 2,
          "%r" % [r.name for r in hub3.roms])

    # 50 toques aleatorios
    random.seed(20261113)
    ok = True
    touched = 0
    try:
        for i in range(50):
            x = random.randint(0, 1919)
            y = random.randint(0, 1079)
            hub.on_touch(TouchEvent("tap", x, y))
            touched += 1
            hub.on_touch(TouchEvent("down", x, y))
            hub.on_touch(TouchEvent("up", x, y))
            hub.on_touch(TouchEvent("scroll", x, y, amount=random.uniform(
                -300, 300)))
            hub.on_touch(TouchEvent("drag", x, y, dx=0, dy=random.uniform(
                -50, 50)))
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao nos toques: %r" % (e,))
    check("50 taps aleatorios sem excecao", ok and touched == 50)

    after = snapshot(tmp)
    check("as interacoes NAO criaram nada no disco", before == after,
          "%r != %r" % (before, after))

    # fluxo real de lancamento
    shell.launched = []
    shell.confirmed = []
    entry = GameEntry(name="Fake Game", path="x", launch_cmd="/bin/true",
                      kind="jogo", playable=True)
    hub._launch_entry(entry)
    check("lancamento pede confirmacao", len(shell.confirmed) == 1,
          "%r" % shell.confirmed)
    check("lancamento executa depois da confirmacao",
          shell.launched == ["/bin/true"], "%r" % shell.launched)

    shell.launched = []
    hub._launch_entry(GameEntry(name="Quebrado", path="x", launch_cmd=None,
                                kind="jogo", playable=False,
                                reason="sem executavel"))
    check("item nao jogavel NAO e executado", shell.launched == [])

    # tela cheia
    hub.fullscreen = False
    hub._toggle_fullscreen()
    check("set_fullscreen do shell foi chamado", shell.fullscreen is True,
          repr(shell.fullscreen))
    hub._toggle_fullscreen()
    check("set_fullscreen alterna", shell.fullscreen is False)

    # shell sem set_fullscreen nao pode quebrar
    s2 = ShellSemFullscreen()
    hub2 = GameHub(shell=s2)
    ok = True
    try:
        hub2._toggle_fullscreen()
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao sem set_fullscreen: %r" % (e,))
    check("shell sem set_fullscreen nao quebra o app", ok)
    check("e o app avisa que o shell nao tem o metodo",
          any("set_fullscreen" in m for m, _ in s2.notifications),
          "%r" % s2.notifications)

    # escala e tema
    ok = True
    try:
        hub._change_scale(0.1)
        hub._change_scale(-0.1)
        hub._change_theme("gamer")
        hub._change_theme("neon")
    except Exception as e:                                     # noqa: BLE001
        ok = False
        print("    excecao em escala/tema: %r" % (e,))
    check("mudar escala/tema nao levanta excecao", ok)
    check("escala limitada a 0.8..1.4",
          0.8 <= hub.ui_scale <= 1.4, repr(hub.ui_scale))


# ----------------------------------------------------------------------
# 8) GameEntry
# ----------------------------------------------------------------------

def test_game_entry():
    print("\n=== GameEntry ===")
    e = GameEntry(name="X", path="/tmp/x", launch_cmd="run x", kind="rom",
                  icon="gamepad", size="1.0 MB", platform="NES",
                  playable=False, reason="sem emulador")
    check("campos basicos", e.name == "X" and e.kind == "rom")
    check("reason preservado", e.reason == "sem emulador")
    d = e.as_dict()
    check("as_dict com todas as chaves",
          set(["name", "path", "launch_cmd", "kind", "icon", "size",
               "platform", "playable", "reason"]).issubset(d.keys()))
    check("playable e bool", isinstance(e.playable, bool))


# ----------------------------------------------------------------------

def main():
    print("NURA OS — teste do NURA Game Hub")
    tmp = tempfile.mkdtemp(prefix="nura-gamehub-")
    try:
        test_scan_games(tmp)
        test_scan_emulators(tmp)
        test_scan_roms(tmp)
        test_scan_roms_nao_cria(tmp)
        test_scan_controllers(tmp)
        test_graphics_status()
        test_game_entry()
        test_hub(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS: %s" % falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
