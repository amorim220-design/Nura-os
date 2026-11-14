"""NURA OS — modo de recuperacao (obrigatorio).

Garante que sempre exista um caminho de volta ao terminal, mesmo que a
interface grafica falhe de forma repetida.

Mecanismo:
  * o shell registra sucesso/falha em /var/lib/nura/state.json;
  * se o desktop falhar N vezes seguidas, o servico de inicializacao
    NAO sobe a interface grafica e o aparelho fica no console
    (fail-safe automatico);
  * o auto-start da interface pode ser desligado a qualquer momento
    (`nura-recovery disable`) sem mexer no bootloader nem em
    particoes;
  * as configuracoes do shell sao guardadas em /var/lib/nura/backup/
    antes de qualquer alteracao, para rollback.

Nada aqui altera o bootloader, o initramfs ou as particoes.
"""

import json
import os
import shutil
import subprocess
import time

STATE_DIR = "/var/lib/nura"
STATE_FILE = os.path.join(STATE_DIR, "state.json")
BACKUP_DIR = os.path.join(STATE_DIR, "backup")
RUNLEVEL_DIR = "/etc/runlevels/default"          # OpenRC
SYSTEMD_UNIT = "nura-shell.service"              # systemd
SERVICE_NAME = "nura-shell"
CONFIG_DIR = "/etc/nura"

FALLBACK_LIMIT = 3          # falhas seguidas -> modo seguro
MAX_BACKUPS = 5


def _ensure_dirs():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except Exception:
        pass


def _read_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_state(st):
    _ensure_dirs()
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, STATE_FILE)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------
# contagem de falhas
# --------------------------------------------------------------------

def record_failure(reason="desconhecido", state_file=None):
    """Registra uma falha da interface grafica."""
    st = _read_state()
    st["failures"] = int(st.get("failures", 0)) + 1
    st["last_failure"] = reason
    st["last_failure_at"] = time.time()
    _write_state(st)
    return st["failures"]


def record_success(state_file=None):
    """Zera a contagem (a sessao grafica subiu bem)."""
    st = _read_state()
    st["failures"] = 0
    st["last_success_at"] = time.time()
    st.pop("last_failure", None)
    _write_state(st)
    return True


def consecutive_failures():
    return int(_read_state().get("failures", 0))


def last_failure():
    return _read_state().get("last_failure")


def should_fallback(limit=FALLBACK_LIMIT):
    """Verdadeiro se a interface falhou demais e o console deve prevalecer."""
    return consecutive_failures() >= limit


def reset_failures():
    st = _read_state()
    st["failures"] = 0
    _write_state(st)


# --------------------------------------------------------------------
# auto-start da interface grafica
# --------------------------------------------------------------------

def _have_systemd():
    return os.path.isdir("/run/systemd/system")


def _systemctl(*args):
    try:
        import subprocess
        return subprocess.call(["systemctl"] + list(args),
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    except Exception:
        return 1


def autostart_enabled():
    """Verdadeiro se a interface grafica sobe automaticamente."""
    if _have_systemd():
        return _systemctl("is-enabled", SYSTEMD_UNIT) == 0
    link = os.path.join(RUNLEVEL_DIR, SERVICE_NAME)
    return os.path.exists(link)


def enable_autostart():
    """Reabilita a inicializacao automatica da interface."""
    _ensure_dirs()
    if _have_systemd():
        ok = _systemctl("enable", SYSTEMD_UNIT) == 0
        return ok, ("auto-start habilitado" if ok
                    else "falha ao habilitar %s" % SYSTEMD_UNIT)
    try:
        os.makedirs(RUNLEVEL_DIR, exist_ok=True)
    except Exception:
        pass
    src = None
    for base in ("/etc/init.d", "/usr/local/etc/init.d"):
        p = os.path.join(base, SERVICE_NAME)
        if os.path.exists(p):
            src = p
            break
    if not src:
        return False, "servico %s nao encontrado" % SERVICE_NAME
    dst = os.path.join(RUNLEVEL_DIR, SERVICE_NAME)
    try:
        if os.path.islink(dst) or os.path.exists(dst):
            os.remove(dst)
        os.symlink(src, dst)
        return True, "auto-start habilitado"
    except Exception as e:
        return False, str(e)


def disable_autostart(reason="desativado pelo usuario"):
    """Desabilita a inicializacao automatica (reboot seguro no console)."""
    st = _read_state()
    st["autostart_disabled_reason"] = reason
    st["autostart_disabled_at"] = time.time()
    _write_state(st)
    if _have_systemd():
        ok = _systemctl("disable", SYSTEMD_UNIT) == 0
        return ok, ("auto-start desabilitado" if ok
                    else "falha ao desabilitar %s" % SYSTEMD_UNIT)
    link = os.path.join(RUNLEVEL_DIR, SERVICE_NAME)
    try:
        if os.path.islink(link):
            os.remove(link)
            return True, "auto-start desabilitado"
        if os.path.exists(link):
            os.rename(link, link + ".disabled")
            return True, "auto-start desabilitado (renomeado)"
        return False, "auto-start ja estava desabilitado"
    except Exception as e:
        return False, str(e)


# --------------------------------------------------------------------
# backup / rollback das configuracoes
# --------------------------------------------------------------------

def backup_config(label=None):
    """Guarda uma copia das configuracoes do NURA. Devolve o caminho."""
    _ensure_dirs()
    ts = time.strftime("%Y%m%d-%H%M%S")
    label = label or ("auto" if consecutive_failures() else "manual")
    dest = os.path.join(BACKUP_DIR, "%s-%s" % (label, ts))
    try:
        if os.path.isdir(CONFIG_DIR):
            shutil.copytree(CONFIG_DIR, dest)
        else:
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "vazio.txt"), "w") as f:
                f.write("sem %s no momento do backup\n" % CONFIG_DIR)
        return dest, None
    except Exception as e:
        return None, str(e)


def list_backups():
    try:
        return sorted(os.listdir(BACKUP_DIR))
    except Exception:
        return []


def restore_last_backup():
    """Restaura o backup mais recente por cima da configuracao atual."""
    backups = list_backups()
    if not backups:
        return False, "nenhum backup disponivel"
    last = os.path.join(BACKUP_DIR, backups[-1])
    try:
        if os.path.isdir(CONFIG_DIR):
            shutil.rmtree(CONFIG_DIR)
        shutil.copytree(last, CONFIG_DIR)
        return True, "restaurado: %s" % last
    except Exception as e:
        return False, str(e)


def prune_backups(keep=MAX_BACKUPS):
    backups = list_backups()
    removed = 0
    for b in backups[:-keep] if keep > 0 else backups:
        try:
            shutil.rmtree(os.path.join(BACKUP_DIR, b))
            removed += 1
        except Exception:
            pass
    return removed


# --------------------------------------------------------------------
# diagnostico
# --------------------------------------------------------------------

def doctor():
    """Relatorio de recuperacao (para o usuario ou para o boot)."""
    st = _read_state()
    info = {
        "state_file": STATE_FILE,
        "state_exists": os.path.exists(STATE_FILE),
        "consecutive_failures": int(st.get("failures", 0)),
        "last_failure": st.get("last_failure"),
        "autostart_enabled": autostart_enabled(),
        "fallback_limit": FALLBACK_LIMIT,
        "should_fallback": should_fallback(),
        "backups": list_backups(),
        "config_dir_exists": os.path.isdir(CONFIG_DIR),
    }
    try:
        info["service_script"] = os.path.exists("/etc/init.d/" + SERVICE_NAME)
    except Exception:
        info["service_script"] = False
    return info


def print_doctor():
    for k, v in doctor().items():
        print("%-22s %s" % (k, v))


def enter_safe_mode():
    """Desabilita o auto-start e devolve o controle ao console.

    Usado pelo servico de boot quando a interface falha repetidamente.
    """
    ok, msg = disable_autostart("falhas repetidas da interface grafica")
    print("[nura-recovery] modo seguro: %s" % msg)
    try:
        # garante que o console continue utilizavel
        subprocess.call(["/etc/init.d/crond", "status"], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return ok


def main():
    import argparse
    ap = argparse.ArgumentParser(description="NURA OS - recuperacao")
    ap.add_argument("acao", choices=["status", "enable", "disable", "backup",
                                     "restore", "reset", "doctor"])
    args = ap.parse_args()

    if args.acao == "status":
        print_doctor()
    elif args.acao == "enable":
        print(enable_autostart()[1])
    elif args.acao == "disable":
        print(disable_autostart()[1])
    elif args.acao == "backup":
        path, err = backup_config("manual")
        print("backup: %s" % (path or err))
    elif args.acao == "restore":
        print(restore_last_backup()[1])
    elif args.acao == "reset":
        reset_failures()
        print("contagem de falhas zerada")
    elif args.acao == "doctor":
        print_doctor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
