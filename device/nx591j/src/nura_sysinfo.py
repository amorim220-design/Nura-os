#!/usr/bin/env python3
# NURA OS — leitura de metricas reais do sistema

"""
nura_sysinfo — camada de leitura de metricas REAIS do sistema.

Usada pelo painel "NURA Performance" e pelo "NURA Control Center".

Principio inegociavel: NUNCA inventar metricas. Se o dado nao existe no
sistema (o driver nao expoe, o arquivo nao esta montado, o hardware nao
tem), o valor e None — a lista fica vazia ou o item simplesmente some do
dict. Nunca 0 falso, nunca "simulacao", nunca chute.

Todos os caminhos sao parametrizaveis (root/proc/etc/var/usr), o que
permite testar com arvores de arquivos falsas sem precisar do aparelho:

    si = nura_sysinfo.SysInfo(root="/sys", proc="/proc")          # real
    si = nura_sysinfo.SysInfo(root=tmp+"/sys", proc=tmp+"/proc")  # fake

Somente biblioteca padrao do Python 3 (compativel com 3.12+ e 3.14 do
Alpine edge). Nada de `os.popen`: tudo que existe em /proc ou /sys e
lido direto do pseudo-sistema de arquivos.
"""

import glob
import json
import os
import re
import shutil
import time

# --- constantes ----------------------------------------------------------

# Campos de /proc/stat, na ordem em que o kernel escreve.
CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq",
              "softirq", "steal")

# Campos cujo valor e "tempo de espera" (nao contam como CPU ocupada).
CPU_IDLE_FIELDS = ("idle", "iowait")


# --- funcoes auxiliares de leitura ---------------------------------------

def _read_text(path, default=None):
    """Le um texto inteiro. Devolve None se o arquivo nao existir/erro."""
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except (OSError, IOError, ValueError):
        return default


def _read_int(path):
    """Le um inteiro de um arquivo. Devolve None se nao der para ler."""
    text = _read_text(path)
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    token = text.split()[0]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return int(float(token))
    except ValueError:
        return None


def _read_float(path):
    """Le um float de um arquivo. Devolve None se nao der para ler."""
    text = _read_text(path)
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    token = text.split()[0]
    try:
        return float(token)
    except ValueError:
        return None


def _read_str(path):
    """Le uma linha de texto e devolve stripped (ou None)."""
    text = _read_text(path)
    if text is None:
        return None
    text = text.strip()
    return text if text else None


def _read_bool(path):
    """Le um arquivo de flag ('0'/'1'). Devolve None se nao existir."""
    text = _read_str(path)
    if text is None:
        return None
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return None


def _listdir(path):
    """Lista um diretorio (ordenado). Devolve [] se nao existir."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _default_clock_ticks():
    """USER_HZ do kernel (normalmente 100 ticks por segundo)."""
    try:
        return int(os.sysconf("SC_CLK_TCK"))
    except (AttributeError, ValueError, OSError):
        return 100


def _default_page_size():
    """Tamanho da pagina de memoria, em bytes (normalmente 4096)."""
    try:
        return int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, ValueError, OSError):
        return 4096


def _unescape_mount(path):
    """Desfaz o escape octal do /proc/*/mountinfo (\\040 -> espaco)."""
    if not path:
        return path
    return (path.replace("\\040", " ")
                .replace("\\011", "\t")
                .replace("\\012", "\n")
                .replace("\\134", "\\"))


def _zone_index(name):
    """Indice numerico de uma zona termica (thermal_zone10 > thermal_zone2)."""
    m = re.search(r"(\d+)$", name or "")
    return int(m.group(1)) if m else 0


# --- funcoes puras de parse (facilmente testaveis) -----------------------

def parse_os_release(text):
    """Parse de um arquivo no formato KEY="VALUE" (os-release).

    Devolve um dict com as chaves como estao no arquivo (NAME, ID, ...).
    Aspas (simples ou duplas) em volta do valor sao removidas.
    """
    out = {}
    if not text:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                value = value.replace('\\"', '"').replace("\\\\", "\\")
        out[key] = value
    return out


def parse_cpu_stat(text):
    """Parse de /proc/stat.

    Devolve (total, cores):
      * total  -> dict com os campos brutos (ticks) da linha agregada "cpu"
      * cores  -> lista de dicts, um por核, na ordem numerica

    Se a linha agregada "cpu" nao existir, o agregado e a soma dos nucleos.
    """
    total = None
    cores = []

    def _fields(values):
        out = {}
        for idx, name in enumerate(CPU_FIELDS):
            if idx >= len(values):
                out[name] = 0
                continue
            try:
                out[name] = int(values[idx])
            except ValueError:
                out[name] = 0
        return out

    for line in (text or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        if name == "cpu":
            total = _fields(parts[1:])
        elif re.match(r"^cpu\d+$", name):
            cores.append((int(name[3:]), _fields(parts[1:])))

    # ordena os nucleos pelo indice numerico (cpu2 antes de cpu10)
    cores.sort(key=lambda c: c[0])
    cores = [c[1] for c in cores]

    if total is None and cores:
        total = {k: sum(c.get(k, 0) for c in cores) for k in CPU_FIELDS}
    return total, cores


def parse_meminfo(text):
    """Parse de /proc/meminfo -> dict {nome: valor_em_kB}."""
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"^\s*([A-Za-z_()]+):\s*(\d+)", line)
        if not m:
            continue
        out[m.group(1)] = int(m.group(2))
    return out


def parse_stat_line(text):
    """Parse de /proc/<pid>/stat.

    Atencao: o campo 'comm' (2o) pode conter espacos e parenteses, entao
    o parse e feito pelo ultimo ')' da linha.

    Devolve dict com pid/name/state/ppid/utime/stime/rss_pages, ou None.
    """
    line = (text or "").strip()
    if not line:
        return None
    lp = line.find("(")
    rp = line.rfind(")")
    if lp < 0 or rp < lp:
        return None
    pid_txt = line[:lp].strip()
    comm = line[lp + 1:rp]
    rest = line[rp + 1:].split()
    # do campo 3 (state) ate o campo 24 (rss) sao 22 campos
    if len(rest) < 22:
        return None

    def _i(idx):
        try:
            return int(rest[idx])
        except (ValueError, IndexError):
            return 0

    try:
        pid = int(pid_txt)
    except ValueError:
        pid = -1

    return {
        "pid": pid,
        "name": comm,
        "state": rest[0],
        "ppid": _i(1),
        "utime": _i(11),
        "stime": _i(12),
        "rss_pages": _i(21),
    }


def parse_status(text):
    """Parse de /proc/<pid>/status -> dict com uid/state/name/vmrss_kb."""
    out = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "Uid":
            parts = value.split()
            if parts:
                try:
                    out["uid"] = int(parts[0])
                except ValueError:
                    out["uid"] = None
        elif key == "State":
            parts = value.split()
            out["state"] = parts[0] if parts else None
            out["state_desc"] = value
        elif key == "Name":
            out["name"] = value
        elif key == "VmRSS":
            parts = value.split()
            if parts:
                try:
                    out["vmrss_kb"] = int(parts[0])
                except ValueError:
                    out["vmrss_kb"] = None
    return out


def busy_fraction(prev, cur):
    """Fracao de CPU ocupada (0..1) entre duas leituras de /proc/stat.

    As entradas sao dicts com os campos de CPU_FIELDS em SEGUNDOS.
    idle + iowait nao contam como ocupacao (mesma semantica do psutil).
    """
    if not prev or not cur:
        return None
    delta = {}
    for name in CPU_FIELDS:
        delta[name] = cur.get(name, 0.0) - prev.get(name, 0.0)
    total = sum(delta.values())
    if total <= 0:
        # nenhum tempo de CPU decorrido: nao da para medir uso
        return 0.0
    idle = sum(delta.get(name, 0.0) for name in CPU_IDLE_FIELDS)
    frac = (total - idle) / total
    if frac < 0.0:
        frac = 0.0
    elif frac > 1.0:
        frac = 1.0
    return frac


# --- a classe principal --------------------------------------------------

class SysInfo(object):
    """Leitura das metricas reais do sistema.

    Parametros:
        root        raiz do sysfs  (padrao "/sys")
        proc        raiz do procfs (padrao "/proc")
        etc         diretorio de configuracao (padrao "/etc")
        var         diretorio de estado (padrao "/var")
        usr         raiz do /usr (padrao "/usr")
        clock_ticks ticks por segundo do /proc/stat (padrao: SC_CLK_TCK)
        page_size   bytes por pagina de memoria (padrao: SC_PAGE_SIZE)
    """

    def __init__(self, root="/sys", proc="/proc", etc="/etc", var="/var",
                 usr="/usr", clock_ticks=None, page_size=None):
        self.root = root
        self.proc = proc
        self.etc = etc
        self.var = var
        self.usr = usr
        self.clock_ticks = int(clock_ticks) if clock_ticks else _default_clock_ticks()
        self.page_size = int(page_size) if page_size else _default_page_size()
        # historico interno: /proc/stat anterior (para cpu_usage)
        self._snapshot = None
        # historico interno: {pid: (cpu_segundos, timestamp)} (para cpu_pct)
        self._proc_cpu = {}

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------

    def _read_cpu_snapshot(self):
        """Le /proc/stat e devolve {'total': {...}, 'cores': [{...}]} em SEGUNDOS."""
        text = _read_text(os.path.join(self.proc, "stat"))
        if not text:
            return None
        total, cores = parse_cpu_stat(text)
        if total is None and not cores:
            return None

        def _to_seconds(fields):
            if fields is None:
                return None
            return dict((k, fields.get(k, 0) / float(self.clock_ticks))
                        for k in CPU_FIELDS)

        total_s = _to_seconds(total)
        if total_s is None and cores:
            total_s = dict((k, sum(c.get(k, 0) for c in cores)
                               / float(self.clock_ticks)) for k in CPU_FIELDS)
        cores_s = [_to_seconds(c) for c in cores]
        return {"total": total_s, "cores": cores_s}

    def cpu_times(self):
        """Tempos de CPU agregados de todas as CPUs, em SEGUNDOS.

        Devolve dict com user/nice/system/idle/iowait/irq/softirq/steal
        (ou None se /proc/stat nao existir).
        """
        snap = self._read_cpu_snapshot()
        if snap is None:
            return None
        self._snapshot = snap
        return dict(snap["total"])

    def cpu_usage(self, prev_times=None):
        """Fracao de uso da CPU (0..1) desde a leitura anterior.

        * prev_times: leitura anterior de cpu_times() (opcional; se nao for
          dada, usa o historico interno da propria instancia).
        * 'total'    -> fracao de ocupacao de todo o sistema.
        * 'per_core' -> lista com a fracao de ocupacao de cada nucleo.

        Devolve None se nao houver leitura anterior valida.
        """
        snap = self._read_cpu_snapshot()
        if snap is None:
            return None

        prev_total = prev_times
        prev_cores = None
        if self._snapshot is not None:
            prev_cores = self._snapshot.get("cores")
            if prev_total is None:
                prev_total = self._snapshot.get("total")

        self._snapshot = snap

        if prev_total is None:
            return None

        total = busy_fraction(prev_total, snap["total"])
        per_core = []
        if prev_cores:
            for idx, cur in enumerate(snap["cores"]):
                if idx < len(prev_cores) and prev_cores[idx] is not None:
                    per_core.append(busy_fraction(prev_cores[idx], cur))
        return {"total": total, "per_core": per_core}

    def cpu_usage_window(self, seconds=0.05):
        """Mede o uso da CPU numa janela de tempo explicita.

        Util quando ainda nao existe leitura anterior (primeiro quadro do
        painel). Faz duas leituras reais de /proc/stat separadas por
        `seconds` — nada e estimado.
        """
        before = self._read_cpu_snapshot()
        if before is None:
            return None
        if seconds and seconds > 0:
            time.sleep(seconds)
        after = self._read_cpu_snapshot()
        if after is None:
            return None
        self._snapshot = after
        total = busy_fraction(before["total"], after["total"])
        per_core = []
        for idx, cur in enumerate(after["cores"]):
            if idx < len(before["cores"]) and before["cores"][idx] is not None:
                per_core.append(busy_fraction(before["cores"][idx], cur))
        return {"total": total, "per_core": per_core}

    def cpu_count(self):
        """Numero de nucleos de CPU (None se nao der para saber)."""
        cores = self._cpu_dirs()
        if cores:
            return len(cores)
        try:
            return os.cpu_count()
        except (AttributeError, OSError):
            return None

    def _cpu_dirs(self):
        """Lista dos diretorios /sys/devices/system/cpu/cpuN (ordenada)."""
        base = os.path.join(self.root, "devices", "system", "cpu")
        found = []
        for d in glob.glob(os.path.join(base, "cpu[0-9]*")):
            m = re.search(r"cpu(\d+)$", os.path.basename(d))
            if not m:
                continue
            found.append((int(m.group(1)), d))
        found.sort()
        return [d for _, d in found]

    def _cpu_freq_list(self, filename):
        """Le um arquivo de frequencia (kHz) de cada nucleo."""
        values = []
        exposed = False
        for d in self._cpu_dirs():
            khz = _read_int(os.path.join(d, "cpufreq", filename))
            if khz is None:
                values.append(None)
            else:
                values.append(khz / 1000.0)
                exposed = True
        if not exposed:
            return []
        return values

    def cpu_freq(self):
        """Frequencias atuais por nucleo, em MHz.

        A lista tem uma entrada por nucleo, na ordem dos nucleos; None
        nos nucleos em que o driver nao expoe scaling_cur_freq.
        Lista vazia se nenhum nucleo expoe a frequencia.
        """
        return self._cpu_freq_list("scaling_cur_freq")

    def cpu_freq_max(self):
        """Frequencias maximas por nucleo, em MHz (mesma forma de cpu_freq).

        Lista vazia se o driver nao expoe scaling_max_freq.
        """
        return self._cpu_freq_list("scaling_max_freq")

    def cpu_freq_current(self):
        """Maior frequencia de CPU agora (MHz) ou None se nao houver.

        Atalho para o painel mostrar "CPU: 1014 MHz" sem mexer na lista
        com None do cpu_freq().
        """
        values = [v for v in self.cpu_freq() if v is not None]
        if not values:
            return None
        return max(values)

    def cpu_governor(self):
        """Governors de frequencia por nucleo (None onde nao houver)."""
        out = []
        exposed = False
        for d in self._cpu_dirs():
            gov = _read_str(os.path.join(d, "cpufreq", "scaling_governor"))
            out.append(gov)
            if gov is not None:
                exposed = True
        if not exposed:
            return []
        return out

    # ------------------------------------------------------------------
    # memoria
    # ------------------------------------------------------------------

    def ram_info(self):
        """Informacoes de memoria RAM (em kB).

        Chaves: total_kb, free_kb, available_kb, used_kb, used_pct,
        cached_kb, swap_total_kb, swap_free_kb.

        used_kb = total_kb - available_kb (NAO e total - free: o "free"
        do kernel ignora o cache, que continua sendo memoria usavel).
        Devolve None se /proc/meminfo nao existir.
        """
        text = _read_text(os.path.join(self.proc, "meminfo"))
        if not text:
            return None
        mi = parse_meminfo(text)

        total = mi.get("MemTotal")
        free = mi.get("MemFree")
        buffers = mi.get("Buffers")
        cached = mi.get("Cached")
        reclaimable = mi.get("SReclaimable")

        available = mi.get("MemAvailable")
        if available is None and free is not None and \
                buffers is not None and cached is not None:
            # kernels antigos sem MemAvailable: available ~ free+buffers+cached
            available = free + buffers + cached

        used = None
        used_pct = None
        if total is not None and available is not None:
            used = total - available
            if total > 0:
                used_pct = used * 100.0 / total

        cached_kb = None
        if cached is not None:
            cached_kb = cached + (reclaimable or 0)

        return {
            "total_kb": total,
            "free_kb": free,
            "available_kb": available,
            "used_kb": used,
            "used_pct": used_pct,
            "cached_kb": cached_kb,
            "swap_total_kb": mi.get("SwapTotal"),
            "swap_free_kb": mi.get("SwapFree"),
        }

    # ------------------------------------------------------------------
    # sistema
    # ------------------------------------------------------------------

    def loadavg(self):
        """Carga media: dict com '1', '5' e '15' (ou None)."""
        text = _read_text(os.path.join(self.proc, "loadavg"))
        if not text:
            return None
        parts = text.split()
        if len(parts) < 3:
            return None
        try:
            return {"1": float(parts[0]), "5": float(parts[1]),
                    "15": float(parts[2])}
        except ValueError:
            return None

    def uptime(self):
        """Tempo de maquina: uptime_s, idle_s e sessions.

        * uptime_s -> segundos desde o boot (1o campo do /proc/uptime)
        * idle_s   -> segundos de CPU ociosa acumulados (2o campo)
        * sessions -> total de processos/threads do sistema, tirado do 4o
                      campo do /proc/loadavg ("N/M" -> M). None se o
                      /proc/loadavg nao existir.

        Devolve None se /proc/uptime nao existir.
        """
        text = _read_text(os.path.join(self.proc, "uptime"))
        if not text:
            return None
        parts = text.split()
        try:
            uptime_s = float(parts[0])
        except (ValueError, IndexError):
            return None
        idle_s = None
        if len(parts) > 1:
            try:
                idle_s = float(parts[1])
            except ValueError:
                idle_s = None

        sessions = None
        la = _read_text(os.path.join(self.proc, "loadavg"))
        if la:
            la_parts = la.split()
            if len(la_parts) >= 4 and "/" in la_parts[3]:
                try:
                    sessions = int(la_parts[3].split("/")[-1])
                except ValueError:
                    sessions = None

        return {"uptime_s": uptime_s, "idle_s": idle_s, "sessions": sessions}

    def kernel_info(self):
        """Informacoes do kernel: release, version, machine (+ proc_version)."""
        out = {"release": None, "version": None, "machine": None,
               "proc_version": None}
        text = _read_text(os.path.join(self.proc, "version"))
        if text:
            text = text.strip()
            out["proc_version"] = text
            parts = text.split()
            if len(parts) >= 3 and parts[0] == "Linux":
                out["release"] = parts[2]
        try:
            uname = os.uname()
            out["release"] = out["release"] or uname.release
            out["version"] = uname.version
            out["machine"] = uname.machine
        except (AttributeError, OSError):
            pass
        return out

    def os_info(self):
        """Conteudo do /etc/os-release (ou /usr/lib/os-release) em dict."""
        candidates = [os.path.join(self.etc, "os-release"),
                      os.path.join(self.usr, "lib", "os-release")]
        for path in candidates:
            text = _read_text(path)
            if text:
                return parse_os_release(text)
        return {}

    # ------------------------------------------------------------------
    # armazenamento
    # ------------------------------------------------------------------

    def _mount_point(self, path):
        """Descobre o ponto de montagem de um caminho (None se nao achar)."""
        try:
            real = os.path.realpath(path)
        except OSError:
            real = path
        best = None
        for table in ("self/mountinfo", "mounts"):
            text = _read_text(os.path.join(self.proc, table))
            if not text:
                continue
            for line in text.splitlines():
                parts = line.split()
                if not parts:
                    continue
                if table.endswith("mountinfo"):
                    if len(parts) < 5:
                        continue
                    mp = parts[4]
                else:
                    if len(parts) < 2:
                        continue
                    mp = parts[1]
                mp = _unescape_mount(mp)
                if real == mp or real.startswith(mp.rstrip("/") + "/"):
                    if best is None or len(mp) > len(best):
                        best = mp
            if best is not None:
                break
        return best

    def storage_info(self, path="/"):
        """Uso do disco em `path`.

        Devolve dict com total/used/free (em BYTES), used_pct e mount
        (ponto de montagem). Levanta FileNotFoundError se o caminho nao
        existir — erro honesto, nada de valor inventado.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(
                "caminho de armazenamento inexistente: %s" % path)
        usage = shutil.disk_usage(path)
        total = usage.total
        used = usage.used
        free = usage.free
        used_pct = (used * 100.0 / total) if total > 0 else None
        return {
            "total": total,
            "used": used,
            "free": free,
            "used_pct": used_pct,
            "mount": self._mount_point(path),
        }

    # ------------------------------------------------------------------
    # energia
    # ------------------------------------------------------------------

    def _power_supply_dirs(self):
        base = os.path.join(self.root, "class", "power_supply")
        return [d for d in (os.path.join(base, n) for n in _listdir(base))
                if os.path.isdir(d)]

    def power_supplies(self):
        """Lista de fontes de energia (name/type/status/capacity)."""
        out = []
        for d in self._power_supply_dirs():
            out.append({
                "name": os.path.basename(d),
                "type": _read_str(os.path.join(d, "type")),
                "status": _read_str(os.path.join(d, "status")),
                "capacity": _read_int(os.path.join(d, "capacity")),
            })
        return out

    def battery(self):
        """Informacoes da bateria (sysfs) ou None se nao houver bateria.

        Unidades (valores brutos do kernel):
          * voltage_now -> microvolt (uV)
          * current_now -> microampere (uA)
          * power_now   -> microwatt (uW)
          * temp        -> decimos de grau Celsius
        """
        for d in self._power_supply_dirs():
            if (_read_str(os.path.join(d, "type")) or "").lower() != "battery":
                continue
            return {
                "name": os.path.basename(d),
                "capacity": _read_int(os.path.join(d, "capacity")),
                "status": _read_str(os.path.join(d, "status")),
                "voltage_now": _read_int(os.path.join(d, "voltage_now")),
                "current_now": _read_int(os.path.join(d, "current_now")),
                "power_now": _read_int(os.path.join(d, "power_now")),
                "temp": _read_int(os.path.join(d, "temp")),
                "health": _read_str(os.path.join(d, "health")),
                "present": _read_bool(os.path.join(d, "present")),
            }
        return None

    # ------------------------------------------------------------------
    # temperatura
    # ------------------------------------------------------------------

    def thermal_zones(self):
        """Zonas termicas: lista de dicts zone/type/temp_c."""
        base = os.path.join(self.root, "class", "thermal")
        out = []
        for name in _listdir(base):
            d = os.path.join(base, name)
            if not name.startswith("thermal_zone") or not os.path.isdir(d):
                continue
            raw = _read_float(os.path.join(d, "temp"))
            temp_c = (raw / 1000.0) if raw is not None else None
            out.append({
                "zone": name,
                "type": _read_str(os.path.join(d, "type")),
                "temp_c": temp_c,
            })
        out.sort(key=lambda z: _zone_index(z["zone"]))
        return out

    # ------------------------------------------------------------------
    # processos
    # ------------------------------------------------------------------

    def _process_cpu_pct(self, pid, cpu_seconds):
        """Percentual de CPU do processo (precisa da leitura anterior)."""
        now = time.time()
        prev = self._proc_cpu.get(pid)
        self._proc_cpu[pid] = (cpu_seconds, now)
        if prev is None:
            return None
        elapsed = now - prev[1]
        if elapsed <= 0:
            return None
        delta = cpu_seconds - prev[0]
        if delta < 0:
            return None
        return delta / elapsed * 100.0

    def processes(self, limit=50):
        """Lista de processos, ordenada por RSS (maior primeiro).

        Cada item: pid, name, rss_kb, cpu_pct, state (+ uid, ppid).
        'cpu_pct' e None na primeira leitura (nao ha amostra anterior).
        Processos que somem no meio da leitura sao ignorados.
        """
        entries = []
        seen = set()
        for name in _listdir(self.proc):
            if not name.isdigit():
                continue
            base = os.path.join(self.proc, name)
            stat = parse_stat_line(_read_text(os.path.join(base, "stat")))
            if stat is None:
                continue
            pid = stat["pid"]
            seen.add(pid)
            rss_kb = stat["rss_pages"] * self.page_size / 1024.0
            cpu_seconds = (stat["utime"] + stat["stime"]) / float(self.clock_ticks)
            cpu_pct = self._process_cpu_pct(pid, cpu_seconds)
            entries.append({
                "pid": pid,
                "name": stat["name"],
                "rss_kb": rss_kb,
                "cpu_pct": cpu_pct,
                "state": stat["state"],
                "ppid": stat["ppid"],
                "uid": None,
            })

        # limpa o historico de processos que ja sumiram
        for pid in list(self._proc_cpu.keys()):
            if pid not in seen:
                del self._proc_cpu[pid]

        entries.sort(key=lambda e: e["rss_kb"], reverse=True)
        if limit and limit > 0:
            entries = entries[:limit]

        # o status so e lido para os que entraram na lista (menos I/O)
        for entry in entries:
            base = os.path.join(self.proc, str(entry["pid"]))
            status = parse_status(_read_text(os.path.join(base, "status")))
            if status.get("uid") is not None:
                entry["uid"] = status["uid"]
            if status.get("state"):
                entry["state"] = status["state"]
            if entry["rss_kb"] == 0.0 and status.get("vmrss_kb"):
                entry["rss_kb"] = float(status["vmrss_kb"])

        return entries

    # ------------------------------------------------------------------
    # video / DRM
    # ------------------------------------------------------------------

    def drm_info(self):
        """Conectores DRM: lista de dicts card/connector/status/modes/enabled."""
        base = os.path.join(self.root, "class", "drm")
        out = []
        for name in _listdir(base):
            d = os.path.join(base, name)
            if not os.path.isdir(d):
                continue
            card = name
            connector = None
            if re.match(r"^card\d+-", name):
                card, _, connector = name.partition("-")
            status = _read_str(os.path.join(d, "status"))
            modes_text = _read_text(os.path.join(d, "modes"))
            modes = []
            if modes_text:
                modes = [m for m in modes_text.split() if m]
            enabled = _read_bool(os.path.join(d, "enabled"))
            if connector is None and status is None and not modes:
                continue
            out.append({
                "card": card,
                "connector": connector,
                "status": status,
                "modes": modes,
                "enabled": enabled,
            })
        out.sort(key=lambda e: (e["card"], e["connector"] or ""))
        return out

    # ------------------------------------------------------------------
    # rede / bluetooth
    # ------------------------------------------------------------------

    def _rfkill(self):
        """Estado do rfkill (lista de dicts) ou [] se nao existir."""
        base = os.path.join(self.root, "class", "rfkill")
        out = []
        for name in _listdir(base):
            d = os.path.join(base, name)
            if not name.startswith("rfkill") or not os.path.isdir(d):
                continue
            out.append({
                "name": _read_str(os.path.join(d, "name")) or name,
                "soft_blocked": _read_bool(os.path.join(d, "soft")),
                "hard_blocked": _read_bool(os.path.join(d, "hard")),
            })
        return out

    def wlan_info(self):
        """Estado do Wi-Fi: iface, present e rfkill (ou None se nao houver).

        A interface e detectada pelo diretorio 'wireless' dentro de
        /sys/class/net/<iface> (ou pelo nome wlan0).
        """
        base = os.path.join(self.root, "class", "net")
        chosen = None
        for name in _listdir(base):
            d = os.path.join(base, name)
            if not os.path.isdir(d):
                continue
            if name == "wlan0":
                chosen = (name, d)
                break
        if chosen is None:
            for name in _listdir(base):
                d = os.path.join(base, name)
                if os.path.isdir(os.path.join(d, "wireless")):
                    chosen = (name, d)
                    break
        if chosen is None:
            return None
        name, d = chosen
        return {
            "iface": name,
            "present": os.path.isdir(d),
            "rfkill": self._rfkill(),
        }

    def bluetooth_info(self):
        """Estado do Bluetooth: present e devices (ou None se nao houver)."""
        base = os.path.join(self.root, "class", "bluetooth")
        if not os.path.isdir(base):
            return None
        devices = []
        for name in _listdir(base):
            if name.startswith("hci") and os.path.isdir(os.path.join(base, name)):
                devices.append(name)
        # dispositivos pareados/configurados (varia entre distros)
        for d in sorted(glob.glob(os.path.join(self.var, "bluetooth", "*",
                                               "devices", "*"))):
            devices.append(os.path.basename(d))
        return {"present": True, "devices": devices}

    # ------------------------------------------------------------------
    # resumo (painel Performance / Control Center)
    # ------------------------------------------------------------------

    def summary(self, storage_path="/", measure=0.05):
        """Coleta tudo que estiver disponivel, num unico dict.

        Sempre presentes:
          * 'collected_at' -> timestamp (time.time())
          * 'missing'      -> lista com o nome das metricas indisponiveis
        """
        usage = self.cpu_usage()
        if usage is None and measure and measure > 0:
            usage = self.cpu_usage_window(measure)
        times = self.cpu_times()

        try:
            storage = self.storage_info(storage_path)
        except (OSError, ValueError):
            storage = None

        data = {
            "collected_at": time.time(),
            "cpu_times": times,
            "cpu_usage": usage,
            "cpu_freq_mhz": self.cpu_freq(),
            "cpu_freq_max_mhz": self.cpu_freq_max(),
            "cpu_governors": self.cpu_governor(),
            "cpu_count": self.cpu_count(),
            "ram": self.ram_info(),
            "loadavg": self.loadavg(),
            "uptime": self.uptime(),
            "storage": storage,
            "battery": self.battery(),
            "power_supplies": self.power_supplies(),
            "thermal_zones": self.thermal_zones(),
            "processes": self.processes(),
            "drm": self.drm_info(),
            "wlan": self.wlan_info(),
            "bluetooth": self.bluetooth_info(),
            "kernel": self.kernel_info(),
            "os": self.os_info(),
        }
        data["missing"] = self._missing(data)
        return data

    @staticmethod
    def _missing(data):
        """Lista das metricas indisponiveis."""
        missing = []
        for name in ("cpu_times", "cpu_usage", "ram", "loadavg", "uptime",
                     "storage", "battery", "wlan", "bluetooth"):
            if data.get(name) is None:
                missing.append(name)
        for name in ("cpu_freq_mhz", "cpu_freq_max_mhz", "cpu_governors",
                     "power_supplies", "thermal_zones", "drm"):
            if not data.get(name):
                missing.append(name)
        if not data.get("os"):
            missing.append("os")
        kernel = data.get("kernel") or {}
        if not any(kernel.values()):
            missing.append("kernel")
        return missing

    def summary_json(self, **kwargs):
        """O resumo em JSON (para o Control Center falar por pipe/socket)."""
        return json.dumps(self.summary(**kwargs), default=str)


# --- instancia padrao (uso pontual) ---------------------------------------

_default = None


def default():
    """Instancia compartilhada com os caminhos reais do sistema."""
    global _default
    if _default is None:
        _default = SysInfo()
    return _default


def summary(**kwargs):
    """Atalho: resumo do sistema real."""
    return default().summary(**kwargs)
