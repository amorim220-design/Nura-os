#!/usr/bin/env python3
"""NURA OS — testes do teclado virtual (nura_keyboard).

Cobre o bug relatado em 13/11/2026: "o Shift nao funciona, nao da para
colocar _". O Shift tem de valer para TODAS as teclas, como num
teclado de PC (Shift + "-" = "_", Shift + "1" = "!", Shift + ";" = ":").

Roda sem aparelho: cria o objeto direto e, no fim, exercita o caminho
completo teclado -> shell -> Terminal com um framebuffer falso.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import nura_theme as T  # noqa: E402
import nura_keyboard as K  # noqa: E402
from nura_input import InputReader, TouchEvent  # noqa: E402

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)


class FakeShell(object):
    """Shell minimo: tema, flag dirty e captura do que foi digitado."""

    def __init__(self, theme="neon"):
        self.theme = T.Theme(theme)
        self.dirty = False
        self.recebido = []
        self.erros = []

    def on_key(self, value):
        self.recebido.append(value)


class Ev(object):
    def __init__(self, tipo, x=0.0, y=0.0):
        self.type = tipo
        self.x = x
        self.y = y


def novo_teclado(theme="neon"):
    sh = FakeShell(theme)
    kb = K.Keyboard(shell=sh)
    kb.show()
    return sh, kb


def acha(kb, label):
    for k in kb.keys:
        if k.label == label:
            return k
    return None


def toca(sh, kb, label):
    """Simula down+up no centro da tecla de rotulo `label`."""
    k = acha(kb, label)
    if k is None:
        return False
    cx, cy = k.x + k.w / 2.0, k.y + k.h / 2.0
    kb.on_touch(Ev("down", cx, cy))
    kb.on_touch(Ev("up", cx, cy))
    return True


def toca_pelo_shell(sh, kb, label, inicio=1.0):
    """Simula o down/up evdev e deixa o GestureDetector gerar o tap."""
    k = acha(kb, label)
    if k is None:
        return False
    cx, cy = int(k.x + k.w / 2), int(k.y + k.h / 2)
    sh._dispatch(TouchEvent("down", cx, cy, time=inicio))
    sh._dispatch(TouchEvent("up", cx, cy, time=inicio + 0.1))
    return True


def valor_de(kb, label):
    k = acha(kb, label)
    return k.value if k else None


# ----------------------------------------------------------------------
# 1. o bug relatado
# ----------------------------------------------------------------------

def test_shift_simbolos():
    print("\n=== o bug: Shift + '-' tem de dar '_' ===")
    sh, kb = novo_teclado()

    check("sem shift existe a tecla '-'", acha(kb, "-") is not None)
    check("sem shift '-' vale '-'", valor_de(kb, "-") == "-")
    check("sem shift NAO existe '_' na camada base",
          acha(kb, "_") is None)

    # liga o shift
    toca(sh, kb, "Shift")
    check("shift ligado", kb.shift is True)
    check("shift destaca a tecla (cor de acento)", kb.shift is True)

    check("com shift aparece a tecla '_'", acha(kb, "_") is not None)
    check("com shift '_' vale '_'", valor_de(kb, "_") == "_")

    sh.recebido = []
    toca(sh, kb, "_")
    check("tocar '_' entrega '_' ao shell", sh.recebido == ["_"],
          "-> %s" % sh.recebido)
    check("shift volta a desligar depois de uma tecla",
          kb.shift is False)


def test_shift_numeros():
    print("\n=== Shift nos numeros (como num PC) ===")
    sh, kb = novo_teclado()
    toca(sh, kb, "Shift")
    pares = [("1", "!"), ("2", "@"), ("9", "("), ("0", ")"), ("=", "+")]
    for base, esperado in pares:
        kb.shift = True
        kb._layout()
        check("shift+%s -> %s" % (base, esperado),
              valor_de(kb, esperado) == esperado,
              "-> %s" % valor_de(kb, esperado))


def test_shift_pontuacao():
    print("\n=== Shift na pontuacao ===")
    sh, kb = novo_teclado()
    casos = [(";", ":"), ("'", "\""), (",", "<"), (".", ">"),
             ("/", "?"), ("\\", "|"), ("[", "{"), ("]", "}")]
    for base, esperado in casos:
        check("sem shift existe '%s'" % base, acha(kb, base) is not None)
        kb.shift = True
        kb._layout()
        check("shift+'%s' -> '%s'" % (base, esperado),
              valor_de(kb, esperado) == esperado,
              "-> %s" % valor_de(kb, esperado))
        kb.shift = False
        kb._layout()


def test_shift_letras():
    print("\n=== Shift nas letras (maiusculas) ===")
    sh, kb = novo_teclado()
    toca(sh, kb, "Shift")
    check("q vira Q", valor_de(kb, "Q") == "Q")
    check("a vira A", valor_de(kb, "A") == "A")
    check("z vira Z", valor_de(kb, "Z") == "Z")
    check("minusculas somem", acha(kb, "q") is None)

    sh.recebido = []
    toca(sh, kb, "Q")
    check("tocar Q entrega 'Q'", sh.recebido == ["Q"], "-> %s" % sh.recebido)


# ----------------------------------------------------------------------
# 2. camada de simbolos / acentos
# ----------------------------------------------------------------------

def test_camada_simbolos():
    print("\n=== camada 123: simbolos e acentos pt-BR ===")
    sh, kb = novo_teclado()
    toca(sh, kb, "123")
    check("camada de simbolos ativa", kb.symbols is True)
    check("o botao passa a dizer ABC", acha(kb, "ABC") is not None)

    for c in "_=[]{};:'\"\\|":
        check("simbolo '%s' presente" % c, acha(kb, c) is not None)

    for c in "áàâãéêíóôõúüç":
        check("acento '%s' presente" % c, acha(kb, c) is not None)
    for c in "ÁÀÂÉÊÍÓÔÕÚÜ":
        check("acento maiusculo '%s' presente" % c, acha(kb, c) is not None)

    sh.recebido = []
    for label in ("ã", "ç", "_"):
        toca(sh, kb, label)
    check("acentos e '_' chegam ao shell",
          sh.recebido == ["ã", "ç", "_"], "-> %s" % sh.recebido)

    toca(sh, kb, "ABC")
    check("ABC volta para as letras", kb.symbols is False)


def test_teclas_especiais():
    print("\n=== teclas especiais ===")
    sh, kb = novo_teclado()
    sh.recebido = []
    toca(sh, kb, "Espaco")
    check("Espaco entrega ' '", sh.recebido == [" "], "-> %s" % sh.recebido)
    toca(sh, kb, "Apagar")
    check("Apagar entrega BackSpace", sh.recebido[-1] == "BackSpace",
          "-> %s" % sh.recebido)
    toca(sh, kb, "Enter")
    check("Enter entrega Return", sh.recebido[-1] == "Return",
          "-> %s" % sh.recebido)

    # o texto acumulado tambem acompanha
    kb.clear()
    check("clear() zera o texto", kb.text == "")


# ----------------------------------------------------------------------
# 3. geometria
# ----------------------------------------------------------------------

def test_geometria():
    print("\n=== geometria (sem sobreposicao, dentro da tela) ===")
    for theme in ("neon", "dark", "minimal", "gamer"):
        sh, kb = novo_teclado(theme)
        sobre = 0
        for i in range(len(kb.keys)):
            a = kb.keys[i]
            for j in range(i + 1, len(kb.keys)):
                b = kb.keys[j]
                if (a.x < b.x + b.w and b.x < a.x + a.w and
                        a.y < b.y + b.h and b.y < a.y + a.h):
                    sobre += 1
        check("[%s] nenhuma tecla se sobrepoe" % theme, sobre == 0,
              "-> %d" % sobre)

        topo = min(k.y for k in kb.keys)
        base = max(k.y + k.h for k in kb.keys)
        check("[%s] teclado dentro da tela" % theme,
              topo >= kb.screen_h - kb.height - 1 and
              base <= kb.screen_h + 1,
              "-> topo=%d base=%d" % (topo, base))
        check("[%s] alvo de toque >= 44 px" % theme,
              min(k.h for k in kb.keys) >= 44,
              "-> %d" % min(k.h for k in kb.keys))


def test_toque():
    print("\n=== semantica do toque ===")
    sh, kb = novo_teclado()

    check("toque fora nao e consumido",
          kb.on_touch(Ev("tap", 100, 100)) is False)

    tecla = acha(kb, "a")
    cx, cy = tecla.x + tecla.w / 2.0, tecla.y + tecla.h / 2.0
    sh.recebido = []
    kb.on_touch(Ev("tap", cx, cy))
    check("tap simples aciona a tecla uma vez", sh.recebido == ["a"],
          "-> %s" % sh.recebido)

    # arrastar para fora da tecla cancela
    k = acha(kb, "a")
    cx, cy = k.x + k.w / 2.0, k.y + k.h / 2.0
    sh.recebido = []
    kb.on_touch(Ev("down", cx, cy))
    kb.on_touch(Ev("up", cx, cy - 400))
    check("arrastar para fora cancela a tecla", sh.recebido == [],
          "-> %s" % sh.recebido)

    # down+up na mesma tecla dispara
    kb.on_touch(Ev("down", cx, cy))
    kb.on_touch(Ev("up", cx, cy))
    check("down+up na mesma tecla dispara", sh.recebido == ["a"],
          "-> %s" % sh.recebido)

    # teclado escondido nao consome nada
    kb.visible = False
    check("teclado escondido ignora o toque",
          kb.on_touch(Ev("tap", cx, cy)) is False)


def test_liberacao_input_reader():
    print("\n=== evdev: soltar o dedo gera evento up ===")
    reader = InputReader()
    reader.slots = {0: (500, 900)}
    reader._touch_state_known = True
    reader.touching = True

    out = []
    reader._sync(1.0, out)
    check("primeiro sync informa down", len(out) == 1 and out[0].type == "down")

    # Firmware que mantem o slot ate o BTN_TOUCH=0.
    reader.touching = False
    out = []
    reader._sync(1.1, out)
    check("BTN_TOUCH=0 informa up", len(out) == 1 and out[0].type == "up")

    # Firmware que remove o slot MT ao soltar.
    reader.touching = True
    reader.slots = {0: (500, 900)}
    out = []
    reader._sync(2.0, out)
    reader.slots.clear()
    out = []
    reader._sync(2.1, out)
    check("slot removido informa up", len(out) == 1 and out[0].type == "up")


# ----------------------------------------------------------------------
# 4. desenho
# ----------------------------------------------------------------------

def test_draw():
    print("\n=== desenho ===")
    import cairo
    for theme in ("neon", "dark", "minimal", "gamer"):
        sh, kb = novo_teclado(theme)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
        ctx = cairo.Context(surf)
        from nura_ui import Painter
        p = Painter(ctx, sh.theme)
        kb.draw(p)
        # com shift e com a camada de simbolos
        kb.shift = True
        kb._layout()
        kb.draw(p)
        kb.symbols = True
        kb._layout()
        kb.draw(p)
        check("[%s] desenha nos 3 estados" % theme, True)


# ----------------------------------------------------------------------
# 5. caminho completo: teclado -> shell -> Terminal
# ----------------------------------------------------------------------

def test_integracao_terminal():
    print("\n=== integracao: Shift+'-' digitado no Terminal ===")
    mock = "/tmp/nura-test-keyboard.mock"
    with open(mock, "wb") as f:
        f.truncate(4352 * 1920)
    try:
        from nura_shell import NuraShell
    except Exception as e:                                  # pragma: no cover
        print("  [SKIP] shell indisponivel: %s" % e)
        return

    sh = NuraShell(mock=mock)
    win = sh.open_app("terminal")
    if win is None:
        print("  [SKIP] Terminal indisponivel neste ambiente")
        sh.fb.close()
        return
    term = win.app
    kb = sh.keyboard
    sh.render()
    x, y, w, h = term._layout()["input"]
    sh._dispatch(TouchEvent("down", x + w // 2, y + h // 2, time=0.1))
    sh._dispatch(TouchEvent("up", x + w // 2, y + h // 2, time=0.2))
    check("toque na linha de comando abre o teclado",
          kb.visible and sh.key_focus is term)
    kb.symbols = False
    kb.shift = False
    kb._layout()
    term.input_line = ""
    term.input_pos = 0

    toca_pelo_shell(sh, kb, "Shift", 1.0)
    check("shift ligado no teclado do shell", kb.shift is True)
    check("shift continua ligado depois de soltar", kb.shift is True)
    toca_pelo_shell(sh, kb, "_", 2.0)
    check("Terminal recebeu '_' na linha de comando",
          "_" in term.input_line, "-> %r" % term.input_line)
    check("shift desliga depois da tecla modificada", kb.shift is False)

    # uma letra maiuscula tambem
    toca_pelo_shell(sh, kb, "Shift", 3.0)
    toca_pelo_shell(sh, kb, "A", 4.0)
    check("Terminal recebeu 'A'", "A" in term.input_line,
          "-> %r" % term.input_line)

    sh.close_window(win)
    check("fechar o Terminal libera o teclado",
          not kb.visible and sh.key_focus is None)

    sh.fb.close()
    try:
        os.unlink(mock)
    except OSError:
        pass


# ----------------------------------------------------------------------

def main():
    print("NURA OS - testes do teclado virtual")
    test_shift_simbolos()
    test_shift_numeros()
    test_shift_pontuacao()
    test_shift_letras()
    test_camada_simbolos()
    test_teclas_especiais()
    test_geometria()
    test_toque()
    test_liberacao_input_reader()
    test_draw()
    test_integracao_terminal()

    print("\n" + "=" * 50)
    if falhas:
        print("FALHAS: %s" % falhas)
        sys.exit(1)
    print("TODOS OS TESTES PASSARAM")


if __name__ == "__main__":
    main()
