#!/usr/bin/env python3
"""NURA OS — o "NURA Start" (menu Iniciar).

O Start e um aplicativo normal do NURA (``App``), mas se comporta como
um menu flutuante ancorado na barra de tarefas:

  * cabecalho com o nome do sistema e do tema ativo;
  * campo de pesquisa que filtra a lista em tempo real;
  * favoritos (topo) e recentes, quando existirem de verdade;
  * lista rolavel de aplicativos em duas colunas (icone + nome + nota);
  * atalhos para locais reais ("/home" e "~/.config/nura");
  * rodape com Desligar / Reiniciar / Encerrar sessao, todos com
    confirmacao.

Regras seguidas:
  * nada e inventado — a lista vem de ``nura_apps`` (que so le .desktop
    reais e os apps internos do NURA);
  * nenhum comando e executado sem acao explicita do usuario (um toque
    no item, e confirmacao para as acoes de energia);
  * nada e desenhado fora do ``Painter``/tema; nada opaco sobre o desktop.

Somente biblioteca padrao + os modulos do proprio NURA.
"""

import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nura_apps as A            # noqa: E402
from nura_window import App, Window   # noqa: E402

# --------------------------------------------------------------------
# constantes de layout
# --------------------------------------------------------------------

ITEM_H = 62               # altura de um item da lista
ITEM_GAP = 8              # espaco vertical entre itens
SEARCH_H = 46              # altura do campo de pesquisa
BTN_H = 44                # altura minima de um botao (alvo de toque)

#: icones coloridos do Painter.app_icon
APP_ICON_NAMES = ("monitor", "folder", "globe", "terminal", "store",
                  "gear", "gamepad", "power")

#: onde procurar o aplicativo interno de cada app_key
#: (modulo, classe) — tried em ordem; o primeiro que existir e usado.
#: A primeira opcao de cada lista e a mesma do shell (nura_shell.make_app).
INTERNAL_SPECS = {
    "terminal": (("nura_terminal", "TerminalApp"),
                 ("nura_terminal", "Terminal")),
    "explorer": (("nura_explorer", "ExplorerApp"),
                 ("nura_explorer", "FileExplorerApp"),
                 ("nura_filemgr_app", "ExplorerApp"),
                 ("nura_filemgr", "FileManagerApp")),
    "control": (("nura_controlcenter", "ControlCenterApp"),
                ("nura_control", "ControlApp"),
                ("nura_settings", "SettingsApp")),
    "performance": (("nura_performance", "PerformanceApp"),
                    ("nura_performance", "Performance")),
    "games": (("nura_gamehub", "GameHub"),
              ("nura_gamehub", "GameHubApp"),
              ("nura_games", "GamesApp")),
}

#: se o shell abrir os apps internos diretamente, usamos esses metodos
SHELL_FALLBACKS = {
    "terminal": ("open_terminal",),
    "explorer": ("open_explorer", "open_files", "open_filemanager"),
    "control": ("open_control", "open_control_center", "open_settings"),
    "performance": ("open_performance", "open_monitor"),
    "games": ("open_games", "open_gamehub"),
}

#: metodos opcionais do shell que abrem o teclado na tela
KEYBOARD_METHODS = ("open_keyboard", "show_keyboard", "start_keyboard",
                    "toggle_keyboard", "keyboard_open")

POWER_ACTIONS = (
    ("shutdown", "Desligar", "power"),
    ("reboot", "Reiniciar", "refresh"),
    ("logout", "Encerrar sessao", "close"),
)

POWER_COMMANDS = {"shutdown": "poweroff", "reboot": "reboot"}

POWER_MESSAGES = {
    "shutdown": "Desligar o NURA OS agora?",
    "reboot": "Reiniciar o NURA OS agora?",
    "logout": "Encerrar a sessao atual do NURA OS?",
}


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------

def _import_module(name):
    """Importa um modulo do NURA sem levantar excecao."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _instantiate(cls, shell, **kw):
    """Cria a instancia do app interno tolerando assinaturas diferentes."""
    tentativas = []
    if kw:
        tentativas.append(dict(kw, shell=shell))
        tentativas.append(dict(kw))
    tentativas.append({"shell": shell})
    tentativas.append({})
    for args in tentativas:
        try:
            return cls(**args)
        except TypeError:
            continue
        except Exception:
            continue
    try:
        return cls(shell)
    except Exception:
        return None


def _expand(path):
    try:
        return os.path.expanduser(os.path.expandvars(str(path)))
    except Exception:
        return str(path)


# --------------------------------------------------------------------
# o aplicativo
# --------------------------------------------------------------------

class StartApp(App):
    """Menu Iniciar do NURA OS."""

    title = "NURA Start"
    icon = "grid"
    width = 760
    height = 620
    min_width = 560
    min_height = 420
    resizable = True

    def __init__(self, shell=None, **kw):
        App.__init__(self, shell=shell, **kw)
        self.visible = False
        self.text_input = ""       # buffer interno do campo de pesquisa
        self.focused = False       # o campo de pesquisa esta focado?
        self.scroll = 0.0
        self.scroll_max = 0.0
        self.pressed = None        # item sob o dedo
        self._hits = []            # areas clicaveis do ultimo quadro
        self._scroll_rect = (0, 0, 0, 0)
        self._last_key = None
        self._last_at = 0.0
        self._last_refresh = 0.0
        self._theme_fallback = None
        self._owns_window = False  # a janela foi criada por nos?
        self.catalog = []
        self.fav_names = []
        self.recent_names = []
        self.recent_items = []

    # ---------------------------------------------------------
    # ciclo de vida
    # ---------------------------------------------------------

    def on_open(self):
        """Mostra a janela do menu (chamado ao abrir)."""
        self.visible = True
        self.refresh()
        self.focused = False
        self.text_input = ""
        self.scroll = 0.0
        self._ensure_window()
        self._anchor()

    def on_close(self):
        self.visible = False
        self.focused = False
        self.pressed = None
        sh = self.shell
        if sh is not None and getattr(sh, "start_window", None) is self.window:
            try:
                sh.start_window = None
            except Exception:
                pass

    def on_focus(self, focused):
        if not focused:
            self.focused = False
            self.pressed = None

    def _ensure_window(self):
        """Garante que existe uma janela para o menu.

        Quando o Start e aberto pelo botao "NURA" da barra de tarefas o
        shell nao cria nenhuma janela: o proprio app cria a sua (para
        parecer um menu flutuante ancorado na barra) e a registra no
        shell, que passa a desenhar e a encaminhar os toques.
        """
        sh = self.shell
        if self.window is not None:
            # janela ja existia (o shell abriu o app): so garante que o
            # shell use a nossa janela como "menu iniciar"
            if sh is not None and hasattr(sh, "start_window"):
                try:
                    sh.start_window = self.window
                except Exception:
                    pass
            return self.window
        try:
            win = Window(self, x=24, y=90, shell=sh)
        except Exception:
            return None
        self.window = win
        self._owns_window = True
        if sh is not None:
            janelas = getattr(sh, "windows", None)
            if isinstance(janelas, list) and win not in janelas:
                janelas.append(win)
            if hasattr(sh, "start_window"):
                try:
                    sh.start_window = win
                except Exception:
                    pass
        return win

    def close(self):
        """Fecha o menu Iniciar (metodo publico)."""
        self.focused = False
        win = self.window
        sh = self.shell
        if win is None:
            self.visible = False
            return False
        fechado = False
        if sh is not None and hasattr(sh, "close_window"):
            try:
                sh.close_window(win)
                fechado = True
            except Exception:
                fechado = False
        if not fechado:
            janelas = getattr(sh, "windows", None) if sh is not None else None
            if isinstance(janelas, list) and win in janelas:
                try:
                    janelas.remove(win)
                except Exception:
                    pass
            try:
                self.on_close()
            except Exception:
                pass
        if sh is not None:
            if getattr(sh, "start_window", None) is win:
                try:
                    sh.start_window = None
                except Exception:
                    pass
            if hasattr(sh, "start_open"):
                try:
                    sh.start_open = False
                except Exception:
                    pass
        self.window = None
        self._owns_window = False
        self.visible = False
        self.pressed = None
        return True

    # ---------------------------------------------------------
    # dados
    # ---------------------------------------------------------

    def refresh(self):
        """Recarrega catalogo, favoritos e recentes."""
        try:
            self.catalog = A.catalog()
        except Exception:
            self.catalog = list(A.NURA_APPS)
        self._reload_lists()
        self._last_refresh = time.time()

    def _reload_lists(self):
        try:
            self.fav_names = A.favorites()
        except Exception:
            self.fav_names = []
        try:
            self.recent_items = A.recent_apps()
        except Exception:
            self.recent_items = []
        self.recent_names = [i.get("name") for i in self.recent_items
                             if isinstance(i, dict)]

    def _fav_set(self):
        return set(n for n in self.fav_names if n)

    # ---------------------------------------------------------
    # tema / geometria
    # ---------------------------------------------------------

    def _theme(self):
        th = getattr(self.shell, "theme", None)
        if th is not None:
            return th
        if self._theme_fallback is None:
            try:
                from nura_theme import Theme
                self._theme_fallback = Theme("neon")
            except Exception:
                return None
        return self._theme_fallback

    def _content_rect(self):
        win = self.window
        if win is not None:
            try:
                return win.content_rect()
            except Exception:
                pass
        return (0, 0, int(self.width), int(self.height))

    def _screen(self):
        """(largura, altura) da tela, se o shell informar."""
        w, h = 1920, 1080
        sh = self.shell
        for attr, current in (("screen_w", w), ("DESK_W", w),
                              ("screen_h", h), ("DESK_H", h)):
            v = getattr(sh, attr, None) if sh is not None else None
            if isinstance(v, (int, float)) and v > 100:
                if attr in ("screen_w", "DESK_W"):
                    w = int(v)
                else:
                    h = int(v)
        return (w, h)

    def _anchor(self):
        """Coloca a janela acima da barra de tarefas (visual de menu)."""
        win = self.window
        if win is None:
            return
        th = self._theme()
        tb = int(getattr(th, "taskbar_h", 64)) if th is not None else 64
        sw, sh_ = self._screen()
        h = min(int(win.h), max(int(self.min_height), sh_ - tb - 24))
        win.h = h
        win.x = 24
        win.y = sh_ - tb - h - 12
        if self.shell is not None and hasattr(self.shell, "clamp_window"):
            try:
                nx, ny = self.shell.clamp_window(win.x, win.y, win.w, win.h)
                win.x, win.y = int(nx), int(ny)
            except Exception:
                pass

    # ---------------------------------------------------------
    # desenho
    # ---------------------------------------------------------

    def draw(self, p):
        th = self._theme()
        if th is None:
            return
        x, y, w, h = self._content_rect()
        if w <= 0 or h <= 0:
            return
        self._hits = []

        # painel translucido do menu (nada opaco sobre o desktop)
        p.round(x + 2, y + 2, w - 4, h - 4, th.radius + 4, th.panel, 0.88)
        p.round(x + 2, y + 2, w - 4, h - 4, th.radius + 4, th.accent, 0.25,
                filled=False, width=1.2)

        pad = th.pad
        ix = x + pad
        iw = w - 2 * pad
        top = y + pad

        self._draw_header(p, th, ix, top, iw)
        div_y = top + self._header_h(th)
        p.line(ix, div_y, ix + iw, div_y, th.accent, 1.0, 0.25)

        sy = div_y + th.gap
        self._draw_search(p, th, ix, sy, iw)

        foot_h = BTN_H + th.gap + BTN_H
        foot_y = y + h - pad - foot_h
        ry = sy + SEARCH_H + th.gap
        rh = max(40, foot_y - th.gap - ry)
        self._scroll_rect = (ix, ry, iw, rh)

        secs = self._sections()
        conteudo_h = sum(self._section_h(sec, th) for sec in secs)
        self.scroll_max = max(0.0, conteudo_h - rh)
        self.scroll = max(0.0, min(self.scroll, self.scroll_max))
        gw = iw - (12 if self.scroll_max > 0 else 0)

        p.ctx.save()
        p.ctx.rectangle(ix, ry, iw, rh)
        p.ctx.clip()
        cy = ry - self.scroll
        for sec in secs:
            cy = self._draw_section(p, th, ix, cy, gw, sec)
        p.ctx.restore()

        if self.scroll_max > 0:
            p.scrollbar(ix + iw - 6, ry, 5, rh, self.scroll / self.scroll_max)

        self._draw_footer(p, th, ix, foot_y, iw)

    def _header_h(self, th):
        nome_tema = str(getattr(th, "name", "") or "")
        extra = (th.font_small + 6) if nome_tema else 0
        return th.font_title * 0.85 + extra + 10

    def _draw_header(self, p, th, ix, top, iw):
        p.text("NURA OS", ix, top + th.font_title * 0.85, th.font_title,
               th.text, "bold")
        nome_tema = str(getattr(th, "name", "") or "")
        if nome_tema:
            p.text(nome_tema, ix, top + th.font_title * 0.85 + th.font_small + 6,
                   th.font_small, th.dim)
        p.icon("grid", ix + iw - 14, top + 18, 28, th.accent)

    def _draw_search(self, p, th, ix, sy, iw):
        p.round(ix, sy, iw, SEARCH_H, th.radius, th.panel_hi, 0.70)
        p.round(ix, sy, iw, SEARCH_H, th.radius, th.accent,
                0.55 if self.focused else 0.20, filled=False, width=1.2)
        p.icon("search", ix + 24, sy + SEARCH_H / 2.0, 20,
               th.accent if self.focused else th.dim)
        texto = self.text_input
        if texto:
            p.text(texto, ix + 46, sy + SEARCH_H / 2.0 + th.font * 0.35,
                   th.font, th.text)
        else:
            p.text("Buscar aplicativos...", ix + 46,
                   sy + SEARCH_H / 2.0 + th.font * 0.35, th.font, th.dim)
        if self.focused and (time.time() % 1.0) < 0.55:
            larg = p.tw(texto, th.font) if texto else 0.0
            p.rect(ix + 48 + larg, sy + 10, 2, SEARCH_H - 20, th.accent, 0.95)
        self._hits.append(("search", None, (ix, sy, iw, SEARCH_H)))

    # ---------------------------------------------------------
    # secoes
    # ---------------------------------------------------------

    def _sections(self):
        vis = A.search_apps(self.text_input, self.catalog)
        secs = []
        if not self.text_input.strip():
            favs = self._fav_set()
            if favs:
                lista = [e for e in self.catalog if e.name in favs]
                if lista:
                    secs.append(("Favoritos", lista))
            recs = self._recent_entries()
            if recs:
                secs.append(("Recentes", recs))
        secs.append(("Aplicativos", vis))
        return secs

    def _recent_entries(self):
        out = []
        for item in self.recent_items:
            nome = item.get("name") if isinstance(item, dict) else None
            if not nome:
                continue
            for e in self.catalog:
                if e.name == nome and e not in out:
                    out.append(e)
                    break
        return out

    def _section_h(self, sec, th):
        label, entries = sec
        rows = (len(entries) + 1) // 2
        if not rows:
            return 0
        return (th.font_small + 8 + rows * ITEM_H +
                max(0, rows - 1) * ITEM_GAP + th.gap)

    def _draw_section(self, p, th, x, y, w, sec):
        label, entries = sec
        if not entries:
            return y
        p.text(label.upper(), x, y + th.font_small, th.font_small, th.dim,
               "bold")
        y += th.font_small + 8
        col_w = (w - th.gap) // 2
        for i, e in enumerate(entries):
            col = i % 2
            row = i // 2
            ix = x + col * (col_w + th.gap)
            iy = y + row * (ITEM_H + ITEM_GAP)
            self._draw_item(p, th, ix, iy, col_w, ITEM_H, e)
            self._hits.append(("app", e, (ix, iy, col_w, ITEM_H)))
        rows = (len(entries) + 1) // 2
        y += rows * ITEM_H + max(0, rows - 1) * ITEM_GAP + th.gap
        return y

    def _draw_item(self, p, th, x, y, w, h, entry):
        if self._is_pressed("app", entry):
            p.round(x, y, w, h, th.radius, th.accent, 0.24)
        else:
            p.round(x, y, w, h, th.radius, th.panel_hi, 0.40)
        self._draw_icon(p, th, entry.icon, x + 26, y + h / 2.0, 32)
        tx = x + 52
        avail = w - 52 - 10
        nome = self._fit(p, entry.name, avail, th.font)
        p.text(nome, tx, y + h / 2.0 - 2, th.font, th.text)
        if entry.comment:
            com = self._fit(p, entry.comment, avail, th.font_small)
            p.text(com, tx, y + h / 2.0 + th.font_small + 2, th.font_small,
                   th.dim)

    def _draw_icon(self, p, th, name, cx, cy, size):
        """Desenha o icone do app (vetorial) ou um marcador neutro."""
        if not name:
            p.icon("grid", cx, cy, size, th.accent)
            return
        if name in APP_ICON_NAMES:
            p.app_icon(name, cx, cy, size)
            return
        if os.path.isabs(name):
            # caminho de icone: o NURA nao carrega PNG, mostra um marcador
            p.round(cx - size * 0.36, cy - size * 0.36, size * 0.72,
                    size * 0.72, size * 0.16, th.accent, 0.30)
            p.round(cx - size * 0.36, cy - size * 0.36, size * 0.72,
                    size * 0.72, size * 0.16, th.accent, 0.0, filled=False,
                    width=1.5)
            return
        p.icon(name, cx, cy, size, th.accent)

    def _fit(self, p, text, maxw, size):
        """Corta o texto para caber em ``maxw`` (com reticencias)."""
        if not text:
            return ""
        if maxw <= 0:
            return ""
        if p.tw(text, size) <= maxw:
            return text
        s = text
        while s and p.tw(s + "...", size) > maxw:
            s = s[:-1]
        return (s + "...") if s else ""

    # ---------------------------------------------------------
    # rodape
    # ---------------------------------------------------------

    def _draw_footer(self, p, th, ix, foot_y, iw):
        atalhos = self._shortcuts()
        if atalhos:
            n = len(atalhos)
            bw = (iw - th.gap * (n - 1)) // n
            for i, sc in enumerate(atalhos):
                bx = ix + i * (bw + th.gap)
                pressed = self._is_pressed("shortcut", sc)
                p.button(bx, foot_y, bw, BTN_H, sc[1], pressed=pressed,
                         size=th.font_small)
                self._hits.append(("shortcut", sc, (bx, foot_y, bw, BTN_H)))

        py = foot_y + BTN_H + th.gap
        n = len(POWER_ACTIONS)
        bw = (iw - th.gap * (n - 1)) // n
        for i, (key, label, icon) in enumerate(POWER_ACTIONS):
            bx = ix + i * (bw + th.gap)
            pressed = self._is_pressed("power", key)
            size = th.font
            if p.tw(label, size) > bw - 52:
                size = th.font_small
            accent = th.err if key == "shutdown" else th.accent
            p.button(bx, py, bw, BTN_H, label, pressed=pressed, accent=accent,
                     size=size, icon=icon)
            self._hits.append(("power", key, (bx, py, bw, BTN_H)))

    def _shortcuts(self):
        """Atalhos para locais que existem de verdade."""
        out = []
        home = "/home"
        try:
            if os.path.isdir(home):
                out.append(("files", "Arquivos", home, "home"))
        except Exception:
            pass
        try:
            cfg = os.path.join(_expand("~"), ".config", "nura")
            if os.path.isdir(cfg):
                out.append(("config", "Configuracoes", cfg, "gear"))
        except Exception:
            pass
        return out

    # ---------------------------------------------------------
    # interacao
    # ---------------------------------------------------------

    def _hit_test(self, x, y):
        for kind, obj, rect in reversed(self._hits):
            rx, ry, rw, rh = rect
            if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
                continue
            if kind == "app":
                vx, vy, vw, vh = self._scroll_rect
                if not (vx <= x <= vx + vw and vy <= y <= vy + vh):
                    continue
            return (kind, obj, rect)
        return None

    def _is_pressed(self, kind, obj):
        pr = self.pressed
        if not pr:
            return False
        return pr[0] == kind and pr[1] is obj

    def on_touch(self, ev):
        et = getattr(ev, "type", "")
        if et == "down":
            self.pressed = self._hit_test(ev.x, ev.y)
            return self.pressed is not None
        if et == "up":
            alvo = self.pressed
            self.pressed = None
            if alvo is not None:
                atual = self._hit_test(ev.x, ev.y)
                if atual is not None and atual[0] == alvo[0] and \
                        atual[1] is alvo[1]:
                    self._activate(alvo)
                    return True
            return False
        if et == "tap":
            alvo = self._hit_test(ev.x, ev.y)
            if alvo is not None:
                self._activate(alvo)
                return True
            return False
        if et == "scroll":
            self._scroll_by(getattr(ev, "amount", 0.0))
            return True
        if et == "drag":
            self._scroll_by(-float(getattr(ev, "dy", 0.0) or 0.0))
            return True
        if et == "longpress":
            alvo = self._hit_test(ev.x, ev.y)
            if alvo is not None and alvo[0] == "app":
                self._toggle_favorite(alvo[1])
                return True
            return False
        if et == "cancel":
            self.pressed = None
        return False

    def on_key(self, ev):
        chave = self._key_of(ev)
        if not chave:
            return False
        k = chave.lower()
        if k in ("escape", "esc"):
            self.close()
            return True
        if k in ("backspace",):
            if self.text_input:
                self.text_input = self.text_input[:-1]
                self._apply_query()
            return True
        if k in ("return", "enter", "kp_enter"):
            self._open_first()
            return True
        if len(chave) == 1 and chave.isprintable() and not chave.isspace():
            self.text_input += chave
            self._apply_query()
            self.focused = True
            return True
        return False

    def _key_of(self, ev):
        for attr in ("char", "key", "name", "text"):
            v = getattr(ev, attr, None)
            if isinstance(v, str) and v:
                return v
        return None

    def on_tick(self, dt):
        self._sync_keyboard()
        agora = time.time()
        if agora - self._last_refresh > 5.0:
            self._last_refresh = agora
            self._reload_lists()
        # o shell fecha o menu pelo botao "NURA" (start_open = False):
        # a janela que criamos precisa sumir junto
        if self._owns_window and self.shell is not None:
            if getattr(self.shell, "start_open", None) is False:
                self.close()

    def _sync_keyboard(self):
        """Usa o texto do teclado do shell, quando ele existir.

        So quando o campo de pesquisa esta focado — assim o teclado do
        shell nao mexe no filtro do menu por conta propria.
        """
        if not self.focused:
            return
        sh = self.shell
        if sh is None:
            return
        txt = getattr(sh, "keyboard_text", None)
        if isinstance(txt, str) and txt != self.text_input:
            self.text_input = txt
            self._apply_query()

    def _apply_query(self):
        self.scroll = 0.0

    def _scroll_by(self, amount):
        self.scroll = max(0.0, min(self.scroll + float(amount or 0.0),
                                   self.scroll_max))

    # ---------------------------------------------------------
    # acoes
    # ---------------------------------------------------------

    def _activate(self, hit):
        kind, obj, rect = hit
        agora = time.time()
        if self._last_key == (kind, id(obj)) and \
                (agora - self._last_at) < 0.6:
            return                      # toque duplicado (tap + up)
        self._last_key = (kind, id(obj))
        self._last_at = agora

        if kind == "search":
            self.focused = True
            self._open_keyboard()
        elif kind == "app":
            self._open_entry(obj)
        elif kind == "shortcut":
            self._open_shortcut(obj)
        elif kind == "power":
            self._confirm_power(obj)

    def _open_entry(self, entry):
        if entry is None:
            return
        if entry.nura and entry.app_key == "start":
            self.close()
            return
        ok = False
        if entry.nura and entry.app_key:
            ok = self._open_internal(entry.app_key)
        elif entry.exec_cmd:
            ok = self._launch(entry.exec_cmd)
        if ok:
            A.record_recent(entry)
            self.close()          # o menu fecha ao abrir um app
        else:
            self._notify("Nao foi possivel abrir %s" % entry.name)

    def _open_internal(self, key, **kw):
        """Abre um aplicativo interno do NURA."""
        app = self._make_internal(key, **kw)
        if app is None:
            return False
        return self._open_app(app, key)

    def _make_internal(self, key, **kw):
        """Cria a instancia do aplicativo interno (sem abrir)."""
        specs = INTERNAL_SPECS.get(key) or ()
        for mod_name, cls_name in specs:
            mod = _import_module(mod_name)
            if mod is None:
                continue
            cls = getattr(mod, cls_name, None)
            if cls is None:
                continue
            app = _instantiate(cls, self.shell, **kw)
            if app is not None:
                return app
        # o proprio shell sabe instanciar os apps internos
        maker = getattr(self.shell, "make_app", None) if self.shell else None
        if callable(maker):
            try:
                app = maker(key)
            except Exception:
                app = None
            if app is not None:
                return app
        return None

    def _open_app(self, app, key=None):
        """Entrega o app ao shell (abre a janela)."""
        if app is None:
            return False
        if self.shell is not None and hasattr(self.shell, "open_app"):
            try:
                self.shell.open_app(app)
                return True
            except Exception:
                pass
        # o proprio shell pode ter um metodo para abrir o app
        for metodo in SHELL_FALLBACKS.get(key, ()):
            fn = getattr(self.shell, metodo, None) if self.shell else None
            if not callable(fn):
                continue
            try:
                fn()
                return True
            except TypeError:
                try:
                    fn(app)
                    return True
                except Exception:
                    continue
            except Exception:
                continue
        return False

    def _open_shortcut(self, sc):
        """Abre um atalho de local real (/home, ~/.config/nura)."""
        if not sc:
            return
        path = sc[2]
        app = self._make_internal("explorer")
        if app is None:
            self._notify("NURA Explorer indisponivel")
            return
        self._set_path(app, path)
        if self._open_app(app, "explorer"):
            self.close()
        else:
            self._notify("Nao foi possivel abrir %s" % path)

    def _set_path(self, app, path):
        """Aponta o app para um caminho (usado nos atalhos)."""
        if app is None or not path:
            return False
        try:
            if not os.path.isdir(path):
                return False
        except Exception:
            return False
        if hasattr(app, "cwd"):
            try:
                app.cwd = path
            except Exception:
                pass
        for nome in ("navigate", "go_to", "open_path", "_navigate",
                     "_load_dir"):
            fn = getattr(app, nome, None)
            if callable(fn):
                try:
                    fn(path)
                    return True
                except Exception:
                    continue
        return hasattr(app, "cwd")

    def _open_first(self):
        vis = A.search_apps(self.text_input, self.catalog)
        if vis:
            self._open_entry(vis[0])

    def _launch(self, cmd):
        """Executa um comando real do sistema (so em toque do usuario)."""
        sh = self.shell
        if sh is not None and hasattr(sh, "launch"):
            try:
                sh.launch(cmd)
                return True
            except Exception:
                return False
        return False

    def _toggle_favorite(self, entry):
        if entry is None:
            return
        novos = A.toggle_favorite(entry.name)
        if novos is None:
            self._notify("Nao foi possivel salvar os favoritos")
            return
        self.fav_names = novos
        self._notify("%s %s favorito" % (entry.name,
                                         "removido dos" if entry.name
                                         not in novos else "adicionado aos"))

    # ---------------------------------------------------------
    # energia
    # ---------------------------------------------------------

    def _confirm_power(self, action):
        sh = self.shell
        if sh is None or not hasattr(sh, "confirm"):
            self._notify("Confirmacao indisponivel neste shell")
            return
        label = dict((a[0], a[1]) for a in POWER_ACTIONS).get(action, action)
        msg = POWER_MESSAGES.get(action, "Confirmar?")

        def _ok():
            self._do_power(action)

        try:
            sh.confirm(label, msg, _ok)
        except TypeError:
            try:
                sh.confirm(label, msg)
            except Exception:
                self._notify("Confirmacao indisponivel neste shell")
        except Exception:
            self._notify("Confirmacao indisponivel neste shell")

    def _do_power(self, action):
        sh = self.shell
        if action == "logout":
            for nome in ("logout", "exit_session", "close_session", "quit",
                         "exit"):
                fn = getattr(sh, nome, None) if sh is not None else None
                if callable(fn):
                    try:
                        fn()
                        return True
                    except Exception:
                        break
            self._notify("Encerrar sessao nao esta disponivel neste shell")
            return False
        cmd = POWER_COMMANDS.get(action)
        if not cmd:
            return False
        if self._run_command(cmd):
            return True
        self._notify("Comando %s indisponivel" % cmd)
        return False

    def _run_command(self, cmd):
        sh = self.shell
        if sh is not None and hasattr(sh, "launch"):
            try:
                sh.launch(cmd)
                return True
            except Exception:
                pass
        try:
            import subprocess
            subprocess.Popen([cmd])
            return True
        except Exception:
            return False

    # ---------------------------------------------------------
    # teclado na tela
    # ---------------------------------------------------------

    def _open_keyboard(self):
        sh = self.shell
        if sh is None:
            return False
        for nome in KEYBOARD_METHODS:
            fn = getattr(sh, nome, None)
            if callable(fn):
                try:
                    fn()
                    return True
                except Exception:
                    continue
        return False

    # ---------------------------------------------------------
    # avisos
    # ---------------------------------------------------------

    def _notify(self, msg):
        sh = self.shell
        if sh is not None and hasattr(sh, "notify"):
            try:
                sh.notify(msg)
                return True
            except Exception:
                pass
        return False


# --------------------------------------------------------------------
# integracao com a barra de tarefas
# --------------------------------------------------------------------

def toggle_start(shell):
    """Abre/fecha o menu Iniciar a partir do botao "NURA" da barra.

    Se o shell ja sabe fazer isso (``shell.toggle_start``), delegamos.
    Caso contrario procuramos uma janela do Start aberta; se nao houver,
    criamos e abrimos uma nova.
    """
    if shell is None:
        return None
    fn = getattr(shell, "toggle_start", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            pass

    janelas = getattr(shell, "windows", None) or []
    for w in janelas:
        app = getattr(w, "app", None)
        if isinstance(app, StartApp):
            app.close()
            return app

    app = StartApp(shell=shell)
    opener = getattr(shell, "open_app", None)
    if callable(opener):
        try:
            opener(app)
        except Exception:
            return app
    return app


def open_start(shell):
    """Abre o menu Iniciar (sem alternar)."""
    if shell is None:
        return None
    fn = getattr(shell, "open_start", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            pass
    app = StartApp(shell=shell)
    opener = getattr(shell, "open_app", None)
    if callable(opener):
        try:
            opener(app)
        except Exception:
            pass
    return app


if __name__ == "__main__":
    print("NURA OS — NURA Start")
    for e in A.catalog():
        print("  %-32s %s" % (e.name, e.app_key or e.exec_cmd or ""))
