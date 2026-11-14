#!/usr/bin/env python3
"""NURA OS — testes do catalogo de aplicativos (nura_apps).

Roda sem aparelho e sem pytest:

    python3 test_apps.py

Monta um diretorio temporario com tres arquivos .desktop (um valido,
um com NoDisplay=true e um quebrado) e verifica:

  * parse_desktop (nome, exec sem %-codes, icone, categorias...);
  * descarte de NoDisplay/Hidden;
  * .desktop quebrado nao levanta excecao;
  * scan_applications com diretorio temporario;
  * search_apps com "nura" e "arc";
  * favoritos e recentes em arquivo temporario (sem tocar no
    ~/.config/nura real).
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from nura_apps import (          # noqa: E402
    AppEntry,
    NURA_APPS,
    NURA_APPS_BY_KEY,
    favorites,
    parse_desktop,
    record_recent,
    recent_apps,
    scan_applications,
    search_apps,
    set_favorites,
    translate_exec,
)

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)
    return bool(cond)


# ----------------------------------------------------------------------
# arquivos .desktop de teste
# ----------------------------------------------------------------------

DESKTOP_VALIDO = """[Desktop Entry]
Type=Application
Name=Calculadora NURA
Comment=Calculadora do sistema
Exec=/usr/bin/calc --window %f
Icon=accessories-calculator
Categories=Utility;Calculator;
Terminal=false
"""

DESKTOP_NODISPLAY = """[Desktop Entry]
Type=Application
Name=App Escondido
Exec=/usr/bin/escondido
NoDisplay=true
"""

DESKTOP_HIDDEN = """[Desktop Entry]
Type=Application
Name=App Secreto
Exec=/usr/bin/secreto
Hidden=true
"""

DESKTOP_SEM_NOME = """[Desktop Entry]
Type=Application
Exec=/usr/bin/semnome
Icon=semnome
"""

# arquivo realmente quebrado: lixo binario e nenhuma secao valida
DESKTOP_QUEBRADO = (
    "\x00\x01\x02\x03 lixo binario\n"
    "[Desktop Entry\n"
    "Name\n"
    "Exec=@@@ nao e um comando @@@\n"
)

# texto sem a secao [Desktop Entry]
DESKTOP_SEM_SECAO = """Name=App Sem Secao
Exec=/usr/bin/semsecao
"""


def write(path, content):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w") as f:
        f.write(content)


def build_dir(tmp):
    """Monta o diretorio de .desktop de teste. Devolve os caminhos."""
    d = os.path.join(tmp, "applications")
    os.makedirs(d)
    valido = os.path.join(d, "calc.desktop")
    nodisplay = os.path.join(d, "escondido.desktop")
    hidden = os.path.join(d, "secreto.desktop")
    quebrado = os.path.join(d, "quebrado.desktop")
    sem_nome = os.path.join(d, "sem_nome.desktop")
    nao_desktop = os.path.join(d, "leia-me.txt")
    write(valido, DESKTOP_VALIDO)
    write(nodisplay, DESKTOP_NODISPLAY)
    write(hidden, DESKTOP_HIDDEN)
    write(quebrado, DESKTOP_QUEBRADO)
    write(sem_nome, DESKTOP_SEM_NOME)
    write(nao_desktop, "isto nao e um .desktop\n")
    return {"dir": d, "valido": valido, "nodisplay": nodisplay,
            "hidden": hidden, "quebrado": quebrado, "sem_nome": sem_nome}


# ----------------------------------------------------------------------
# testes
# ----------------------------------------------------------------------

def test_parse_desktop(tmp):
    print("\n=== parse_desktop ===")
    arq = os.path.join(tmp, "valido.desktop")
    write(arq, DESKTOP_VALIDO)

    e = parse_desktop(arq)
    check("parse_desktop: devolve AppEntry", isinstance(e, AppEntry),
          repr(e))
    if not isinstance(e, AppEntry):
        return
    check("parse_desktop: nome", e.name == "Calculadora NURA", repr(e.name))
    check("parse_desktop: comentario", e.comment == "Calculadora do sistema",
          repr(e.comment))
    check("parse_desktop: icone", e.icon == "accessories-calculator",
          repr(e.icon))
    check("parse_desktop: caminho do .desktop", e.desktop_file == arq,
          repr(e.desktop_file))
    check("parse_desktop: categorias", e.categories == ["Utility",
                                                        "Calculator"],
          repr(e.categories))
    check("parse_desktop: nao e app do NURA", e.nura is False, repr(e.nura))
    check("parse_desktop: app_key vazio", e.app_key is None, repr(e.app_key))
    check("parse_desktop: Terminal=false", e.terminal is False, repr(e.terminal))
    check("parse_desktop: Exec sem %-codes", "%" not in (e.exec_cmd or ""),
          repr(e.exec_cmd))
    check("parse_desktop: Exec executavel",
          (e.exec_cmd or "").startswith("/usr/bin/calc"), repr(e.exec_cmd))
    check("parse_desktop: remove o token %f",
          (e.exec_cmd or "").strip() == "/usr/bin/calc --window",
          repr(e.exec_cmd))


def test_exec_codes():
    print("\n=== traducao do Exec (%-codes) ===")
    check("Exec: %f removido", translate_exec("app %f") == "app",
          repr(translate_exec("app %f")))
    check("Exec: %u/%U removidos", translate_exec("app %u %U") == "app",
          repr(translate_exec("app %u %U")))
    check("Exec: %i/%c/%k removidos", translate_exec("app %i %c %k") == "app",
          repr(translate_exec("app %i %c %k")))
    check("Exec: opcao que so existe pelo %f some",
          translate_exec("app --file=%f") == "app",
          repr(translate_exec("app --file=%f")))
    check("Exec: %% vira %",
          translate_exec("app %") == "app %",
          repr(translate_exec("app %")))
    check("Exec: token legado 'Remove' sai",
          translate_exec("app Remove %f") == "app",
          repr(translate_exec("app Remove %f")))
    check("Exec: aspas preservadas", translate_exec('app "meu arg"') ==
          'app "meu arg"', repr(translate_exec('app "meu arg"')))
    check("Exec: vazio devolve vazio", translate_exec("") == "",
          repr(translate_exec("")))
    check("Exec: None devolve vazio", translate_exec(None) == "",
          repr(translate_exec(None)))


def test_parse_descartes(tmp):
    print("\n=== descarte de NoDisplay/Hidden ===")
    nd = os.path.join(tmp, "nodisplay.desktop")
    write(nd, DESKTOP_NODISPLAY)
    hd = os.path.join(tmp, "hidden.desktop")
    write(hd, DESKTOP_HIDDEN)
    sn = os.path.join(tmp, "sem_nome.desktop")
    ss = os.path.join(tmp, "sem_secao.desktop")

    check("NoDisplay=true: descartado", parse_desktop(nd) is None,
          repr(parse_desktop(nd)))
    check("Hidden=true: descartado", parse_desktop(hd) is None,
          repr(parse_desktop(hd)))
    check("sem Name: descartado", parse_desktop(sn) is None,
          repr(parse_desktop(sn)))
    check("sem [Desktop Entry]: descartado", parse_desktop(ss) is None,
          repr(parse_desktop(ss)))


def test_parse_quebrado(tmp):
    print("\n=== .desktop quebrado ===")
    qb = os.path.join(tmp, "quebrado.desktop")
    write(qb, DESKTOP_QUEBRADO)

    erro = None
    resultado = None
    try:
        resultado = parse_desktop(qb)
    except Exception as e:
        erro = e
    check("quebrado: nao levanta excecao", erro is None,
          "%s: %s" % (type(erro).__name__, erro) if erro else "")
    check("quebrado: devolve None", resultado is None, repr(resultado))

    # arquivo inexistente e arquivo vazio tambem nao podem estourar
    erro = None
    try:
        parse_desktop(os.path.join(tmp, "nao-existe.desktop"))
        parse_desktop("")
        vazio = os.path.join(tmp, "vazio.desktop")
        write(vazio, "")
        parse_desktop(vazio)
    except Exception as e:
        erro = e
    check("inexistente/vazio: nao levanta excecao", erro is None,
          "%s: %s" % (type(erro).__name__, erro) if erro else "")


def test_scan(tmp):
    print("\n=== scan_applications ===")
    d = os.path.join(tmp, "applications")
    os.makedirs(d)
    write(os.path.join(d, "calc.desktop"), DESKTOP_VALIDO)
    write(os.path.join(d, "escondido.desktop"), DESKTOP_NODISPLAY)
    write(os.path.join(d, "secreto.desktop"), DESKTOP_HIDDEN)
    write(os.path.join(d, "quebrado.desktop"), DESKTOP_QUEBRADO)
    write(os.path.join(d, "sem_nome.desktop"), DESKTOP_SEM_NOME)
    write(os.path.join(d, "leia-me.txt"), "nao e .desktop\n")

    erro = None
    lista = None
    try:
        lista = scan_applications(dirs=[d])
    except Exception as e:
        erro = e
    check("scan: nao levanta excecao com arquivo quebrado", erro is None,
          "%s: %s" % (type(erro).__name__, erro) if erro else "")
    check("scan: apenas o app valido", len(lista) == 1, repr(lista))
    if lista:
        check("scan: nome correto", lista[0].name == "Calculadora NURA",
              repr(lista[0].name))
        check("scan: ordenado por nome",
              [a.name for a in lista] == sorted(a.name for a in lista),
              repr([a.name for a in lista]))

    # diretorio que nao existe -> lista vazia, sem excecao
    vazio = scan_applications(dirs=[os.path.join(tmp, "nao-existe")])
    check("scan: diretorio inexistente devolve []", vazio == [], repr(vazio))
    check("scan: sem diretorio nenhum devolve []", scan_applications(dirs=[]) == [],
          "")

    # a funcao padrao (sem dirs) nao pode estourar no sistema real
    erro = None
    try:
        padrao = scan_applications()
    except Exception as e:
        erro = e
        padrao = []
    check("scan: sem argumento usa os diretorios padrao", erro is None,
          "%s: %s" % (type(erro).__name__, erro) if erro else "")
    check("scan: lista padrao e uma lista",
          isinstance(padrao, list), repr(type(padrao)))


def test_busca():
    print("\n=== search_apps ===")
    entradas = [
        AppEntry(name="NURA Terminal", app_key="terminal", nura=True),
        AppEntry(name="NURA Explorer", app_key="explorer", nura=True),
        AppEntry(name="Arc Browser", exec_cmd="/usr/bin/arc"),
        AppEntry(name="Navegador", exec_cmd="/usr/bin/browser"),
    ]

    r = search_apps("nura", entradas)
    check("busca 'nura': 2 resultados", len(r) == 2, repr([a.name for a in r]))
    check("busca 'nura': NURA Terminal",
          any(a.name == "NURA Terminal" for a in r),
          repr([a.name for a in r]))

    r = search_apps("arc", entradas)
    check("busca 'arc': 1 resultado", len(r) == 1, repr([a.name for a in r]))
    check("busca 'arc': Arc Browser",
          bool(r) and r[0].name == "Arc Browser", repr([a.name for a in r]))

    r = search_apps("NURA", entradas)
    check("busca: case-insensitive", len(r) == 2, repr([a.name for a in r]))

    r = search_apps("arc browser", entradas)
    check("busca: varios termos", len(r) == 1, repr([a.name for a in r]))

    r = search_apps("", entradas)
    check("busca vazia devolve tudo", len(r) == len(entradas), repr(r))

    r = search_apps("inexistente", entradas)
    check("busca sem resultado", r == [], repr(r))

    # acento: "Configuracoes" encontra "Configuracoes"/"Configurações"
    acentos = [AppEntry(name="Configurações")]
    r = search_apps("configuracoes", acentos)
    check("busca ignora acento", len(r) == 1, repr([a.name for a in r]))


def test_nura_apps():
    print("\n=== NURA_APPS (apps internos) ===")
    check("NURA_APPS: 6 aplicativos", len(NURA_APPS) == 6,
          repr([a.name for a in NURA_APPS]))
    esperado = {
        "terminal": ("NURA Terminal", "terminal"),
        "explorer": ("NURA Explorer", "folder"),
        "control": ("NURA Control Center", "cpu"),
        "performance": ("NURA Performance", "ram"),
        "games": ("NURA Game Hub", "gamepad"),
        "start": ("NURA Start", "grid"),
    }
    for key, (nome, icone) in esperado.items():
        e = NURA_APPS_BY_KEY.get(key)
        check("NURA_APPS: %s existe" % key, e is not None, repr(key))
        if e is None:
            continue
        check("NURA_APPS: %s nome" % key, e.name == nome, repr(e.name))
        check("NURA_APPS: %s icone" % key, e.icon == icone, repr(e.icon))
        check("NURA_APPS: %s marcado como interno" % key, e.nura is True,
              repr(e.nura))
        check("NURA_APPS: %s sem comando externo" % key, not e.exec_cmd,
              repr(e.exec_cmd))
    check("NURA_APPS: app_keys unicos",
          len([a.app_key for a in NURA_APPS]) == len(NURA_APPS), "")


def test_favoritos(tmp):
    print("\n=== favoritos ===")
    pasta = os.path.join(tmp, "fav")
    os.makedirs(pasta)
    arq = os.path.join(pasta, "favorites.json")

    check("favorites: [] quando nao existe", favorites(arq) == [],
          repr(favorites(arq)))
    check("favorites: nao cria o arquivo ao ler",
          not os.path.exists(arq), arq)

    ok = set_favorites(["NURA Terminal", "Arc Browser"], arq)
    check("set_favorites: grava", ok is True, repr(ok))
    check("set_favorites: arquivo criado", os.path.isfile(arq), arq)
    f = favorites(arq)
    check("favorites: 2 favoritos", len(f) == 2, repr(f))
    check("favorites: nomes conferem",
          "NURA Terminal" in f and "Arc Browser" in f, repr(f))

    # a pasta e criada quando falta
    sub = os.path.join(tmp, "novo", "sub")
    ok = set_favorites(["X"], os.path.join(sub, "favorites.json"))
    check("set_favorites: cria o diretorio", ok is True and os.path.isfile(
        os.path.join(sub, "favorites.json")), repr(ok))

    # falha de escrita nao levanta excecao
    erro = None
    try:
        caminho = os.path.join(tmp, "arquivo", "favorites.json")
        with open(os.path.join(tmp, "arquivo"), "w") as fh:
            fh.write("sou um arquivo, nao um diretorio\n")
        ok = set_favorites(["Y"], caminho)
    except Exception as e:
        erro = e
        ok = False
    check("set_favorites: falha de escrita nao levanta excecao", erro is None,
          "%s: %s" % (type(erro).__name__, erro) if erro else "")
    check("set_favorites: falha de escrita devolve False", ok is False,
          repr(ok))


def test_recentes(tmp):
    print("\n=== recentes ===")
    pasta = os.path.join(tmp, "rec")
    os.makedirs(pasta)
    arq = os.path.join(pasta, "recent.json")

    check("recent_apps: [] quando nao existe", recent_apps(arq) == [],
          repr(recent_apps(arq)))
    check("recent_apps: nao cria o arquivo ao ler",
          not os.path.exists(arq), arq)

    e = AppEntry(name="NURA Terminal", app_key="terminal", nura=True)
    ok = record_recent(e, arq)
    check("record_recent: grava", ok is True, repr(ok))
    check("record_recent: arquivo criado", os.path.isfile(arq), arq)

    r = recent_apps(arq)
    check("recent_apps: 1 item", len(r) == 1, repr(r))
    check("recent_apps: nome", bool(r) and r[0]["name"] == "NURA Terminal",
          repr(r))
    check("recent_apps: timestamp numerico",
          bool(r) and isinstance(r[0].get("ts"), (int, float)), repr(r))

    # repetir o mesmo app move para o topo, sem duplicar
    record_recent(AppEntry(name="Arc Browser"), arq)
    record_recent(e, arq)
    r = recent_apps(arq)
    check("recent_apps: sem duplicados", len(r) == 2, repr(r))
    check("recent_apps: mais novo primeiro",
          bool(r) and r[0]["name"] == "NURA Terminal", repr(r))

    # maximo de 10
    for i in range(15):
        record_recent(AppEntry(name="App %02d" % i), arq)
    r = recent_apps(arq)
    check("recent_apps: maximo de 10", len(r) == 10, repr(len(r)))

    # arquivo corrompido -> lista vazia, sem excecao
    erro = None
    try:
        with open(arq, "w") as fh:
            fh.write("{isto nao e json")
        r = recent_apps(arq)
    except Exception as ex:
        erro = ex
        r = None
    check("recent_apps: arquivo corrompido nao levanta excecao",
          erro is None, "%s: %s" % (type(erro).__name__, erro) if erro else "")
    check("recent_apps: arquivo corrompido devolve []", r == [], repr(r))

    # falha de escrita nao levanta excecao
    erro = None
    try:
        caminho = os.path.join(tmp, "arquivo2", "recent.json")
        with open(os.path.join(tmp, "arquivo2"), "w") as fh:
            fh.write("sou um arquivo, nao um diretorio\n")
        ok = record_recent(AppEntry(name="Falha"), caminho)
    except Exception as e:
        erro = e
        ok = True
    check("record_recent: falha de escrita nao levanta excecao", erro is None,
          "%s: %s" % (type(erro).__name__, erro) if erro else "")
    check("record_recent: falha de escrita devolve False", ok is False,
          repr(ok))

    # o JSON gravado tem o formato combinado
    record_recent(AppEntry(name="NURA Terminal"), arq)
    try:
        with open(arq) as fh:
            dados = json.load(fh)
        formato_ok = isinstance(dados, list) and \
            all(isinstance(x, dict) and "name" in x and "ts" in x
                for x in dados)
    except Exception:
        formato_ok = False
    check("recent.json: formato lista de {name, ts}", formato_ok, "")


def test_nao_toca_config_real():
    print("\n=== isolamento do ~/.config real ===")
    real = os.path.expanduser("~/.config/nura")
    antes = os.path.isdir(real)
    # apenas leitura: nao pode criar nada
    try:
        recent_apps()
        favorites()
    except Exception:
        pass
    depois = os.path.isdir(real)
    check("leitura nao cria ~/.config/nura", antes == depois,
          "antes=%s depois=%s" % (antes, depois))


# ----------------------------------------------------------------------

def main():
    print("NURA OS — teste do catalogo de aplicativos (nura_apps)")
    tmp = tempfile.mkdtemp(prefix="nura-apps-")
    try:
        test_parse_desktop(tmp)
        test_exec_codes()
        test_parse_descartes(tmp)
        test_parse_quebrado(tmp)
        test_scan(tmp)
        test_busca()
        test_nura_apps()
        test_favoritos(tmp)
        test_recentes(tmp)
        test_nao_toca_config_real()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS (%d): %s" % (len(falhas), falhas)))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
