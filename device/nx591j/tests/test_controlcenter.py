#!/usr/bin/env python3
"""NURA OS — testes do NURA Control Center e do NURA Performance.

Roda sem aparelho e sem pytest:

    python3 test_controlcenter.py

Saida: "TODOS OS TESTES PASSARAM" (exit 0) ou a lista de falhas (exit 1).

O que e verificado:
  * os dois apps instanciam e desenham sem excecao num contexto cairo
    1920x1080 (surface em memoria);
  * toques aleatorios (50 pontos) nao quebram nada;
  * a DETECCAO de disponibilidade bate com a existencia real dos
    caminhos do sistema (a expectativa e calculada no proprio teste);
  * sem `nura_sysinfo` (SysInfo=None) NENHUM controle aparece como
    "ligado" — todos ficam indisponivel;
  * a coleta periodica nao roda a cada quadro (contador de atualizacoes);
  * todo alvo de toque tem pelo menos 44x44 px;
  * erros de escrita (EACCES/EPERM) sao mostrados de verdade.
"""

import os
import random
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..", "src")
_SRC = os.path.normpath(_SRC)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import cairo                                        # noqa: E402

from nura_theme import Theme                         # noqa: E402
from nura_ui import Painter                          # noqa: E402

import nura_controlcenter as cc                      # noqa: E402
from nura_controlcenter import (                     # noqa: E402
    Control,
    ControlCenterApp,
    ControlPanel,
    build_controls,
    probe_brightness,
    probe_battery,
    probe_governor,
    probe_volume,
    probe_wifi,
)
import nura_performance as perf_mod                  # noqa: E402
from nura_performance import PerformanceApp          # noqa: E402

try:                                                # evento de toque real
    from nura_input import TouchEvent
except Exception:                                   # pragma: no cover
    class TouchEvent(object):                       # stub minimo
        def __init__(self, type="down", x=0, y=0, **kw):
            self.type = type
            self.x = x
            self.y = y
            self.dx = 0
            self.dy = 0
            self.amount = 0.0
            self.scale = 1.0
            self.time = 0.0
            self.slots = 0

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)
    return bool(cond)


# ----------------------------------------------------------------------
# expectativas calculadas no proprio teste (independente do modulo)
# ----------------------------------------------------------------------

_BIN_CACHE = {}


def _bin(nome):
    """Existe o executavel no PATH ou nos diretorios de sistema?

    Implementacao independente da do modulo (mesma regra, codigo
    proprio). O resultado e memorizado para o teste ser rapido.
    """
    if nome in _BIN_CACHE:
        return _BIN_CACHE[nome]
    found = False
    for folder in ("/usr/local/bin", "/usr/local/sbin", "/usr/bin",
                   "/usr/sbin", "/bin", "/sbin"):
        path = os.path.join(folder, nome)
        try:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                found = True
                break
        except OSError:
            continue
    if not found:
        found = bool(shutil.which(nome))
    _BIN_CACHE[nome] = found
    return found


def _listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _expect_wifi():
    net = "/sys/class/net"
    names = _listdir(net)
    has_iface = any(n.startswith("wlan") for n in names)
    if not has_iface:
        has_iface = any(os.path.isdir(os.path.join(net, n, "wireless"))
                        for n in names)
    tools = any(_bin(b) for b in ("iw", "rfkill", "wpa_supplicant", "wpa_cli",
                                  "connmanctl", "connmand", "nmcli",
                                  "NetworkManager"))
    return has_iface or tools


def _expect_bluetooth():
    if os.path.isdir("/sys/class/bluetooth"):
        return True
    if any(n.startswith("hci") for n in _listdir("/sys/class/bluetooth")):
        return True
    return any(_bin(b) for b in ("bluetoothctl", "bluetoothd", "hciconfig",
                                 "rfkill", "bluez"))


def _expect_brightness():
    for name in _listdir("/sys/class/backlight"):
        d = os.path.join("/sys/class/backlight", name)
        if os.path.isfile(os.path.join(d, "brightness")):
            return True
    return False


def _expect_volume():
    if os.path.isdir("/proc/asound"):
        return True
    return any(_bin(b) for b in ("amixer", "pactl", "pulseaudio", "pipewire",
                                 "wpctl", "pw-dump"))


def _expect_battery():
    for name in _listdir("/sys/class/power_supply"):
        path = os.path.join("/sys/class/power_supply", name, "type")
        try:
            with open(path) as f:
                if f.read().strip().lower() == "battery":
                    return True
        except OSError:
            continue
    return False


def _expect_governor():
    base = "/sys/devices/system/cpu"
    for name in _listdir(base):
        if name.startswith("cpu") and name[3:].isdigit():
            if os.path.isfile(os.path.join(base, name, "cpufreq",
                                          "scaling_governor")):
                return True
    return False


EXPECT = {
    "Wi-Fi": _expect_wifi,
    "Bluetooth": _expect_bluetooth,
    "Brilho": _expect_brightness,
    "Volume": _expect_volume,
    "Bateria": _expect_battery,
    "Energia": _expect_governor,
}


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def make_surface(w=1920, h=1080):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    return surface, ctx, Painter(ctx, Theme("neon"))


def tap(p, x, y, kinds=("down", "up")):
    for kind in kinds:
        ev = TouchEvent(kind, x, y)
        p.on_touch(ev)


class _StubSysInfo(object):
    """nura_sysinfo minimo, usado quando o modulo real nao existe.

    Devolve apenas dados minimos e coerentes — o resto e None/vazio
    (nenhum valor inventado).
    """

    def kernel_info(self):
        return {"release": "test-kernel", "version": "test",
                "machine": "aarch64", "proc_version": None}

    def os_info(self):
        return {"NAME": "NURA Test", "PRETTY_NAME": "NURA Test"}

    def ram_info(self):
        return {"total_kb": 1048576, "free_kb": 524288,
                "available_kb": 524288, "used_kb": 524288,
                "used_pct": 50.0, "cached_kb": 0,
                "swap_total_kb": 0, "swap_free_kb": 0}

    def uptime(self):
        return {"uptime_s": 3600.0, "idle_s": 100.0, "sessions": 42}

    def battery(self):
        return None

    def cpu_usage(self, prev=None):
        return {"total": 0.25, "per_core": [0.25]}

    def cpu_freq(self):
        return []

    def cpu_governor(self):
        return []

    def storage_info(self, path="/"):
        return {"total": 1000000, "used": 400000, "free": 600000,
                "used_pct": 40.0, "mount": "/"}

    def processes(self, limit=50):
        return []

    def thermal_zones(self):
        return []

    def drm_info(self):
        return []

    def loadavg(self):
        return {"1": 0.1, "5": 0.2, "15": 0.3}


def by_name(controls):
    return {c.name: c for c in controls}


def build_fake_sysfs(base):
    """Arvore de /sys falsa: cria Wi-Fi, backlight, bateria e cpufreq.

    Serve para exercitar os botoes (toggle/slider) mesmo num sistema
    que nao tem nenhum desses recursos (WSL, por exemplo).
    """
    def write(path, content):
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(path, "w") as f:
            f.write(content)

    net = os.path.join(base, "class", "net", "wlan0")
    os.makedirs(net)
    write(os.path.join(net, "operstate"), "up\n")

    back = os.path.join(base, "class", "backlight", "panel0")
    write(os.path.join(back, "brightness"), "120\n")
    write(os.path.join(back, "max_brightness"), "255\n")

    bat = os.path.join(base, "class", "power_supply", "battery")
    write(os.path.join(bat, "type"), "Battery\n")
    write(os.path.join(bat, "capacity"), "77\n")
    write(os.path.join(bat, "status"), "Discharging\n")
    write(os.path.join(bat, "temp"), "410\n")

    cdir = os.path.join(base, "devices", "system", "cpu", "cpu0", "cpufreq")
    write(os.path.join(cdir, "scaling_governor"), "schedutil\n")
    write(os.path.join(cdir, "scaling_available_governors"),
          "performance powersave schedutil\n")
    write(os.path.join(cdir, "scaling_cur_freq"), "1400000\n")
    return base


# ----------------------------------------------------------------------
# testes
# ----------------------------------------------------------------------

def test_apps_instantiate():
    print("\n=== instancia dos apps ===")
    app = ControlCenterApp()
    check("ControlCenterApp: instancia", app is not None)
    check("ControlCenterApp: title", app.title == "NURA Control Center",
          repr(app.title))
    check("ControlCenterApp: icon", app.icon == "cpu", repr(app.icon))
    check("ControlCenterApp: 860x640",
          (app.width, app.height) == (860, 640), repr((app.width, app.height)))
    check("ControlCenterApp: min 520x420",
          (app.min_width, app.min_height) == (520, 420),
          repr((app.min_width, app.min_height)))

    perf = PerformanceApp()
    check("PerformanceApp: instancia", perf is not None)
    check("PerformanceApp: title", perf.title == "NURA Performance",
          repr(perf.title))
    check("PerformanceApp: icon", perf.icon == "ram", repr(perf.icon))
    check("PerformanceApp: 980x680",
          (perf.width, perf.height) == (980, 680),
          repr((perf.width, perf.height)))
    check("PerformanceApp: min 560x420",
          (perf.min_width, perf.min_height) == (560, 420),
          repr((perf.min_width, perf.min_height)))
    check("PerformanceApp: intervalo de 2 s documentado",
          perf.refresh_interval == 2.0, repr(perf.refresh_interval))
    check("PerformanceApp: historico de 60 amostras",
          perf.cpu_history.maxlen == 60 and len(perf.cpu_history) <= 60,
          repr(perf.cpu_history.maxlen))


def test_draw_cairo():
    print("\n=== desenho num contexto cairo 1920x1080 ===")
    surface, ctx, painter = make_surface()
    app = ControlCenterApp()
    try:
        app.draw(painter)
        ok = True
        detail = ""
    except Exception as exc:
        ok = False
        detail = "%s: %s" % (type(exc).__name__, exc)
    check("ControlCenterApp.draw nao lanca", ok, detail)

    perf = PerformanceApp()
    try:
        perf.draw(painter)
        ok = True
        detail = ""
    except Exception as exc:
        ok = False
        detail = "%s: %s" % (type(exc).__name__, exc)
    check("PerformanceApp.draw nao lanca", ok, detail)

    panel = ControlPanel(shell=None, x=0, y=0, w=460, h=1080)
    try:
        panel.draw(painter)
        ok = True
        detail = ""
    except Exception as exc:
        ok = False
        detail = "%s: %s" % (type(exc).__name__, exc)
    check("ControlPanel.draw nao lanca", ok, detail)
    check("ControlPanel: retangulo conhecido",
          panel.rect() == (0, 0, 460, 1080), repr(panel.rect()))


def test_touch_random():
    print("\n=== toques aleatorios (50 pontos) ===")
    rnd = random.Random(20241113)
    surface, ctx, painter = make_surface()

    app = ControlCenterApp()
    perf = PerformanceApp()
    panel = ControlPanel(shell=None, x=1400, y=0, w=460, h=1080)
    app.draw(painter)
    perf.draw(painter)
    panel.draw(painter)

    erro = ""
    try:
        for _ in range(50):
            x = rnd.uniform(0, 1920)
            y = rnd.uniform(0, 1080)
            tap(app, x, y)
            tap(perf, x, y)
            tap(panel, x, y)
    except Exception as exc:
        erro = "%s: %s" % (type(exc).__name__, exc)
    check("50 pontos aleatorios no app/painel sem excecao", not erro, erro)

    # toques com todos os tipos de evento
    erro = ""
    try:
        for kind in ("down", "move", "up", "cancel", "scroll", "drag",
                     "longpress", "pinch"):
            ev = TouchEvent(kind, 900, 400)
            app.on_touch(ev)
            perf.on_touch(ev)
            panel.on_touch(ev)
    except Exception as exc:
        erro = "%s: %s" % (type(exc).__name__, exc)
    check("todos os tipos de evento sem excecao", not erro, erro)


def test_touch_targets():
    print("\n=== alvos de toque >= 44px ===")
    surface, ctx, painter = make_surface()
    tmp = tempfile.mkdtemp(prefix="nura-cc-")
    try:
        fake = build_fake_sysfs(os.path.join(tmp, "sys"))
        app = ControlCenterApp(shell=None, root=fake,
                               sysinfo=_StubSysInfo())
        app.draw(painter)
        deck = app.deck
        check("deck: ha botoes posicionados", len(deck.hits) > 0,
              repr(len(deck.hits)))
        pequenos = []
        for kind, ctrl, rect in deck.hits:
            if rect[2] < 44 or rect[3] < 44:
                pequenos.append((ctrl.name, kind, rect))
        check("todo alvo tem >= 44x44 px", not pequenos, repr(pequenos))

        # tocar de verdade em cada botao (sem o botao de governor, que
        # escreveria no /sys do host)
        erro = ""
        try:
            for kind, ctrl, rect in list(deck.hits):
                if kind == "button":
                    continue
                cx = rect[0] + rect[2] / 2.0
                cy = rect[1] + rect[3] / 2.0
                tap(app, cx, cy)
        except Exception as exc:
            erro = "%s: %s" % (type(exc).__name__, exc)
        check("tocar em cada botao nao lanca", not erro, erro)

        # sliders: o valor visual muda ao tocar (feedback imediato)
        sliders = [h for h in deck.hits if h[0] == "slider"]
        check("existe um slider (brilho) para testar", len(sliders) > 0,
              repr(len(sliders)))
        if sliders:
            kind, ctrl, rect = sliders[0]
            before = ctrl.value_num
            tap(app, rect[0] + rect[2] * 0.75, rect[1] + rect[3] / 2.0,
                kinds=("down",))
            check("slider responde ao toque (feedback imediato)",
                  ctrl.value_num != before,
                  "antes=%r depois=%r" % (before, ctrl.value_num))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_detection_real():
    print("\n=== deteccao de disponibilidade (comparada ao sistema real) ===")
    controls = build_controls(cc.SysInfo() if cc.SysInfo else None)
    mapa = by_name(controls)
    check("8 controles construidos", len(controls) == 8, repr(len(controls)))

    for nome, func in EXPECT.items():
        ctrl = mapa.get(nome)
        if ctrl is None:
            check("controle %s existe" % nome, False)
            continue
        esperado = bool(func())
        check("%s: available bate com a existencia real (%s)" %
              (nome, "presente" if esperado else "ausente"),
              ctrl.available == esperado,
              "available=%r esperado=%r reason=%r" % (ctrl.available, esperado,
                                                      ctrl.reason))
        if not ctrl.available:
            check("%s: indisponivel mostra o motivo" % nome,
                  bool(ctrl.reason), repr(ctrl.reason))
            check("%s: valor e 'indisponivel'" % nome,
                  ctrl.value == "indisponivel", repr(ctrl.value))
        else:
            check("%s: nao aparece como 'indisponivel'" % nome,
                  ctrl.value != "indisponivel", repr(ctrl.value))

    # os controles que dependem do hardware
    check("Wi-Fi: probe devolve interface ou ferramentas",
          probe_wifi()["available"] == _expect_wifi())
    check("Brilho: probe bate com /sys/class/backlight",
          probe_brightness()["available"] == _expect_brightness())
    check("Volume: probe bate com ALSA/Pulse",
          probe_volume()["available"] == _expect_volume())
    check("Bateria: probe bate com power_supply",
          probe_battery()["available"] == _expect_battery())
    check("Energia: probe bate com cpufreq",
          probe_governor()["available"] == _expect_governor())


def test_sysinfo_ausente():
    print("\n=== SysInfo ausente: nada aparece como 'ligado' ===")
    app = ControlCenterApp(shell=None, sysinfo=None)
    mapa = by_name(app.controls)
    # "Orientacao" e um fato fixo do NURA (paisagem), nao uma metrica do
    # sistema: continua visivel, mas sem nenhuma acao.
    dependentes = [c for c in app.controls if c.name != "Orientacao"]
    check("nenhum controle de sistema disponivel sem o modulo",
          all(not c.available for c in dependentes),
          repr([(c.name, c.available) for c in dependentes]))
    check("Orientacao continua informacao (paisagem fixa)",
          mapa["Orientacao"].available is True)
    check("Orientacao nao tem acao",
          mapa["Orientacao"].action is None)
    for nome in ("Wi-Fi", "Bluetooth", "Brilho", "Volume"):
        ctrl = mapa[nome]
        check("%s: available False sem sysinfo" % nome,
              ctrl.available is False, repr(ctrl.available))
        check("%s: NAO aparece como 'ligado'" % nome,
              ctrl.value != "ligado" and ctrl.state is not True,
              "value=%r state=%r" % (ctrl.value, ctrl.state))
        check("%s: motivo menciona o modulo de sistema" % nome,
              "modulo de sistema indisponivel" in ctrl.reason,
              repr(ctrl.reason))
        check("%s: sem acao quando indisponivel" % nome,
              ctrl.action is None, repr(ctrl.action))

    check("o painel avisa que o modulo de sistema esta indisponivel",
          app.deck.module_missing() is True)
    check("o painel mostra a faixa de aviso",
          app.deck.banner_h() > 0, repr(app.deck.banner_h()))

    # caminho alternativo: o modulo global foi substituido por None
    original = cc.SysInfo
    original_perf = perf_mod.SysInfo
    try:
        cc.SysInfo = None
        perf_mod.SysInfo = None
        app2 = ControlCenterApp(shell=None)
        check("SysInfo=None no modulo: app abre sem quebrar",
              app2 is not None)
        check("SysInfo=None no modulo: tudo de sistema indisponivel",
              all(not c.available for c in app2.controls
                  if c.name != "Orientacao"),
              repr([(c.name, c.available) for c in app2.controls]))
        check("SysInfo=None no modulo: nenhum 'ligado'",
              all(c.state is not True for c in app2.controls))
        perf = PerformanceApp(shell=None)
        check("Performance com SysInfo=None mostra aviso",
              perf.module_missing is True, repr(perf.module_missing))
        surface, ctx, painter = make_surface()
        perf.draw(painter)
        check("Performance com SysInfo=None desenha sem excecao", True)
    finally:
        cc.SysInfo = original
        perf_mod.SysInfo = original_perf


def test_tick_periodico():
    print("\n=== atualizacao periodica (nao a cada quadro) ===")
    perf = PerformanceApp(shell=None, sysinfo=None)
    antes = perf.update_count
    for _ in range(60):
        perf.on_tick(0.016)          # ~1 s de quadros a 60 Hz
    check("60 quadros de 16 ms nao coletam (ainda nao passou de 2 s)",
          perf.update_count == antes,
          "delta=%d" % (perf.update_count - antes))

    antes = perf.update_count
    perf.on_tick(10.0)               # um quadro muito longo
    check("dt grande dispara UMA coleta (nao uma por intervalo)",
          perf.update_count == antes + 1,
          "delta=%d" % (perf.update_count - antes))

    antes = perf.update_count
    for _ in range(130):
        perf.on_tick(0.016)          # ~2.08 s
    check("2 s de quadros coletam uma vez",
          perf.update_count == antes + 1,
          "delta=%d" % (perf.update_count - antes))

    # o painel lateral tambem nao coleta a cada quadro
    deck = cc.ControlDeck(shell=None, sysinfo=None)
    antes = deck.update_count
    for _ in range(60):
        deck.on_tick(0.016)
    check("ControlDeck: 60 quadros nao reavaliam (intervalo de 5 s)",
          deck.update_count == antes,
          "delta=%d" % (deck.update_count - antes))
    antes = deck.update_count
    deck.on_tick(30.0)
    check("ControlDeck: dt grande reavalia uma vez",
          deck.update_count == antes + 1,
          "delta=%d" % (deck.update_count - antes))


def test_erro_real_de_escrita():
    print("\n=== erro real de escrita (EACCES/EPERM) ===")
    # caminho inexistente: o open() falha e o erro tem de aparecer
    probe = {"cpus": [{"name": "cpu0",
                        "gov_path": "/proc/nura-nao-existe/scaling_governor"}],
             "governors": ["performance", "powersave"],
             "current": "performance"}
    action = cc._governor_action(probe)
    check("governor: acao existe", action is not None)
    result = action()
    check("governor: erro real devolvido", bool(result) and
          "erro" in result.lower(), repr(result))

    # arvore falsa: o governor existe mas a escrita falha
    tmp = tempfile.mkdtemp(prefix="nura-cc-")
    try:
        cdir = os.path.join(tmp, "devices", "system", "cpu", "cpu0", "cpufreq")
        os.makedirs(cdir)
        gov_path = os.path.join(cdir, "scaling_governor")
        with open(gov_path, "w") as f:
            f.write("schedutil\n")
        with open(os.path.join(cdir, "scaling_available_governors"), "w") as f:
            f.write("performance powersave schedutil\n")
        det = probe_governor(root=tmp)
        check("governor: probe le a arvore falsa", det["available"] is True,
              repr(det))
        check("governor: lista de governors reais",
              det["governors"] == ["performance", "powersave", "schedutil"],
              repr(det["governors"]))
        check("governor: governor atual lido", det["current"] == "schedutil",
              repr(det["current"]))
        os.chmod(gov_path, 0o444)
        if os.geteuid() != 0:
            act = cc._governor_action(det)
            res = act()
            check("governor: erro de permissao mostrado",
                  bool(res) and "erro" in res.lower(), repr(res))
        else:
            print("  [ -- ] governor: rodando como root, "
                  "teste de permissao ignorado")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # brilho: caminho inexistente -> erro honesto
    bri = cc._brightness_action({"path": "/proc/nura-nao-existe/brightness",
                                 "max": 255})
    res = bri(50.0)
    check("brilho: erro real devolvido", bool(res) and "erro" in res.lower(),
          repr(res))

    # volume sem ALSA: nao ha acao (nao existe botao ficticio)
    sem_alisa = cc._volume_action({"tools": {}})
    check("volume sem mixer: nenhuma acao", sem_alisa is None,
          repr(sem_alisa))
    sem_wifi = cc._wifi_action({"tools": {}, "iface": None})
    check("wi-fi sem gerenciador: nenhuma acao", sem_wifi is None,
          repr(sem_wifi))

    # o erro tem de continuar visivel NO CARTAO depois da reavaliacao
    tmp = tempfile.mkdtemp(prefix="nura-cc-")
    try:
        fake = build_fake_sysfs(os.path.join(tmp, "sys"))
        deck = cc.ControlDeck(shell=None, root=fake,
                              sysinfo=_StubSysInfo())
        bri = by_name(deck.controls)["Brilho"]
        bri.action = lambda pct: "erro: escrita negada (EACCES)"
        deck._commit_slider(bri)
        novo = by_name(deck.controls)["Brilho"]
        check("erro continua no cartao depois da reavaliacao",
              "erro" in novo.error.lower(), repr(novo.error))
        check("erro aparece no status do painel",
              "erro" in deck.status.lower(), repr(deck.status))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_estrutura_dos_controles():
    print("\n=== estrutura dos controles ===")
    controls = build_controls(cc.SysInfo() if cc.SysInfo else None)
    ok = True
    detalhe = ""
    for ctrl in controls:
        for attr in ("name", "icon", "available", "reason", "value", "action",
                     "kind"):
            if not hasattr(ctrl, attr):
                ok = False
                detalhe = "%s sem %s" % (ctrl.name, attr)
        if ctrl.kind not in Control.KINDS:
            ok = False
            detalhe = "kind invalido: %r" % ctrl.kind
        if not isinstance(ctrl.available, bool):
            ok = False
            detalhe = "available nao e bool"
        if ctrl.available and ctrl.action is None and ctrl.kind != "info":
            detalhe += " | %s: disponivel sem acao" % ctrl.name
    check("todos os controles tem os atributos exigidos", ok, detalhe)

    nomes = [c.name for c in controls]
    for nome in ("Wi-Fi", "Bluetooth", "Brilho", "Volume", "Bateria",
                 "Energia", "Orientacao", "Sistema"):
        check("controle %s presente" % nome, nome in nomes, repr(nomes))

    orient = by_name(controls)["Orientacao"]
    check("orientacao: e paisagem fixa", "Paisagem" in orient.value,
          repr(orient.value))
    check("orientacao: nao finge alternar", orient.action is None)
    check("orientacao: explica a rotacao por software",
          "software" in orient.detail.lower(), repr(orient.detail))


# ----------------------------------------------------------------------

def main():
    print("NURA OS — teste do Control Center e do Performance")
    test_apps_instantiate()
    test_draw_cairo()
    test_touch_random()
    test_touch_targets()
    test_detection_real()
    test_sysinfo_ausente()
    test_tick_periodico()
    test_erro_real_de_escrita()
    test_estrutura_dos_controles()

    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS (%d): %s" % (len(falhas), falhas)))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
