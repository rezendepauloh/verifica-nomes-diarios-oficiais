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
UPLOADS_DIR = ROOT_DIR / "uploads"
EDITAIS_DIR = UPLOADS_DIR / "editais"
DB_PATH = DATA_DIR / "results.db"
ENV_FILE_PATH = ROOT_DIR / ".env"

# Aplica permissões restritas (0600) no arquivo .env e banco se existirem
try:
    from src.security import enforce_secure_file_permissions, enforce_secure_dir_permissions, validate_slug
    if ENV_FILE_PATH.exists():
        enforce_secure_file_permissions(ENV_FILE_PATH)
    if DATA_DIR.exists():
        enforce_secure_dir_permissions(DATA_DIR)
    if DB_PATH.exists():
        enforce_secure_file_permissions(DB_PATH)
except Exception:
    validate_slug = None  # fallback defensivo

PORT = os.getenv("PORT", "")
TZ_NAME = os.getenv("TZ", "America/Campo_Grande").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

def get_concurso_slug(titulo: str = "", ano: int = 2026, link_oficial: str = "") -> str:
    """
    Gera ou extrai o slug padronizado da pasta do concurso com whitelist estrita anti-Path Traversal.
    Prioridade:
    1. Slug oficial extraído da URL (ex: cebraspe.org.br/.../cgu_26_affc -> 'cgu_26_affc')
    2. Fallback: '{titulo_limpo}_{ano}' (ex: 'cgu_2026', 'mpe_ms_2026')
    """
    import re
    if link_oficial:
        # Se for Cebraspe
        m_cebraspe = re.search(r'/concursos/([^/?#]+)', link_oficial, re.IGNORECASE)
        if m_cebraspe:
            cand = re.sub(r'[^a-z0-9_-]', '_', m_cebraspe.group(1).strip().lower()).strip('._-')
            if len(cand) >= 3 and ".." not in cand:
                return cand[:80]
        # Se tiver outro padrão com slug no path
        path_parts = [p for p in link_oficial.split('?')[0].split('/') if p]
        if path_parts and len(path_parts[-1]) >= 4 and not path_parts[-1].endswith('.html'):
            slug_cand = re.sub(r'[^a-z0-9_-]', '_', path_parts[-1].lower()).strip('._-')
            if len(slug_cand) >= 3 and ".." not in slug_cand:
                return slug_cand[:80]

    # Fallback: nome_ano (com normalização de acentos para ASCII)
    import unicodedata
    raw_tit = unicodedata.normalize('NFKD', titulo or "concurso").encode('ASCII', 'ignore').decode('utf-8')
    t_clean = re.sub(r'[^a-z0-9]', '_', raw_tit.strip().lower())
    t_clean = re.sub(r'_+', '_', t_clean).strip('_') or "concurso"
    safe_ano = int(ano) if str(ano).isdigit() else 2026
    return f"{t_clean[:60]}_{safe_ano}"

def get_edital_folder(titulo: str = "", ano: int = 2026, link_oficial: str = "") -> Path:
    """Retorna o diretório específico do concurso dentro de uploads/editais/ criando-o se necessário."""
    slug = get_concurso_slug(titulo=titulo, ano=ano, link_oficial=link_oficial)
    folder = EDITAIS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    return folder


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
