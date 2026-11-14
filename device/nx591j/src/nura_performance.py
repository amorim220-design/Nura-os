#!/usr/bin/env python3
"""NURA OS — NURA Performance (painel de monitoramento).

Painel de monitoramento em tempo real do NURA OS (Nubia NX591J em
paisagem 1920x1080, tema preto/azul-neon).

Conteudo:
    CPU         uso total (%), historico em grafico de barras (60 amostras),
               frequencia por nucleo e governor
    RAM         total / usado / livre + barra + %
    Disco       storage_info('/') -> total / usado / livre + barra
    Processos   os 20 maiores por RSS (nome, pid, RSS, CPU%)
    Temperatura thermal_zones() (so aparece se existir)
    Bateria     battery() (so aparece se existir)
    GPU         drm_info() (so aparece se houver conector)

REGRAS:
  * NUNCA inventar valor: dado ausente vira "indisponivel"/"—".
  * A coleta roda a cada 2 SEGUNDOS (nao a cada quadro): ler /proc a 60 Hz
    gastaria CPU e bateria do aparelho sem necessidade.
  * O modulo `nura_sysinfo` e opcional. Se faltar, o app abre e mostra
    "modulo de sistema indisponivel" sem quebrar.
"""

import os
import sys
from collections import deque

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import nura_theme as T                        # noqa: E402
from nura_window import App                   # noqa: E402

try:                                         # modulo de metricas (opcional)
    from nura_sysinfo import SysInfo
except ImportError:                          # pragma: no cover
    SysInfo = None


# --------------------------------------------------------------------
# constantes
# --------------------------------------------------------------------

#: intervalo entre duas coletas de metricas (segundos)
REFRESH_INTERVAL = 2.0

#: quantas amostras de CPU ficam no historico (grafico de barras)
HISTORY_SIZE = 60

#: quantos processos sao listados
PROCESS_LIMIT = 20

#: placeholder para valor ausente
MISSING = "\u2014"

#: alvo minimo de toque
MIN_TOUCH = 44

_AUTO = object()


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------

def _human_bytes(n):
    """Formata bytes em KB/MB/GB/TB. '-' quando o valor nao existe."""
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
    try:
        return _human_bytes(float(kb) * 1024.0)
    except (TypeError, ValueError):
        return "-"


def _human_duration(seconds):
    """Formata segundos em '3h 12min'. '-' quando nao existe."""
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


def _percent(value):
    """'42%' ou '—' (nunca 0 falso)."""
    if value is None:
        return MISSING
    try:
        return "%d%%" % int(round(float(value)))
    except (TypeError, ValueError):
        return MISSING


def _freq_list(values):
    """'1400, 1400 MHz' a partir da lista por nucleo (pode ter None)."""
    if not values:
        return MISSING
    parts = []
    for value in values:
        if value is None:
            parts.append(MISSING)
        else:
            try:
                parts.append("%d" % int(round(float(value))))
            except (TypeError, ValueError):
                parts.append(MISSING)
    text = ", ".join(parts)
    return "%s MHz" % text


# --------------------------------------------------------------------
# aplicacao
# --------------------------------------------------------------------

class PerformanceApp(App):
    """NURA Performance (janela de monitoramento)."""

    title = "NURA Performance"
    icon = "ram"
    width = 980
    height = 680
    min_width = 560
    min_height = 420
    resizable = True

    #: intervalo de coleta (s) — documentado e usedo em on_tick()
    refresh_interval = REFRESH_INTERVAL

    def __init__(self, shell=None, sysinfo=_AUTO, **kw):
        App.__init__(self, shell=shell, **kw)
        self.theme = T.Theme("neon")
        self.cpu_history = deque(maxlen=HISTORY_SIZE)
        self.data = {}
        self.sysinfo = None
        self.module_missing = False
        self.update_count = 0
        self._acc = 0.0
        self._sysinfo_request = sysinfo
        self._own_sysinfo = None
        self._refresh_rect = (-1000.0, -1000.0, 140.0, float(MIN_TOUCH))
        self._refresh_pressed = False
        self.refresh()

    # ---------------- ciclo de vida ----------------

    def on_open(self):
        self.refresh()

    def on_close(self):
        pass

    # ---------------- sistema ----------------

    def resolve_sysinfo(self):
        """Instancia do nura_sysinfo (ou None)."""
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
            self._own_sysinfo = cls()
        except Exception:
            self._own_sysinfo = None
        return self._own_sysinfo

    @staticmethod
    def _safe(func, default=None):
        """Chama uma metrica do sysinfo sem deixar excecao passar."""
        try:
            value = func()
        except Exception:
            return default
        return value if value is not None else default

    def refresh(self):
        """Coleta todas as metricas disponiveis (nada e inventado)."""
        si = self.resolve_sysinfo()
        self.sysinfo = si
        self.update_count += 1

        if si is None:
            self.module_missing = True
            self.data = {}
            return self.data
        self.module_missing = False

        data = {
            "cpu_usage": self._safe(lambda: si.cpu_usage()),
            "cpu_freq": self._safe(lambda: si.cpu_freq(), []) or [],
            "cpu_governor": self._safe(lambda: si.cpu_governor(), []) or [],
            "ram": self._safe(lambda: si.ram_info()),
            "storage": self._safe(lambda: si.storage_info("/")),
            "processes": self._safe(lambda: si.processes(limit=PROCESS_LIMIT),
                                    []) or [],
            "thermal": self._safe(lambda: si.thermal_zones(), []) or [],
            "battery": self._safe(lambda: si.battery()),
            "drm": self._safe(lambda: si.drm_info(), []) or [],
            "uptime": self._safe(lambda: si.uptime()),
            "loadavg": self._safe(lambda: si.loadavg()),
            "kernel": self._safe(lambda: si.kernel_info(), {}) or {},
            "os": self._safe(lambda: si.os_info(), {}) or {},
        }
        self.data = data

        usage = data.get("cpu_usage") or {}
        total = usage.get("total")
        if total is not None:
            try:
                self.cpu_history.append(max(0.0, min(1.0, float(total))))
            except (TypeError, ValueError):
                pass
        return data

    def on_tick(self, dt):
        """Coleta periodica: 1 vez a cada `refresh_interval` segundos.

        NAO coleta a cada quadro (60 Hz) — isso gastaria CPU e bateria.
        """
        try:
            step = float(dt)
        except (TypeError, ValueError):
            step = 0.0
        self._acc += step
        if self._acc >= self.refresh_interval:
            # descarta o excedente: um quadro longo nao causa uma rajada
            # de coletas seguidas.
            self._acc = 0.0
            self.refresh()

    # ---------------- geometria ----------------

    def content_rect(self):
        win = self.window
        if win is not None:
            try:
                return win.content_rect()
            except Exception:
                pass
        return (0, 0, self.width, self.height)

    def layout(self):
        """Calcula os retangulos das secoes."""
        th = self.theme
        x, y, w, h = self.content_rect()
        pad = th.pad
        gap = th.gap
        header_h = th.font_title + th.font_small + 14
        top = y + header_h
        avail_w = max(200, w - pad * 2)
        avail_h = max(160, (y + h) - top - pad)
        left_w = int(avail_w * 0.52)
        right_w = avail_w - left_w - gap
        right_x = x + pad + left_w + gap
        bottom = top + avail_h

        cpu_h = 208
        small_h = 86
        left = []
        cy = top
        left.append(("cpu", x + pad, cy, left_w, cpu_h))
        cy += cpu_h + gap
        left.append(("ram", x + pad, cy, left_w, small_h))
        cy += small_h + gap
        left.append(("disk", x + pad, cy, left_w, small_h))
        cy += small_h + gap

        extras = []
        if self.data.get("thermal"):
            extras.append(("thermal",))
        if self.data.get("battery"):
            extras.append(("battery",))
        if self.data.get("drm"):
            extras.append(("gpu",))
        if extras:
            room = bottom - cy
            per = (room - gap * (len(extras) - 1)) / float(len(extras))
            per = max(56.0, min(88.0, per))
            for kind in extras:
                if cy + per > bottom:
                    break
                left.append((kind[0], x + pad, cy, left_w, per))
                cy += per + gap

        right = [("processes", right_x, top, right_w, avail_h)]
        return {"left": left, "right": right, "header": (x, y, w, header_h),
                "top": top, "bottom": bottom}

    # ---------------- desenho ----------------

    def draw(self, p):
        self.theme = p.theme
        th = self.theme
        rect = self.content_rect()
        x, y, w, h = rect

        if self.module_missing:
            self._draw_missing(p, x, y, w, h)
            return

        geo = self.layout()
        hx, hy, hw, hh = geo["header"]
        p.text(self.title, hx + th.pad, hy + th.font_title, th.font_title,
               th.text, "bold")
        p.text("atualizacao automatica a cada %g s" % self.refresh_interval,
               hx + th.pad, hy + th.font_title + th.font_small + 4,
               th.font_small, th.dim2)

        # botao atualizar (>= 44px de altura)
        bw, bh = 140.0, float(MIN_TOUCH)
        bx = hx + hw - th.pad - bw
        by = hy + 2
        self._refresh_rect = (bx, by, bw, bh)
        p.button(bx, by, bw, bh, "Atualizar", pressed=self._refresh_pressed,
                 size=th.font_small, icon="refresh")

        for kind, cx, cy, cw, ch in geo["left"]:
            self._draw_section(p, kind, cx, cy, cw, ch)
        for kind, cx, cy, cw, ch in geo["right"]:
            self._draw_section(p, kind, cx, cy, cw, ch)

    def _draw_missing(self, p, x, y, w, h):
        th = self.theme
        cx = x + w / 2.0
        cy = y + h / 2.0
        p.icon("info", cx, cy - 44, 46, th.warn)
        p.text("modulo de sistema indisponivel", cx, cy + 10, th.font_title,
               th.warn, "bold", align="center")
        p.text("nura_sysinfo nao foi encontrado — sem metricas para exibir",
               cx, cy + 36, th.font_small, th.dim, align="center")

    def _card(self, p, x, y, w, h, title, subtitle=""):
        """Desenha um cartao e devolve a area util (abaixo do titulo)."""
        th = self.theme
        p.panel(x, y, w, h, th.panel, 0.92, r=th.radius, border=True)
        p.text(title, x + th.pad, y + 24, th.font, th.text, "bold")
        if subtitle:
            p.text(subtitle, x + w - th.pad, y + 24, th.font_small, th.dim2,
                   align="right")
        return (x + th.pad, y + 34, w - th.pad * 2, h - 34 - th.pad * 0.6)

    def _draw_section(self, p, kind, x, y, w, h):
        if kind == "cpu":
            self._draw_cpu(p, x, y, w, h)
        elif kind == "ram":
            self._draw_ram(p, x, y, w, h)
        elif kind == "disk":
            self._draw_disk(p, x, y, w, h)
        elif kind == "processes":
            self._draw_processes(p, x, y, w, h)
        elif kind == "thermal":
            self._draw_thermal(p, x, y, w, h)
        elif kind == "battery":
            self._draw_battery(p, x, y, w, h)
        elif kind == "gpu":
            self._draw_gpu(p, x, y, w, h)

    # ---- CPU ----

    def _draw_cpu(self, p, x, y, w, h):
        th = self.theme
        usage = self.data.get("cpu_usage") or {}
        total = usage.get("total")
        per_core = usage.get("per_core") or []

        count = len(self.data.get("cpu_freq") or []) or len(per_core)
        self._card(p, x, y, w, h, "CPU")

        # numero de nucleos (mesma linha do titulo, a direita)
        if count:
            p.text("%d nucleos" % count, x + w - th.pad, y + 24, th.font_small,
                   th.dim2, align="right")

        # percentual grande (canto direito)
        big = MISSING if total is None else "%d%%" % int(round(total * 100))
        color = th.accent if total is not None else th.dim2
        p.text(big, x + w - th.pad, y + 74, th.font_huge, color, "bold",
               align="right")

        # grafico de barras do historico (60 amostras)
        chart_x = x + th.pad
        chart_y = y + 40
        chart_w = max(80.0, w - th.pad * 2 - 96)
        chart_h = max(40.0, h - 118)
        p.round(chart_x, chart_y, chart_w, chart_h, th.radius * 0.5,
                th.bg2, 0.85)
        p.line(chart_x, chart_y + chart_h, chart_x + chart_w,
               chart_y + chart_h, th.dim2, 1.0, 0.6)
        p.line(chart_x, chart_y + chart_h * 0.5, chart_x + chart_w,
               chart_y + chart_h * 0.5, th.dim2, 1.0, 0.25)

        history = list(self.cpu_history)
        if history:
            step = chart_w / float(HISTORY_SIZE)
            bw = max(1.0, step - 1.0)
            for i, value in enumerate(history):
                bh = chart_h * max(0.0, min(1.0, value))
                bx = chart_x + i * step
                by = chart_y + chart_h - bh
                p.rect(bx, by, bw, max(1.0, bh), th.accent, 0.9)
        else:
            p.text("sem amostras ainda", chart_x + chart_w / 2.0,
                   chart_y + chart_h / 2.0, th.font_small, th.dim2,
                   align="center")

        # frequencias por nucleo + governor
        line_y = chart_y + chart_h + 22
        freqs = self.data.get("cpu_freq") or []
        p.text("freq/core: %s" % _freq_list(freqs), x + th.pad, line_y,
               th.font_small, th.dim)
        gov = self.data.get("cpu_governor") or []
        gov_text = ", ".join(sorted({g for g in gov if g})) or MISSING
        p.text("governor: %s" % gov_text, x + th.pad,
               line_y + th.font_small + 6, th.font_small, th.dim)

    # ---- RAM ----

    def _draw_ram(self, p, x, y, w, h):
        th = self.theme
        ram = self.data.get("ram")
        area = self._card(p, x, y, w, h, "Memoria (RAM)")
        if not ram or not ram.get("total_kb"):
            p.text("indisponivel", area[0], area[1] + 22, th.font_small,
                   th.warn)
            return
        total = ram.get("total_kb")
        used = ram.get("used_kb")
        free = ram.get("free_kb")
        pct = ram.get("used_pct")
        p.text("usado %s de %s  (%s)" % (_human_kb(used), _human_kb(total),
                                         _percent(pct)),
               area[0], area[1] + 20, th.font_small, th.text)
        p.text("livre %s" % _human_kb(free), area[0], area[1] + 20 +
               th.font_small + 4, th.font_small, th.dim)
        bar_y = area[1] + 20 + th.font_small + 4 + 8
        frac = (pct / 100.0) if pct is not None else None
        if frac is None:
            p.text(MISSING, area[0], bar_y + 14, th.font_small, th.dim2)
        else:
            p.progress(area[0], bar_y, area[2], 10, frac, th.accent,
                       th.panel_hi)

    # ---- Armazenamento ----

    def _draw_disk(self, p, x, y, w, h):
        th = self.theme
        st = self.data.get("storage")
        area = self._card(p, x, y, w, h, "Armazenamento")
        if not st or not st.get("total"):
            p.text("indisponivel", area[0], area[1] + 22, th.font_small,
                   th.warn)
            return
        total = st.get("total")
        used = st.get("used")
        free = st.get("free")
        pct = st.get("used_pct")
        p.text("usado %s de %s  (%s)" % (_human_bytes(used),
                                         _human_bytes(total),
                                         _percent(pct)),
               area[0], area[1] + 20, th.font_small, th.text)
        p.text("livre %s" % _human_bytes(free), area[0], area[1] + 20 +
               th.font_small + 4, th.font_small, th.dim)
        bar_y = area[1] + 20 + th.font_small + 4 + 8
        frac = (pct / 100.0) if pct is not None else None
        if frac is None:
            p.text(MISSING, area[0], bar_y + 14, th.font_small, th.dim2)
        else:
            p.progress(area[0], bar_y, area[2], 10, frac, th.accent2,
                       th.panel_hi)

    # ---- Processos ----

    def _draw_processes(self, p, x, y, w, h):
        th = self.theme
        procs = self.data.get("processes") or []
        area = self._card(p, x, y, w, h, "Processos",
                          "%d maiores por RSS" % len(procs))
        # cabecalho das colunas
        name_x = area[0]
        pid_x = area[0] + area[2] * 0.48
        rss_x = area[0] + area[2] * 0.70
        cpu_x = area[0] + area[2]
        head_y = area[1] + 16
        p.text("PROCESSO", name_x, head_y, th.font_small, th.dim2)
        p.text("PID", pid_x, head_y, th.font_small, th.dim2, align="right")
        p.text("RSS", rss_x, head_y, th.font_small, th.dim2, align="right")
        p.text("CPU%", cpu_x, head_y, th.font_small, th.dim2, align="right")
        p.line(name_x, head_y + 6, cpu_x, head_y + 6, th.dim2, 1.0, 0.35)

        if not procs:
            p.text("indisponivel", name_x, head_y + 30, th.font_small, th.warn)
            return

        row_h = th.font_small + 8
        top = head_y + 12
        room = max(0, (area[1] + area[3]) - top)
        max_rows = int(room // row_h)
        for i, proc in enumerate(procs[:max_rows]):
            ry = top + i * row_h + th.font_small
            name = proc.get("name") or MISSING
            p.text(name, name_x, ry, th.font_small, th.text)
            p.text(str(proc.get("pid", MISSING)), pid_x, ry, th.font_small,
                   th.dim, align="right")
            rss = proc.get("rss_kb")
            p.text("%s" % (_human_kb(rss) if rss is not None else MISSING),
                   rss_x, ry, th.font_small, th.dim, align="right")
            cpu = proc.get("cpu_pct")
            p.text(_percent(cpu), cpu_x, ry, th.font_small, th.dim,
                   align="right")
        if len(procs) > max_rows:
            p.text("... +%d processos" % (len(procs) - max_rows),
                   name_x, area[1] + area[3] + 4, th.font_small, th.dim2)

    # ---- Temperaturas ----

    def _draw_thermal(self, p, x, y, w, h):
        th = self.theme
        zones = self.data.get("thermal") or []
        area = self._card(p, x, y, w, h, "Temperaturas",
                          "%d zonas" % len(zones))
        row_h = th.font_small + 6
        for i, zone in enumerate(zones):
            ry = area[1] + 18 + i * row_h
            if ry > area[1] + area[3]:
                break
            name = zone.get("type") or zone.get("zone") or MISSING
            p.text(str(name), area[0], ry, th.font_small, th.text)
            temp = zone.get("temp_c")
            if temp is None:
                p.text(MISSING, area[0] + area[2], ry, th.font_small, th.dim,
                       align="right")
            else:
                color = th.err if temp >= 80 else (th.warn if temp >= 60
                                                  else th.ok)
                p.text("%.1f C" % temp, area[0] + area[2], ry, th.font_small,
                       color, align="right")

    # ---- Bateria ----

    def _draw_battery(self, p, x, y, w, h):
        th = self.theme
        bat = self.data.get("battery") or {}
        area = self._card(p, x, y, w, h, "Bateria",
                          str(bat.get("name") or ""))
        cap = bat.get("capacity")
        status = bat.get("status") or MISSING
        p.text("%s - %s" % (_percent(cap), status.lower()), area[0],
               area[1] + 18, th.font_small, th.text)
        info = []
        if bat.get("temp_c") is not None:
            info.append("temp %.1f C" % bat["temp_c"])
        if bat.get("voltage_v") is not None:
            info.append("%.2f V" % bat["voltage_v"])
        if bat.get("health"):
            info.append(str(bat["health"]))
        if info:
            p.text(" | ".join(info), area[0], area[1] + 18 + th.font_small + 4,
                   th.font_small, th.dim)
        if cap is not None:
            frac = max(0.0, min(1.0, float(cap) / 100.0))
            bar_y = area[1] + 18 + th.font_small + 4 + 10
            color = th.err if frac <= 0.15 else (th.warn if frac <= 0.30
                                                 else th.ok)
            p.progress(area[0], bar_y, area[2], 10, frac, color, th.panel_hi)

    # ---- GPU / video ----

    def _draw_gpu(self, p, x, y, w, h):
        th = self.theme
        cards = self.data.get("drm") or []
        area = self._card(p, x, y, w, h, "GPU / video",
                          "%d conectores" % len(cards))
        row_h = th.font_small + 6
        for i, card in enumerate(cards):
            ry = area[1] + 18 + i * row_h
            if ry > area[1] + area[3]:
                break
            name = card.get("connector") or card.get("card") or MISSING
            p.text(str(name), area[0], ry, th.font_small, th.text)
            status = card.get("status") or MISSING
            p.text(str(status), area[0] + area[2] * 0.55, ry, th.font_small,
                   th.dim)
            modes = card.get("modes") or []
            p.text(modes[0] if modes else MISSING, area[0] + area[2], ry,
                   th.font_small, th.dim2, align="right")

    # ---------------- toque ----------------

    def on_touch(self, ev):
        et = getattr(ev, "type", "")
        rect = self._refresh_rect
        inside = (rect[0] <= ev.x <= rect[0] + rect[2] and
                  rect[1] <= ev.y <= rect[1] + rect[3])
        if et == "down":
            if inside:
                self._refresh_pressed = True
                return True
        elif et == "up":
            if self._refresh_pressed:
                self._refresh_pressed = False
                if inside:
                    self.refresh()
                    self._acc = 0.0
                    return True
        elif et == "cancel":
            self._refresh_pressed = False
        return False


# --------------------------------------------------------------------

def main():   # pragma: no cover - utilidade de inspecao manual
    """Imprime um resumo textual das metricas (sem interface)."""
    app = PerformanceApp()
    data = app.data
    print("NURA Performance — resumo")
    print("sysinfo: %s" % ("disponivel" if app.sysinfo else "INDISPONIVEL"))
    usage = data.get("cpu_usage") or {}
    print("cpu: %s" % (usage.get("total")))
    print("ram: %s" % (data.get("ram")))
    print("processos: %d" % len(data.get("processes") or []))


if __name__ == "__main__":   # pragma: no cover
    main()
