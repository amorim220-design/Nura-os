"""NURA OS — teclado virtual nativo (QWERTY, pt-BR).

Desenhado em cairo, como todo o resto do NURA. Nao depende do X11, do
GTK, do matchbox-keyboard nem do buffyboard.

Funcao:
  * aparece quando um campo de texto ganha foco;
  * cada tecla e um alvo de toque grande (>= 44 px logicos);
  * "Shift" alterna maiusculas **e** os sinais, como num teclado de PC
    (Shift + "-" = "_", Shift + "1" = "!", Shift + ";" = ":", ...);
  * "123" troca para a camada de simbolos + acentos do portugues;
  * o texto digitado e entregue ao app que esta em foco atraves de
    `shell.on_key(TerminalKey-like)`;
  * `shell.keyboard_text` mantem o texto digitado para apps que
    precisam do valor completo (ex.: o filtro do NURA Start).
"""

import cairo

import nura_theme as T
from nura_input import TouchEvent
from nura_window import Widget

# Camada base: layout US completo (letras + pontuacao), no formato
# (sem shift, com shift). O Shift vale para TODAS as teclas, como num
# teclado de PC: digitos -> sinais, ; -> :, , -> <, / -> ?, \ -> |.
BASE = (
    ("1234567890-=", "!@#$%^&*()_+"),
    ("qwertyuiop[]", "QWERTYUIOP{}"),
    ("asdfghjkl;'", "ASDFGHJKL:\""),
    ("zxcvbnm,./\\", "ZXCVBNM<>?|"),
)

# Camada "123": simbolos que o Shift nao cobre + acentos do portugues.
SYM_ROWS = (
    list("!@#$%^&*()-+"),
    list("_=[]{};:'\"\\|"),
    list("áàâãéêíóôõúü"),
    list("çÁÀÂÉÊÍÓÔÕÚÜ~"),
)


class Key(object):
    __slots__ = ("label", "value", "x", "y", "w", "h", "kind", "color")

    def __init__(self, label, value, kind="char", color=None):
        self.label = label
        self.value = value
        self.kind = kind          # char|shift|sym|space|back|enter
        self.x = self.y = 0
        self.w = self.h = 0
        self.color = color


class Keyboard(Widget):
    """Teclado virtual desenhado na tela."""

    def __init__(self, shell=None, width=1920, height=1080):
        self.shell = shell
        self.screen_w = width
        self.screen_h = height
        self.visible = False
        self.shift = False
        self.symbols = False
        self.text = ""            # texto acumulado
        self.keys = []
        self.pressed = None
        self.height = int(330 * (shell.theme.ui_scale if shell else 1.0))
        self._layout()

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------

    def _layout(self):
        th = self.shell.theme if self.shell else T.Theme("neon")
        s = th.ui_scale
        kh = int(52 * s)
        gap = int(6 * s)
        y0 = self.screen_h - self.height
        rows = self._rows()
        # largura util: 96% da tela, com margem
        total_w = int(self.screen_w * 0.96)
        x0 = (self.screen_w - total_w) // 2
        self.keys = []

        # --- linha de acoes (no topo, mais perto dos dedos) ---
        ah = int(52 * s)
        acoes = [
            Key("Shift", "shift", "shift"),
            Key("123" if not self.symbols else "ABC", "sym", "sym"),
            Key("Espaco", " ", "space"),
            Key("Enter", "enter", "enter"),
            Key("Apagar", "back", "back"),
        ]
        # larguras proporcionais que somam EXATAMENTE a largura util
        pesos = [1.25, 1.25, 2.80, 1.35, 1.35]
        soma = float(sum(pesos))
        disponivel = total_w - gap * (len(pesos) - 1)
        widths = [int(disponivel * w / soma) for w in pesos]
        widths[-1] += total_w - (sum(widths) + gap * (len(widths) - 1))
        x = x0
        for k, w in zip(acoes, widths):
            k.x = x
            k.y = y0 + int(10 * s)
            k.w = w
            k.h = ah
            self.keys.append(k)
            x += w + gap

        # --- linhas de letras ---
        top = y0 + int(10 * s) + ah + gap
        for ri, row in enumerate(rows):
            n = len(row)
            kw = (total_w - gap * (n - 1)) // n
            y = top + ri * (kh + gap)
            x = x0
            for label, value in row:
                key = Key(label, value, "char")
                key.x = x
                key.y = y
                key.w = kw
                key.h = kh
                self.keys.append(key)
                x += kw + gap

    def _rows(self):
        """Devolve as linhas como listas de (rotulo, valor)."""
        if self.symbols:
            return [[(c, c) for c in row] for row in SYM_ROWS]
        out = []
        for normal, shifted in BASE:
            if self.shift:
                out.append([(s, s) for s in shifted])
            else:
                out.append([(n, n) for n in normal])
        return out

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def show(self):
        self.visible = True
        self._layout()
        if self.shell:
            self.shell.dirty = True

    def hide(self):
        self.visible = False
        if self.shell:
            self.shell.dirty = True

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def clear(self):
        self.text = ""
        if self.shell:
            self.shell.dirty = True

    # ------------------------------------------------------------------
    # desenho
    # ------------------------------------------------------------------

    def draw(self, p):
        if not self.visible:
            return
        th = p.theme
        y0 = self.screen_h - self.height
        # opaco: nada da barra de tarefas pode aparecer por baixo
        p.rect(0, y0, self.screen_w, self.height, th.bg, 1.0)
        p.rect(0, y0, self.screen_w, self.height, th.panel, 1.0)
        p.rect(0, y0, self.screen_w, 2, th.accent, 0.55)
        for k in self.keys:
            if k.kind == "char":
                cor = th.panel_hi
                txt = th.text
            elif k.kind == "shift":
                cor = th.accent if self.shift else th.panel_hi
                txt = th.text
            elif k.kind == "sym":
                cor = th.accent if self.symbols else th.panel_hi
                txt = th.text
            else:
                cor = th.panel_hi
                txt = th.text
            pressed = (self.pressed is k)
            p.round(k.x, k.y, k.w, k.h, th.radius, cor,
                    0.95 if pressed else 0.70)
            if k.kind != "space":
                p.round(k.x, k.y, k.w, k.h, th.radius, th.accent, 0.0,
                        filled=False, width=1.0)
            p.text(k.label, k.x + k.w / 2, k.y + k.h / 2 + th.font * 0.38,
                   th.font_title if k.kind == "char" else th.font, txt,
                   align="center")

    # ------------------------------------------------------------------
    # toque
    # ------------------------------------------------------------------

    def hit(self, x, y):
        for k in self.keys:
            if k.x <= x <= k.x + k.w and k.y <= y <= k.y + k.h:
                return k
        return None

    def on_touch(self, ev):
        if not self.visible:
            return False
        if ev.type == "tap":
            k = self.hit(ev.x, ev.y)
            if k is not None:
                self.pressed = None
                self.activate(k)
            if self.shell:
                self.shell.dirty = True
            return ev.y >= self.screen_h - self.height
        if ev.type == "down":
            k = self.hit(ev.x, ev.y)
            self.pressed = k
            if self.shell:
                self.shell.dirty = True
            return True
        if ev.type == "up":
            k = self.hit(ev.x, ev.y)
            # Em eventos brutos, so dispara quando down e up correspondem.
            # O caminho normal do shell usa "tap" (tratado acima).
            alvo = k if k is not None and k is self.pressed else None
            self.pressed = None
            if alvo is not None:
                self.activate(alvo)
            if self.shell:
                self.shell.dirty = True
            return True
        return ev.y >= self.screen_h - self.height

    def activate(self, k):
        """Executa a tecla."""
        if k.kind == "shift":
            self.shift = not self.shift
            self._layout()
        elif k.kind == "sym":
            self.symbols = not self.symbols
            self._layout()
        elif k.kind == "space":
            self._send(" ")
        elif k.kind == "back":
            self._send("BackSpace")
        elif k.kind == "enter":
            self._send("Return")
        else:
            self._send(k.value)
            if self.shift and not self.symbols:
                self.shift = False
                self._layout()

    def _send(self, value):
        """Entrega o texto/tecla ao app em foco."""
        if value == "BackSpace":
            self.text = self.text[:-1]
        elif value == "Return":
            pass
        elif value == " ":
            self.text += " "
        else:
            self.text += value
        if self.shell is not None:
            try:
                self.shell.on_key(value)
            except Exception:
                pass
            self.shell.dirty = True
