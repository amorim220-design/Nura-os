"""NURA OS — temas e identidade visual.

Quatro temas prontos:
  * "neon"    -> NURA OS — Neon Blue (padrao)
  * "dark"    -> NURA Dark
  * "minimal" -> NURA Minimal (claro)
  * "gamer"   -> NURA Gamer

Nenhum recurso externo: cores, formas, icones e o papel de parede
sao desenhados em cairo. O tema funciona offline, sem GPU.
"""

import cairo

# --------------------------------------------------------------------
# paletas
# --------------------------------------------------------------------
# Cada cor e (r, g, b) em 0..1

PALETTES = {
    "neon": {
        "name": "NURA OS — Neon Blue",
        "bg": (0.020, 0.024, 0.043),
        "bg2": (0.043, 0.071, 0.129),
        "panel": (0.043, 0.055, 0.094),
        "panel_hi": (0.078, 0.098, 0.153),
        "accent": (0.106, 0.855, 0.980),     # ciano neon
        "accent2": (0.118, 0.443, 0.925),    # azul eletrico
        "text": (0.937, 0.965, 0.980),
        "dim": (0.478, 0.510, 0.573),
        "dim2": (0.290, 0.322, 0.388),
        "ok": (0.235, 0.831, 0.541),
        "warn": (0.980, 0.729, 0.239),
        "err": (0.957, 0.400, 0.400),
        "light": False,
        "glow": True,
    },
    "dark": {
        "name": "NURA Dark",
        "bg": (0.070, 0.070, 0.078),
        "bg2": (0.110, 0.110, 0.122),
        "panel": (0.125, 0.125, 0.137),
        "panel_hi": (0.180, 0.180, 0.196),
        "accent": (0.647, 0.678, 0.722),
        "accent2": (0.290, 0.565, 0.851),
        "text": (0.933, 0.933, 0.933),
        "dim": (0.541, 0.541, 0.573),
        "dim2": (0.388, 0.388, 0.416),
        "ok": (0.404, 0.788, 0.451),
        "warn": (0.929, 0.702, 0.290),
        "err": (0.867, 0.388, 0.388),
        "light": False,
        "glow": False,
    },
    "minimal": {
        "name": "NURA Minimal",
        "bg": (0.980, 0.980, 0.984),
        "bg2": (0.937, 0.945, 0.957),
        "panel": (1.000, 1.000, 1.000),
        "panel_hi": (0.898, 0.914, 0.937),
        "accent": (0.169, 0.424, 0.690),
        "accent2": (0.173, 0.478, 0.482),
        "text": (0.102, 0.125, 0.173),
        "dim": (0.443, 0.502, 0.588),
        "dim2": (0.639, 0.686, 0.749),
        "ok": (0.145, 0.545, 0.361),
        "warn": (0.749, 0.451, 0.063),
        "err": (0.741, 0.204, 0.204),
        "light": True,
        "glow": False,
    },
    "gamer": {
        "name": "NURA Gamer",
        "bg": (0.039, 0.035, 0.071),
        "bg2": (0.082, 0.043, 0.145),
        "panel": (0.082, 0.067, 0.122),
        "panel_hi": (0.141, 0.106, 0.196),
        "accent": (1.000, 0.180, 0.533),     # magenta
        "accent2": (0.000, 1.000, 0.612),    # verde neon
        "text": (0.949, 0.949, 0.969),
        "dim": (0.545, 0.498, 0.659),
        "dim2": (0.373, 0.333, 0.475),
        "ok": (0.000, 1.000, 0.612),
        "warn": (1.000, 0.780, 0.000),
        "err": (1.000, 0.231, 0.310),
        "light": False,
        "glow": True,
    },
}

THEME_NAMES = ["neon", "dark", "minimal", "gamer"]


class Theme(object):
    """Paleta ativa + metricas de interface."""

    def __init__(self, name="neon", ui_scale=1.0):
        if name not in PALETTES:
            name = "neon"
        self.key = name
        p = PALETTES[name]
        for k, v in p.items():
            setattr(self, k, v)
        self.name = p["name"]
        self.ui_scale = float(ui_scale)
        self._apply_metrics()

    def _apply_metrics(self):
        s = self.ui_scale
        self.taskbar_h = int(64 * s)
        self.titlebar_h = int(46 * s)
        self.icon = int(72 * s)
        self.radius = int(10 * s)
        self.gap = int(12 * s)
        self.pad = int(14 * s)
        self.font = int(17 * s)
        self.font_small = int(14 * s)
        self.font_title = int(21 * s)
        self.font_huge = int(34 * s)

    def set_scale(self, scale):
        self.ui_scale = float(scale)
        self._apply_metrics()

    def reload(self, name=None):
        if name:
            self.key = name if name in PALETTES else "neon"
        p = PALETTES[self.key]
        for k, v in p.items():
            setattr(self, k, v)
        self.name = p["name"]

    def rgba(self, color, a=1.0):
        return (color[0], color[1], color[2], a)


# --------------------------------------------------------------------
# helpers de desenho (independentes do tema)
# --------------------------------------------------------------------

def _set_stop(g, offset, r, g_, b, a):
    """Compativel com pycairo antigo (set_color_stop_rgba) e novo."""
    if hasattr(g, "add_color_stop_rgba"):
        g.add_color_stop_rgba(offset, r, g_, b, a)
    else:
        g.set_color_stop_rgba(offset, r, g_, b, a)


def gradient_v(ctx, x, y, w, h, top, bottom):
    g = cairo.LinearGradient(x, y, x, y + h)
    ta = top[3] if len(top) > 3 else 1.0
    ba = bottom[3] if len(bottom) > 3 else 1.0
    _set_stop(g, 0, top[0], top[1], top[2], ta)
    _set_stop(g, 1, bottom[0], bottom[1], bottom[2], ba)
    ctx.set_source(g)
    ctx.rectangle(x, y, w, h)
    ctx.fill()


def gradient_diag(ctx, x, y, w, h, c0, c1):
    g = cairo.LinearGradient(x, y, x + w, y + h)
    _set_stop(g, 0, c0[0], c0[1], c0[2], c0[3] if len(c0) > 3 else 1.0)
    _set_stop(g, 1, c1[0], c1[1], c1[2], c1[3] if len(c1) > 3 else 1.0)
    ctx.set_source(g)
    ctx.rectangle(x, y, w, h)
    ctx.fill()


def rounded_rect(ctx, x, y, w, h, r=10):
    """Path de um retangulo com cantos arredondados."""
    r = max(0.0, min(r, w / 2.0, h / 2.0))
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -1.5707963, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, 1.5707963)
    ctx.arc(x + r, y + h - r, r, 1.5707963, 3.1415926)
    ctx.arc(x + r, y + r, r, 3.1415926, 4.7123890)
    ctx.close_path()


def panel(ctx, x, y, w, h, color, alpha=0.92, r=10, border=None,
          border_alpha=0.35, border_w=1.0):
    """Painel translucido com borda opcional."""
    rounded_rect(ctx, x, y, w, h, r)
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.fill()
    if border is not None:
        ctx.set_source_rgba(border[0], border[1], border[2], border_alpha)
        ctx.set_line_width(border_w)
        ctx.stroke()


def shadow(ctx, x, y, w, h, r=10, color=(0, 0, 0), alpha=0.45, spread=6):
    """Sombra difusa (varias passadas)."""
    for i in range(spread, 0, -1):
        rounded_rect(ctx, x - i, y - i + 2, w + 2 * i, h + 2 * i, r + i)
        ctx.set_source_rgba(color[0], color[1], color[2],
                            alpha * (1.0 - i / float(spread)) * 0.35)
        ctx.fill()


def glow(ctx, color, alpha=0.5, width=2.0, spread=8):
    """Prepara o 'glow' neon: varias passadas largas e translucidas."""
    def _draw():
        for i in range(spread, 0, -1):
            ctx.set_source_rgba(color[0], color[1], color[2],
                                alpha * (1.0 - i / float(spread)) * 0.5)
            ctx.set_line_width(width + i * 1.8)
            ctx.stroke()
    return _draw


def text(ctx, s, x, y, size=17, color=(1, 1, 1), weight="normal", align="left",
         family=None):
    """Escreve texto com a fonte sans do cairo (toy API)."""
    ctx.select_font_face(family or "Nura Sans",
                         cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if weight == "bold"
                         else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ctx.set_source_rgb(color[0], color[1], color[2])
    if align == "center":
        x -= ctx.text_extents(s)[4] / 2.0
    elif align == "right":
        x -= ctx.text_extents(s)[4]
    ctx.move_to(x, y)
    ctx.show_text(s)
    return ctx.text_extents(s)[4]


def text_width(ctx, s, size=17, weight="normal", family=None):
    ctx.select_font_face(family or "Nura Sans",
                         cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if weight == "bold"
                         else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    return ctx.text_extents(s)[4]


def text_size(ctx, s, size=17, weight="normal", family=None):
    ctx.select_font_face(family or "Nura Sans",
                         cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if weight == "bold"
                         else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    return (ext[4], ext[3])     # largura, altura


def ellipse_glow(ctx, cx, cy, rx, ry, color, alpha=0.35, width=2.0, spread=10):
    for i in range(spread, 0, -1):
        ctx.save()
        ctx.set_source_rgba(color[0], color[1], color[2],
                            alpha * (1.0 - i / float(spread)) * 0.45)
        ctx.set_line_width(width + i * 2.4)
        ctx.scale(1.0, ry / float(rx))
        ctx.arc(cx, cy, rx, 0, 6.2831853)
        ctx.restore()
        ctx.stroke()
