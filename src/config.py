# -*- coding: utf-8 -*-
"""
Configurações centrais, carregamento de variáveis de ambiente e helpers de lock/processos.
"""
import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# Se estiver no Linux/Debian e houver o bundle do sistema com CAs locais atualizadas,
# direciona o requests e OpenSSL para usá-lo em vez do certifi padrão isolado
_sys_ca_bundle = "/etc/ssl/certs/ca-certificates.crt"
if os.path.exists(_sys_ca_bundle):
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _sys_ca_bundle)
    os.environ.setdefault("SSL_CERT_FILE", _sys_ca_bundle)

# Caminhos base
ROOT_DIR = Path(__file__).parent.parent
LOGS_DIR = ROOT_DIR / "logs"
ASSETS_DIR = ROOT_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "results.db"

PORT = os.getenv("PORT", "")
TZ_NAME = os.getenv("TZ", "America/Campo_Grande").strip()

def get_system_timezone():
    """Retorna o objeto ZoneInfo configurado para o fuso horário da aplicação."""
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(os.getenv("TZ", "America/Campo_Grande").strip())
    except Exception:
        return ZoneInfo("America/Campo_Grande")

def format_br_datetime(val, is_utc: bool = True) -> str:
    """
    Formata datas ISO, timestamps ou strings para o padrão brasileiro DD/MM/AAAA HH:MM:SS.
    Por padrão (is_utc=True), converte datas registradas em UTC (padrão SQLite CURRENT_TIMESTAMP)
    para o fuso horário local configurado (ex: America/Campo_Grande, UTC-4).
    Caso is_utc=False, mantém o horário local direto (usado para próximos agendamentos pré-calculados).
    """
    if not val or str(val).strip().lower() in ["none", "nan", ""]:
        return "-"
    try:
        from datetime import datetime, timezone
        import pandas as pd
        val_str = str(val).strip()
        # Tratamento seguro caso venha com microssegundos ou separador T
        if "T" in val_str:
            dt = datetime.fromisoformat(val_str)
        else:
            dt = datetime.strptime(val_str[:19], "%Y-%m-%d %H:%M:%S")

        target_tz = get_system_timezone()
        if is_utc:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_local = dt.astimezone(target_tz)
        else:
            if dt.tzinfo is not None:
                dt_local = dt.astimezone(target_tz)
            else:
                dt_local = dt

        return dt_local.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(val)


def get_monitored_names():
    """Retorna lista de nomes monitorados ativos do SQLite, com fallback para o .env."""
    try:
        from src.database.db import get_active_monitored_names
        names = get_active_monitored_names()
        if names:
            return names
    except Exception:
        pass

    names_env = os.getenv("MONITOR_NAMES", "")
    return [name.strip() for name in names_env.split(",") if name.strip()]


def get_lock_file() -> Path:
    """Retorna o caminho do arquivo de lock da varredura."""
    return Path(tempfile.gettempdir()) / "diarios_oficiais_scan.lock"

def check_scan_running() -> bool:
    """Verifica se a varredura está rodando de forma ativa (compatível com Linux, Docker e Windows)."""
    lock_file = get_lock_file()
    if not lock_file.exists():
        return False
        
    try:
        with open(lock_file, "r") as f:
            pid = int(f.read().strip())
        
        # POSIX (Linux / Docker / macOS)
        if hasattr(os, "kill"):
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
        
        # Windows
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                kernel32.CloseHandle(handle)
                return exit_code.value == 259  # STILL_ACTIVE
            kernel32.CloseHandle(handle)
    except Exception:
        pass
    return False

def read_last_log_lines(n: int = 25) -> str:
    """Lê as últimas N linhas do arquivo de log."""
    log_path = LOGS_DIR / "app.log"
    if not log_path.exists():
        return "Nenhum log gerado ainda. Aguardando início..."
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except Exception as e:
        return f"Erro ao ler arquivo de log: {e}"
