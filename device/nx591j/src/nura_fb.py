"""NURA OS — acesso ao framebuffer com rotação de 90 graus.

O painel do NX591J é retrato (1080x1920) e o NURA OS é paisagem
(1920x1080). O MSM8953 não tem rotator de hardware (o MDP5 não), e o
driver fbdev do Xorg não expõe RandR rotation — então a rotação é feita
por software, aqui mesmo.

A rotação canônica é a mesma do Android para "landscape": o aparelho
girado 90 graus no sentido ANTIHORÁRIO. Nesse caso:

    paisagem (LX, LY)  ->  retrato (px, py)
        px = 1079 - LY        (topo da paisagem vai para a borda direita)
        py = LX               (esquerda da paisagem vai para o topo)

E o inverso, para o touch (que chega em coordenadas do painel):

    retrato (px, py)  ->  paisagem (LX, LY)
        LX = py
        LY = 1079 - px

O desenho e feito pelo proprio cairo (rotacao em C), escrevendo
direto na memoria do framebuffer via `create_for_data` — sem copia
intermediaria no caminho normal.
"""

import ctypes
import fcntl
import mmap
import os

import cairo

# --- ioctl / structs do framebuffer (uapi do Linux) ---------------------

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602


class _FbBitfield(ctypes.Structure):
    _fields_ = [
        ("offset", ctypes.c_uint32),
        ("length", ctypes.c_uint32),
        ("msb_right", ctypes.c_uint32),
    ]


class _FbVarScreeninfo(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_uint32), ("yres", ctypes.c_uint32),
        ("xres_virtual", ctypes.c_uint32), ("yres_virtual", ctypes.c_uint32),
        ("xoffset", ctypes.c_uint32), ("yoffset", ctypes.c_uint32),
        ("bits_per_pixel", ctypes.c_uint32), ("grayscale", ctypes.c_uint32),
        ("red", _FbBitfield), ("green", _FbBitfield),
        ("blue", _FbBitfield), ("transp", _FbBitfield),
        ("nonstd", ctypes.c_uint32), ("activate", ctypes.c_uint32),
        ("height", ctypes.c_uint32), ("width", ctypes.c_uint32),
        ("accel_flags", ctypes.c_uint32), ("pixclock", ctypes.c_uint32),
        ("left_margin", ctypes.c_uint32), ("right_margin", ctypes.c_uint32),
        ("upper_margin", ctypes.c_uint32), ("lower_margin", ctypes.c_uint32),
        ("hsync_len", ctypes.c_uint32), ("vsync_len", ctypes.c_uint32),
        ("sync", ctypes.c_uint32), ("vmode", ctypes.c_uint32),
        ("rotate", ctypes.c_uint32), ("colorspace", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]


class _FbFixScreeninfo(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char * 16), ("smem_start", ctypes.c_uint64),
        ("smem_len", ctypes.c_uint32), ("type", ctypes.c_uint32),
        ("type_aux", ctypes.c_uint32), ("visual", ctypes.c_uint32),
        ("xpanstep", ctypes.c_uint16), ("ypanstep", ctypes.c_uint16),
        ("ywrapstep", ctypes.c_uint16), ("line_length", ctypes.c_uint32),
        ("mmio_start", ctypes.c_ulong), ("mmio_len", ctypes.c_uint32),
        ("accel", ctypes.c_uint32), ("capabilities", ctypes.c_uint16),
        ("reserved", ctypes.c_uint16 * 2),
    ]


class FramebufferError(RuntimeError):
    pass


class Framebuffer(object):
    """Framebuffer do painel, com apresentação rotacionada.

    mock=...  -> usa um arquivo comum no lugar do /dev/fb0 (testes
                 isolados, sem hardware).
    """

    def __init__(self, path="/dev/fb0", mock=None, layout="auto"):
        self.mock = mock
        self.path = path
        self.fd = -1
        self.map = None
        self.var = None
        self.fix = None
        self.xres = 0
        self.yres = 0
        self.bpp = 32
        self.stride = 0
        self.layout = layout       # 'bgra' (nativo do cairo) ou 'rgba'
        self.red_off = 2
        self.green_off = 1
        self.blue_off = 0
        self.alpha_off = 3
        self._open()
        self._setup_surfaces()

    # ------------------------------------------------------------------
    # abertura
    # ------------------------------------------------------------------

    def _open(self):
        if self.mock:
            self.fd = os.open(self.mock, os.O_RDWR)
            self.xres, self.yres = 1080, 1920
            self.bpp, self.stride = 32, 4352
            self.var = None
            self.fix = None
            size = self.stride * self.yres
            self.map = mmap.mmap(self.fd, size, mmap.MAP_SHARED,
                                 prot=mmap.PROT_READ | mmap.PROT_WRITE)
            print("[nura-fb] MOCK %dx%d bpp=%d stride=%d" % (
                self.xres, self.yres, self.bpp, self.stride))
            if self.layout == "auto":
                self.layout = "bgra"
            if self.layout == "bgra":
                # XRGB8888 em little-endian: R no byte 2, G no 1, B no 0
                self.red_off, self.green_off = 2, 1
                self.blue_off, self.alpha_off = 0, 3
            else:
                # painel com R no byte 0 (raro, mas existe em fbdev/X11)
                self.red_off, self.green_off = 0, 1
                self.blue_off, self.alpha_off = 2, 3
            print("[nura-fb] mock layout=%s (R=%d G=%d B=%d A=%d)" % (
                self.layout, self.red_off, self.green_off,
                self.blue_off, self.alpha_off))
            return

        self.fd = os.open(self.path, os.O_RDWR)
        var = _FbVarScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, var)
        fix = _FbFixScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_FSCREENINFO, fix)
        self.var = var
        self.fix = fix
        self.xres = var.xres
        self.yres = var.yres
        self.bpp = var.bits_per_pixel
        self.stride = fix.line_length
        if self.bpp != 32:
            raise FramebufferError(
                "framebuffer de %d bpp nao suportado (precisa de 32)" % self.bpp)
        size = self.stride * self.yres
        self.map = mmap.mmap(self.fd, size, mmap.MAP_SHARED,
                             prot=mmap.PROT_READ | mmap.PROT_WRITE)
        print("[nura-fb] %dx%d bpp=%d stride=%d (virt %dx%d)" % (
            self.xres, self.yres, self.bpp, self.stride,
            var.xres_virtual, var.yres_virtual))

        # detecta o layout de bytes real do painel
        self.red_off = var.red.offset // 8
        self.green_off = var.green.offset // 8
        self.blue_off = var.blue.offset // 8
        self.alpha_off = var.transp.offset // 8
        print("[nura-fb] offsets: R=%d G=%d B=%d A=%d (bits)  ->  bytes %d/%d/%d/%d" % (
            var.red.offset, var.green.offset, var.blue.offset, var.transp.offset,
            self.red_off, self.green_off, self.blue_off, self.alpha_off))
        if self.layout == "auto":
            if (self.red_off, self.green_off, self.blue_off) == (2, 1, 0):
                self.layout = "bgra"     # identico ao ARGB32 do cairo
            else:
                self.layout = "rgba"     # precisa trocar os canais
        print("[nura-fb] layout: %s" % self.layout)

    def _setup_surfaces(self):
        """Prepara as superficies cairo.

        - layout 'bgra': o cairo escreve DIRETO na memoria do fb
          (create_for_data) — zero copias.
        - layout 'rgba': desenha numa superficie intermediaria e troca
          os canais na hora de copiar.
        """
        self._mv = memoryview(self.map)
        if self.layout == "bgra":
            self.fb_surface = cairo.ImageSurface.create_for_data(
                self._mv, cairo.FORMAT_ARGB32, self.xres, self.yres,
                self.stride)
            self.fb_ctx = cairo.Context(self.fb_surface)
            self.stage = None
        else:
            self.fb_surface = None
            self.fb_ctx = None
            self.stage = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                            self.xres, self.yres)
            self.stage_ctx = cairo.Context(self.stage)

    def close(self):
        # a superficie do cairo segura uma referencia ao memoryview;
        # tem que soltar tudo antes de fechar o mmap
        self.fb_surface = None
        self.fb_ctx = None
        self.stage = None
        self.stage_ctx = None
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        mv = getattr(self, "_mv", None)
        if mv is not None:
            try:
                mv.release()
            except Exception:
                pass
            self._mv = None
        if self.map:
            try:
                self.map.close()
            except Exception as e:
                print("[nura-fb] aviso ao fechar: %s" % e)
        if self.fd >= 0:
            os.close(self.fd)

    # ------------------------------------------------------------------
    # geometria
    # ------------------------------------------------------------------

    def _matrix(self, rotation):
        """Matriz do cairo que leva a imagem (LX,LY) ate o painel.

        O deslocamento de meio pixel e o que faz o mapeamento cair exato
        nos pixels (sem amostragem "borrada" nas bordas).
        """
        if rotation == 90:
            # paisagem -> retrato girando o aparelho no sentido antihorario:
            #   px = 1079 - LY ,  py = LX
            return cairo.Matrix(xx=0.0, yx=1.0, xy=-1.0, yy=0.0,
                                x0=float(self.xres), y0=0.0)
        if rotation == 270:
            #   px = LY ,  py = 1919 - LX
            return cairo.Matrix(xx=0.0, yx=-1.0, xy=1.0, yy=0.0,
                                x0=0.0, y0=float(self.yres))
        raise ValueError("rotation deve ser 90 ou 270")

    def portrait_to_landscape(self, px, py):
        """Coordenada do painel (toque) -> coordenada da paisagem."""
        return py, self.xres - 1 - px

    def landscape_to_portrait(self, lx, ly):
        """Coordenada da paisagem -> coordenada do painel."""
        return self.xres - 1 - ly, lx

    # ------------------------------------------------------------------
    # apresentacao
    # ------------------------------------------------------------------

    def present(self, src_surface, rotation=90):
        """Desenha a superficie (paisagem) no painel, ja rotacionada."""
        if self.fb_ctx is not None:
            ctx = self.fb_ctx
            ctx.save()
            ctx.set_matrix(self._matrix(rotation))
            ctx.set_source_surface(src_surface, 0, 0)
            src = ctx.get_source()
            try:
                src.set_filter(cairo.FILTER_NEAREST)
            except Exception:
                pass
            ctx.paint()
            ctx.restore()
            self.fb_surface.flush()
        else:
            # caminho com troca de canais
            ctx = self.stage_ctx
            ctx.save()
            ctx.set_matrix(self._matrix(rotation))
            ctx.set_source_surface(src_surface, 0, 0)
            try:
                ctx.get_source().set_filter(cairo.FILTER_NEAREST)
            except Exception:
                pass
            ctx.paint()
            ctx.restore()
            self.stage.flush()
            self._copy_swizzled()

    def _copy_swizzled(self):
        """Copia a superficie intermediaria para o fb trocando os canais."""
        data = self.stage.get_data()
        sstride = self.stage.get_stride()
        dst = self._mv
        w4 = self.xres * 4
        for y in range(self.yres):
            row = data[y * sstride:y * sstride + w4]
            if not row:
                break
            out = bytearray(w4)
            out[self.red_off::4] = row[2::4]
            out[self.green_off::4] = row[1::4]
            out[self.blue_off::4] = row[0::4]
            if self.alpha_off is not None and self.alpha_off < 4:
                out[self.alpha_off::4] = row[3::4]
            off = y * self.stride
            dst[off:off + w4] = out
        dst.release()

    # ------------------------------------------------------------------
    # caminho legado (bytes) — mantido para compatibilidade
    # ------------------------------------------------------------------

    def blit_rotated(self, src, src_w, src_h, rotation=90):
        """Escreve um buffer ARGB32 (bytes) no painel, rotacionado.

        Só para testes antigos; o caminho normal é `present()`.
        """
        surf = cairo.ImageSurface.create_for_data(
            bytearray(src), cairo.FORMAT_ARGB32, src_w, src_h, src_w * 4)
        self.present(surf, rotation=rotation)

    def blit(self, src, src_w, src_h):
        """Escreve sem rotacionar (modo retrato)."""
        surf = cairo.ImageSurface.create_for_data(
            bytearray(src), cairo.FORMAT_ARGB32, src_w, src_h, src_w * 4)
        ctx = cairo.Context(self.fb_surface) if self.fb_ctx is None else self.fb_ctx
        ctx.set_source_surface(surf, 0, 0)
        ctx.paint()
        self.fb_surface.flush()
