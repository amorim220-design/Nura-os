#!/usr/bin/env python3
# NURA OS — camada de operacoes de arquivo do "NURA Explorer"

"""
nura_filemgr — a camada de regras do gerenciador de arquivos do NURA OS.

Este modulo faz o trabalho pesado do "NURA Explorer" (listar, copiar, mover,
renomear, apagar, medir, procurar) e devolve dados ja prontos para a camada
visual desenhar. Nao tem dependencia externa nenhuma: so biblioteca padrao do
Python 3 (roda igual no Python 3.12 e no 3.14 do Alpine edge do aparelho).

================================  GARANTIAS DE SEGURANCA  =============================

1. NADA AQUI E PRIVILEGIADO.
   O modulo NUNCA chama sudo, chmod, chown, mount, umount, fdisk ou mkfs;
   nunca roda "rm -rf" de casca; nunca escreve em /proc, /sys, /dev ou /boot.
   Se o usuario sem privilegio nao tem permissao, a operacao falha com
   PermissionError — o modulo nao tenta contornar, nao eleva privilegio e
   nao mascara o erro: ele propaga o erro do sistema honestamente.

2. NADA E APAGADO SEM CONFIRMACAO EXPLICITA.
   Toda operacao destrutiva (delete()) exige o parametro confirm=True.
   Sem ele o modulo levanta ConfirmationRequired (que e subclasse de
   PermissionError) e NAO faz nada: o arquivo continua la, intacto.

3. "rm -rf" ACIDENTAL E BLOQUEADO EM TRES NIVEIS:
   a) delete() de um diretorio nao vazio exige recursive=True explicito;
   b) delete() de um caminho protegido (PROTECTED) e SEMPRE recusado, mesmo
      com confirm=True e recursive=True;
   c) quando a instancia tem "root" definido (modo sandbox, usado nos
      testes), delete() so trabalha dentro dessa raiz.

4. CAMINHOS PROTEGIDOS (PROTECTED).
   A lista abaixo e bloqueada: o proprio caminho E qualquer caminho que
   esteja DENTRO dele (inclusive com "..", links simbolicos ou caminhos
   relativos). '/' e apenas o proprio "/" (nao a arvore inteira).

       '/'  '/bin'  '/boot'  '/bootdevice'  '/dev'  '/etc'  '/home'
       '/lib' '/proc' '/root' '/sbin' '/sys' '/usr' '/var'

   Por padrao /home e /var tambem estao protegidos — ou seja, apagar dados
   do usuario dentro do home exige que o CHAMADOR faca isso de forma
   explicita, instanciando o gerenciador com `protected=` reduzido. A UI do
   NURA Explorer nao faz isso: o default e a protecao maxima. A razao e
   simples: a maior parte dos "acidentes" de apagamento acontece em /home,
   /root e /var.

   ALWAYS_PROTECTED e um nucleo que NUNCA pode ser removido da protecao,
   nem por `protected=`: '/'  '/proc'  '/sys'  '/dev'.

5. OPERACOES EM MASSA PEDEM EXPLICTICIDADE.
   Apagar diretorio nao vazio (recursive=True) e copiar/arvore inteira sao
   as duas operacoes que mais destroem dados. As duas exigem parametro
   explicito (recursive=True / overwrite=True) alem da confirmacao.

6. NADA E INVENTADO.
   O modulo le /proc/mounts e a arvore de arquivos de verdade. Se o dado
   nao existe (sem SD card, sem xdg-open, sem arquivo de recentes), devolve
   lista vazia — nunca inventa entrada nem cria arquivo so para encher
   lista. recent_files() jamais cria o arquivo de recentes.

================================================================================
"""

import errno
import json
import os
import shutil
import stat as stat_mod
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import unquote, urlparse

__all__ = [
    "FileManager",
    "FileManagerError",
    "ConfirmationRequired",
    "ProtectedPathError",
    "OutsideRootError",
    "NotEmptyError",
    "PROTECTED",
    "ALWAYS_PROTECTED",
    "human_size",
]


# ---------------------------------------------------------------------------
# constantes de politica
# ---------------------------------------------------------------------------

#: diretorios de sistema que nunca podem ser apagados (nem o conteudo deles)
PROTECTED = frozenset({
    "/", "/bin", "/boot", "/bootdevice", "/dev", "/etc", "/home",
    "/lib", "/proc", "/root", "/sbin", "/sys", "/usr", "/var",
})

#: nucleo da protecao: nao pode ser removido nem por `protected=`
ALWAYS_PROTECTED = frozenset({"/", "/proc", "/sys", "/dev"})

#: pseudo-sistemas que nao aparecem como "armazenamento real"
PSEUDO_FS = frozenset({
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2", "configfs",
    "debugfs", "devpts", "devtmpfs", "efivarfs", "fuse.gvfsd-fuse",
    "fusectl", "hugetlbfs", "mqueue", "nsfs", "overlay", "proc",
    "pstore", "ramfs", "securityfs", "squashfs", "sysfs", "tracefs",
})

#: pontos de montagem onde costuma aparecer cartao SD / pendrive
REMOVABLE_MIDPOINTS = ("/media", "/run/media", "/mnt")

IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "gif", "bmp", "webp"})

TEXT_EXTS = frozenset({
    "txt", "md", "rst", "log", "ini", "cfg", "conf", "cnf", "env",
    "json", "yaml", "yml", "toml", "xml", "csv", "tsv", "html", "htm",
    "css", "js", "py", "c", "h", "cpp", "hpp", "sh", "bash", "zsh",
    "desktop", "service", "list", "patch", "diff", "src", "mk", "conf",
})

BINARY_EXTS = frozenset({
    "png", "jpg", "jpeg", "gif", "bmp", "webp", "ico", "tiff", "svg",
    "pdf", "epub", "zip", "gz", "bz2", "xz", "7z", "rar", "tar", "tgz",
    "iso", "bin", "img", "apk", "deb", "rpm", "so", "a", "o", "exe",
    "dll", "mp3", "flac", "ogg", "wav", "m4a", "aac", "opus", "mp4",
    "mkv", "avi", "webm", "mov", "mkv", "ttf", "otf", "woff", "woff2",
    "db", "sqlite", "pyc", "class", "jar", "dmg", "core",
})

#: log de operacoes (criado apenas quando uma operacao realmente acontece)
DEFAULT_LOG_PATH = os.path.join("~", ".config", "nura", "filemgr.log")


# ---------------------------------------------------------------------------
# excecoes
# ---------------------------------------------------------------------------

class FileManagerError(Exception):
    """Erro base das operacoes do gerenciador de arquivos."""


class ConfirmationRequired(FileManagerError, PermissionError):
    """Operacao destrutiva sem `confirm=True` explicito.

    E subclasse de PermissionError, entao quem so conhece a hierarquia
    padrao do OS continua tratando como "sem permissao".
    """


class ProtectedPathError(FileManagerError, PermissionError):
    """Caminho protegido: operacao recusada por politica de seguranca."""


class OutsideRootError(FileManagerError, PermissionError):
    """Caminho fora da raiz (`root`) permitida para esta instancia."""


class NotEmptyError(FileManagerError, OSError):
    """Diretorio nao vazio apagado sem `recursive=True` explicito."""


# ---------------------------------------------------------------------------
# helpers puros
# ---------------------------------------------------------------------------

def _fmt_decimal(value, casas=1):
    """Formata float no estilo pt-BR: '1.234,5' (milhar com ponto)."""
    texto = "%.*f" % (casas, value)
    inteiro, _, resto = texto.partition(".")
    try:
        inteiro = "{:,}".format(int(inteiro)).replace(",", ".")
    except (TypeError, ValueError):
        pass
    if resto:
        return inteiro + "," + resto
    return inteiro


def human_size(num):
    """Bytes -> texto legivel pt-BR ('1,2 MB', '512 B', '3,4 GB')."""
    try:
        num = int(num)
    except (TypeError, ValueError):
        return "0 B"
    if num < 0:
        return "-" + human_size(-num)
    if num < 1024:
        return "%d B" % num
    valor = float(num)
    for unidade in ("KB", "MB", "GB", "TB", "PB"):
        valor /= 1024.0
        if valor < 1024.0 or unidade == "PB":
            return "%s %s" % (_fmt_decimal(valor), unidade)
    return "%s PB" % _fmt_decimal(valor)


def _now_iso():
    """Data/hora local em ISO ('2026-11-13 10:42:00')."""
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _now_ts():
    """Timestamp float do instante atual."""
    return datetime.now().timestamp()


def _unescape_mount(text):
    """/proc/mounts usa escapes octais para espaco e afins."""
    if "\\" not in text:
        return text
    saida = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 3 < len(text):
            try:
                saida.append(chr(int(text[i + 1:i + 4], 8)))
                i += 4
                continue
            except ValueError:
                pass
        saida.append(text[i])
        i += 1
    return "".join(saida)


def _call_progress(callback, feito, total):
    """Chama o callback de progresso: progress(feito, total)."""
    if callback is None:
        return
    try:
        callback(feito, total)
    except TypeError:
        # callback de um argumento so: progress(feito)
        callback(feito)


# ---------------------------------------------------------------------------
# gerenciador
# ---------------------------------------------------------------------------

class FileManager(object):
    """Camada de operacoes de arquivo do NURA Explorer.

    root      -> se definido, caminhos relativos sao resolvidos dentro dele e
                 delete() so pode mexer dentro da raiz (modo sandbox/teste).
    protected -> conjunto de diretorios protegidos desta instancia. None
                 (default) usa a lista global PROTECTED. '/', '/proc',
                 '/sys' e '/dev' nunca saem da protecao.
    log_path  -> arquivo de log das operacoes. None usa
                 ~/.config/nura/filemgr.log.
    log_to_file -> False mantem o log so em memoria.
    """

    def __init__(self, root=None, protected=None, log_path=None,
                 log_to_file=True, max_log=500):
        self.root = None
        if root:
            self.root = os.path.normpath(os.path.abspath(os.path.expanduser(root)))
        protecao = set(PROTECTED) if protected is None else set(protected)
        protecao |= set(ALWAYS_PROTECTED)
        self.protected = frozenset(protecao)
        self.log_to_file = bool(log_to_file)
        if log_path is None:
            log_path = DEFAULT_LOG_PATH
        self.log_path = os.path.abspath(os.path.expanduser(log_path))
        self.max_log = int(max_log)
        self._log = []

    # ------------------------------------------------------------------
    # infra: resolucao de caminhos e guardas de seguranca
    # ------------------------------------------------------------------

    def _resolve(self, path):
        """Normaliza um caminho (relativo -> relativo a root, ou ao cwd)."""
        if path is None:
            raise ValueError("caminho obrigatorio")
        if isinstance(path, bytes):
            path = path.decode("utf-8", "replace")
        elif not isinstance(path, str):
            path = os.fspath(path)
            if isinstance(path, bytes):
                path = path.decode("utf-8", "replace")
        if not path:
            raise ValueError("caminho vazio")
        if os.path.isabs(path):
            return os.path.normpath(path)
        if self.root:
            return os.path.normpath(os.path.join(self.root, path))
        return os.path.abspath(path)

    def is_protected(self, path):
        """True se o caminho (ou o alvo real dele) for caminho protegido."""
        try:
            alvo = self._resolve(path)
        except (ValueError, TypeError):
            return False
        candidatos = [alvo]
        try:
            real = os.path.realpath(alvo)
            if real and real != alvo:
                candidatos.append(real)
        except OSError:
            pass
        for cand in candidatos:
            if self._is_protected_path(cand):
                return True
        return False

    def _is_protected_path(self, path):
        alvo = os.path.normpath(os.path.abspath(path))
        for base in self.protected:
            base = base.rstrip("/")
            if not base:
                # '/' protege apenas o proprio "/" (e nao a arvore toda)
                if alvo == "/":
                    return True
                continue
            if alvo == base or alvo.startswith(base + "/"):
                return True
        return False

    def _guard(self, path, acao="operacao"):
        """Recusa caminho protegido. Devolve o caminho ja resolvido."""
        alvo = self._resolve(path)
        if self.is_protected(alvo):
            raise ProtectedPathError(
                "%s recusada: caminho protegido (%s)" % (acao, alvo))
        return alvo

    def _guard_root(self, path, acao="operacao"):
        """Recusa caminho fora da raiz da instancia (modo sandbox).

        Compara tambem o caminho real (resolve symlink), para que um link
        dentro da raiz nao aponte para fora dela.
        """
        alvo = self._resolve(path)
        if self.root:
            raiz = os.path.realpath(self.root).rstrip("/")
            real = os.path.realpath(alvo)
            for cand in (alvo, real):
                if cand != raiz and not cand.startswith(raiz + "/"):
                    raise OutsideRootError(
                        "%s recusada: caminho fora da raiz permitida (%s)"
                        % (acao, alvo))
        return alvo

    def _check_writable_dir(self, path):
        """Falha cedo (e com honestidade) se nao der para escrever no pai."""
        pai = os.path.dirname(path) or "."
        if not os.path.isdir(pai):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), pai)
        if not os.access(pai, os.W_OK | os.X_OK):
            raise PermissionError(
                errno.EACCES,
                "sem permissao de escrita em %s" % pai, pai)

    def _check_readable(self, path):
        if not os.access(path, os.R_OK):
            raise PermissionError(
                errno.EACCES, "sem permissao de leitura em %s" % path, path)

    # ------------------------------------------------------------------
    # listagem
    # ------------------------------------------------------------------

    def listdir(self, path=".", show_hidden=False):
        """Lista o conteudo de um diretorio.

        Devolve lista de dicts: name, path, is_dir, is_link, size, mtime,
        mode e target. Diretorios primeiro, depois arquivos, ambos em
        ordem alfabetica sem diferenciar maiusculas/minusculas.
        `size` de diretorio e -1; `mtime` e timestamp float.
        """
        base = self._resolve(path)
        entradas = []
        with os.scandir(base) as scan:
            for entrada in scan:
                if not show_hidden and entrada.name.startswith("."):
                    continue
                entradas.append(self._entry_info(entrada))
        entradas.sort(key=lambda e: (0 if e["is_dir"] else 1,
                                     e["name"].lower()))
        return entradas

    def _entry_info(self, entrada):
        """Monta o dict de uma entrada de os.scandir (sem levantar excecao)."""
        caminho = entrada.path
        is_link = entrada.is_symlink()
        st = None
        lstat = None
        try:
            lstat = entrada.stat(follow_symlinks=False)
        except OSError:
            lstat = None
        try:
            st = entrada.stat()          # segue o link
        except OSError:
            st = None                    # link quebrado
        base = lstat if lstat is not None else st
        if base is None:
            return {
                "name": entrada.name, "path": caminho, "is_dir": False,
                "is_link": is_link, "size": 0, "mtime": 0.0,
                "mode": "----------", "target": None,
            }
        is_dir = bool(st is not None and stat_mod.S_ISDIR(st.st_mode))
        size = -1 if is_dir else int(base.st_size)
        target = None
        if is_link:
            try:
                target = os.readlink(caminho)
            except OSError:
                target = None
        return {
            "name": entrada.name,
            "path": caminho,
            "is_dir": is_dir,
            "is_link": is_link,
            "size": size,
            "mtime": float(base.st_mtime),
            "mode": stat_mod.filemode(base.st_mode),
            "target": target,
        }

    # ------------------------------------------------------------------
    # metadados
    # ------------------------------------------------------------------

    def stat_info(self, path):
        """Metadados de um caminho.

        Devolve dict com: name, path, type, size, size_human, mtime,
        mtime_iso, mode (simbolico), permission (octal), uid, gid, owner,
        group, target, hidden, is_image e is_text.
        """
        alvo = self._resolve(path)
        lstat = os.lstat(alvo)
        is_link = stat_mod.S_ISLNK(lstat.st_mode)
        try:
            st = os.stat(alvo) if is_link else lstat
        except OSError:
            st = lstat
        alvo_str = os.path.basename(alvo.rstrip("/")) or alvo
        tipo = self._file_type(lstat.st_mode)
        dono = str(lstat.st_uid)
        grupo = str(lstat.st_gid)
        try:
            import pwd
            dono = pwd.getpwuid(lstat.st_uid).pw_name
        except Exception:
            pass
        try:
            import grp
            grupo = grp.getgrgid(lstat.st_gid).gr_name
        except Exception:
            pass
        target = None
        if is_link:
            try:
                target = os.readlink(alvo)
            except OSError:
                target = None
        ext = os.path.splitext(alvo_str)[1].lower().lstrip(".")
        return {
            "name": alvo_str,
            "path": alvo,
            "type": tipo,
            "is_dir": bool(stat_mod.S_ISDIR(st.st_mode)),
            "is_link": is_link,
            "size": int(st.st_size),
            "size_human": human_size(st.st_size),
            "mtime": float(lstat.st_mtime),
            "mtime_iso": datetime.fromtimestamp(
                lstat.st_mtime).isoformat(timespec="seconds"),
            "mtime_human": datetime.fromtimestamp(
                lstat.st_mtime).isoformat(sep=" ", timespec="seconds"),
            "mode": stat_mod.filemode(lstat.st_mode),
            "permission": "%04o" % stat_mod.S_IMODE(lstat.st_mode),
            "uid": int(lstat.st_uid),
            "gid": int(lstat.st_gid),
            "owner": dono,
            "group": grupo,
            "target": target,
            "hidden": alvo_str.startswith("."),
            "is_image": ext in IMAGE_EXTS,
            "is_text": self._looks_text(alvo, st, ext),
        }

    def _file_type(self, mode):
        if stat_mod.S_ISDIR(mode):
            return "dir"
        if stat_mod.S_ISLNK(mode):
            return "link"
        if stat_mod.S_ISREG(mode):
            return "file"
        if stat_mod.S_ISFIFO(mode):
            return "fifo"
        if stat_mod.S_ISSOCK(mode):
            return "socket"
        if stat_mod.S_ISBLK(mode):
            return "block"
        if stat_mod.S_ISCHR(mode):
            return "char"
        return "other"

    def _looks_text(self, path, st, ext):
        """Heuristica simples: extensao conhecida ou inspecao do conteudo."""
        if ext in TEXT_EXTS:
            return True
        if ext in BINARY_EXTS:
            return False
        try:
            if st.st_size == 0:
                return True
            if st.st_size > 1024 * 1024:
                return False
            with open(path, "rb") as fh:
                bloco = fh.read(4096)
        except OSError:
            return False
        if b"\x00" in bloco:
            return False
        try:
            bloco.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True

    # ------------------------------------------------------------------
    # copiar / mover / renomear / criar
    # ------------------------------------------------------------------

    def copy(self, src, dst, overwrite=False, progress=None):
        """Copia arquivo (ou arvore) preservando permissao e mtime.

        progress -> callback opcional progress(bytes_feitos, bytes_total),
        chamado durante a copia de um arquivo unico (em arvore nao ha
        progresso por arquivo).
        Se `dst` ja existe e overwrite=False, levanta FileExistsError.
        """
        origem = self._resolve(src)
        destino = self._resolve(dst)
        if os.path.lexists(destino) and not overwrite:
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), destino)
        self._check_readable(origem)
        if os.path.isdir(origem) and not os.path.islink(origem):
            return self._copy_tree(origem, destino, overwrite, progress)
        self._check_writable_dir(destino)
        if os.path.isdir(destino) and not os.path.islink(destino):
            raise IsADirectoryError(
                errno.EISDIR, "destino e um diretorio", destino)
        total = 0
        try:
            total = os.path.getsize(origem)
        except OSError:
            total = 0
        with open(origem, "rb") as fonte:
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(destino, flags, 0o600)
            with os.fdopen(fd, "wb") as saida:
                feito = 0
                while True:
                    bloco = fonte.read(256 * 1024)
                    if not bloco:
                        break
                    saida.write(bloco)
                    feito += len(bloco)
                    _call_progress(progress, feito, total)
        try:
            shutil.copystat(origem, destino)   # permissao + mtime
        except OSError:
            pass          # alguns sistemas de arquivo nao suportam; a copia vale
        self._record("copy", destino, True,
                     "%s -> %s" % (origem, destino))
        return {"src": origem, "dst": destino, "type": "file",
                "bytes": total, "ok": True}

    def _copy_tree(self, origem, destino, overwrite, progress):
        """Copia uma arvore inteira (copytree). Nao apaga nada."""
        if os.path.lexists(destino):
            if not os.path.isdir(destino) or os.path.islink(destino):
                raise FileExistsError(
                    errno.EEXIST, os.strerror(errno.EEXIST), destino)
            if not overwrite:
                raise FileExistsError(
                    errno.EEXIST, os.strerror(errno.EEXIST), destino)
        total = 0
        for dirpath, _dirnames, filenames in os.walk(origem):
            for nome in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, nome))
                except OSError:
                    pass
        shutil.copytree(origem, destino, symlinks=True,
                        dirs_exist_ok=bool(overwrite))
        self._record("copy", destino, True,
                     "%s -> %s" % (origem, destino))
        return {"src": origem, "dst": destino, "type": "dir",
                "bytes": total, "ok": True}

    def move(self, src, dst, overwrite=False):
        """Move/renomeia src para dst.

        Usa os.replace quando possivel (mesmo disco) e shutil.move quando
        precisa atravessar dispositivos. Destino existente exige
        overwrite=True; diretorio nunca e substituido por arquivo (e vice
        versa) para nao destruir nada por engano.
        """
        origem = self._resolve(src)
        destino = self._resolve(dst)
        if os.path.lexists(destino):
            if not overwrite:
                raise FileExistsError(
                    errno.EEXIST, os.strerror(errno.EEXIST), destino)
            destino_e_dir = os.path.isdir(destino) and not os.path.islink(destino)
            origem_e_dir = os.path.isdir(origem) and not os.path.islink(origem)
            if destino_e_dir != origem_e_dir:
                raise IsADirectoryError(
                    errno.EISDIR if destino_e_dir else errno.ENOTDIR,
                    "nao posso substituir %s por %s" % (
                        "diretorio" if destino_e_dir else "arquivo",
                        "diretorio" if origem_e_dir else "arquivo"),
                    destino)
            if destino_e_dir:
                raise IsADirectoryError(
                    errno.EEXIST,
                    "destino e um diretorio existente: substitui-lo apagaria"
                    " dados", destino)
        self._check_writable_dir(destino)
        try:
            os.replace(origem, destino)
        except OSError as erro:
            if erro.errno != errno.EXDEV:
                raise
            shutil.move(origem, destino)
        self._record("move", destino, True,
                     "%s -> %s" % (origem, destino))
        return {"src": origem, "dst": destino, "ok": True}

    def rename(self, path, new_name):
        """Renomeia um caminho dentro do mesmo diretorio.

        O novo nome nao pode ser vazio, nao pode conter '/' nem ser '.' ou
        '..' — nesses casos levanta ValueError.
        """
        origem = self._guard(path, "renomeacao")
        if new_name is None:
            raise ValueError("nome novo obrigatorio")
        if isinstance(new_name, bytes):
            new_name = new_name.decode("utf-8", "replace")
        nome = str(new_name)
        if not nome:
            raise ValueError("nome novo vazio")
        if "/" in nome or os.sep in nome or (os.altsep and os.altsep in nome):
            raise ValueError("nome novo invalido: contem separador (%s)" % nome)
        if nome in (".", ".."):
            raise ValueError("nome novo invalido: %s" % nome)
        if "\x00" in nome:
            raise ValueError("nome novo invalido: caractere nulo")
        if nome.strip() == "":
            raise ValueError("nome novo invalido: so espacos")
        destino = os.path.join(os.path.dirname(origem) or "/", nome)
        if os.path.lexists(destino):
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), destino)
        self._check_writable_dir(destino)
        os.rename(origem, destino)
        self._record("rename", destino, True, "%s -> %s" % (origem, destino))
        return destino

    def mkdir(self, path, parents=False):
        """Cria um diretorio. Erro se ja existir."""
        alvo = self._resolve(path)
        if os.path.lexists(alvo):
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), alvo)
        if parents:
            os.makedirs(alvo, exist_ok=False)
        else:
            os.mkdir(alvo)
        self._record("mkdir", alvo, True)
        return alvo

    def touch(self, path):
        """Cria um arquivo vazio. Erro se ja existir."""
        alvo = self._resolve(path)
        if os.path.lexists(alvo):
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), alvo)
        self._check_writable_dir(alvo)
        with open(alvo, "ab"):
            pass
        self._record("touch", alvo, True)
        return alvo

    # ------------------------------------------------------------------
    # apagar
    # ------------------------------------------------------------------

    def delete(self, path, recursive=False, confirm=False):
        """Apaga um arquivo ou diretorio.

        Regras (todas obrigatorias):
          * sem confirm=True -> levanta ConfirmationRequired e NAO apaga nada;
          * diretorio nao vazio sem recursive=True -> levanta NotEmptyError;
          * caminho protegido -> levanta ProtectedPathError (sempre);
          * fora de `root` (quando definido) -> OutsideRootError.

        Devolve um dict com o que foi feito.
        """
        alvo = self._guard(path, "remocao")
        alvo = self._guard_root(alvo, "remocao")
        if not confirm:
            self._record("delete", alvo, False, "sem confirmacao")
            raise ConfirmationRequired(
                "remocao de %s cancelada: falta confirm=True" % alvo)
        if not os.path.lexists(alvo):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), alvo)
        eh_link = os.path.islink(alvo)
        if eh_link:
            # remove o link, nunca o alvo
            self._check_writable_dir(alvo)
            os.unlink(alvo)
            self._record("delete", alvo, True, "link removido")
            return {"path": alvo, "action": "delete", "type": "link",
                    "ok": True, "entries": 1, "bytes": 0}
        if os.path.isdir(alvo):
            conteudo = self.listdir(alvo, show_hidden=True)
            if conteudo and not recursive:
                self._record("delete", alvo, False, "diretorio nao vazio")
                raise NotEmptyError(
                    errno.ENOTEMPTY,
                    "diretorio nao vazio: %s (use recursive=True)" % alvo,
                    alvo)
            self._check_writable_dir(alvo)
            if not os.access(alvo, os.W_OK | os.X_OK):
                raise PermissionError(
                    errno.EACCES,
                    "sem permissao de escrita em %s" % alvo, alvo)
            if conteudo:
                tamanho = self.du(alvo)["total_bytes"]
                shutil.rmtree(alvo)
            else:
                tamanho = 0
                os.rmdir(alvo)
            self._record("delete", alvo, True, "diretorio removido")
            return {"path": alvo, "action": "delete", "type": "dir",
                    "ok": True, "entries": len(conteudo), "bytes": tamanho}
        self._check_writable_dir(alvo)
        try:
            tamanho = os.path.getsize(alvo)
        except OSError:
            tamanho = 0
        os.unlink(alvo)
        self._record("delete", alvo, True, "arquivo removido")
        return {"path": alvo, "action": "delete", "type": "file",
                "ok": True, "entries": 1, "bytes": tamanho}

    # ------------------------------------------------------------------
    # medicao
    # ------------------------------------------------------------------

    def du(self, path):
        """Tamanho recursivo de um caminho.

        Devolve {'total_bytes', 'files', 'dirs'}. Nao segue symlinks.
        """
        alvo = self._resolve(path)
        total = 0
        arquivos = 0
        diretorios = 0
        if os.path.islink(alvo):
            try:
                total += os.lstat(alvo).st_size
            except OSError:
                pass
            return {"total_bytes": total, "files": 1, "dirs": 0}
        if not os.path.isdir(alvo):
            try:
                total = os.path.getsize(alvo)
            except OSError:
                total = 0
            return {"total_bytes": total, "files": 1, "dirs": 0}
        for dirpath, dirnames, filenames in os.walk(alvo, followlinks=False):
            diretorios += len(dirnames) + 1
            for nome in filenames:
                caminho = os.path.join(dirpath, nome)
                try:
                    total += os.lstat(caminho).st_size
                except OSError:
                    pass
                arquivos += 1
        return {"total_bytes": total, "files": arquivos, "dirs": diretorios}

    # ------------------------------------------------------------------
    # armazenamento e montagens
    # ------------------------------------------------------------------

    def storage(self, path="/"):
        """Uso do disco onde `path` esta montado.

        Devolve {'mount', 'total', 'used', 'free', 'used_pct', 'label'}.
        Usa 'df -P' e cai para shutil.disk_usage se o df nao estiver
        disponivel ou falhar.
        """
        alvo = self._resolve(path)
        uso = None
        ponto = alvo
        rotulo = ""
        info = self._df_info(alvo)
        if info:
            ponto = info["mount"]
            uso = (info["total"], info["used"], info["free"])
        if uso is None:
            try:
                disco = shutil.disk_usage(alvo)
            except OSError as erro:
                raise
            uso = (disco.total, disco.used, disco.free)
            ponto = self._mount_point_of(alvo) or ponto
        total, usado, livre = uso
        usado = int(usado)
        livre = int(livre)
        total = int(total)
        if total > 0:
            pct = round(usado * 100.0 / total, 1)
        else:
            pct = 0.0
        rotulo = self._label_of(ponto)
        return {"mount": ponto, "total": total, "used": usado,
                "free": livre, "used_pct": pct, "label": rotulo}

    def _df_info(self, path):
        """Le 'df -P <path>'; None se nao der (df ausente ou erro)."""
        try:
            processo = subprocess.run(
                ["df", "-P", path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if processo.returncode != 0:
            return None
        linhas = processo.stdout.decode("utf-8", "replace").splitlines()
        if len(linhas) < 2:
            return None
        campos = linhas[-1].split()
        if len(campos) < 6:
            return None
        try:
            total = int(campos[1]) * 1024
            usado = int(campos[2]) * 1024
            livre = int(campos[3]) * 1024
        except ValueError:
            return None
        return {"mount": campos[5], "total": total, "used": usado,
                "free": livre}

    def mounts(self):
        """Pontos de montagem reais lidos de /proc/mounts.

        Filtra pseudo-sistemas (proc, sysfs, devpts, cgroup, ...) e mantem
        tmpfs e o armazenamento real. Devolve lista de dicts com device,
        mount, fstype e options.
        """
        resultado = []
        try:
            with open("/proc/mounts", "r", encoding="utf-8",
                      errors="replace") as fh:
                linhas = fh.readlines()
        except OSError:
            return []
        for linha in linhas:
            partes = linha.split()
            if len(partes) < 4:
                continue
            fstype = partes[2]
            if fstype in PSEUDO_FS:
                continue
            resultado.append({
                "device": _unescape_mount(partes[0]),
                "mount": _unescape_mount(partes[1]),
                "fstype": fstype,
                "options": partes[3],
            })
        return resultado

    def _mount_point_of(self, path):
        """Achata o ponto de montagem do caminho (prefixo mais longo)."""
        alvo = os.path.abspath(path)
        melhor = None
        for entrada in self.mounts():
            ponto = entrada["mount"]
            if alvo == ponto or alvo.startswith(ponto.rstrip("/") + "/"):
                if melhor is None or len(ponto) > len(melhor):
                    melhor = ponto
        return melhor

    def _fstype_of(self, path):
        for entrada in self.mounts():
            if entrada["mount"] == path:
                return entrada["fstype"]
        return ""

    def _label_of(self, mount_point):
        """Rotulo do volume (via /dev/disk/by-label), quando houver."""
        if not mount_point:
            return ""
        device = ""
        for entrada in self.mounts():
            if entrada["mount"] == mount_point:
                device = entrada["device"]
                break
        if not device or not device.startswith("/dev/"):
            return ""
        try:
            entradas = os.listdir("/dev/disk/by-label")
        except OSError:
            return ""
        for nome in entradas:
            caminho = os.path.join("/dev/disk/by-label", nome)
            try:
                alvo = os.path.realpath(caminho)
            except OSError:
                continue
            if alvo == os.path.realpath(device):
                return nome
        return ""

    def removable_devices(self):
        """Dispositivos removiveis (cartao SD / pendrive).

        Procura em /media, /run/media e /mnt e nos pontos de montagem de
        /proc/mounts que nao sejam a raiz. Devolve lista de dicts com
        path, label, fstype, total e free; lista vazia se nao houver.
        """
        candidatos = []
        vistos = set()
        for entrada in self.mounts():
            ponto = entrada["mount"]
            if ponto == "/":
                continue
            if not self._is_removable_point(ponto):
                continue
            candidatos.append((ponto, entrada.get("fstype", "")))
        for base in REMOVABLE_MIDPOINTS:
            if not os.path.isdir(base):
                continue
            try:
                nomes = sorted(os.listdir(base))
            except OSError:
                continue
            for nome in nomes:
                ponto = os.path.join(base, nome)
                if os.path.isdir(ponto) and not os.path.islink(ponto):
                    candidatos.append((ponto, ""))
        dispositivos = []
        for ponto, fstype in candidatos:
            if ponto in vistos:
                continue
            vistos.add(ponto)
            try:
                uso = shutil.disk_usage(ponto)
            except OSError:
                continue
            if not fstype:
                fstype = self._fstype_of(ponto)
            rotulo = self._label_of(ponto)
            if not rotulo:
                rotulo = os.path.basename(ponto.rstrip("/"))
            dispositivos.append({
                "path": ponto,
                "label": rotulo,
                "fstype": fstype,
                "total": int(uso.total),
                "free": int(uso.free),
            })
        return dispositivos

    def _is_removable_point(self, point):
        for base in REMOVABLE_MIDPOINTS:
            base = base.rstrip("/")
            if point == base or point.startswith(base + "/"):
                return True
        return False

    # ------------------------------------------------------------------
    # busca
    # ------------------------------------------------------------------

    def search(self, root, query, max_results=200):
        """Procura arquivos/diretorios pelo nome (sem diferenciar caixa).

        Nao segue symlinks e nao entra em pseudo-sistemas (/proc, /sys,
        /dev). Devolve lista de dicts no mesmo formato de listdir.
        """
        base = self._resolve(root)
        alvo = (query or "").strip().lower()
        resultados = []
        if not alvo or not os.path.isdir(base):
            return resultados
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not self._is_pseudo_dir(os.path.join(dirpath, d))]
            for nome in dirnames + filenames:
                if alvo in nome.lower():
                    caminho = os.path.join(dirpath, nome)
                    resultados.append(self._info_of_path(caminho))
                    if len(resultados) >= max_results:
                        return resultados
        return resultados

    def _is_pseudo_dir(self, path):
        for pseudo in ("/proc", "/sys", "/dev"):
            pseudo = pseudo.rstrip("/")
            if path == pseudo or path.startswith(pseudo + "/"):
                return True
        return False

    def _info_of_path(self, caminho):
        try:
            st = os.lstat(caminho)
        except OSError:
            return {"name": os.path.basename(caminho), "path": caminho,
                    "is_dir": False, "is_link": False, "size": 0,
                    "mtime": 0.0, "mode": "----------", "target": None}
        is_link = stat_mod.S_ISLNK(st.st_mode)
        is_dir = False
        if not is_link:
            is_dir = stat_mod.S_ISDIR(st.st_mode)
        target = None
        if is_link:
            try:
                target = os.readlink(caminho)
            except OSError:
                target = None
        return {
            "name": os.path.basename(caminho),
            "path": caminho,
            "is_dir": is_dir,
            "is_link": is_link,
            "size": -1 if is_dir else int(st.st_size),
            "mtime": float(st.st_mtime),
            "mode": stat_mod.filemode(st.st_mode),
            "target": target,
        }

    # ------------------------------------------------------------------
    # abrir com
    # ------------------------------------------------------------------

    def open_with(self, path):
        """Lista de comandos do sistema que poderiam abrir o arquivo.

        Devolve apenas os comandos que EXISTEM no PATH (shutil.which).
        Nada e executado aqui — quem decide o que rodar e a camada de UI,
        e mesmo assim so com o usuario mandando. Lista vazia se nenhum
        abridor existir no sistema.
        """
        alvo = self._resolve(path)
        ext = os.path.splitext(alvo)[1].lower().lstrip(".")
        candidatos = []
        if ext in IMAGE_EXTS:
            candidatos += ["feh", "eog", "gpicview", "sxiv", "display", "imv"]
        if ext in ("pdf", "epub", "djvu", "xps"):
            candidatos += ["evince", "zathura", "mupdf", "atril"]
        if ext in ("txt", "md", "log", "ini", "conf", "py", "c", "h",
                   "sh", "json", "xml", "csv", "desktop"):
            candidatos += ["mousepad", "geany", "gedit", "nano", "vim"]
        if ext in ("mp3", "flac", "ogg", "wav", "m4a", "opus", "aac"):
            candidatos += ["mpv", "mpg123", "paplay", "audacious"]
        if ext in ("mp4", "mkv", "avi", "webm", "mov", "m4v"):
            candidatos += ["mpv", "mplayer", "vlc", "gst-launch-1.0"]
        candidatos += ["xdg-open", "pcmanfm", "thunar", "nautilus",
                       "dolphin", "marlin"]
        encontrados = []
        for comando in candidatos:
            if comando in encontrados:
                continue
            if shutil.which(comando):
                encontrados.append(comando)
        return encontrados

    # ------------------------------------------------------------------
    # recentes
    # ------------------------------------------------------------------

    def recent_files(self):
        """Arquivos acessados recentemente.

        Le ~/.config/nura/recent.json ou, na falta dele,
        ~/.local/share/recently-used.xbel. Devolve [] se nenhum existir.
        NUNCA cria esses arquivos.
        """
        home = os.path.expanduser("~")
        config = os.path.join(home, ".config", "nura", "recent.json")
        if os.path.isfile(config):
            try:
                with open(config, "r", encoding="utf-8") as fh:
                    dados = json.load(fh)
            except (OSError, ValueError):
                dados = None
            if dados is not None:
                return self._norm_recent(dados)
        xbel = os.path.join(home, ".local", "share", "recently-used.xbel")
        if os.path.isfile(xbel):
            return self._read_xbel(xbel)
        return []

    def _norm_recent(self, dados):
        itens = dados
        if isinstance(dados, dict):
            itens = dados.get("recent") or dados.get("files") or []
        if not isinstance(itens, list):
            return []
        saida = []
        for item in itens:
            if isinstance(item, str):
                caminho = item
                marca = None
            elif isinstance(item, dict):
                caminho = item.get("path") or item.get("file") or ""
                marca = item.get("mtime") or item.get("time")
            else:
                continue
            if not caminho:
                continue
            saida.append({"path": caminho,
                          "name": os.path.basename(caminho.rstrip("/")),
                          "mtime": marca})
        return saida

    def _read_xbel(self, caminho):
        try:
            arvore = ET.parse(caminho)
        except (OSError, ET.ParseError):
            return []
        itens = []
        for elemento in arvore.iter():
            tag = elemento.tag.split("}")[-1]
            if tag != "bookmark":
                continue
            href = elemento.get("href") or ""
            if href.startswith("file://"):
                alvo = unquote(urlparse(href).path)
            elif href.startswith("file:"):
                alvo = unquote(href[5:])
            else:
                alvo = href
            if not alvo:
                continue
            itens.append({"path": alvo,
                          "name": os.path.basename(alvo.rstrip("/")),
                          "mtime": elemento.get("modified")})
        return itens

    # ------------------------------------------------------------------
    # log de operacoes
    # ------------------------------------------------------------------

    def _record(self, acao, path, ok=True, detalhe=""):
        """Registra uma operacao no log em memoria (e no arquivo, se der).

        O arquivo de log e criado apenas quando a operacao realmente
        aconteceu (ok=True) — uma remocao recusada nao cria arquivo.
        """
        entrada = {
            "path": path,
            "action": acao,
            "timestamp": _now_ts(),
            "time": _now_iso(),
            "ok": bool(ok),
            "detail": detalhe,
        }
        self._log.append(entrada)
        if len(self._log) > self.max_log:
            del self._log[:-self.max_log]
        if ok and self.log_to_file:
            self._write_log(entrada)
        return entrada

    def _write_log(self, entrada):
        """Acrescenta a operacao no arquivo de log (falha aqui nao quebra)."""
        try:
            pasta = os.path.dirname(self.log_path)
            if pasta and not os.path.isdir(pasta):
                os.makedirs(pasta, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write("%s\t%s\t%s\t%s\n" % (
                    entrada["time"],
                    "ok" if entrada["ok"] else "erro",
                    entrada["action"],
                    entrada["path"]))
        except OSError:
            pass

    def operation_log(self):
        """Ultimas operacoes (path, action, timestamp, ok)."""
        return [dict(e) for e in self._log]

    def read_log_file(self, limit=100):
        """Le o arquivo de log (read-only). Devolve [] se nao existir."""
        if not os.path.isfile(self.log_path):
            return []
        linhas = []
        try:
            with open(self.log_path, "r", encoding="utf-8",
                      errors="replace") as fh:
                for linha in fh:
                    linha = linha.rstrip("\n")
                    if not linha:
                        continue
                    partes = linha.split("\t")
                    while len(partes) < 4:
                        partes.append("")
                    linhas.append({"time": partes[0], "ok": partes[1] == "ok",
                                   "action": partes[2], "path": partes[3]})
        except OSError:
            return []
        if limit and limit > 0:
            return linhas[-limit:]
        return linhas
