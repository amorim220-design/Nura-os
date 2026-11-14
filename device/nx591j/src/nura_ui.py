"""NURA OS — toolkit de interface (widgets, icones, papel de parede).

Tudo desenhado em cairo: nenhum PNG, nenhuma fonte embutida, nenhuma
aceleracao de hardware. Serve tanto para o desktop quanto para as
janelas dos aplicativos.
"""

import math

import cairo

import nura_theme as T


class Painter(object):
    """Envoltou um contexto cairo + o tema ativo."""

    def __init__(self, ctx, theme):
        self.ctx = ctx
        self.theme = theme

    # ---------------- formas basicas ----------------

    def rect(self, x, y, w, h, color=None, alpha=1.0):
        c = self.ctx
        color = color or self.theme.text
        c.set_source_rgba(color[0], color[1], color[2], alpha)
        c.rectangle(x, y, w, h)
        c.fill()

    def round(self, x, y, w, h, r=10, color=None, alpha=1.0, filled=True,
              width=1.0):
        c = self.ctx
        color = color or self.theme.text
        T.rounded_rect(c, x, y, w, h, r)
        c.set_source_rgba(color[0], color[1], color[2], alpha)
        if filled:
            c.fill()
        else:
            c.set_line_width(width)
            c.stroke()

    def line(self, x1, y1, x2, y2, color=None, width=1.0, alpha=1.0):
        c = self.ctx
        color = color or self.theme.text
        c.set_source_rgba(color[0], color[1], color[2], alpha)
        c.set_line_width(width)
        c.move_to(x1, y1)
        c.line_to(x2, y2)
        c.stroke()

    def circle(self, cx, cy, r, color=None, alpha=1.0, filled=True, width=2.0):
        c = self.ctx
        color = color or self.theme.text
        c.set_source_rgba(color[0], color[1], color[2], alpha)
        c.arc(cx, cy, r, 0, 6.2831853)
        if filled:
            c.fill()
        else:
            c.set_line_width(width)
            c.stroke()

    def arc(self, cx, cy, r, a0, a1, color=None, width=2.0, alpha=1.0):
        c = self.ctx
        color = color or self.theme.text
        c.set_source_rgba(color[0], color[1], color[2], alpha)
        c.set_line_width(width)
        c.arc(cx, cy, r, a0, a1)
        c.stroke()

    def poly(self, points, color=None, alpha=1.0, filled=True, width=2.0):
        c = self.ctx
        color = color or self.theme.text
        c.new_sub_path()
        c.move_to(points[0][0], points[0][1])
        for (px, py) in points[1:]:
            c.line_to(px, py)
        c.close_path()
        c.set_source_rgba(color[0], color[1], color[2], alpha)
        if filled:
            c.fill()
        else:
            c.set_line_width(width)
            c.stroke()

    def gradient_v(self, x, y, w, h, top, bottom):
        T.gradient_v(self.ctx, x, y, w, h, top, bottom)

    def gradient_diag(self, x, y, w, h, c0, c1):
        T.gradient_diag(self.ctx, x, y, w, h, c0, c1)

    # ---------------- texto ----------------

    def text(self, s, x, y, size=None, color=None, weight="normal",
             align="left"):
        size = size or self.theme.font
        color = color or self.theme.text
        return T.text(self.ctx, s, x, y, size, color, weight, align)

    def tw(self, s, size=None, weight="normal"):
        size = size or self.theme.font
        return T.text_width(self.ctx, s, size, weight)

    def ts(self, s, size=None, weight="normal"):
        size = size or self.theme.font
        return T.text_size(self.ctx, s, size, weight)

    # ---------------- widgets ----------------

    def panel(self, x, y, w, h, color=None, alpha=0.92, r=None, border=True):
        th = self.theme
        color = color or th.panel
        r = th.radius if r is None else r
        if border and not th.light:
            T.shadow(self.ctx, x, y, w, h, r)
        T.panel(self.ctx, x, y, w, h, color, alpha, r,
                border=th.accent if border else None,
                border_alpha=0.30)

    def button(self, x, y, w, h, label, pressed=False, accent=None,
               size=None, icon=None):
        """Botao de toque. Retorna o retangulo (x,y,w,h)."""
        th = self.theme
        accent = accent or th.accent
        size = size or th.font
        if pressed:
            self.round(x, y, w, h, th.radius, accent, 0.34)
        else:
            self.round(x, y, w, h, th.radius, th.panel_hi, 0.75)
            if not th.light:
                self.round(x, y, w, h, th.radius, accent, 0.55, filled=False,
                           width=1.0)
        tx = x + w / 2
        if icon:
            self.icon(icon, x + 22, y + h / 2, int(h * 0.55), th.text)
            tx = x + 44
            self.text(label, tx, y + h / 2 + size * 0.35, size, th.text)
        else:
            self.text(label, tx, y + h / 2 + size * 0.35, size, th.text,
                      align="center")
        return (x, y, w, h)

    def progress(self, x, y, w, h, frac, color=None, bg=None):
        th = self.theme
        color = color or th.accent
        bg = bg or th.panel_hi
        frac = max(0.0, min(1.0, frac))
        self.round(x, y, w, h, h / 2.0, bg, 0.9)
        if frac > 0:
            self.round(x, y, max(h, w * frac), h, h / 2.0, color, 0.95)

    def scrollbar(self, x, y, w, h, frac, view=1.0):
        """Barra de rolagem vertical. frac = posicao 0..1."""
        th = self.theme
        self.round(x, y, w, h, w / 2.0, th.panel_hi, 0.5)
        th_h = max(24, int(h * view))
        self.round(x, y + int((h - th_h) * frac), w, th_h, w / 2.0,
                   th.accent, 0.8)

    # ---------------- icones ----------------

    def icon(self, name, cx, cy, size, color=None):
        """Desenha um icone vetorial centrado em (cx, cy)."""
        th = self.theme
        color = color or th.text
        s = float(size)
        c = self.ctx
        if name == "search":
            r = s * 0.34
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.arc(cx - s * 0.08, cy - s * 0.08, r, 0, 6.2831853)
            c.stroke()
            c.set_line_width(s * 0.13)
            c.move_to(cx + s * 0.18, cy + s * 0.18)
            c.line_to(cx + s * 0.42, cy + s * 0.42)
            c.stroke()
        elif name == "bluetooth":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx, cy - s * 0.42)
            c.line_to(cx + s * 0.26, cy - s * 0.12)
            c.line_to(cx, cy + s * 0.16)
            c.line_to(cx, cy - s * 0.42)
            c.move_to(cx, cy - s * 0.42)
            c.line_to(cx + s * 0.26, cy - s * 0.12)
            c.line_to(cx, cy + s * 0.42)
            c.line_to(cx - s * 0.26, cy + s * 0.12)
            c.line_to(cx, cy - s * 0.16)
            c.stroke()
        elif name == "wifi":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            for i, rr in enumerate((s * 0.42, s * 0.28, s * 0.14)):
                c.set_line_width(s * 0.09)
                c.arc(cx, cy + s * 0.28, rr, 3.9269908, 5.4977871)
                c.stroke()
            c.arc(cx, cy + s * 0.30, s * 0.05, 0, 6.2831853)
            c.fill()
        elif name == "battery":
            w, h = s * 0.62, s * 0.34
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.06)
            c.rectangle(cx - w / 2, cy - h / 2, w, h)
            c.stroke()
            c.rectangle(cx + w / 2, cy - h * 0.16, s * 0.07, h * 0.32)
            c.fill()
            c.rectangle(cx - w / 2 + s * 0.05, cy - h / 2 + s * 0.05,
                        w * 0.62, h - s * 0.10)
            c.fill()
        elif name == "volume":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            self.poly([(cx - s * 0.36, cy - s * 0.12),
                       (cx - s * 0.16, cy - s * 0.12),
                       (cx + s * 0.04, cy - s * 0.34),
                       (cx + s * 0.04, cy + s * 0.34),
                       (cx - s * 0.16, cy + s * 0.12),
                       (cx - s * 0.36, cy + s * 0.12)], color, 0.95)
            c.set_line_width(s * 0.07)
            for rr in (s * 0.18, s * 0.30):
                c.arc(cx + s * 0.06, cy, rr, -0.9, 0.9)
                c.stroke()
        elif name == "power":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.arc(cx, cy + s * 0.06, s * 0.32, -2.2, -0.94)
            c.stroke()
            c.move_to(cx, cy - s * 0.38)
            c.line_to(cx, cy - s * 0.05)
            c.stroke()
        elif name == "info":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.08)
            c.arc(cx, cy, s * 0.36, 0, 6.2831853)
            c.stroke()
            c.arc(cx, cy - s * 0.16, s * 0.055, 0, 6.2831853)
            c.fill()
            c.set_line_width(s * 0.09)
            c.move_to(cx, cy - s * 0.02)
            c.line_to(cx, cy + s * 0.24)
            c.stroke()
        elif name == "close":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx - s * 0.22, cy - s * 0.22)
            c.line_to(cx + s * 0.22, cy + s * 0.22)
            c.move_to(cx + s * 0.22, cy - s * 0.22)
            c.line_to(cx - s * 0.22, cy + s * 0.22)
            c.stroke()
        elif name == "check":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.12)
            c.move_to(cx - s * 0.26, cy)
            c.line_to(cx - s * 0.06, cy + s * 0.22)
            c.line_to(cx + s * 0.28, cy - s * 0.24)
            c.stroke()
        elif name == "chevron_up":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx - s * 0.22, cy + s * 0.12)
            c.line_to(cx, cy - s * 0.12)
            c.line_to(cx + s * 0.22, cy + s * 0.12)
            c.stroke()
        elif name == "chevron_down":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx - s * 0.22, cy - s * 0.12)
            c.line_to(cx, cy + s * 0.12)
            c.line_to(cx + s * 0.22, cy - s * 0.12)
            c.stroke()
        elif name == "back":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx + s * 0.20, cy - s * 0.22)
            c.line_to(cx - s * 0.16, cy)
            c.line_to(cx + s * 0.20, cy + s * 0.22)
            c.stroke()
        elif name == "forward":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx - s * 0.20, cy - s * 0.22)
            c.line_to(cx + s * 0.16, cy)
            c.line_to(cx - s * 0.20, cy + s * 0.22)
            c.stroke()
        elif name == "up":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.10)
            c.move_to(cx - s * 0.22, cy + s * 0.20)
            c.line_to(cx, cy - s * 0.16)
            c.line_to(cx + s * 0.22, cy + s * 0.20)
            c.stroke()
        elif name == "home":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            self.poly([(cx, cy - s * 0.34), (cx + s * 0.34, cy + s * 0.04),
                       (cx + s * 0.22, cy + s * 0.04),
                       (cx + s * 0.22, cy + s * 0.30),
                       (cx - s * 0.22, cy + s * 0.30),
                       (cx - s * 0.22, cy + s * 0.04),
                       (cx - s * 0.34, cy + s * 0.04)], color, 0.95)
        elif name == "star":
            pts = []
            for i in range(10):
                a = -math.pi / 2 + i * math.pi / 5
                r = s * 0.40 if i % 2 == 0 else s * 0.17
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            self.poly(pts, color, 0.95)
        elif name == "grid":
            for gx in (-1, 1):
                for gy in (-1, 1):
                    self.round(cx + gx * s * 0.17 - s * 0.13,
                               cy + gy * s * 0.17 - s * 0.13,
                               s * 0.26, s * 0.26, s * 0.05, color, 0.95)
        elif name == "refresh":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.09)
            c.arc(cx, cy, s * 0.30, 0.6, 5.2)
            c.stroke()
            self.poly([(cx + s * 0.18, cy - s * 0.34),
                       (cx + s * 0.34, cy - s * 0.06),
                       (cx + s * 0.02, cy - s * 0.04)], color, 0.95)
        elif name == "cpu":
            self.round(cx - s * 0.26, cy - s * 0.26, s * 0.52, s * 0.52,
                       s * 0.08, color, 0.0, filled=False, width=s * 0.07)
            self.round(cx - s * 0.14, cy - s * 0.14, s * 0.28, s * 0.28,
                       s * 0.04, color, 0.95)
            for i in range(3):
                p = -s * 0.18 + i * s * 0.18
                self.line(cx + p, cy - s * 0.40, cx + p, cy - s * 0.26,
                          color, s * 0.06)
                self.line(cx + p, cy + s * 0.26, cx + p, cy + s * 0.40,
                          color, s * 0.06)
                self.line(cx - s * 0.40, cy + p, cx - s * 0.26, cy + p,
                          color, s * 0.06)
                self.line(cx + s * 0.26, cy + p, cx + s * 0.40, cy + p,
                          color, s * 0.06)
        elif name == "ram":
            self.round(cx - s * 0.36, cy - s * 0.16, s * 0.72, s * 0.32,
                       s * 0.04, color, 0.0, filled=False, width=s * 0.07)
            for i in range(4):
                p = cx - s * 0.24 + i * s * 0.16
                self.rect(p, cy + s * 0.16, s * 0.08, s * 0.10, color, 0.95)
        elif name == "disk":
            self.round(cx - s * 0.34, cy - s * 0.24, s * 0.68, s * 0.48,
                       s * 0.06, color, 0.0, filled=False, width=s * 0.07)
            self.circle(cx + s * 0.18, cy, s * 0.06, color, 0.95)
            self.line(cx - s * 0.24, cy + s * 0.12, cx - s * 0.02, cy + s * 0.12,
                      color, s * 0.05)
        elif name == "temp":
            c.set_source_rgba(color[0], color[1], color[2], 0.95)
            c.set_line_width(s * 0.09)
            c.arc(cx, cy + s * 0.16, s * 0.13, 0, 6.2831853)
            c.stroke()
            c.move_to(cx, cy + s * 0.16)
            c.line_to(cx, cy - s * 0.32)
            c.stroke()
            c.arc(cx, cy + s * 0.16, s * 0.07, 0, 6.2831853)
            c.fill()
        else:
            self.circle(cx, cy, s * 0.30, color, 0.6)

    def app_icon(self, name, cx, cy, size):
        """Icones coloridos no estilo da referencia visual do NURA.

        Desenhados vetorialmente (sem PNG), com a mesma linguagem
        visual: monitor, pasta, globo, terminal, loja, engrenagem,
        controle de videogame.
        """
        th = self.theme
        s = float(size)
        c = self.ctx
        if name == "monitor":
            self.round(cx - s * 0.42, cy - s * 0.40, s * 0.84, s * 0.58,
                       s * 0.08, (0.35, 0.62, 0.90), 0.95)
            self.round(cx - s * 0.37, cy - s * 0.35, s * 0.74, s * 0.48,
                       s * 0.05, (0.16, 0.36, 0.66), 0.95)
            self.round(cx - s * 0.36, cy - s * 0.34, s * 0.72, s * 0.20,
                       s * 0.04, (0.45, 0.78, 0.98), 0.95)
            self.rect(cx - s * 0.07, cy + s * 0.18, s * 0.14, s * 0.14,
                      (0.75, 0.78, 0.82), 0.95)
            self.round(cx - s * 0.24, cy + s * 0.30, s * 0.48, s * 0.10,
                       s * 0.04, (0.75, 0.78, 0.82), 0.95)
        elif name == "folder":
            self.round(cx - s * 0.42, cy - s * 0.28, s * 0.36, s * 0.12,
                       s * 0.03, (0.95, 0.66, 0.18), 0.98)
            self.round(cx - s * 0.42, cy - s * 0.20, s * 0.84, s * 0.46,
                       s * 0.06, (0.99, 0.76, 0.27), 0.98)
            self.round(cx - s * 0.38, cy - s * 0.14, s * 0.76, s * 0.34,
                       s * 0.04, (1.0, 0.83, 0.40), 0.98)
        elif name == "globe":
            self.circle(cx, cy, s * 0.42, (0.16, 0.45, 0.85), 0.98)
            self.circle(cx - s * 0.10, cy - s * 0.12, s * 0.26,
                        (0.30, 0.64, 0.95), 0.95)
            c.set_source_rgba(0.85, 0.94, 1.0, 0.85)
            c.set_line_width(s * 0.045)
            c.arc(cx, cy, s * 0.42, 0, 6.2831853)
            c.stroke()
            c.save()
            c.translate(cx, cy)
            c.scale(0.45, 1.0)
            c.arc(0, 0, s * 0.42, 0, 6.2831853)
            c.restore()
            c.stroke()
            c.set_line_width(s * 0.04)
            c.move_to(cx - s * 0.40, cy)
            c.line_to(cx + s * 0.40, cy)
            c.stroke()
        elif name == "terminal":
            self.round(cx - s * 0.42, cy - s * 0.34, s * 0.84, s * 0.60,
                       s * 0.08, (0.09, 0.10, 0.13), 0.98)
            self.round(cx - s * 0.42, cy - s * 0.34, s * 0.84, s * 0.60,
                       s * 0.08, (0.45, 0.85, 1.0), 0.0, filled=False,
                       width=s * 0.05)
            c.set_source_rgba(0.75, 0.95, 1.0, 0.95)
            c.set_line_width(s * 0.055)
            c.move_to(cx - s * 0.30, cy - s * 0.14)
            c.line_to(cx - s * 0.16, cy - s * 0.04)
            c.line_to(cx - s * 0.30, cy + s * 0.06)
            c.stroke()
            c.move_to(cx - s * 0.08, cy + s * 0.08)
            c.line_to(cx + s * 0.16, cy + s * 0.08)
            c.stroke()
        elif name == "store":
            self.round(cx - s * 0.36, cy - s * 0.24, s * 0.72, s * 0.56,
                       s * 0.08, (0.13, 0.55, 0.92), 0.98)
            c.set_source_rgba(0.85, 0.95, 1.0, 0.95)
            c.set_line_width(s * 0.07)
            c.arc(cx, cy - s * 0.24, s * 0.20, 3.1415926, 6.2831853)
            c.stroke()
            self.circle(cx - s * 0.14, cy + s * 0.04, s * 0.05,
                        (1, 1, 1), 0.95)
            self.circle(cx + s * 0.14, cy + s * 0.04, s * 0.05,
                        (1, 1, 1), 0.95)
            c.set_source_rgba(1, 1, 1, 0.9)
            c.set_line_width(s * 0.05)
            c.arc(cx, cy + s * 0.06, s * 0.14, 0.3, 2.84)
            c.stroke()
        elif name == "gear":
            self.circle(cx, cy, s * 0.26, (0.70, 0.73, 0.78), 0.98)
            self.circle(cx, cy, s * 0.11, (0.13, 0.14, 0.17), 0.98)
            for i in range(8):
                a = i * math.pi / 4
                px = cx + math.cos(a) * s * 0.33
                py = cy + math.sin(a) * s * 0.33
                self.round(px - s * 0.07, py - s * 0.07, s * 0.14, s * 0.14,
                           s * 0.03, (0.70, 0.73, 0.78), 0.98)
        elif name == "gamepad":
            self.round(cx - s * 0.44, cy - s * 0.24, s * 0.88, s * 0.46,
                       s * 0.20, (0.58, 0.42, 0.86), 0.98)
            c.set_source_rgba(1, 1, 1, 0.95)
            c.set_line_width(s * 0.06)
            c.move_to(cx - s * 0.24, cy - s * 0.10)
            c.line_to(cx - s * 0.24, cy + s * 0.10)
            c.move_to(cx - s * 0.34, cy)
            c.line_to(cx - s * 0.14, cy)
            c.stroke()
            self.circle(cx + s * 0.18, cy - s * 0.06, s * 0.055,
                        (0.98, 0.45, 0.72), 0.98)
            self.circle(cx + s * 0.28, cy + s * 0.06, s * 0.055,
                        (0.98, 0.45, 0.72), 0.98)
        elif name == "power":
            self.circle(cx, cy, s * 0.40, (0.16, 0.17, 0.20), 0.98)
            self.icon("power", cx, cy, s * 0.72, (0.98, 0.45, 0.42))
        else:
            self.circle(cx, cy, s * 0.36, th.accent, 0.85)


# --------------------------------------------------------------------
# papel de parede
# --------------------------------------------------------------------

def draw_wallpaper(p, w, h, t=0.0):
    """Papel de parede do NURA: triangulo neon, aneis, fascas de luz
    e silhueta de montanhas. Tudo procedural (sem imagem)."""
    th = p.theme
    c = p.ctx
    c.set_operator(cairo.OPERATOR_SOURCE)
    p.gradient_v(0, 0, w, h, (th.bg[0], th.bg[1], th.bg[2], 1.0),
                 (th.bg2[0], th.bg2[1], th.bg2[2], 1.0))
    c.set_operator(cairo.OPERATOR_OVER)

    cx, cy = w * 0.50, h * 0.46
    R = h * 0.46

    # --- aneis concentricos (arcos parciais, estilo radar) ---
    ring_specs = ((R * 0.92, 0.30, 0.55), (R * 0.78, -0.9, 0.4),
                  (R * 0.64, 2.4, 1.3), (R * 1.06, 1.9, 1.0))
    for (r, a0, a1) in ring_specs:
        alpha = 0.22 if th.glow else 0.14
        p.arc(cx, cy, r, a0, a1, th.accent, 2.0, alpha)
        if th.glow:
            p.arc(cx, cy, r, a0, a1, th.accent, 6.0, alpha * 0.22)

    # --- triangulo neon central ---
    s = R * 0.62
    tri = [(cx, cy - s), (cx + s * 0.90, cy + s * 0.62), (cx - s * 0.90,
                                                          cy + s * 0.62)]
    if th.glow:
        for i in range(10, 0, -1):
            p.poly(tri, th.accent, 0.045, filled=False, width=i * 2.6)
    p.poly(tri, th.accent, 0.95, filled=False, width=3.0)
    # reflexo interno (o "A" do logo)
    p.poly([(cx - s * 0.42, cy + s * 0.44), (cx - s * 0.20, cy - s * 0.26),
            (cx + s * 0.02, cy + s * 0.44)], th.accent, 0.35)

    # --- fascas de luz diagonais (cantos) ---
    shards = [
        (w * 0.02, h * 0.16, w * 0.16, h * 0.02, 0.30),
        (w * 0.05, h * 0.52, w * 0.13, h * 0.60, 0.16),
        (w * 0.86, h * 0.02, w * 0.99, h * 0.20, 0.26),
        (w * 0.88, h * 0.34, w * 0.99, h * 0.48, 0.14),
        (w * 0.20, h * 0.93, w * 0.30, h * 0.99, 0.12),
        (w * 0.62, h * 0.95, w * 0.74, h * 0.99, 0.10),
    ]
    for (x1, y1, x2, y2, a) in shards:
        c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], a * 0.30)
        c.set_line_width(26)
        c.move_to(x1, y1)
        c.line_to(x2, y2)
        c.stroke()
        c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], a)
        c.set_line_width(2.0)
        c.move_to(x1, y1)
        c.line_to(x2, y2)
        c.stroke()

    # --- grade de pontos ---
    c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.10)
    for gx in range(0, int(w), 26):
        for gy in range(0, int(h), 26):
            if (gx * 7 + gy * 13) % 5:
                continue
            c.rectangle(gx, gy, 1.6, 1.6)

    # --- montanhas ao pe ---
    base = h * 0.93
    p.poly([(0, h), (0, base - h * 0.06), (w * 0.14, base - h * 0.16),
            (w * 0.27, base - h * 0.02), (w * 0.42, base - h * 0.13),
            (w * 0.56, base), (w * 0.72, base - h * 0.10),
            (w * 0.86, base - h * 0.02), (w, base - h * 0.12), (w, h)],
          th.bg, 0.95)
    p.poly([(0, h), (0, base), (w * 0.18, base - h * 0.05),
            (w * 0.33, base + h * 0.01), (w * 0.5, base - h * 0.04),
            (w * 0.68, base + h * 0.02), (w * 0.84, base - h * 0.03),
            (w, base), (w, h)], (0.0, 0.0, 0.0), 0.55)


def draw_logo_text(p, cx, cy, size, text="NURA OS", alpha=1.0):
    """'NURA' em branco metalico + 'OS' em ciano neon, com o triangulo
    atras — igual a referencia visual."""
    th = p.theme
    c = p.ctx
    w_nura = p.tw("NURA", size, "bold")
    w_os = p.tw(" OS", size, "bold")
    total = w_nura + w_os
    x = cx - total / 2.0
    c.save()
    c.set_operator(cairo.OPERATOR_OVER)
    T.text(c, "NURA", x, cy, size, (0.92, 0.94, 0.98), "bold")
    T.text(c, " OS", x + w_nura, cy, size, th.accent, "bold")
    c.restore()
    return total
