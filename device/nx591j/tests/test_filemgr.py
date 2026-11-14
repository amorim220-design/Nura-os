#!/usr/bin/env python3
"""NURA OS — testes do gerenciador de arquivos (nura_filemgr).

Roda sem o aparelho e sem pytest:

    python3 test_filemgr.py

Cria uma arvore falsa em /tmp e verifica o gerenciador inteiro, com
atencao especial as garantias de seguranca:
  * apagar exige confirm=True;
  * "rm -rf" acidental e bloqueado (recursive=True e caminho protegido);
  * nada sai da raiz (root) da instancia;
  * o log de operacoes so e criado depois de uma operacao de verdade.
"""

import os
import shutil
import stat
import sys
import tempfile

# nao deixa o teste sujar a arvore do projeto com __pycache__
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from nura_filemgr import (  # noqa: E402
    FileManager,
    ConfirmationRequired,
    ProtectedPathError,
    OutsideRootError,
    NotEmptyError,
    human_size,
)

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)


# ---------------------------------------------------------------------------
# arvore de teste
# ---------------------------------------------------------------------------

def montar_arvore(base):
    """Cria a arvore falsa de teste e devolve o dicionario de tamanhos."""
    docs = os.path.join(base, "docs")
    imagem = os.path.join(base, "imagem")
    cache = os.path.join(base, ".cache")
    os.makedirs(docs)
    os.makedirs(imagem)
    os.makedirs(cache)

    with open(os.path.join(docs, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("ola mundo\n")                 # 10 bytes
    with open(os.path.join(docs, "b.png"), "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)   # 108 bytes
    with open(os.path.join(imagem, "foto.jpg"), "wb") as fh:
        fh.write(b"\xff\xd8\xff" + b"\x00" * 50)          # 53 bytes
    with open(os.path.join(base, ".oculto"), "w", encoding="utf-8") as fh:
        fh.write("segredo\n")                            # 8 bytes
    with open(os.path.join(base, "vazio.txt"), "w", encoding="utf-8") as fh:
        pass                                              # 0 bytes
    with open(os.path.join(cache, "temporario.bin"), "wb") as fh:
        fh.write(b"\x00" * 20)                           # 20 bytes
    return {
        "a.txt": 10,
        "b.png": 108,
        "foto.jpg": 53,
        ".oculto": 8,
        "vazio.txt": 0,
        "temporario.bin": 20,
    }


# ---------------------------------------------------------------------------
# testes
# ---------------------------------------------------------------------------

def test_listdir(fm, base):
    print("\n=== listdir (ordenacao e ocultos) ===")
    itens = fm.listdir(base)
    nomes = [i["name"] for i in itens]
    check("diretorios primeiro, arquivos depois, em ordem alfabetica",
          nomes == ["docs", "imagem", "vazio.txt"], "-> %s" % nomes)

    itens_com = fm.listdir(base, show_hidden=True)
    nomes_com = [i["name"] for i in itens_com]
    check("show_hidden=True inclui os ocultos",
          nomes_com == [".cache", "docs", "imagem", ".oculto", "vazio.txt"],
          "-> %s" % nomes_com)

    docs = [i for i in itens_com if i["name"] == "docs"][0]
    check("is_dir verdadeiro para diretorio", docs["is_dir"] is True)
    check("size de diretorio e -1", docs["size"] == -1, "-> %s" % docs["size"])
    check("mtime e timestamp float", isinstance(docs["mtime"], float) and
          docs["mtime"] > 0)
    check("mode traz as permissoes em texto",
          isinstance(docs["mode"], str) and docs["mode"][0] == "d",
          "-> %s" % docs["mode"])
    check("is_link falso para arquivo comum", docs["is_link"] is False)
    check("target e None quando nao e link", docs["target"] is None)

    arq = [i for i in itens_com if i["name"] == "vazio.txt"][0]
    check("size de arquivo vazio e 0", arq["size"] == 0)
    check("is_dir falso para arquivo", arq["is_dir"] is False)


def test_stat_info(fm, base):
    print("\n=== stat_info (metadados) ===")
    a_txt = os.path.join(base, "docs", "a.txt")
    info = fm.stat_info(a_txt)
    check("nome do arquivo", info["name"] == "a.txt", "-> %s" % info["name"])
    check("caminho absoluto", info["path"] == a_txt)
    check("tamanho em bytes", info["size"] == 10, "-> %s" % info["size"])
    check("tamanho legivel pt-BR", info["size_human"] == "10 B",
          "-> %s" % info["size_human"])
    check("tipo do arquivo", info["type"] == "file", "-> %s" % info["type"])
    check("permissao em octal", info["permission"] == "0644",
          "-> %s" % info["permission"])
    check("mtime em ISO", "T" in info["mtime_iso"], "-> %s" % info["mtime_iso"])
    check("dono resolvido (uid/gid->nome)", info["owner"] != "" and
          info["group"] != "")
    check("arquivo texto e is_text", info["is_text"] is True)
    check("arquivo texto nao e is_image", info["is_image"] is False)
    check("hidden falso para nome normal", info["hidden"] is False)

    b_png = fm.stat_info(os.path.join(base, "docs", "b.png"))
    check("png e is_image", b_png["is_image"] is True)
    check("png nao e is_text", b_png["is_text"] is False)

    dirinfo = fm.stat_info(os.path.join(base, "docs"))
    check("tipo de diretorio", dirinfo["type"] == "dir",
          "-> %s" % dirinfo["type"])

    oculto = fm.stat_info(os.path.join(base, ".oculto"))
    check("hidden verdadeiro para nome com ponto", oculto["hidden"] is True)


def test_copy(fm, base):
    print("\n=== copy (copia, mtime, overwrite) ===")
    origem = os.path.join(base, "docs", "a.txt")
    destino = os.path.join(base, "docs", "copia.txt")

    progresso = []
    fm.copy(origem, destino, progress=lambda f, t: progresso.append((f, t)))
    check("arquivo copiado existe", os.path.isfile(destino))
    with open(destino, encoding="utf-8") as fh:
        check("conteudo identico", fh.read() == "ola mundo\n")
    check("mtime preservado",
          os.stat(destino).st_mtime_ns == os.stat(origem).st_mtime_ns,
          "-> %s vs %s" % (os.stat(destino).st_mtime_ns,
                           os.stat(origem).st_mtime_ns))
    check("permissao preservada",
          stat.S_IMODE(os.stat(destino).st_mode) ==
          stat.S_IMODE(os.stat(origem).st_mode))
    check("callback de progresso chamado", len(progresso) > 0)

    try:
        fm.copy(origem, destino)
        ok = False
    except FileExistsError:
        ok = True
    check("copy sem overwrite levanta FileExistsError", ok)

    fm.copy(origem, destino, overwrite=True)
    check("copy com overwrite funciona", os.path.isfile(destino))

    # conteudo diferente para provar que o overwrite realmente sobrescreveu
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("X")
    fm.copy(origem, destino, overwrite=True)
    with open(destino, encoding="utf-8") as fh:
        check("overwrite substituiu o conteudo", fh.read() == "ola mundo\n")


def test_rename(fm, base):
    print("\n=== rename (valido e invalido) ===")
    origem = os.path.join(base, "docs", "a.txt")
    novo = os.path.join(base, "docs", "renomeado.txt")
    fm.rename(origem, "renomeado.txt")
    check("arquivo renomeado existe", os.path.isfile(novo))
    check("nome antigo sumiu", not os.path.exists(origem))

    invalidos = ["com/barra", "..", ".", "", "   "]
    for nome in invalidos:
        try:
            fm.rename(novo, nome)
            ok = False
        except ValueError:
            ok = True
        except Exception as erro:          # noqa: BLE001
            ok = False
            print("    (%r -> %s)" % (nome, erro))
        check("rename invalido %r levanta ValueError" % nome, ok)
    check("arquivo continua no lugar apos renomes invalidos",
          os.path.isfile(novo))


def test_mkdir(fm, base):
    print("\n=== mkdir ===")
    novo = os.path.join(base, "nova_pasta")
    fm.mkdir(novo)
    check("diretorio criado", os.path.isdir(novo))
    try:
        fm.mkdir(novo)
        ok = False
    except FileExistsError:
        ok = True
    check("mkdir em caminho existente levanta FileExistsError", ok)
    fundo = os.path.join(base, "a", "b", "c")
    fm.mkdir(fundo, parents=True)
    check("mkdir com parents cria a arvore", os.path.isdir(fundo))

    novo_arq = os.path.join(base, "novo.txt")
    fm.touch(novo_arq)
    check("touch cria arquivo vazio",
          os.path.isfile(novo_arq) and os.path.getsize(novo_arq) == 0)
    try:
        fm.touch(novo_arq)
        ok = False
    except FileExistsError:
        ok = True
    check("touch em arquivo existente levanta FileExistsError", ok)


def test_delete_sem_confirm(fm, base):
    print("\n=== delete (exige confirmacao) ===")
    alvo = os.path.join(base, "docs", "b.png")
    try:
        fm.delete(alvo)
        ok = False
    except ConfirmationRequired:
        ok = True
    except PermissionError:
        ok = True
    check("delete sem confirm levanta excecao", ok)
    check("arquivo AINDA EXISTE apos o delete recusado", os.path.isfile(alvo))
    check("tamanho do arquivo inalterado",
          os.path.getsize(alvo) == 108)


def test_delete_com_confirm(fm, base):
    print("\n=== delete (com confirm=True) ===")
    alvo = os.path.join(base, "docs", "b.png")
    resultado = fm.delete(alvo, confirm=True)
    check("arquivo apagado", not os.path.exists(alvo))
    check("retorna o que foi feito",
          isinstance(resultado, dict) and resultado["ok"] is True and
          resultado["path"] == alvo, "-> %s" % resultado)


def test_delete_diretorio(fm, base):
    print("\n=== delete (diretorio nao vazio) ===")
    alvo = os.path.join(base, "imagem")
    try:
        fm.delete(alvo, confirm=True)
        ok = False
    except NotEmptyError:
        ok = True
    except OSError:
        ok = True
    check("diretorio nao vazio sem recursive=True falha", ok)
    check("diretorio AINDA EXISTE", os.path.isdir(alvo))
    check("conteudo do diretorio intacto",
          os.path.isfile(os.path.join(alvo, "foto.jpg")))

    fm.delete(alvo, confirm=True, recursive=True)
    check("com confirm=True e recursive=True o diretorio some",
          not os.path.exists(alvo))


def test_delete_protegido(fm):
    print("\n=== delete (caminhos protegidos) ===")
    protegidos = ["/", "/etc", "/etc/passwd", "/usr", "/boot", "/proc",
                   "/sys", "/dev", "/var", "/home", "/root", "/bin",
                   "/bootdevice"]
    for caminho in protegidos:
        try:
            fm.delete(caminho, confirm=True, recursive=True)
            ok = False
        except ProtectedPathError:
            ok = True
        except PermissionError:
            ok = True
        except Exception as erro:          # noqa: BLE001
            ok = False
            print("    (%s -> %s: %s)" % (caminho, type(erro).__name__, erro))
        check("delete de %s e recusado" % caminho, ok)
    check("/etc/passwd continua no lugar", os.path.exists("/etc/passwd"))


def test_delete_fora_da_raiz(fm, base, fora):
    print("\n=== delete (fora da raiz da instancia) ===")
    alvo = os.path.join(fora, "fora.txt")
    try:
        fm.delete(alvo, confirm=True)
        ok = False
    except OutsideRootError:
        ok = True
    except PermissionError:
        ok = True
    check("delete fora de root e recusado", ok)
    check("arquivo de fora continua no lugar", os.path.isfile(alvo))


def test_delete_link(fm, base):
    print("\n=== delete (link simbolico) ===")
    alvo_real = os.path.join(base, "docs", "copia.txt")
    link = os.path.join(base, "link.txt")
    if os.path.lexists(link):
        os.unlink(link)
    os.symlink(alvo_real, link)
    fm.delete(link, confirm=True)
    check("link apagado", not os.path.lexists(link))
    check("alvo do link preservado", os.path.isfile(alvo_real))


def test_du(fm, base, tamanhos):
    print("\n=== du (tamanho recursivo) ===")
    docs = os.path.join(base, "docs")
    info = fm.du(docs)
    esperado = tamanhos["a.txt"] + tamanhos["b.png"]
    check("total_bytes correto", info["total_bytes"] == esperado,
          "-> %s (esperado %s)" % (info["total_bytes"], esperado))
    check("contagem de arquivos", info["files"] == 2,
          "-> %s" % info["files"])
    check("contagem de diretorios >= 1", info["dirs"] >= 1,
          "-> %s" % info["dirs"])

    geral = fm.du(base)
    total_esperado = sum(tamanhos.values())
    check("total da arvore inteira", geral["total_bytes"] == total_esperado,
          "-> %s (esperado %s)" % (geral["total_bytes"], total_esperado))

def test_storage(fm):
    print("\n=== storage (uso do disco) ===")
    info = fm.storage("/")
    esperado = {"mount", "total", "used", "free", "used_pct", "label"}
    check("devolve um dict", isinstance(info, dict))
    check("tem todas as chaves", esperado.issubset(set(info)),
          "-> %s" % sorted(info))
    check("total positivo", info["total"] > 0, "-> %s" % info["total"])
    check("free <= total", 0 <= info["free"] <= info["total"])
    check("used_pct entre 0 e 100", 0.0 <= info["used_pct"] <= 100.0,
          "-> %s" % info["used_pct"])


def test_mounts(fm):
    print("\n=== mounts (/proc/mounts) ===")
    lista = fm.mounts()
    check("devolve uma lista", isinstance(lista, list))
    # ambientes sem /proc montado (ex.: chroot de build) nao tem
    # mounts para listar -> o teste nao pode reprovar por isso
    tem_proc = os.path.exists("/proc/mounts") and \
        os.path.getsize("/proc/mounts") > 0
    if tem_proc:
        check("tem entradas", len(lista) > 0, "-> %s" % len(lista))
    else:
        print("  [SKIP] /proc/mounts indisponivel neste ambiente")
    ok_formato = all(isinstance(m, dict) and "mount" in m and "fstype" in m
                      for m in lista)
    check("todas as entradas tem mount e fstype", ok_formato)
    pseudo = [m for m in lista if m.get("fstype") in ("proc", "sysfs", "devpts")]
    check("pseudo-sistemas filtrados", not pseudo, "-> %s" % pseudo)


def test_removable(fm):
    print("\n=== removable_devices ===")
    lista = fm.removable_devices()
    check("devolve uma lista", isinstance(lista, list))
    ok_formato = all(isinstance(d, dict) and "path" in d and "total" in d and
                     "free" in d for d in lista)
    check("entradas com path/total/free", ok_formato)


def test_search(fm, base):
    print("\n=== search (busca por nome) ===")
    achou = fm.search(base, "a.txt")
    nomes = [r["name"] for r in achou]
    check("encontra pelo nome exato", "a.txt" in nomes, "-> %s" % nomes)
    check("resultado tem caminho absoluto",
          all(os.path.isabs(r["path"]) for r in achou))
    achou2 = fm.search(base, "FOTO")
    check("busca ignora maiusculas/minusculas",
          "foto.jpg" in [r["name"] for r in achou2],
          "-> %s" % [r["name"] for r in achou2])
    check("busca sem resultado devolve lista vazia",
          fm.search(base, "zzzznaoexiste") == [])
    limitado = fm.search(base, "", max_results=5)
    check("busca vazia devolve lista vazia", limitado == [])
    muitos = fm.search(base, ".", max_results=2)
    check("max_results respeitado", len(muitos) <= 2, "-> %s" % len(muitos))

def test_open_with(fm, base):
    print("\n=== open_with (sem executar nada) ===")
    alvo = os.path.join(base, "docs", "a.txt")
    comandos = fm.open_with(alvo)
    check("devolve uma lista", isinstance(comandos, list))
    check("todo comando listado existe no PATH",
          all(shutil.which(c) for c in comandos), "-> %s" % comandos)
    imagem = fm.open_with(os.path.join(base, "imagem", "foto.jpg"))
    check("imagem devolve lista", isinstance(imagem, list))


def test_recent(fm):
    print("\n=== recent_files (sem criar arquivo) ===")
    recentes = fm.recent_files()
    check("devolve uma lista", isinstance(recentes, list))
    ok_formato = all(isinstance(r, dict) and "path" in r for r in recentes)
    check("entradas com path", ok_formato)


def test_log(fm_log, base, tmp):
    print("\n=== operation_log (log em memoria e em arquivo) ===")
    log_path = fm_log.log_path
    check("log nao nasce junto com a instancia", not os.path.exists(log_path))

    origem = os.path.join(base, "vazio.txt")
    destino = os.path.join(base, "vazio_copia.txt")
    fm_log.copy(origem, destino)
    check("arquivo de log criado depois da operacao",
          os.path.isfile(log_path))
    entradas = fm_log.operation_log()
    check("operacao registrada em memoria", len(entradas) == 1,
          "-> %s" % len(entradas))
    if entradas:
        e = entradas[0]
        check("entrada tem path/action/timestamp/ok",
              set(["path", "action", "timestamp", "ok"]).issubset(set(e)))
        check("acao registrada", e["action"] == "copy", "-> %s" % e["action"])
        check("marcada como ok", e["ok"] is True)

    # remocao recusada: nao pode apagar, e nao cria arquivo novo de log
    antes = len(open(log_path, encoding="utf-8").read().splitlines())
    alvo = os.path.join(base, "vazio_copia.txt")
    try:
        fm_log.delete(alvo)
    except ConfirmationRequired:
        pass
    check("arquivo recusado continua no lugar", os.path.isfile(alvo))
    depois = len(open(log_path, encoding="utf-8").read().splitlines())
    check("recusa nao acrescenta linha no arquivo de log", antes == depois,
          "-> %s vs %s" % (antes, depois))
    check("recusa fica registrada em memoria",
          len(fm_log.operation_log()) == 2,
          "-> %s" % len(fm_log.operation_log()))


def test_human_size():
    print("\n=== human_size (pt-BR) ===")
    check("bytes", human_size(0) == "0 B", "-> %s" % human_size(0))
    check("512 bytes", human_size(512) == "512 B", "-> %s" % human_size(512))
    check("1 KB", human_size(1024) == "1,0 KB", "-> %s" % human_size(1024))
    check("1,2 MB", human_size(1234567) == "1,2 MB",
          "-> %s" % human_size(1234567))
    check("separador de milhar", human_size(1024 ** 3) == "1,0 GB",
          "-> %s" % human_size(1024 ** 3))


# ---------------------------------------------------------------------------

def main():
    print("NURA OS — teste do gerenciador de arquivos (nura_filemgr)")
    tmp = tempfile.mkdtemp(prefix="nura-fm-")
    # raiz da instancia (modo sandbox) e arvore de fora dela
    raiz = os.path.join(tmp, "raiz")
    base = os.path.join(raiz, "base")
    base_aux = os.path.join(raiz, "base_aux")
    fora = os.path.join(tmp, "fora")
    os.makedirs(base)
    os.makedirs(base_aux)
    os.makedirs(fora)
    try:
        tamanhos = montar_arvore(base)
        montar_arvore(base_aux)
        with open(os.path.join(fora, "fora.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("fora\n")

        fm = FileManager(root=raiz, log_path=os.path.join(tmp, "ops.log"))
        # instancia separada: o log dela comeca vazio e sem arquivo
        fm_log = FileManager(root=raiz, log_path=os.path.join(tmp, "log.log"))

        test_listdir(fm, base)
        test_stat_info(fm, base)
        test_copy(fm, base)
        test_rename(fm, base)
        test_mkdir(fm, base)
        test_delete_sem_confirm(fm, base)
        test_delete_com_confirm(fm, base)
        test_delete_diretorio(fm, base)
        test_delete_protegido(fm)
        test_delete_fora_da_raiz(fm, base, fora)
        test_delete_link(fm, base)
        test_du(fm, base_aux, tamanhos)
        test_storage(fm)
        test_mounts(fm)
        test_removable(fm)
        test_search(fm, base_aux)
        test_open_with(fm, base)
        test_recent(fm)
        test_log(fm_log, base, tmp)
        test_human_size()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS: %s" % falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
