#!/usr/bin/env python3
"""NURA OS — testes da camada de metricas do sistema (nura_sysinfo).

Roda sem o aparelho: as metricas sao lidas de uma arvore de arquivos
falsa montada num diretorio temporario. No fim, o mesmo codigo e
exercitado contra o /proc e o /sys reais, so para garantir que nada
quebre (e nao para comparar valores).

Uso:
    python3 test_sysinfo.py
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from nura_sysinfo import (  # noqa: E402
    SysInfo,
    parse_os_release,
    parse_cpu_stat,
    parse_meminfo,
    parse_stat_line,
    busy_fraction,
)

falhas = []


def check(nome, cond, detalhe=""):
    if cond:
        print("  [ OK ] %s" % nome)
    else:
        print("  [FALHA] %s %s" % (nome, detalhe))
        falhas.append(nome)
    return bool(cond)


def near(a, b, tol=1e-6):
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


# ----------------------------------------------------------------------
# arvore de arquivos falsa
# ----------------------------------------------------------------------

def write(path, content):
    """Cria um arquivo (com os diretorios) e escreve o conteudo."""
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w") as f:
        f.write(content)


STAT_A = (
    "cpu  100 0 100 1000 0 0 0 0 0 0\n"
    "cpu0 100 0 100 1000 0 0 0 0 0 0\n"
    "cpu1 0 0 0 1000 0 0 0 0 0 0\n"
    "intr 12345\n"
    "ctxt 6789\n"
)

STAT_B = (
    "cpu  200 0 200 1050 0 0 0 0 0 0\n"
    "cpu0 200 0 200 1000 0 0 0 0 0 0\n"
    "cpu1 0 0 0 1050 0 0 0 0 0 0\n"
    "intr 12345\n"
)

MEMINFO = (
    "MemTotal:        2048000 kB\n"
    "MemFree:          100000 kB\n"
    "MemAvailable:     800000 kB\n"
    "Buffers:           50000 kB\n"
    "Cached:           400000 kB\n"
    "SwapCached:            0 kB\n"
    "SwapTotal:        500000 kB\n"
    "SwapFree:         450000 kB\n"
)

LOADAVG = "0.52 0.58 0.59 2/437 1234\n"

# o 4o campo do loadavg e "running/total" (2 rodando de 437 processos)
LOADAVG_TOTAL = 437

UPTIME = "12345.67 98765.43\n"

PROC_VERSION = ("Linux version 4.14.0-nura (gcc 8.3.0) #1 SMP PREEMPT "
                "Tue Nov 12 10:00:00 UTC 2019\n")

OS_RELEASE = (
    "# comentario de teste\n"
    'NAME="Alpine Linux"\n'
    "ID=alpine\n"
    'VERSION_ID=3.19.1\n'
    'PRETTY_NAME="Alpine Linux v3.19"\n'
    "HOME_URL=https://alpinelinux.org/\n"
)

# /proc/<pid>/stat: pid (comm) state ppid pgrp session tty tpgid flags
# minflt cminflt majflt cmajflt utime stime cutime cstime priority nice
# num_threads itrealvalue starttime vsize rss
STAT_PID100 = ("100 (worker do sistema) S 1 100 100 0 -1 4194560 1234 0 0 0 "
               "100 50 0 0 20 0 3 0 500 123456 4096\n")
STAT_PID101 = ("101 (init) S 0 101 101 0 -1 4194560 10 0 0 0 10 5 0 0 20 0 1 "
               "0 400 99999 1024\n")

STATUS_PID100 = ("Name:\tworker\n"
                 "State:\tS (sleeping)\n"
                 "Uid:\t0\t0\t0\t0\n"
                 "VmRSS:\t   16384 kB\n")
STATUS_PID101 = ("Name:\tinit\n"
                 "State:\tR (running)\n"
                 "Uid:\t1000\t1000\t1000\t1000\n"
                 "VmRSS:\t    4096 kB\n")


def build_fake_tree(base):
    """Monta a arvore de /proc e /sys falsos. Devolve os caminhos."""
    proc = os.path.join(base, "proc")
    sysfs = os.path.join(base, "sys")
    etc = os.path.join(base, "etc")
    var = os.path.join(base, "var")
    usr = os.path.join(base, "usr")

    write(os.path.join(proc, "stat"), STAT_A)
    write(os.path.join(proc, "meminfo"), MEMINFO)
    write(os.path.join(proc, "loadavg"), LOADAVG)
    write(os.path.join(proc, "uptime"), UPTIME)
    write(os.path.join(proc, "version"), PROC_VERSION)

    write(os.path.join(proc, "100", "stat"), STAT_PID100)
    write(os.path.join(proc, "100", "status"), STATUS_PID100)
    write(os.path.join(proc, "101", "stat"), STAT_PID101)
    write(os.path.join(proc, "101", "status"), STATUS_PID101)

    # tabela de montagem (para o storage_info achar o ponto de montagem)
    write(os.path.join(proc, "self", "mountinfo"),
          "25 0 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw\n"
          "30 25 8:2 / /tmp rw,relatime shared:2 - ext4 /dev/sdb1 rw\n")

    # bateria
    bat = os.path.join(sysfs, "class", "power_supply", "battery")
    write(os.path.join(bat, "type"), "Battery\n")
    write(os.path.join(bat, "capacity"), "87\n")
    write(os.path.join(bat, "status"), "Charging\n")
    write(os.path.join(bat, "voltage_now"), "4200000\n")
    write(os.path.join(bat, "current_now"), "1500000\n")
    write(os.path.join(bat, "power_now"), "6300000\n")
    write(os.path.join(bat, "temp"), "425\n")
    write(os.path.join(bat, "health"), "Good\n")
    write(os.path.join(bat, "present"), "1\n")

    # zonas termicas
    write(os.path.join(sysfs, "class", "thermal", "thermal_zone0", "type"),
          "cpu-thermal\n")
    write(os.path.join(sysfs, "class", "thermal", "thermal_zone0", "temp"),
          "45000\n")
    write(os.path.join(sysfs, "class", "thermal", "thermal_zone1", "type"),
          "gpu-thermal\n")
    write(os.path.join(sysfs, "class", "thermal", "thermal_zone1", "temp"),
          "52000\n")

    # frequencias
    for idx, (cur, mx, gov) in enumerate(((1014000, 1998000, "schedutil"),
                                           (998000, 1998000, "schedutil"))):
        d = os.path.join(sysfs, "devices", "system", "cpu", "cpu%d" % idx,
                         "cpufreq")
        write(os.path.join(d, "scaling_cur_freq"), "%d\n" % cur)
        write(os.path.join(d, "scaling_max_freq"), "%d\n" % mx)
        write(os.path.join(d, "scaling_governor"), "%s\n" % gov)

    # DRM
    drm = os.path.join(sysfs, "class", "drm", "card0-HDMI-A-1")
    write(os.path.join(drm, "status"), "connected\n")
    write(os.path.join(drm, "modes"), "1920x1080 1280x720\n")
    write(os.path.join(drm, "enabled"), "1\n")

    # /etc/os-release
    write(os.path.join(etc, "os-release"), OS_RELEASE)

    # /var vazio (sem bluetooth)
    if not os.path.isdir(var):
        os.makedirs(var)
    if not os.path.isdir(usr):
        os.makedirs(usr)

    return {"proc": proc, "sys": sysfs, "etc": etc, "var": var, "usr": usr}


def fake_sysinfo(tree, **kw):
    """Instancia do SysInfo apontada para a arvore falsa."""
    return SysInfo(root=tree["sys"], proc=tree["proc"], etc=tree["etc"],
                   var=tree["var"], usr=tree["usr"], clock_ticks=100,
                   page_size=4096, **kw)


# ----------------------------------------------------------------------
# testes com a arvore falsa
# ----------------------------------------------------------------------

def test_parse_pure():
    print("\n=== funcoes de parse ===")
    d = parse_os_release(OS_RELEASE)
    check("os-release: NAME sem aspas", d.get("NAME") == "Alpine Linux",
          repr(d.get("NAME")))
    check("os-release: ID sem aspas", d.get("ID") == "alpine",
          repr(d.get("ID")))
    check("os-release: valor sem aspas", d.get("HOME_URL") ==
          "https://alpinelinux.org/", repr(d.get("HOME_URL")))
    check("os-release: comentario ignorado", "#" not in d)

    total, cores = parse_cpu_stat(STAT_A)
    check("cpu_stat: agregado lido", total is not None and
          total["user"] == 100, repr(total))
    check("cpu_stat: dois nucleos", len(cores) == 2, repr(cores))

    mi = parse_meminfo(MEMINFO)
    check("meminfo: MemTotal em kB", mi.get("MemTotal") == 2048000,
          repr(mi.get("MemTotal")))

    st = parse_stat_line(STAT_PID100)
    check("stat: nome com espacos", st and st["name"] == "worker do sistema",
          repr(st))
    check("stat: rss em paginas", st and st["rss_pages"] == 4096, repr(st))
    check("stat: utime/stime", st and st["utime"] == 100 and st["stime"] == 50,
          repr(st))

    check("busy_fraction: 100% quando so ha trabalho",
          near(busy_fraction({"idle": 0.0, "iowait": 0.0},
                             {"idle": 0.0, "iowait": 0.0,
                              "user": 1.0}), 1.0))


def test_cpu_times(tree):
    print("\n=== cpu_times / cpu_usage ===")
    si = fake_sysinfo(tree)
    t = si.cpu_times()
    check("cpu_times: devolve dict", isinstance(t, dict), repr(t))
    check("cpu_times: user em segundos", near(t.get("user"), 1.0),
          repr(t.get("user")))
    check("cpu_times: idle em segundos", near(t.get("idle"), 10.0),
          repr(t.get("idle")))
    check("cpu_times: steal zerado (valor real)", near(t.get("steal"), 0.0),
          repr(t.get("steal")))

    # cpu_usage sem leitura anterior valida -> None
    si2 = fake_sysinfo(tree)
    check("cpu_usage: None sem leitura anterior", si2.cpu_usage() is None)

    # agora mede o delta entre STAT_A e STAT_B
    write(os.path.join(tree["proc"], "stat"), STAT_B)
    u = si.cpu_usage(t)
    check("cpu_usage: devolve dict", isinstance(u, dict), repr(u))
    # delta agregado: user +100, system +100, idle +50 (ticks) -> 200/250 = 0.8
    check("cpu_usage: total == 0.8", near(u.get("total"), 0.8),
          repr(u.get("total")))
    cores = u.get("per_core") or []
    check("cpu_usage: per_core com 2 nucleos", len(cores) == 2, repr(cores))
    if len(cores) == 2:
        check("cpu_usage: nucleo 0 a 100%", near(cores[0], 1.0), repr(cores[0]))
        check("cpu_usage: nucleo 1 a 0%", near(cores[1], 0.0), repr(cores[1]))

    # sem mudanca no arquivo -> 0.0 (nenhum tempo de CPU decorreu)
    u2 = si.cpu_usage()
    check("cpu_usage: sem delta -> 0.0", near(u2.get("total"), 0.0),
          repr(u2.get("total")))

    freqs = si.cpu_freq()
    check("cpu_freq: lista em MHz", freqs == [1014.0, 998.0], repr(freqs))
    fmax = si.cpu_freq_max()
    check("cpu_freq_max: lista em MHz", fmax == [1998.0, 1998.0], repr(fmax))
    check("cpu_freq_current: maior frequencia",
          near(si.cpu_freq_current(), 1014.0), repr(si.cpu_freq_current()))
    govs = si.cpu_governor()
    check("cpu_governor: lista de governors", govs == ["schedutil",
                                                       "schedutil"],
          repr(govs))


def test_ram(tree):
    print("\n=== ram_info ===")
    si = fake_sysinfo(tree)
    r = si.ram_info()
    check("ram_info: devolve dict", isinstance(r, dict), repr(r))
    check("ram_info: total_kb", r.get("total_kb") == 2048000,
          repr(r.get("total_kb")))
    check("ram_info: free_kb", r.get("free_kb") == 100000,
          repr(r.get("free_kb")))
    check("ram_info: available_kb", r.get("available_kb") == 800000,
          repr(r.get("available_kb")))
    check("ram_info: used_kb == total - available (nao total - free)",
          r.get("used_kb") == 2048000 - 800000, repr(r.get("used_kb")))
    check("ram_info: used_pct ~ 60.9375", near(r.get("used_pct"), 60.9375),
          repr(r.get("used_pct")))
    check("ram_info: cached_kb", r.get("cached_kb") == 400000,
          repr(r.get("cached_kb")))
    check("ram_info: swap_total_kb", r.get("swap_total_kb") == 500000,
          repr(r.get("swap_total_kb")))
    check("ram_info: swap_free_kb", r.get("swap_free_kb") == 450000,
          repr(r.get("swap_free_kb")))


def test_battery(tree):
    print("\n=== bateria / power_supply ===")
    si = fake_sysinfo(tree)
    b = si.battery()
    check("battery: devolve dict", isinstance(b, dict), repr(b))
    check("battery: nome", b.get("name") == "battery", repr(b.get("name")))
    check("battery: capacity", b.get("capacity") == 87,
          repr(b.get("capacity")))
    check("battery: status", b.get("status") == "Charging",
          repr(b.get("status")))
    check("battery: voltage_now", b.get("voltage_now") == 4200000,
          repr(b.get("voltage_now")))
    check("battery: current_now", b.get("current_now") == 1500000,
          repr(b.get("current_now")))
    check("battery: power_now", b.get("power_now") == 6300000,
          repr(b.get("power_now")))
    check("battery: temp", b.get("temp") == 425, repr(b.get("temp")))
    check("battery: health", b.get("health") == "Good", repr(b.get("health")))
    check("battery: present", b.get("present") is True,
          repr(b.get("present")))

    ps = si.power_supplies()
    check("power_supplies: 1 fonte", len(ps) == 1, repr(ps))
    if ps:
        check("power_supplies: type", ps[0].get("type") == "Battery",
              repr(ps[0]))
        check("power_supplies: capacity", ps[0].get("capacity") == 87,
              repr(ps[0]))

    # arvore sem bateria -> None (e nao um dict falso)
    tmp = tempfile.mkdtemp(prefix="nura-sysinfo-")
    try:
        tree2 = build_fake_tree(tmp)
        shutil.rmtree(os.path.join(tree2["sys"], "class", "power_supply"))
        si2 = fake_sysinfo(tree2)
        check("battery: None quando nao ha bateria", si2.battery() is None)
        check("power_supplies: lista vazia", si2.power_supplies() == [],
              repr(si2.power_supplies()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_thermal(tree):
    print("\n=== zonas termicas ===")
    si = fake_sysinfo(tree)
    z = si.thermal_zones()
    check("thermal_zones: 2 zonas", len(z) == 2, repr(z))
    if len(z) == 2:
        check("thermal_zones: zona0 tipo", z[0].get("type") == "cpu-thermal",
              repr(z[0]))
        check("thermal_zones: zona0 temp_c == 45.0",
              near(z[0].get("temp_c"), 45.0), repr(z[0]))
        check("thermal_zones: zona1 temp_c == 52.0",
              near(z[1].get("temp_c"), 52.0), repr(z[1]))


def test_processes(tree):
    print("\n=== processos ===")
    si = fake_sysinfo(tree)
    p = si.processes()
    check("processes: 2 processos", len(p) == 2, repr(p))
    if len(p) == 2:
        check("processes: ordenado por RSS decrescente",
              p[0]["rss_kb"] > p[1]["rss_kb"], repr([x["rss_kb"] for x in p]))
        check("processes: rss_kb do maior", near(p[0]["rss_kb"], 16384.0),
              repr(p[0]["rss_kb"]))
        check("processes: rss_kb do menor", near(p[1]["rss_kb"], 4096.0),
              repr(p[1]["rss_kb"]))
        check("processes: pid", p[0]["pid"] == 100, repr(p[0]))
        check("processes: nome", p[0]["name"] == "worker do sistema",
              repr(p[0]))
        check("processes: uid vem do status", p[1]["uid"] == 1000,
              repr(p[1]))
        check("processes: state", p[0]["state"] == "S", repr(p[0]))
        check("processes: cpu_pct sem amostra anterior -> None",
              p[0]["cpu_pct"] is None, repr(p[0]["cpu_pct"]))

    p2 = si.processes()
    if p2:
        check("processes: cpu_pct medido na segunda leitura",
              p2[0]["cpu_pct"] is not None and p2[0]["cpu_pct"] >= 0.0,
              repr(p2[0]["cpu_pct"]))

    limited = si.processes(limit=1)
    check("processes: respeita o limite", len(limited) == 1, repr(limited))


def test_os_kernel(tree):
    print("\n=== os-release / kernel ===")
    si = fake_sysinfo(tree)
    o = si.os_info()
    check("os_info: NAME", o.get("NAME") == "Alpine Linux", repr(o))
    check("os_info: VERSION_ID", o.get("VERSION_ID") == "3.19.1", repr(o))

    k = si.kernel_info()
    check("kernel_info: release", k.get("release") == "4.14.0-nura",
          repr(k.get("release")))
    check("kernel_info: proc_version comeca com Linux",
          (k.get("proc_version") or "").startswith("Linux version"),
          repr(k.get("proc_version")))
    check("kernel_info: machine presente ou None",
          k.get("machine") is None or isinstance(k.get("machine"), str),
          repr(k.get("machine")))


def test_drm(tree):
    print("\n=== DRM ===")
    si = fake_sysinfo(tree)
    d = si.drm_info()
    check("drm_info: 1 conector", len(d) == 1, repr(d))
    if d:
        check("drm_info: card", d[0].get("card") == "card0", repr(d[0]))
        check("drm_info: connector", d[0].get("connector") == "HDMI-A-1",
              repr(d[0]))
        check("drm_info: status", d[0].get("status") == "connected",
              repr(d[0]))
        check("drm_info: modes", d[0].get("modes") == ["1920x1080", "1280x720"],
              repr(d[0]))


def test_load_uptime(tree):
    print("\n=== loadavg / uptime ===")
    si = fake_sysinfo(tree)
    la = si.loadavg()
    check("loadavg: 1 min", near(la.get("1"), 0.52), repr(la))
    check("loadavg: 5 min", near(la.get("5"), 0.58), repr(la))
    check("loadavg: 15 min", near(la.get("15"), 0.59), repr(la))

    up = si.uptime()
    check("uptime: uptime_s", near(up.get("uptime_s"), 12345.67), repr(up))
    check("uptime: idle_s", near(up.get("idle_s"), 98765.43), repr(up))
    check("uptime: sessions (total de processos do loadavg)",
          up.get("sessions") == LOADAVG_TOTAL,
          repr(up))


def test_storage(tree, base):
    print("\n=== armazenamento ===")
    si = fake_sysinfo(tree)
    s = si.storage_info("/")
    check("storage_info: devolve dict", isinstance(s, dict), repr(s))
    check("storage_info: total > 0", (s.get("total") or 0) > 0, repr(s))
    check("storage_info: used_pct entre 0 e 100",
          s.get("used_pct") is not None and
          0.0 <= s["used_pct"] <= 100.0, repr(s.get("used_pct")))
    check("storage_info: mount vem do mountinfo",
          s.get("mount") == "/", repr(s.get("mount")))
    # o prefixo mais longo da tabela de montagem que cobre o caminho
    s2 = si.storage_info(base)
    check("storage_info: mount do prefixo mais longo",
          s2.get("mount") == "/tmp", repr(s2.get("mount")))

    erro = None
    try:
        si.storage_info("/caminho/que/nao/existe/nura")
    except (OSError, ValueError) as e:
        erro = e
    check("storage_info: erro honesto para caminho inexistente",
          erro is not None, "nao levantou erro")


def test_summary(tree):
    print("\n=== summary ===")
    si = fake_sysinfo(tree)
    # measure=0.05: mede o uso da CPU numa janela real (o arquivo do
    # /proc/stat falso nao muda -> 0.0 de uso, que e a medicao honesta)
    s = si.summary()
    check("summary: devolve dict", isinstance(s, dict))
    check("summary: collected_at e numero",
          isinstance(s.get("collected_at"), float), repr(s.get("collected_at")))
    check("summary: missing e lista", isinstance(s.get("missing"), list),
          repr(s.get("missing")))
    miss = s.get("missing") or []
    check("summary: 'bluetooth' em missing (nao existe na arvore)",
          "bluetooth" in miss, repr(miss))
    check("summary: 'wlan' em missing (nao existe na arvore)",
          "wlan" in miss, repr(miss))
    check("summary: 'battery' NAO esta em missing", "battery" not in miss,
          repr(miss))
    check("summary: 'ram' NAO esta em missing", "ram" not in miss, repr(miss))
    check("summary: 'thermal_zones' NAO esta em missing",
          "thermal_zones" not in miss, repr(miss))
    check("summary: 'drm' NAO esta em missing", "drm" not in miss, repr(miss))
    check("summary: 'os' NAO esta em missing", "os" not in miss, repr(miss))
    check("summary: cpu_times presente", isinstance(s.get("cpu_times"), dict),
          repr(s.get("cpu_times")))
    check("summary: cpu_usage presente (medido na janela)",
          isinstance(s.get("cpu_usage"), dict), repr(s.get("cpu_usage")))
    check("summary: cpu_usage sem leitura anterior e None",
          fake_sysinfo(tree).summary(measure=0.0).get("cpu_usage") is None,
          "deveria ser None sem janela de medicao")
    check("summary: processos presentes", len(s.get("processes") or []) == 2,
          repr(s.get("processes")))

    txt = si.summary_json()
    obj = json.loads(txt)
    check("summary_json: JSON valido", obj.get("missing") is not None,
          txt[:120])


def test_missing_e_empty(tree):
    print("\n=== metricas ausentes ===")
    tmp = tempfile.mkdtemp(prefix="nura-sysinfo-")
    try:
        # arvore praticamente vazia: nada existe
        proc = os.path.join(tmp, "proc")
        sysfs = os.path.join(tmp, "sys")
        etc = os.path.join(tmp, "etc")
        var = os.path.join(tmp, "var")
        usr = os.path.join(tmp, "usr")
        for d in (proc, sysfs, etc, var, usr):
            os.makedirs(d)
        si = SysInfo(root=sysfs, proc=proc, etc=etc, var=var, usr=usr,
                     clock_ticks=100, page_size=4096)

        check("cpu_times: None sem /proc/stat", si.cpu_times() is None)
        check("ram_info: None sem /proc/meminfo", si.ram_info() is None)
        check("loadavg: None sem /proc/loadavg", si.loadavg() is None)
        check("uptime: None sem /proc/uptime", si.uptime() is None)
        check("cpu_freq: [] sem driver", si.cpu_freq() == [],
              repr(si.cpu_freq()))
        check("cpu_freq_max: [] sem driver", si.cpu_freq_max() == [],
              repr(si.cpu_freq_max()))
        check("cpu_freq_current: None sem driver",
              si.cpu_freq_current() is None, repr(si.cpu_freq_current()))
        check("cpu_governor: [] sem driver", si.cpu_governor() == [],
              repr(si.cpu_governor()))
        check("battery: None sem bateria", si.battery() is None)
        check("power_supplies: []", si.power_supplies() == [])
        check("thermal_zones: []", si.thermal_zones() == [])
        check("drm_info: []", si.drm_info() == [])
        check("wlan_info: None", si.wlan_info() is None)
        check("bluetooth_info: None", si.bluetooth_info() is None)
        check("processes: []", si.processes() == [])
        check("os_info: {} ", si.os_info() == {}, repr(si.os_info()))

        s = si.summary(measure=0.0)
        miss = s.get("missing") or []
        check("summary: lista bem grande de ausentes",
              "ram" in miss and "battery" in miss and "cpu_times" in miss,
              repr(miss))
        check("summary: nenhum valor inventado (cpu_times e None)",
              s.get("cpu_times") is None, repr(s.get("cpu_times")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# teste contra o sistema real
# ----------------------------------------------------------------------

def test_real_system():
    print("\n=== sistema real (/proc e /sys de verdade) ===")
    si = SysInfo()
    try:
        t = si.cpu_times()
        check("real: cpu_times nao quebra",
              t is None or isinstance(t, dict), repr(t))
        u = si.cpu_usage(t) if t else si.cpu_usage()
        check("real: cpu_usage nao quebra",
              u is None or isinstance(u, dict), repr(u))
        r = si.ram_info()
        check("real: ram_info nao quebra",
              r is None or isinstance(r, dict), repr(r))
        la = si.loadavg()
        check("real: loadavg nao quebra", la is None or isinstance(la, dict))
        up = si.uptime()
        check("real: uptime nao quebra", up is None or isinstance(up, dict))
        f = si.cpu_freq()
        check("real: cpu_freq e lista", isinstance(f, list), repr(f))
        b = si.battery()
        check("real: battery e dict ou None", b is None or isinstance(b, dict))
        z = si.thermal_zones()
        check("real: thermal_zones e lista", isinstance(z, list))
        p = si.processes(limit=5)
        check("real: processes e lista", isinstance(p, list))
        if p:
            check("real: processos tem pid/nome/rss",
                  all(("pid" in x and "name" in x and "rss_kb" in x)
                      for x in p), repr(p[:2]))
        d = si.drm_info()
        check("real: drm_info e lista", isinstance(d, list))
        w = si.wlan_info()
        check("real: wlan_info e dict ou None", w is None or isinstance(w, dict))
        bl = si.bluetooth_info()
        check("real: bluetooth_info e dict ou None",
              bl is None or isinstance(bl, dict))
        k = si.kernel_info()
        check("real: kernel_info tem release", isinstance(k, dict) and
              ("release" in k), repr(k))
        o = si.os_info()
        check("real: os_info e dict", isinstance(o, dict))
        s = si.summary()
        check("real: summary nao quebra", isinstance(s, dict))
        check("real: summary tem collected_at",
              isinstance(s.get("collected_at"), float))
        check("real: summary tem missing (lista)",
              isinstance(s.get("missing"), list))
        print("    (missing no sistema real: %s)" % (s.get("missing"),))
    except Exception as e:  # nao deve acontecer
        check("real: nenhuma excecao", False, "%s: %s" % (type(e).__name__, e))


# ----------------------------------------------------------------------

def main():
    print("NURA OS — teste de metricas do sistema (nura_sysinfo)")
    base = tempfile.mkdtemp(prefix="nura-sysinfo-")
    try:
        tree = build_fake_tree(base)
        test_parse_pure()
        test_cpu_times(tree)
        test_ram(tree)
        test_battery(tree)
        test_thermal(tree)
        test_processes(tree)
        test_os_kernel(tree)
        test_drm(tree)
        test_load_uptime(tree)
        test_storage(tree, base)
        test_summary(tree)
        test_missing_e_empty(tree)
        test_real_system()
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print("\n%s" % ("TODOS OS TESTES PASSARAM" if not falhas
                    else "FALHAS (%d): %s" % (len(falhas), falhas)))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
