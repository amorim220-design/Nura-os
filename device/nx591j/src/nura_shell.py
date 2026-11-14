#!/usr/bin/env python3
"""NURA OS — NURA Shell (o desktop).

Compositor/DE nativo: desenha em 1920x1080 sobre cairo e apresenta
rotacionado no painel retrato do NX591J (rotacao por software).

Elementos:
  * area de trabalho com icones (coluna esquerda)
  * widgets: relogio+data (canto superior direito) e monitor de
    sistema (CPU / RAM / armazenamento) logo abaixo
  * barra de tarefas: Iniciar, busca, aplicativos fixados, indicadores
    (Bluetooth / Wi-Fi / bateria / volume) e relogio
  * janelas moveis e redimensionaveis (NURA Terminal, Explorer, ...)
  * menu Iniciar (NURA Start)

Sem X11, sem Wayland, sem mesa, sem GPU. Somente cairo + evdev.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cairo  # noqa: E402

import nura_theme as T  # noqa: E402
from nura_fb import Framebuffer  # noqa: E402
from nura_input import GestureDetector, InputReader, TouchEvent  # noqa: E402
from nura_ui import Painter, draw_wallpaper, draw_logo_text  # noqa: E402
from nura_window import App, Window  # noqa: E402

DESK_W, DESK_H = 1920, 1080

# --- import tolerante: os componentes podem ainda nao existir -------
try:
    import nura_sysinfo
except ImportError:
    nura_sysinfo = None
try:
    import nura_recovery
except ImportError:
    nura_recovery = None
try:
    from nura_start import StartApp
except ImportError:
    StartApp = None
try:
    from nura_keyboard import Keyboard
except ImportError:
    Keyboard = None


class NuraShell(object):
    def __init__(self, fb=None, mock=None, theme="neon", ui_scale=1.0,
                 input_device=None):
        self.fb = fb or Framebuffer(mock=mock)
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, DESK_W, DESK_H)
        self.ctx = cairo.Context(self.surface)
        self.theme = T.Theme(theme, ui_scale)
        self.painter = Painter(self.ctx, self.theme)
        self.t0 = time.time()
        self.last_frame = time.time()
        self.frames = 0
        self.fps = 0.0
        self.dirty = True

        # --- entrada ---
        self.reader = None
        self.gesture = GestureDetector()
        if input_device is None:
            try:
                from nura_input import find_touch_device
                input_device = find_touch_device()
            except Exception:
                input_device = None
        if input_device and os.path.exists(input_device):
            try:
                self.reader = InputReader(input_device).open()
                print("[nura] touchscreen: %s" % input_device)
            except Exception as e:
                print("[nura] falha ao abrir %s: %s" % (input_device, e))

        # --- apps ---
        self.windows = []
        self.focus = None
        self.start_open = False
        self.start_app = None
        self.start_window = None
        self.sysinfo = None
        if nura_sysinfo is not None:
            try:
                self.sysinfo = nura_sysinfo.SysInfo()
            except Exception:
                self.sysinfo = None
        self.filemgr = None
        try:
            import nura_filemgr
            self.filemgr = nura_filemgr.FileManager()
        except Exception:
            self.filemgr = None

        self._monitor_at = 0.0
        self.monitor = {}
        self.notices = []          # mensagens temporarias
        self.pressed = {}          # botoes pressionados
        self.bg_surface = None     # cache do papel de parede + logo

        # --- teclado virtual nativo ---
        self.keyboard = None
        if Keyboard is not None:
            try:
                self.keyboard = Keyboard(shell=self)
            except Exception:
                self.keyboard = None
        self.key_focus = None      # app que esta receiving keys

        self.desktop_icons = [
            ("Computador", "monitor", "explorer"),
            ("Arquivos", "folder", "explorer"),
            ("Navegador", "globe", None),
            ("Terminal", "terminal", "terminal"),
            ("Loja de Apps", "store", None),
            ("Configuracoes", "gear", "control"),
            ("Jogos", "gamepad", "games"),
        ]
        self.pinned = ["explorer", "terminal", "control", "performance",
                       "games"]
        self.selected_icon = 1

    # ==================================================================
    # API para os aplicativos
    # ==================================================================

    def open_app(self, app, **kw):
        """Abre um aplicativo (instancia de App) em uma janela."""
        if isinstance(app, str):
            app = self.make_app(app)
            if app is None:
                return None
        win = Window(app, x=180 + 40 * (len(self.windows) % 5),
                     y=90 + 28 * (len(self.windows) % 5), shell=self)
        self.windows.append(win)
        self.focus_window(win)
        try:
            app.on_open()
        except Exception as e:
            self.notify("erro ao abrir %s: %s" % (getattr(app, "title", "app"),
                                                  e), "err")
        self.dirty = True
        return win

    def make_app(self, key):
        """Instancia um app interno pelo identificador."""
        table = {
            "explorer": ("nura_explorer", "ExplorerApp"),
            "terminal": ("nura_terminal", "TerminalApp"),
            "control": ("nura_controlcenter", "ControlCenterApp"),
            "performance": ("nura_performance", "PerformanceApp"),
            "games": ("nura_gamehub", "GameHub"),
            "start": ("nura_start", "StartApp"),
        }
        if key not in table:
            self.notify("aplicativo desconhecido: %s" % key, "err")
            return None
        mod_name, cls_name = table[key]
        try:
            mod = __import__(mod_name)
            cls = getattr(mod, cls_name)
            return cls(shell=self)
        except Exception as e:
            self.notify("NURA %s indisponivel (%s)" % (key, e), "warn")
            return None

    def close_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
        if self.key_focus is win.app:
            self.set_key_focus(None)
        if self.focus is win:
            self.focus = self.windows[-1] if self.windows else None
        try:
            win.app.on_close()
        except Exception:
            pass
        self.dirty = True

    def focus_window(self, win):
        if win in self.windows:
            if self.key_focus is not None and self.key_focus is not win.app:
                self.set_key_focus(None)
            self.windows.remove(win)
            self.windows.append(win)
            self.focus = win
        self.dirty = True

    def notify(self, msg, kind="info", ttl=4.0):
        self.notices.append({"msg": msg, "kind": kind, "t": time.time()})
        self.dirty = True

    def confirm(self, title, message, on_ok=None):
        """Dialogo de confirmacao (retorna True se o usuario aceitou)."""
        self.confirm_dialog = {"title": title, "msg": message, "on_ok": on_ok}
        self.dirty = True
        return False

    def set_fullscreen(self, on):
        self.fullscreen = bool(on)
        self.dirty = True

    # ---------------- teclado virtual ----------------

    @property
    def keyboard_text(self):
        """Texto digitado no teclado virtual (usado pelo NURA Start)."""
        return self.keyboard.text if self.keyboard else ""

    def open_keyboard(self):
        if self.keyboard is not None:
            self.keyboard.show()
        self.dirty = True

    def show_keyboard(self):
        self.open_keyboard()

    def close_keyboard(self):
        if self.keyboard is not None:
            self.keyboard.hide()
        self.dirty = True

    def toggle_keyboard(self):
        if self.keyboard is not None:
            self.keyboard.toggle()
        self.dirty = True

    def on_key(self, key):
        """Entrega uma tecla ao app em foco (ou ao teclado virtual).

        `key` pode ser uma string ("a", "Return", "BackSpace") ou um
        objeto com .key/.text/.ctrl/.alt/.shift.
        """
        if isinstance(key, str):
            key = _SimpleKey(key)
        if self.key_focus is not None:
            try:
                self.key_focus.on_key(key)
                self.dirty = True
                return
            except Exception as e:
                self.notify("erro no teclado: %s" % e, "err")
        if self.focus is not None:
            try:
                self.focus.on_key(key)
                self.dirty = True
            except Exception as e:
                self.notify("erro no teclado: %s" % e, "err")
        else:
            self.open_keyboard()

    def set_key_focus(self, app):
        """Define qual app recebe as teclas do teclado virtual."""
        self.key_focus = app
        if app is not None:
            self.open_keyboard()
        else:
            self.close_keyboard()
        self.dirty = True

    def clamp_window(self, x, y, w, h):
        x = max(-w + 120, min(DESK_W - 120, x))
        y = max(0, min(DESK_H - self.theme.taskbar_h - h, y))
        return x, y

    def launch(self, cmd):
        """Executa um comando real (usado pelo Start e pelo Game Hub)."""
        try:
            import subprocess
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            self.notify("executado: %s" % cmd)
            return True
        except Exception as e:
            self.notify("falha ao executar: %s" % e, "err")
            return False

    # ==================================================================
    # desenho
    # ==================================================================

    def render(self):
        p = self.painter
        th = self.theme
        c = self.ctx
        c.set_operator(cairo.OPERATOR_SOURCE)
        c.set_source_rgba(th.bg[0], th.bg[1], th.bg[2], 1.0)
        c.paint()
        c.set_operator(cairo.OPERATOR_OVER)

        # fundo (papel de parede + logo) vem de um cache: redesenhar os
        # brilhos a cada quadro custaria ~50 ms
        self.paint_background(p)
        self.draw_desktop_icons(p)
        self.draw_clock_widget(p)
        self.draw_monitor_widget(p)
        self.draw_windows(p)
        self.draw_taskbar(p)
        if self.start_open:
            self.draw_start_menu(p)
        if self.keyboard is not None:
            self.keyboard.draw(p)
        self.draw_notices(p)
        self.draw_confirm(p)
        self.surface.flush()

    def paint_background(self, p):
        """Faz o cache do fundo e o pinta."""
        if self.bg_surface is None:
            self.bg_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                                 DESK_W, DESK_H)
            bc = cairo.Context(self.bg_surface)
            bp = Painter(bc, self.theme)
            draw_wallpaper(bp, DESK_W, DESK_H, 0.0)
            self.draw_logo_center(bp)
            self.bg_surface.flush()
        c = self.ctx
        c.set_operator(cairo.OPERATOR_OVER)
        c.set_source_surface(self.bg_surface, 0, 0)
        c.paint()

    def draw_logo_center(self, p):
        """Logo NURA OS no centro da area de trabalho."""
        th = self.theme
        cx = DESK_W * 0.50
        cy = DESK_H * 0.46
        size = int(DESK_H * 0.082)
        # triangulo grande atras do texto
        s = DESK_H * 0.255
        tri = [(cx, cy - s), (cx + s * 0.92, cy + s * 0.66),
               (cx - s * 0.92, cy + s * 0.66)]
        if th.glow:
            for i in range(12, 0, -1):
                p.poly(tri, th.accent, 0.030, filled=False, width=i * 2.8)
        p.poly(tri, th.accent, 0.55, filled=False, width=3.0)
        draw_logo_text(p, cx, cy + s * 0.40, size, "NURA OS")

    def draw_desktop_icons(self, p):
        th = self.theme
        x = 46
        y = 26
        for i, (name, icon, action) in enumerate(self.desktop_icons):
            cy = y + th.icon * 0.42
            sel = (i == self.selected_icon)
            if sel:
                p.round(x - 12, y - 6, th.icon + 30, th.icon + 22, th.radius,
                        th.accent, 0.16)
            p.app_icon(icon, x + th.icon * 0.42, cy, int(th.icon * 0.72))
            p.text(name, x + th.icon * 0.42, y + th.icon + 16, th.font_small,
                   th.text if sel else th.dim, align="center")
            y += th.icon + 44

    def draw_clock_widget(self, p):
        """Relogio + data (canto superior direito)."""
        th = self.theme
        w, h = 420, 128
        x = DESK_W - w - 30
        y = 24
        p.panel(x, y, w, h, th.panel, 0.86, r=th.radius + 4, border=True)
        tm = time.localtime()
        hh = "%02d" % tm.tm_hour
        mm = "%02d" % tm.tm_min
        p.text(hh + ":" + mm, x + 28, y + 62, 52, th.text, "bold")
        dias = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado",
                "domingo"]
        meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set",
                 "out", "nov", "dez"]
        data = "%s, %d de %s" % (dias[tm.tm_wday][:3].capitalize(), tm.tm_mday,
                                 meses[tm.tm_mon - 1])
        p.text(data, x + 30, y + 98, th.font, th.dim)
        # coluna direita: bateria/temperatura REAIS (quando existirem)
        bx = x + w - 150
        bat = self._battery()
        if bat is not None:
            pct = bat.get("capacity")
            p.round(bx, y + 22, 44, 22, 4, th.text, 0.95, filled=False,
                    width=2)
            p.rect(bx + 45, y + 29, 4, 9, th.text, 0.95)
            if pct is not None:
                p.rect(bx + 3, y + 25, 38 * pct / 100.0, 16, th.ok, 0.95)
            p.text("%d%%" % pct if pct is not None else "--", bx, y + 74,
                   th.font_small, th.text)
        sensor = self.monitor.get("temperature")
        p.icon("temp", bx + 4, y + 98, 18, th.accent)
        label = "%.1f °C (%s)" % (sensor["temp_c"], sensor["type"] or
                                 sensor["zone"]) if sensor else "Indisponível"
        p.text(label, x + w - 16, y + 104, th.font_small, th.dim, align="right")

    def draw_monitor_widget(self, p):
        """Monitor de sistema (CPU / RAM / armazenamento) — dados REAIS."""
        if not self.monitor:
            return
        th = self.theme
        w, h = 420, 176
        x = DESK_W - w - 30
        y = 24 + 128 + 16
        p.panel(x, y, w, h, th.panel, 0.86, r=th.radius + 4, border=True)
        rows = [
            ("CPU", self.monitor.get("cpu_pct"), self.monitor.get("cpu_txt"),
             th.accent),
            ("RAM", self.monitor.get("ram_pct"), self.monitor.get("ram_txt"),
             th.accent),
            ("Armazenamento", self.monitor.get("disk_pct"),
             self.monitor.get("disk_txt"), th.accent2),
        ]
        ry = y + 34
        for (name, pct, txt, col) in rows:
            p.text(name, x + 24, ry, th.font, th.text)
            p.text(txt or "—", x + w - 24, ry, th.font, th.dim, align="right")
            p.progress(x + 24, ry + 12, w - 48, 10,
                       pct if pct is not None else 0.0, col,
                       th.panel_hi)
            ry += 52

    def draw_windows(self, p):
        for win in self.windows:
            win.draw(p)

    def draw_taskbar(self, p):
        th = self.theme
        c = p.ctx
        h = th.taskbar_h
        y = DESK_H - h
        # fundo translucido
        c.set_source_rgba(th.panel[0], th.panel[1], th.panel[2], 0.92)
        c.rectangle(0, y, DESK_W, h)
        c.fill()
        c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.35)
        c.set_line_width(1.0)
        c.move_to(0, y + 0.5)
        c.line_to(DESK_W, y + 0.5)
        c.stroke()

        # --- botao Iniciar (4 quadrados) ---
        bx, by, bs = 18, y + (h - 38) // 2, 38
        pressed = self.pressed.get("start")
        p.round(bx, by, bs, bs, 9, th.accent,
                0.40 if pressed else (0.26 if self.start_open else 0.20))
        q = bs / 2.0 - 4
        gx, gy = bx + 7, by + 7
        for i in range(2):
            for j in range(2):
                p.rect(gx + j * (q + 3), gy + i * (q + 3), q, q, th.text, 0.95)
        p.text("NURA OS", bx + bs + 16, y + h / 2 + th.font * 0.38, th.font_title,
               th.text, "bold")

        # --- busca ---
        sx = bx + bs + 150
        sw = 210
        p.round(sx, y + (h - 38) // 2, sw, 38, 19, th.panel_hi, 0.75)
        p.icon("search", sx + 24, y + h / 2, 20, th.dim)
        p.text("Pesquisar", sx + 44, y + h / 2 + 6, th.font, th.dim)

        # --- aplicativos fixados ---
        px = sx + sw + 26
        for key in self.pinned:
            self.draw_pinned_icon(p, key, px + 26, y + h / 2, 34)
            px += 62

        # --- indicadores (reais) ---
        ix = DESK_W - 300
        if self._has_bluetooth():
            p.icon("bluetooth", ix, y + h / 2, 22, th.accent)
            ix += 34
        if self._has_wifi():
            p.icon("wifi", ix, y + h / 2, 22, th.accent)
            ix += 34
        bat = self._battery()
        if bat is not None:
            pct = bat.get("capacity")
            col = th.ok if (pct is None or pct > 20) else th.err
            p.round(ix, y + h / 2 - 10, 34, 19, 4, th.text, 0.95, filled=False,
                    width=2)
            p.rect(ix + 35, y + h / 2 - 4, 4, 8, th.text, 0.95)
            if pct is not None:
                p.rect(ix + 3, y + h / 2 - 7, 28 * pct / 100.0, 13, col, 0.95)
            p.text("%d%%" % pct if pct is not None else "--", ix + 48,
                   y + h / 2 + 6, th.font_small, th.text)
            ix += 100
        if self._has_audio():
            p.icon("volume", ix, y + h / 2, 22, th.text)
            ix += 34

        # --- relogio ---
        tm = time.localtime()
        p.text("%02d:%02d" % (tm.tm_hour, tm.tm_min), DESK_W - 58,
               y + h / 2 + th.font * 0.38, th.font_title, th.text, "bold",
               align="center")

    def pinned_icon(self, key):
        return {"explorer": "folder", "terminal": "terminal",
                "control": "cpu", "performance": "ram",
                "games": "gamepad"}.get(key, "grid")

    def draw_pinned_icon(self, p, key, cx, cy, size):
        """Icone do item fixado: colorido (app) ou vetorial (sistema)."""
        th = self.theme
        icon = self.pinned_icon(key)
        if icon in ("folder", "terminal", "gamepad", "monitor", "globe",
                    "store", "gear"):
            p.app_icon(icon, cx, cy, size)
        else:
            p.icon(icon, cx, cy, size, th.accent)

    def draw_start_menu(self, p):
        """Menu Iniciar (delegado ao NURA Start quando disponivel)."""
        if self.start_window is not None:
            # se a janela do Start ja esta na pilha, ela foi desenhada
            # por draw_windows() — nao desenhar de novo
            if self.start_window not in self.windows:
                self.start_window.draw(p)
            return
        th = self.theme
        w, h = 620, 660
        x, y = 150, DESK_H - th.taskbar_h - h - 18
        p.panel(x, y, w, h, th.panel, 0.97, r=14)
        p.text("NURA OS", x + 28, y + 52, 30, th.accent, "bold")
        p.text(self.theme.name, x + 28, y + 80, th.font_small, th.dim)
        p.rect(x + 28, y + 100, w - 56, 1, th.accent, 0.18)
        rows = [("Terminal", "terminal"), ("Arquivos", "folder"),
                ("Configuracoes", "gear"), ("Performance", "ram"),
                ("Game Hub", "gamepad")]
        ry = y + 146
        for (name, icon) in rows:
            p.round(x + 22, ry - 26, w - 44, 50, 8, th.panel_hi, 0.55)
            p.app_icon(icon, x + 50, ry - 1, 30)
            p.text(name, x + 78, ry + 7, th.font + 3, th.text)
            ry += 60
        ry += 10
        for (name, icon) in (("Desligar", "power"), ("Reiniciar", "refresh")):
            p.round(x + 22, ry - 26, w - 44, 50, 8, th.panel_hi, 0.4)
            p.icon(icon, x + 50, ry - 1, 26, th.warn)
            p.text(name, x + 78, ry + 7, th.font + 3, th.text)
            ry += 58

    def draw_notices(self, p):
        th = self.theme
        now = time.time()
        self.notices = [n for n in self.notices if now - n["t"] < 4.0]
        y = DESK_H - th.taskbar_h - 20
        for n in self.notices:
            w = p.tw(n["msg"], th.font) + 40
            col = {"err": th.err, "warn": th.warn}.get(n["kind"], th.accent)
            p.panel(DESK_W - w - 24, y - 34, w, 42, th.panel, 0.96, r=10)
            p.rect(DESK_W - w - 24, y - 34, 4, 42, col, 0.95)
            p.text(n["msg"], DESK_W - w - 6, y - 7, th.font, th.text)
            y -= 50

    def draw_confirm(self, p):
        dlg = getattr(self, "confirm_dialog", None)
        if not dlg:
            return
        th = self.theme
        w, h = 620, 240
        x = (DESK_W - w) // 2
        y = (DESK_H - h) // 2
        p.round(0, 0, DESK_W, DESK_H, 0, (0, 0, 0), 0.55)
        p.panel(x, y, w, h, th.panel, 0.98, r=14)
        p.text(dlg["title"], x + 28, y + 48, th.font_title, th.accent, "bold")
        p.text(dlg["msg"], x + 28, y + 92, th.font, th.text)
        bw, bh = 160, 48
        by = y + h - bh - 24
        self.confirm_rects = {
            "ok": (x + w - bw * 2 - 48, by, bw, bh),
            "cancel": (x + w - bw - 24, by, bw, bh),
        }
        p.round(self.confirm_rects["ok"][0], by, bw, bh, th.radius,
                th.accent, 0.85)
        p.text("Confirmar", self.confirm_rects["ok"][0] + bw / 2,
               by + bh / 2 + 6, th.font, (0.02, 0.03, 0.05), "bold",
               align="center")
        p.round(self.confirm_rects["cancel"][0], by, bw, bh, th.radius,
                th.panel_hi, 0.9)
        p.text("Cancelar", self.confirm_rects["cancel"][0] + bw / 2,
               by + bh / 2 + 6, th.font, th.text, align="center")

    # ==================================================================
    # dados reais (usados nos widgets)
    # ==================================================================

    def _battery(self):
        if self.sysinfo is not None:
            try:
                return self.sysinfo.battery()
            except Exception:
                return None
        try:
            base = "/sys/class/power_supply"
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if not os.path.exists(os.path.join(p, "type")):
                    continue
                if open(os.path.join(p, "type")).read().strip() != "Battery":
                    continue
                out = {"name": d}
                try:
                    out["capacity"] = int(
                        open(os.path.join(p, "capacity")).read().strip())
                except Exception:
                    out["capacity"] = None
                try:
                    out["status"] = open(os.path.join(p, "status")).read().strip()
                except Exception:
                    out["status"] = None
                return out
        except Exception:
            pass
        return None

    def _temperature(self):
        if self.sysinfo is not None:
            try:
                zones = self.sysinfo.thermal_zones()
                return next((zone for zone in zones
                             if zone.get("temp_c") is not None), None)
            except Exception:
                pass
        return None

    def _has_wifi(self):
        return os.path.exists("/sys/class/net/wlan0")

    def _has_bluetooth(self):
        d = "/sys/class/bluetooth"
        if os.path.isdir(d):
            try:
                return any(n.startswith("hci") for n in os.listdir(d))
            except Exception:
                return False
        return False

    def _has_audio(self):
        return os.path.isdir("/proc/asound")

    def update_monitor(self):
        """Atualiza os dados do widget de monitor (a cada 2 s)."""
        if self.sysinfo is None:
            return
        m = {"temperature": self._temperature()}
        try:
            usage = self.sysinfo.cpu_usage()
            total = usage.get("total") if usage else None
            if total is not None:
                m["cpu_pct"] = total
                m["cpu_txt"] = "%d%%" % round(total * 100)
            else:
                m["cpu_pct"] = None
                m["cpu_txt"] = None
        except Exception:
            m["cpu_pct"] = None
            m["cpu_txt"] = None
        try:
            ram = self.sysinfo.ram_info()
            if ram:
                pct = ram.get("used_pct")
                m["ram_pct"] = pct / 100 if pct is not None else None
                m["ram_txt"] = "%s / %s" % (
                    _fmt_kb(ram.get("used_kb")), _fmt_kb(ram.get("total_kb")))
        except Exception:
            m["ram_pct"] = None
        try:
            st = self.sysinfo.storage_info("/")
            if st:
                pct = st.get("used_pct")
                m["disk_pct"] = pct / 100 if pct is not None else None
                m["disk_txt"] = "%s / %s" % (_fmt_bytes(st.get("used")),
                                             _fmt_bytes(st.get("total")))
        except Exception:
            m["disk_pct"] = None
        self.monitor = m
        self.dirty = True

    # ==================================================================
    # interacao
    # ==================================================================

    def on_touch(self, ev):
        """Roteia o evento de toque."""
        # 0) teclado virtual (esta por cima de tudo)
        if self.keyboard is not None and self.keyboard.visible:
            if self.keyboard.on_touch(ev):
                self.dirty = True
                return

        # 1) dialogo de confirmacao tem prioridade
        dlg = getattr(self, "confirm_dialog", None)
        if dlg:
            rects = getattr(self, "confirm_rects", {})
            if ev.type == "tap":
                for key, (x, y, w, h) in rects.items():
                    if x <= ev.x <= x + w and y <= ev.y <= y + h:
                        cb = dlg.get("on_ok")
                        self.confirm_dialog = None
                        self.dirty = True
                        if key == "ok" and cb:
                            try:
                                cb()
                            except Exception as e:
                                self.notify("falha: %s" % e, "err")
                        return
            return

        # 2) barra de tarefas
        if self._taskbar_touch(ev):
            return

        # 3) janelas (de cima para baixo)
        for win in reversed(self.windows):
            if win.contains(ev.x, ev.y) or win.dragging or win.resizing:
                consumido = False
                try:
                    consumido = bool(win.on_touch(ev))
                except Exception as e:
                    # um app com defeito nao pode derrubar o desktop
                    self.notify("erro em %s: %s" %
                                (getattr(win.app, "title", "app"), e), "err")
                if consumido:
                    self.focus_window(win)
                    self.dirty = True
                    return
                break

        # 4) menu Iniciar (se aberto e fora dele -> fecha)
        if self.start_open and self.start_window is not None:
            if not self.start_window.contains(ev.x, ev.y):
                if ev.type == "tap":
                    self.start_open = False
                    self.dirty = True
                return

        # 5) area de trabalho: icones
        if ev.type == "tap":
            self._desktop_icon_tap(ev.x, ev.y)

    def _taskbar_touch(self, ev):
        th = self.theme
        h = th.taskbar_h
        y = DESK_H - h
        if not (y <= ev.y <= DESK_H):
            return False
        if ev.type == "down":
            if ev.x <= 18 + 38:
                self.pressed["start"] = True
                self.dirty = True
                return True
            sx = 18 + 38 + 150
            if sx <= ev.x <= sx + 210:
                self.pressed["search"] = True
                self.dirty = True
                return True
            px = sx + 210 + 26
            for key in self.pinned:
                if px <= ev.x <= px + 52:
                    self.pressed["pin:" + key] = True
                    self.dirty = True
                    return True
                px += 62
        elif ev.type == "up":
            for k in list(self.pressed):
                self.pressed.pop(k, None)
            self.dirty = True
        elif ev.type == "tap":
            if ev.x <= 18 + 38:
                self.toggle_start()
                return True
            sx = 18 + 38 + 150
            if sx <= ev.x <= sx + 210:
                self.notify("pesquisa: em breve (use o NURA Start)", "info")
                return True
            px = sx + 210 + 26
            for key in self.pinned:
                if px <= ev.x <= px + 52:
                    self.open_app(key)
                    return True
                px += 62
        return False

    def toggle_start(self):
        self.start_open = not self.start_open
        if self.start_open:
            if self.start_app is None and StartApp is not None:
                try:
                    self.start_app = StartApp(shell=self)
                except Exception as e:
                    self.notify("NURA Start indisponivel: %s" % e, "err")
                    self.start_app = None
            if self.start_app is not None:
                try:
                    self.start_app.on_open()
                except Exception:
                    pass
        self.dirty = True

    def _desktop_icon_tap(self, x, y):
        th = self.theme
        iy = 26
        for i, (name, icon, action) in enumerate(self.desktop_icons):
            h = th.icon + 44
            if iy - 6 <= y <= iy + h - 6 and x <= 46 + th.icon + 30:
                self.selected_icon = i
                if action:
                    self.open_app(action)
                elif icon == "globe":
                    self.notify("navegador nao instalado", "warn")
                elif icon == "store":
                    self.notify("loja de apps nao disponivel", "warn")
                self.dirty = True
                return
            iy += h

    # ==================================================================
    # laco principal
    # ==================================================================

    def tick(self):
        now = time.time()
        dt = now - self.last_frame
        self.last_frame = now
        self.frames += 1
        if self.frames % 20 == 0:
            self.fps = 20.0 / max(dt * 20, 0.001)
        # dados do monitor a cada 2 s
        if now - self._monitor_at > 2.0:
            self._monitor_at = now
            self.update_monitor()
        # relogio muda -> redesenhar
        if int(now * 1) != int((now - dt) * 1):
            self.dirty = True
        if self.notices:
            self.dirty = True
        for win in self.windows:
            try:
                win.on_tick(dt)
            except Exception:
                pass
        if self.reader is not None:
            self._pump_input()
        self.render()
        self.fb.present(self.surface, rotation=90)

    def _pump_input(self):
        raw = self.reader.poll()
        if not raw:
            return
        for ev in raw:
            if ev.type == "up":
                ev = ev
            self._dispatch(ev)
        # toque prolongado (precisa de tick mesmo sem eventos)
        for g in self.gesture.tick(time.time()):
            self._dispatch(g)

    def _dispatch(self, ev):
        gestures = self.gesture.feed(ev)
        for g in gestures:
            self.on_touch(g)
        # Um tap ja representa o ciclo down+up. Reenviar o "up" bruto
        # poderia acionar a mesma tecla duas vezes. Arrastos ainda precisam
        # do "up" bruto para encerrar o movimento da janela.
        if ev.type == "up" and not any(g.type == "tap" for g in gestures):
            self.on_touch(ev)

    def run(self, fps=20, frames=None):
        dt = 1.0 / fps
        n = 0
        while frames is None or n < frames:
            t0 = time.time()
            self.tick()
            n += 1
            rest = dt - (time.time() - t0)
            if rest > 0:
                time.sleep(rest)


class _SimpleKey(object):
    """Tecla minima entregue ao app (compatibilidade com o Terminal)."""

    __slots__ = ("key", "text", "ctrl", "alt", "shift")

    def __init__(self, key, text="", ctrl=False, alt=False, shift=False):
        self.key = key
        self.text = text
        self.ctrl = ctrl
        self.alt = alt
        self.shift = shift

    def __repr__(self):
        return "<key %s>" % self.key


def _fmt_kb(kb):
    return _fmt_bytes(kb * 1024 if kb is not None else None)


def _fmt_bytes(b):
    if b is None:
        return "--"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024:
            return "%.1f %s" % (b, unit)
        b /= 1024.0
    return "%.1f PiB" % b


class TouchTest(object):
    """Modo de teste de toque: mostra um retículo na posicao do dedo.

    Uso:  python3 nura_shell.py --touch-test
    Serve para conferir, no aparelho real, se a imagem e o toque estao
    alinhados depois da rotacao de 90 graus.
    """

    def __init__(self, shell):
        self.shell = shell
        self.point = None
        self.raw = None
        self.history = []

    def draw(self, p):
        th = p.theme
        if self.point is None:
            p.text("Toque em qualquer ponto da tela para testar o mapeamento",
                   DESK_W / 2, DESK_H / 2, th.font_title, th.text,
                   align="center")
            return
        x, y = self.point
        c = p.ctx
        c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.95)
        c.set_line_width(2.0)
        c.arc(x, y, 26, 0, 6.2831853)
        c.stroke()
        c.move_to(x - 46, y)
        c.line_to(x + 46, y)
        c.move_to(x, y - 46)
        c.line_to(x, y + 46)
        c.stroke()
        p.panel(x + 60, y - 40, 340, 80, th.panel, 0.92, r=8)
        p.text("paisagem: %d, %d" % (x, y), x + 76, y - 12, th.font, th.text)
        p.text("painel:    %d, %d" % self.raw, x + 76, y + 10,
               th.font_small, th.dim)
        p.text("toques:   %d" % len(self.history), x + 76, y + 30,
               th.font_small, th.dim)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    mock = None
    theme = "neon"
    bench = 0
    touch_test = False
    for a in argv:
        if a == "--mock":
            mock = "/tmp/nura-fb.mock"
        elif a == "--touch-test":
            touch_test = True
        elif a.startswith("--theme="):
            theme = a.split("=", 1)[1]
        elif a.startswith("--bench"):
            bench = int(a.split("=")[1]) if "=" in a else 60

    if mock:
        with open(mock, "wb") as f:
            f.truncate(4352 * 1920)

    sh = NuraShell(mock=mock, theme=theme)
    tt = TouchTest(sh) if touch_test else None

    if bench:
        # mede o desempenho real do aparelho
        import resource
        t0 = time.time()
        n = 0
        while time.time() - t0 < bench:
            sh.tick()
            n += 1
        dt = time.time() - t0
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        print("[bench] %d quadros em %.2f s -> %.1f fps" %
              (n, dt, n / dt))
        print("[bench] RAM maxima: %.1f MB" % rss)
        print("[bench] por quadro: %.1f ms" % (dt / n * 1000))
        return 0

    if mock:
        sh.update_monitor()
        sh.tick()
        sh.surface.write_to_png("/tmp/nura-shell.png")
        print("[nura] frame gravado em /tmp/nura-shell.png")
        return 0

    # --- laco principal no aparelho ---
    if tt is not None:
        orig_render = sh.render

        def render_com_teste():
            orig_render()
            tt.draw(sh.painter)
        sh.render = render_com_teste
        orig_touch = sh.on_touch

        def touch_com_teste(ev):
            if ev.type in ("down", "tap"):
                tt.point = (ev.x, ev.y)
                if sh.reader is not None:
                    pass
                tt.history.append((ev.x, ev.y))
            return orig_touch(ev)
        sh.on_touch = touch_com_teste

    sh.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
