#!/usr/bin/env python3
"""NURA OS — NURA Game Hub (central de jogos do desktop).

O Game Hub e um *catalogo honesto* do que existe de fato no aparelho:

  * **Biblioteca**   -> jogos declarados nos `.desktop` do sistema
                       (`Categories=Game;...`) que realmente existem.
  * **Emuladores**   -> binarios de emulador que estao de fato no PATH
                       (os ausentes aparecem marcados, nunca sao
                       instalados pelo hub).
  * **Controles**    -> dispositivos de joystick/gamepad reais lidos de
                       `/proc/bus/input/devices` + `/dev/input/js*`.
  * **Configuracoes**-> tela cheia, escala da interface e tema de cores.

Regras de ouro deste modulo (nao negociaveis):

  1. **Nada e instalado, nada e baixado, nada e criado no disco.**
     As varreduras sao somente-leitura e nunca criam pastas.
  2. **Nada e prometido.** Se o aparelho nao tem GPU/OpenGL o hub
     escreve "sem aceleracao 3D (sem GPU/OpenGL)" em vez de fingir que
     jogos 3D funcionam.
  3. **Todo botao faz algo real** (ler um arquivo, abrir um programa que
     existe) ou fica visivelmente desabilitado.
  4. **Nada de sudo**, nada de driver, nada de pacote de sistema.

Somente biblioteca padrao do Python + cairo (via nura_theme/nura_ui).
"""

import ctypes.util
import glob
import os
import re
import shlex
import shutil
import struct
import sys
import time

# --------------------------------------------------------------------
# importacoes do NURA (com fallbacks para o modulo funcionar sozinho)
# --------------------------------------------------------------------

try:
    from nura_theme import Theme, THEME_NAMES
except Exception:                                     # pragma: no cover
    Theme = None
    THEME_NAMES = ["neon", "dark", "minimal", "gamer"]

try:
    from nura_window import App
except Exception:                                     # pragma: no cover
    class App(object):
        """Fallback minimo da API de App (usado so sem nura_window)."""

        title = "Aplicativo"
        icon = "terminal"
        width = 900
        height = 620
        min_width = 480
        min_height = 320
        resizable = True

        def __init__(self, shell=None, **kw):
            self.shell = shell
            self.ctx_data = kw
            self.window = None
            self._t0 = 0.0

        def on_open(self):
            pass

        def on_close(self):
            pass

        def on_focus(self, focused):
            pass

try:
    from nura_sysinfo import SysInfo
except ImportError:
    SysInfo = None

__all__ = ["GameEntry", "GameHub", "scan_games", "scan_emulators",
           "scan_roms", "scan_controllers", "graphics_status",
           "emulator_catalog", "EMULATORS", "ROM_EXTENSIONS"]


# --------------------------------------------------------------------
# constantes / catalogos
# --------------------------------------------------------------------

#: extensoes de ROM reconhecidas (somente leitura)
ROM_EXTENSIONS = (
    ".gba", ".nes", ".sfc", ".smc", ".iso", ".bin", ".cue", ".chd",
    ".rom", ".z64", ".n64", ".gb", ".gbc", ".ps1", ".psp", ".nds",
)

#: plataforma legivel por extensao de ROM
ROM_PLATFORM = {
    ".gba": "Game Boy Advance",
    ".nes": "NES",
    ".sfc": "SNES",
    ".smc": "SNES",
    ".iso": "ISO (PS2/GC/Wii)",
    ".bin": "BIN (PS2/GC/Wii)",
    ".cue": "CUE",
    ".chd": "CHD",
    ".rom": "ROM (diversos)",
    ".z64": "Nintendo 64",
    ".n64": "Nintendo 64",
    ".gb": "Game Boy",
    ".gbc": "Game Boy Color",
    ".ps1": "PlayStation",
    ".psp": "PlayStation Portable",
    ".nds": "Nintendo DS",
}

#: emuladores conhecidos: (chave/binario, nome bonito, para que serve)
EMULATORS = (
    ("retroarch", "RetroArch", "multi-sistema"),
    ("retroarch-gtk", "RetroArch (GTK)", "multi-sistema"),
    ("dolphin-emu", "Dolphin", "GameCube / Wii"),
    ("pcsx2", "PCSX2", "PlayStation 2"),
    ("cpcs2", "cpcs2", "PlayStation 2"),
    ("pcsx-rearmed", "PCSX-ReARMed", "PlayStation 1"),
    ("duckstation", "DuckStation", "PlayStation 1"),
    ("ppsspp", "PPSSPP", "PlayStation Portable"),
    ("desmume", "DeSmuME", "Nintendo DS"),
    ("melonds", "melonDS", "Nintendo DS"),
    ("mgba", "mGBA", "Game Boy Advance"),
    ("mgba-qt", "mGBA (Qt)", "Game Boy Advance"),
    ("gpsp", "GPSP", "Game Boy Advance"),
    ("mednafen", "Mednafen", "multi-sistema"),
    ("dosbox", "DOSBox", "MS-DOS"),
    ("dosbox-staging", "DOSBox Staging", "MS-DOS"),
    ("scummvm", "ScummVM", "jogos de aventura"),
    ("snes9x", "Snes9x", "SNES"),
    ("bsnes", "bsnes", "SNES"),
    ("mupen64plus", "Mupen64Plus", "Nintendo 64"),
    ("fceux", "FCEUX", "NES"),
    ("gambatte", "Gambatte", "Game Boy / Color"),
    ("sameboy", "SameBoy", "Game Boy / Color"),
)

#: extensao de ROM -> emuladores candidatos (o primeiro INSTALADO vence)
ROM_EMULATORS = {
    ".gba": ("mgba", "mgba-qt", "gpsp", "retroarch"),
    ".nes": ("fceux", "retroarch"),
    ".sfc": ("snes9x", "bsnes", "retroarch"),
    ".smc": ("snes9x", "bsnes", "retroarch"),
    ".iso": ("pcsx2", "cpcs2", "dolphin-emu", "ppsspp", "mednafen",
            "retroarch"),
    ".bin": ("pcsx2", "cpcs2", "dolphin-emu", "ppsspp", "mednafen",
             "retroarch"),
    ".cue": ("pcsx2", "mednafen", "retroarch"),
    ".chd": ("pcsx2", "cpcs2", "dolphin-emu", "mednafen", "retroarch"),
    ".rom": ("mednafen", "retroarch"),
    ".z64": ("mupen64plus", "retroarch"),
    ".n64": ("mupen64plus", "retroarch"),
    ".gb": ("gambatte", "sameboy", "retroarch"),
    ".gbc": ("gambatte", "sameboy", "retroarch"),
    ".ps1": ("pcsx2", "pcsx-rearmed", "duckstation", "mednafen",
             "retroarch"),
    ".psp": ("ppsspp",),
    ".nds": ("desmume", "melonds", "retroarch"),
}

#: categorias do menu XDG -> nome legivel
CATEGORY_LABELS = {
    "ArcadeGame": "Arcade",
    "ActionGame": "Acao",
    "AdventureGame": "Aventura",
    "PuzzleGame": "Puzzle",
    "RacingGame": "Corrida",
    "RolePlayingGame": "RPG",
    "SimulationGame": "Simulacao",
    "SportsGame": "Esporte",
    "StrategyGame": "Estrategia",
    "BoardGame": "Tabuleiro",
    "CardGame": "Cartas",
    "KidsGame": "Infantil",
    "MusicGame": "Musica",
    "PlatformGame": "Plataforma",
    "ShooterGame": "Tiro",
    "CasualGame": "Casual",
    "Game": "Linux",
    "GameX": "Linux",
}

#: texto honesto quando o aparelho nao tem aceleracao 3D
NO_ACCEL_NOTE = "sem aceleracao 3D (sem GPU/OpenGL)"
#: banner da interface (o mesmo aviso, em linguagem de usuario)
NO_ACCEL_BANNER = "sem aceleracao 3D — jogos 3D nao sao viáveis"

TABS = ("Biblioteca", "Emuladores", "Controles", "Configuracoes")

#: codigos de campo do Exec (nao existem para um jogo sem arquivo)
_FIELD_CODE = re.compile(r"%[fFuUicdDkmNvN]")

#: leitura do joystick (/dev/input/jsN) — struct js_event do kernel
JS_EVENT_FMT = "IhBB"
JS_EVENT_SIZE = struct.calcsize(JS_EVENT_FMT)
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

#: cache do catalogo de emuladores (por PATH) e da busca de OpenGL
_CATALOG_CACHE = {}
_GL_CACHE = []


# --------------------------------------------------------------------
# helpers pequenos
# --------------------------------------------------------------------

def _read_text(path, limit=262144):
    """Le um arquivo de texto. Devolve '' se nao der."""
    try:
        with open(path, "r", errors="replace") as f:
            return f.read(limit)
    except Exception:
        return ""


def human_size(n):
    """Bytes -> '12.4 MB'."""
    if n is None or n < 0:
        return "-"
    units = ("B", "KB", "MB", "GB", "TB")
    v = float(n)
    i = 0
    while v >= 1024.0 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    if i == 0:
        return "%d %s" % (int(v), units[i])
    return "%.1f %s" % (v, units[i])


def _is_executable(path):
    try:
        return os.path.isfile(path) and os.access(path, os.X_OK)
    except Exception:
        return False


def _which(program, path=None):
    """Localiza um programa. 'which' do sistema, com fallback simples."""
    if not program:
        return None
    if "/" in program:
        p = os.path.abspath(os.path.expanduser(program))
        return p if _is_executable(p) else None
    try:
        found = shutil.which(program, path=path)
    except Exception:
        found = None
    if found:
        return found
    # fallback: procura nos diretorios do PATH manualmente
    env_path = path if path is not None else os.environ.get("PATH", "")
    for d in env_path.split(os.pathsep):
        if not d:
            continue
        cand = os.path.join(d, program)
        if _is_executable(cand):
            return cand
    return None


def _which_many(names, path=None):
    """Resolve varios binarios de uma vez (uma unica varredura do PATH).

    Mucho mais rapido que chamar `which` para cada nome: em sistemas
    com o PATH grande (ou em rede) 24 buscas viram 1 listagem.
    """
    names = list(names)
    found = {}
    plain = []
    for n in names:
        if not n:
            continue
        if "/" in n:
            p = _which(n, path=path)
            if p:
                found[n] = p
        else:
            plain.append(n)
    if not plain:
        return found
    env_path = path if path is not None else os.environ.get("PATH", "")
    dirs = []
    for d in env_path.split(os.pathsep):
        if d and d not in dirs:
            dirs.append(d)
    remaining = set(plain)
    for d in dirs:
        if not remaining:
            break
        try:
            entries = os.listdir(d)
        except Exception:
            continue
        for n in list(remaining):
            if n in entries:
                p = os.path.join(d, n)
                if _is_executable(p):
                    found[n] = p
                    remaining.discard(n)
    return found


def parse_desktop(path):
    """Le um arquivo .desktop. Devolve um dict (vazio em caso de erro).

    Reconhece apenas o grupo ``[Desktop Entry]`` e ignora as linhas de
    continuacao (que em .desktop reais quase nunca importam para o Exec).
    """
    data = {}
    group = None
    try:
        with open(path, "r", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n").rstrip("\r")
                if not line.strip():
                    continue
                if line.startswith("[") and line.endswith("]"):
                    group = line[1:-1].strip()
                    continue
                if group != "Desktop Entry":
                    continue
                if line[:1] in (" ", "\t"):
                    continue                      # continuacao
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key in data:
                    continue
                data[key] = value.strip()
    except Exception:
        return {}
    return data


def _desktop_name(data):
    """Nome de exibicao (prefere 'Name', cai para 'Name[xx]')."""
    name = data.get("Name")
    if name:
        return name
    for key in sorted(data.keys()):
        if key.startswith("Name[") and data[key]:
            return data[key]
    return ""


def _desktop_categories(data):
    raw = data.get("Categories", "") or ""
    return [c.strip() for c in raw.split(";") if c.strip()]


def _strip_field_codes(cmd):
    """Remove os codigos de campo do Exec (%f, %U, %i...)."""
    if not cmd:
        return ""
    cmd = cmd.replace("%%", "\x00")
    cmd = _FIELD_CODE.sub("", cmd)
    return cmd.replace("\x00", "%").strip()


def _split_exec(cmd):
    """Divide o Exec em (programa, argumentos)."""
    cmd = _strip_field_codes(cmd)
    if not cmd:
        return "", []
    try:
        parts = shlex.split(cmd)
    except Exception:
        parts = cmd.split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _platform_from_categories(cats):
    """Plataforma legivel a partir das categorias XDG."""
    for c in cats:                      # categoria especifica primeiro
        if c in CATEGORY_LABELS and c not in ("Game", "GameX"):
            return CATEGORY_LABELS[c]
    for c in cats:
        if c == "Game" or c.startswith("Game"):
            return "Linux"
    return "Linux"


def _desktop_dirs():
    home = os.path.expanduser("~")
    return [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.join(home, ".local", "share", "applications"),
    ]


def _default_rom_dirs():
    """Pastas onde Usually ficam as ROMs — apenas para LEITURA."""
    home = os.path.expanduser("~")
    dirs = []
    if home and home != "~":
        dirs.append(os.path.join(home, "Games"))
        dirs.append(os.path.join(home, "ROMs"))
        user = os.path.basename(home)
        if user:
            dirs.append(os.path.join("/home", user, "Games"))
    dirs.append("/mnt")
    out = []
    for d in dirs:
        if d and d not in out:
            out.append(d)
    return out


# --------------------------------------------------------------------
# GameEntry
# --------------------------------------------------------------------

class GameEntry(object):
    """Um item da biblioteca (jogo, emulador, ROM ou atalho)."""

    def __init__(self, name="", path="", launch_cmd=None, kind="jogo",
                 icon="gamepad", size="-", platform="Linux", playable=False,
                 reason="", size_bytes=0):
        self.name = name or "sem nome"
        self.path = path or ""
        self.launch_cmd = launch_cmd
        self.kind = kind            # jogo | emulador | rom | atalho
        self.icon = icon or "gamepad"
        self.size = size            # texto ("12.4 MB")
        self.size_bytes = size_bytes
        self.platform = platform
        self.playable = bool(playable)
        self.reason = reason or ""

    def as_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "launch_cmd": self.launch_cmd,
            "kind": self.kind,
            "icon": self.icon,
            "size": self.size,
            "size_bytes": self.size_bytes,
            "platform": self.platform,
            "playable": self.playable,
            "reason": self.reason,
        }

    def __repr__(self):
        return "<GameEntry %r kind=%s playable=%s>" % (
            self.name, self.kind, self.playable)


# --------------------------------------------------------------------
# varreduras reais (somente leitura)
# --------------------------------------------------------------------

def scan_games(dirs=None, emulators=None):
    """Procura jogos declarados nos `.desktop` do sistema.

    Varre ``/usr/share/applications``, ``/usr/local/share/applications``
    e ``~/.local/share/applications`` (ou os diretorios informados) e
    fica com os arquivos que tem `Categories` contendo `Game` (ou
    `GameX`). Devolve uma lista de `GameEntry`.

    NUNCA cria nada no disco.
    """
    if dirs is None:
        dirs = _desktop_dirs()
    if emulators is None:
        emulators = emulator_catalog()

    installed = dict((e["name"], e["cmd"]) for e in emulators
                     if e.get("installed"))

    out = []
    seen = set()
    # 1a passada: le os .desktop e anota os programas a resolver
    pending = []
    for base in dirs:
        if not base:
            continue
        try:
            if not os.path.isdir(base):
                continue
            files = sorted(glob.glob(os.path.join(base, "*.desktop")))
            # um nivel de subpastas (flatpak/electron costumam usar)
            for sub in sorted(glob.glob(os.path.join(base, "*"))):
                if os.path.isdir(sub):
                    files += sorted(glob.glob(os.path.join(sub, "*.desktop")))
        except Exception:
            continue
        for path in files:
            if path in seen:
                continue
            seen.add(path)
            data = parse_desktop(path)
            if not data:
                continue
            cats = _desktop_categories(data)
            is_game = any(c == "Game" or c.startswith("Game") for c in cats)
            name = _desktop_name(data)
            if not is_game:
                # atalho para um jogo que nao se declarou como Game
                low = (os.path.basename(path) + " " + name).lower()
                if not ("game" in low or "jogo" in low):
                    continue
                kind = "atalho"
            else:
                kind = "jogo"
            exec_raw = data.get("Exec", "")
            program, args = _split_exec(exec_raw)
            pending.append((path, name, kind, cats, exec_raw, program, args,
                            data))

    # 2a passada: resolve todos os executaveis de uma vez
    resolved_map = _which_many([p[5] for p in pending])

    # 3a passada: monta os GameEntry
    for (path, name, kind, cats, exec_raw, program, args, data) in pending:
        resolved = resolved_map.get(program) if program else None
        launch_cmd = None
        if resolved:
            launch_cmd = " ".join([resolved] + list(args))

        size_bytes = 0
        if resolved:
            try:
                size_bytes = os.path.getsize(resolved)
            except Exception:
                size_bytes = 0

        playable = bool(resolved)
        reason = ""
        if not exec_raw:
            reason = "o .desktop nao tem comando Exec"
        elif not resolved:
            reason = "executavel '%s' nao encontrado no PATH" % program

        platform = _platform_from_categories(cats)
        if kind == "atalho" and platform == "Linux":
            platform = "Atalho"

        out.append(GameEntry(
            name=name or os.path.basename(path),
            path=path,
            launch_cmd=launch_cmd,
            kind=kind,
            icon=data.get("Icon", "") or "gamepad",
            size=human_size(size_bytes) if size_bytes else "-",
            platform=platform,
            playable=playable,
            reason=reason,
            size_bytes=size_bytes,
        ))
    out.sort(key=lambda e: e.name.lower())
    return out


def emulator_catalog(path=None, force=False):
    """Todos os emuladores conhecidos, com o estado real de instalacao.

    Devolve uma lista de dicts: ``name`` (binario), ``label``, ``cmd``
    (caminho absoluto ou None), ``installed`` (bool) e ``note``.

    O resultado fica em cache por PATH (a busca de binarios no PATH e
    lenta em sistemas de arquivos em rede); use ``force=True`` para
    reler (botao "Reescanear").
    """
    key = path if path is not None else os.environ.get("PATH", "")
    if not force:
        hit = _CATALOG_CACHE.get(key)
        if hit is not None:
            return [dict(e) for e in hit]
    out = []
    found = _which_many([e[0] for e in EMULATORS], path=path)
    for emu_key, label, note in EMULATORS:
        cmd = found.get(emu_key)
        out.append({
            "name": emu_key,
            "label": label,
            "cmd": cmd,
            "installed": bool(cmd),
            "note": note,
        })
    _CATALOG_CACHE[key] = [dict(e) for e in out]
    return [dict(e) for e in out]


def scan_emulators(path=None):
    """Emuladores REALMENTE instalados (apenas os que existem no PATH).

    Devolve lista de dicts ``{'name', 'cmd', 'installed': True, ...}``.
    """
    return [e for e in emulator_catalog(path=path) if e["installed"]]


def scan_roms(dirs=None, limit=500, max_depth=3, deadline=None):
    """Procura arquivos de ROM existentes (somente leitura).

    Varre ``~/Games``, ``~/ROMs``, ``/home/<usuario>/Games`` e ``/mnt``
    (ou os diretorios informados) com limite de profundidade e de
    quantidade de arquivos. **NUNCA cria pastas.**
    """
    if dirs is None:
        dirs = _default_rom_dirs()
    catalog = emulator_catalog()
    installed = dict((e["name"], e["cmd"]) for e in catalog
                     if e.get("installed"))

    out = []
    for base in dirs:
        if not base:
            continue
        if deadline is not None and time.time() > deadline:
            break
        try:
            if not os.path.isdir(base):
                continue
        except Exception:
            continue
        base_depth = base.rstrip("/").count("/")
        try:
            walker = os.walk(base, topdown=True)
        except Exception:
            continue
        for dirpath, dirnames, filenames in walker:
            depth = dirpath.rstrip("/").count("/") - base_depth
            if depth >= max_depth:
                dirnames[:] = []          # nao desce mais
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in sorted(filenames):
                ext = os.path.splitext(fn)[1].lower()
                if ext not in ROM_EXTENSIONS:
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    size_bytes = os.path.getsize(full)
                except Exception:
                    size_bytes = 0
                candidates = ROM_EMULATORS.get(ext, ())
                emu_key = None
                emu_cmd = None
                for key in candidates:
                    if key in installed:
                        emu_key = key
                        emu_cmd = installed[key]
                        break
                playable = emu_cmd is not None
                if playable:
                    launch_cmd = "%s %s" % (emu_cmd, shlex.quote(full))
                    reason = ""
                else:
                    launch_cmd = None
                    if candidates:
                        reason = ("nenhum emulador instalado para %s "
                                  "(%s)" % (ext, ", ".join(candidates)))
                    else:
                        reason = "sem emulador conhecido para %s" % ext
                out.append(GameEntry(
                    name=os.path.splitext(fn)[0],
                    path=full,
                    launch_cmd=launch_cmd,
                    kind="rom",
                    icon="gamepad",
                    size=human_size(size_bytes),
                    platform=ROM_PLATFORM.get(ext, ext.lstrip(".").upper()),
                    playable=playable,
                    reason=reason,
                    size_bytes=size_bytes,
                ))
                if len(out) >= limit:
                    return out
            if deadline is not None and time.time() > deadline:
                break
    return out


def scan_controllers(proc_path="/proc/bus/input/devices",
                     dev_dir="/dev/input"):
    """Detecta controles de videogame REAIS.

    Le ``/proc/bus/input/devices`` procurando dispositivos com
    "joystick"/"gamepad" e pega o caminho ``/dev/input/eventN``;
    verifica tambem a existencia de ``/dev/input/js*``.

    Devolve lista de dicts ``{'name', 'device', 'present'}`` (mais
    ``js`` e ``kind``, apenas informativos). Nao instala driver.
    """
    out = []
    text = _read_text(proc_path)
    if text:
        for block in text.split("\n\n"):
            low = block.lower()
            if "joystick" not in low and "gamepad" not in low:
                continue
            name = ""
            m = re.search(r'^N:\s*Name="([^"]*)"', block, re.M)
            if m:
                name = m.group(1).strip()
            device = ""
            js = ""
            m = re.search(r"^H:\s*Handlers=(.*)$", block, re.M)
            if m:
                handlers = m.group(1)
                for tok in handlers.split():
                    if tok.startswith("event"):
                        device = os.path.join(dev_dir, tok)
                    elif tok.startswith("js"):
                        js = os.path.join(dev_dir, tok)
            if not name:
                name = "controle"
            present = bool(device) and os.path.exists(device)
            out.append({
                "name": name,
                "device": device,
                "present": present,
                "js": js,
                "kind": "joystick",
            })
    # dispositivos js* que nao apareceram no arquivo de dispositivos
    known_js = set(o["js"] for o in out if o.get("js"))
    try:
        for js in sorted(glob.glob(os.path.join(dev_dir, "js*"))):
            if js in known_js:
                continue
            out.append({
                "name": os.path.basename(js),
                "device": js,
                "present": os.path.exists(js),
                "js": js,
                "kind": "joystick",
            })
    except Exception:
        pass
    return out


def _has_gl():
    """Existe OpenGL/GLES no sistema? (procura de verdade, no cache do SO)"""
    if _GL_CACHE:
        return _GL_CACHE[0]
    found = False
    names = ("GL", "GLESv2", "OpenGL")
    for n in names:
        try:
            if ctypes.util.find_library(n):
                found = True
                break
        except Exception:
            pass
    if not found:
        dirs = ["/usr/lib", "/usr/lib64", "/lib", "/lib64", "/usr/local/lib",
                "/usr/lib/aarch64-linux-gnu", "/usr/lib/arm-linux-gnueabihf"]
        pats = ("libGL.so.1", "libGLESv2.so.2", "libGLESv2.so", "libGL.so",
                "libOpenGL.so.0")
        for d in dirs:
            for pat in pats:
                try:
                    if glob.glob(os.path.join(d, pat)):
                        found = True
                        break
                except Exception:
                    pass
            if found:
                break
    _GL_CACHE.append(found)
    return found


def _drm_connectors():
    """Conectores DRM reais (lista de dicts). Vazio se nao houver."""
    out = []
    for c in _drm_cards():
        out.extend(c["connectors"])
    return out


#: drivers de DRM que NAO sao GPU de verdade (painel/framebuffer virtual)
_FAKE_GPU_DRIVERS = ("simple-framebuffer", "simplefb", "ofdrm", "bochs-drm",
                     "bochs", "vesa", "vgem", "vgacon", "drm_kms_helper")


def _drm_cards():
    """Cartoes DRM do sistema: driver + conectores (leitura de /sys)."""
    cards = []
    base = "/sys/class/drm"
    try:
        names = sorted(os.listdir(base))
    except Exception:
        names = []
    card_names = [n for n in names
                  if n.startswith("card") and n[4:].isdigit()]
    for name in card_names:
        driver = ""
        try:
            driver = os.path.basename(
                os.readlink(os.path.join(base, name, "device", "driver")))
        except Exception:
            driver = ""
        conns = []
        for c in names:
            if c.startswith(name + "-"):
                conns.append({
                    "card": name,
                    "connector": c[len(name) + 1:],
                    "status": _read_text(os.path.join(base, c,
                                                     "status")).strip() or None,
                })
        cards.append({"card": name, "driver": driver, "connectors": conns})
    return cards


def graphics_status():
    """Estado honesto do subsistema grafico.

    Devolve ``{'accel': bool, 'gl': bool, 'drm': [...], 'note': str}``.

    So existe aceleracao 3D de verdade quando ha OpenGL **e** uma GPU
    real (um cartao DRM cujo driver nao e um framebuffer virtual). Sem
    isso a nota e exatamente ``"sem aceleracao 3D (sem GPU/OpenGL)"``.
    """
    gl = _has_gl()
    cards = _drm_cards()
    drm = []
    for c in cards:
        drm.extend(c["connectors"])

    if SysInfo is not None and not drm:
        try:
            drm = SysInfo().drm_info() or []
        except Exception:
            drm = []

    real_gpu = False
    for c in cards:
        drv = (c.get("driver") or "").lower()
        if drv in _FAKE_GPU_DRIVERS:
            continue
        if c["connectors"]:
            real_gpu = True

    accel = bool(gl and real_gpu)
    detail = ""
    if accel:
        note = "aceleracao 3D disponivel (OpenGL + GPU real)"
        if drm:
            note += " — %d conector(es) DRM" % len(drm)
    else:
        note = NO_ACCEL_NOTE
        if gl and not real_gpu:
            detail = ("OpenGL esta no sistema, mas nao ha GPU real "
                      "(so framebuffer virtual)")
        elif not gl:
            detail = "OpenGL/GLES nao encontrado no sistema"
    return {"accel": accel, "gl": gl, "drm": drm, "note": note,
            "detail": detail}


# --------------------------------------------------------------------
# o aplicativo
# --------------------------------------------------------------------

class GameHub(App):
    """Central de jogos do NURA OS."""

    title = "NURA Game Hub"
    icon = "gamepad"
    width = 1080
    height = 680
    min_width = 640
    min_height = 440
    resizable = True

    def __init__(self, shell=None, **kw):
        App.__init__(self, shell=shell, **kw)
        self.tab = 0
        self.scroll = 0.0
        self.entries = []          # biblioteca (jogos/atalhos)
        self.roms = []             # ROMs encontradas
        self.emu_catalog = []      # todos os emuladores conhecidos
        self.controllers = []
        self.gfx = graphics_status()
        self.status_msg = ""
        self.fullscreen = False
        self.ui_scale = 1.0
        self.theme_key = "neon"
        # diretorios usados pelas varreduras (None = padrao do sistema)
        self.game_dirs = None
        self.rom_dirs = None

        # leitura ao vivo do joystick
        self.ctrl_test = False
        self.js_path = ""
        self.js_fd = -1
        self.js_axes = {}
        self.js_buttons = {}
        self.js_error = ""

        # momento de abertura (a busca de ROMs e adiada)
        self._open_time = 0.0
        self._roms_scanned = True

        # interacao
        self._hot = []             # hotspots do ultimo layout
        self._pressed = None
        self._theme = None
        self._area_cache = (0, 0, int(self.width), int(self.height))
        self._tick_acc = 0.0
        self._drag_from = None

    # ---------------------------------------------------------------
    # ciclo de vida
    # ---------------------------------------------------------------

    def on_open(self):
        # varredura rapida: a busca de ROMs e feita depois (on_tick),
        # para a janela aparecer na hora
        self._open_time = time.time()
        self._roms_scanned = False
        self.refresh(deep=False)

    def on_close(self):
        self._close_js()

    def on_focus(self, focused):
        pass

    # ---------------------------------------------------------------
    # dados
    # ---------------------------------------------------------------

    def refresh(self, game_dirs=None, rom_dirs=None, deep=True):
        """Refaz todas as varreduras (somente leitura)."""
        if game_dirs is None:
            game_dirs = self.game_dirs
        if rom_dirs is None:
            rom_dirs = self.rom_dirs
        self.gfx = graphics_status()
        self.emu_catalog = emulator_catalog(force=True)
        self.entries = scan_games(dirs=game_dirs, emulators=self.emu_catalog)
        if deep:
            deadline = time.time() + 3.0
            self.roms = scan_roms(dirs=rom_dirs, limit=500, max_depth=3,
                                  deadline=deadline)
            self._roms_scanned = True
        else:
            self.roms = []
        self.controllers = scan_controllers()
        self._sync_js_path()
        return self

    def _scan_roms_later(self):
        """Busca as ROMs (uma vez, depois que a janela ja apareceu)."""
        if self._roms_scanned:
            return
        self._roms_scanned = True
        deadline = time.time() + 2.5
        try:
            self.roms = scan_roms(dirs=self.rom_dirs, limit=500, max_depth=3,
                                  deadline=deadline)
        except Exception:
            self.roms = []

    # atalhos usados pela interface (metodos = delegam para as funcoes)
    def scan_games(self, dirs=None):
        return scan_games(dirs=dirs)

    def scan_emulators(self):
        return scan_emulators()

    def scan_roms(self, dirs=None):
        return scan_roms(dirs=dirs)

    def scan_controllers(self):
        return scan_controllers()

    def graphics_status(self):
        return graphics_status()

    # ---------------------------------------------------------------
    # utilitarios internos
    # ---------------------------------------------------------------

    def _theme_obj(self):
        th = self._theme
        if th is not None:
            return th
        shell = self.shell
        if shell is not None:
            th = getattr(shell, "theme", None)
            if th is not None:
                self._theme = th
                return th
        if Theme is not None:
            self._theme = Theme(self.theme_key)
            return self._theme
        return None

    def _area(self, p=None):
        if self.window is not None:
            try:
                return self.window.content_rect()
            except Exception:
                pass
        if p is not None:
            try:
                target = p.ctx.get_target()
                return (0, 0, int(target.get_width()),
                        int(target.get_height()))
            except Exception:
                pass
        return self._area_cache

    def _notify(self, msg, kind="info"):
        shell = self.shell
        if shell is not None and hasattr(shell, "notify"):
            try:
                shell.notify(msg, kind=kind)
                return
            except TypeError:
                try:
                    shell.notify(msg)
                    return
                except Exception:
                    pass
            except Exception:
                pass
        self.status_msg = msg

    def _fit(self, p, s, max_w, size=None, weight="normal"):
        """Corta o texto para caber em max_w."""
        if not s:
            return ""
        size = size or p.theme.font
        if p.tw(s, size, weight) <= max_w:
            return s
        s = str(s)
        while s and p.tw(s + "...", size, weight) > max_w:
            s = s[:-1]
        return (s + "...") if s else ""

    # ---------------------------------------------------------------
    # acoes
    # ---------------------------------------------------------------

    def _launch_entry(self, entry):
        if entry is None or not entry.playable or not entry.launch_cmd:
            self._notify("Este item nao pode ser iniciado aqui.", "warn")
            return
        shell = self.shell
        if shell is None:
            self._notify("Sem shell: nenhum comando pode ser executado.",
                         "warn")
            return
        cmd = entry.launch_cmd

        def _go():
            if hasattr(shell, "launch"):
                try:
                    shell.launch(cmd)
                    self._notify("Iniciando %s" % entry.name)
                except Exception as e:
                    self._notify("Falha ao iniciar: %s" % e, "error")
            else:
                self._notify("O shell nao expoe launch().", "warn")

        if hasattr(shell, "confirm"):
            try:
                shell.confirm("Jogar %s?" % entry.name, cmd, _go)
                return
            except TypeError:
                pass
            except Exception:
                pass
        _go()

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        shell = self.shell
        if shell is not None and hasattr(shell, "set_fullscreen"):
            try:
                shell.set_fullscreen(self.fullscreen)
                self._notify("Tela cheia %s" %
                             ("ativada" if self.fullscreen else "desativada"))
            except Exception as e:
                self._notify("set_fullscreen falhou: %s" % e, "error")
        else:
            self._notify("Este shell nao expoe set_fullscreen().", "warn")

    def _change_scale(self, delta):
        shell = self.shell
        th = getattr(shell, "theme", None) if shell is not None else None
        base = self.ui_scale
        if th is not None:
            try:
                base = float(getattr(th, "ui_scale", base))
            except Exception:
                pass
        value = max(0.8, min(1.4, round(base + delta, 2)))
        self.ui_scale = value
        if th is not None and hasattr(th, "set_scale"):
            try:
                th.set_scale(value)
                self._notify("Escala da interface: %.1fx" % value)
                return
            except Exception as e:
                self._notify("set_scale falhou: %s" % e, "error")
                return
        self._notify("Escala da interface: %.1fx (local)" % value)

    def _change_theme(self, key):
        if key not in THEME_NAMES:
            return
        self.theme_key = key
        shell = self.shell
        th = getattr(shell, "theme", None) if shell is not None else None
        if th is not None and hasattr(th, "reload"):
            try:
                th.reload(key)
                self._theme = th
                self._notify("Tema: %s" % key)
                return
            except Exception as e:
                self._notify("reload falhou: %s" % e, "error")
                return
        self._notify("Tema: %s (local)" % key)

    def _rescan(self):
        self.refresh()
        self._notify("Varredura concluida: %d jogo(s), %d ROM(s)" %
                     (len(self.entries), len(self.roms)))

    def _toggle_ctrl_test(self):
        if not self.controllers:
            self._notify("Nenhum controle detectado.", "warn")
            return
        self.ctrl_test = not self.ctrl_test
        if self.ctrl_test:
            self._sync_js_path()
            self._notify("Lendo %s (somente leitura)"
                         % (self.js_path or "/dev/input/js0"))
        else:
            self._close_js()

    def _sync_js_path(self):
        if self.js_path:
            return
        for c in self.controllers:
            js = c.get("js")
            if js and os.path.exists(js):
                self.js_path = js
                return
        try:
            found = sorted(glob.glob("/dev/input/js*"))
        except Exception:
            found = []
        if found:
            self.js_path = found[0]

    # ---------------------------------------------------------------
    # leitura do joystick (somente leitura)
    # ---------------------------------------------------------------

    def _close_js(self):
        if self.js_fd >= 0:
            try:
                os.close(self.js_fd)
            except Exception:
                pass
        self.js_fd = -1

    def _read_js(self):
        """Le o joystick nao-bloqueante e atualiza eixos/botoes."""
        if not self.ctrl_test:
            return
        if self.js_fd < 0:
            path = self.js_path or "/dev/input/js0"
            try:
                self.js_fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                self.js_error = ""
            except OSError as e:
                self.js_error = "nao foi possivel ler %s: %s" % (path, e)
                return
        try:
            data = os.read(self.js_fd, 4096)
        except (BlockingIOError, OSError):
            return
        except Exception as e:
            self.js_error = str(e)
            self._close_js()
            return
        if not data:
            return
        n = len(data) // JS_EVENT_SIZE
        for i in range(n):
            try:
                _t, value, etype, number = struct.unpack_from(
                    JS_EVENT_FMT, data, i * JS_EVENT_SIZE)
            except Exception:
                break
            if etype & JS_EVENT_INIT:
                etype &= ~JS_EVENT_INIT
            if etype == JS_EVENT_AXIS:
                v = max(-1.0, min(1.0, value / 32767.0))
                self.js_axes[number] = v
            elif etype == JS_EVENT_BUTTON:
                self.js_buttons[number] = bool(value)

    # ---------------------------------------------------------------
    # layout (usado pelo desenho E pelo toque — sempre igual)
    # ---------------------------------------------------------------

    def _layout(self):
        th = self._theme_obj()
        area = self._area()
        x, y, w, h = area
        gap = max(8, int(getattr(th, "gap", 12))) if th else 12
        pad = int(getattr(th, "pad", 14)) if th else 14
        geo = {"area": area, "hot": [], "tabs": [], "content": None,
               "cards": [], "rows": [], "banner": None, "buttons": [],
               "live": None, "gap": gap, "pad": pad}

        # ---- abas ----
        tab_h = 48
        rescan_w = 110
        avail = w - 2 * pad - rescan_w - gap
        n = len(TABS)
        tw = int(max(80, min(210, (avail - (n - 1) * gap) / float(n))))
        tx = x + pad
        for i, label in enumerate(TABS):
            r = (tx, y + 6, tw, tab_h)
            geo["tabs"].append({"label": label, "rect": r,
                                "active": i == self.tab})
            geo["hot"].append(("tab:%d" % i, r, ("tab", i)))
            tx += tw + gap
        # botao reescanear (acao real: refaz a varredura)
        rscan = (x + w - pad - rescan_w, y + 6, rescan_w, tab_h)
        geo["buttons"].append({"id": "rescan", "rect": rscan,
                                "label": "Reescanear", "disabled": False})
        geo["hot"].append(("rescan", rscan, ("rescan",)))

        cy = y + 6 + tab_h + gap
        ch = h - (6 + tab_h + gap) - pad
        content = (x, cy, w, max(0, ch))
        geo["content"] = content

        if self.tab == 0:
            self._layout_library(geo, th, content, gap, pad)
        elif self.tab == 1:
            self._layout_emulators(geo, th, content, gap, pad)
        elif self.tab == 2:
            self._layout_controllers(geo, th, content, gap, pad)
        else:
            self._layout_settings(geo, th, content, gap, pad)
        return geo

    # -- biblioteca ---------------------------------------------------

    def _layout_library(self, geo, th, content, gap, pad):
        x, y, w, h = content
        banner_h = 0
        if not self.gfx.get("accel"):
            banner_h = 40
            geo["banner"] = (x, y, w, banner_h)
        top = y + banner_h + (gap if banner_h else 0)

        # lista = jogos + ROMs encontradas
        items = list(self.entries) + list(self.roms)
        card_w = 210
        card_h = 244
        cols = max(1, int((w + gap) // (card_w + gap)))
        rows = (len(items) + cols - 1) // cols if items else 0
        content_h = rows * (card_h + gap) - gap if rows else 0
        view_h = max(0, y + h - top)
        max_scroll = max(0, content_h - view_h)
        if self.scroll > max_scroll:
            self.scroll = float(max_scroll)
        if self.scroll < 0:
            self.scroll = 0.0

        reserve = 14 if max_scroll > 0 else 0
        grid_w = w - reserve
        for i, entry in enumerate(items):
            col = i % cols
            row = i // cols
            cx = x + col * (card_w + gap)
            cy2 = top + row * (card_h + gap) - self.scroll
            card = (cx, cy2, card_w, card_h)
            btn = (cx + 10, cy2 + card_h - 54, card_w - 20, 44)
            geo["cards"].append({"rect": card, "entry": entry,
                                 "button": btn, "index": i})
            if entry.playable:
                geo["hot"].append(("play:%d" % i, btn, ("play", i)))
        geo["scroll"] = {"max": max_scroll, "view": view_h, "top": top,
                         "x": x + w - 10, "h": view_h}
        geo["items"] = items

    # -- emuladores ---------------------------------------------------

    def _layout_emulators(self, geo, th, content, gap, pad):
        x, y, w, h = content
        header_h = (int(getattr(th, "font_small", 14)) + 16) if th else 30
        top = y + header_h
        row_h = 54
        cat = self.emu_catalog or emulator_catalog()
        view_h = max(0, y + h - top)
        max_scroll = max(0, len(cat) * row_h - view_h)
        if self.scroll > max_scroll:
            self.scroll = float(max_scroll)
        if self.scroll < 0:
            self.scroll = 0.0
        for i, e in enumerate(cat):
            ry = top + i * row_h - self.scroll
            rect = (x, ry, w, row_h - 6)
            geo["rows"].append({"rect": rect, "emu": e})
            if e["installed"]:
                geo["hot"].append(("emu:%s" % e["name"], rect,
                                   ("emu", e["name"])))
        geo["scroll"] = {"max": max_scroll, "view": view_h, "top": top,
                         "x": x + w - 10, "h": view_h}

    # -- controles ----------------------------------------------------

    def _layout_controllers(self, geo, th, content, gap, pad):
        x, y, w, h = content
        btn_w = 190
        test_rect = (x, y, btn_w, 48)
        geo["buttons"].append({"id": "test_ctrl", "rect": test_rect,
                                "label": "Testar controle", "disabled": False})
        geo["hot"].append(("test_ctrl", test_rect, ("test_ctrl",)))
        ty = y + 48 + gap
        row_h = 54
        max_scroll = max(0, len(self.controllers) * row_h - (h - 60))
        if self.scroll > max_scroll:
            self.scroll = float(max_scroll)
        if self.scroll < 0:
            self.scroll = 0.0
        for i, c in enumerate(self.controllers):
            ry = ty + i * row_h - self.scroll
            rect = (x, ry, w, row_h - 6)
            geo["rows"].append({"rect": rect, "ctrl": c})
        geo["scroll"] = {"max": max_scroll, "view": h - 60, "top": ty,
                         "x": x + w - 10, "h": max(0, h - 60)}
        if self.ctrl_test:
            live_h = min(220, max(120, h - 60 - len(self.controllers) * row_h))
            geo["live"] = (x, ty + len(self.controllers) * row_h -
                           self.scroll, w, live_h)

    # -- configuracoes ------------------------------------------------

    def _layout_settings(self, geo, th, content, gap, pad):
        x, y, w, h = content
        row_h = 66
        # tela cheia
        fs_w = 170
        fs_rect = (x + w - pad - fs_w, y + 8, fs_w, 48)
        geo["buttons"].append({"id": "fullscreen", "rect": fs_rect,
                                "label": "Ativar" if not self.fullscreen
                                else "Desativar",
                                "disabled": False})
        geo["hot"].append(("fullscreen", fs_rect, ("fullscreen",)))
        # escala
        minus = (x + w - pad - 200, y + row_h + 12, 54, 48)
        plus = (x + w - pad - 54, y + row_h + 12, 54, 48)
        geo["buttons"].append({"id": "scale-", "rect": minus, "label": "-",
                                "disabled": False})
        geo["buttons"].append({"id": "scale+", "rect": plus, "label": "+",
                                "disabled": False})
        geo["hot"].append(("scale-", minus, ("scale", -0.1)))
        geo["hot"].append(("scale+", plus, ("scale", 0.1)))
        # temas
        ty = y + row_h * 2 + 44
        bw = 120
        tx = x
        for i, name in enumerate(THEME_NAMES):
            rect = (tx, ty, bw, 48)
            geo["buttons"].append({"id": "theme:%s" % name, "rect": rect,
                                    "label": name, "disabled": False})
            geo["hot"].append(("theme:%s" % name, rect, ("theme", name)))
            tx += bw + gap
        geo["theme_y"] = ty

    # ---------------------------------------------------------------
    # desenho
    # ---------------------------------------------------------------

    def draw(self, p):
        th = p.theme
        self._theme = th
        area = self._area(p)
        self._area_cache = area
        geo = self._layout()
        self._hot = geo["hot"]

        x, y, w, h = area
        p.rect(x, y, w, h, th.bg, 1.0)

        # fundo decorativo (mesmo espirito do papel de parede do NURA)
        p.gradient_v(x, y, w, h, (th.bg[0], th.bg[1], th.bg[2], 1.0),
                     (th.bg2[0], th.bg2[1], th.bg2[2], 1.0))

        # ---- abas ----
        for tab in geo["tabs"]:
            tx, ty, tw, tht = tab["rect"]
            if tab["active"]:
                p.round(tx, ty, tw, tht, th.radius, th.accent, 0.22)
                p.round(tx, ty, tw, tht, th.radius, th.accent, 0.0,
                        filled=False, width=1.0)
                p.text(tab["label"], tx + tw / 2, ty + tht / 2 + th.font / 3,
                       th.font, th.accent, "bold", "center")
            else:
                p.round(tx, ty, tw, tht, th.radius, th.panel_hi, 0.55)
                p.text(tab["label"], tx + tw / 2, ty + tht / 2 + th.font / 3,
                       th.font, th.dim, "normal", "center")

        # ---- botao reescanear ----
        for b in geo["buttons"]:
            if b["id"] != "rescan":
                continue
            self._draw_button(p, b)

        content = geo["content"]
        if self.tab == 0:
            self._draw_library(p, geo, content)
        elif self.tab == 1:
            self._draw_emulators(p, geo, content)
        elif self.tab == 2:
            self._draw_controllers(p, geo, content)
        else:
            self._draw_settings(p, geo, content)

        # ---- rodape: estado honesto ----
        pad = geo.get("pad", 14)
        if self.status_msg:
            p.text(self._fit(p, self.status_msg, w - 2 * pad), x + pad,
                   y + h - 6, th.font_small, th.dim)
        elif not self.gfx.get("accel") and self.tab != 0:
            p.text(self._fit(p, NO_ACCEL_BANNER, w - 2 * pad), x + pad,
                   y + h - 6, th.font_small, th.warn)

    def _draw_button(self, p, b, pressed=False):
        th = p.theme
        x, y, w, h = b["rect"]
        if b.get("disabled"):
            p.round(x, y, w, h, th.radius, th.panel_hi, 0.35)
            p.text(b["label"], x + w / 2, y + h / 2 + th.font_small / 3,
                   th.font_small, th.dim2, "normal", "center")
            return
        p.button(x, y, w, h, b["label"], pressed=pressed)

    def _draw_library(self, p, geo, content):
        th = p.theme
        x, y, w, h = content
        items = geo.get("items") or []

        # banner honesto
        banner = geo.get("banner")
        if banner:
            bx, by, bw, bh = banner
            p.round(bx, by, bw, bh, th.radius, th.warn, 0.16)
            p.round(bx, by, bw, bh, th.radius, th.warn, 0.0, filled=False,
                    width=1.0)
            p.icon("info", bx + 20, by + bh / 2, 22, th.warn)
            p.text(self._fit(p, NO_ACCEL_BANNER, bw - 44),
                   bx + 38, by + bh / 2 + th.font_small / 3, th.font_small,
                   th.warn)

        if not items:
            # estado vazio honesto
            cx = x + w / 2
            cy = y + min(160, h / 2)
            p.app_icon("gamepad", cx, cy, 84)
            p.text("Nenhum jogo instalado", cx, cy + 74, th.font_title,
                   th.text, "bold", "center")
            p.text("o hub apenas detecta o que ja existe no aparelho",
                   cx, cy + 102, th.font_small, th.dim, "normal", "center")
            p.text("(nada e instalado automaticamente)", cx, cy + 126,
                   th.font_small, th.dim2, "normal", "center")
            # botao desabilitado
            bw2 = 160
            p.round(cx - bw2 / 2, cy + 146, bw2, 44, th.radius, th.panel_hi,
                    0.35)
            p.text("Jogar", cx, cy + 146 + 22 + th.font_small / 3,
                   th.font_small, th.dim2, "normal", "center")
            return

        for card in geo["cards"]:
            cx, cy, cw, ch = card["rect"]
            if cy + ch < y - 40 or cy > y + h + 40:
                continue
            entry = card["entry"]
            p.panel(cx, cy, cw, ch, th.panel, 0.92, r=th.radius)
            # capa
            cover = (cx + 10, cy + 10, cw - 20, 112)
            p.round(cover[0], cover[1], cover[2], cover[3], th.radius,
                    th.panel_hi, 0.85)
            p.round(cover[0], cover[1], cover[2], cover[3], th.radius,
                    th.accent, 0.35, filled=False, width=1.0)
            p.app_icon("gamepad", cover[0] + cover[2] / 2,
                       cover[1] + cover[3] / 2, 60)
            # textos
            p.text(self._fit(p, entry.name, cw - 20), cx + 10, cy + 142,
                   th.font_small, th.text, "bold")
            p.text(self._fit(p, entry.platform, cw - 20), cx + 10, cy + 163,
                   th.font_small, th.dim)
            if entry.playable:
                p.text(entry.size, cx + 10, cy + 183, th.font_small, th.dim2)
            else:
                p.text(self._fit(p, entry.reason or "nao jogavel", cw - 20),
                       cx + 10, cy + 183, th.font_small, th.warn)
            # botao jogar
            bx, by, bw, bh = card["button"]
            if entry.playable:
                p.button(bx, by, bw, bh, "Jogar",
                         pressed=("play:%d" % card["index"]) ==
                         self._pressed)
            else:
                p.round(bx, by, bw, bh, th.radius, th.panel_hi, 0.35)
                p.text("Indisponivel", bx + bw / 2,
                       by + bh / 2 + th.font_small / 3, th.font_small,
                       th.dim2, "normal", "center")

        sc = geo.get("scroll")
        if sc and sc["max"] > 0:
            frac = self.scroll / float(sc["max"])
            p.scrollbar(sc["x"], sc["top"], 8, sc["h"], frac,
                        view=max(0.1, sc["view"] / float(sc["max"] + sc["view"])))

    def _draw_emulators(self, p, geo, content):
        th = p.theme
        x, y, w, h = content
        p.text("Emuladores instalados no sistema (PATH). O hub nao instala "
               "nada.", x, y + th.font_small, th.font_small, th.dim)
        for row in geo["rows"]:
            rx, ry, rw, rh = row["rect"]
            if ry + rh < y - 10 or ry > y + h + 10:
                continue
            e = row["emu"]
            p.panel(rx, ry, rw, rh, th.panel, 0.9, r=th.radius)
            if e["installed"]:
                p.app_icon("gamepad", rx + 32, ry + rh / 2, 34)
                p.text(self._fit(p, e["label"], rw - 60), rx + 62,
                       ry + rh / 2 - 2, th.font_small, th.text, "bold")
                p.text(self._fit(p, e["cmd"], rw - 60), rx + 62,
                       ry + rh / 2 + 18, th.font_small, th.ok)
            else:
                p.app_icon("gamepad", rx + 32, ry + rh / 2, 34)
                p.text(self._fit(p, e["label"], rw - 60), rx + 62,
                       ry + rh / 2 - 2, th.font_small, th.dim, "bold")
                p.text("nao instalado — %s" % e["note"], rx + 62,
                       ry + rh / 2 + 18, th.font_small, th.dim2)
        sc = geo.get("scroll")
        if sc and sc["max"] > 0:
            frac = self.scroll / float(sc["max"])
            p.scrollbar(sc["x"], sc["top"], 8, sc["h"], frac,
                        view=max(0.1, sc["view"] / float(sc["max"] + sc["view"])))

    def _draw_controllers(self, p, geo, content):
        th = p.theme
        x, y, w, h = content
        for b in geo["buttons"]:
            if b["id"] == "test_ctrl":
                self._draw_button(p, b,
                                  pressed=("test_ctrl" == self._pressed))
        ty = y + 48 + geo["gap"]
        if not self.controllers:
            p.app_icon("gamepad", x + w / 2, ty + 60, 70)
            p.text("nenhum controle detectado", x + w / 2, ty + 130,
                   th.font_title, th.text, "bold", "center")
            p.text("conecte um controle USB/BT e clique em Reescanear",
                   x + w / 2, ty + 158, th.font_small, th.dim, "normal",
                   "center")
            return
        for row in geo["rows"]:
            rx, ry, rw, rh = row["rect"]
            if ry + rh < ty - 10 or ry > y + h + 10:
                continue
            c = row["ctrl"]
            p.panel(rx, ry, rw, rh, th.panel, 0.9, r=th.radius)
            p.app_icon("gamepad", rx + 32, ry + rh / 2, 34)
            p.text(self._fit(p, c["name"], rw - 60), rx + 62,
                   ry + rh / 2 - 2, th.font_small, th.text, "bold")
            if c.get("present"):
                p.text(self._fit(p, c["device"] or c.get("js", ""), rw - 60),
                       rx + 62, ry + rh / 2 + 18, th.font_small, th.ok)
            else:
                p.text("dispositivo ausente", rx + 62, ry + rh / 2 + 18,
                       th.font_small, th.warn)
        # painel de leitura ao vivo
        live = geo.get("live")
        if live and self.ctrl_test:
            lx, ly, lw, lh = live
            p.panel(lx, ly, lw, lh, th.panel_hi, 0.85, r=th.radius)
            p.text("leitura ao vivo — %s" % (self.js_path or "sem device"),
                   lx + 14, ly + 24, th.font_small, th.text, "bold")
            if self.js_error:
                p.text(self._fit(p, self.js_error, lw - 28), lx + 14,
                       ly + 50, th.font_small, th.err)
            axes = self.js_axes
            buttons = self.js_buttons
            if not axes and not buttons:
                p.text("nenhum evento ainda — mexa nos eixos e botoes",
                       lx + 14, ly + 50, th.font_small, th.dim)
            else:
                names = []
                for num in sorted(axes.keys()):
                    names.append("eixo %d: %+.2f" % (num, axes[num]))
                txt = "   ".join(names) if names else "sem eixos"
                p.text(self._fit(p, txt, lw - 28), lx + 14, ly + 50,
                       th.font_small, th.accent)
                pressed = [str(n) for n in sorted(buttons.keys())
                           if buttons[n]]
                bt = ("botoes: " + ", ".join(pressed)) if pressed else \
                    "botoes: nenhum pressionado"
                p.text(self._fit(p, bt, lw - 28), lx + 14, ly + 76,
                       th.font_small, th.ok)
            p.text("somente leitura — nenhum driver e instalado",
                   lx + 14, ly + lh - 12, th.font_small, th.dim2)

    def _draw_settings(self, p, geo, content):
        th = p.theme
        x, y, w, h = content
        row_h = 66
        # tela cheia
        p.text("Tela cheia", x, y + 30, th.font, th.text, "bold")
        p.text("usa set_fullscreen() do shell (quando existir)",
               x, y + 52, th.font_small, th.dim)
        for b in geo["buttons"]:
            if b["id"] == "fullscreen":
                self._draw_button(p, b,
                                  pressed=("fullscreen" == self._pressed))
        # escala
        ey = y + row_h + 12
        p.text("Escala da interface", x, ey + 22, th.font, th.text, "bold")
        p.text("atual: %.1fx (0.8 a 1.4)" % self.ui_scale, x, ey + 44,
               th.font_small, th.dim)
        for b in geo["buttons"]:
            if b["id"] in ("scale-", "scale+"):
                self._draw_button(p, b, pressed=(b["id"] == self._pressed))
        # tema
        ty = geo.get("theme_y", y + row_h * 2 + 44)
        p.text("Tema de cores", x, ty - 16, th.font, th.text, "bold")
        for b in geo["buttons"]:
            if b["id"].startswith("theme:"):
                sel = b["id"] == "theme:%s" % self.theme_key
                if sel:
                    bx, by, bw, bh = b["rect"]
                    p.round(bx, by, bw, bh, th.radius, th.accent, 0.24)
                self._draw_button(p, b, pressed=(b["id"] == self._pressed))

    # ---------------------------------------------------------------
    # toque
    # ---------------------------------------------------------------

    def _hit(self, x, y):
        for hid, rect, action in self._hot:
            rx, ry, rw, rh = rect
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return (hid, rect, action)
        return None

    def _do_action(self, action):
        kind = action[0]
        if kind == "tab":
            self.tab = action[1]
            self.scroll = 0.0
        elif kind == "play":
            items = self._layout().get("items") or []
            idx = action[1]
            if 0 <= idx < len(items):
                self._launch_entry(items[idx])
        elif kind == "rescan":
            self._rescan()
        elif kind == "emu":
            for e in self.emu_catalog:
                if e["name"] == action[1] and e["installed"]:
                    self._notify("%s instalado em %s" % (e["label"], e["cmd"]))
                    break
        elif kind == "test_ctrl":
            self._toggle_ctrl_test()
        elif kind == "fullscreen":
            self._toggle_fullscreen()
        elif kind == "scale":
            self._change_scale(action[1])
        elif kind == "theme":
            self._change_theme(action[1])

    def on_touch(self, ev):
        et = getattr(ev, "type", "")
        x = getattr(ev, "x", 0)
        y = getattr(ev, "y", 0)

        if et == "down":
            hit = self._hit(x, y)
            self._pressed = hit[0] if hit else None
            self._drag_from = (x, y) if hit else None
            return bool(hit)
        if et == "up":
            hit = self._hit(x, y)
            pressed = self._pressed
            self._pressed = None
            self._drag_from = None
            if hit and hit[0] == pressed:
                self._do_action(hit[2])
                return True
            return False
        if et == "tap":
            hit = self._hit(x, y)
            if hit:
                self._do_action(hit[2])
                return True
            return False
        if et == "scroll":
            amount = float(getattr(ev, "amount", 0.0) or 0.0)
            geo = self._layout()
            sc = geo.get("scroll") or {"max": 0}
            self.scroll -= amount
            self.scroll = max(0.0, min(float(sc.get("max", 0)), self.scroll))
            return True
        if et == "drag":
            dy = float(getattr(ev, "dy", 0.0) or 0.0)
            geo = self._layout()
            sc = geo.get("scroll") or {"max": 0}
            if sc.get("max", 0) > 0 and dy:
                self.scroll -= dy
                self.scroll = max(0.0, min(float(sc["max"]), self.scroll))
                return True
            return False
        return False

    # ---------------------------------------------------------------
    # tick
    # ---------------------------------------------------------------

    def on_tick(self, dt):
        """So atualiza a leitura do controle (~150 ms)."""
        try:
            dt = float(dt)
        except Exception:
            dt = 0.0
        self._tick_acc += dt
        if self._tick_acc >= 0.15:
            self._tick_acc = 0.0
            if self.ctrl_test:
                self._read_js()
        # a busca de ROMs roda uma vez, depois que a janela ja apareceu
        if not self._roms_scanned and \
                (time.time() - getattr(self, "_open_time", 0.0)) > 0.6:
            self._scan_roms_later()


# --------------------------------------------------------------------
# relatorio de linha de comando (util para depurar no aparelho)
# --------------------------------------------------------------------

def _cli():
    gfx = graphics_status()
    print("NURA Game Hub — relatorio")
    print("  grafico: %s" % gfx["note"])
    print("  conectores DRM: %d" % len(gfx["drm"]))
    emu = scan_emulators()
    print("  emuladores instalados: %d" % len(emu))
    for e in emu:
        print("    - %s -> %s" % (e["name"], e["cmd"]))
    games = scan_games()
    print("  jogos: %d" % len(games))
    for g in games:
        print("    - %s [%s] jogavel=%s %s" %
              (g.name, g.platform, g.playable, g.reason))
    ctrls = scan_controllers()
    print("  controles: %d" % len(ctrls))
    for c in ctrls:
        print("    - %s (%s) presente=%s" %
              (c["name"], c["device"], c["present"]))


if __name__ == "__main__":                                  # pragma: no cover
    _cli()
    sys.exit(0)
