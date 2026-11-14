"""NURA OS — NURA Terminal (terminal grafico nativo do NURA).

Um terminal completo desenhado em cairo, pensado para o NX591J em
paisagem 1920x1080, touch-first, tema preto/azul-neon.

 ---------------------------------------------------------------------------
 O QUE ESTE APP **NAO** E
 ---------------------------------------------------------------------------
 Este app NAO substitui o terminal real do sistema. O console/TTY do Linux
 (e o `getty`/`agetty` do init) continuam existindo e continuam sendo a
 forma canonica de recuperar o aparelho (por exemplo `Ctrl+Alt+F2` no
 console virtual, ou um `screen`/`tmux` iniciado fora daqui).

 Aqui rodam **sessoes de shell do usuario normal** (`$SHELL`, `/bin/ash`
 ou `/bin/sh`), em PTY, com as mesmas permissoes do usuario que esta
 logado. O app nao eleva privilegio: nunca chama `setuid`, nunca roda
 `sudo` por conta propria e nunca escreve em device de bloco.

 ---------------------------------------------------------------------------
 SEGURANCA
 ---------------------------------------------------------------------------
 Comandos administrativos (sudo, su, mount, mkfs, dd para device, ...)
 passam por `BLOCKED_PATTERNS`. Quando o padrao e detectado, o app
 pede confirmacao EXPLICITA via `self.shell.confirm(...)` antes de
 escrever o comando na PTY. Sem confirmacao, o comando nao roda.

 ---------------------------------------------------------------------------
 CONTRATO DE TECLAS (o shell entrega assim)
 ---------------------------------------------------------------------------
 O shell chama `app.on_key(ev)` com um objeto que possui:

     ev.key    -> str   nome da tecla ("Return", "BackSpace", "Up",
                          "a", "space", ...) ou "ctrl+c" / "alt+Tab"
     ev.text   -> str   texto a inserir (opcional; default "")
     ev.ctrl   -> bool  modificador Control
     ev.alt    -> bool  modificador Alt
     ev.shift  -> bool  modificador Shift

 Dict com as mesmas chaves tambem e aceito (`{"key": ..., "text": ...}`),
 assim como uma string simples com o nome da tecla.
 Ver `TerminalKey` (classe pronta para o shell instanciar).

 ---------------------------------------------------------------------------
 SO BIBLIOTECA PADRAO
 ---------------------------------------------------------------------------
 os, sys, subprocess, pty, select, signal, threading, time, shlex, re
 (+ fcntl/termios para o ioctl TIOCSWINSZ da PTY e errno para o EIO).
 Nada de readline, curses, GTK ou X11.
"""

import errno
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import time

try:                                   # ioctl da PTY (Linux/BSD)
    import fcntl
    import termios
except ImportError:                    # pragma: no cover
    fcntl = None
    termios = None

try:
    import pty
except ImportError:                    # pragma: no cover
    pty = None

try:
    from nura_window import App
except Exception:                      # pragma: no cover
    # fallback minimo: permite importar o modulo (e testar o filtro de
    # comandos perigosos) mesmo sem a camada de janelas.
    class App(object):
        title = "Aplicativo"
        icon = "terminal"
        width = 900
        height = 620
        min_width = 480
        min_height = 320
        resizable = True

        def __init__(self, shell=None, **kw):
            self.shell = shell
            self.ctx_data = kw
            self.window = None
            self._t0 = 0.0

try:
    import nura_theme as T
except Exception:                      # pragma: no cover
    T = None

MONO = "monospace"

# --------------------------------------------------------------------
# filtro de comandos perigosos
# --------------------------------------------------------------------
# Cada padrao aponta para uma operacao administrativa/destrutiva.
# O app NUNCA eleva privilegio: quando o padrao casa, o usuario tem que
# confirmar explicitamente antes do comando ser entregue a PTY.

BLOCKED_PATTERNS = [
    # --- elevacao de privilegio ---
    re.compile(r"(?:^|[\s;|&(`$/])(?:sudo|doas|pkexec|runuser)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])su(?![\w-])"),
    # --- sistema de arquivos e devices ---
    re.compile(r"(?:^|[\s;|&(`$/])(?:mount|umount)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])mkfs(?:\.[A-Za-z0-9_]+)?(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:mke2fs|mkdosfs|mkswap|newfs)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])dd(?![\w-])(?=[\s\S]*(?:/dev/|of=))"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:fdisk|sfdisk|cfdisk|gdisk|sgdisk|parted"
               r"|wipefs|blkdiscard|hdparm)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:chown|chgrp|chattr|setfacl)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:chroot|unshare)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:insmod|rmmod|modprobe)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:systemctl|rc-service|rc-update|telinit)"
               r"(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:reboot|poweroff|halt|shutdown)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:passwd|chpasswd|useradd|adduser|userdel"
               r"|deluser|usermod|groupadd|groupdel|groupmod)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])(?:iptables|ip6tables|nft)(?![\w-])"),
    re.compile(r"(?:^|[\s;|&(`$/])init(?![\w-])"),
    # --- redirecionamento para device ---
    re.compile(r">\s*/dev/[A-Za-z0-9]"),
    # --- remocao destrutiva ---
    re.compile(r"(?:^|[\s;|&(`$/])rm\s+-[A-Za-z]*[rf][A-Za-z]*\s+"
               r"(?:/|/\*|~|\$HOME)(?:\s|$)"),
]

BLOCKED_LABELS = [
    "elevacao de privilegio (sudo/doas/pkexec)",
    "troca de usuario (su)",
    "montagem de sistema de arquivos (mount/umount)",
    "formatacao de disco (mkfs)",
    "formatacao de disco (mkfs/mkswap)",
    "escrita direta em device (dd)",
    "particionamento de disco",
    "alteracao de proprietario/permissao de arquivo do sistema",
    "mudar de raiz (chroot/unshare)",
    "carregar modulo do kernel (insmod/modprobe)",
    "gerenciamento de servico do sistema",
    "desligar/reiniciar a maquina",
    "gerenciamento de contas do sistema",
    "configuracao de firewall",
    "alterar o init do sistema",
    "redirecionamento para device (/dev/...)",
    "remocao destrutiva (rm -rf /)",
]


def is_blocked(cmd):
    """True se o comando precisa de confirmacao do usuario.

    >>> is_blocked("sudo ls")
    True
    >>> is_blocked("ls -la")
    False
    """
    if not cmd or not isinstance(cmd, str):
        return False
    text = cmd.strip()
    if not text:
        return False
    for pat in BLOCKED_PATTERNS:
        try:
            if pat.search(text):
                return True
        except re.error:               # pragma: no cover
            continue
    return False


def blocked_reason(cmd):
    """Motivo (texto) do bloqueio, ou '' se o comando nao for bloqueado."""
    if not cmd or not isinstance(cmd, str):
        return ""
    text = cmd.strip()
    for pat, label in zip(BLOCKED_PATTERNS, BLOCKED_LABELS):
        try:
            if pat.search(text):
                return label
        except re.error:               # pragma: no cover
            continue
    return ""


# --------------------------------------------------------------------
# palettes ANSI (16 cores + 256)
# --------------------------------------------------------------------

ANSI16 = [
    (0.05, 0.05, 0.08), (0.86, 0.33, 0.33), (0.35, 0.85, 0.42),
    (0.95, 0.76, 0.28), (0.38, 0.58, 0.96), (0.76, 0.48, 0.92),
    (0.38, 0.86, 0.92), (0.82, 0.85, 0.90),
    (0.36, 0.39, 0.45), (0.97, 0.47, 0.44), (0.47, 0.94, 0.55),
    (1.00, 0.87, 0.45), (0.55, 0.72, 1.00), (0.90, 0.62, 1.00),
    (0.58, 0.96, 1.00), (1.00, 1.00, 1.00),
]


def xterm256(n):
    """Converte um indice xterm-256 em RGB 0..1."""
    n = int(n) & 0xFF
    if n < 16:
        return ANSI16[n]
    if n < 232:
        n -= 16
        r, g, b = n // 36, (n // 6) % 6, n % 6

        def _c(v):
            return 0.0 if v == 0 else (55.0 + 40.0 * v) / 255.0
        return (_c(r), _c(g), _c(b))
    v = ((n - 232) * 10 + 8) / 255.0
    return (v, v, v)


# --------------------------------------------------------------------
# evento de teclado
# --------------------------------------------------------------------

class TerminalKey(object):
    """Evento de tecla entregue pelo shell ao terminal.

    Campos:
        key   -> nome da tecla ("Return", "BackSpace", "Up", "a", ...)
        text  -> texto a inserir (opcional)
        ctrl  -> bool
        alt   -> bool
        shift -> bool
    """

    __slots__ = ("key", "text", "ctrl", "alt", "shift")

    def __init__(self, key="", text="", ctrl=False, alt=False, shift=False):
        self.key = key or ""
        self.text = text if text is not None else ""
        self.ctrl = bool(ctrl)
        self.alt = bool(alt)
        self.shift = bool(shift)

    def __repr__(self):
        mods = ""
        if self.ctrl:
            mods += "ctrl+"
        if self.alt:
            mods += "alt+"
        if self.shift:
            mods += "shift+"
        return "<TerminalKey %s%s>" % (mods, self.key)


# --------------------------------------------------------------------
# sessao de shell (PTY)
# --------------------------------------------------------------------

def _winsize(rows, cols):
    """Empacota um struct winsize (rows, cols, xpix, ypix) sem struct."""
    rows = int(rows) & 0xFFFF
    cols = int(cols) & 0xFFFF
    return bytes((rows & 0xFF, (rows >> 8) & 0xFF,
                  cols & 0xFF, (cols >> 8) & 0xFF,
                  0, 0, 0, 0))


class ShellSession(object):
    """Uma sessao de shell real (o usuario normal, sem privilegio extra).

    Usa `pty.fork()` para ter um TTY de verdade (o shell do Alpine e o
    busybox ash precisam disso para o prompt, para o `stty` e para o
    SIGWINCH). Se a PTY nao estiver disponivel, cai para
    `subprocess.Popen` com pipes.

    Nunca bloqueia: `read_available()` usa `select` com timeout 0.
    """

    def __init__(self, shell=None, command=None, env=None, rows=24, cols=80,
                 cwd=None):
        self.shell = shell
        self.command = command
        self.rows = int(rows)
        self.cols = int(cols)
        self.cwd = cwd
        self.mode = "none"           # "pty" | "pipe" | "none"
        self._pid = None
        self._fd = None
        self._in_fd = None
        self._proc = None
        self._closed = False
        self._reaped = False
        self._status = None
        self._wbuf = b""
        self._eof = False

        base = dict(os.environ)
        if env:
            base.update(env)
        base.setdefault("TERM", "xterm-256color")
        base["COLUMNS"] = str(self.cols)
        base["LINES"] = str(self.rows)
        if cwd:
            base["PWD"] = cwd
        self.env = base

        self.cmd = self._resolve_cmd()
        self._spawn()

    # ---------------- execucao ----------------

    def _resolve_cmd(self):
        if self.command:
            if isinstance(self.command, (list, tuple)):
                cmd = [str(c) for c in self.command]
            else:
                try:
                    cmd = shlex.split(self.command)
                except ValueError:
                    cmd = [str(self.command)]
            if cmd:
                return cmd
        env_shell = os.environ.get("SHELL") or ""
        if env_shell and os.path.exists(env_shell):
            return [env_shell]
        for cand in ("/bin/ash", "/usr/bin/ash", "/bin/sh", "/usr/bin/sh",
                     "/bin/bash"):
            if os.path.exists(cand):
                return [cand]
        return ["/bin/sh"]

    def _spawn(self):
        if pty is not None:
            try:
                pid, fd = pty.fork()
            except (OSError, AttributeError):
                pid = None
            if pid is not None:
                if pid == 0:            # processo filho
                    try:
                        os.environ.clear()
                        os.environ.update(self.env)
                        if self.cwd:
                            try:
                                os.chdir(self.cwd)
                            except OSError:
                                pass
                        os.execvp(self.cmd[0], self.cmd)
                    except BaseException:
                        pass
                    os._exit(127)
                # processo pai
                self.mode = "pty"
                self._pid = pid
                self._fd = fd
                try:
                    os.set_blocking(fd, False)
                except OSError:          # pragma: no cover
                    pass
                self.resize(self.rows, self.cols)
                return
        self._spawn_pipe()

    def _spawn_pipe(self):
        """Fallback: subprocess com pipes (sem TTY)."""
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=self.env,
                cwd=self.cwd,
                bufsize=0,
                close_fds=True,
            )
        except (OSError, ValueError):
            self.mode = "none"
            return
        self.mode = "pipe"
        self._pid = self._proc.pid
        self._fd = self._proc.stdout.fileno()
        self._in_fd = self._proc.stdin.fileno()
        for fd in (self._fd, self._in_fd):
            try:
                os.set_blocking(fd, False)
            except OSError:              # pragma: no cover
                pass

    # ---------------- leitura / escrita ----------------

    def write(self, data):
        """Envia bytes/texto para o shell. Nunca bloqueia."""
        if self._closed:
            return 0
        if isinstance(data, str):
            data = data.encode("utf-8", "replace")
        elif not isinstance(data, (bytes, bytearray)):
            return 0
        self._wbuf += bytes(data)
        return self._flush_writes()

    def _flush_writes(self):
        sent = 0
        while self._wbuf:
            try:
                if self.mode == "pty":
                    n = os.write(self._fd, self._wbuf)
                elif self.mode == "pipe":
                    n = os.write(self._in_fd, self._wbuf)
                else:
                    self._wbuf = b""
                    break
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                self._wbuf = b""
                break
            if n <= 0:
                break
            self._wbuf = self._wbuf[n:]
            sent += n
        return sent

    def read_available(self, limit=65536):
        """Le o que estiver disponivel na PTY (nao bloqueante)."""
        if self._closed:
            return b""
        self._flush_writes()
        if self._fd is None:
            return b""
        try:
            ready, _, _ = select.select([self._fd], [], [], 0)
        except (OSError, ValueError):
            return b""
        if not ready:
            return b""
        try:
            data = os.read(self._fd, limit)
        except (BlockingIOError, InterruptedError):
            return b""
        except OSError as e:
            if e.errno in (errno.EIO, errno.EBADF):
                # EOF da PTY (filho morreu)
                self._eof = True
            return b""
        if not data:
            self._eof = True
            return b""
        return data

    # ---------------- estado ----------------

    @property
    def pid(self):
        return self._pid

    @property
    def alive(self):
        """True enquanto o processo do shell estiver vivo."""
        if self._closed:
            return False
        if self.mode == "pipe":
            if self._proc is None:
                return False
            return self._proc.poll() is None
        if self._pid is None or self._reaped:
            return False
        try:
            pid, status = os.waitpid(self._pid, os.WNOHANG)
        except OSError:
            return False
        except ChildProcessError:       # pragma: no cover
            return False
        if pid == self._pid:
            self._reaped = True
            self._status = status
            return False
        return True

    @property
    def eof(self):
        return self._eof

    def cwd_of(self):
        """Diretorio de trabalho da sessao (via /proc/<pid>/cwd)."""
        if self._pid:
            try:
                return os.readlink("/proc/%d/cwd" % self._pid)
            except OSError:
                pass
        try:
            return os.getcwd()
        except OSError:                 # pragma: no cover
            return None

    # ---------------- tamanho ----------------

    def resize(self, rows, cols):
        """Ajusta o tamanho da PTY (TIOCSWINSZ) e COLUMNS/LINES."""
        try:
            rows = int(rows)
            cols = int(cols)
        except (TypeError, ValueError):
            return False
        if rows < 1:
            rows = 1
        if cols < 1:
            cols = 1
        self.rows = rows
        self.cols = cols
        self.env["COLUMNS"] = str(cols)
        self.env["LINES"] = str(rows)
        if self.mode == "pty" and self._fd is not None and \
                fcntl is not None and termios is not None:
            try:
                fcntl.ioctl(self._fd, termios.TIOCSWINSZ,
                            _winsize(rows, cols))
            except OSError:
                pass
        return True

    def interrupt(self):
        """Ctrl+C: envia SIGINT para o processo do shell."""
        if not self._pid or self._closed:
            return False
        try:
            pgid = os.getpgid(self._pid)
        except OSError:
            pgid = None
        try:
            if pgid and pgid != os.getpgrp():
                os.killpg(pgid, signal.SIGINT)
            else:
                os.kill(self._pid, signal.SIGINT)
            return True
        except OSError:
            return False

    # ---------------- encerramento ----------------

    def close(self):
        """Encerra a sessao (fecha a PTY e mata o shell)."""
        if self._closed:
            return
        self._closed = True
        # 1) derruba o shell
        if self.mode == "pipe" and self._proc is not None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        elif self._pid:
            # o shell da PTY e o lider do seu proprio grupo de processos:
            # derruba o grupo todo (inclui programas em foreground)
            pgid = None
            try:
                pgid = os.getpgid(self._pid)
            except OSError:
                pgid = None
            try:
                if pgid is not None and pgid == self._pid:
                    os.killpg(pgid, signal.SIGHUP)
                else:
                    os.kill(self._pid, signal.SIGHUP)
            except OSError:
                pass
        # 2) fecha os descritores
        for fd in (self._fd, self._in_fd):
            if fd is not None and fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._fd = None
        self._in_fd = None
        # 3) reapa o filho
        if self._pid and not self._reaped:
            for _ in range(20):
                try:
                    pid, status = os.waitpid(self._pid, os.WNOHANG)
                except OSError:
                    break
                if pid == self._pid:
                    self._reaped = True
                    self._status = status
                    break
                time.sleep(0.01)
            if not self._reaped:
                try:
                    pgid = os.getpgid(self._pid)
                except OSError:
                    pgid = None
                try:
                    if pgid is not None and pgid == self._pid:
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        os.kill(self._pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    os.waitpid(self._pid, 0)
                except OSError:
                    pass
                self._reaped = True

    def __del__(self):                   # pragma: no cover
        try:
            self.close()
        except Exception:
            pass


# --------------------------------------------------------------------
# buffer de saida (interpretador leve de ANSI)
# --------------------------------------------------------------------

class OutputBuffer(object):
    """Guarda a saida do shell como linhas com segmentos coloridos.

    Cada linha e uma lista de [texto, cor]. Interpreta CR, LF, TAB,
    BS e as sequencias SGR do ANSI (cores 16, 256 e truecolor).
    """

    def __init__(self, max_lines=2000):
        self.max_lines = int(max_lines)
        self.lines = []
        self._cur = []            # celulas da linha atual: [(char, cor)]
        self._color = None        # cor SGR ativa (RGB ou None)
        self._col = 0
        self._pending = ""        # escape incompleto (chegou no fim do chunk)

    # ---------------- escrita ----------------

    def feed(self, data):
        if not data:
            return
        if isinstance(data, (bytes, bytearray)):
            text = bytes(data).decode("utf-8", "replace")
        else:
            text = str(data)
        if self._pending:
            text = self._pending + text
            self._pending = ""
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\x1b":
                used, self._pending = self._escape(text, i)
                if self._pending:
                    break
                i += used
                continue
            i += 1
            if ch == "\n":
                self._newline()
            elif ch == "\r":
                self._col = 0
            elif ch == "\b":
                self._col = max(0, self._col - 1)
            elif ch == "\t":
                self._col = (self._col // 8 + 1) * 8
            elif ch == "\x07" or ch == "\x00":
                continue
            elif ch >= " ":
                self._put(ch)

    def _escape(self, text, i):
        """Processa uma sequencia ESC. Devolve (consumido, pendente)."""
        n = len(text)
        if i + 1 >= n:
            return 0, text[i:]
        c = text[i + 1]
        if c == "[":
            j = i + 2
            while j < n and (0x20 <= ord(text[j]) <= 0x3F):
                j += 1
            if j >= n:
                return 0, text[i:]
            final = text[j]
            if final == "m":
                self._sgr(text[i + 2:j])
            return (j + 1 - i), ""
        if c == "]":                      # OSC (titulo) -> ignora
            j = i + 2
            while j < n:
                if text[j] == "\x07":
                    return (j + 1 - i), ""
                if text[j] == "\x1b" and j + 1 < n and text[j + 1] == "\\":
                    return (j + 2 - i), ""
                j += 1
            return 0, text[i:]
        if c in "()#":
            if i + 2 >= n:
                return 0, text[i:]
            return (i + 3 - i), ""
        return (2), ""

    def _sgr(self, params):
        """Interpreta uma sequencia SGR (m)."""
        if params == "":
            params = "0"
        try:
            nums = [int(x) if x.strip() else 0
                    for x in params.replace(":", ";").split(";")]
        except ValueError:
            nums = [0]
        i = 0
        while i < len(nums):
            v = nums[i]
            if v == 0:
                self._color = None
            elif v == 1:
                pass                    # negrito: mantido simples
            elif v == 22:
                pass
            elif 30 <= v <= 37:
                self._color = ANSI16[v - 30]
            elif v == 39:
                self._color = None
            elif 40 <= v <= 47:
                pass                    # cor de fundo: ignorada
            elif v == 49:
                pass
            elif 90 <= v <= 97:
                self._color = ANSI16[v - 90]
            elif 100 <= v <= 107:
                pass
            elif v in (38, 48):
                if i + 1 < len(nums) and nums[i + 1] == 5 and i + 2 < len(nums):
                    if v == 38:
                        self._color = xterm256(nums[i + 2])
                    i += 2
                elif i + 1 < len(nums) and nums[i + 1] == 2 and i + 4 < len(nums):
                    if v == 38:
                        self._color = (nums[i + 2] / 255.0,
                                       nums[i + 3] / 255.0,
                                       nums[i + 4] / 255.0)
                    i += 4
            i += 1

    def _put(self, ch):
        if self._col < len(self._cur):
            self._cur[self._col] = (ch, self._color)
        else:
            while len(self._cur) <= self._col:
                self._cur.append((" ", None))
            self._cur[self._col] = (ch, self._color)
        self._col += 1

    def _newline(self):
        self.lines.append(self._segments(self._cur))
        self._cur = []
        self._col = 0
        if len(self.lines) > self.max_lines:
            del self.lines[:len(self.lines) - self.max_lines]

    def add_line(self, text, color=None):
        """Insere uma linha 'sintetica' (notas do proprio app)."""
        self.lines.append([[text, color]])
        if len(self.lines) > self.max_lines:
            del self.lines[:len(self.lines) - self.max_lines]

    def clear(self):
        self.lines = []
        self._cur = []
        self._col = 0
        self._color = None
        self._pending = ""

    # ---------------- leitura ----------------

    @staticmethod
    def _segments(cells):
        segs = []
        for ch, color in cells:
            if segs and segs[-1][1] == color:
                segs[-1][0] += ch
            else:
                segs.append([ch, color])
        while segs:
            segs[-1][0] = segs[-1][0].rstrip()
            if segs[-1][0]:
                break
            segs.pop()
        return [(t, c) for (t, c) in segs]

    def visible_lines(self):
        """Todas as linhas (incluindo a linha parcial em andamento)."""
        out = list(self.lines)
        cur = self._segments(self._cur)
        if cur:
            out.append(cur)
        return out

    @staticmethod
    def line_text(line):
        return "".join(t for (t, _c) in line)


# --------------------------------------------------------------------
# temas de cor do terminal
# --------------------------------------------------------------------

COLOR_THEME_NAMES = ["Neon", "Verde", "Ambiente"]

COLOR_THEMES = {
    "Neon": {
        "bg": (0.016, 0.020, 0.036),
        "panel": (0.043, 0.055, 0.094),
        "panel_hi": (0.090, 0.118, 0.184),
        "fg": (0.902, 0.941, 0.980),
        "dim": (0.451, 0.494, 0.573),
        "accent": (0.106, 0.855, 0.980),
        "cursor": (0.106, 0.855, 0.980),
        "sel": (0.098, 0.176, 0.282),
        "warn": (0.980, 0.729, 0.239),
        "err": (0.957, 0.400, 0.400),
    },
    "Verde": {
        "bg": (0.016, 0.043, 0.027),
        "panel": (0.043, 0.090, 0.055),
        "panel_hi": (0.078, 0.153, 0.094),
        "fg": (0.855, 0.980, 0.878),
        "dim": (0.404, 0.596, 0.463),
        "accent": (0.290, 0.925, 0.514),
        "cursor": (0.290, 0.925, 0.514),
        "sel": (0.071, 0.180, 0.106),
        "warn": (0.925, 0.800, 0.290),
        "err": (0.980, 0.400, 0.400),
    },
    "Ambiente": {
        "bg": (0.055, 0.055, 0.047),
        "panel": (0.098, 0.098, 0.086),
        "panel_hi": (0.153, 0.153, 0.133),
        "fg": (0.933, 0.929, 0.902),
        "dim": (0.576, 0.573, 0.541),
        "accent": (0.847, 0.788, 0.588),
        "cursor": (0.925, 0.878, 0.694),
        "sel": (0.145, 0.145, 0.129),
        "warn": (0.949, 0.749, 0.325),
        "err": (0.898, 0.400, 0.361),
    },
}


# --------------------------------------------------------------------
# app
# --------------------------------------------------------------------

class _Tab(object):
    """Estado de uma aba (sessao + buffer + rolagem)."""

    __slots__ = ("session", "buffer", "scroll", "hist_idx", "hist_tmp", "dead")

    def __init__(self, session, buffer):
        self.session = session
        self.buffer = buffer
        self.scroll = 0
        self.hist_idx = None
        self.hist_tmp = ""
        self.dead = False


class TerminalApp(App):
    """NURA Terminal: terminal grafico nativo, touch-first."""

    title = "NURA Terminal"
    icon = "terminal"
    width = 980
    height = 620
    min_width = 560
    min_height = 360
    resizable = True

    MAX_SESSIONS = 4
    MAX_LINES = 2000
    MAX_HISTORY = 100
    MIN_ZOOM = 12
    MAX_ZOOM = 24

    # ----------------------------------------------------------------
    # ciclo de vida
    # ----------------------------------------------------------------

    def __init__(self, shell=None, history_path=None, max_lines=None,
                 max_history=None, **kw):
        App.__init__(self, shell=shell, **kw)
        self.tabs = []
        self.active = 0
        self.input_line = ""
        self.input_pos = 0
        self.history = []
        self.history_path = history_path or self._default_history_path()
        self.max_lines = int(max_lines or self.MAX_LINES)
        self.max_history = int(max_history or self.MAX_HISTORY)
        self.zoom = 16
        self.color_theme = "Neon"
        self.dirty = 0
        self.needs_redraw = False
        self.popup = None
        self.clipboard = ""
        self.focused = True
        self.selected_line = None
        self._blink = True
        self._blink_t = 0.0
        self._cwd = ""
        self._cwd_t = 0.0
        self._pressed = None
        self._buttons = []
        self._m = None                  # metricas da ultima renderizacao
        self._ctx = None
        self._cols = 80
        self._rows = 24

    @staticmethod
    def _default_history_path():
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", "nura", "history")

    def on_open(self):
        self.load_history()
        self._ensure_session()

    def on_close(self):
        for tab in self.tabs:
            try:
                tab.session.close()
            except Exception:
                pass
        self.tabs = []
        self.active = 0

    def on_focus(self, focused):
        self.focused = bool(focused)

    # ----------------------------------------------------------------
    # sessoes
    # ----------------------------------------------------------------

    @property
    def sessions(self):
        """Lista de ShellSession (uma por aba)."""
        return [t.session for t in self.tabs]

    def _ensure_session(self):
        if not self.tabs:
            self.new_session()
        return self._active_tab()

    def new_session(self):
        """Abre uma nova aba com um shell do usuario normal."""
        if len(self.tabs) >= self.MAX_SESSIONS:
            self._notify("Limite de %d sessoes." % self.MAX_SESSIONS, "warn")
            return None
        try:
            session = ShellSession(shell=self.shell)
        except Exception as e:            # pragma: no cover
            self._notify("Nao foi possivel abrir o shell: %s" % e, "err")
            return None
        tab = _Tab(session, OutputBuffer(self.max_lines))
        self.tabs.append(tab)
        self.active = len(self.tabs) - 1
        self.dirty += 1
        self.needs_redraw = True
        return tab

    def close_session(self, index=None):
        if index is None:
            index = self.active
        if not (0 <= index < len(self.tabs)):
            return False
        tab = self.tabs.pop(index)
        try:
            tab.session.close()
        except Exception:
            pass
        if not self.tabs:
            self.new_session()
        elif self.active >= len(self.tabs):
            self.active = len(self.tabs) - 1
        self.dirty += 1
        self.needs_redraw = True
        return True

    def switch_session(self, index):
        if 0 <= index < len(self.tabs) and index != self.active:
            self.active = index
            self.popup = None
            self.dirty += 1
            self.needs_redraw = True
            return True
        return False

    def _active_tab(self):
        if 0 <= self.active < len(self.tabs):
            return self.tabs[self.active]
        return None

    def _active_session(self):
        tab = self._active_tab()
        return tab.session if tab else None

    # ----------------------------------------------------------------
    # historico
    # ----------------------------------------------------------------

    def load_history(self):
        path = self.history_path
        if not path or not os.path.exists(path):
            self.history = []
            return self.history
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            self.history = []
            return self.history
        items = [ln for ln in raw.splitlines() if ln.strip()]
        items.reverse()                 # mais recente primeiro
        self.history = items[:self.max_history]
        return self.history

    def save_history(self):
        path = self.history_path
        if not path:
            return False
        try:
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(reversed(self.history[:self.max_history])))
                f.write("\n")
            os.replace(tmp, path)
            return True
        except OSError:
            return False

    def _push_history(self, cmd):
        cmd = cmd.strip()
        if not cmd:
            return
        while cmd in self.history:
            self.history.remove(cmd)
        self.history.insert(0, cmd)
        del self.history[self.max_history:]
        self.save_history()

    # ----------------------------------------------------------------
    # execucao de comandos
    # ----------------------------------------------------------------

    def execute_line(self, cmd=None):
        """Executa a linha digitada (ou a linha informada)."""
        if cmd is None:
            cmd = self.input_line
        cmd = (cmd or "").strip()
        self.input_line = ""
        self.input_pos = 0
        tab = self._active_tab()
        if tab is not None:
            tab.hist_idx = None
        if not cmd:
            self.dirty += 1
            return False
        self._push_history(cmd)
        if is_blocked(cmd):
            reason = blocked_reason(cmd) or "operacao administrativa"
            # o comando so e entregue a PTY dentro do callback de
            # confirmacao (ou nunca, se o usuario recusar).
            self._confirm_blocked(cmd, reason)
            self.dirty += 1
            return True
        self._send(cmd)
        return True

    def _confirm_blocked(self, cmd, reason):
        """Pede confirmacao explicita. Nunca eleva privilegio."""
        title = "Confirmar comando perigoso"
        msg = ("Este comando exige uma operacao administrativa (%s).\n\n"
               "%s\n\nConfirmar a execucao?" % (reason, cmd))
        shell = self.shell
        # guarda a aba de origem: se o usuario trocar de aba enquanto o
        # dialogo esta aberto, o comando vai para a sessao que pediu.
        tab = self._active_tab()
        if shell is not None and hasattr(shell, "confirm"):
            def _ok():
                self._send(cmd, tab)
            try:
                shell.confirm(title, msg, _ok)
                return True
            except TypeError:
                try:
                    res = shell.confirm(title, msg)
                except Exception:
                    res = False
                if res:
                    _ok()
                return bool(res)
            except Exception:
                return False
        self._notify("Comando bloqueado (%s). Sem confirmacao nao roda."
                     % reason, "warn")
        return False

    def _send(self, cmd, tab=None):
        """Escreve o comando na PTY da sessao (a ativa, por padrao)."""
        if tab is None:
            tab = self._ensure_session()
        if tab is None:
            return False
        session = tab.session
        if not session.alive:
            tab.dead = True
            self._notify("A sessao encerrou. Use 'Nova sessao'.", "warn")
            return False
        if session.mode != "pty":
            # sem eco da PTY: escreve a linha no buffer para o usuario ver
            tab.buffer.add_line(cmd, None)
        session.write(cmd + "\n")
        tab.scroll = 0
        self.dirty += 1
        self.needs_redraw = True
        return True

    # ----------------------------------------------------------------
    # copiar / colar
    # ----------------------------------------------------------------

    @staticmethod
    def _which(name):
        path = os.environ.get("PATH", "")
        for d in path.split(os.pathsep):
            if not d:
                continue
            cand = os.path.join(d, name)
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        return None

    def copy_text(self, text):
        """Copia para a area de transferencia (xclip/xsel) ou interna."""
        text = text or ""
        self.clipboard = text
        tool = self._which("xclip") or self._which("xsel")
        if tool:
            try:
                cmd = [tool]
                if tool.endswith("xclip"):
                    cmd = [tool, "-selection", "clipboard"]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                proc.communicate(input=text.encode("utf-8"), timeout=2)
                self._notify("Copiado.")
                return True
            except Exception:
                pass
        self._notify("Copiado para a area interna do terminal.")
        return False

    def paste_text(self):
        """Cola da area de transferencia interna."""
        if not self.clipboard:
            self._notify("Nada para colar.", "warn")
            return False
        self._insert(self.clipboard)
        return True

    # ----------------------------------------------------------------
    # layout
    # ----------------------------------------------------------------

    def _content_rect(self):
        win = getattr(self, "window", None)
        if win is not None:
            try:
                return win.content_rect()
            except Exception:
                pass
        return (0, 0, 1920, 1080)

    def _layout(self):
        cx, cy, cw, ch = self._content_rect()
        tab_h = 48
        status_h = 30
        input_h = 54
        tool_w = 58
        out_y = cy + tab_h
        out_h = max(80, ch - tab_h - input_h - status_h)
        return {
            "x": cx, "y": cy, "w": cw, "h": ch,
            "tab": (cx, cy, cw, tab_h),
            "out": (cx, out_y, cw, out_h),
            "text": (cx + 12, out_y + 8, cw - 24 - (tool_w + 14),
                     out_h - 16),
            "tool": (cx + cw - tool_w - 10, out_y + 8, tool_w, out_h - 16),
            "input": (cx, out_y + out_h, cw, input_h),
            "status": (cx, out_y + out_h + input_h, cw, status_h),
        }

    def _metrics(self):
        if self._m:
            return self._m
        return {"line_h": 22, "rows": 10, "cols": 60, "cw": 9.0}

    def _compute_metrics(self, p, L):
        """Mede a fonte monoespacada e ajusta o tamanho da PTY."""
        size = self.zoom
        cw = 9.0
        if T is not None:
            try:
                cw = T.text_width(p.ctx, "M", size, "normal", family=MONO)
            except Exception:
                cw = size * 0.6
        if not cw or cw <= 0:
            cw = size * 0.6
        line_h = int(size * 1.45) + 2
        tx, ty, tw, th = L["text"]
        cols = max(20, int(tw / cw))
        rows = max(1, int(th / line_h))
        self._m = {"line_h": line_h, "rows": rows, "cols": cols, "cw": cw}
        # mantem a PTY do tamanho util da janela
        if cols != self._cols or rows != self._rows:
            self._cols = cols
            self._rows = rows
            for tab in self.tabs:
                try:
                    tab.session.resize(rows, cols)
                except Exception:
                    pass

    # ----------------------------------------------------------------
    # desenho
    # ----------------------------------------------------------------

    def _colors(self):
        return COLOR_THEMES.get(self.color_theme, COLOR_THEMES["Neon"])

    def draw(self, p):
        ctx = p.ctx
        self._ctx = ctx
        ct = self._colors()
        L = self._layout()
        self._buttons = []

        # metricas da fonte (monoespacada) + tamanho da PTY
        self._compute_metrics(p, L)

        # ---------------- fundo ----------------
        ctx.set_source_rgb(*ct["bg"])
        ctx.rectangle(L["x"], L["y"], L["w"], L["h"])
        ctx.fill()

        # ---------------- abas ----------------
        self._draw_tabs(p, L, ct)

        # ---------------- saida ----------------
        self._draw_output(p, L, ct)

        # ---------------- barra de acoes flutuantes ----------------
        self._draw_tools(p, L, ct)

        # ---------------- linha de comando ----------------
        self._draw_input(p, L, ct)

        # ---------------- barra de status ----------------
        self._draw_status(p, L, ct)

        # ---------------- popup ----------------
        self._draw_popup(p, L, ct)

    # ---- abas ----

    def _draw_tabs(self, p, L, ct):
        tx, ty, tw, th = L["tab"]
        p.rect(tx, ty, tw, th, ct["panel"], 0.85)
        p.line(tx, ty + th - 1, tx + tw, ty + th - 1, ct["accent"], 1.0, 0.35)
        tab_w = 170
        tab_h = 40
        for i, tab in enumerate(self.tabs):
            bx = tx + 10 + i * (tab_w + 8)
            if bx + tab_w > tx + tw - 50:
                break
            active = (i == self.active)
            p.round(bx, ty + 4, tab_w, tab_h, 8,
                    ct["panel_hi"] if active else ct["panel"],
                    0.95 if active else 0.55)
            if active:
                p.round(bx, ty + 4, tab_w, tab_h, 8, ct["accent"], 0.0,
                        filled=False, width=1.4)
                p.rect(bx + 10, ty + 4, tab_w - 20, 2, ct["accent"], 0.95)
            try:
                p.app_icon("terminal", bx + 24, ty + 4 + tab_h / 2, 20)
            except Exception:
                pass
            self._text(p, "Sessao %d" % (i + 1), bx + 42,
                       ty + 4 + tab_h / 2 + 5, 14,
                       ct["fg"] if active else ct["dim"],
                       "bold" if active else "normal")
            self._buttons.append(("tab:%d" % i, (bx, ty + 4, tab_w, tab_h)))
            if active and len(self.tabs) > 1:
                p.icon("close", bx + tab_w - 22, ty + 4 + tab_h / 2, 14,
                       ct["dim"])
                self._buttons.append(
                    ("close:%d" % i, (bx + tab_w - 44, ty + 4, 44, tab_h)))
        # botao '+' (nova sessao)
        nb = (tx + 10 + max(1, len(self.tabs)) * (tab_w + 8), ty + 4,
              44, tab_h)
        p.round(nb[0], nb[1], nb[2], nb[3], 8, ct["panel_hi"], 0.6)
        self._text(p, "+", nb[0] + nb[2] / 2, nb[1] + nb[3] / 2 + 7, 22,
                   ct["accent"], "bold", align="center")
        self._buttons.append(("new", nb))

    # ---- saida ----

    def _draw_output(self, p, L, ct):
        tx, ty, tw, th = L["text"]
        p.rect(tx - 4, ty - 4, tw + 8, th + 8, ct["bg"], 0.55)
        m = self._metrics()
        line_h = m["line_h"]
        rows = m["rows"]
        cols = m["cols"]
        cw = m["cw"]
        lines = self._current_lines()
        first = max(0, len(lines) - rows - self._scroll())
        for row in range(rows):
            idx = first + row
            if idx >= len(lines):
                break
            line = lines[idx]
            x = tx
            y = ty + row * line_h + line_h * 0.78
            if self.selected_line is not None and idx == self.selected_line:
                p.rect(tx - 2, ty + row * line_h, tw + 2, line_h, ct["sel"],
                       0.95)
            for (text, color) in line:
                if not text:
                    continue
                if x > tx + tw:
                    break
                room = cols - int((x - tx) / max(cw, 1))
                if room <= 0:
                    break
                if len(text) > room:
                    text = text[:room]
                self._text(p, text, x, y, self.zoom,
                           ct["fg"] if color is None else color)
                x += len(text) * cw
            if x > tx + tw:
                break
        # barra de rolagem (desenhada com a paleta do terminal)
        sb_x = tx + tw + 8
        total = max(1, len(lines))
        view = min(1.0, float(rows) / total)
        frac = 1.0 - float(self._scroll()) / total
        p.round(sb_x, ty, 5, th, 2.5, ct["panel_hi"], 0.45)
        thumb_h = max(24, int(th * view))
        p.round(sb_x, ty + int((th - thumb_h) * max(0.0, min(1.0, frac))),
                5, thumb_h, 2.5, ct["accent"], 0.55)

    def _current_lines(self):
        tab = self._active_tab()
        if tab is None:
            return []
        return tab.buffer.visible_lines()

    def _scroll(self):
        tab = self._active_tab()
        return tab.scroll if tab else 0

    # ---- barra flutuante ----

    def _draw_tools(self, p, L, ct):
        tx, ty, tw, th = L["tool"]
        p.round(tx, ty, tw, th, 10, ct["panel"], 0.82)
        p.round(tx, ty, tw, th, 10, ct["accent"], 0.0, filled=False, width=1.0)
        labels = [("new", "Nova", "Nova sessao"), ("copy", "Copiar", "Copiar"),
                  ("paste", "Colar", "Colar"), ("clear", "Limpar", "Limpar"),
                  ("zoom_out", "Zoom-", "Reduzir texto"),
                  ("zoom_in", "Zoom+", "Aumentar texto")]
        n = len(labels)
        gap = 8
        bh = min(52, (th - gap * (n - 1)) / float(n))
        if bh < 30:
            bh = 30
        y = ty + (th - (bh * n + gap * (n - 1))) / 2.0
        for (name, label, tip) in labels:
            rect = (tx + 6, y, tw - 12, bh)
            pressed = (self._pressed == name)
            p.round(rect[0], rect[1], rect[2], rect[3], 8,
                    ct["accent"] if pressed else ct["panel_hi"],
                    0.55 if pressed else 0.8)
            size = 13 if len(label) <= 4 else 12
            self._text(p, label, rect[0] + rect[2] / 2,
                       rect[1] + rect[3] / 2 + size * 0.35, size, ct["fg"],
                       align="center")
            self._buttons.append((name, rect))
            y += bh + gap

    # ---- linha de comando ----

    def _draw_input(self, p, L, ct):
        ix, iy, iw, ih = L["input"]
        p.rect(ix, iy, iw, ih, ct["panel"], 0.92)
        p.line(ix, iy, ix + iw, iy, ct["accent"], 1.0, 0.45)
        exec_w = 116
        field_x = ix + 14
        field_w = iw - 28 - exec_w - 10
        p.round(field_x, iy + 6, field_w, ih - 12, 8, ct["bg"], 0.75)
        # prompt
        self._text(p, ">", field_x + 10, iy + ih / 2 + 5, self.zoom,
                   ct["accent"])
        # texto + cursor
        cw = self._metrics()["cw"]
        tx = field_x + 10 + cw * 1.6
        base_y = iy + ih / 2 + self.zoom * 0.36
        text = self.input_line
        pos = max(0, min(self.input_pos, len(text)))
        self._text(p, text[:pos], tx, base_y, self.zoom, ct["fg"])
        cx = tx + cw * pos
        rest = text[pos:]
        if rest:
            self._text(p, rest, cx, base_y, self.zoom, ct["fg"])
        # cursor piscando
        if self._blink:
            cur_char = text[pos] if pos < len(text) else " "
            p.rect(cx, base_y - self.zoom * 0.82, cw, self.zoom * 1.05,
                   ct["cursor"], 0.85)
            if cur_char != " ":
                self._text(p, cur_char, cx, base_y, self.zoom, ct["bg"])
        # botao executar
        brect = (ix + iw - exec_w - 10, iy + 6, exec_w, ih - 12)
        pressed = (self._pressed == "exec")
        p.round(brect[0], brect[1], brect[2], brect[3], 8,
                ct["accent"] if pressed else ct["panel_hi"],
                0.65 if pressed else 0.85)
        p.round(brect[0], brect[1], brect[2], brect[3], 8, ct["accent"], 0.0,
                filled=False, width=1.2)
        self._text(p, "Executar", brect[0] + brect[2] / 2,
                   brect[1] + brect[3] / 2 + 5, 15, ct["fg"], align="center")
        self._buttons.append(("exec", brect))

    # ---- status ----

    def _draw_status(self, p, L, ct):
        sx, sy, sw, sh = L["status"]
        p.rect(sx, sy, sw, sh, ct["panel"], 0.9)
        p.line(sx, sy, sx + sw, sy, ct["accent"], 1.0, 0.25)
        tab = self._active_tab()
        sess = "Sessao %d/%d" % (min(self.active + 1, max(1, len(self.tabs))),
                                  max(1, len(self.tabs)))
        cwd = self._cwd or "~"
        info = "%s   |   %s   |   zoom %d   |   hist %d   |   %s" % (
            sess, cwd, self.zoom, len(self.history), self.color_theme)
        self._text(p, info, sx + 12, sy + sh / 2 + 5, 13, ct["dim"])
        hint = "Ctrl+L limpar   Ctrl+C interromper   Tab completa"
        w = self._text_width(p, hint, 13)
        w_info = self._text_width(p, info, 13)
        if sw > w + w_info + 48:
            self._text(p, hint, sx + sw - 12, sy + sh / 2 + 5, 13,
                       ct["dim"], align="right")

    # ---- popup ----

    def _draw_popup(self, p, L, ct):
        if not self.popup:
            return
        bw, bh = 96, 46
        gap = 10
        w = bw * 2 + gap
        h = bh + 26
        x = self.popup["x"]
        y = self.popup["y"]
        x = max(L["x"] + 8, min(x, L["x"] + L["w"] - w - 8))
        y = max(L["y"] + 8, min(y, L["y"] + L["h"] - h - 8))
        p.round(x, y, w, h, 10, ct["panel_hi"], 0.97)
        p.round(x, y, w, h, 10, ct["accent"], 0.0, filled=False, width=1.3)
        self._text(p, "Linha %d" % (self.popup.get("index", 0) + 1),
                   x + w / 2, y + 18, 13, ct["dim"], align="center")
        buttons = []
        for i, (name, label) in enumerate((("copiar_linha", "Copiar"),
                                           ("limpar_buffer", "Limpar"))):
            bx = x + i * (bw + gap)
            by = y + 24
            pressed = (self._pressed == name)
            p.round(bx, by, bw, bh, 8,
                    ct["accent"] if pressed else ct["panel"], 0.6 if pressed
                    else 0.9)
            p.round(bx, by, bw, bh, 8, ct["accent"], 0.0, filled=False,
                    width=1.0)
            self._text(p, label, bx + bw / 2, by + bh / 2 + 5, 14, ct["fg"],
                       align="center")
            buttons.append((name, (bx, by, bw, bh)))
        self.popup["buttons"] = buttons

    # ---- texto monoespacado ----

    def _text(self, p, s, x, y, size=None, color=None, weight="normal",
              align="left"):
        size = size or self.zoom
        color = color or self._colors()["fg"]
        if T is not None:
            return T.text(p.ctx, s, x, y, size, color, weight, align,
                          family=MONO)
        return 0.0                       # pragma: no cover

    def _text_width(self, p, s, size=None):
        size = size or self.zoom
        if T is not None:
            return T.text_width(p.ctx, s, size, "normal", family=MONO)
        return len(s) * size * 0.6      # pragma: no cover

    # ----------------------------------------------------------------
    # tick
    # ----------------------------------------------------------------

    def on_tick(self, dt):
        changed = False
        # le a saida de todas as sessoes (sem bloquear)
        for tab in self.tabs:
            try:
                data = tab.session.read_available()
            except Exception:
                data = b""
            if data:
                tab.buffer.feed(data)
                if tab.scroll > 0:
                    tab.scroll = 0
                changed = True
            if not tab.dead and not tab.session.alive:
                tab.dead = True
                tab.buffer.add_line("[sessao encerrada]", self._colors()["err"])
                changed = True
        # cwd
        try:
            self._cwd_t += dt
            if self._cwd_t >= 0.4:
                self._cwd_t = 0.0
                session = self._active_session()
                cwd = session.cwd_of() if session else None
                if cwd and cwd != self._cwd:
                    self._cwd = cwd
                    changed = True
        except Exception:
            pass
        # cursor piscando
        self._blink_t += dt
        if self._blink_t >= 0.5:
            self._blink_t = 0.0
            self._blink = not self._blink
            changed = True
        if changed:
            self.dirty += 1
        self.needs_redraw = changed

    # ----------------------------------------------------------------
    # toque
    # ----------------------------------------------------------------

    @staticmethod
    def _inside(rect, x, y):
        return (rect[0] <= x < rect[0] + rect[2] and
                rect[1] <= y < rect[1] + rect[3])

    def _hit(self, x, y):
        for (name, rect) in self._buttons:
            if self._inside(rect, x, y):
                return name
        return None

    def on_touch(self, ev):
        etype = getattr(ev, "type", "")
        x = getattr(ev, "x", 0)
        y = getattr(ev, "y", 0)

        if etype == "down":
            hit = self._hit(x, y)
            self._pressed = hit
            return hit is not None
        if etype == "up":
            pressed = self._pressed
            self._pressed = None
            if pressed and self._hit(x, y) == pressed:
                self._action(pressed)
                return True
            return False
        if etype == "cancel":
            self._pressed = None
            return False
        if etype == "tap":
            return self._on_tap(x, y)
        if etype == "longpress":
            return self._on_tap(x, y)
        if etype == "drag":
            dy = getattr(ev, "dy", 0) or 0
            if dy:
                self._scroll_by(dy)
                return True
            return False
        if etype == "scroll":
            amount = getattr(ev, "amount", 0) or 0
            if amount:
                self._scroll_by(amount)
                return True
            return False
        if etype == "pinch":
            scale = getattr(ev, "scale", 1.0) or 1.0
            if scale > 1.08:
                self.zoom += 1
            elif scale < 0.92:
                self.zoom -= 1
            self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom))
            self.dirty += 1
            return True
        return False

    def _on_tap(self, x, y):
        L = self._layout()
        # popup aberto: seus botoes tem prioridade
        if self.popup:
            for (name, rect) in self.popup.get("buttons", []):
                if self._inside(rect, x, y):
                    self._popup_action(name)
                    return True
            # toque fora do popup: so fecha o popup (nao aciona o que
            # estiver por baixo, para nao executar nada por engano)
            self.popup = None
            self.dirty += 1
            return True
        # botoes (flutuantes, abas, executar)
        name = self._hit(x, y)
        if name:
            self._action(name)
            return True
        # linha de comando
        if self._inside(L["input"], x, y):
            self.focused = True
            set_key_focus = getattr(self.shell, "set_key_focus", None)
            if set_key_focus is not None:
                set_key_focus(self)
            self.dirty += 1
            return True
        # linha da saida -> popup
        if self._inside(L["text"], x, y):
            idx = self._line_index_at(y)
            if idx is not None:
                self.selected_line = idx
                self.popup = {"index": idx, "x": x, "y": y, "buttons": []}
                self.dirty += 1
            return True
        self.focused = False
        self.dirty += 1
        return False

    def _action(self, name):
        self.dirty += 1
        self.needs_redraw = True
        if name.startswith("tab:"):
            self.switch_session(int(name.split(":", 1)[1]))
            return
        if name.startswith("close:"):
            self.close_session(int(name.split(":", 1)[1]))
            return
        if name == "new":
            self.new_session()
            return
        if name == "exec":
            self.execute_line()
            return
        if name == "copy":
            self._copy_selection()
            return
        if name == "paste":
            self.paste_text()
            return
        if name == "clear":
            tab = self._active_tab()
            if tab:
                tab.buffer.clear()
                tab.scroll = 0
                self.selected_line = None
            self.popup = None
            return
        if name == "zoom_in":
            self.zoom = min(self.MAX_ZOOM, self.zoom + 1)
            return
        if name == "zoom_out":
            self.zoom = max(self.MIN_ZOOM, self.zoom - 1)
            return

    def _popup_action(self, name):
        self.dirty += 1
        if name == "copiar_linha":
            self._copy_selection()
        elif name == "limpar_buffer":
            tab = self._active_tab()
            if tab:
                tab.buffer.clear()
                tab.scroll = 0
            self.selected_line = None
        self.popup = None

    def _copy_selection(self):
        lines = self._current_lines()
        idx = self.selected_line
        if idx is None or idx < 0 or idx >= len(lines):
            idx = len(lines) - 1
        if idx is None or idx < 0:
            self._notify("Nada para copiar.", "warn")
            return False
        text = OutputBuffer.line_text(lines[idx])
        return self.copy_text(text)

    def _line_index_at(self, y):
        L = self._layout()
        m = self._metrics()
        tx, ty, tw, th = L["text"]
        if y < ty or y >= ty + th:
            return None
        row = int((y - ty) // max(1, m["line_h"]))
        lines = self._current_lines()
        first = max(0, len(lines) - m["rows"] - self._scroll())
        idx = first + row
        if 0 <= idx < len(lines):
            return idx
        return None

    def _scroll_by(self, pixels):
        tab = self._active_tab()
        if tab is None:
            return
        m = self._metrics()
        lines = self._current_lines()
        max_scroll = max(0, len(lines) - m["rows"])
        delta = int(round(float(pixels) / max(1, m["line_h"])))
        if delta == 0 and pixels:
            delta = 1 if pixels > 0 else -1
        tab.scroll = max(0, min(max_scroll, tab.scroll + delta))
        self.dirty += 1
        self.needs_redraw = True

    # ----------------------------------------------------------------
    # teclado
    # ----------------------------------------------------------------

    def _set_input(self, text, pos=None):
        self.input_line = text
        if pos is None:
            pos = len(text)
        self.input_pos = max(0, min(int(pos), len(text)))

    def _insert(self, text):
        pos = max(0, min(self.input_pos, len(self.input_line)))
        self.input_line = (self.input_line[:pos] + text +
                           self.input_line[pos:])
        self.input_pos = pos + len(text)
        self.dirty += 1

    def on_key(self, ev):
        info = key_info(ev)
        if info is None:
            return False
        key = info["key"]
        text = info["text"]
        ctrl = info["ctrl"]
        alt = info["alt"]

        if ctrl:
            k = key.lower()
            if k == "c":
                self._interrupt()
                return True
            if k == "l":
                tab = self._active_tab()
                if tab:
                    tab.buffer.clear()
                    tab.scroll = 0
                self.selected_line = None
                self.dirty += 1
                return True
            if k == "a":
                self.input_pos = 0
                self.dirty += 1
                return True
            if k == "e":
                self.input_pos = len(self.input_line)
                self.dirty += 1
                return True
            if k == "u":
                self._set_input("")
                self.dirty += 1
                return True
            if k == "k":
                self._set_input("")
                self.dirty += 1
                return True
            if k == "w":
                self._delete_word()
                return True
            if k == "d":
                session = self._active_session()
                if session:
                    session.write("\x04")
                return True
            return True

        if alt:
            if key.lower() in ("t",):
                self.new_session()
                return True
            return True

        if key in ("Return", "Enter", "KP_Enter", "return", "enter"):
            self.execute_line()
            return True
        if key in ("BackSpace", "Backspace", "backspace", "BS"):
            self._backspace()
            return True
        if key in ("Delete", "Del", "delete"):
            self._delete()
            return True
        if key in ("Left", "left"):
            self.input_pos = max(0, self.input_pos - 1)
            self.dirty += 1
            return True
        if key in ("Right", "right"):
            self.input_pos = min(len(self.input_line), self.input_pos + 1)
            self.dirty += 1
            return True
        if key in ("Home", "home"):
            self.input_pos = 0
            self.dirty += 1
            return True
        if key in ("End", "end"):
            self.input_pos = len(self.input_line)
            self.dirty += 1
            return True
        if key in ("Up", "up"):
            self._history_prev()
            return True
        if key in ("Down", "down"):
            self._history_next()
            return True
        if key in ("Tab", "tab"):
            self._complete()
            return True
        if key in ("Escape", "escape", "Esc"):
            self.popup = None
            self.selected_line = None
            self.dirty += 1
            return True
        if key in ("space", "Space", " "):
            self._insert(" ")
            return True

        # caractere imprimivel
        ins = text if text else (key if len(key) == 1 else "")
        if ins and ins >= " " and ins != "\x7f":
            self._insert(ins)
            return True
        return False

    def _interrupt(self):
        session = self._active_session()
        if session:
            session.interrupt()
        tab = self._active_tab()
        if tab:
            tab.buffer.add_line("^C", self._colors()["err"])
        self.dirty += 1

    def _backspace(self):
        if self.input_pos <= 0:
            return
        self.input_line = (self.input_line[:self.input_pos - 1] +
                           self.input_line[self.input_pos:])
        self.input_pos -= 1
        self.dirty += 1

    def _delete(self):
        if self.input_pos >= len(self.input_line):
            return
        self.input_line = (self.input_line[:self.input_pos] +
                           self.input_line[self.input_pos + 1:])
        self.dirty += 1

    def _delete_word(self):
        text = self.input_line
        pos = self.input_pos
        i = pos
        while i > 0 and text[i - 1] == " ":
            i -= 1
        while i > 0 and text[i - 1] != " ":
            i -= 1
        self.input_line = text[:i] + text[pos:]
        self.input_pos = i
        self.dirty += 1

    def _history_prev(self):
        if not self.history:
            return
        tab = self._active_tab()
        if tab is None:
            return
        if tab.hist_idx is None:
            tab.hist_tmp = self.input_line
            tab.hist_idx = 0
        else:
            tab.hist_idx = min(len(self.history) - 1, tab.hist_idx + 1)
        self._set_input(self.history[tab.hist_idx])
        self.dirty += 1

    def _history_next(self):
        tab = self._active_tab()
        if tab is None or tab.hist_idx is None:
            return
        tab.hist_idx -= 1
        if tab.hist_idx < 0:
            tab.hist_idx = None
            self._set_input(tab.hist_tmp)
        else:
            self._set_input(self.history[tab.hist_idx])
        self.dirty += 1

    def _complete(self):
        """Completamento simples: ultimo token da linha, no cwd."""
        text = self.input_line
        pos = self.input_pos
        left = text[:pos]
        m = re.search(r"(\S+)$", left)
        token = m.group(1) if m else ""
        if not token:
            return
        base_dir = os.path.dirname(token)
        prefix = os.path.basename(token)
        if base_dir.startswith("~"):
            base_dir = os.path.expanduser(base_dir)
        elif not base_dir:
            base_dir = self._cwd or os.getcwd()
        elif not os.path.isabs(base_dir):
            base_dir = os.path.join(self._cwd or os.getcwd(), base_dir)
        try:
            names = os.listdir(base_dir)
        except OSError:
            return
        matches = sorted(n for n in names if n.startswith(prefix))
        if not matches:
            return
        if len(matches) == 1:
            full = matches[0]
            new_token = os.path.join(os.path.dirname(token), full) \
                if os.path.dirname(token) else full
            self.input_line = left[:len(left) - len(token)] + new_token + \
                text[pos:]
            self.input_pos = len(left) - len(token) + len(new_token)
        else:
            tab = self._active_tab()
            if tab:
                tab.buffer.add_line("  ".join(matches), self._colors()["dim"])
        self.dirty += 1

    # ----------------------------------------------------------------
    # avisos
    # ----------------------------------------------------------------

    def _notify(self, msg, kind="info"):
        shell = self.shell
        if shell is not None and hasattr(shell, "notify"):
            try:
                shell.notify(msg, kind=kind)
                return True
            except TypeError:
                try:
                    shell.notify(msg)
                    return True
                except Exception:
                    pass
            except Exception:
                pass
        tab = self._active_tab()
        if tab:
            color = self._colors().get(
                "err" if kind == "err" else ("warn" if kind == "warn" else
                                             "dim"))
            tab.buffer.add_line(msg, color)
        self.dirty += 1
        return False


# --------------------------------------------------------------------
# normalizacao de eventos de teclado
# --------------------------------------------------------------------

def key_info(ev):
    """Normaliza um evento de tecla para um dict.

    Aceita: objeto com .key/.text/.ctrl/.alt/.shift, dict com as mesmas
    chaves, ou uma string simples com o nome da tecla.
    """
    if ev is None:
        return None
    if isinstance(ev, str):
        ev = {"key": ev}
    if isinstance(ev, dict):
        get = ev.get
        key = get("key", "") or ""
        text = get("text", "") or ""
        ctrl = bool(get("ctrl", False))
        alt = bool(get("alt", False))
        shift = bool(get("shift", False))
    else:
        key = getattr(ev, "key", "") or ""
        text = getattr(ev, "text", "") or ""
        ctrl = bool(getattr(ev, "ctrl", False))
        alt = bool(getattr(ev, "alt", False))
        shift = bool(getattr(ev, "shift", False))
    if not isinstance(key, str):
        key = str(key)
    if not isinstance(text, str):
        text = str(text)
    low = key.lower()
    for pre in ("ctrl+", "control+"):
        if low.startswith(pre):
            ctrl = True
            key = key[len(pre):]
            low = key.lower()
            break
    for pre in ("alt+", "meta+"):
        if low.startswith(pre):
            alt = True
            key = key[len(pre):]
            low = key.lower()
            break
    if low.startswith("shift+"):
        shift = True
        key = key[len("shift+"):]
    return {"key": key, "text": text, "ctrl": ctrl, "alt": alt,
            "shift": shift}
