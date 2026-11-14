#!/usr/bin/env python3
"""NURA OS — teste de integracao do NURA Shell.

Roda sem aparelho: usa um arquivo como framebuffer falso.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import cairo  # noqa: E402

import nura_theme as T  # noqa: E402
from nura_fb import Framebuffer  # noqa: E402
from nura_input import TouchEvent  # noqa: E402
from nura_shell import DESK_W, DESK_H, NuraShell  # noqa: E402

MOCK = "/tmp/nura-test-shell.mock"
STRIDE = 4352

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)


def novo_shell():
    with open(MOCK, "wb") as f:
        f.truncate(STRIDE * 1920)
    return NuraShell(mock=MOCK)


def test_render():
    print("\n=== renderizacao da area de trabalho ===")
    sh = novo_shell()
    t0 = time.time()
    sh.render()          # primeiro quadro: inclui o cache do fundo
    t1 = time.time()
    for _ in range(5):
        sh.render()
    dt = (time.time() - t1) / 5
    check("render() nao lanca excecao", True)
    # Limite generoso: pega regressao patologica. O gate real de
    # desempenho e o benchmark NO APARELHO (nura_shell.py --bench=30),
    # porque aqui o cairo roda em x86 ou em aarch64 emulado (qemu), que
    # e varias vezes mais lento que o A53 real.
    print("      render em regime: %.1f ms" % (dt * 1000))
    check("render em regime < 250 ms (%.1f ms)" % (dt * 1000), dt < 0.25)
    # a superficie tem o tamanho certo
    check("superficie 1920x1080",
          sh.surface.get_width() == DESK_W and sh.surface.get_height() == DESK_H)
    # apresentar no framebuffer mock e conferir que houve pixels
    sh.tick()
    data = open(MOCK, "rb").read()
    distintos = len(set(data[0:400000:4]))
    check("framebuffer recebeu conteudo (%d tons distintos)" % distintos,
          distintos > 3)
    sh.fb.close()


def test_temas():
    print("\n=== temas ===")
    sh = novo_shell()
    for nome in T.THEME_NAMES:
        sh.theme.reload(nome)
        try:
            sh.bg_surface = None
            sh.render()
            ok = True
        except Exception as e:
            ok = False
            print("      erro no tema %s: %s" % (nome, e))
        check("tema %s renderiza" % nome, ok)
    sh.theme.reload("neon")
    sh.bg_surface = None
    sh.fb.close()


def test_toques():
    print("\n=== toques na area de trabalho ===")
    sh = novo_shell()
    alvos = [(20, 20), (100, 100), (960, 540), (1900, 1070), (200, 60),
             (1830, 40), (500, 1040), (1000, 1040)]
    tipos = ["down", "up", "move", "drag", "tap", "longpress", "scroll"]
    erro = None
    for (x, y) in alvos:
        for t in tipos:
            try:
                ev = TouchEvent(t, x, y, dx=1, dy=1, amount=10, time=time.time())
                sh.on_touch(ev)
            except Exception as e:
                erro = "%s em (%d,%d): %s" % (t, x, y, e)
                break
        if erro:
            break
    check("nenhum toque levantou excecao", erro is None, erro or "")
    sh.fb.close()


def test_icones_e_barra():
    print("\n=== icones e barra de tarefas ===")
    sh = novo_shell()
    sh.render()
    # icones da area de trabalho (coluna esquerda)
    sh.on_touch(TouchEvent("tap", 60, 60, time=time.time()))     # 1o icone
    check("abrir Computador nao lanca", True)
    sh.on_touch(TouchEvent("tap", 60, 300, time=time.time()))    # Terminal
    check("abrir Terminal nao lanca", True)
    # botao Iniciar (canto inferior esquerdo)
    sh.on_touch(TouchEvent("tap", 36, DESK_H - 30, time=time.time()))
    check("menu Iniciar abre", sh.start_open)
    sh.render()
    sh.on_touch(TouchEvent("tap", 36, DESK_H - 30, time=time.time()))
    check("menu Iniciar fecha", not sh.start_open)
    sh.fb.close()


def test_janelas():
    print("\n=== janelas ===")
    sh = novo_shell()
    sh.open_app("terminal")
    check("janela criada", len(sh.windows) == 1)
    win = sh.windows[0]
    sh.render()
    # arrastar pela barra de titulo
    sh.on_touch(TouchEvent("down", win.x + 40, win.y + 10))
    sh.on_touch(TouchEvent("drag", win.x + 140, win.y + 60, dx=100, dy=50))
    sh.on_touch(TouchEvent("up", win.x + 140, win.y + 60))
    check("janela moveu (%d,%d)" % (win.x, win.y), win.x > 100)
    # redimensionar pela borda inferior direita
    old_w = win.w
    sh.on_touch(TouchEvent("down", win.x + win.w - 5, win.y + win.h - 5))
    sh.on_touch(TouchEvent("drag", win.x + win.w + 60, win.y + win.h + 30,
                           dx=60, dy=30))
    sh.on_touch(TouchEvent("up", win.x + win.w + 60, win.y + win.h + 30))
    check("janela redimensionou (%d -> %d)" % (old_w, win.w), win.w > old_w)
    sh.render()
    x, y, w, h = win.close_button_rect()
    check("botao fechar tem alvo de pelo menos 44 px", w >= 44 and h >= 44)
    sh.set_key_focus(win.app)
    sh._dispatch(TouchEvent("down", x + w // 2, y + h // 2, time=1.0))
    check("janela permanece aberta enquanto o dedo esta na tela", win in sh.windows)
    sh._dispatch(TouchEvent("up", x + w // 2, y + h // 2, time=1.1))
    check("toque no X fecha a janela e o teclado",
          not sh.windows and not sh.keyboard.visible and sh.key_focus is None)
    sh.fb.close()


def test_dialogo_confirmacao():
    print("\n=== dialogo de confirmacao ===")
    sh = novo_shell()
    chamadas = []
    sh.confirm("Teste", "Confirma?", lambda: chamadas.append(1))
    sh.render()
    rects = getattr(sh, "confirm_rects", {})
    check("dialogo desenhou os botoes", "ok" in rects and "cancel" in rects)
    if "cancel" in rects:
        x, y, w, h = rects["cancel"]
        sh.on_touch(TouchEvent("tap", x + w / 2, y + h / 2))
        check("cancelar nao executa a acao", chamadas == [])
    sh.confirm("Teste", "Confirma?", lambda: chamadas.append(1))
    sh.render()
    x, y, w, h = getattr(sh, "confirm_rects", {})["ok"]
    sh.on_touch(TouchEvent("tap", x + w / 2, y + h / 2))
    check("confirmar executa a acao", chamadas == [1])
    sh.fb.close()


def test_notificacoes():
    print("\n=== notificacoes ===")
    sh = novo_shell()
    sh.notify("mensagem de teste", "warn")
    sh.render()
    check("notificacao registrada", len(sh.notices) == 1)
    sh.fb.close()


def test_splash():
    print("\n=== animacao de boot (splash) ===")
    try:
        from nura_splash import Splash
    except Exception as e:
        check("import do splash", False, str(e))
        return
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "assets", "splash")
    sp = Splash(dirs=[here])
    check("frames da animacao encontrados (%d)" % sp.frame_count(),
          sp.frame_count() > 50)
    surf = sp.surface_for()
    sp.draw_frame(0)
    check("frame desenhado sem excecao", True)
    sp.draw_procedural(1.5)
    check("animacao procedural desenhada sem excecao", True)
    # tempo de carga de um frame (amostra)
    t0 = time.time()
    for i in range(10):
        sp.load_frame(i)
    dt = (time.time() - t0) / 10
    check("carga de frame < 40 ms (%.1f ms)" % (dt * 1000), dt < 0.04)


def test_recuperacao():
    print("\n=== modulo de recuperacao ===")
    try:
        import nura_recovery as R
    except Exception as e:
        check("import da recuperacao", False, str(e))
        return
    import tempfile
    tmp = tempfile.mkdtemp()
    arquivo = os.path.join(tmp, "state.json")
    R.STATE_FILE = arquivo
    R.STATE_DIR = tmp
    R.BACKUP_DIR = os.path.join(tmp, "backup")
    R._ensure_dirs()
    R.reset_failures()
    check("falhas comecam em zero", R.consecutive_failures() == 0)
    R.record_failure("teste 1")
    R.record_failure("teste 2")
    check("falhas acumulam", R.consecutive_failures() == 2)
    check("nao ha fallback com 2 falhas", not R.should_fallback())
    R.record_failure("teste 3")
    check("fallback com 3 falhas", R.should_fallback())
    R.record_success()
    check("sucesso zera a contagem", R.consecutive_failures() == 0)
    check("estado salvo em disco", os.path.exists(arquivo))


if __name__ == "__main__":
    print("NURA OS — teste de integracao do shell")
    test_render()
    test_temas()
    test_toques()
    test_icones_e_barra()
    test_janelas()
    test_dialogo_confirmacao()
    test_notificacoes()
    test_splash()
    test_recuperacao()
    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS (%d): %s" % (len(falhas), falhas)))
    sys.exit(1 if falhas else 0)
