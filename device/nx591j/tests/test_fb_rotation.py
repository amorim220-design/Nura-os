#!/usr/bin/env python3
"""NURA OS — testes isolados do framebuffer e da rotacao.

Nao precisa do aparelho: usa um arquivo comum como framebuffer falso.
"""

import ctypes
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import cairo  # noqa: E402

from nura_fb import (Framebuffer, _FbFixScreeninfo,
                     _FbVarScreeninfo)  # noqa: E402

DESK_W, DESK_H = 1920, 1080
FB_W, FB_H = 1080, 1920
STRIDE = 4352

# caminhos unicos por processo: evita colisao se varias suites rodarem
# ao mesmo tempo (o mock e um arquivo mmap; trunca-lo por fora daria SIGBUS)
PID = os.getpid()


def mock_path(nome):
    return "/tmp/nura-fb-%d-%s.mock" % (PID, nome)

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)


def test_ioctl_struct_sizes():
    print("\n=== tamanhos UAPI dos ioctls do framebuffer ===")
    check("fb_var_screeninfo ocupa 160 bytes",
          ctypes.sizeof(_FbVarScreeninfo) == 160,
          "-> %d" % ctypes.sizeof(_FbVarScreeninfo))
    check("fb_fix_screeninfo ocupa 80 bytes",
          ctypes.sizeof(_FbFixScreeninfo) == 80,
          "-> %d" % ctypes.sizeof(_FbFixScreeninfo))


def make_pattern():
    """Superficie paisagem onde cada pixel codifica a propria posicao.

    cairo ARGB32 em little-endian => bytes: B, G, R, A.
    """
    stride = DESK_W * 4 + 0
    buf = bytearray(stride * DESK_H)
    for y in range(DESK_H):
        base = y * stride
        for x in range(DESK_W):
            o = base + x * 4
            buf[o + 0] = x & 0xFF          # B
            buf[o + 1] = y & 0xFF          # G
            buf[o + 2] = (x + y) & 0xFF    # R
            buf[o + 3] = 0xFF              # A
    surf = cairo.ImageSurface.create_for_data(
        buf, cairo.FORMAT_ARGB32, DESK_W, DESK_H, stride)
    surf.flush()
    return surf


def read_fb(path, layout):
    data = open(path, "rb").read()
    px = []
    for y in range(FB_H):
        row = []
        for x in range(FB_W):
            off = y * STRIDE + x * 4
            b, g, r = data[off], data[off + 1], data[off + 2]
            if layout == "rgba":
                # o fb esta em R,G,B,A; o cairo produz B,G,R,A
                b, g, r = r, g, b
            row.append((b, g, r))
        px.append(row)
    return px


def test_rotation(layout):
    print("\n=== rotacao 90 graus (layout %s) ===" % layout)
    path = mock_path("test-%s" % layout)
    with open(path, "wb") as f:
        f.truncate(STRIDE * FB_H)

    fb = Framebuffer(mock=path, layout=layout)
    surf = make_pattern()
    fb.present(surf, rotation=90)

    px = read_fb(path, layout)

    erros = 0
    primeiro_erro = None
    amostras = 0
    for LY in range(0, DESK_H, 97):
        for LX in range(0, DESK_W, 173):
            amostras += 1
            pxp = FB_W - 1 - LY     # landscape_to_portrait
            pyp = LX
            got = px[pyp][pxp]
            esp = (LX & 0xFF, LY & 0xFF, (LX + LY) & 0xFF)
            if got != esp:
                erros += 1
                if primeiro_erro is None:
                    primeiro_erro = (LX, LY, got, esp)
    check("ida-e-volta pixel a pixel (%d amostras)" % amostras,
          erros == 0, "%d erros, primeiro=%s" % (erros, primeiro_erro))
    fb.close()


def test_corner_marker():
    """Pinta um marcador unico e verifica onde ele cai."""
    print("\n=== marcador de canto ===")
    path = mock_path("corner")
    with open(path, "wb") as f:
        f.truncate(STRIDE * FB_H)
    fb = Framebuffer(mock=path, layout="bgra")
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, DESK_W, DESK_H)
    ctx = cairo.Context(surf)
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    ctx.set_source_rgb(1, 1, 1)
    ctx.rectangle(0, 0, 8, 8)        # canto superior-esquerdo da paisagem
    ctx.fill()
    fb.present(surf, rotation=90)

    px = read_fb(path, "bgra")
    achou = []
    for y in range(FB_H):
        for x in range(FB_W):
            if px[y][x] == (255, 255, 255):
                achou.append((x, y))
    if achou:
        xs = [a[0] for a in achou]
        ys = [a[1] for a in achou]
        print("  marcador em x=[%d..%d] y=[%d..%d]" % (
            min(xs), max(xs), min(ys), max(ys)))
        check("marcador da paisagem fica no topo-direita do painel",
              min(xs) >= FB_W - 9 and max(xs) <= FB_W - 1 and
              min(ys) <= 1 and max(ys) <= 8)
    else:
        check("marcador encontrado", False, "nenhum pixel branco")
    fb.close()


def test_touch_mapping():
    print("\n=== mapeamento de coordenadas do toque ===")
    with open(mock_path("touch"), "wb") as f:
        f.truncate(STRIDE * FB_H)
    fb = Framebuffer(mock=mock_path("touch"), layout="bgra")
    ok = True
    for (lx, ly) in ((0, 0), (1919, 0), (0, 1079), (1919, 1079), (960, 540)):
        px, py = fb.landscape_to_portrait(lx, ly)
        back = fb.portrait_to_landscape(px, py)
        if back != (lx, ly):
            ok = False
            print("    falha em (%d,%d) -> (%d,%d) -> %s" % (lx, ly, px, py, back))
    check("portrait_to_landscape e o inverso de landscape_to_portrait", ok)
    px, py = fb.landscape_to_portrait(0, 0)
    check("paisagem (0,0) -> painel (%d,%d) [canto sup-dir]" % (px, py),
          px == FB_W - 1 and py == 0)
    fb.close()


def test_swizzle_matches():
    """O caminho 'rgba' deve produzir os mesmos pixels que o 'bgra'."""
    print("\n=== equivalencia dos dois layouts ===")
    outs = {}
    for layout in ("bgra", "rgba"):
        path = mock_path("eq-%s" % layout)
        with open(path, "wb") as f:
            f.truncate(STRIDE * FB_H)
        fb = Framebuffer(mock=path, layout=layout)
        fb.present(make_pattern(), rotation=90)
        fb.close()
        outs[layout] = read_fb(path, layout)
    igual = outs["bgra"] == outs["rgba"]
    check("layout rgba produz a mesma imagem que bgra", igual)


if __name__ == "__main__":
    print("NURA OS — teste de framebuffer/rotacao")
    test_ioctl_struct_sizes()
    test_rotation("bgra")
    test_rotation("rgba")
    test_corner_marker()
    test_touch_mapping()
    test_swizzle_matches()
    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS: %s" % falhas))
    sys.exit(1 if falhas else 0)
