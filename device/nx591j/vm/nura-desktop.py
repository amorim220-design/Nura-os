#!/usr/bin/env python3
"""Run the NURA Linux shell in a virtual machine window."""
import io
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nura_input import TouchEvent
from nura_shell import DESK_H, DESK_W, NuraShell, _SimpleKey


def main():
    root = tk.Tk()
    root.title("NURA OS")
    root.attributes("-fullscreen", True)
    view = tk.Label(root, background="black", borderwidth=0, highlightthickness=0)
    view.pack(fill="both", expand=True)

    with tempfile.TemporaryDirectory(prefix="nura-vm-") as work:
        fb = Path(work) / "fb"
        with fb.open("wb") as stream:
            stream.truncate(4352 * 1920)

        shell = NuraShell(mock=str(fb), input_device="")
        ready = Path("/run/nura-vm/ready")

        def touch(kind, event):
            x = event.x * DESK_W // max(1, view.winfo_width())
            y = event.y * DESK_H // max(1, view.winfo_height())
            shell._dispatch(TouchEvent(kind, x, y, time=time.monotonic()))

        def key(event):
            if event.keysym == "Escape":
                root.attributes("-fullscreen", False)
                return
            value = event.char if event.char and event.char.isprintable() else event.keysym
            shell.on_key(_SimpleKey(value, text=event.char,
                                    ctrl=bool(event.state & 4),
                                    shift=bool(event.state & 1)))

        def draw():
            shell.tick()
            width, height = view.winfo_width(), view.winfo_height()
            if width < 2 or height < 2:
                root.after(125, draw)
                return
            output = io.BytesIO()
            shell.surface.write_to_png(output)
            output.seek(0)
            with Image.open(output) as source:
                frame = ImageTk.PhotoImage(source.resize((width, height),
                                                         Image.Resampling.BILINEAR))
            view.configure(image=frame)
            view.image = frame
            if ready.parent.is_dir() and not ready.exists():
                ready.touch()
            root.after(125, draw)

        view.bind("<ButtonPress-1>", lambda e: touch("down", e))
        view.bind("<B1-Motion>", lambda e: touch("move", e))
        view.bind("<ButtonRelease-1>", lambda e: touch("up", e))
        root.bind("<KeyPress>", key)
        root.after(0, draw)
        try:
            root.mainloop()
        finally:
            shell.fb.close()


if __name__ == "__main__":
    main()
