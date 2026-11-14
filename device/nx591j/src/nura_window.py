"""NURA OS — base de widgets, aplicativos e janelas.

O shell (nura_shell.py) gerencia uma pilha de janelas: foco, ordem,
arrastar e redimensionar. Cada aplicativo e um `App` que desenha
dentro de uma `Window`.

Contrato:

    class MeuApp(App):
        title = "Meu App"
        icon = "terminal"
        width, height = 900, 600

        def on_open(self): ...          # chamado uma vez
        def on_close(self): ...         # chamado ao fechar
        def draw(self, p): ...          # desenha o CONTEUDO da janela
        def on_touch(self, ev): ...     # True = consumido
        def on_key(self, ev): ...       # True = consumido
        def on_tick(self, dt): ...      # chamado a cada quadro

Coordenadas: sempre no espaco paisagem 1920x1080.
"""

from nura_input import TouchEvent
from nura_theme import text as draw_text
from nura_ui import Painter
import nura_theme as T


class Widget(object):
    """Qualquer coisa desenhavel e tocavel."""

    def draw(self, p):
        pass

    def on_touch(self, ev):
        return False

    def on_key(self, ev):
        return False

    def on_tick(self, dt):
        pass


class App(Widget):
    """Aplicativo do NURA."""

    title = "Aplicativo"
    icon = "terminal"
    width = 900
    height = 620
    min_width = 480
    min_height = 320
    resizable = True
    modal = False
    start_hidden = False

    def __init__(self, shell=None, **kw):
        self.shell = shell
        self.ctx_data = kw
        self.window = None
        self._t0 = 0.0

    # ciclo de vida
    def on_open(self):
        pass

    def on_close(self):
        pass

    def on_focus(self, focused):
        pass

    # atalhos que o shell oferece
    def shortcut(self, key):
        return None


class Window(Widget):
    """Janela movevel e redimensionavel, com barra de titulo."""

    def __init__(self, app, x=200, y=120, w=None, h=None, title=None,
                 shell=None):
        self.app = app
        self.shell = shell
        self.x = int(x)
        self.y = int(y)
        self.w = int(w or getattr(app, "width", 900))
        self.h = int(h or getattr(app, "height", 620))
        self.title = title or getattr(app, "title", "Janela")
        self.icon = getattr(app, "icon", "terminal")
        self.resizable = getattr(app, "resizable", True)
        self.dragging = False
        self.resizing = None
        self._drag_off = (0, 0)
        self.min_w = getattr(app, "min_width", 480)
        self.min_h = getattr(app, "min_height", 320)
        app.window = self

    # ---------------------------------------------------------
    # geometria
    # ---------------------------------------------------------
    @property
    def titlebar_h(self):
        if self.shell is not None and self.shell.theme is not None:
            return self.shell.theme.titlebar_h
        return 46

    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def contains(self, x, y):
        return (self.x <= x < self.x + self.w and
                self.y <= y < self.y + self.h)

    def content_rect(self):
        tb = self.titlebar_h
        return (self.x, self.y + tb, self.w, self.h - tb)

    def close_button_rect(self):
        tb = self.titlebar_h
        s = max(44, tb - 18)
        return (self.x + self.w - s - 10, self.y + max(0, (tb - s) // 2), s, s)

    # ---------------------------------------------------------
    # desenho
    # ---------------------------------------------------------
    def draw(self, p):
        th = p.theme
        tb = self.titlebar_h
        # sombra + corpo
        p.panel(self.x, self.y, self.w, self.h, th.panel, 0.97,
                r=th.radius + 2, border=True)
        # barra de titulo
        p.rect(self.x + 1, self.y + 1, self.w - 2, tb - 1, th.panel_hi, 0.85)
        p.line(self.x + 1, self.y + tb, self.x + self.w - 1, self.y + tb,
               th.accent, 1.0, 0.45)
        # icone + titulo
        if self.icon in ("monitor", "folder", "globe", "terminal", "store",
                         "gear", "gamepad", "power"):
            p.app_icon(self.icon, self.x + 26, self.y + tb // 2,
                       int(tb * 0.62))
        else:
            p.icon(self.icon, self.x + 26, self.y + tb // 2, int(tb * 0.55),
                   th.accent)
        draw_text(p.ctx, self.title, self.x + 46,
                  self.y + tb / 2 + th.font * 0.35, th.font, th.text, "bold")
        # botao fechar
        cx, cy, cw, ch = self.close_button_rect()
        p.icon("close", cx + cw / 2, cy + ch / 2, int(cw * 0.55), th.dim)
        # conteudo
        cr = self.content_rect()
        p.ctx.save()
        p.ctx.rectangle(cr[0], cr[1], cr[2], cr[3])
        p.ctx.clip()
        try:
            self.app.draw(p)
        except Exception as e:                # nunca derruba o shell
            p.text("erro ao desenhar: %s" % e, cr[0] + 16, cr[1] + 28,
                   th.font_small, th.err)
        p.ctx.restore()

    # ---------------------------------------------------------
    # interacao
    # ---------------------------------------------------------
    def on_touch(self, ev):
        tb = self.titlebar_h
        cx, cy, cw, ch = self.close_button_rect()
        on_close = cx <= ev.x < cx + cw and cy <= ev.y < cy + ch
        if ev.type == "tap" and on_close:
            if self.shell is not None:
                self.shell.close_window(self)
            return True
        if ev.type == "down":
            if on_close:
                self._close_pressed = True
                return True
            if (self.y <= ev.y < self.y + tb and
                    self.x <= ev.x < self.x + self.w):
                self.dragging = True
                self._drag_off = (ev.x - self.x, ev.y - self.y)
                return True
            if self.resizable:
                m = 18
                if (ev.x > self.x + self.w - m and
                        ev.y > self.y + self.h - m):
                    self.resizing = "se"
                    return True
                if (ev.x > self.x + self.w - m and
                        self.y < ev.y < self.y + tb):
                    self.resizing = "e"
                    return True
                if (ev.y > self.y + self.h - m and
                        self.x < ev.x < self.x + self.w):
                    self.resizing = "s"
                    return True
        elif ev.type == "drag":
            if self.dragging:
                nx = ev.x - self._drag_off[0]
                ny = ev.y - self._drag_off[1]
                if self.shell is not None and hasattr(self.shell, "clamp_window"):
                    nx, ny = self.shell.clamp_window(nx, ny, self.w, self.h)
                self.x, self.y = int(nx), int(ny)
                return True
            if self.resizing:
                dx, dy = ev.dx, ev.dy
                if "e" in self.resizing:
                    self.w = max(self.min_w, self.w + dx)
                if "s" in self.resizing:
                    self.h = max(self.min_h, self.h + dy)
                if "se" in self.resizing:
                    self.w = max(self.min_w, self.w + dx)
                    self.h = max(self.min_h, self.h + dy)
                return True
        elif ev.type == "up":
            if getattr(self, "_close_pressed", False):
                self._close_pressed = False
                if on_close:
                    if self.shell is not None:
                        self.shell.close_window(self)
                    return True
            if self.dragging or self.resizing:
                self.dragging = False
                self.resizing = None
                return True
        return self.app.on_touch(ev)

    def on_key(self, ev):
        return self.app.on_key(ev)

    def on_tick(self, dt):
        self.app.on_tick(dt)
