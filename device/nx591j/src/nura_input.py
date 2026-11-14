"""NURA OS — entrada por toque (evdev) e reconhecimento de gestos.

Le o touchscreen direto do /dev/input/event* (sem libinput, sem X11),
normaliza as coordenadas para o espaco paisagem (1920x1080) e
reconhece:

    tap / toque simples        (down+up rapido, sem mover)
    toque prolongado           (down segurado)
    arrastar                   (down + movimento)
    rolagem                    (1 dedo rapido vertical / 2 dedos)
    pinça (zoom)               (2 dedos, distancia muda)

Nada deprivilegio: leitura pura dos dispositivos de entrada.
"""

import ctypes
import fcntl
import os
import struct
import time

# --------------------------------------------------------------------
# constantes evdev
# --------------------------------------------------------------------
EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03

SYN_REPORT = 0x00

ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2F
ABS_MT_TOUCH_MAJOR = 0x30
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39
ABS_MT_PRESSURE = 0x3A

BTN_TOUCH = 0x14A

# _IOC(_IOC_READ,'E',0x40+code,24) em LP64
EVIOCGABS_BASE = 0x80184540

INPUT_EVENT_FMT = "llHHi"          # timeval(16) + u16 + u16 + s32 = 24
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FMT)


class _AbsInfo(ctypes.Structure):
    _fields_ = [("value", ctypes.c_int32), ("minimum", ctypes.c_int32),
                ("maximum", ctypes.c_int32), ("fuzz", ctypes.c_int32),
                ("flat", ctypes.c_int32), ("resolution", ctypes.c_int32)]


class TouchEvent(object):
    """Evento de toque ja em coordenadas paisagem (1920x1080)."""

    __slots__ = ("type", "x", "y", "button", "dx", "dy", "amount",
                 "scale", "time", "slots")

    def __init__(self, type="down", x=0, y=0, button=1, dx=0, dy=0,
                 amount=0.0, scale=1.0, time=0.0, slots=0):
        self.type = type          # down|up|move|cancel|scroll|pinch
        self.x = x                # paisagem
        self.y = y
        self.button = button
        self.dx = dx
        self.dy = dy
        self.amount = amount      # rolagem (pixels)
        self.scale = scale        # pinca (>1 = zoom in)
        self.time = time
        self.slots = slots

    def __repr__(self):
        return "<TouchEvent %s x=%.0f y=%.0f%s>" % (
            self.type, self.x, self.y,
            (" d=(%.0f,%.0f)" % (self.dx, self.dy)) if self.dx or self.dy else "")

    def as_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


class InputReader(object):
    """Le os eventos brutos do evdev e converte para paisagem."""

    def __init__(self, device="/dev/input/event3", panel_w=1080,
                 panel_h=1920, landscape_w=1920, landscape_h=1080,
                 rotation=90):
        self.device = device
        self.panel_w = panel_w
        self.panel_h = panel_h
        self.landscape_w = landscape_w
        self.landscape_h = landscape_h
        self.rotation = rotation
        self.fd = -1
        self.slots = {}            # id -> (x, y) em coords do painel
        self.active = 0            # slot ativo (protocolo B)
        self.x_min = 0
        self.x_max = panel_w - 1
        self.y_min = 0
        self.y_max = panel_h - 1
        self.touching = False
        self._touch_state_known = False
        self._was_down = False
        self._buf = b""

    # ---------------- abertura ----------------

    def open(self):
        self.fd = os.open(self.device, os.O_RDONLY | os.O_NONBLOCK)
        self._detect_range()
        return self

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def _detect_range(self):
        """Le o intervalo real do digitizador (EVIOCGABS)."""
        try:
            for code, cur_max in ((ABS_X, self.x_max), (ABS_Y, self.y_max)):
                info = _AbsInfo()
                fcntl.ioctl(self.fd, EVIOCGABS_BASE + code, info)
                if info.maximum > info.minimum and info.maximum < 10000:
                    if code == ABS_X:
                        self.x_min, self.x_max = info.minimum, info.maximum
                    else:
                        self.y_min, self.y_max = info.minimum, info.maximum
        except Exception:
            pass    # sem ioctl: assume a resolucao do painel

    # ---------------- geometria ----------------

    def to_landscape(self, px, py):
        """Ponto do painel (retrato) -> ponto da paisagem."""
        # normaliza para a resolucao do painel
        if self.x_max > self.x_min:
            px = (px - self.x_min) * (self.panel_w - 1) / float(
                self.x_max - self.x_min)
        if self.y_max > self.y_min:
            py = (py - self.y_min) * (self.panel_h - 1) / float(
                self.y_max - self.y_min)
        px = max(0, min(self.panel_w - 1, int(round(px))))
        py = max(0, min(self.panel_h - 1, int(round(py))))
        if self.rotation == 90:
            # o topo da paisagem e a borda direita do painel
            lx = py
            ly = self.panel_w - 1 - px
        elif self.rotation == 270:
            lx = self.panel_h - 1 - py
            ly = px
        else:
            lx, ly = px, py
        return (max(0, min(self.landscape_w - 1, lx)),
                max(0, min(self.landscape_h - 1, ly)))

    # ---------------- leitura ----------------

    def poll(self):
        """Le os eventos disponiveis (nao bloqueante). Devolve uma lista."""
        out = []
        if self.fd < 0:
            return out
        try:
            data = os.read(self.fd, 4096)
        except (BlockingIOError, OSError):
            return out
        if not data:
            return out
        self._buf += data
        while len(self._buf) >= INPUT_EVENT_SIZE:
            (sec, usec, etype, code, value) = struct.unpack(
                INPUT_EVENT_FMT, self._buf[:INPUT_EVENT_SIZE])
            self._buf = self._buf[INPUT_EVENT_SIZE:]
            self._handle(etype, code, value, sec + usec / 1e6, out)
        return out

    def _handle(self, etype, code, value, ts, out):
        if etype == EV_ABS:
            if code == ABS_MT_SLOT:
                self.active = value
            elif code == ABS_MT_TRACKING_ID:
                if value < 0:
                    self.slots.pop(self.active, None)
                else:
                    self.slots[self.active] = self.slots.get(
                        self.active, (0, 0))
            elif code == ABS_MT_POSITION_X:
                self._set_slot("x", value)
            elif code == ABS_MT_POSITION_Y:
                self._set_slot("y", value)
            elif code == ABS_X:
                self._single = ("x", value)
            elif code == ABS_Y:
                self._single = ("y", value)
        elif etype == EV_KEY:
            if code == BTN_TOUCH:
                self._touch_state_known = True
                if value == 1:
                    self.touching = True
                else:
                    self.touching = False
        elif etype == EV_SYN and code == SYN_REPORT:
            self._sync(ts, out)

    def _set_slot(self, axis, value):
        cur = self.slots.get(self.active)
        if cur is None:
            cur = (0, 0)
        if axis == "x":
            self.slots[self.active] = (value, cur[1])
        else:
            self.slots[self.active] = (cur[0], value)

    def _sync(self, ts, out):
        # Alguns digitizadores removem o slot MT ao soltar; outros mantem
        # a ultima coordenada e sinalizam a liberacao apenas com BTN_TOUCH=0.
        # Nos dois casos precisamos entregar um "up" ao reconhecedor de gesto.
        if not self.slots:
            if getattr(self, "_was_down", False):
                lx, ly = getattr(self, "_last", (0, 0))
                out.append(TouchEvent("up", lx, ly, time=ts))
                self._was_down = False
                self.touching = False
            return
        if self._touch_state_known and not self.touching:
            if getattr(self, "_was_down", False):
                lx, ly = getattr(self, "_last", (0, 0))
                out.append(TouchEvent("up", lx, ly, time=ts))
            self._was_down = False
            self.slots.clear()
            return
        pts = sorted(self.slots.items())
        if len(pts) == 1:
            _, (px, py) = pts[0]
            lx, ly = self.to_landscape(px, py)
            out.append(TouchEvent("move" if self._was_down else "down",
                                   lx, ly, time=ts, slots=1))
            self._was_down = True
            self._last = (lx, ly)
        else:
            (_, (x0, y0)), (_, (x1, y1)) = pts[0], pts[1]
            l0 = self.to_landscape(x0, y0)
            l1 = self.to_landscape(x1, y1)
            cx = (l0[0] + l1[0]) // 2
            cy = (l0[1] + l1[1]) // 2
            out.append(TouchEvent("move", cx, cy, time=ts, slots=2))
            self._was_down = True
            self._last = (cx, cy)

    def release(self, ts=0.0):
        """Evento de 'up' quando o dedo sai (BTN_TOUCH = 0)."""
        if getattr(self, "_was_down", False):
            lx, ly = getattr(self, "_last", (0, 0))
            self._was_down = False
            self.slots.clear()
            return TouchEvent("up", lx, ly, time=ts)
        return None


class GestureDetector(object):
    """Transforma eventos brutos em gestos de alto nivel.

    Configuravel para dedos grandes: tap_tolerance, long_press_ms,
    scroll_threshold.
    """

    def __init__(self, tap_tolerance=14, long_press_ms=550,
                 scroll_threshold=90, scroll_time=420):
        self.tap_tolerance = tap_tolerance
        self.long_press_ms = long_press_ms
        self.scroll_threshold = scroll_threshold
        self.scroll_time = scroll_time
        self.reset()

    def reset(self):
        self.down_xy = None
        self.down_t = 0.0
        self.moved = False
        self.long_fired = False
        self.last_xy = None
        self.last_t = 0.0
        self.pinch_start = None
        self.pinch_scale = 1.0

    def feed(self, ev):
        """Devolve uma lista de gestos reconhecidos."""
        out = []
        if ev.type == "down":
            self.reset()
            self.down_xy = (ev.x, ev.y)
            self.last_xy = (ev.x, ev.y)
            self.down_t = ev.time
            self.last_t = ev.time
        elif ev.type == "move":
            if self.down_xy is None:
                return out
            dx = ev.x - self.last_xy[0]
            dy = ev.y - self.last_xy[1]
            dist = ((ev.x - self.down_xy[0]) ** 2 +
                    (ev.y - self.down_xy[1]) ** 2) ** 0.5
            if dist > self.tap_tolerance:
                self.moved = True
            if ev.slots >= 2:
                out.append(TouchEvent("drag", ev.x, ev.y, dx=dx, dy=dy,
                                      time=ev.time, slots=2))
            else:
                out.append(TouchEvent("drag", ev.x, ev.y, dx=dx, dy=dy,
                                      time=ev.time))
            self.last_xy = (ev.x, ev.y)
            self.last_t = ev.time
        elif ev.type == "up":
            if self.down_xy is not None:
                dist = ((ev.x - self.down_xy[0]) ** 2 +
                        (ev.y - self.down_xy[1]) ** 2) ** 0.5
                dt = ev.time - self.down_t
                if not self.moved and not self.long_fired and \
                        dist <= self.tap_tolerance and dt < 0.8:
                    out.append(TouchEvent("tap", ev.x, ev.y, time=ev.time))
                elif self.moved and dt < (self.scroll_time / 1000.0):
                    # arrasto curto e rapido -> rolagem
                    dy = ev.y - self.down_xy[1]
                    dx = ev.x - self.down_xy[0]
                    if abs(dy) > abs(dx):
                        out.append(TouchEvent("scroll", ev.x, ev.y,
                                              amount=-dy * 1.6, time=ev.time))
                    else:
                        out.append(TouchEvent("drag", ev.x, ev.y, dx=dx,
                                              dy=dy, time=ev.time))
            self.reset()
        return out

    def tick(self, now):
        """Chame periodicamente: dispara o 'toque prolongado'."""
        if self.down_xy is not None and not self.moved and \
                not self.long_fired and \
                (now - self.down_t) * 1000.0 >= self.long_press_ms:
            self.long_fired = True
            return [TouchEvent("longpress", self.down_xy[0], self.down_xy[1],
                               time=now)]
        return []


def find_touch_device(preferred="/dev/input/event3"):
    """Descobre o dispositivo de touchscreen lendo /proc/bus/input/devices."""
    try:
        txt = open("/proc/bus/input/devices").read()
    except Exception:
        return preferred
    bloco = ""
    for parte in txt.split("\n\n"):
        low = parte.lower()
        if "touch" in low or "synaptics" in low or "rmi" in low:
            for linha in parte.splitlines():
                if linha.startswith("H:"):
                    bloco = linha
            if bloco:
                for ev in bloco.split():
                    if ev.startswith("event"):
                        return "/dev/input/" + ev
    return preferred
