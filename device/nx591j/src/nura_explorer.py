#!/usr/bin/env python3
"""NURA OS - NURA Explorer (gerenciador de arquivos grafico).

Gerenciador de arquivos touch-first do NURA Desktop:

  * cabecalho com Voltar, Caminho, Home, Dispositivos, Ocultos,
    Atualizar e Pesquisar;
  * barra lateral com atalhos, uso real do armazenamento (via
    `nura_filemgr.storage()`) e dispositivos removiveis;
  * area principal com lista (ou grade) de entradas: icone, nome,
    tamanho e data;
  * barra de acoes no rodape: Novo, Copiar, Colar, Renomear, Excluir,
    Info e Abrir com;
  * toque prolongado num item abre uma barra de acoes no rodape
    (sem menu de botao direito);
  * visualizador de imagens embutido (`ImageViewerApp`), com zoom.

Regras:

  * nenhuma operacao privilegiada (sudo/chown/mount/rm -rf);
  * exclusao sempre com confirmacao explicita na propria UI antes de
    chamar a camada de arquivos;
  * erros de permissao aparecem na interface (nada e escondido);
  * todas as operacoes de arquivo passam por `nura_filemgr`.

Se `nura_filemgr` ainda nao existir, o app abre em modo degradado e
mostra "modulo de arquivos indisponivel" sem quebrar.

Coordenadas sempre em paisagem 1920x1080 (ver `nura_input`).
"""

import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cairo  # noqa: E402

import nura_theme as T  # noqa: E402
from nura_theme import Theme  # noqa: E402
from nura_window import App  # noqa: E402

try:                                     # camada de operacoes de arquivo
    from nura_filemgr import FileManager
except ImportError:                      # ainda nao existe -> degradado
    FileManager = None


# --------------------------------------------------------------------
# constantes de layout e conteudo
# --------------------------------------------------------------------

MIN_TOUCH = 44

SIDEBAR_W = 280
HEAD1_H = 66
HEAD2_H = 54
FOOTER_H = 78
FOOTER_ROW_H = 56
ACTION_H = 56
LIST_ROW_H = 56
LIST_HEAD_H = 34
GRID_CELL_H = 124

PAD = 10

IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif",
           ".tiff")
PNG_EXT = (".png",)

# atalhos da barra lateral (o "None" e resolvido em tempo de execucao)
SHORTCUTS = (
    ("Home", None),
    ("Raiz", "/"),
    ("Armazenamento", "/storage"),
    ("/mnt", "/mnt"),
    ("/media", "/media"),
    ("/run/media", "/run/media"),
)

FOOTER_ACTIONS = (
    ("novo", "Novo"),
    ("copiar", "Copiar"),
    ("colar", "Colar"),
    ("renomear", "Renomear"),
    ("excluir", "Excluir"),
    ("info", "Info"),
    ("abrir_com", "Abrir com"),
)

ACTION_ACTIONS = (
    ("abrir", "Abrir"),
    ("copiar", "Copiar"),
    ("mover", "Mover"),
    ("renomear", "Renomear"),
    ("excluir", "Excluir"),
    ("info", "Info"),
    ("abrir_com", "Abrir com"),
    ("fechar", "Fechar"),
)

# teclado virtual (touch-first) dos dialogos com texto
KB_ROWS = (
    ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
    ("q", "w", "e", "r", "t", "y", "u", "i", "o", "p"),
    ("a", "s", "d", "f", "g", "h", "j", "k", "l", "-"),
    ("z", "x", "c", "v", "b", "n", "m", "_", ".", "/"),
    (" ", "\b"),
)
KB_KEY_H = 46
KB_GAP = 6
KB_COLS = 10

STAT_LABELS = {
    "name": "Nome",
    "path": "Caminho",
    "type": "Tipo",
    "size": "Tamanho",
    "size_human": "Tamanho",
    "size_bytes": "Tamanho",
    "bytes": "Tamanho",
    "mtime": "Modificado em",
    "mtime_iso": "Modificado em",
    "mtime_human": "Modificado em",
    "ctime": "Criado em",
    "atime": "Acesso em",
    "mode": "Permissoes",
    "perms": "Permissoes",
    "permission": "Permissoes",
    "mode_oct": "Modo",
    "owner": "Dono",
    "user": "Dono",
    "group": "Grupo",
    "uid": "UID",
    "gid": "GID",
    "nlink": "Links",
    "is_dir": "Eh pasta",
    "isdir": "Eh pasta",
    "dir": "Eh pasta",
    "is_link": "Link simbolico",
    "is_image": "Imagem",
    "is_text": "Texto",
    "hidden": "Oculto",
    "symlink": "Link simbolico",
    "real_path": "Destino real",
    "target": "Destino",
    "label": "Rotulo",
    "fstype": "Sistema de arquivos",
    "device": "Dispositivo",
    "options": "Opcoes de montagem",
}


# --------------------------------------------------------------------
# utilitarios
# --------------------------------------------------------------------

_MCTX = None


def measure(s, size=14, weight="normal"):
    """Largura de um texto (sem depender de um Painter ativo)."""
    global _MCTX
    if _MCTX is None:
        _MCTX = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
    try:
        return T.text_width(_MCTX, s, size, weight)
    except Exception:
        return float(len(s) * size * 0.55)


def human_size(n):
    """Bytes -> texto legivel. 'None' quando o dado nao existe."""
    if n is None:
        return "-"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024.0 or unit == "TB":
            if unit == "B":
                return "%d B" % int(v)
            return "%.1f %s" % (v, unit)
        v /= 1024.0
    return "%.1f TB" % v


def human_date(ts):
    """Timestamp -> data curta ('-' quando nao existe)."""
    if not ts:
        return "-"
    try:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(float(ts)))
    except Exception:
        return "-"


def in_rect(rect, x, y):
    if not rect:
        return False
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def ellipsis(s, maxw, size=14, weight="normal"):
    """Corta o texto pela direita para caber em `maxw`."""
    s = str(s)
    if maxw <= 4:
        return ""
    if measure(s, size, weight) <= maxw:
        return s
    out = s
    while out and measure(out + "...", size, weight) > maxw:
        out = out[:-1]
    return (out + "...") if out else "..."


def ellipsis_left(s, maxw, size=14, weight="normal"):
    """Corta o texto pela esquerda (util para caminhos)."""
    s = str(s)
    if maxw <= 4:
        return ""
    if measure(s, size, weight) <= maxw:
        return s
    out = s
    while out and measure("..." + out, size, weight) > maxw:
        out = out[1:]
    return ("..." + out) if out else "..."


def is_image(name):
    return os.path.splitext(name or "")[1].lower() in IMG_EXT


def is_png(name):
    return os.path.splitext(name or "")[1].lower() in PNG_EXT


def join_path(base, name):
    if not name:
        return base
    if os.path.isabs(name):
        return name
    return os.path.join(base, name)


# --------------------------------------------------------------------
# aplicativo
# --------------------------------------------------------------------

class ExplorerApp(App):
    """Gerenciador de arquivos do NURA OS."""

    title = "NURA Explorer"
    icon = "folder"
    width = 1100
    height = 680
    min_width = 640
    min_height = 420
    resizable = True

    def __init__(self, shell=None, **kw):
        App.__init__(self, shell=shell, **kw)
        self.cwd = os.path.expanduser("~") or "/"
        self.entries = []            # entradas visiveis (ja filtradas)
        self.scroll = 0.0            # 0..1
        self.selected = -1           # indice em self.entries
        self.show_hidden = False
        self.view_mode = "lista"     # "lista" | "icones"
        self.clipboard = {}          # {"acao": ..., "path": ...}
        self.dialog = None           # ver DIALOG_KINDS
        self.overlay = None          # painel auxiliar (busca/paths/...)
        self.action_bar = None       # barra de acoes (toque prolongado)

        self.dirty = True
        self.status = ""
        self.status_kind = "info"
        self.error = ""
        self.history = []
        self.hist_idx = -1
        self.viewer = None
        self.viewer_is_window = False

        self._raw_entries = []
        self._storage = []
        self._devices = []
        self._dir_size = None
        self._btns = []
        self._modal_btns = []
        self._rects = {}
        self._modal = None
        self._pressed = None
        self._last_tap = -1
        self._t = 0.0
        self._status_ttl = 0.0
        self._own_theme = Theme("neon")
        self.fm = None
        self.fm_error = ""

    # ----------------------------------------------------------------
    # ciclo de vida
    # ----------------------------------------------------------------

    def on_open(self):
        self._ensure_fm()
        if self.fm is None:
            self.error = self.fm_error or "modulo de arquivos indisponivel"
            self.dirty = True
            return
        if not os.path.isdir(self.cwd):
            self.cwd = os.path.expanduser("~") or "/"
        self.history = [self.cwd]
        self.hist_idx = 0
        self._load_dir(self.cwd, history=False)
        self._refresh_system()
        self.dirty = True

    def on_close(self):
        self.dialog = None
        self.overlay = None
        self.viewer = None

    def on_focus(self, focused):
        if focused:
            self.dirty = True

    def on_tick(self, dt):
        """Nao redesenha se nada mudou: so marca `dirty` quando precisa."""
        self._t += dt
        if self._status_ttl > 0.0:
            self._status_ttl -= dt
            if self._status_ttl <= 0.0:
                self._status_ttl = 0.0
                self.status = ""
                self.dirty = True

    # ----------------------------------------------------------------
    # tema / shell
    # ----------------------------------------------------------------

    def _theme(self):
        sh = self.shell
        if sh is not None:
            th = getattr(sh, "theme", None)
            if th is not None:
                return th
        return self._own_theme

    def _notify(self, msg, kind="info"):
        """Mostra uma mensagem sem esconder o erro real."""
        self.status = str(msg)
        self.status_kind = kind
        self._status_ttl = 6.0 if kind == "info" else 0.0
        self.dirty = True
        sh = self.shell
        if sh is not None and hasattr(sh, "notify"):
            try:
                sh.notify(self.status, kind=kind)
                return
            except TypeError:
                try:
                    sh.notify(self.status)
                    return
                except Exception:
                    pass
            except Exception:
                pass

    def _fail(self, msg):
        """Erro de operacao: fica visivel ate a proxima acao."""
        self.error = str(msg)
        self.status = str(msg)
        self.status_kind = "err"
        self._status_ttl = 0.0
        self.dirty = True

    def _clear_error(self):
        if self.error:
            self.error = ""
            self.dirty = True

    # ----------------------------------------------------------------
    # camada de arquivos
    # ----------------------------------------------------------------

    def _ensure_fm(self):
        """Pega a camada de arquivos (shell -> modulo -> degradado)."""
        if self.fm is not None:
            return self.fm
        sh = self.shell
        if sh is not None:
            fm = getattr(sh, "filemgr", None)
            if fm is not None:
                self.fm = fm
                return fm
        if FileManager is None:
            self.fm_error = "modulo de arquivos indisponivel"
            return None
        try:
            self.fm = FileManager()
        except TypeError:
            try:
                self.fm = FileManager(root=os.path.expanduser("~") or "/")
            except Exception as e:
                self.fm = None
                self.fm_error = "erro ao iniciar a camada de arquivos: %s" % e
        except Exception as e:
            self.fm = None
            self.fm_error = "erro ao iniciar a camada de arquivos: %s" % e
        return self.fm

    def _fm_try(self, name, variants):
        """Chama um metodo da camada de arquivos tolerando assinaturas.

        `variants` e uma lista de (args, kwargs). Devolve (ok, resultado).
        """
        fn = getattr(self.fm, name, None)
        if fn is None:
            return False, "metodo ausente na camada de arquivos: %s" % name
        last = None
        for args, kwargs in variants:
            try:
                return True, fn(*args, **kwargs)
            except TypeError as e:
                msg = str(e)
                if ("argument" not in msg and "positional" not in msg and
                        "keyword" not in msg):
                    return False, "%s: %s" % (type(e).__name__, msg)
                last = msg
                continue
            except Exception as e:
                return False, "%s: %s" % (type(e).__name__, e)
        return False, last or "assinatura nao suportada: %s" % name

    # ---------------- listagem ----------------

    def _load_dir(self, path, history=True):
        """Le o diretorio e atualiza a lista de entradas."""
        self._ensure_fm()
        if self.fm is None:
            self._raw_entries = []
            self.entries = []
            self._clear_error()
            self.error = self.fm_error or "modulo de arquivos indisponivel"
            self.dirty = True
            return False
        ok, res = self._fm_try("listdir",
                                [((path,), {"show_hidden": self.show_hidden}),
                                 ((path,), {}),
                                 ((), {})])
        if not ok:
            self._raw_entries = []
            self.entries = []
            self._fail(res)
            return False
        if history:
            self._push_history(path)
        self.cwd = path
        self._raw_entries = self._norm_entries(res, path)
        self._apply_filter()
        self._clear_error()
        self._dir_size = self._read_du(path)
        self._last_tap = -1
        self.dirty = True
        return True

    def _norm_entries(self, raw, base):
        """Normaliza a saida de listdir() para uma lista de dicts."""
        out = []
        if raw is None:
            return out
        if isinstance(raw, dict):
            for key in ("entries", "items", "files", "list"):
                if isinstance(raw.get(key), (list, tuple)):
                    raw = raw[key]
                    break
            else:
                raw = list(raw.values())
        if not isinstance(raw, (list, tuple)):
            return out
        for it in raw:
            e = self._norm_entry(it, base)
            if e:
                out.append(e)
        return out

    def _norm_entry(self, it, base):
        d = {"name": "", "path": "", "is_dir": False, "size": None,
             "mtime": None, "ctime": None, "atime": None, "mode": None,
             "uid": None, "gid": None, "owner": None, "group": None,
             "is_link": False, "target": None, "kind_known": False}
        if isinstance(it, str):
            d["name"] = os.path.basename(it.rstrip("/")) or it
            d["path"] = it
        elif isinstance(it, dict):
            d["name"] = str(it.get("name") or it.get("fname") or
                            it.get("basename") or "")
            p = it.get("path") or it.get("full_path") or it.get("abs")
            d["path"] = str(p) if p else ""
            if "is_dir" in it:
                d["is_dir"] = bool(it["is_dir"])
                d["kind_known"] = True
            elif "isdir" in it:
                d["is_dir"] = bool(it["isdir"])
                d["kind_known"] = True
            elif "dir" in it:
                d["is_dir"] = bool(it["dir"])
                d["kind_known"] = True
            else:
                t = str(it.get("type", "")).lower()
                if t in ("dir", "directory", "folder", "pasta"):
                    d["is_dir"] = True
                    d["kind_known"] = True
            d["size"] = it.get("size", it.get("bytes", it.get("size_bytes")))
            d["mtime"] = it.get("mtime", it.get("modified", it.get("mtime_ts")))
            d["ctime"] = it.get("ctime", it.get("created", it.get("birth")))
            d["atime"] = it.get("atime", it.get("accessed"))
            d["mode"] = it.get("mode", it.get("perms", it.get("permissions")))
            d["uid"] = it.get("uid")
            d["gid"] = it.get("gid")
            d["owner"] = it.get("owner", it.get("user"))
            d["group"] = it.get("group")
            d["is_link"] = bool(it.get("is_link", False))
            d["target"] = it.get("target")
        elif isinstance(it, (list, tuple)):
            if not it:
                return None
            d["name"] = str(it[0])
            d["path"] = str(it[0])
            if len(it) > 1 and isinstance(it[1], dict):
                sub = self._norm_entry(it[1], base)
                sub["name"] = d["name"] or sub["name"]
                sub["path"] = d["path"] or sub["path"]
                return sub
        else:
            return None
        if not d["path"]:
            d["path"] = join_path(base, d["name"])
        if not d["name"]:
            d["name"] = os.path.basename(d["path"].rstrip("/")) or d["path"]
        if not d["kind_known"]:
            try:
                d["is_dir"] = os.path.isdir(d["path"])
            except Exception:
                d["is_dir"] = False
        if d["size"] is None and not d["is_dir"]:
            st = self._stat(d["path"])
            if st:
                d["size"] = st.get("size")
                if d["mtime"] is None:
                    d["mtime"] = st.get("mtime")
        return d

    def _apply_filter(self):
        """Aplica o filtro de ocultos e ordena (pastas primeiro)."""
        if self.show_hidden:
            vis = list(self._raw_entries)
        else:
            vis = [e for e in self._raw_entries
                   if not e["name"].startswith(".")]
        vis.sort(key=lambda e: (0 if e["is_dir"] else 1, e["name"].lower()))
        self.entries = vis
        if self.selected >= len(vis):
            self.selected = len(vis) - 1

    def _stat(self, path):
        """stat_info() da camada de arquivos (com reserva em os.stat)."""
        if self.fm is not None:
            ok, res = self._fm_try("stat_info", [((path,), {}), ((), {})])
            if ok and isinstance(res, dict):
                return res
        try:
            st = os.stat(path)
        except Exception:
            return None
        return {"name": os.path.basename(path), "path": path,
                "type": "dir" if os.path.isdir(path) else "file",
                "is_dir": os.path.isdir(path),
                "size": int(st.st_size), "mtime": st.st_mtime,
                "ctime": st.st_ctime, "atime": st.st_atime,
                "mode": st.st_mode, "uid": st.st_uid, "gid": st.st_gid}

    def _read_du(self, path):
        ok, res = self._fm_try("du", [((path,), {}), ((), {})])
        if not ok:
            return None
        if isinstance(res, dict):
            for k in ("total_bytes", "total", "size", "bytes", "total_size"):
                if k in res:
                    try:
                        return float(res[k])
                    except (TypeError, ValueError):
                        return None
            return None
        try:
            return float(res)
        except (TypeError, ValueError):
            return None

    # ---------------- armazenamento e dispositivos ----------------

    def _refresh_system(self):
        """Le armazenamento e dispositivos removiveis (dados reais)."""
        self._ensure_fm()
        if self.fm is None:
            self._storage = []
            self._devices = []
            return
        ok, res = self._fm_try("storage", [((), {}), (("/",), {})])
        self._storage = self._norm_storage(res) if ok else []
        ok, res = self._fm_try("removable_devices", [((), {})])
        self._devices = self._norm_devices(res) if ok else []
        self.dirty = True

    def _norm_storage(self, raw):
        out = []
        if raw is None:
            return out
        if isinstance(raw, dict):
            if any(k in raw for k in ("mount", "device", "mountpoint",
                                      "name", "total", "used")):
                raw = [raw]
            elif raw and all(isinstance(v, dict) for v in raw.values()):
                for k, v in raw.items():
                    v = dict(v)
                    v.setdefault("mount", k)
                    out.append(self._norm_storage_one(v))
                return out
            else:
                raw = [raw]
        if not isinstance(raw, (list, tuple)):
            return out
        for it in raw:
            if isinstance(it, dict):
                out.append(self._norm_storage_one(it))
            elif isinstance(it, str):
                out.append({"mount": it, "total": None, "used": None,
                            "free": None, "pct": None})
        return out

    def _norm_storage_one(self, it):
        mount = (it.get("mount") or it.get("mountpoint") or
                 it.get("device") or it.get("name") or "?")
        total = it.get("total", it.get("size", it.get("size_bytes")))
        used = it.get("used", it.get("used_bytes"))
        free = it.get("free", it.get("available", it.get("free_bytes")))
        pct = it.get("used_pct", it.get("percent", it.get("pct")))
        try:
            if pct is None and total and used is not None:
                pct = float(used) * 100.0 / float(total)
        except (TypeError, ValueError, ZeroDivisionError):
            pct = None
        return {"mount": str(mount), "total": total, "used": used,
                "free": free, "pct": pct}

    def _norm_devices(self, raw):
        out = []
        if raw is None:
            return out
        if isinstance(raw, dict):
            raw = list(raw.values())
        if not isinstance(raw, (list, tuple)):
            return out
        for it in raw:
            if isinstance(it, dict):
                path = (it.get("path") or it.get("mount") or
                        it.get("mountpoint") or it.get("device") or "")
                label = (it.get("label") or it.get("name") or
                         it.get("title") or os.path.basename(str(path)) or
                         "?")
                out.append({"path": str(path), "label": str(label)})
            elif isinstance(it, str):
                out.append({"path": it,
                            "label": os.path.basename(it.rstrip("/")) or it})
        return out

    def _read_mounts(self):
        """Pontos de montagem reais (camada de arquivos)."""
        if self.fm is None:
            return []
        ok, res = self._fm_try("mounts", [((), {})])
        if not ok or not res:
            return []
        out = []
        if isinstance(res, dict):
            res = list(res.values())
        if not isinstance(res, (list, tuple)):
            return []
        for it in res:
            if isinstance(it, dict):
                mp = (it.get("mount") or it.get("mountpoint") or
                      it.get("target") or it.get("path") or "?")
                out.append({"mount": str(mp)})
            elif isinstance(it, str):
                out.append({"mount": it})
        return out

    def _free_space(self):
        """Espaco livre do volume que contem o cwd."""
        for s in self._storage:
            m = s.get("mount") or ""
            if m and m != "?" and (self.cwd == m or
                                   self.cwd.startswith(m.rstrip("/") + "/")):
                return s.get("free")
        if self._storage:
            return self._storage[0].get("free")
        return None

    # ---------------- historico ----------------

    def _push_history(self, path):
        if self.history and self.history[self.hist_idx] == path and \
                self.cwd == path:
            return          # ja estamos neste caminho: nao duplica
        self.history = self.history[:self.hist_idx + 1]
        self.history.append(path)
        self.hist_idx = len(self.history) - 1

    def _go_back(self):
        if self.hist_idx > 0:
            self.hist_idx -= 1
            self._load_dir(self.history[self.hist_idx], history=False)
            return
        parent = os.path.dirname(self.cwd.rstrip("/")) or "/"
        if parent != self.cwd:
            self._load_dir(parent)

    # ----------------------------------------------------------------
    # operacoes do usuario
    # ----------------------------------------------------------------

    def _selected_entry(self):
        if 0 <= self.selected < len(self.entries):
            return self.entries[self.selected]
        return None

    def _navigate(self, path):
        if not path:
            return
        if not os.path.isdir(path):
            self._fail("nao e um diretorio: %s" % path)
            return
        self.overlay = None
        self.action_bar = None
        self._load_dir(path)

    def _go_shortcut(self, index):
        """Atalho da barra lateral -> caminho real."""
        if index < 0 or index >= len(SHORTCUTS):
            return
        label, path = SHORTCUTS[index]
        if path is None:
            path = os.path.expanduser("~") or "/"
        elif label == "Armazenamento":
            for cand in ("/storage", "/mnt", "/media"):
                if os.path.isdir(cand):
                    path = cand
                    break
        if not os.path.isdir(path):
            self._fail("caminho inexistente: %s" % path)
            return
        self._navigate(path)

    def _open_entry(self, idx):
        if not (0 <= idx < len(self.entries)):
            return
        e = self.entries[idx]
        if e["is_dir"]:
            self._navigate(e["path"])
            return
        if is_image(e["name"]):
            self._open_image(e["path"])
            return
        cmds = self._read_open_with(e["path"])
        if not cmds:
            self._notify("nenhum programa disponivel para %s" % e["name"],
                         "warn")
            return
        self.overlay = {"kind": "abrir_com", "path": e["path"],
                        "commands": cmds, "name": e["name"]}
        self.dirty = True

    def _read_open_with(self, path):
        ok, res = self._fm_try("open_with", [((path,), {}), ((), {})])
        if not ok or not res:
            return []
        out = []
        if isinstance(res, dict):
            res = res.get("commands") or res.get("apps") or []
        if not isinstance(res, (list, tuple)):
            return []
        for it in res:
            if isinstance(it, str):
                out.append({"label": it.split()[0] if it.split() else it,
                            "cmd": it})
            elif isinstance(it, dict):
                cmd = (it.get("cmd") or it.get("command") or
                       it.get("exec") or it.get("path") or "")
                label = (it.get("name") or it.get("label") or
                         (str(cmd).split()[0] if str(cmd).split() else "?"))
                out.append({"label": str(label), "cmd": str(cmd)})
        return out

    def _run_command(self, cmd):
        sh = self.shell
        if sh is not None and hasattr(sh, "launch"):
            try:
                sh.launch(cmd)
                self._notify("executando: %s" % cmd)
                return
            except Exception as e:
                self._fail("falha ao executar %s: %s" % (cmd, e))
                return
        self._notify("execucao disponivel apenas dentro do shell do NURA",
                     "warn")

    def _open_image(self, path):
        v = ImageViewerApp(path=path, shell=self.shell, parent=self)
        self.viewer = v
        self.viewer_is_window = False
        sh = self.shell
        if sh is not None and hasattr(sh, "open_app"):
            try:
                sh.open_app(v)
                self.viewer_is_window = True
            except Exception:
                self.viewer_is_window = False
        self._notify("abrindo %s" % os.path.basename(path))
        self.dirty = True

    def on_viewer_closed(self, viewer):
        if self.viewer is viewer:
            self.viewer = None
            self.viewer_is_window = False
            self.dirty = True

    # ---------------- copiar / colar / mover ----------------

    def _copy(self, path):
        if not path:
            self._notify("nenhum item selecionado", "warn")
            return
        self.clipboard = {"acao": "copiar", "path": path}
        self._notify("copiado: %s" % os.path.basename(path))

    def _move(self, path):
        if not path:
            self._notify("nenhum item selecionado", "warn")
            return
        self.clipboard = {"acao": "mover", "path": path}
        self._notify("movido para a area de transferencia: %s" %
                     os.path.basename(path))

    def _paste(self):
        cb = self.clipboard or {}
        src = cb.get("path")
        if not src:
            self._notify("area de transferencia vazia", "warn")
            return
        dst = join_path(self.cwd, os.path.basename(src.rstrip("/")))
        if os.path.abspath(dst) == os.path.abspath(src):
            self._fail("origem e destino sao o mesmo caminho")
            return
        acao = cb.get("acao", "copiar")
        name = "copy" if acao == "copiar" else "move"
        ok, res = self._fm_try(name, [((src, dst), {}),
                                      ((src,), {"dst": dst}),
                                      ((src, dst), {"overwrite": True})])
        if not ok:
            self._fail(res)
            return
        self._notify("%s: %s" % ("copiado" if acao == "copiar" else "movido",
                                  os.path.basename(src)))
        self._load_dir(self.cwd, history=False)

    # ---------------- criar / renomear / excluir ----------------

    def _mkdir(self, name):
        path = join_path(self.cwd, name)
        ok, res = self._fm_try("mkdir", [((path,), {}),
                                         ((name,), {"parent": self.cwd})])
        if not ok:
            self._fail(res)
            return
        self._notify("pasta criada: %s" % name)
        self._load_dir(self.cwd, history=False)

    def _create_file(self, name):
        """Cria um arquivo vazio (usa a camada de arquivos se houver)."""
        path = join_path(self.cwd, name)
        for meth in ("touch", "create", "create_file", "newfile", "new_file"):
            if self.fm is not None and hasattr(self.fm, meth):
                ok, res = self._fm_try(meth, [((path,), {}),
                                              ((name,), {"parent": self.cwd})])
                if ok:
                    self._notify("arquivo criado: %s" % name)
                    self._load_dir(self.cwd, history=False)
                    return
        # reserva: a camada de arquivos nao tem "criar arquivo"; usa a
        # biblioteca padrao (sem shell, sem privilegio).
        try:
            with open(path, "ab"):
                pass
        except Exception as e:
            self._fail("nao foi possivel criar %s: %s" % (name, e))
            return
        self._notify("arquivo criado: %s" % name)
        self._load_dir(self.cwd, history=False)

    def _rename_style(self, fn):
        """Detecta a convencao de rename(): nome novo ou caminho completo."""
        try:
            import inspect
            params = list(inspect.signature(fn).parameters)
        except Exception:
            return "name"
        if len(params) >= 2:
            segundo = params[1].lower()
            if segundo in ("dst", "dest", "destino", "target", "new_path",
                           "novo_caminho", "to"):
                return "path"
        return "name"

    def _rename(self, path, new_name):
        if not path:
            self._notify("nenhum item selecionado", "warn")
            return
        new_name = (new_name or "").strip()
        if not new_name:
            self._fail("nome invalido")
            return
        if "/" in new_name:
            self._fail("nome invalido: %s" % new_name)
            return
        target = join_path(os.path.dirname(path.rstrip("/")), new_name)
        if os.path.abspath(target) == os.path.abspath(path):
            self._notify("nome inalterado")
            return
        fn = getattr(self.fm, "rename", None)
        if fn is None:
            self._fail("metodo ausente na camada de arquivos: rename")
            return
        if self._rename_style(fn) == "path":
            variantes = [((path, target), {}), ((path, new_name), {})]
        else:
            variantes = [((path, new_name), {}), ((path, target), {})]
        ok, res = self._fm_try("rename", variantes)
        if not ok:
            self._fail(res)
            return
        self._notify("renomeado: %s" % new_name)
        self._load_dir(self.cwd, history=False)

    def _ask_delete(self, path):
        """Exclusao: confirmacao ANTES de chamar a camada de arquivos."""
        if not path:
            self._notify("nenhum item selecionado", "warn")
            return
        name = os.path.basename(path.rstrip("/")) or path
        self.action_bar = None
        sh = self.shell
        if sh is not None and hasattr(sh, "confirm"):
            def _do_ok():
                self._delete(path)
            try:
                sh.confirm("Excluir", "Excluir '%s'?" % name, _do_ok)
                self.dirty = True
                return
            except Exception:
                pass
        # sem shell: dialogo proprio de confirmacao
        self.dialog = {"kind": "excluir", "path": path, "name": name}
        self.dirty = True

    def _delete(self, path):
        """Chamada final: sempre com confirm=True na camada de arquivos."""
        self._ensure_fm()
        if self.fm is None:
            self._fail(self.fm_error or "modulo de arquivos indisponivel")
            return
        ok, res = self._fm_try("delete",
                                [((path,), {"recursive": True, "confirm": True}),
                                 ((path, True, True), {}),
                                 ((path,), {"confirm": True})])
        if not ok:
            self._fail(res)
            return
        self._notify("excluido: %s" % os.path.basename(path.rstrip("/")))
        self._load_dir(self.cwd, history=False)

    # ---------------- info ----------------

    def _show_info(self, path):
        if not path:
            self._notify("nenhum item selecionado", "warn")
            return
        self._ensure_fm()
        info = None
        if self.fm is not None:
            ok, res = self._fm_try("stat_info", [((path,), {}), ((), {})])
            if ok and isinstance(res, dict):
                info = res
        if info is None:
            info = self._stat(path) or {}
        if not info:
            self._fail("nao foi possivel ler as informacoes de %s" % path)
            return
        self.dialog = {"kind": "info", "path": path, "info": info,
                       "name": os.path.basename(path.rstrip("/"))}
        self.dirty = True

    # ---------------- busca ----------------

    def _param_name(self, fn, index):
        """Nome do n-esimo parametro de uma funcao ("" se nao der)."""
        try:
            import inspect
            params = list(inspect.signature(fn).parameters)
        except Exception:
            return ""
        if len(params) > index:
            return params[index].lower()
        return ""

    def _search(self, query):
        self._ensure_fm()
        if self.fm is None:
            self._fail(self.fm_error or "modulo de arquivos indisponivel")
            return []
        fn = getattr(self.fm, "search", None)
        if fn is None:
            self._fail("metodo ausente na camada de arquivos: search")
            return []
        # a ordem dos argumentos varia: search(root, query) ou
        # search(query, root). Decide pelo nome do primeiro parametro.
        primeiro = self._param_name(fn, 0)
        if primeiro in ("query", "pattern", "termo", "needle", "text",
                        "name", "busca"):
            variantes = [((query, self.cwd), {}), ((self.cwd, query), {})]
        else:
            variantes = [((self.cwd, query), {}), ((query, self.cwd), {})]
        ok, res = self._fm_try("search", variantes)
        if not ok:
            self._fail(res)
            return []
        return self._norm_entries(res, self.cwd)

    # ----------------------------------------------------------------
    # acoes dos botoes
    # ----------------------------------------------------------------

    def _do_button(self, bid):
        if bid == "voltar":
            self._go_back()
        elif bid == "caminho":
            self.overlay = {"kind": "ir_para", "text": self.cwd,
                            "title": "Ir para o caminho"}
            self.dirty = True
        elif bid == "home":
            self._navigate(os.path.expanduser("~") or "/")
        elif bid == "disp":
            self._refresh_system()
            self.overlay = {"kind": "dispositivos", "title": "Dispositivos",
                            "devices": list(self._devices),
                            "mounts": self._read_mounts()}
            self.dirty = True
        elif bid == "atualizar":
            self._refresh_system()
            self._load_dir(self.cwd, history=False)
            self._notify("atualizado")
        elif bid == "buscar":
            self.overlay = {"kind": "buscar", "text": "", "results": [],
                            "title": "Pesquisar"}
            self.dirty = True
        elif bid == "ocultos":
            self.show_hidden = not self.show_hidden
            self._apply_filter()
            self._notify("arquivos ocultos: %s" %
                         ("sim" if self.show_hidden else "nao"))
        elif bid == "vista_lista":
            self.view_mode = "lista"
            self.dirty = True
        elif bid == "vista_icones":
            self.view_mode = "icones"
            self.dirty = True
        elif bid == "novo":
            self.dialog = {"kind": "novo", "field": "", "mode": "arquivo"}
            self.dirty = True
        elif bid == "copiar":
            e = self._selected_entry()
            self._copy(e["path"] if e else None)
        elif bid == "colar":
            self._paste()
        elif bid == "renomear":
            e = self._selected_entry()
            if not e:
                self._notify("nenhum item selecionado", "warn")
            else:
                self.dialog = {"kind": "renomear", "path": e["path"],
                               "field": e["name"], "name": e["name"]}
                self.dirty = True
        elif bid == "excluir":
            e = self._selected_entry()
            self._ask_delete(e["path"] if e else None)
        elif bid == "info":
            e = self._selected_entry()
            self._show_info(e["path"] if e else None)
        elif bid == "abrir_com":
            e = self._selected_entry()
            if not e:
                self._notify("nenhum item selecionado", "warn")
                return
            cmds = self._read_open_with(e["path"])
            if not cmds:
                self._notify("nenhum programa disponivel para %s" % e["name"],
                             "warn")
                return
            self.overlay = {"kind": "abrir_com", "path": e["path"],
                            "commands": cmds, "name": e["name"]}
            self.dirty = True
        elif bid.startswith("act:"):
            self._run_action(bid[4:], (self.action_bar or {}).get("path"))
        elif bid.startswith("sc:"):
            try:
                self._go_shortcut(int(bid[3:]))
            except (ValueError, IndexError):
                pass
        elif bid.startswith("kb:"):
            self._kb_press(bid[3:])
        elif bid.startswith("dlg:"):
            if self.dialog is not None:
                self._dlg_action(bid[4:])
            else:
                self._ov_action(bid[4:])
        elif bid.startswith("ov:"):
            self._ov_action(bid[3:])

    def _run_action(self, act, path):
        if act == "fechar":
            self.action_bar = None
            self.dirty = True
            return
        if not path:
            self.action_bar = None
            self._notify("nenhum item selecionado", "warn")
            return
        if act == "abrir":
            self.action_bar = None
            for i, e in enumerate(self.entries):
                if e["path"] == path:
                    self._open_entry(i)
                    return
            self._notify("item nao esta mais na lista", "warn")
        elif act == "copiar":
            self.action_bar = None
            self._copy(path)
        elif act == "mover":
            self.action_bar = None
            self._move(path)
        elif act == "renomear":
            self.action_bar = None
            self.dialog = {"kind": "renomear", "path": path,
                           "field": os.path.basename(path.rstrip("/"))}
            self.dirty = True
        elif act == "excluir":
            self._ask_delete(path)
        elif act == "info":
            self.action_bar = None
            self._show_info(path)
        elif act == "abrir_com":
            self.action_bar = None
            cmds = self._read_open_with(path)
            if not cmds:
                self._notify("nenhum programa disponivel para %s" %
                             os.path.basename(path.rstrip("/")), "warn")
                return
            self.overlay = {"kind": "abrir_com", "path": path,
                            "commands": cmds,
                            "name": os.path.basename(path.rstrip("/"))}
            self.dirty = True

    # ---------------- acoes do modal ----------------

    def _kb_press(self, key):
        m = self.dialog or self.overlay
        if not m:
            return
        field = m.get("field")
        if field is None:
            field = m.get("text")
        if field is None:
            return
        if key == "space":
            field += " "
        elif key == "back":
            field = field[:-1]
        else:
            field += key
        if self.dialog is not None and "field" in self.dialog:
            self.dialog["field"] = field
        else:
            m["text"] = field
        self.dirty = True

    def _dlg_action(self, act):
        d = self.dialog
        if not d:
            return
        kind = d.get("kind")
        if act == "cancel":
            self.dialog = None
            self.dirty = True
            return
        if act == "modo_arquivo":
            d["mode"] = "arquivo"
            d["kind"] = "novo"
            self.dirty = True
            return
        if act == "modo_pasta":
            d["mode"] = "pasta"
            d["kind"] = "novo_pasta"
            self.dirty = True
            return
        if kind == "excluir":
            if act == "delete":
                path = d.get("path")
                self.dialog = None
                self._delete(path)
            else:
                self.dialog = None
            self.dirty = True
            return
        if kind == "info":
            self.dialog = None
            self.dirty = True
            return
        if kind in ("novo", "novo_pasta"):
            name = (d.get("field") or "").strip()
            if not name:
                self._fail("informe um nome")
                return
            self.dialog = None
            if d.get("mode") == "pasta":
                self._mkdir(name)
            else:
                self._create_file(name)
            return
        if kind == "renomear":
            name = (d.get("field") or "").strip()
            path = d.get("path")
            self.dialog = None
            if not name:
                self._fail("informe um nome")
                return
            self._rename(path, name)
            return
        self.dialog = None
        self.dirty = True

    def _ov_action(self, act):
        o = self.overlay
        if not o:
            return
        kind = o.get("kind")
        if act == "cancel" or act == "close":
            self.overlay = None
            self.dirty = True
            return
        if act == "ok":
            if kind == "buscar":
                return self._ov_action("buscar")
            if kind == "ir_para":
                return self._ov_action("ir_para")
            self.overlay = None
            self.dirty = True
            return
        if act == "buscar":
            query = (o.get("text") or "").strip()
            if not query:
                self._fail("informe um termo de busca")
                return
            o["results"] = self._search(query)
            self.dirty = True
            return
        if act == "ir_para":
            path = (o.get("text") or "").strip()
            self.overlay = None
            if path:
                self._navigate(path)
            return
        if act.startswith("cmd:"):
            idx = int(act[4:])
            cmds = o.get("commands") or []
            if 0 <= idx < len(cmds):
                cmd = cmds[idx]["cmd"]
                self.overlay = None
                self._run_command(cmd)
            return
        if act.startswith("res:"):
            idx = int(act[4:])
            res = o.get("results") or []
            if 0 <= idx < len(res):
                path = res[idx]["path"]
                self.overlay = None
                self._navigate(os.path.dirname(path) or self.cwd)
                self.selected = -1
                for i, e in enumerate(self.entries):
                    if e["path"] == path:
                        self.selected = i
                        break
                self.dirty = True
            return
        if act.startswith("dev:"):
            idx = int(act[4:])
            devs = o.get("devices") or []
            if 0 <= idx < len(devs):
                path = devs[idx]["path"]
                self.overlay = None
                self._navigate(path)
            return
        if act.startswith("mnt:"):
            idx = int(act[4:])
            mts = o.get("mounts") or []
            if 0 <= idx < len(mts):
                path = mts[idx]["mount"]
                self.overlay = None
                self._navigate(path)
            return

    # ----------------------------------------------------------------
    # toque
    # ----------------------------------------------------------------

    def on_touch(self, ev):
        self._layout()
        et = getattr(ev, "type", "")
        if et == "down":
            hit = self._hit_button(ev.x, ev.y)
            if hit is not None:
                self._pressed = hit.get("id")
                for b in self._btns + self._modal_btns:
                    b["pressed"] = (b["id"] == self._pressed)
                self.dirty = True
                return True
            return False
        if et == "up":
            if self._pressed is not None:
                self._pressed = None
                for b in self._btns + self._modal_btns:
                    b["pressed"] = False
                self.dirty = True
            return False
        if et == "tap":
            return self._on_tap(ev)
        if et == "drag":
            return self._on_drag(ev)
        if et == "scroll":
            return self._on_scroll(ev)
        if et == "longpress":
            return self._on_longpress(ev)
        if et == "pinch":
            return False
        return False

    def _on_tap(self, ev):
        x, y = ev.x, ev.y
        # modal tem prioridade
        if self.dialog is not None or self.overlay is not None:
            return self._tap_modal(x, y)
        # barra de acoes
        for b in self._btns:
            if b.get("zone") == "action" and in_rect(b["rect"], x, y):
                self._do_button(b["id"])
                return True
        if self.action_bar is not None:
            self.action_bar = None
            self.dirty = True
            return True
        # botoes normais
        for b in self._btns:
            if in_rect(b["rect"], x, y):
                self._do_button(b["id"])
                return True
        # itens da lista
        idx = self._entry_at(x, y)
        if idx is not None:
            if idx == self.selected and self._last_tap == idx:
                self._last_tap = -1
                self._open_entry(idx)
            else:
                self.selected = idx
                self._last_tap = idx
                self.dirty = True
            return True
        return False

    def _tap_modal(self, x, y):
        for b in self._modal_btns:
            if in_rect(b["rect"], x, y):
                self._do_button(b["id"])
                return True
        return True

    def _on_drag(self, ev):
        dy = getattr(ev, "dy", 0.0) or 0.0
        dx = getattr(ev, "dx", 0.0) or 0.0
        if abs(dy) < abs(dx):
            return False
        main = self._rects.get("main")
        if not main:
            return False
        if not in_rect(main, ev.x, ev.y):
            return False
        self._scroll_by(-dy)
        return True

    def _on_scroll(self, ev):
        amount = getattr(ev, "amount", 0.0) or 0.0
        self._scroll_by(amount)
        return True

    def _on_longpress(self, ev):
        if self.dialog is not None or self.overlay is not None:
            return False
        idx = self._entry_at(ev.x, ev.y)
        if idx is None:
            return False
        e = self.entries[idx]
        self.selected = idx
        self.action_bar = {"path": e["path"], "name": e["name"]}
        self._notify("%s - escolha uma acao" % e["name"])
        self.dirty = True
        return True

    def on_key(self, ev):
        """Teclado fisico ou virtual: edita o campo de texto do modal."""
        m = self.dialog or self.overlay
        if not m:
            return False
        texto = getattr(ev, "text", "") or ""
        key = getattr(ev, "key", None)
        if not key:
            key = texto
        if not key:
            return False
        if key in ("BackSpace", "backspace", "\b"):
            self._kb_press("back")
            return True
        if key in ("Return", "Enter", "\r", "\n"):
            if self.dialog is not None:
                self._dlg_action("ok")
            elif self.overlay is not None:
                o = self.overlay
                if o.get("kind") == "buscar":
                    self._ov_action("buscar")
                elif o.get("kind") == "ir_para":
                    self._ov_action("ir_para")
            return True
        if texto and len(texto) == 1 and texto.isprintable():
            self._kb_press(texto)
            return True
        if isinstance(key, str) and len(key) == 1 and key.isprintable():
            self._kb_press(key)
            return True
        return False

    # ----------------------------------------------------------------
    # rolagem
    # ----------------------------------------------------------------

    def _content_height(self):
        if not self.entries:
            return 0
        if self.view_mode == "icones":
            main = self._rects.get("main")
            w = main[2] if main else 800
            cols = max(1, int((w - 2 * PAD) // 150))
            rows = (len(self.entries) + cols - 1) // cols
            return rows * GRID_CELL_H
        return len(self.entries) * LIST_ROW_H

    def _scroll_by(self, delta):
        main = self._rects.get("main")
        if not main:
            return
        track = main[3] - LIST_HEAD_H
        if track <= 0:
            return
        total = self._content_height()
        max_scroll = max(0, total - track)
        if max_scroll <= 0:
            return
        cur = self.scroll * max_scroll
        cur = max(0.0, min(float(max_scroll), cur + float(delta)))
        self.scroll = cur / max_scroll
        self.dirty = True

    # ----------------------------------------------------------------
    # geometria
    # ----------------------------------------------------------------

    def _content_rect(self):
        if self.window is not None:
            return self.window.content_rect()
        return (0, 0, self.width, max(240, self.height - 46))

    def _layout(self):
        cx, cy, cw, ch = self._content_rect()
        th = self._theme()
        L = {"content": (cx, cy, cw, ch)}
        head_h = HEAD1_H + HEAD2_H
        L["head1"] = (cx, cy, cw, HEAD1_H)
        L["head2"] = (cx, cy + HEAD1_H, cw, HEAD2_H)
        action_h = ACTION_H if self.action_bar else 0
        foot_h = self._footer_height(cw, th)
        L["footer"] = (cx, cy + ch - foot_h, cw, foot_h)
        L["action"] = (cx, cy + ch - foot_h - action_h, cw, action_h)
        sb_w = SIDEBAR_W if cw >= 780 else 0
        main_h = max(120, ch - head_h - foot_h - action_h)
        L["sidebar"] = (cx, cy + head_h, sb_w, main_h)
        L["main"] = (cx + sb_w, cy + head_h, cw - sb_w, main_h)
        self._rects = L
        self._build_buttons(L, th)
        self._layout_modal()
        return L

    def _footer_height(self, cw, th):
        total = 0
        for _bid, label in FOOTER_ACTIONS:
            total += max(MIN_TOUCH, int(measure(label, th.font_small)) + 26)
        total += (len(FOOTER_ACTIONS) - 1) * 8
        status_min = 200
        if total + status_min + PAD * 2 <= cw:
            return FOOTER_H
        return FOOTER_H + FOOTER_ROW_H

    def _build_buttons(self, L, th):
        btns = []
        fs = th.font_small

        def add(bid, rect, label=None, icon=None, kind="normal", zone="main",
                active=False):
            btns.append({"id": bid, "rect": rect, "label": label or "",
                         "icon": icon, "kind": kind, "zone": zone,
                         "active": active,
                         "pressed": (bid == self._pressed)})

        # ---- cabecalho linha 1 ----
        hx, hy, hw, hh = L["head1"]
        pad = 8
        bh = HEAD1_H - 16
        by = hy + 8
        x = hx + pad
        add("voltar", (x, by, 104, bh), "Voltar", "back", zone="header")
        x += 104 + 8
        w_home = max(MIN_TOUCH, int(measure("Home", fs)) + 30)
        w_ref = max(MIN_TOUCH, int(measure("Atual.", fs)) + 30)
        w_search = max(MIN_TOUCH, int(measure("Buscar", fs)) + 30)
        right = w_home + w_ref + w_search + 16
        path_w = max(120, (hx + hw - pad) - right - 8 - x)
        add("caminho", (x, by, path_w, bh), "", None, kind="path",
            zone="header")
        x += path_w + 8
        add("home", (x, by, w_home, bh), "Home", "home", zone="header")
        x += w_home + 8
        add("atualizar", (x, by, w_ref, bh), "Atual.", "refresh",
            zone="header")
        x += w_ref + 8
        add("buscar", (x, by, w_search, bh), "Buscar", "search", zone="header")

        # ---- cabecalho linha 2 ----
        hx, hy, hw, hh = L["head2"]
        by = hy + 6
        bh = HEAD2_H - 12
        x = hx + pad
        w_disp = max(MIN_TOUCH, int(measure("Dispositivos", fs)) + 52)
        add("disp", (x, by, w_disp, bh), "Dispositivos", "disk", zone="header")
        x += w_disp + 8
        w_oc = max(MIN_TOUCH, int(measure("Ocultos", fs)) + 30)
        add("ocultos", (x, by, w_oc, bh), "Ocultos", "eye",
            zone="header", active=self.show_hidden)
        x += w_oc + 8
        w_ls = max(MIN_TOUCH, int(measure("Lista", fs)) + 26)
        add("vista_lista", (x, by, w_ls, bh), "Lista", None, zone="header",
            active=(self.view_mode == "lista"))
        x += w_ls + 8
        w_ic = max(MIN_TOUCH, int(measure("Icones", fs)) + 26)
        add("vista_icones", (x, by, w_ic, bh), "Icones", None, zone="header",
            active=(self.view_mode == "icones"))

        # ---- barra lateral (atalhos) ----
        sx, sy, sw, sh = L["sidebar"]
        if sw > 0:
            ly = sy + 10
            for i, (label, path) in enumerate(SHORTCUTS):
                add("sc:%d" % i, (sx + 8, ly, sw - 16, MIN_TOUCH), label,
                    "home" if i == 0 else None, kind="shortcut",
                    zone="sidebar")
                ly += MIN_TOUCH + 4

        # ---- rodape ----
        fx, fy, fw, fh = L["footer"]
        widths = []
        for bid, label in FOOTER_ACTIONS:
            widths.append(max(MIN_TOUCH, int(measure(label, fs)) + 26))
        total = sum(widths) + (len(widths) - 1) * 8
        status_w = fw - PAD * 2 - total - 12
        two_rows = status_w < 200
        if two_rows:
            per_row = 4
            row_y = fy + 12
            bx = fx + PAD
            for i, (bid, label) in enumerate(FOOTER_ACTIONS):
                if i == per_row:
                    bx = fx + PAD
                    row_y += FOOTER_ROW_H
                add(bid, (bx, row_y, widths[i], MIN_TOUCH), label,
                    zone="footer")
                bx += widths[i] + 8
        else:
            bx = fx + fw - PAD - total
            for i, (bid, label) in enumerate(FOOTER_ACTIONS):
                add(bid, (bx, fy + (fh - MIN_TOUCH) // 2, widths[i],
                          MIN_TOUCH), label, zone="footer")
                bx += widths[i] + 8

        # ---- barra de acoes ----
        ax, ay, aw, ah = L["action"]
        if aw > 0 and self.action_bar:
            name = str(self.action_bar.get("name", ""))
            name_w = min(int(measure(name, fs)) + 12, int(aw * 0.30))
            bx = ax + PAD
            limit = ax + aw - PAD - name_w
            for bid, label in ACTION_ACTIONS:
                w = max(MIN_TOUCH, int(measure(label, fs)) + 26)
                if bx + w > limit:
                    break
                add("act:%s" % bid, (bx, ay + (ah - MIN_TOUCH) // 2, w,
                                     MIN_TOUCH), label, zone="action")
                bx += w + 8

        self._btns = btns

    def _layout_modal(self):
        """Geometria do modal (dialogo ou overlay)."""
        m = self.dialog or self.overlay
        self._modal_btns = []
        if not m:
            self._modal = None
            return
        kind = m.get("kind")
        cx, cy, cw, ch = self._content_rect()
        needs_kb = kind in ("novo", "novo_pasta", "renomear", "buscar",
                            "ir_para")
        if kind == "excluir":
            dw, dh = 540, 300
        elif kind == "info":
            dw, dh = 620, 470
        elif needs_kb:
            dw, dh = 680, 540
        else:
            dw, dh = 600, 450
        dw = min(dw, max(240, cw - 30))
        dh = min(dh, max(200, ch - 30))
        x = cx + (cw - dw) / 2.0
        y = cy + (ch - dh) / 2.0
        M = {"rect": (x, y, dw, dh), "kind": kind}
        M["title"] = (x, y, dw, 48)
        kb_h = (len(KB_ROWS) * KB_KEY_H + (len(KB_ROWS) - 1) * KB_GAP
                if needs_kb else 0)
        act_h = 60
        M["actions"] = (x, y + dh - kb_h - act_h, dw, act_h)
        M["kb"] = (x, y + dh - kb_h, dw, kb_h) if kb_h else None
        body_y = y + 48 + 12
        body_h = max(40, (y + dh - kb_h - act_h - 12) - body_y)
        M["body"] = (x + 18, body_y, dw - 36, body_h)
        self._modal = M

        th = self._theme()
        fs = th.font_small
        btns = []

        def add(bid, rect, label, kind_btn="normal"):
            btns.append({"id": bid, "rect": rect, "label": label,
                         "icon": None, "kind": kind_btn, "zone": "modal",
                         "active": False, "pressed": False})

        # teclado
        if M["kb"]:
            kx, ky, kw, kh = M["kb"]
            gap = KB_GAP
            inner = kw - 24
            colw = (inner - (KB_COLS - 1) * gap) / float(KB_COLS)
            ry = ky
            for ri, row in enumerate(KB_ROWS):
                if ri < len(KB_ROWS) - 1:
                    for ci, key in enumerate(row):
                        kxx = kx + 12 + ci * (colw + gap)
                        add("kb:%s" % key, (kxx, ry, colw, KB_KEY_H), key,
                            "key")
                else:
                    sw = 6 * colw + 5 * gap
                    add("kb:space", (kx + 12, ry, sw, KB_KEY_H), " ",
                        "key")
                    bxx = kx + 12 + 6 * (colw + gap)
                    add("kb:back", (bxx, ry, 2 * colw + gap, KB_KEY_H), "<-",
                        "key")
                ry += KB_KEY_H + gap

        # acoes do rodape do modal
        ax, ay, aw, ah = M["actions"]
        by = ay + (ah - MIN_TOUCH) // 2

        def right_buttons(items):
            bx = ax + aw - 18
            for bid, label in reversed(items):
                w = max(MIN_TOUCH, int(measure(label, fs)) + 26)
                bx -= w
                add(bid, (bx, by, w, MIN_TOUCH), label)
                bx -= 8

        if kind in ("novo", "novo_pasta"):
            bx = ax + 18
            mode = (self.dialog or {}).get("mode", "arquivo")
            for bid, label, val in (("dlg:modo_arquivo", "Arquivo", "arquivo"),
                                    ("dlg:modo_pasta", "Pasta", "pasta")):
                w = max(MIN_TOUCH, int(measure(label, fs)) + 26)
                b = {"id": bid, "rect": (bx, by, w, MIN_TOUCH), "label": label,
                     "icon": None, "kind": "toggle", "zone": "modal",
                     "active": (mode == val), "pressed": False}
                btns.append(b)
                bx += w + 8
            right_buttons((("dlg:cancel", "Cancelar"),
                           ("dlg:ok", "Criar")))
        elif kind == "renomear":
            right_buttons((("dlg:cancel", "Cancelar"),
                           ("dlg:ok", "Renomear")))
        elif kind == "excluir":
            right_buttons((("dlg:cancel", "Cancelar"),
                           ("dlg:delete", "Excluir")))
        elif kind == "info":
            right_buttons((("dlg:ok", "Fechar"),))
        elif kind == "buscar":
            right_buttons((("dlg:cancel", "Cancelar"),
                           ("dlg:ok", "Buscar")))
        elif kind == "ir_para":
            right_buttons((("dlg:cancel", "Cancelar"),
                           ("dlg:ok", "Ir")))
        else:
            right_buttons((("dlg:cancel", "Fechar"),))

        # itens de lista (resultados / comandos / dispositivos)
        o = self.overlay or {}
        if kind in ("abrir_com", "buscar", "dispositivos"):
            items = []
            if kind == "abrir_com":
                items = [("cmd:%d" % i, c["label"])
                         for i, c in enumerate(o.get("commands") or [])]
            elif kind == "buscar":
                items = [("res:%d" % i, r["name"])
                         for i, r in enumerate(o.get("results") or [])]
            else:
                items = [("dev:%d" % i, d["label"])
                         for i, d in enumerate(o.get("devices") or [])]
                items += [("mnt:%d" % i, mt["mount"])
                          for i, mt in enumerate(o.get("mounts") or [])]
            bx, byy, bw, bh2 = M["body"]
            ry = byy
            for bid, label in items:
                if ry + MIN_TOUCH > byy + bh2:
                    break
                add(bid, (bx, ry, bw, MIN_TOUCH), label, "row")
                ry += MIN_TOUCH + 4

        self._modal_btns = btns

    def _hit_button(self, x, y):
        for b in (self._modal_btns + self._btns):
            if in_rect(b["rect"], x, y):
                return b
        return None

    def _entry_at(self, x, y):
        """Indice da entrada sob o ponto (ou None)."""
        main = self._rects.get("main")
        if not main:
            return None
        mx, my, mw, mh = main
        if not in_rect((mx, my + LIST_HEAD_H, mw, mh - LIST_HEAD_H), x, y):
            return None
        if not self.entries:
            return None
        if self.view_mode == "icones":
            cols = max(1, int((mw - 2 * PAD) // 150))
            cw = (mw - 2 * PAD) / float(cols)
            rel_x = x - (mx + PAD)
            rel_y = y - (my + LIST_HEAD_H)
            if rel_x < 0 or rel_y < 0:
                return None
            col = int(rel_x // cw)
            row = int(rel_y // GRID_CELL_H)
            idx = row * cols + col
            if 0 <= idx < len(self.entries):
                return idx
            return None
        track = mh - LIST_HEAD_H
        max_scroll = max(0, self._content_height() - track)
        off = self.scroll * max_scroll
        row = int((y - (my + LIST_HEAD_H) + off) // LIST_ROW_H)
        if 0 <= row < len(self.entries):
            return row
        return None

    # ----------------------------------------------------------------
    # desenho
    # ----------------------------------------------------------------

    def draw(self, p):
        th = p.theme
        L = self._layout()
        cx, cy, cw, ch = L["content"]
        p.rect(cx, cy, cw, ch, th.bg, 1.0)
        self._draw_sidebar(p)
        self._draw_main(p)
        self._draw_header(p)
        self._draw_action_bar(p)
        self._draw_footer(p)
        if self.dialog is not None or self.overlay is not None:
            self._draw_modal(p)
        if self.viewer is not None and not self.viewer_is_window:
            self._draw_viewer(p)
        self.dirty = False

    # ---------------- cabecalho ----------------

    def _draw_header(self, p):
        th = p.theme
        L = self._rects
        x, y, w, h = L["head1"]
        p.rect(x, y, w, h, th.panel_hi, 0.60)
        p.line(x, y + h - 1, x + w, y + h - 1, th.accent, 1.0, 0.25)
        x2, y2, w2, h2 = L["head2"]
        p.rect(x2, y2, w2, h2, th.panel, 0.55)
        p.line(x2, y2 + h2 - 1, x2 + w2, y2 + h2 - 1, th.accent, 1.0, 0.18)
        for b in self._btns:
            if b.get("zone") == "header":
                self._draw_button(p, b, th)
        # caminho atual dentro do botao "Caminho"
        for b in self._btns:
            if b["id"] == "caminho":
                bx, by, bw, bh = b["rect"]
                label = ellipsis_left(self.cwd, bw - 52, th.font_small)
                p.text(label, bx + 40, by + bh / 2 + th.font_small * 0.35,
                       th.font_small, th.text)

    # ---------------- botoes ----------------

    def _draw_button(self, p, b, th):
        x, y, w, h = b["rect"]
        pressed = b.get("pressed")
        kind = b.get("kind")
        if kind == "key":
            if pressed:
                p.round(x, y, w, h, 8, th.accent, 0.45)
            else:
                p.round(x, y, w, h, 8, th.panel_hi, 0.9)
                p.round(x, y, w, h, 8, th.accent, 0.35, filled=False,
                        width=1.0)
            p.text(b["label"], x + w / 2, y + h / 2 + th.font_small * 0.35,
                   th.font_small, th.text, align="center")
            return
        if kind == "row":
            if pressed:
                p.round(x, y, w, h, th.radius, th.accent, 0.34)
            else:
                p.round(x, y, w, h, th.radius, th.panel_hi, 0.70)
            p.text(b["label"], x + 12, y + h / 2 + th.font_small * 0.35,
                   th.font_small, th.text)
            return
        if kind == "shortcut":
            if pressed:
                p.round(x, y, w, h, th.radius, th.accent, 0.34)
            else:
                p.round(x, y, w, h, th.radius, th.panel_hi, 0.55)
            p.icon("home", x + 20, y + h / 2, 20, th.accent)
            p.text(b["label"], x + 38, y + h / 2 + th.font_small * 0.35,
                   th.font_small, th.text)
            return
        if kind == "toggle":
            if pressed:
                p.round(x, y, w, h, th.radius, th.accent, 0.40)
            elif b.get("active"):
                p.round(x, y, w, h, th.radius, th.accent, 0.26)
                p.round(x, y, w, h, th.radius, th.accent, 0.70, filled=False,
                        width=1.0)
            else:
                p.round(x, y, w, h, th.radius, th.panel_hi, 0.75)
                p.round(x, y, w, h, th.radius, th.accent, 0.45, filled=False,
                        width=1.0)
            p.text(b["label"], x + w / 2, y + h / 2 + th.font_small * 0.35,
                   th.font_small, th.text, align="center")
            return
        if kind == "path":
            if pressed:
                p.round(x, y, w, h, th.radius, th.accent, 0.34)
            else:
                p.round(x, y, w, h, th.radius, th.panel_hi, 0.75)
                p.round(x, y, w, h, th.radius, th.accent, 0.55, filled=False,
                        width=1.0)
            p.icon("up", x + 20, y + h / 2, 20, th.accent)
            return
        # botao normal (com ou sem icone)
        if pressed:
            p.round(x, y, w, h, th.radius, th.accent, 0.34)
        elif b.get("active"):
            p.round(x, y, w, h, th.radius, th.accent, 0.26)
            p.round(x, y, w, h, th.radius, th.accent, 0.70, filled=False,
                    width=1.0)
        else:
            p.round(x, y, w, h, th.radius, th.panel_hi, 0.75)
            p.round(x, y, w, h, th.radius, th.accent, 0.55, filled=False,
                    width=1.0)
        if b.get("icon"):
            horizontal = bool(b.get("label")) and w >= 90
            if horizontal:
                # icone a esquerda, rotulo a direita
                if b["icon"] == "eye":
                    self._draw_eye(p, x + 22, y + h / 2, int(h * 0.5),
                                   th.accent if b.get("active") else th.text)
                else:
                    p.icon(b["icon"], x + 22, y + h / 2, int(h * 0.5), th.text)
                p.text(b["label"], x + 42, y + h / 2 + th.font_small * 0.35,
                       th.font_small, th.text)
            else:
                # icone em cima, rotulo embaixo (alvo de toque unico)
                if b["icon"] == "eye":
                    self._draw_eye(p, x + w / 2, y + h / 2 - 9,
                                   int(h * 0.52),
                                   th.accent if b.get("active") else th.text)
                else:
                    p.icon(b["icon"], x + w / 2, y + h / 2 - 9, int(h * 0.42),
                           th.text)
                if b.get("label"):
                    p.text(b["label"], x + w / 2, y + h - 6, th.font_small,
                           th.dim, align="center")
        else:
            p.text(b["label"], x + w / 2, y + h / 2 + th.font_small * 0.35,
                   th.font_small, th.text, align="center")

    def _draw_eye(self, p, cx, cy, size, color):
        """Olho (usado no botao 'Ocultos'): duas palpebras + pupila."""
        s = float(size)
        r = s * 0.55
        p.arc(cx, cy + s * 0.18, r, math.pi, 2.0 * math.pi, color, 2.0)
        p.arc(cx, cy - s * 0.18, r, 0.0, math.pi, color, 2.0)
        p.circle(cx, cy, s * 0.16, color, 0.95)

    # ---------------- barra lateral ----------------

    def _draw_sidebar(self, p):
        th = p.theme
        L = self._rects
        sx, sy, sw, sh = L["sidebar"]
        if sw <= 0:
            return
        p.ctx.save()
        p.ctx.rectangle(sx, sy, sw, sh)
        p.ctx.clip()
        p.rect(sx, sy, sw, sh, th.panel, 0.72)
        p.line(sx + sw - 1, sy, sx + sw - 1, sy + sh, th.accent, 1.0, 0.25)
        for b in self._btns:
            if b.get("zone") == "sidebar":
                self._draw_button(p, b, th)
        # atalhos resolvidos (Home real, Armazenamento existente...)
        ly = sy + 10 + len(SHORTCUTS) * (MIN_TOUCH + 4) + 6
        ly = self._draw_sidebar_storage(p, sx, sy, sw, sh, ly)
        self._draw_sidebar_devices(p, sx, sy, sw, sh, ly)
        p.ctx.restore()

    def _draw_sidebar_storage(self, p, sx, sy, sw, sh, y):
        """Barras de uso real (dados de storage()). Devolve a nova altura."""
        th = p.theme
        p.text("ARMAZENAMENTO", sx + 14, y + 14, th.font_small, th.dim)
        y += 26
        if not self._storage:
            p.text("sem dados", sx + 14, y + 14, th.font_small, th.dim2)
            return y + 26
        for s in self._storage[:6]:
            if y + 46 > sy + sh:
                break
            p.text(ellipsis(s["mount"], sw - 28, th.font_small), sx + 14,
                   y + 12, th.font_small, th.text)
            pct = s.get("pct")
            if pct is None:
                p.text("uso desconhecido", sx + 14, y + 32, th.font_small,
                       th.dim2)
                y += 44
                continue
            p.progress(sx + 14, y + 22, sw - 28, 12,
                       max(0.0, min(1.0, float(pct) / 100.0)))
            p.text("%d%%  livre %s" % (int(round(float(pct))),
                                       human_size(s.get("free"))),
                   sx + 14, y + 48, th.font_small, th.dim)
            y += 60
        return y

    def _draw_sidebar_devices(self, p, sx, sy, sw, sh, y):
        th = p.theme
        if not self._devices:
            return
        y += 6
        p.text("DISPOSITIVOS REMOVEIS", sx + 14, y + 14, th.font_small, th.dim)
        y += 24
        for d in self._devices[:5]:
            if y + MIN_TOUCH > sy + sh:
                break
            p.round(sx + 8, y, sw - 16, MIN_TOUCH, th.radius, th.panel_hi,
                    0.55)
            p.icon("disk", sx + 28, y + MIN_TOUCH / 2, 20, th.accent)
            p.text(ellipsis(d["label"], sw - 60, th.font_small), sx + 46,
                   y + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.text)
            y += MIN_TOUCH + 4

    # ---------------- area principal ----------------

    def _draw_main(self, p):
        th = p.theme
        mx, my, mw, mh = self._rects["main"]
        p.rect(mx, my, mw, mh, th.bg2, 0.30)
        # banner de erro
        top = my
        if self.error:
            bh = 34
            p.rect(mx, my, mw, bh, th.err, 0.20)
            p.rect(mx, my, 4, bh, th.err, 0.95)
            p.text(ellipsis(self.error, mw - 24, th.font_small), mx + 14,
                   my + bh / 2 + th.font_small * 0.35, th.font_small, th.err)
            top = my + bh
        if self.fm is None:
            self._draw_degraded(p, mx, top, mw, mh - (top - my))
            return
        if not self.entries:
            p.text("pasta vazia", mx + mw / 2, my + mh / 2, th.font,
                   th.dim, align="center")
            return
        if self.view_mode == "icones":
            self._draw_grid(p, mx, top, mw, mh - (top - my))
        else:
            self._draw_rows(p, mx, top, mw, mh - (top - my))

    def _draw_degraded(self, p, mx, my, mw, mh):
        th = p.theme
        w = min(520, mw - 40)
        h = 160
        x = mx + (mw - w) / 2.0
        y = my + max(10, (mh - h) / 2.0)
        p.round(x, y, w, h, th.radius, th.panel, 0.95)
        p.round(x, y, w, h, th.radius, th.err, 0.6, filled=False, width=1.5)
        p.text("modulo de arquivos indisponivel", x + w / 2, y + 52,
               th.font_title, th.err, "bold", align="center")
        p.text("o componente nura_filemgr nao esta presente:",
               x + w / 2, y + 92, th.font_small, th.dim, align="center")
        p.text("o Explorer abre em modo degradado (somente leitura da tela).",
               x + w / 2, y + 118, th.font_small, th.dim, align="center")

    def _draw_rows(self, p, mx, my, mw, mh):
        th = p.theme
        fs = th.font_small
        p.ctx.save()
        p.ctx.rectangle(mx, my, mw, mh)
        p.ctx.clip()
        # cabecalho de colunas
        p.rect(mx, my, mw, LIST_HEAD_H, th.panel_hi, 0.45)
        name_x = mx + 52
        size_x = mx + mw - 16
        date_x = mx + mw - 120
        p.text("Nome", name_x, my + LIST_HEAD_H / 2 + fs * 0.35, fs, th.dim)
        p.text("Tamanho", size_x, my + LIST_HEAD_H / 2 + fs * 0.35, fs, th.dim,
               align="right")
        p.text("Data", date_x, my + LIST_HEAD_H / 2 + fs * 0.35, fs, th.dim,
               align="right")
        p.line(mx, my + LIST_HEAD_H, mx + mw, my + LIST_HEAD_H, th.accent,
               1.0, 0.22)
        track = mh - LIST_HEAD_H
        max_scroll = max(0, self._content_height() - track)
        off = self.scroll * max_scroll
        first = int(off // LIST_ROW_H)
        visible = int(track // LIST_ROW_H) + 1
        ry = my + LIST_HEAD_H - (off - first * LIST_ROW_H)
        for i in range(first, min(len(self.entries), first + visible)):
            e = self.entries[i]
            sel = (i == self.selected)
            if sel:
                p.round(mx + 4, ry + 2, mw - 8, LIST_ROW_H - 4, th.radius,
                        th.accent, 0.20)
                p.rect(mx + 4, ry + 2, 3, LIST_ROW_H - 4, th.accent, 0.95)
            self._draw_entry_icon(p, e, mx + 32, ry + LIST_ROW_H / 2, 22,
                                  sel)
            name = ellipsis(e["name"], max(60, mw - 52 - 250), fs)
            p.text(name, name_x, ry + LIST_ROW_H / 2 + fs * 0.35, fs,
                   th.text if sel else th.text)
            size = "-" if e["is_dir"] else human_size(e.get("size"))
            p.text(size, size_x, ry + LIST_ROW_H / 2 + fs * 0.35, fs, th.dim,
                   align="right")
            p.text(human_date(e.get("mtime")), date_x,
                   ry + LIST_ROW_H / 2 + fs * 0.35, fs, th.dim, align="right")
            p.line(mx + 8, ry + LIST_ROW_H - 1, mx + mw - 8,
                   ry + LIST_ROW_H - 1, th.dim2, 1.0, 0.22)
            ry += LIST_ROW_H
        if max_scroll > 0:
            p.scrollbar(mx + mw - 8, my + LIST_HEAD_H, 6,
                        max(24, track), self.scroll,
                        view=min(1.0, track / float(self._content_height())))
        p.ctx.restore()

    def _draw_grid(self, p, mx, my, mw, mh):
        th = p.theme
        fs = th.font_small
        p.ctx.save()
        p.ctx.rectangle(mx, my, mw, mh)
        p.ctx.clip()
        cols = max(1, int((mw - 2 * PAD) // 150))
        cw = (mw - 2 * PAD) / float(cols)
        track = mh
        max_scroll = max(0, self._content_height() - track)
        off = self.scroll * max_scroll
        first_row = int(off // GRID_CELL_H)
        visible = int(track // GRID_CELL_H) + 1
        for r in range(first_row, first_row + visible):
            for c in range(cols):
                i = r * cols + c
                if i >= len(self.entries):
                    break
                e = self.entries[i]
                x = mx + PAD + c * cw
                y = my + r * GRID_CELL_H - (off - first_row * GRID_CELL_H)
                if y + GRID_CELL_H < my or y > my + mh:
                    continue
                sel = (i == self.selected)
                if sel:
                    p.round(x + 2, y + 2, cw - 8, GRID_CELL_H - 8, th.radius,
                            th.accent, 0.20)
                self._draw_entry_icon(p, e, x + (cw - 8) / 2 - 6, y + 42, 36,
                                      sel)
                p.text(ellipsis(e["name"], cw - 20, fs),
                       x + (cw - 8) / 2 - 6, y + 86, fs, th.text, align="center")
                p.text("-" if e["is_dir"] else human_size(e.get("size")),
                       x + (cw - 8) / 2 - 6, y + 106, fs, th.dim,
                       align="center")
        if max_scroll > 0:
            p.scrollbar(mx + mw - 8, my, 6, max(24, track), self.scroll,
                        view=min(1.0, track / float(self._content_height())))
        p.ctx.restore()

    def _draw_entry_icon(self, p, e, cx, cy, size, sel=False):
        th = p.theme
        if e["is_dir"]:
            p.app_icon("folder", cx, cy, size)
            return
        if is_image(e["name"]):
            # miniaturas: moldura com "paisagem"
            s = float(size)
            p.round(cx - s * 0.42, cy - s * 0.34, s * 0.84, s * 0.68,
                    s * 0.10, th.accent2, 0.55)
            p.poly([(cx - s * 0.30, cy + s * 0.24), (cx - s * 0.06, cy - s * 0.10),
                    (cx + s * 0.12, cy + s * 0.24)], th.accent, 0.95)
            p.circle(cx + s * 0.18, cy - s * 0.12, s * 0.09, th.warn, 0.95)
            return
        s = float(size)
        p.round(cx - s * 0.34, cy - s * 0.44, s * 0.68, s * 0.88, s * 0.07,
                th.dim2, 0.45)
        p.round(cx - s * 0.34, cy - s * 0.44, s * 0.68, s * 0.88, s * 0.07,
                th.dim, 0.0, filled=False, width=1.4)
        for i in range(3):
            p.line(cx - s * 0.20, cy - s * 0.16 + i * s * 0.18,
                   cx + s * 0.16, cy - s * 0.16 + i * s * 0.18, th.dim, 1.2,
                   0.8)

    # ---------------- barra de acoes ----------------

    def _draw_action_bar(self, p):
        th = p.theme
        ax, ay, aw, ah = self._rects.get("action", (0, 0, 0, 0))
        if aw <= 0 or not self.action_bar:
            return
        p.rect(ax, ay, aw, ah, th.panel_hi, 0.85)
        p.line(ax, ay, ax + aw, ay, th.accent, 1.0, 0.45)
        for b in self._btns:
            if b.get("zone") == "action":
                self._draw_button(p, b, th)
        # nome do item alvo (a direita)
        name = ellipsis(self.action_bar.get("name", ""),
                        int(aw * 0.30), th.font_small)
        p.text(name, ax + aw - PAD, ay + ah / 2 + th.font_small * 0.35,
               th.font_small, th.dim, align="right")

    # ---------------- rodape ----------------

    def _draw_footer(self, p):
        th = p.theme
        fx, fy, fw, fh = self._rects["footer"]
        p.rect(fx, fy, fw, fh, th.panel, 0.92)
        p.line(fx, fy, fx + fw, fy, th.accent, 1.0, 0.35)
        for b in self._btns:
            if b.get("zone") == "footer":
                self._draw_button(p, b, th)
        # status: contagem, tamanho, espaco livre
        items = len(self.entries)
        total = self._dir_size
        if total is None:
            total = sum((e.get("size") or 0) for e in self.entries
                        if not e["is_dir"])
        free = self._free_space()
        line1 = "%d itens - %s" % (items, human_size(total))
        col = th.ok
        if self.status_kind == "err":
            col = th.err
        elif self.status_kind == "warn":
            col = th.warn
        line2 = self.status if self.status else "livre: %s" % human_size(free)
        p.text(ellipsis(line1, fw - 30, th.font_small), fx + PAD,
               fy + 24, th.font_small, th.dim)
        p.text(ellipsis(line2, fw - 30, th.font_small), fx + PAD,
               fy + 46, th.font_small, col)

    # ---------------- modal ----------------

    def _draw_modal(self, p):
        th = p.theme
        M = self._modal
        if not M:
            return
        x, y, w, h = M["rect"]
        # escurece o fundo
        cx, cy, cw, ch = self._content_rect()
        p.rect(cx, cy, cw, ch, (0, 0, 0), 0.55)
        p.panel(x, y, w, h, th.panel, 0.98, r=th.radius, border=True)
        # titulo
        tx, ty, tw, thh = M["title"]
        p.rect(x + 1, y + 1, w - 2, thh - 1, th.panel_hi, 0.9)
        p.text(self._modal_title(), tx + 18, ty + thh / 2 + th.font * 0.35,
               th.font, th.text, "bold")
        for b in self._modal_btns:
            self._draw_button(p, b, th)
        kind = M["kind"]
        m = self.dialog or self.overlay
        if kind in ("novo", "novo_pasta", "renomear", "buscar", "ir_para"):
            self._draw_text_field(p, M, m)
        if kind == "excluir":
            self._draw_delete_body(p, M, m)
        if kind == "info":
            self._draw_info_body(p, M, m)
        if kind == "abrir_com":
            self._draw_list_body(p, M, m)
        if kind == "buscar":
            self._draw_results_body(p, M, m)
        if kind == "dispositivos":
            self._draw_devices_body(p, M, m)

    def _modal_title(self):
        m = self.dialog or self.overlay or {}
        kind = m.get("kind")
        if m.get("title"):
            return m["title"]
        if kind == "novo":
            return "Novo item"
        if kind == "novo_pasta":
            return "Nova pasta"
        if kind == "renomear":
            return "Renomear"
        if kind == "excluir":
            return "Excluir"
        if kind == "info":
            return "Informacoes"
        if kind == "abrir_com":
            return "Abrir com"
        if kind == "buscar":
            return "Pesquisar"
        if kind == "ir_para":
            return "Ir para o caminho"
        if kind == "dispositivos":
            return "Dispositivos"
        return "NURA Explorer"

    def _draw_text_field(self, p, M, m):
        th = p.theme
        bx, by, bw, bh = M["body"]
        field = m.get("field")
        if field is None:
            field = m.get("text", "")
        p.round(bx, by, bw, MIN_TOUCH, th.radius, th.panel_hi, 0.9)
        p.round(bx, by, bw, MIN_TOUCH, th.radius, th.accent, 0.5,
                filled=False, width=1.0)
        p.text(ellipsis(field, bw - 24, th.font), bx + 12,
               by + MIN_TOUCH / 2 + th.font * 0.35, th.font, th.text)

    def _draw_delete_body(self, p, M, m):
        th = p.theme
        bx, by, bw, bh = M["body"]
        p.text("Excluir '%s'?" % m.get("name", ""), bx + 6,
               by + 30, th.font, th.text, "bold")
        p.text("A exclusao nao pode ser desfeita.", bx + 6, by + 60,
               th.font_small, th.dim)
        p.text("O pedido so e enviado depois da confirmacao.", bx + 6,
               by + 84, th.font_small, th.dim)

    def _draw_info_body(self, p, M, m):
        th = p.theme
        bx, by, bw, bh = M["body"]
        info = m.get("info") or {}
        rows = []
        for key in sorted(info.keys()):
            val = info[key]
            if isinstance(val, (dict, list, tuple)):
                val = str(val)
            if val is None or val == "":
                continue
            if key in ("size", "bytes", "size_bytes"):
                val = "%s (%s bytes)" % (human_size(val), val)
            if key in ("mtime", "ctime", "atime"):
                val = human_date(val)
            if key in ("mode", "mode_oct") and isinstance(val, int):
                try:
                    val = "%04o" % val
                except Exception:
                    pass
            label = STAT_LABELS.get(key, str(key).replace("_", " ").capitalize())
            rows.append((label, str(val)))
        if not rows:
            rows = [("Informacoes", "indisponivel")]
        ry = by
        for label, val in rows:
            if ry + 24 > by + bh:
                break
            p.text(label, bx + 4, ry + 14, th.font_small, th.dim)
            p.text(ellipsis(val, bw - 180, th.font_small), bx + 170, ry + 14,
                   th.font_small, th.text)
            ry += 26

    def _draw_list_body(self, p, M, m):
        th = p.theme
        bx, by, bw, bh = M["body"]
        cmds = m.get("commands") or []
        if not cmds:
            p.text("nenhum programa disponivel", bx + 6, by + 24,
                   th.font_small, th.warn)
            return
        ry = by
        for c in cmds:
            if ry + MIN_TOUCH > by + bh:
                break
            p.round(bx, ry, bw, MIN_TOUCH, th.radius, th.panel_hi, 0.55)
            p.icon("terminal", bx + 24, ry + MIN_TOUCH / 2, 20, th.accent)
            p.text(ellipsis(c["label"], bw - 120, th.font_small), bx + 44,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.text)
            p.text(ellipsis(c["cmd"], bw - 60, th.font_small), bx + bw - 10,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.dim, align="right")
            ry += MIN_TOUCH + 4

    def _draw_results_body(self, p, M, m):
        th = p.theme
        bx, by, bw, bh = M["body"]
        res = m.get("results") or []
        if not res:
            p.text("nenhum resultado", bx + 6, by + 24, th.font_small, th.dim)
            return
        ry = by
        for r in res:
            if ry + MIN_TOUCH > by + bh:
                break
            p.round(bx, ry, bw, MIN_TOUCH, th.radius, th.panel_hi, 0.55)
            p.icon("search", bx + 24, ry + MIN_TOUCH / 2, 18, th.accent)
            p.text(ellipsis(r["name"], bw - 150, th.font_small), bx + 44,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.text)
            p.text(ellipsis(r["path"], bw - 60, th.font_small), bx + bw - 10,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.dim, align="right")
            ry += MIN_TOUCH + 4

    def _draw_devices_body(self, p, M, m):
        th = p.theme
        bx, by, bw, bh = M["body"]
        devs = m.get("devices") or []
        mts = m.get("mounts") or []
        if not devs and not mts:
            p.text("nenhum dispositivo adicional", bx + 6, by + 24,
                   th.font_small, th.dim)
            return
        ry = by
        for d in devs:
            if ry + MIN_TOUCH > by + bh:
                break
            p.round(bx, ry, bw, MIN_TOUCH, th.radius, th.panel_hi, 0.55)
            p.icon("disk", bx + 24, ry + MIN_TOUCH / 2, 20, th.accent)
            p.text(ellipsis(d["label"], bw - 120, th.font_small), bx + 44,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.text)
            p.text(ellipsis(d["path"], bw - 60, th.font_small), bx + bw - 10,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.dim, align="right")
            ry += MIN_TOUCH + 4
        for mt in mts:
            if ry + MIN_TOUCH > by + bh:
                break
            p.round(bx, ry, bw, MIN_TOUCH, th.radius, th.panel_hi, 0.55)
            p.icon("disk", bx + 24, ry + MIN_TOUCH / 2, 20, th.accent)
            p.text(ellipsis(mt["mount"], bw - 60, th.font_small), bx + 44,
                   ry + MIN_TOUCH / 2 + th.font_small * 0.35, th.font_small,
                   th.text)
            ry += MIN_TOUCH + 4

    # ---------------- visualizador embutido ----------------

    def _draw_viewer(self, p):
        th = p.theme
        cx, cy, cw, ch = self._content_rect()
        p.rect(cx, cy, cw, ch, (0, 0, 0), 0.80)
        v = self.viewer
        rect = (cx + 20, cy + 20, cw - 40, ch - 40)
        p.panel(rect[0], rect[1], rect[2], rect[3], th.panel, 0.98,
                r=th.radius, border=True)
        v.draw_in(p, rect)


# --------------------------------------------------------------------
# visualizador de imagens
# --------------------------------------------------------------------

class ImageViewerApp(App):
    """Visualizador embutido do Explorer (PNG via cairo)."""

    title = "Visualizador"
    icon = "info"
    width = 900
    height = 620
    min_width = 480
    min_height = 320

    def __init__(self, path=None, shell=None, parent=None, **kw):
        App.__init__(self, shell=shell, **kw)
        self.path = path or ""
        self.parent = parent
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.surface = None
        self.error = ""
        self.closed = False
        self.dirty = True
        self._pressed = None
        self._btns = []
        self._own_theme = Theme("neon")
        self.load()

    # ---------------- carga ----------------

    def load(self):
        """Carrega a imagem. JPEG e outros formatos: aviso honesto."""
        self.surface = None
        self.error = ""
        if not self.path:
            self.error = "nenhuma imagem selecionada"
            return
        ext = os.path.splitext(self.path)[1].lower()
        if ext not in PNG_EXT:
            if ext in IMG_EXT:
                self.error = ("formato nao suportado: %s "
                              "(o visualizador usa PNG via cairo)" % ext)
            else:
                self.error = "nao e uma imagem: %s" % ext
            return
        try:
            self.surface = cairo.ImageSurface.create_from_png(self.path)
        except Exception as e:
            self.error = ("nao foi possivel abrir a imagem "
                          "(PNG invalido ou corrompido): %s" % e)

    # ---------------- ciclo de vida ----------------

    def on_open(self):
        self.load()
        self.dirty = True

    def on_close(self):
        self.closed = True
        if self.parent is not None:
            try:
                self.parent.on_viewer_closed(self)
            except Exception:
                pass

    def on_tick(self, dt):
        pass

    # ---------------- desenho ----------------

    def _theme(self):
        sh = self.shell
        if sh is not None:
            th = getattr(sh, "theme", None)
            if th is not None:
                return th
        return self._own_theme

    def _content_rect(self):
        if self.window is not None:
            return self.window.content_rect()
        return (0, 0, self.width, max(200, self.height - 46))

    def draw(self, p):
        cx, cy, cw, ch = self._content_rect()
        p.rect(cx, cy, cw, ch, p.theme.bg, 1.0)
        self.draw_in(p, (cx, cy, cw, ch))
        self.dirty = False

    def draw_in(self, p, rect):
        """Desenha o visualizador dentro de um retangulo."""
        th = p.theme
        x, y, w, h = rect
        p.rect(x, y, w, h, th.bg, 0.98)
        bar_h = MIN_TOUCH + 12
        area = (x, y + bar_h, w, h - bar_h)
        if self.error:
            p.text(self.error, x + w / 2, y + h / 2 - 10, th.font_title,
                   th.warn, "bold", align="center")
            if not is_png(self.path):
                p.text("o cairo so decodifica PNG; os demais formatos "
                       "precisam de outro visualizador.",
                       x + w / 2, y + h / 2 + 24, th.font_small, th.dim,
                       align="center")
        elif self.surface is None:
            p.text("sem imagem", x + w / 2, y + h / 2, th.font, th.dim,
                   align="center")
        else:
            iw = self.surface.get_width()
            ih = self.surface.get_height()
            dw = iw * self.zoom
            dh = ih * self.zoom
            ox = x + (w - dw) / 2.0 + self.pan_x
            oy = y + (h - dh) / 2.0 + self.pan_y
            p.ctx.save()
            p.ctx.rectangle(area[0], area[1], area[2], area[3])
            p.ctx.clip()
            p.ctx.set_source_surface(self.surface, ox, oy)
            p.ctx.paint()
            p.ctx.restore()
        # barra de ferramentas
        self._draw_toolbar(p, x, y, w, bar_h, th)

    def _draw_toolbar(self, p, x, y, w, bar_h, th):
        fs = th.font_small
        p.rect(x, y, w, bar_h, th.panel, 0.95)
        p.line(x, y + bar_h, x + w, y + bar_h, th.accent, 1.0, 0.35)
        name = os.path.basename(self.path or "")
        bx = x + 12
        for bid, label in (("zoom_out", "-"), ("zoom_in", "+"),
                           ("zoom_fit", "Ajustar")):
            bw = max(MIN_TOUCH, int(measure(label, fs)) + 26)
            p.round(bx, y + 6, bw, MIN_TOUCH, th.radius, th.panel_hi, 0.75)
            p.round(bx, y + 6, bw, MIN_TOUCH, th.radius, th.accent, 0.45,
                    filled=False, width=1.0)
            p.text(label, bx + bw / 2, y + 6 + MIN_TOUCH / 2 + fs * 0.35, fs,
                   th.text, align="center")
            bx += bw + 8
        p.text("%s  (%.0f%%)" % (ellipsis(name, max(60, w - bx - 200), fs),
                                 self.zoom * 100.0),
               bx + 4, y + bar_h / 2 + fs * 0.35, fs, th.dim)
        bw = max(MIN_TOUCH, int(measure("Fechar", fs)) + 26)
        p.round(x + w - bw - 12, y + 6, bw, MIN_TOUCH, th.radius, th.err,
                0.30)
        p.text("Fechar", x + w - bw / 2 - 12, y + 6 + MIN_TOUCH / 2 + fs * 0.35,
               fs, th.text, align="center")

    # ---------------- toque ----------------

    def on_touch(self, ev):
        et = getattr(ev, "type", "")
        th = self._theme()
        if et == "down":
            b = self._hit(ev.x, ev.y)
            if b is not None:
                self._pressed = b
                self.dirty = True
                return True
            return False
        if et == "up":
            self._pressed = None
            return False
        if et == "tap":
            b = self._hit(ev.x, ev.y)
            if b is None:
                return False
            self._press(b)
            return True
        if et == "pinch":
            scale = getattr(ev, "scale", 1.0) or 1.0
            self._zoom(self.zoom * scale)
            return True
        if et == "drag":
            self.pan_x += getattr(ev, "dx", 0.0) or 0.0
            self.pan_y += getattr(ev, "dy", 0.0) or 0.0
            self.dirty = True
            return True
        return False

    def _hit(self, x, y):
        th = self._theme()
        fs = th.font_small
        cx, cy, cw, ch = self._content_rect()
        bar_h = MIN_TOUCH + 12
        bx = cx + 12
        for bid, label in (("zoom_out", "-"), ("zoom_in", "+"),
                           ("zoom_fit", "Ajustar")):
            bw = max(MIN_TOUCH, int(measure(label, fs)) + 26)
            if bx <= x <= bx + bw and cy + 6 <= y <= cy + 6 + MIN_TOUCH:
                return bid
            bx += bw + 8
        bw = max(MIN_TOUCH, int(measure("Fechar", fs)) + 26)
        if cx + cw - bw - 12 <= x <= cx + cw - 12 and \
                cy + 6 <= y <= cy + 6 + MIN_TOUCH:
            return "close"
        return None

    def _press(self, bid):
        if bid == "zoom_in":
            self._zoom(self.zoom * 1.25)
        elif bid == "zoom_out":
            self._zoom(self.zoom / 1.25)
        elif bid == "zoom_fit":
            self.zoom = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0
            self.dirty = True
        elif bid == "close":
            self._close()

    def _zoom(self, z):
        self.zoom = max(0.1, min(8.0, float(z)))
        self.dirty = True

    def _close(self):
        sh = self.shell
        if sh is not None and hasattr(sh, "close_window") and \
                self.window is not None:
            try:
                sh.close_window(self.window)
                return
            except Exception:
                pass
        self.closed = True
        if self.parent is not None:
            try:
                self.parent.on_viewer_closed(self)
            except Exception:
                pass


# --------------------------------------------------------------------
# helpers publicos
# --------------------------------------------------------------------

def open_explorer(shell=None, **kw):
    """Cria e devolve um ExplorerApp pronto para `shell.open_app`."""
    return ExplorerApp(shell=shell, **kw)


if __name__ == "__main__":       # pragma: no cover
    print("NURA Explorer - use dentro do shell do NURA OS.")
