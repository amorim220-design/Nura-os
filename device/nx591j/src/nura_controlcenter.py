#!/usr/bin/env python3
"""NURA OS — NURA Control Center (painel de configuracoes rapidas).

Painel touch-first de configuracao rapida do NURA OS (Nubia NX591J como
desktop em paisagem 1920x1080).

REGRA DE OURO: nenhum controle e ficticio. Antes de desenhar um botao o
painel verifica se o recurso existe DE VERDADE no sistema:

    Wi-Fi      /sys/class/net/wlan*, iw, rfkill,
               wpa_supplicant/connman/NetworkManager
    Bluetooth  /sys/class/bluetooth/hci*, bluetoothd/bluez/rfkill
    Brilho     /sys/class/backlight/*/brightness
    Volume     /proc/asound, amixer, pulseaudio/pipewire
    Bateria    /sys/class/power_supply/* (type=Battery)
    Energia    /sys/devices/system/cpu/cpu*/cpufreq/scaling_available_governors
    Orientacao sempre presente (o NURA e paisagem fixa)
    Sistema    kernel / SoC / RAM / uptime (via nura_sysinfo)

Se o recurso nao existe, o cartao aparece cinza, com o texto
"indisponivel" e o motivo real ao lado. Nenhum valor e inventado e
nenhuma acao destrutiva e executada (sem sudo).

O modulo `nura_sysinfo` e opcional: se ele nao carregar, o app abre
normal e mostra "modulo de sistema indisponivel" — sem quebrar.

Uso no shell (painel lateral na area de trabalho):

    from nura_controlcenter import ControlPanel
    panel = ControlPanel(shell=shell, x=0, y=0, w=460, h=1080)
    panel.draw(p)
    panel.on_touch(ev)          # ev.x/ev.y ja em paisagem
"""

import os
import re
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import nura_theme as T                        # noqa: E402
from nura_window import App, Widget           # noqa: E402

try:                                         # modulo de metricas (opcional)
    from nura_sysinfo import SysInfo
except ImportError:                          # pragma: no cover
    SysInfo = None


# --------------------------------------------------------------------
# constantes
# --------------------------------------------------------------------

SYS_ROOT = "/sys"
PROC_ROOT = "/proc"

#: intervalo (s) entre duas reavaliacoes automaticas dos controles
REFRESH_INTERVAL = 5.0

#: alvo minimo de toque (regra da API: 44x44 px logicos)
MIN_TOUCH = 44

_AUTO = object()


# --------------------------------------------------------------------
# helpers de leitura do sistema
# --------------------------------------------------------------------

def _read_text(path):
    """Le um texto. Devolve None se nao existir/nao puder ler."""
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except (OSError, IOError, ValueError):
        return None


def _read_int(path):
    """Le um inteiro. Devolve None se nao existir."""
    text = _read_text(path)
    if not text:
        return None
    token = text.strip().split()
    if not token:
        return None
    try:
        return int(token[0])
    except ValueError:
        try:
            return int(float(token[0]))
        except ValueError:
            return None


def _read_str(path):
    """Le uma linha. Devolve None se nao existir ou estiver vazia."""
    text = _read_text(path)
    if text is None:
        return None
    text = text.strip()
    return text or None


def _listdir(path):
    """Lista um diretorio (ordenado). Devolve [] se nao existir."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


#: PATH do sistema (rapido). O PATH completo pode conter diretorios
#: montados/slow (rede, /mnt/c) — procura la em segundo lugar.
_FAST_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

#: cache dos executaveis ja procurados (a lista de ferramentas do
#: sistema nao muda durante a execucao e a busca e lenta).
_BIN_CACHE = {}


def _find_bin(name):
    """Acha um executavel no PATH ou nos diretorios de sistema.

    Devolve o caminho ou None. Nao executa nada. O resultado e
    memorizado: procurar binarios em toda a particao e lento.
    """
    if name in _BIN_CACHE:
        return _BIN_CACHE[name]
    found = shutil.which(name, path=_FAST_PATH)
    if not found:
        found = shutil.which(name)
    if not found:
        for folder in ("/usr/local/sbin", "/usr/local/bin", "/usr/sbin",
                       "/usr/bin", "/sbin", "/bin", "/libexec"):
            cand = os.path.join(folder, name)
            try:
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    found = cand
                    break
            except OSError:
                continue
    _BIN_CACHE[name] = found
    return found


def _run(args, timeout=4.0):
    """Executa um comando (sem shell, sem sudo).

    Devolve (codigo, stdout, stderr). Nunca levanta excecao.
    """
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        return 127, "", "%s: executavel nao encontrado" % args[0]
    except subprocess.TimeoutExpired:
        return 124, "", "%s: tempo esgotado" % args[0]
    except OSError as exc:
        return 1, "", "%s: %s" % (args[0], exc)
    out = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
    err = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
    return proc.returncode, out, err


def _human_bytes(n):
    """Formata bytes em KB/MB/GB. '-' quando o valor nao existe."""
    if n is None:
        return "-"
    try:
        value = float(n)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0 or unit == "TB":
            if unit == "B":
                return "%d %s" % (int(value), unit)
            return "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%.1f TB" % value


def _human_kb(kb):
    """Formata kB (como o /proc/meminfo) em KB/MB/GB."""
    if kb is None:
        return "-"
    return _human_bytes(float(kb) * 1024.0)


def _human_duration(seconds):
    """Formata segundos em 'Xd Yh Zmin'. '-' quando nao existe."""
    if seconds is None:
        return "-"
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return "%dd %dh %dmin" % (days, hours, minutes)
    if hours:
        return "%dh %dmin" % (hours, minutes)
    return "%dmin %ds" % (minutes, rem % 60)


# --------------------------------------------------------------------
# deteccao de recursos (somente leitura — nada e executado aqui)
# --------------------------------------------------------------------

def _rfkill_state(root, kind):
    """Estado do rfkill para 'wlan'/'bluetooth'.

    Devolve True (bloqueado por software), False (liberado) ou None
    (nao ha rfkill para esse tipo / estado ilegivel).
    """
    base = os.path.join(root, "class", "rfkill")
    for name in _listdir(base):
        if not name.startswith("rfkill"):
            continue
        d = os.path.join(base, name)
        if not os.path.isdir(d):
            continue
        if (_read_str(os.path.join(d, "type")) or "").lower() != kind:
            continue
        soft = (_read_str(os.path.join(d, "soft")) or "").strip()
        if soft == "1":
            return True
        if soft == "0":
            return False
    return None


def probe_wifi(root=SYS_ROOT):
    """Detecta se existe Wi-Fi de verdade.

    Devolve dict com: available, reason, iface, tools, state, detail.
    'state' e True (ligado), False (desligado) ou None (desconhecido).
    """
    netdir = os.path.join(root, "class", "net")
    iface = None
    for name in _listdir(netdir):
        d = os.path.join(netdir, name)
        if not os.path.isdir(d):
            continue
        if name.startswith("wlan"):
            iface = name
            break
    if iface is None:
        for name in _listdir(netdir):
            d = os.path.join(netdir, name)
            if os.path.isdir(os.path.join(d, "wireless")):
                iface = name
                break

    tools = {}
    for name in ("iw", "rfkill", "wpa_supplicant", "wpa_cli", "connmanctl",
                 "connmand", "nmcli", "NetworkManager"):
        path = _find_bin(name)
        if path:
            tools[name] = path

    blocked = _rfkill_state(root, "wlan")
    state = None
    detail = ""
    if iface:
        oper = _read_str(os.path.join(netdir, iface, "operstate")) or ""
        if blocked is True:
            state = False
            detail = "interface %s bloqueada por software (rfkill)" % iface
        elif oper == "up":
            state = True
            detail = "interface %s ativa" % iface
        elif oper == "down":
            state = False
            detail = "interface %s ociosa" % iface
        else:
            detail = ("interface %s presente (operstate=%s)"
                      % (iface, oper or "?"))
    elif blocked is not None:
        state = not blocked
        detail = "rfkill presente (%s)" % ("bloqueado" if blocked
                                           else "liberado")

    available = iface is not None or bool(tools)
    reason = ""
    if not available:
        reason = ("nenhuma interface Wi-Fi em %s e nenhum gerenciador "
                  "(iw/rfkill/NetworkManager/wpa_supplicant)" % netdir)
    return {"available": available, "reason": reason, "iface": iface,
            "tools": tools, "state": state, "detail": detail}


def probe_bluetooth(root=SYS_ROOT):
    """Detecta se existe Bluetooth de verdade."""
    base = os.path.join(root, "class", "bluetooth")
    devices = []
    if os.path.isdir(base):
        for name in _listdir(base):
            if not name.startswith("hci"):
                continue
            if os.path.isdir(os.path.join(base, name)):
                devices.append(name)

    tools = {}
    for name in ("bluetoothctl", "bluetoothd", "hciconfig", "rfkill",
                 "bluez"):
        path = _find_bin(name)
        if path:
            tools[name] = path

    blocked = _rfkill_state(root, "bluetooth")
    state = None
    detail = ""
    if blocked is True:
        state = False
        detail = "bloqueado por software (rfkill)"
    elif devices:
        state = True
        detail = "adaptadores: %s" % ", ".join(devices)
    elif blocked is False:
        state = True
        detail = "rfkill liberado, nenhum adaptador exposto"

    available = os.path.isdir(base) or bool(devices) or bool(tools)
    reason = ""
    if not available:
        reason = ("sem /sys/class/bluetooth, sem adaptador hci* e sem "
                  "bluetoothd/bluez")
    return {"available": available, "reason": reason, "devices": devices,
            "tools": tools, "state": state, "detail": detail}


def probe_brightness(root=SYS_ROOT):
    """Detecta backlight (controle de brilho) de verdade."""
    base = os.path.join(root, "class", "backlight")
    found = None
    for name in _listdir(base):
        d = os.path.join(base, name)
        bright = os.path.join(d, "brightness")
        maxb = os.path.join(d, "max_brightness")
        if os.path.isfile(bright) and os.path.isfile(maxb):
            found = (name, bright, maxb)
            break

    if not found:
        return {"available": False,
                "reason": ("nenhum backlight em %s (sem controle de "
                           "brilho)" % base),
                "path": None, "current": None, "max": None}

    name, bright, maxb = found
    current = _read_int(bright)
    maximum = _read_int(maxb)
    if not maximum:
        maximum = current
    return {"available": True, "reason": "", "path": bright,
            "device": name, "current": current, "max": maximum}


def probe_volume(root=SYS_ROOT, proc=PROC_ROOT):
    """Detecta controle de volume de verdade (ALSA / Pulse / PipeWire)."""
    asound = os.path.join(proc, "asound")
    has_alsa = os.path.isdir(asound)
    tools = {}
    for name in ("amixer", "pactl", "pulseaudio", "pipewire", "wpctl",
                 "pw-dump"):
        path = _find_bin(name)
        if path:
            tools[name] = path

    available = has_alsa or bool(tools)
    reason = ""
    if not available:
        reason = ("sem ALSA (/proc/asound) e sem amixer/pulseaudio/pipewire")

    percent = None
    muted = None
    detail = ""
    if "amixer" in tools:
        rc, out, err = _run([tools["amixer"], "-M", "master", "get", "Master"],
                            timeout=3.0)
        if rc == 0 and out:
            m = re.search(r"\[(\d+)%\]", out)
            if m:
                percent = int(m.group(1))
            m2 = re.search(r"\[(on|off|muted)\]", out)
            if m2:
                muted = (m2.group(1) == "on")
            detail = "ALSA (amixer)"
        else:
            detail = "ALSA (amixer)"
    elif "pactl" in tools:
        rc, out, err = _run([tools["pactl"], "get-sink-volume",
                             "@DEFAULT_SINK@"], timeout=3.0)
        if rc == 0 and out:
            m = re.search(r"(\d+)%", out)
            if m:
                percent = int(m.group(1))
            muted = "Mute: no" in out or "Mute: yes" not in out
            detail = "PulseAudio/PipeWire (pactl)"
    elif has_alsa:
        detail = "ALSA (sem mixer de linha de comando)"

    state = None
    if muted is not None:
        state = bool(muted)
    return {"available": available, "reason": reason, "tools": tools,
            "percent": percent, "muted": muted, "detail": detail,
            "has_alsa": has_alsa}


def probe_battery(root=SYS_ROOT):
    """Detecta bateria de verdade (/sys/class/power_supply, type=Battery)."""
    base = os.path.join(root, "class", "power_supply")
    for name in _listdir(base):
        d = os.path.join(base, name)
        if not os.path.isdir(d):
            continue
        if (_read_str(os.path.join(d, "type")) or "").lower() != "battery":
            continue
        capacity = _read_int(os.path.join(d, "capacity"))
        temp = _read_int(os.path.join(d, "temp"))
        voltage = _read_int(os.path.join(d, "voltage_now"))
        current = _read_int(os.path.join(d, "current_now"))
        power = _read_int(os.path.join(d, "power_now"))
        return {
            "available": True, "reason": "", "name": name, "path": d,
            "capacity": capacity,
            "status": _read_str(os.path.join(d, "status")),
            "health": _read_str(os.path.join(d, "health")),
            "present": _read_str(os.path.join(d, "present")),
            "temp_c": (float(temp) / 10.0) if temp is not None else None,
            "voltage_v": ((float(voltage) / 1e6)
                          if voltage is not None else None),
            "current_a": ((float(current) / 1e6)
                          if current is not None else None),
            "power_w": (float(power) / 1e6) if power is not None else None,
        }
    return {"available": False,
            "reason": "nenhuma bateria em %s (type=Battery)" % base,
            "name": None, "capacity": None, "status": None, "health": None,
            "present": None, "temp_c": None, "voltage_v": None,
            "current_a": None, "power_w": None}


def probe_governor(root=SYS_ROOT):
    """Detecta os governors de CPU disponiveis (cpufreq)."""
    base = os.path.join(root, "devices", "system", "cpu")
    cpus = []
    for name in _listdir(base):
        if not re.match(r"^cpu\d+$", name):
            continue
        cdir = os.path.join(base, name, "cpufreq")
        gov_path = os.path.join(cdir, "scaling_governor")
        if not os.path.isfile(gov_path):
            continue
        avail_file = os.path.join(cdir, "scaling_available_governors")
        available = (_read_str(avail_file) or "").split()
        cpus.append({"name": name, "dir": cdir, "gov_path": gov_path,
                     "current": _read_str(gov_path),
                     "available": available})

    if not cpus:
        return {"available": False,
                "reason": "nenhum driver cpufreq em %s" % base,
                "cpus": [], "governors": [], "current": None}

    governors = []
    for cpu in cpus:
        for gov in cpu["available"]:
            if gov not in governors:
                governors.append(gov)
    currents = [c["current"] for c in cpus if c["current"]]
    current = currents[0] if currents else None
    return {"available": True, "reason": "", "cpus": cpus,
            "governors": governors, "current": current}


def probe_soc(proc=PROC_ROOT):
    """Tenta identificar o SoC (device-tree, cpuinfo, uname)."""
    model = _read_text(os.path.join(proc, "device-tree", "model"))
    if model:
        model = model.replace("\x00", " ").strip()
        if model:
            return model
    text = _read_text(os.path.join(proc, "cpuinfo")) or ""
    for key in ("Hardware", "model name", "Model"):
        m = re.search(r"^%s\s*:\s*(.+)$" % re.escape(key), text, re.M)
        if m:
            return m.group(1).strip()
    try:
        return os.uname().machine
    except (AttributeError, OSError):
        return None


def probe_system(si):
    """Informacoes do sistema via nura_sysinfo (None se nao houver)."""
    if si is None:
        return {"available": False,
                "reason": "modulo de sistema indisponivel",
                "kernel": None, "os": None, "soc": None, "ram": None,
                "uptime": None, "lines": []}

    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    kernel = _safe(lambda: si.kernel_info() or {})
    osinfo = _safe(lambda: si.os_info() or {})
    ram = _safe(si.ram_info)
    uptime = _safe(si.uptime)

    rel = kernel.get("release") if isinstance(kernel, dict) else None
    distro = None
    if isinstance(osinfo, dict):
        distro = (osinfo.get("PRETTY_NAME") or osinfo.get("NAME") or
                  osinfo.get("ID"))
    soc = probe_soc()

    lines = []
    if rel:
        lines.append("kernel: %s" % rel)
    if distro:
        lines.append("distro: %s" % distro)
    if soc:
        lines.append("SoC: %s" % soc)
    if isinstance(ram, dict) and ram.get("total_kb"):
        lines.append("RAM: %s (usado %s)" % (_human_kb(ram.get("total_kb")),
                                            _human_kb(ram.get("used_kb"))))
    if isinstance(uptime, dict) and uptime.get("uptime_s") is not None:
        lines.append("uptime: %s" % _human_duration(uptime.get("uptime_s")))

    value = distro or rel or "informacoes indisponiveis"
    return {"available": bool(lines), "reason": "" if lines else
            "nenhuma informacao de sistema disponivel",
            "kernel": kernel, "os": osinfo, "soc": soc, "ram": ram,
            "uptime": uptime, "lines": lines, "value": value}


# --------------------------------------------------------------------
# acoes (executam comandos reais; nunca usam sudo)
# --------------------------------------------------------------------

def _wifi_action(probe):
    """Acao de alternar o Wi-Fi (nmcli > connmanctl > rfkill)."""
    tools = probe.get("tools") or {}
    iface = probe.get("iface") or "wlan0"

    if "nmcli" in tools:
        def act():
            want = not probe.get("state")
            rc, out, err = _run([tools["nmcli"], "radio", "wifi",
                                 "on" if want else "off"])
            if rc != 0:
                return "erro: nmcli radio wifi %s falhou (codigo %d): %s" % (
                    "on" if want else "off", rc,
                    (err or out).strip()[:160] or "sem mensagem")
            return None
        return act

    if "connmanctl" in tools:
        def act():
            want = not probe.get("state")
            rc, out, err = _run([tools["connmanctl"],
                                 "enable" if want else "disable", "wifi"])
            if rc != 0:
                return "erro: connmanctl %s wifi falhou (codigo %d): %s" % (
                    "enable" if want else "disable", rc,
                    (err or out).strip()[:160] or "sem mensagem")
            return None
        return act

    if "rfkill" in tools and probe.get("iface"):
        def act():
            want = not probe.get("state")
            rc, out, err = _run([tools["rfkill"],
                                 "unblock" if want else "block", iface])
            if rc != 0:
                return "erro: rfkill %s %s falhou (codigo %d): %s" % (
                    "unblock" if want else "block", iface, rc,
                    (err or out).strip()[:160] or "sem mensagem")
            return None
        return act
    return None


def _bluetooth_action(probe):
    """Acao de alternar o Bluetooth (bluetoothctl > rfkill)."""
    tools = probe.get("tools") or {}

    if "bluetoothctl" in tools:
        def act():
            want = not probe.get("state")
            rc, out, err = _run([tools["bluetoothctl"], "power",
                                 "on" if want else "off"], timeout=6.0)
            if rc != 0:
                return "erro: bluetoothctl power %s falhou (codigo %d): %s" % (
                    "on" if want else "off", rc,
                    (err or out).strip()[:160] or "sem mensagem")
            return None
        return act

    if "rfkill" in tools:
        def act():
            want = not probe.get("state")
            rc, out, err = _run([tools["rfkill"],
                                 "unblock" if want else "block", "bluetooth"])
            if rc != 0:
                return "erro: rfkill %s bluetooth falhou (codigo %d): %s" % (
                    "unblock" if want else "block", rc,
                    (err or out).strip()[:160] or "sem mensagem")
            return None
        return act
    return None


def _brightness_action(probe):
    """Acao do slider de brilho (escreve em /sys/class/backlight)."""
    path = probe.get("path")
    if not path:
        return None
    maximum = probe.get("max") or 100

    def act(percent):
        try:
            value = max(0.0, min(100.0, percent))
            target = max(1, int(round(maximum * value / 100.0)))
        except (TypeError, ValueError):
            return "erro: valor de brilho invalido"
        try:
            with open(path, "w") as f:
                f.write(str(target))
        except PermissionError as exc:
            helper = "/usr/bin/nura-brightness"
            device = probe.get("device")
            if not device or not os.path.isfile(helper):
                return "erro: %s: %s" % (path, exc.strerror or "sem permissao")
            rc, _, err = _run(["/usr/bin/sudo", "-n", helper, device, str(target)])
            if rc != 0:
                return "erro: brilho: %s" % (err.strip() or "ajuste recusado")
        except OSError as exc:
            return "erro: %s: %s" % (path, exc.strerror or str(exc))
        return None
    return act


def _volume_action(probe):
    """Acao do slider de volume (amixer > pactl)."""
    tools = probe.get("tools") or {}

    if "amixer" in tools:
        def act(percent):
            try:
                value = "%d%%" % int(round(max(0.0, min(100.0, percent))))
            except (TypeError, ValueError):
                return "erro: valor de volume invalido"
            rc, out, err = _run([tools["amixer"], "-q", "sset", "Master",
                                  value])
            if rc != 0:
                return "erro: amixer sset Master %s falhou (codigo %d): %s" % (
                    value, rc, (err or out).strip()[:160] or "sem mensagem")
            return None
        return act

    if "pactl" in tools:
        def act(percent):
            try:
                value = "%d%%" % int(round(max(0.0, min(100.0, percent))))
            except (TypeError, ValueError):
                return "erro: valor de volume invalido"
            rc, out, err = _run([tools["pactl"], "set-sink-volume",
                                 "@DEFAULT_SINK@", value])
            if rc != 0:
                return ("erro: pactl set-sink-volume %s falhou "
                        "(codigo %d): %s"
                        % (value, rc, (err or out).strip()[:160]
                           or "sem mensagem"))
            return None
        return act
    return None


def _governor_action(probe):
    """Acao de trocar o governor (escreve em scaling_governor)."""
    cpus = probe.get("cpus") or []
    governors = probe.get("governors") or []
    if not cpus or not governors:
        return None
    current = probe.get("current")

    def act():
        try:
            idx = governors.index(current)
        except ValueError:
            idx = -1
        target = governors[(idx + 1) % len(governors)]
        errors = []
        for cpu in cpus:
            try:
                with open(cpu["gov_path"], "w") as f:
                    f.write(target)
            except PermissionError as exc:
                errors.append("%s: %s" % (cpu["name"],
                                          exc.strerror or "sem permissao"))
            except OSError as exc:
                errors.append("%s: %s" % (cpu["name"],
                                          exc.strerror or str(exc)))
        if errors:
            return ("erro ao mudar governor para '%s': %s"
                    % (target, "; ".join(errors)))
        return None
    return act


# --------------------------------------------------------------------
# o controle
# --------------------------------------------------------------------

class Control(object):
    """Um controle do painel.

    name      rotulo exibido
    icon      nome do icone (nura_ui.Painter.icon)
    available o recurso existe de verdade?
    reason    motivo quando indisponivel (texto curto)
    value     estado atual (texto)
    action    callable ou None (nenhuma acao = somente leitura)
    kind      "toggle" | "slider" | "button" | "info"
    """

    KINDS = ("toggle", "slider", "button", "info")

    def __init__(self, name, icon, available=True, reason="", value="",
                 action=None, kind="info", state=None, detail="",
                 value_num=None, extra=None):
        self.name = name
        self.icon = icon
        self.available = bool(available)
        self.reason = reason or ""
        self.value = value if value is not None else ""
        self.action = action
        self.kind = kind if kind in self.KINDS else "info"
        self.state = state                 # True/False/None (toggle)
        self.detail = detail or ""
        self.value_num = value_num         # 0..1 (slider)
        self.extra = extra or {}
        self.error = ""

    @property
    def enabled(self):
        """Verdadeiro quando o controle pode ser acionado."""
        return self.available and self.action is not None

    def __repr__(self):
        return "<Control %s kind=%s available=%s value=%r>" % (
            self.name, self.kind, self.available, self.value)


def _reason(probe, mod_ok, base=""):
    """Motivo mostrado quando o controle esta indisponivel."""
    if not mod_ok:
        if isinstance(probe, dict):
            extra = base or probe.get("reason") or ""
        else:
            extra = base or ""
        if extra:
            return "modulo de sistema indisponivel (%s)" % extra
        return "modulo de sistema indisponivel"
    if isinstance(probe, dict):
        return probe.get("reason") or ""
    return base or ""


def build_controls(si, root=SYS_ROOT, proc=PROC_ROOT):
    """Monta a lista de controles detectando o que existe de verdade.

    'si' e a instancia de nura_sysinfo (ou None). Quando e None, NENHUM
    controle aparece como disponivel: nada e inventado.
    """
    mod_ok = si is not None
    out = []

    # ---------------- Wi-Fi ----------------
    wifi = probe_wifi(root)
    wifi_value = "indisponivel"
    if wifi["available"] and mod_ok:
        if wifi["state"] is True:
            wifi_value = "ligado"
        elif wifi["state"] is False:
            wifi_value = "desligado"
        else:
            wifi_value = "presente"
    wifi_action = None
    if wifi["available"] and mod_ok:
        wifi_action = _wifi_action(wifi)
    out.append(Control(
        name="Wi-Fi", icon="wifi",
        available=bool(wifi["available"] and mod_ok),
        reason=_reason(wifi, mod_ok),
        value=wifi_value,
        action=wifi_action,
        kind="toggle",
        state=wifi["state"] if (wifi["available"] and mod_ok) else None,
        detail=wifi["detail"],
        extra={"iface": wifi["iface"], "tools": sorted(wifi["tools"].keys())}))

    # ---------------- Bluetooth ----------------
    bt = probe_bluetooth(root)
    bt_value = "indisponivel"
    if bt["available"] and mod_ok:
        if bt["state"] is True:
            bt_value = "ligado"
        elif bt["state"] is False:
            bt_value = "desligado"
        else:
            bt_value = "presente"
    bt_action = _bluetooth_action(bt) if (bt["available"] and mod_ok) else None
    out.append(Control(
        name="Bluetooth", icon="bluetooth",
        available=bool(bt["available"] and mod_ok),
        reason=_reason(bt, mod_ok),
        value=bt_value,
        action=bt_action,
        kind="toggle",
        state=bt["state"] if (bt["available"] and mod_ok) else None,
        detail=bt["detail"],
        extra={"devices": bt["devices"]}))

    # ---------------- Brilho ----------------
    bri = probe_brightness(root)
    bri_num = None
    bri_value = "indisponivel"
    if bri["available"] and mod_ok:
        maximum = bri.get("max") or 0
        current = bri.get("current")
        if maximum and current is not None:
            bri_num = max(0.0, min(1.0, float(current) / float(maximum)))
            bri_value = "%d%%" % int(round(bri_num * 100))
        else:
            bri_value = "presente"
    bri_action = None
    if bri["available"] and mod_ok and bri.get("path"):
        bri_action = _brightness_action(bri)
    out.append(Control(
        name="Brilho", icon="star",
        available=bool(bri["available"] and mod_ok),
        reason=_reason(bri, mod_ok),
        value=bri_value,
        action=bri_action,
        kind="slider",
        value_num=bri_num,
        detail=("dispositivo: %s" % bri["device"])
        if bri.get("device") else ""))

    # ---------------- Volume ----------------
    vol = probe_volume(root, proc)
    vol_num = None
    vol_value = "indisponivel"
    if vol["available"] and mod_ok:
        percent = vol.get("percent")
        if percent is not None:
            vol_num = max(0.0, min(1.0, float(percent) / 100.0))
            vol_value = "%d%%" % int(round(vol_num * 100))
        else:
            vol_value = vol.get("detail") or "presente"
    vol_action = (_volume_action(vol)
                  if (vol["available"] and mod_ok) else None)
    out.append(Control(
        name="Volume", icon="volume",
        available=bool(vol["available"] and mod_ok),
        reason=_reason(vol, mod_ok),
        value=vol_value,
        action=vol_action,
        kind="slider",
        value_num=vol_num,
        detail=vol.get("detail") or "",
        extra={"muted": vol.get("muted")}))

    # ---------------- Bateria ----------------
    bat = probe_battery(root)
    bat_lines = []
    bat_value = "indisponivel"
    if bat["available"] and mod_ok:
        cap = bat.get("capacity")
        bat_value = "%d%%" % cap if cap is not None else "presente"
        if bat.get("status"):
            bat_value = "%s - %s" % (bat_value, bat["status"].lower())
        if bat.get("health"):
            bat_lines.append("saude: %s" % bat["health"])
        if bat.get("temp_c") is not None:
            bat_lines.append("temperatura: %.1f C" % bat["temp_c"])
        if bat.get("voltage_v") is not None:
            bat_lines.append("tensao: %.2f V" % bat["voltage_v"])
        if bat.get("current_a") is not None:
            bat_lines.append("corrente: %.2f A" % bat["current_a"])
        if bat.get("power_w") is not None:
            bat_lines.append("potencia: %.2f W" % bat["power_w"])
    out.append(Control(
        name="Bateria", icon="battery",
        available=bool(bat["available"] and mod_ok),
        reason=_reason(bat, mod_ok),
        value=bat_value,
        action=None,
        kind="info",
        detail="\n".join(bat_lines),
        extra={"name": bat.get("name")}))

    # ---------------- Energia / governor ----------------
    gov = probe_governor(root)
    gov_value = "indisponivel"
    if gov["available"] and mod_ok:
        gov_value = gov.get("current") or "desconhecido"
    gov_detail = ""
    if gov.get("governors"):
        gov_detail = "disponiveis: %s" % ", ".join(gov["governors"])
    gov_action = (_governor_action(gov)
                  if (gov["available"] and mod_ok) else None)
    out.append(Control(
        name="Energia", icon="cpu",
        available=bool(gov["available"] and mod_ok),
        reason=_reason(gov, mod_ok),
        value=gov_value,
        action=gov_action,
        kind="button",
        detail=gov_detail,
        extra={"governors": gov.get("governors") or [],
               "cpus": len(gov.get("cpus") or [])}))

    # ---------------- Orientacao ----------------
    out.append(Control(
        name="Orientacao", icon="grid",
        available=True,
        reason="",
        value="Paisagem (fixa)",
        action=None,
        kind="info",
        detail=("O painel fisico e retrato 1080x1920; a paisagem 1920x1080 e "
                "obtida por rotacao de software no compositor.\n"
                "A rotacao e fixa e nao e alternavel aqui.")))

    # ---------------- Sistema ----------------
    sysinfo = probe_system(si)
    sys_value = "indisponivel"
    if sysinfo["available"] and mod_ok:
        sys_value = sysinfo.get("value") or "informacoes disponiveis"
    out.append(Control(
        name="Sistema", icon="info",
        available=bool(sysinfo["available"] and mod_ok),
        reason=_reason(sysinfo, mod_ok),
        value=sys_value,
        action=None,
        kind="info",
        detail="\n".join(sysinfo.get("lines") or [])))

    return out


# --------------------------------------------------------------------
# o painel (desenho + toque) compartilhado pelo app e pelo widget
# --------------------------------------------------------------------

class ControlDeck(object):
    """Conjunto de controles + desenho + toque.

    Serve tanto para a janela do Control Center quanto para o painel
    lateral embutido na area de trabalho.
    """

    def __init__(self, shell=None, sysinfo=_AUTO, root=SYS_ROOT,
                 proc=PROC_ROOT):
        self.shell = shell
        self.root = root
        self.proc = proc
        self.theme = T.Theme("neon")
        self.title = "NURA Control Center"
        self.header = True
        self.controls = []
        self.hits = []
        self.cards = []
        self.pressed = None
        self.status = ""
        self.status_error = False
        self.update_count = 0
        self.refresh_interval = REFRESH_INTERVAL
        self._acc = 0.0
        self._origin = (0, 0, 860, 640)
        self._sysinfo_request = sysinfo
        self._own_sysinfo = None
        self.refresh()

    # ---------------- sistema ----------------

    def resolve_sysinfo(self):
        """Obtem a instancia do nura_sysinfo (ou None).

        Ordem: parametro explicito > shell.sysinfo > instancia propria.
        A instancia propria e memorizada (o nura_sysinfo guarda o
        historico de /proc/stat para medir o uso de CPU entre leituras).
        """
        req = self._sysinfo_request
        if req is not _AUTO:
            return req
        shell = self.shell
        si = getattr(shell, "sysinfo", None) if shell is not None else None
        if si is not None:
            return si
        if self._own_sysinfo is not None:
            return self._own_sysinfo
        cls = globals().get("SysInfo")
        if cls is None:
            return None
        try:
            self._own_sysinfo = cls(root=self.root, proc=self.proc)
        except Exception:
            try:
                self._own_sysinfo = cls()
            except Exception:
                self._own_sysinfo = None
        return self._own_sysinfo

    def refresh(self):
        """Reavalia todos os controles (detecao real, sem cache)."""
        si = self.resolve_sysinfo()
        self.sysinfo = si
        new = build_controls(si, root=self.root, proc=self.proc)
        self.controls[:] = new
        self.update_count += 1
        return self.controls

    def on_tick(self, dt):
        """Reavalia periodicamente (nao a cada quadro)."""
        try:
            step = float(dt)
        except (TypeError, ValueError):
            step = 0.0
        self._acc += step
        if self._acc >= self.refresh_interval:
            self._acc = 0.0
            self.refresh()
            self.layout()

    def set_origin(self, x, y, w, h):
        """Define o retangulo (em coordenadas paisagem) do painel."""
        self._origin = (int(x), int(y), int(w), int(h))

    def origin(self):
        return self._origin

    # ---------------- layout ----------------

    def header_h(self):
        th = self.theme
        if not self.header:
            return 0
        height = th.font_title + 8
        if self.status:
            height += th.font_small + 10
        return height

    def banner_h(self):
        """Altura da faixa de aviso ('modulo de sistema indisponivel')."""
        if self.sysinfo is not None:
            return 0
        return self.theme.font_small + 10

    def module_missing(self):
        """True quando o nura_sysinfo nao esta disponivel."""
        return self.sysinfo is None

    def layout(self):
        """Calcula a posicao de cada cartao e de cada botao."""
        th = self.theme
        ox, oy, ow, oh = self._origin
        pad = th.pad
        gap = th.gap
        top = oy + self.header_h() + self.banner_h()
        total = len(self.controls) or 1
        cols = 2 if ow >= 680 else 1
        rows = (total + cols - 1) // cols
        avail_h = max(120.0, (oy + oh) - top - pad)
        card_w = (ow - pad * 2 - gap * (cols - 1)) / float(cols)
        card_h = max(116.0, (avail_h - gap * (rows - 1)) / float(rows))

        self.cards = []
        for index, ctrl in enumerate(self.controls):
            row, col = divmod(index, cols)
            cx = ox + pad + col * (card_w + gap)
            cy = top + row * (card_h + gap)
            self.cards.append((ctrl, cx, cy, card_w, card_h))

        self.hits = []
        for ctrl, cx, cy, cw, ch in self.cards:
            if not ctrl.available:
                continue
            if ctrl.kind == "toggle":
                bw, bh = 64.0, float(MIN_TOUCH)
                self.hits.append(("toggle", ctrl,
                                  (cx + cw - pad - bw, cy + 10, bw, bh)))
            elif ctrl.kind == "button":
                bw, bh = 128.0, float(MIN_TOUCH)
                self.hits.append(("button", ctrl,
                                  (cx + cw - pad - bw, cy + 10, bw, bh)))
            elif ctrl.kind == "slider":
                sw = cw - pad * 2
                sh = float(MIN_TOUCH)
                self.hits.append(("slider", ctrl,
                                  (cx + pad, cy + ch - pad - sh, sw, sh)))
        return self.hits

    # ---------------- desenho ----------------

    def draw(self, p):
        """Desenha o painel inteiro (titulo + cartoes)."""
        self.theme = p.theme
        self.layout()
        ox, oy, ow, oh = self._origin
        th = self.theme

        if self.header:
            p.text(self.title, ox + th.pad, oy + th.font_title,
                   th.font_title, th.text, "bold")
            if self.status:
                color = th.err if self.status_error else th.ok
                p.text(self.status, ox + th.pad,
                       oy + th.font_title + th.font_small + 6,
                       th.font_small, color)

        if self.module_missing():
            by = oy + self.header_h() + th.font_small
            p.text("modulo de sistema indisponivel", ox + th.pad, by,
                   th.font_small, th.warn)

        for ctrl, cx, cy, cw, ch in self.cards:
            self._draw_card(p, ctrl, cx, cy, cw, ch)

    def _draw_card(self, p, ctrl, x, y, w, h):
        th = self.theme
        accent = th.accent if ctrl.available else th.dim2
        p.panel(x, y, w, h, th.panel, 0.92 if ctrl.available else 0.60,
                r=th.radius, border=True)
        if not ctrl.available:
            p.round(x, y, w, h, th.radius, th.dim2, 0.0, filled=False,
                    width=1.0)

        # icone + nome + valor
        p.icon(ctrl.icon, x + 28, y + 30, 26, accent)
        p.text(ctrl.name, x + 52, y + 26, th.font,
               th.text if ctrl.available else th.dim, "bold")
        if ctrl.available:
            p.text(ctrl.value, x + 52, y + 50, th.font_small, th.dim)
        else:
            p.text("indisponivel", x + 52, y + 50, th.font_small, th.warn)

        # ate onde o texto de detalhe pode ir (sem cobrir o controle)
        detail_top = y + 68
        bottom = y + h - th.pad
        if ctrl.available and ctrl.kind == "slider":
            # o slider ocupa os 44 px finais: o texto para antes da trilha
            detail_limit = bottom - MIN_TOUCH + 22 - 6
        else:
            detail_limit = bottom - 4

        # texto de detalhe / motivo / erro real
        text = ctrl.error or (ctrl.detail if ctrl.available else ctrl.reason)
        room = int((detail_limit - detail_top) / (th.font_small + 4))
        if room < 0:
            room = 0
        lines = _wrap_lines(p, text, w - th.pad * 2, room) if (text and room) \
            else []
        for i, line in enumerate(lines):
            color = th.err if ctrl.error else th.dim2
            p.text(line, x + th.pad, detail_top + i * (th.font_small + 4),
                   th.font_small, color)

        # widget
        if not ctrl.available:
            return
        for kind, target, rect in self.hits:
            if target is not ctrl:
                continue
            if kind == "toggle":
                self._draw_toggle(p, ctrl, rect)
            elif kind == "slider":
                self._draw_slider(p, ctrl, rect)
            elif kind == "button":
                self._draw_button(p, ctrl, rect)
            break

    def _draw_toggle(self, p, ctrl, rect):
        th = self.theme
        x, y, w, h = rect
        on = ctrl.state is True
        color = th.ok if on else th.dim2
        pressed = self.pressed is not None and self.pressed[1] is ctrl
        p.round(x, y, w, h, h / 2.0, color, 0.40 if pressed else 0.22)
        p.round(x, y, w, h, h / 2.0, color, 0.0, filled=False, width=1.6)
        knob = h / 2.0 - 6.0
        kx = x + w - h / 2.0 if on else x + h / 2.0
        p.circle(kx, y + h / 2.0, knob, color, 0.98)
        if ctrl.state is None:
            p.text("?", kx, y + h / 2.0 + 6, th.font_small, th.bg, "bold",
                   align="center")

    def _draw_slider(self, p, ctrl, rect):
        th = self.theme
        x, y, w, h = rect
        frac = ctrl.value_num if ctrl.value_num is not None else 0.0
        frac = max(0.0, min(1.0, frac))
        track = 10.0
        ty = y + (h - track) / 2.0
        p.round(x, ty, w, track, track / 2.0, th.panel_hi, 0.95)
        if frac > 0:
            p.round(x, ty, max(track, w * frac), track, track / 2.0,
                    th.accent, 0.95)
        kx = x + w * frac
        p.circle(kx, y + h / 2.0, 13, th.accent, 0.95)
        p.circle(kx, y + h / 2.0, 6, th.bg, 0.85)

    def _draw_button(self, p, ctrl, rect):
        th = self.theme
        x, y, w, h = rect
        pressed = self.pressed is not None and self.pressed[1] is ctrl
        p.button(x, y, w, h, "trocar", pressed=pressed, size=th.font_small)

    # ---------------- toque ----------------

    @staticmethod
    def _inside(rect, x, y):
        return (rect[0] <= x <= rect[0] + rect[2] and
                rect[1] <= y <= rect[1] + rect[3])

    def _hit_test(self, x, y):
        for hit in self.hits:
            if self._inside(hit[2], x, y):
                return hit
        return None

    def _notify(self, message):
        shell = self.shell
        if shell is not None and hasattr(shell, "notify"):
            try:
                shell.notify(message)
            except Exception:
                pass

    def _rebuild(self, ctrl):
        """Reavalia os controles e mantem o erro no cartao.

    O erro real (EACCES/EPERM/etc.) tem de continuar visivel no cartao
    depois da reavaliacao — senao ele sumiria da tela.
    """
        self.refresh()
        self.layout()
        for novo in self.controls:
            if novo.name == ctrl.name:
                novo.error = ctrl.error
                break

    def _invoke(self, ctrl):
        """Executa a acao de um controle e mostra o resultado real."""
        if ctrl.action is None:
            self.status = "%s: nenhuma acao disponivel" % ctrl.name
            self.status_error = True
            return
        try:
            result = ctrl.action()
        except Exception as exc:
            result = "erro: %s: %s" % (type(exc).__name__, exc)
        if result:
            ctrl.error = result
            self.status = result
            self.status_error = True
            self._notify(result)
        else:
            ctrl.error = ""
            self.status = "%s: aplicado" % ctrl.name
            self.status_error = False
            self._notify(self.status)
        self._rebuild(ctrl)

    def _set_slider(self, ctrl, x):
        for kind, target, rect in self.hits:
            if kind == "slider" and target is ctrl:
                if rect[2] <= 0:
                    return
                frac = (x - rect[0]) / float(rect[2])
                ctrl.value_num = max(0.0, min(1.0, frac))
                ctrl.value = "%d%%" % int(round(ctrl.value_num * 100))
                return

    def _commit_slider(self, ctrl):
        if ctrl.action is None:
            return
        try:
            result = ctrl.action(ctrl.value_num * 100.0)
        except Exception as exc:
            result = "erro: %s: %s" % (type(exc).__name__, exc)
        if result:
            ctrl.error = result
            self.status = result
            self.status_error = True
            self._notify(result)
        else:
            ctrl.error = ""
            self.status = "%s: aplicado" % ctrl.name
            self.status_error = False
            self._notify(self.status)
        self._rebuild(ctrl)

    def on_touch(self, ev):
        """Trata o toque (coordenadas ja em paisagem)."""
        et = getattr(ev, "type", "")
        if et == "tap":
            self.pressed = None
            self.layout()
            hit = self._hit_test(ev.x, ev.y)
            if hit is None:
                return False
            kind, ctrl, _ = hit
            if kind == "slider":
                if ctrl.action is not None:
                    self._set_slider(ctrl, ev.x)
                    self._commit_slider(ctrl)
            else:
                self._invoke(ctrl)
            return True
        if et == "down":
            self.layout()
            hit = self._hit_test(ev.x, ev.y)
            self.pressed = hit
            if hit is not None and hit[0] == "slider":
                self._set_slider(hit[1], ev.x)
            return hit is not None
        if et == "move":
            if self.pressed is not None and self.pressed[0] == "slider":
                self._set_slider(self.pressed[1], ev.x)
                return True
            return self.pressed is not None
        if et == "up":
            hit = self.pressed
            self.pressed = None
            if hit is None:
                return False
            kind, ctrl, rect = hit
            if not self._inside(rect, ev.x, ev.y):
                return True
            if kind == "slider":
                self._commit_slider(ctrl)
            else:
                self._invoke(ctrl)
            return True
        if et == "cancel":
            self.pressed = None
            return False
        return False


def _wrap_lines(p, text, max_w, max_lines):
    """Quebra um texto em linhas (no maximo 'max_lines').

    Se sobrar texto, a ultima linha ganha '...' para deixar claro que
    o texto foi cortado.
    """
    if not text or max_lines <= 0:
        return []
    out = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        if not words:
            out.append("")
            continue
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if p.tw(candidate) <= max_w or not current:
                current = candidate
            else:
                out.append(current)
                current = word
        if current:
            out.append(current)

    if len(out) > max_lines:
        out = out[:max_lines]
        last = out[-1]
        while last and p.tw(last + "...") > max_w:
            last = last[:-1]
        out[-1] = (last or "") + "..."
    return out


# --------------------------------------------------------------------
# aplicativo em janela
# --------------------------------------------------------------------

class ControlCenterApp(App):
    """NURA Control Center (janela)."""

    title = "NURA Control Center"
    icon = "cpu"
    width = 860
    height = 640
    min_width = 520
    min_height = 420
    resizable = True

    def __init__(self, shell=None, sysinfo=_AUTO, root=SYS_ROOT,
                 proc=PROC_ROOT, **kw):
        App.__init__(self, shell=shell, **kw)
        self.deck = ControlDeck(shell=shell, sysinfo=sysinfo, root=root,
                                proc=proc)
        self.deck.title = self.title
        self.deck.header = True
        self._close_rect = (0.0, 0.0, float(MIN_TOUCH), float(MIN_TOUCH))
        self._close_pressed = False

    # ---------------- ciclo de vida ----------------

    @property
    def controls(self):
        return self.deck.controls

    @property
    def sysinfo(self):
        return self.deck.sysinfo

    def on_open(self):
        self.deck.refresh()

    def on_close(self):
        pass

    def content_rect(self):
        """Area util da janela (ou a area padrao, se nao houver janela)."""
        win = self.window
        if win is not None:
            try:
                return win.content_rect()
            except Exception:
                pass
        return (0, 0, self.width, self.height)

    # ---------------- desenho ----------------

    def draw(self, p):
        th = p.theme
        x, y, w, h = self.content_rect()
        self.deck.set_origin(x, y, w, h)
        self.deck.draw(p)

        # botao de fechar no canto (>= 44x44)
        bx = x + w - th.pad - MIN_TOUCH
        by = y + 6
        self._close_rect = (bx, by, float(MIN_TOUCH), float(MIN_TOUCH))
        pressed = self._close_pressed
        p.round(bx, by, MIN_TOUCH, MIN_TOUCH, th.radius,
                th.panel_hi, 0.85 if not pressed else 0.95)
        p.icon("close", bx + MIN_TOUCH / 2.0, by + MIN_TOUCH / 2.0, 20,
               th.err if pressed else th.dim)

    # ---------------- toque ----------------

    def on_touch(self, ev):
        et = getattr(ev, "type", "")
        if et == "down":
            if ControlDeck._inside(self._close_rect, ev.x, ev.y):
                self._close_pressed = True
                return True
        elif et == "up":
            if self._close_pressed:
                self._close_pressed = False
                if ControlDeck._inside(self._close_rect, ev.x, ev.y):
                    self.close()
                    return True
        elif et == "cancel":
            self._close_pressed = False
        return self.deck.on_touch(ev)

    def close(self):
        """Fecha a janela pelo shell (se houver)."""
        shell = self.shell
        if shell is not None and hasattr(shell, "close_window"):
            try:
                shell.close_window(self.window)
                return True
            except Exception:
                return False
        return False


# --------------------------------------------------------------------
# widget para o painel lateral da area de trabalho
# --------------------------------------------------------------------

class ControlPanel(Widget):
    """Painel lateral do Control Center (area de trabalho).

    O shell instancia este widget, define o retangulo e o desenha:

        panel = ControlPanel(shell=shell, x=0, y=0, w=460, h=1080)
        panel.draw(p)
        panel.on_touch(ev)        # ev.x/ev.y ja em paisagem

    O retangulo e sempre conhecido (`panel.rect()`) e todos os botoes
    tem alvo de toque >= 44x44 px.
    """

    def __init__(self, shell=None, x=0, y=0, w=460, h=1080, sysinfo=_AUTO,
                 root=SYS_ROOT, proc=PROC_ROOT):
        Widget.__init__(self)
        self.shell = shell
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.deck = ControlDeck(shell=shell, sysinfo=sysinfo, root=root,
                                proc=proc)
        self.deck.header = False
        self.deck.set_origin(self.x, self.y, self.w, self.h)

    # ---------------- geometria ----------------

    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def set_rect(self, x, y, w, h):
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)
        self.deck.set_origin(*self.rect())
        return self

    @property
    def controls(self):
        return self.deck.controls

    # ---------------- ciclo de vida ----------------

    def refresh(self):
        return self.deck.refresh()

    def on_tick(self, dt):
        self.deck.on_tick(dt)

    # ---------------- desenho / toque ----------------

    def draw(self, p):
        self.deck.set_origin(*self.rect())
        self.deck.draw(p)

    def on_touch(self, ev):
        self.deck.set_origin(*self.rect())
        return self.deck.on_touch(ev)


# alias explicito para quem procurar pelo widget pelo nome do app
ControlCenterWidget = ControlPanel


# --------------------------------------------------------------------

def main():   # pragma: no cover - utilidade de inspecao manual
    """Imprime o estado real dos controles (sem interface)."""
    deck = ControlDeck()
    print("NURA Control Center — estado real dos controles")
    print("sysinfo: %s" % ("disponivel" if deck.sysinfo else
                           "INDISPONIVEL"))
    for ctrl in deck.controls:
        print("  %-12s %-14s %-12s %s" % (ctrl.name, ctrl.kind,
                                          ctrl.value, ctrl.reason))


if __name__ == "__main__":   # pragma: no cover
    main()
