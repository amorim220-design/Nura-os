#!/usr/bin/env python3
"""NURA OS — renderiza a area de trabalho num framebuffer falso e
exporta um PNG para conferencia visual.

Gera dois arquivos:
  <out>          -> a area de trabalho em paisagem (1920x1080)
  <out>-fb.png   -> o conteudo real do framebuffer (retrato, ja rotacionado)

uso:  python3 preview.py [--out arquivo.png] [--bench N]
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import cairo  # noqa: E402

from nura_shell import NuraShell, DESK_W, DESK_H  # noqa: E402

MOCK = "/tmp/nura-preview.mock"
STRIDE = 4352


def dump_mock_png(mock_path, out_png):
    """Joga no PNG o conteudo cru do framebuffer (retrato)."""
    data = open(mock_path, "rb").read()
    w, h = 1080, 1920
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    sstride = surf.get_stride()
    dst = surf.get_data()
    for y in range(h):
        base = y * sstride
        row = bytearray(w * 4)
        off = y * STRIDE
        row[0:w * 4] = data[off:off + w * 4]
        dst[base:base + w * 4] = row
    surf.mark_dirty()
    surf.write_to_png(out_png)
    surf.flush()
    print("[preview] framebuffer cru -> %s" % out_png)


def main():
    out = "nura-desktop.png"
    bench = 0
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--out" and i + 1 < len(args):
            out = args[i + 1]
        if a == "--bench" and i + 1 < len(args):
            bench = int(args[i + 1])

    with open(MOCK, "wb") as f:
        f.truncate(STRIDE * 1920)

    sh = NuraShell(mock=MOCK)
    sh.menu_open = True
    sh.selected = 1

    if bench:
        t0 = time.time()
        for _ in range(bench):
            sh.tick()
        dt = time.time() - t0
        print("[preview] render+present: %.1f ms/frame -> %.1f fps" %
              (dt / bench * 1000.0, bench / dt))

    sh.surface.write_to_png(out)
    print("[preview] area de trabalho -> %s" % out)
    dump_mock_png(MOCK, out.rsplit(".", 1)[0] + "-fb.png")
    sh.fb.close()


if __name__ == "__main__":
    main()
