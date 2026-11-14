#!/usr/bin/env python3
"""NURA OS - testes do NURA Explorer (gerenciador de arquivos).

Roda sem aparelho e sem pytest:

    python3 test_explorer.py

Saida: "TODOS OS TESTES PASSARAM" (exit 0) ou a lista de falhas (exit 1).

Sobre a camada de arquivos:

  * se `nura_filemgr.py` existir, ele e usado DE VERDADE: o teste cria
    uma arvore temporaria e valida listagem, selecao, novo item,
    renomear, copiar/colar e exclusao com confirmacao;
  * se ainda nao existir, o teste injeta um modulo falso em
    `sys.modules` com uma implementacao minima do contrato, para o
    Explorer poder ser exercitado do mesmo jeito.
"""

import os
import shutil
import sys
import tempfile
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import cairo  # noqa: E402

from nura_input import TouchEvent  # noqa: E402
from nura_theme import Theme  # noqa: E402
from nura_ui import Painter  # noqa: E402
from nura_window import Window  # noqa: E402

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)
    return bool(cond)


# ----------------------------------------------------------------------
# camada de arquivos: real ou falsa
# ----------------------------------------------------------------------

class FakeFileManager(object):
    """Implementacao minima do contrato `nura_filemgr` (arvore real)."""

    def __init__(self, root=None):
        self.root = root or os.getcwd()
        self.log = []

    def listdir(self, path=None, show_hidden=False):
        path = path or self.root
        out = []
        for name in sorted(os.listdir(path)):
            if name.startswith(".") and not show_hidden:
                continue
            full = os.path.join(path, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            out.append({"name": name, "path": full,
                        "is_dir": os.path.isdir(full),
                        "is_link": os.path.islink(full),
                        "size": 0 if os.path.isdir(full) else st.st_size,
                        "mtime": st.st_mtime})
        return out

    def stat_info(self, path):
        st = os.stat(path)
        return {"name": os.path.basename(path), "path": path,
                "type": "dir" if os.path.isdir(path) else "file",
                "is_dir": os.path.isdir(path), "size": st.st_size,
                "mtime": st.st_mtime, "ctime": st.st_ctime,
                "mode": st.st_mode, "uid": st.st_uid, "gid": st.st_gid}

    def copy(self, src, dst):
        self.log.append(("copy", src, dst))
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return dst

    def move(self, src, dst):
        self.log.append(("move", src, dst))
        shutil.move(src, dst)
        return dst

    def rename(self, path, new_name):
        """Mesma convencao do nura_filemgr real: nome novo, mesmo diretorio."""
        self.log.append(("rename", path, new_name))
        destino = os.path.join(os.path.dirname(path.rstrip("/")), new_name)
        os.rename(path, destino)
        return destino

    def mkdir(self, path):
        self.log.append(("mkdir", path))
        os.mkdir(path)
        return path

    def delete(self, path, recursive=False, confirm=False):
        self.log.append(("delete", path, recursive, confirm))
        if not confirm:
            raise PermissionError("exclusao exige confirmacao explicita")
        if os.path.isdir(path):
            if not recursive:
                raise PermissionError("diretorio nao vazio")
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True

    def du(self, path):
        total = 0
        arquivos = 0
        for base, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(base, f))
                    arquivos += 1
                except OSError:
                    pass
        return {"total_bytes": total, "files": arquivos, "dirs": 0}

    def storage(self):
        u = shutil.disk_usage(self.root)
        return [{"mount": "/", "total": u.total, "used": u.used,
                 "free": u.free, "used_pct": (u.used * 100.0 / u.total
                                              if u.total else None)}]

    def mounts(self):
        return [{"mount": "/"}]

    def removable_devices(self):
        return []

    def search(self, pattern, root=None):
        root = root or self.root
        out = []
        for base, dirs, files in os.walk(root):
            for n in list(files) + list(dirs):
                if pattern in n:
                    full = os.path.join(base, n)
                    out.append({"name": n, "path": full,
                                "is_dir": os.path.isdir(full), "size": 0})
        return out

    def open_with(self, path):
        return []

    def recent_files(self):
        return []

    def operation_log(self):
        return list(self.log)


def install_fake_filemgr():
    mod = types.ModuleType("nura_filemgr")
    mod.FileManager = FakeFileManager
    mod.__doc__ = "modulo falso de teste (nura_filemgr ainda nao existe)"
    sys.modules["nura_filemgr"] = mod
    return mod


try:
    import nura_filemgr  # noqa: F401
    REAL_FILEMGR = True
except ImportError:
    REAL_FILEMGR = False
    install_fake_filemgr()

import nura_explorer  # noqa: E402
from nura_explorer import ExplorerApp, ImageViewerApp  # noqa: E402

if REAL_FILEMGR:
    from nura_filemgr import FileManager
else:
    FileManager = FakeFileManager


# ----------------------------------------------------------------------
# shell falso
# ----------------------------------------------------------------------

class FakeShell(object):
    """Shell minimo: implementa a parte do contrato usada pelo Explorer."""

    def __init__(self, filemgr=None):
        self.theme = Theme("neon")
        self.filemgr = filemgr
        self.notices = []
        self.confirms = []
        self.launched = []
        self.opened = []

    def notify(self, msg, kind="info"):
        self.notices.append((msg, kind))

    def confirm(self, title, message, on_ok):
        self.confirms.append((title, message, on_ok))

    def open_app(self, app, **kw):
        self.opened.append(app)
        try:
            app.on_open()
        except Exception:
            pass
        return app

    def launch(self, cmd):
        self.launched.append(cmd)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def render(app, w=1920, h=1080):
    """Desenha o app num contexto cairo 1920x1080."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    p = Painter(ctx, app._theme())
    app.draw(p)
    surf.flush()
    return surf


def make_app(shell, root=None, w=1100, h=680):
    app = ExplorerApp(shell=shell)
    Window(app, 100, 80, w, h, shell=shell)
    app.on_open()
    if root:
        app._load_dir(root, history=True)
    app._layout()
    return app


def make_fm(root):
    """Instancia a camada de arquivos sem gravar log em disco."""
    try:
        return FileManager(root=root, log_to_file=False)
    except TypeError:
        return FileManager(root=root)


def tap(app, x, y):
    app.on_touch(TouchEvent("tap", x, y, time=1.0))


def tap_entry(app, idx):
    """Toca na linha `idx` da lista (posicao real na tela)."""
    mx, my, mw, mh = app._rects["main"]
    y = my + 34 + idx * 56 + 28
    tap(app, mx + 60, y)
    return idx


def entry_index(app, name):
    for i, e in enumerate(app.entries):
        if e["name"] == name:
            return i
    return -1


def write_png(path, w=24, h=24):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0.10, 0.85, 0.98)
    ctx.paint()
    surf.write_to_png(path)
    surf.flush()


# ----------------------------------------------------------------------
# testes
# ----------------------------------------------------------------------

def test_metadados():
    print("\n=== metadados do aplicativo ===")
    check("titulo", ExplorerApp.title == "NURA Explorer", ExplorerApp.title)
    check("icone", ExplorerApp.icon == "folder", ExplorerApp.icon)
    check("tamanho 1100x680",
          ExplorerApp.width == 1100 and ExplorerApp.height == 680)
    check("tamanho minimo 640x420",
          ExplorerApp.min_width == 640 and ExplorerApp.min_height == 420)
    app = ExplorerApp(shell=FakeShell())
    check("estado inicial completo",
          app.entries == [] and app.scroll == 0.0 and app.selected == -1 and
          app.show_hidden is False and app.view_mode == "lista" and
          app.clipboard == {} and app.dialog is None, vars(app))


def test_draw_sem_excecao():
    print("\n=== instancia + draw() em cairo 1920x1080 ===")
    shell = FakeShell()
    try:
        app = ExplorerApp(shell=shell)
        Window(app, 100, 80, 1100, 680, shell=shell)
        app.on_open()
        surf = render(app)
        check("draw() nao levanta excecao", True)
        check("superficie 1920x1080 criada",
              surf.get_width() == 1920 and surf.get_height() == 1080)
        # janela minima (640x420) tambem desenha
        app2 = ExplorerApp(shell=shell)
        Window(app2, 10, 10, 640, 420, shell=shell)
        app2.on_open()
        render(app2)
        check("draw() na janela minima (640x420)", True)
        # modo grade
        app.view_mode = "icones"
        render(app)
        check("draw() no modo grade", True)
        # dialogo aberto (teclado virtual) desenha
        app.dialog = {"kind": "renomear", "path": "/tmp/x", "field": "abc"}
        render(app)
        check("draw() com dialogo aberto", True)
        app.dialog = None
        # overlay e barra de acoes
        app.action_bar = {"path": "/tmp/x", "name": "x"}
        app.overlay = {"kind": "dispositivos", "devices": [], "mounts": []}
        render(app)
        check("draw() com overlay e barra de acoes", True)
    except Exception as e:
        check("draw() nao levanta excecao", False, repr(e))


def test_toque_fora_dos_itens():
    print("\n=== toque fora de qualquer item ===")
    shell = FakeShell()
    app = make_app(shell)
    try:
        pontos = [(5, 5), (1900, 1075), (960, 1079), (1919, 0),
                  (app._rects["main"][0] + 5, app._rects["main"][1] + 5)]
        for (x, y) in pontos:
            tap(app, x, y)
        check("tap fora de qualquer item nao levanta", True)
        # outros gestos
        app.on_touch(TouchEvent("drag", 900, 500, dx=0, dy=-40))
        app.on_touch(TouchEvent("scroll", 900, 500, amount=120))
        app.on_touch(TouchEvent("longpress", 900, 500))
        app.on_touch(TouchEvent("down", 100, 100))
        app.on_touch(TouchEvent("up", 100, 100))
        app.on_touch(TouchEvent("pinch", 900, 500, scale=1.2))
        check("drag/scroll/longpress/down/up nao levantam", True)
        app.on_tick(0.016)
        check("on_tick nao levanta", True)
    except Exception as e:
        check("tap fora de qualquer item nao levanta", False, repr(e))


def test_modo_degradado():
    print("\n=== modo degradado (nura_filemgr ausente) ===")
    saved = nura_explorer.FileManager
    nura_explorer.FileManager = None
    try:
        shell = FakeShell()          # sem filemgr no shell
        app = ExplorerApp(shell=shell)
        Window(app, 100, 80, 1100, 680, shell=shell)
        app.on_open()
        render(app)
        check("app abre sem crash", True)
        msg = (app.error + " " + app.status).lower()
        check("mostra 'modulo de arquivos indisponivel'",
              "indisponivel" in msg, msg)
        check("lista fica vazia", app.entries == [], app.entries)
        # um toque em qualquer lugar nao pode quebrar
        tap(app, 400, 400)
        tap(app, 100, 100)
        render(app)
        check("toque no modo degradado nao quebra", True)
    except Exception as e:
        check("app abre sem crash", False, repr(e))
    finally:
        nura_explorer.FileManager = saved


def test_operacoes_de_arquivo():
    print("\n=== listagem, selecao, novo, renomear, copiar/colar, excluir ===")
    origem = ("modulo real nura_filemgr" if REAL_FILEMGR
              else "modulo falso de teste")
    print("  (usando %s)" % origem)
    root = tempfile.mkdtemp(prefix="nura-explorer-")
    try:
        os.mkdir(os.path.join(root, "subdir"))
        with open(os.path.join(root, "alfa.txt"), "w") as f:
            f.write("0123456789")
        write_png(os.path.join(root, "beta.png"))
        with open(os.path.join(root, ".oculto"), "w") as f:
            f.write("x")

        fm = make_fm(root)
        shell = FakeShell(filemgr=fm)
        app = make_app(shell, root=root)

        # --- listagem ---
        nomes = sorted(e["name"] for e in app.entries)
        check("listagem traz os itens reais",
              nomes == ["alfa.txt", "beta.png", "subdir"], nomes)
        check("pastas vem primeiro",
              app.entries[0]["name"] == "subdir", app.entries[0]["name"])
        check("ocultos ficam de fora por padrao",
              ".oculto" not in nomes, nomes)
        check("cwd e o caminho atual", app.cwd == root, app.cwd)
        check("tamanho do arquivo lido",
              any(e["name"] == "alfa.txt" and e["size"] == 10
                  for e in app.entries),
              [e for e in app.entries if e["name"] == "alfa.txt"])

        # --- ocultos ---
        app.show_hidden = True
        app._load_dir(root, history=False)
        check("mostrar ocultos inclui .oculto",
              ".oculto" in [e["name"] for e in app.entries],
              [e["name"] for e in app.entries])
        app.show_hidden = False
        app._load_dir(root, history=False)

        # --- selecao por toque ---
        idx = entry_index(app, "alfa.txt")
        tap_entry(app, idx)
        check("toque seleciona o item",
              app.selected == idx and
              app.entries[app.selected]["name"] == "alfa.txt",
              app.selected)

        # --- novo item (pasta) ---
        app.dialog = {"kind": "novo_pasta", "field": "novapasta",
                      "mode": "pasta"}
        app._dlg_action("ok")
        check("nova pasta criada",
              os.path.isdir(os.path.join(root, "novapasta")))

        # --- renomear ---
        app._load_dir(root, history=False)
        idx = entry_index(app, "alfa.txt")
        app.selected = idx
        target = app.entries[idx]["path"]
        app.dialog = {"kind": "renomear", "path": target, "field": "alfa2.txt"}
        app._dlg_action("ok")
        check("arquivo renomeado",
              os.path.isfile(os.path.join(root, "alfa2.txt")) and
              not os.path.exists(target))

        # --- copiar / colar ---
        app._load_dir(root, history=False)
        idx = entry_index(app, "alfa2.txt")
        app.selected = idx
        app._copy(app.entries[idx]["path"])
        check("copia registra a area de transferencia",
              app.clipboard.get("acao") == "copiar" and
              app.clipboard.get("path", "").endswith("alfa2.txt"),
              app.clipboard)
        app._navigate(os.path.join(root, "subdir"))
        check("navegou para a subpasta",
              app.cwd == os.path.join(root, "subdir"), app.cwd)
        app._paste()
        check("colar copiou o arquivo",
              os.path.isfile(os.path.join(root, "subdir", "alfa2.txt")))

        # --- exclusao com confirmacao (shell.confirm) ---
        deletes = []
        orig_delete = fm.delete

        def spy(path, *a, **kw):
            deletes.append((path, a, kw))
            return orig_delete(path, *a, **kw)

        fm.delete = spy
        victim = os.path.join(root, "alfa2.txt")
        shell.confirms.clear()
        app._load_dir(root, history=False)
        app._ask_delete(victim)
        check("exclusao pede confirmacao antes de executar",
              len(shell.confirms) == 1 and os.path.exists(victim),
              shell.confirms)
        if shell.confirms:
            shell.confirms[0][2]()      # o usuario confirma
        check("arquivo excluido apos a confirmacao",
              not os.path.exists(victim))
        ok_confirm = False
        if deletes:
            path, a, kw = deletes[-1]
            ok_confirm = (kw.get("confirm") is True or
                          (len(a) >= 3 and a[2] is True) or
                          (len(a) >= 2 and a[1] is True))
        check("delete chamado com confirm=True", ok_confirm, deletes)

        # --- exclusao sem shell: dialogo proprio ---
        fm.delete = orig_delete
        victim2 = os.path.join(root, "beta.png")
        app.shell = None
        app._ask_delete(victim2)
        check("sem shell abre o dialogo de exclusao",
              app.dialog is not None and app.dialog.get("kind") == "excluir",
              app.dialog)
        app._layout()
        btn = [b for b in app._modal_btns if b["id"] == "dlg:delete"]
        check("dialogo tem o botao Excluir", len(btn) == 1)
        if btn:
            r = btn[0]["rect"]
            app.on_touch(TouchEvent("tap", r[0] + 5, r[1] + 5, time=2.0))
        check("exclusao confirmada no dialogo proprio",
              not os.path.exists(victim2))
        app.shell = shell
    except Exception as e:
        import traceback
        traceback.print_exc()
        check("fluxo de operacoes de arquivo", False, repr(e))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_imagem_e_visualizador():
    print("\n=== visualizador de imagens ===")
    root = tempfile.mkdtemp(prefix="nura-explorer-img-")
    try:
        write_png(os.path.join(root, "foto.png"))
        with open(os.path.join(root, "foto.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0 nao e um jpeg de verdade")
        fm = make_fm(root)
        shell = FakeShell(filemgr=fm)
        app = make_app(shell, root=root)

        idx = entry_index(app, "foto.png")
        tap_entry(app, idx)
        tap_entry(app, idx)          # segundo toque: abre
        check("toque em imagem abre o visualizador",
              app.viewer is not None)
        if app.viewer is not None:
            check("PNG carregado pelo cairo", app.viewer.surface is not None,
                  app.viewer.error)
            render(app.viewer)
            check("visualizador desenha sem excecao", True)

        # JPEG: aviso honesto, sem fingir que abriu
        v = ImageViewerApp(path=os.path.join(root, "foto.jpg"))
        check("JPEG: 'formato nao suportado'",
              v.surface is None and "nao suportado" in v.error, v.error)
        render(v)
        check("visualizador de JPEG nao quebra", True)

        # arquivo que nao existe
        v2 = ImageViewerApp(path=os.path.join(root, "nao-existe.png"))
        check("arquivo inexistente reporta erro", bool(v2.error), v2.error)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check("visualizador de imagens", False, repr(e))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_sem_programas():
    print("\n=== 'Abrir com' (comandos reais ou aviso honesto) ===")
    root = tempfile.mkdtemp(prefix="nura-explorer-open-")
    try:
        with open(os.path.join(root, "nota.txt"), "w") as f:
            f.write("ola")
        fm = make_fm(root)
        shell = FakeShell(filemgr=fm)
        app = make_app(shell, root=root)
        path = os.path.join(root, "nota.txt")
        idx = entry_index(app, "nota.txt")
        tap_entry(app, idx)
        tap_entry(app, idx)          # segundo toque: abre

        # caso 1: a camada devolve comandos -> o overlay lista exatamente
        # esses comandos (nada inventado)
        cmds = app._read_open_with(path)
        if cmds:
            comandos = [c["cmd"] for c in cmds]
            check("overlay 'Abrir com' aberto",
                  app.overlay is not None and
                  app.overlay.get("kind") == "abrir_com", app.overlay)
            check("lista exatamente os comandos da camada",
                  [c["cmd"] for c in (app.overlay or {}).get("commands", [])]
                  == comandos, comandos)
            check("nao inventa comando",
                  all(c["cmd"] in comandos
                      for c in (app.overlay or {}).get("commands", [])))
        else:
            msg = " ".join(m[0] for m in shell.notices).lower()
            check("informa que nao ha programa disponivel",
                  "nenhum programa disponivel" in msg, msg)

        # caso 2: a camada nao encontra nenhum abridor -> aviso honesto
        orig_open = fm.open_with
        fm.open_with = lambda *a, **k: []
        app.overlay = None
        shell.notices.clear()
        tap_entry(app, idx)
        tap_entry(app, idx)
        msg = " ".join(m[0] for m in shell.notices).lower()
        check("sem programa: 'nenhum programa disponivel'",
              "nenhum programa disponivel" in msg, msg)
        check("nao inventa comando", not shell.launched, shell.launched)
        fm.open_with = orig_open
    except Exception as e:
        check("'Abrir com'", False, repr(e))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_busca_teclado_e_atalhos():
    print("\n=== busca, teclado virtual e atalhos ===")
    root = tempfile.mkdtemp(prefix="nura-explorer-busca-")
    try:
        os.mkdir(os.path.join(root, "Documentos"))
        with open(os.path.join(root, "alfa.txt"), "w") as f:
            f.write("x")
        with open(os.path.join(root, "Documentos", "beta.txt"), "w") as f:
            f.write("x")
        fm = make_fm(root)
        shell = FakeShell(filemgr=fm)
        app = make_app(shell, root=root)

        # botao "Pesquisar" do cabecalho
        app._do_button("buscar")
        check("overlay de busca aberto",
              app.overlay is not None and
              app.overlay.get("kind") == "buscar", app.overlay)

        # teclado virtual (toque nas teclas)
        for ch in "alfa":
            app._kb_press(ch)
        check("teclado virtual preenche o campo",
              app.overlay.get("text") == "alfa", app.overlay.get("text"))
        app._kb_press("back")
        check("tecla de apagar funciona",
              app.overlay.get("text") == "alf", app.overlay.get("text"))

        # confirma a busca pelo botao do modal
        app._do_button("dlg:ok")
        res = app.overlay.get("results") or []
        check("busca devolve o arquivo real",
              any(r["name"] == "alfa.txt" for r in res),
              [r["name"] for r in res])
        render(app)
        check("overlay de resultados desenha", True)

        # atalho da barra lateral (Home)
        app._do_button("sc:0")
        check("atalho Home navega para a home",
              app.cwd == os.path.expanduser("~"), app.cwd)

        # voltar (historico)
        app._do_button("voltar")
        check("Voltar refaz o historico", app.cwd == root, app.cwd)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check("busca/teclado/atalhos", False, repr(e))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    print("NURA OS - testes do NURA Explorer")
    print("camada de arquivos: %s" %
          ("nura_filemgr real" if REAL_FILEMGR else "modulo falso de teste"))
    test_metadados()
    test_draw_sem_excecao()
    test_toque_fora_dos_itens()
    test_modo_degradado()
    test_operacoes_de_arquivo()
    test_imagem_e_visualizador()
    test_sem_programas()
    test_busca_teclado_e_atalhos()
    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS (%d): %s" % (len(falhas), falhas)))
    sys.exit(1 if falhas else 0)
