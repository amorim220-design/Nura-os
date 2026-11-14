#!/usr/bin/env python3
"""NURA OS — catalogo de aplicativos.

O catalogo do NURA tem DUAS fontes de verdade, e nada mais:

  1) os arquivos ``.desktop`` que existem de verdade no sistema:
        /usr/share/applications
        /usr/local/share/applications
        ~/.local/share/applications
  2) a lista interna ``NURA_APPS``: os aplicativos que sao implementados
     dentro do proprio NURA (Terminal, Explorer, Control Center,
     Performance, Game Hub e o proprio Start).

Regra central: **nenhum item aparece no menu sem existir de verdade**.
Um ``.desktop`` quebrado e pulado (sem estourar excecao); um
``NoDisplay=true``/``Hidden=true`` e ignorado.

Nada aqui executa comando nenhum: este modulo apenas *lê* e *cataloga*.
A execucao acontece apenas quando o usuario toca no item.

Somente biblioteca padrao do Python (sem GTK/Qt/gi, sem rede).
"""

import json
import os
import re
import time
import unicodedata

# --------------------------------------------------------------------
# configuracao
# --------------------------------------------------------------------

#: diretorios de onde os .desktop do sistema sao lidos
APP_DIRS = ("/usr/share/applications",
            "/usr/local/share/applications",
            "~/.local/share/applications")

#: diretorio de configuracao do NURA (historico e favoritos)
CONFIG_DIR = "~/.config/nura"

RECENT_FILE = "recent.json"
FAVORITES_FILE = "favorites.json"

#: tamanho maximo do historico de recentes
MAX_RECENT = 10

#: codigos de campo do formato .desktop que nao fazem sentido como
#: argumento quando o item e aberto pelo menu
FIELD_CODES = "fFuUdDnNickvm"

_FIELD_RE = re.compile(r"%[fFuUdDnNickvm%]")

#: token legado que alguns arquivos antigos usam no Exec
_LEGACY_REMOVE = "Remove"


# --------------------------------------------------------------------
# utilidades
# --------------------------------------------------------------------

def _expand(path):
    """Expande ~ e variaveis de ambiente sem quebrar se falhar."""
    try:
        return os.path.expanduser(os.path.expandvars(str(path)))
    except Exception:
        return str(path)


def _config_path(path, filename):
    """Resolve o caminho do arquivo de configuracao.

    ``path`` pode ser:
      * None        -> ``~/.config/nura/``
      * um diretorio-> ``<diretorio>/``
      * um arquivo  -> usado como esta
    """
    if path is None:
        return os.path.join(_expand(CONFIG_DIR), filename)
    p = _expand(path)
    if os.path.isdir(p):
        return os.path.join(p, filename)
    if p.endswith(os.sep):
        return os.path.join(p, filename)
    # um arquivo: se o nome bate com o esperado usa como esta,
    # senao trata como diretorio.
    if os.path.basename(p) == filename:
        return p
    return os.path.join(p, filename)


def _is_true(value):
    """True para 'true'/'True'/'1'/'yes'."""
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _unescape(value):
    """Desfaz as sequencias de escape do formato .desktop."""
    if not value:
        return ""
    out = []
    i = 0
    n = len(value)
    while i < n:
        c = value[i]
        if c == "\\" and i + 1 < n:
            nxt = value[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            elif nxt == "s":
                out.append(" ")
            elif nxt == "\\":
                out.append("\\")
            elif nxt == ";":
                out.append(";")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def normalize(text):
    """minusculas e sem acentos (para busca tolerante)."""
    if not text:
        return ""
    s = str(text).lower()
    try:
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
    except Exception:
        pass
    return s


# --------------------------------------------------------------------
# traducao do Exec
# --------------------------------------------------------------------

def _split_exec(text):
    """Quebra uma linha Exec em tokens, respeitando aspas.

    As aspas sao mantidas no token (um argumento com espaco precisa
    delas para continuar executavel).
    """
    tokens = []
    cur = []
    quote = None
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            cur.append(ch)
            continue
        if ch.isspace():
            if cur:
                tokens.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens


def _strip_field_codes(token):
    """Remove os %-codes de um token.

    Devolve None quando o token era so um %-code (ou uma opcao que
    existia apenas para receber o %-code) e deve sair da linha.
    """
    if not _FIELD_RE.search(token):
        return token
    limpo = _FIELD_RE.sub("", token)
    interno = limpo.strip('"').strip("'")
    if not interno:
        return None
    # '--file=%f' -> '--file=' : a opcao nao faz sentido sem o argumento
    if interno.endswith("="):
        return None
    return limpo


def translate_exec(exec_raw):
    """Traduz a chave ``Exec`` de um .desktop num comando executavel.

    Remove os codigos de campo (%f, %u, %U, %i, %c, %k, ...) e o token
    legado ``Remove``. Devolve uma string (vazia se nao ha comando).
    """
    if not exec_raw:
        return ""
    texto = str(exec_raw).strip()
    if not texto:
        return ""
    # '%%' e um '%' literal: protege antes de remover os outros codigos
    texto = texto.replace("%%", "\x00")
    saida = []
    for token in _split_exec(texto):
        if token == _LEGACY_REMOVE:
            continue
        limpo = _strip_field_codes(token)
        if limpo is None:
            continue
        limpo = limpo.replace("\x00", "%")
        if not limpo:
            continue
        saida.append(limpo)
    return " ".join(saida).strip()


# --------------------------------------------------------------------
# AppEntry
# --------------------------------------------------------------------

class AppEntry(object):
    """Um aplicativo do catalogo NURA.

    Campos:
        name         nome exibido
        icon         nome de icone do Painter ou caminho de um icone
        exec_cmd     comando executavel (str) ou None
        desktop_file caminho do .desktop de origem (ou None)
        categories   lista de categorias
        comment      comentario/descricao
        nura         True quando e um aplicativo interno do NURA
        app_key      identificador do aplicativo interno
        terminal     True quando o .desktop pede um terminal
    """

    __slots__ = ("name", "icon", "exec_cmd", "desktop_file", "categories",
                 "comment", "nura", "app_key", "terminal")

    def __init__(self, name, icon=None, exec_cmd=None, desktop_file=None,
                 categories=None, comment="", nura=False, app_key=None,
                 terminal=False):
        self.name = str(name or "")
        self.icon = icon
        self.exec_cmd = exec_cmd
        self.desktop_file = desktop_file
        self.categories = list(categories or [])
        self.comment = comment or ""
        self.nura = bool(nura)
        self.app_key = app_key
        self.terminal = bool(terminal)

    # --------------------------------------------------
    def __repr__(self):
        return "<AppEntry %r%s>" % (self.name,
                                    " nura" if self.nura else "")

    def __eq__(self, other):
        if not isinstance(other, AppEntry):
            return NotImplemented
        return (self.name == other.name and
                self.desktop_file == other.desktop_file and
                self.exec_cmd == other.exec_cmd)

    def __hash__(self):
        return hash((self.name, self.desktop_file, self.exec_cmd))

    # --------------------------------------------------
    def to_dict(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "exec_cmd": self.exec_cmd,
            "desktop_file": self.desktop_file,
            "categories": list(self.categories),
            "comment": self.comment,
            "nura": self.nura,
            "app_key": self.app_key,
            "terminal": self.terminal,
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(name=data.get("name", ""),
                   icon=data.get("icon"),
                   exec_cmd=data.get("exec_cmd"),
                   desktop_file=data.get("desktop_file"),
                   categories=data.get("categories"),
                   comment=data.get("comment", ""),
                   nura=bool(data.get("nura")),
                   app_key=data.get("app_key"),
                   terminal=bool(data.get("terminal")))

    @property
    def is_system(self):
        """True quando vem de um .desktop real do sistema."""
        return not self.nura


# --------------------------------------------------------------------
# leitura de .desktop
# --------------------------------------------------------------------

def _read_desktop_section(path):
    """Le a secao ``[Desktop Entry]`` de um .desktop.

    Devolve um dict (chaves em minusculas) ou None se o arquivo nao
    pode ser lido / nao tem a secao / nao e um arquivo de texto valido.
    Nunca levanta excecao.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except (OSError, IOError, UnicodeError):
        return None
    except Exception:
        return None

    if not texto.strip():
        return None
    # arquivo binario (lixo) nao e um .desktop valido
    if "\x00" in texto:
        return None

    dados = {}
    secao = None
    achou_secao = False
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.startswith("[") and linha.endswith("]"):
            secao = linha[1:-1].strip()
            if secao == "Desktop Entry":
                achou_secao = True
            continue
        if "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip().lower()
        if not chave:
            continue
        # antes da primeira secao, ou dentro de [Desktop Entry]
        if secao is None or secao == "Desktop Entry":
            dados[chave] = valor.strip()

    # sem [Desktop Entry] o arquivo nao e um .desktop valido
    if not achou_secao:
        return None
    return dados


def parse_desktop(path):
    """Le um arquivo .desktop e devolve um :class:`AppEntry`.

    Devolve ``None`` quando o arquivo nao serve como aplicativo
    (quebrado, sem ``[Desktop Entry]``, ``NoDisplay=true``,
    ``Hidden=true`` ou ``Type`` diferente de ``Application``).
    Nunca levanta excecao.
    """
    if not path:
        return None
    try:
        dados = _read_desktop_section(path)
    except Exception:
        return None
    if not dados:
        return None

    if _is_true(dados.get("nodisplay")) or _is_true(dados.get("hidden")):
        return None

    tipo = (dados.get("type") or "Application").strip().lower()
    if tipo != "application":
        return None

    nome = _unescape(dados.get("name") or "").strip()
    if not nome:
        return None

    exec_raw = dados.get("exec")
    try:
        comando = translate_exec(exec_raw) if exec_raw else ""
    except Exception:
        comando = ""

    icone = (dados.get("icon") or "").strip() or None
    comentario = _unescape(dados.get("comment") or "").strip()
    cats_raw = dados.get("categories") or ""
    categorias = [c.strip() for c in cats_raw.split(";") if c.strip()]

    return AppEntry(name=nome,
                    icon=icone,
                    exec_cmd=comando or None,
                    desktop_file=str(path),
                    categories=categorias,
                    comment=comentario,
                    nura=False,
                    app_key=None,
                    terminal=_is_true(dados.get("terminal")))


def scan_applications(dirs=None):
    """Le os .desktop do sistema e devolve a lista ordenada por nome.

    ``dirs`` = None usa :data:`APP_DIRS`. Um .desktop quebrado e pulado
    (sem excecao). Se dois arquivos tiverem o mesmo nome, vale o do
    diretorio lido por ultimo (assim o ``~/.local`` sobrescreve o
    ``/usr``).
    """
    if dirs is None:
        dirs = APP_DIRS
    elif isinstance(dirs, str):
        dirs = [dirs]

    vistos = {}
    for d in dirs:
        try:
            caminho = _expand(d)
        except Exception:
            continue
        if not caminho or not os.path.isdir(caminho):
            continue
        try:
            nomes = sorted(os.listdir(caminho))
        except OSError:
            continue
        for nome in nomes:
            if not nome.endswith(".desktop"):
                continue
            arq = os.path.join(caminho, nome)
            if not os.path.isfile(arq):
                continue
            try:
                entrada = parse_desktop(arq)
            except Exception:
                entrada = None
            if entrada is None:
                continue
            chave = normalize(entrada.name)
            vistos[chave] = entrada

    return sorted(vistos.values(), key=lambda e: (normalize(e.name), e.name))


# --------------------------------------------------------------------
# aplicativos internos do NURA
# --------------------------------------------------------------------

def _nura_app(key, name, icon, comment):
    return AppEntry(name=name, icon=icon, exec_cmd=None, desktop_file=None,
                    categories=["NURA"], comment=comment, nura=True,
                    app_key=key, terminal=False)


#: aplicativos implementados dentro do proprio NURA
NURA_APPS = [
    _nura_app("terminal", "NURA Terminal", "terminal",
              "Terminal do NURA OS"),
    _nura_app("explorer", "NURA Explorer", "folder",
              "Gerenciador de arquivos"),
    _nura_app("control", "NURA Control Center", "cpu",
              "Configuracoes do sistema"),
    _nura_app("performance", "NURA Performance", "ram",
              "CPU, memoria e temperatura"),
    _nura_app("games", "NURA Game Hub", "gamepad",
              "Biblioteca de jogos"),
    _nura_app("start", "NURA Start", "grid",
              "Menu iniciar do NURA OS"),
]

NURA_APPS_BY_KEY = dict((a.app_key, a) for a in NURA_APPS)


def catalog(dirs=None, include_nura=True):
    """Catalogo completo: apps internos do NURA + .desktop do sistema."""
    lista = list(NURA_APPS) if include_nura else []
    lista.extend(scan_applications(dirs))
    return sorted(lista, key=lambda e: (normalize(e.name), e.name))


# --------------------------------------------------------------------
# historico de recentes
# --------------------------------------------------------------------

def recent_apps(path=None):
    """Le o historico de aplicativos abertos.

    O arquivo e ``~/.config/nura/recent.json`` (lista de
    ``{"name": ..., "ts": ...}``, mais novo primeiro).

    Devolve ``[]`` quando o arquivo nao existe. **Nunca cria o arquivo
    ao ler.**
    """
    arq = _config_path(path, RECENT_FILE)
    if not os.path.isfile(arq):
        return []
    try:
        with open(arq, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return []
    if not isinstance(dados, list):
        return []
    saida = []
    for item in dados:
        if isinstance(item, dict):
            nome = str(item.get("name") or "").strip()
            if not nome:
                continue
            ts = item.get("ts")
            if not isinstance(ts, (int, float)):
                ts = 0.0
            saida.append({"name": nome, "ts": float(ts)})
        elif isinstance(item, str) and item.strip():
            saida.append({"name": item.strip(), "ts": 0.0})
    return saida


def record_recent(entry, path=None):
    """Registra um aplicativo no historico de recentes.

    ``entry`` pode ser um :class:`AppEntry` ou um nome (str).
    Guarda no maximo :data:`MAX_RECENT` itens e tolera falha de
    escrita (devolve False, sem levantar excecao).
    """
    nome = getattr(entry, "name", entry)
    nome = str(nome or "").strip()
    if not nome:
        return False

    arq = _config_path(path, RECENT_FILE)
    atual = recent_apps(arq)
    novo = [{"name": nome, "ts": time.time()}]
    for item in atual:
        if normalize(item.get("name")) == normalize(nome):
            continue
        novo.append(item)
    novo = novo[:MAX_RECENT]

    try:
        pasta = os.path.dirname(arq)
        if pasta and not os.path.isdir(pasta):
            os.makedirs(pasta, exist_ok=True)
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(novo, f, indent=2)
        return True
    except Exception:
        return False


def clear_recent(path=None):
    """Apaga o historico de recentes (best effort)."""
    arq = _config_path(path, RECENT_FILE)
    try:
        if os.path.isfile(arq):
            os.remove(arq)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------
# favoritos
# --------------------------------------------------------------------

def favorites(path=None):
    """Lista de favoritos (``~/.config/nura/favorites.json``)."""
    arq = _config_path(path, FAVORITES_FILE)
    if not os.path.isfile(arq):
        return []
    try:
        with open(arq, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return []
    if isinstance(dados, dict):
        dados = dados.get("favorites") or []
    if not isinstance(dados, list):
        return []
    saida = []
    for item in dados:
        if isinstance(item, str) and item.strip():
            nome = item.strip()
            if nome not in saida:
                saida.append(nome)
    return saida


def set_favorites(names, path=None):
    """Grava a lista de favoritos. Tolera falha de escrita."""
    arq = _config_path(path, FAVORITES_FILE)
    limpo = []
    for item in (names or []):
        nome = str(item).strip()
        if nome and nome not in limpo:
            limpo.append(nome)
    try:
        pasta = os.path.dirname(arq)
        if pasta and not os.path.isdir(pasta):
            os.makedirs(pasta, exist_ok=True)
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(limpo, f, indent=2)
        return True
    except Exception:
        return False


def toggle_favorite(name, path=None):
    """Marca/desmarca um favorito. Devolve a nova lista (ou None)."""
    nome = str(name or "").strip()
    if not nome:
        return None
    atual = favorites(path)
    if nome in atual:
        atual = [x for x in atual if x != nome]
    else:
        atual = atual + [nome]
    if set_favorites(atual, path):
        return atual
    return None


# --------------------------------------------------------------------
# busca
# --------------------------------------------------------------------

def search_apps(query, entries):
    """Filtra ``entries`` pelo nome (sem diferenciar maiusculas/acento).

    Todos os termos da busca precisam aparecer no nome. Busca vazia
    devolve a lista inteira.
    """
    itens = list(entries or [])
    q = normalize(query).strip()
    if not q:
        return itens
    termos = [t for t in q.split() if t]
    if not termos:
        return itens
    saida = []
    for e in itens:
        nome = normalize(getattr(e, "name", e) or "")
        if all(t in nome for t in termos):
            saida.append(e)
    return saida


# --------------------------------------------------------------------
# linha de comando (apenas diagnostico, nao faz parte do desktop)
# --------------------------------------------------------------------

def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    print("NURA OS — catalogo de aplicativos")
    if argv and argv[0] == "--search" and len(argv) > 1:
        for e in search_apps(argv[1], catalog()):
            print("  %-32s %s" % (e.name, e.exec_cmd or e.app_key or ""))
        return 0
    for e in catalog():
        origem = "NURA" if e.nura else (e.desktop_file or "")
        print("  %-32s %s" % (e.name, origem))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
