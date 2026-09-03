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

# Caminhos base
ROOT_DIR = Path(__file__).parent.parent
LOGS_DIR = ROOT_DIR / "logs"
ASSETS_DIR = ROOT_DIR / "assets"
DB_PATH = ROOT_DIR / "results.db"

PORT = os.getenv("PORT", "")

def get_monitored_names():
    """Retorna lista de nomes monitorados do .env."""
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
