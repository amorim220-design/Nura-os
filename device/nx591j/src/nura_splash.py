"""NURA OS — animacao de inicializacao (NURA Splash).

Toca a animacao de boot do NURA (frames PNG extraidos do video de
referencia) diretamente no framebuffer, em paisagem, com a mesma
rotacao de software do desktop.

Se os frames nao estiverem presentes no aparelho, cai num modo
PROCEDURAL (desenhado em cairo, sem nenhum arquivo externo) — o
sistema sempre entra com uma animacao coerente com a identidade.

Nao depende de X11, de GPU, de rede nem de nenhum recurso externo.
"""

import glob
import math
import os
import time

import cairo

import nura_theme as T

DEFAULT_DIRS = [
    "/usr/share/nura/splash",
    "/usr/local/share/nura/splash",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets",
                 "splash"),
]


def find_frame_dir(dirs=None):
    """Acha o diretorio com os frames da animacao."""
    for d in (dirs or DEFAULT_DIRS):
        if not d:
            continue
        d = os.path.abspath(d)
        if os.path.isdir(d):
            found = sorted(glob.glob(os.path.join(d, "*.png")))
            if found:
                return d, found
    return None, []


class Splash(object):
    """Animacao de boot do NURA."""

    def __init__(self, dirs=None, fps=30, loop=True):
        self.dir, self.files = find_frame_dir(dirs)
        self.fps = fps
        self.loop = loop
        self.surface = None
        self.ctx = None
        self.w = 1920
        self.h = 1080
        self._cache = {}
        self._cache_order = []
        self._next_index = 0

    # ------------------------------------------------------------------
    # frames em disco
    # ------------------------------------------------------------------

    def has_frames(self):
        return bool(self.files)

    def frame_count(self):
        return len(self.files)

    def load_frame(self, index):
        """Carrega um frame (com cache LRU de 8 frames)."""
        if not self.files:
            return None
        index %= len(self.files)
        if index in self._cache:
            return self._cache[index]
        try:
            surf = cairo.ImageSurface.create_from_png(self.files[index])
        except Exception:
            return None
        self._cache[index] = surf
        self._cache_order.append(index)
        while len(self._cache_order) > 8:
            old = self._cache_order.pop(0)
            self._cache.pop(old, None)
        return surf

    # ------------------------------------------------------------------
    # superficie
    # ------------------------------------------------------------------

    def surface_for(self, w=1920, h=1080):
        if self.surface is None or self.w != w or self.h != h:
            self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            self.ctx = cairo.Context(self.surface)
            self.w, self.h = w, h
        return self.surface

    def clear(self):
        s = self.surface_for()
        self.ctx.set_operator(cairo.OPERATOR_SOURCE)
        self.ctx.set_source_rgb(0, 0, 0)
        self.ctx.paint()
        self.ctx.set_operator(cairo.OPERATOR_OVER)

    # ------------------------------------------------------------------
    # desenho
    # ------------------------------------------------------------------

    def draw_frame(self, index):
        """Desenha o frame 'index' (do disco) na superficie."""
        surf = self.load_frame(index)
        if surf is None:
            return False
        s = self.surface_for()
        c = self.ctx
        c.set_operator(cairo.OPERATOR_SOURCE)
        c.set_source_rgb(0, 0, 0)
        c.paint()
        c.set_operator(cairo.OPERATOR_OVER)
        # centraliza mantendo proporcao
        sw, sh = surf.get_width(), surf.get_height()
        k = min(self.w / float(sw), self.h / float(sh))
        dw, dh = sw * k, sh * k
        c.set_source_surface(surf, (self.w - dw) / 2.0, (self.h - dh) / 2.0)
        c.paint()
        return True

    def draw_procedural(self, t, theme=None):
        """Animacao vetorial (fallback sem nenhum arquivo).

        Sequencia: flare de luz -> particulas -> anel + triangulo ->
        "NURA OS" aparecendo. Mesma identidade do video de referencia.
        """
        s = self.surface_for()
        c = self.ctx
        w, h = self.w, self.h
        th = theme or T.Theme("neon")
        c.set_operator(cairo.OPERATOR_SOURCE)
        c.set_source_rgb(0, 0, 0)
        c.paint()
        c.set_operator(cairo.OPERATOR_OVER)

        cx, cy = w * 0.5, h * 0.48
        R = h * 0.42

        # --- flare de luz inicial (0 .. 0.45 s) ---
        if t < 0.55:
            k = t / 0.55
            x = w * (0.5 - 0.45 * k)
            c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2],
                              0.75 * (1.0 - abs(k - 0.5) * 1.2))
            c.set_line_width(3.0)
            c.move_to(x - 260, cy)
            c.line_to(x + 260, cy)
            c.stroke()
            for i in range(10, 0, -1):
                c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2],
                                  0.05 * (1.0 - i / 10.0))
                c.set_line_width(i * 5)
                c.move_to(x - 260, cy)
                c.line_to(x + 260, cy)
                c.stroke()

        # --- particulas (a partir de 0.35 s) ---
        if t > 0.35:
            n = 90
            for i in range(n):
                a = (i * 2.399) % 6.2831853
                rad = ((i * 37) % 100) / 100.0
                drift = (t * 0.5 + rad) % 1.0
                ang = a + t * 0.6
                px = cx + math.cos(ang) * R * (0.35 + drift * 0.62)
                py = cy + math.sin(ang) * R * (0.35 + drift * 0.62)
                alpha = 0.35 * (1.0 - drift) * min(1.0, (t - 0.35) * 3)
                c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2],
                                  alpha)
                c.rectangle(px, py, 2.0, 2.0)

        # --- anel + triangulo (a partir de 0.7 s) ---
        if t > 0.7:
            k = min(1.0, (t - 0.7) / 0.9)
            c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.5)
            c.set_line_width(2.0)
            c.arc(cx, cy, R * 0.86, 0, 6.2831853)
            c.stroke()
            c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.22)
            c.set_line_width(1.0)
            c.arc(cx, cy, R * 1.02, 0, 6.2831853)
            c.stroke()
            # arcos girando
            for i in range(3):
                a0 = t * (1.2 + i * 0.4) + i * 2.1
                c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2],
                                  0.55 - i * 0.12)
                c.set_line_width(2.0)
                c.arc(cx, cy, R * (0.92 + i * 0.06), a0, a0 + 1.1)
                c.stroke()

            s2 = R * 0.60 * k
            tri = [(cx, cy - s2), (cx + s2 * 0.90, cy + s2 * 0.62),
                   (cx - s2 * 0.90, cy + s2 * 0.62)]
            for i in range(9, 0, -1):
                c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.04)
                c.set_line_width(i * 2.4)
                c.move_to(tri[0][0], tri[0][1])
                c.line_to(tri[1][0], tri[1][1])
                c.line_to(tri[2][0], tri[2][1])
                c.close_path()
                c.stroke()
            c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.95)
            c.set_line_width(3.0)
            c.move_to(tri[0][0], tri[0][1])
            c.line_to(tri[1][0], tri[1][1])
            c.line_to(tri[2][0], tri[2][1])
            c.close_path()
            c.stroke()

        # --- "NURA OS" (a partir de 1.9 s) ---
        if t > 1.9:
            k = min(1.0, (t - 1.9) / 0.8)
            alpha = k
            size = int(h * 0.115)
            w_nura = T.text_width(c, "NURA", size, "bold")
            w_os = T.text_width(c, " OS", size, "bold")
            x = cx - (w_nura + w_os) / 2.0
            c.set_source_rgba(0.93, 0.95, 0.98, alpha)
            T.text(c, "NURA", x, cy + R * 0.42, size, (0.93, 0.95, 0.98),
                   "bold")
            c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], alpha)
            T.text(c, " OS", x + w_nura, cy + R * 0.42, size, th.accent, "bold")

        # --- barra de progresso (a partir de 1.2 s) ---
        if t > 1.2:
            k = min(1.0, (t - 1.2) / 1.8)
            bw = w * 0.34
            bx = cx - bw / 2.0
            by = h * 0.86
            c.set_source_rgba(1, 1, 1, 0.10)
            c.rectangle(bx, by, bw, 4)
            c.fill()
            c.set_source_rgba(th.accent[0], th.accent[1], th.accent[2], 0.9)
            c.rectangle(bx, by, bw * k, 4)
            c.fill()
        return True

    # ------------------------------------------------------------------
    # execucao
    # ------------------------------------------------------------------

    def play(self, fb, duration=None, frames=None, on_frame=None):
        """Toca a animacao no framebuffer. Devolve o numero de frames."""
        self.surface_for()
        dt = 1.0 / self.fps
        t0 = time.time()
        n = 0
        limit = frames if frames is not None else duration
        while True:
            t = time.time() - t0
            if self.has_frames():
                idx = self._next_index % len(self.files)
                self.draw_frame(idx)
                self._next_index += 1
            else:
                self.draw_procedural(t)
            fb.present(self.surface, rotation=90)
            n += 1
            if on_frame:
                try:
                    on_frame(n, t)
                except Exception:
                    pass
            if limit is not None:
                if isinstance(limit, int) and n >= limit:
                    break
                if duration is not None and t >= duration:
                    break
            else:
                break
            time.sleep(dt)
        return n

    def play_once_procedural(self, fb, duration=3.5):
        """Modo procedural completo (sem frames em disco)."""
        self.surface_for()
        dt = 1.0 / self.fps
        t0 = time.time()
        n = 0
        while True:
            t = time.time() - t0
            self.draw_procedural(t)
            fb.present(self.surface, rotation=90)
            n += 1
            if t >= duration:
                break
            time.sleep(dt)
        return n


def main():
    import argparse
    from nura_fb import Framebuffer

    ap = argparse.ArgumentParser(description="NURA Splash")
    ap.add_argument("--dir", default=None, help="diretorio dos frames")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--info", action="store_true")
    args = ap.parse_args()

    sp = Splash(dirs=[args.dir] if args.dir else None, fps=args.fps)
    if args.info:
        print("frames: %s (%d)" % (sp.dir, sp.frame_count()))
        return
    fb = Framebuffer()
    if sp.has_frames():
        sp.play(fb, duration=args.duration, frames=args.frames)
    else:
        print("[nura-splash] sem frames: usando animacao procedural")
        sp.play_once_procedural(fb, duration=args.duration or 3.5)
    fb.close()


if __name__ == "__main__":
    main()
