# -*- coding: utf-8 -*-
"""
Módulo Central de Segurança Ofensiva/Defensiva (SecOps & Hardening).
Fornece:
- Travas 'Fail-Closed' para variáveis de ambiente, portas, túneis e deploy
- Whitelists Regex estritas (slugs, hosts, usuários, portas, caminhos POSIX e nomes de arquivo)
- Proteção contra SSRF, Path Traversal, Zip-Slip, Zip-Bomb e DoS por tamanho de payload
- Escapamento HTML (anti-XSS) e validação de assinatura mágica de PDFs (%PDF-)
- Autenticação com comparação em tempo constante (hmac.compare_digest), validação de Host Header,
  Rate Limiting e bloqueio contra força bruta (Brute-Force Lockout)
- Imposição automática de permissões restritivas de sistema de arquivos (chmod 600 / 700)
"""
from __future__ import annotations

import hmac
import html
import io
import ipaddress
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

# ==============================================================================
# 1. CONSTANTES E WHITELISTS REGEX ESTRITAS
# ==============================================================================

MAX_DOWNLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_DOWNLOAD_BYTES = MAX_DOWNLOAD_SIZE_BYTES
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_ZIP_UNCOMPRESSED_BYTES = MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES
MAX_DOCX_XML_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_ZIP_ENTRIES = 2000
MAX_COMPRESSION_RATIO = 100.0

REGEX_SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REGEX_SAFE_HOST = re.compile(r"^[a-zA-Z0-9._-]+$")
REGEX_SAFE_USER = re.compile(r"^[a-zA-Z0-9_-]+$")
REGEX_SAFE_PORT = re.compile(r"^[0-9]{2,5}$")
REGEX_SAFE_POSIX_PATH = re.compile(r"^/[a-zA-Z0-9._/-]+$")
REGEX_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")
REGEX_SHELL_METACHARS = re.compile(r"[;&|`$><\n\r\x00\\]")

PLACEHOLDER_PATTERNS = (
    "changeme",
    "seu dominio",
    "seu_ip_homelab",
    "seu_usuario_ssh",
    "sua_chave",
    "todo",
    "example",
)


class FailClosedError(RuntimeError):
    """Exceção lançada quando uma verificação de segurança 'Fail-Closed' falha."""


# ==============================================================================
# 2. TRAVAS FAIL-CLOSED DE AMBIENTE E INFRAESTRUTURA
# ==============================================================================

def validate_fail_closed_env(
    required_vars: Iterable[str],
    env: Optional[Mapping[str, str]] = None,
    reject_placeholders: bool = True,
) -> Dict[str, str]:
    """
    Garante que todas as variáveis de ambiente essenciais estejam presentes e preenchidas.
    Lança FailClosedError imediatamente caso qualquer variável esteja ausente, vazia ou com placeholder.
    """
    source_env = env if env is not None else os.environ
    validated: Dict[str, str] = {}

    for var_name in required_vars:
        raw_val = source_env.get(var_name, "")
        clean_val = str(raw_val).strip().strip('"').strip("'") if raw_val is not None else ""
        if not clean_val:
            raise FailClosedError(
                f"Fail-Closed: Variável de ambiente obrigatória '{var_name}' está ausente ou vazia."
            )
        if reject_placeholders:
            lower_val = clean_val.lower()
            if any(p in lower_val for p in PLACEHOLDER_PATTERNS):
                raise FailClosedError(
                    f"Fail-Closed: Variável de ambiente '{var_name}' contém valor de placeholder não configurado."
                )
        validated[var_name] = clean_val

    return validated


def validate_runtime_port(port_val: Optional[str | int] = None, env: Optional[Mapping[str, str]] = None) -> int:
    """Valida que a porta de execução é estritamente numérica e está na faixa 1..65535."""
    if port_val is None:
        source_env = env if env is not None else os.environ
        port_val = source_env.get("PORT", "")
    port_str = str(port_val).strip().strip('"').strip("'")
    if not port_str or not REGEX_SAFE_PORT.match(port_str):
        raise FailClosedError(f"Fail-Closed: Variável PORT inválida ou ausente ('{port_str}').")
    port_num = int(port_str)
    if not (1 <= port_num <= 65535):
        raise FailClosedError(f"Fail-Closed: Porta fora do intervalo permitido (1-65535): {port_num}")
    return port_num


def validate_homelab_deploy_env(env: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """
    Valida estritamente todas as variáveis necessárias para deploy remoto via SSH/Rsync.
    Impede execução com defaults implícitos e bloqueia injeção de comandos shell.
    """
    required = [
        "HOMELAB_HOST",
        "HOMELAB_USER",
        "HOMELAB_PORT",
        "HOMELAB_DEST_DIR",
        "HOMELAB_PORT_APP",
    ]
    vals = validate_fail_closed_env(required, env=env, reject_placeholders=True)

    if REGEX_SHELL_METACHARS.search(vals["HOMELAB_HOST"]) or not REGEX_SAFE_HOST.match(vals["HOMELAB_HOST"]):
        raise FailClosedError("Fail-Closed: HOMELAB_HOST contém caracteres inválidos.")

    if REGEX_SHELL_METACHARS.search(vals["HOMELAB_USER"]) or not REGEX_SAFE_USER.match(vals["HOMELAB_USER"]):
        raise FailClosedError("Fail-Closed: HOMELAB_USER contém caracteres inválidos.")

    validate_runtime_port(vals["HOMELAB_PORT"])
    validate_runtime_port(vals["HOMELAB_PORT_APP"])

    dest_dir = vals["HOMELAB_DEST_DIR"]
    if (
        REGEX_SHELL_METACHARS.search(dest_dir)
        or not REGEX_SAFE_POSIX_PATH.match(dest_dir)
        or ".." in Path(dest_dir).parts
        or dest_dir.strip("/") == ""
    ):
        raise FailClosedError("Fail-Closed: HOMELAB_DEST_DIR inválido ou inseguro.")

    return vals


# ==============================================================================
# 3. VALIDAÇÃO DE INPUTS, SLUGS, NOMES DE ARQUIVOS E ANTI-XSS
# ==============================================================================

def validate_slug(raw_slug: str, fallback: Optional[str] = None) -> str:
    """
    Higieniza e valida um identificador (slug) contra Path Traversal e caracteres fora da whitelist.
    Garante que o resultado respeite estritamente ^[a-z0-9][a-z0-9_-]{0,63}$.
    Se `fallback` for None, lança ValueError quando o slug contiver Path Traversal ou for inválido.
    """
    if not raw_slug or not str(raw_slug).strip():
        if fallback is not None:
            return fallback
        raise ValueError("Slug vazio ou ausente.")

    raw_str = str(raw_slug).strip()
    if ".." in raw_str or "/" in raw_str or "\\" in raw_str or "\x00" in raw_str:
        if fallback is not None:
            raw_str = raw_str.replace("..", "").replace("/", "_").replace("\\", "_").replace("\x00", "")
        else:
            raise ValueError(f"Tentativa de Path Traversal bloqueada no slug: {raw_slug}")

    normalized = (
        unicodedata.normalize("NFKD", raw_str)
        .encode("ASCII", "ignore")
        .decode("utf-8")
        .strip()
        .lower()
    )

    cleaned = re.sub(r"[^a-z0-9_-]", "_", normalized)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    if not cleaned or not re.match(r"^[a-z0-9]", cleaned):
        if fallback is not None:
            return fallback
        raise ValueError(f"Slug inválido após sanitização: {raw_slug}")
    cleaned = cleaned[:64]
    if not REGEX_SAFE_SLUG.match(cleaned):
        if fallback is not None:
            return fallback
        raise ValueError(f"Slug fora do padrão seguro: {raw_slug}")
    return cleaned


def sanitize_filename(
    filename: str,
    default_name: str = "documento.pdf",
    default_ext: Optional[str] = None,
    max_len: int = 120,
) -> str:
    """
    Sanitiza nomes de arquivos vindos de uploads de usuários ou cabeçalhos/URLs externas.
    Remove componentes de diretório (os.path.basename), bytes nulos, '..' e caracteres fora da whitelist.
    """
    if default_ext:
        ext_norm = default_ext if default_ext.startswith(".") else f".{default_ext}"
        default_name = f"documento{ext_norm}"

    if not filename:
        return default_name
    raw_base = os.path.basename(str(filename).replace("\\", "/").replace("\x00", "")).strip()
    if not raw_base or raw_base in (".", ".."):
        return default_name

    normalized = (
        unicodedata.normalize("NFKD", raw_base)
        .encode("ASCII", "ignore")
        .decode("utf-8")
    )
    name_part, ext_part = os.path.splitext(normalized)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name_part)
    safe_name = re.sub(r"_+", "_", safe_name).strip("._-")
    if not safe_name:
        safe_name = "documento"

    safe_ext = re.sub(r"[^a-zA-Z0-9.]", "", ext_part.lower())
    if not safe_ext.startswith(".") or len(safe_ext) > 10:
        safe_ext = default_ext if (default_ext and default_ext.startswith(".")) else (os.path.splitext(default_name)[1] or ".pdf")

    final_name = f"{safe_name[:max_len]}{safe_ext}"
    if ".." in final_name or not REGEX_SAFE_FILENAME.match(final_name):
        return default_name
    return final_name


def sanitize_html(value: Any) -> str:
    """Escapa caracteres especiais HTML (&, <, >, \", ') para prevenir Stored/Reflected XSS."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


# ==============================================================================
# 4. PROTEÇÃO CONTRA SSRF, PATH TRAVERSAL, ZIP-BOMB E DOS
# ==============================================================================

def is_safe_external_url(url: str, allow_private: bool = False) -> bool:
    """
    Valida se uma URL externa é segura para requisição HTTP/HTTPS ou redirecionamento/link:
    - Exige esquema http ou https
    - Rejeita credenciais embutidas, caracteres de controle e espaços
    - Bloqueia localhost, loopback (127.0.0.0/8, ::1), link-local/metadata (169.254.0.0/16)
      e redes privadas RFC1918 (a menos que allow_private=True).
    """
    if not url or not isinstance(url, str):
        return False
    clean_url = url.strip()
    if any(ord(c) < 32 for c in clean_url):
        return False

    try:
        parsed = urllib.parse.urlsplit(clean_url)
    except Exception:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    if parsed.username or parsed.password:
        return False

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return False

    if not allow_private:
        if hostname in ("localhost", "0.0.0.0") or hostname.endswith((".local", ".internal", ".localhost")):
            return False

    try:
        ip_obj = ipaddress.ip_address(hostname)
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_unspecified:
            return False
        if not allow_private and (ip_obj.is_private or ip_obj.is_reserved):
            return False
    except ValueError:
        # Hostname DNS; valida formato seguro de domínio
        if not REGEX_SAFE_HOST.match(hostname) or ".." in hostname:
            return False

    return True


def resolve_safe_path(
    base_or_path: str | Path,
    *subpaths: str | Path,
    allowed_roots: Optional[Iterable[Path]] = None,
) -> Path:
    """
    Resolve um caminho de arquivo garantindo que o destino real (após resolução de symlinks e '..')
    esteja estritamente contido dentro do diretório base ou de `allowed_roots`.
    Lança ValueError caso detecte tentativa de Path Traversal.
    """
    if not base_or_path:
        raise ValueError("Caminho base inválido ou vazio.")

    if subpaths:
        base_root = Path(base_or_path).resolve(strict=False)
        joined = Path(base_or_path)
        for sp in subpaths:
            sp_str = str(sp)
            if "\x00" in sp_str:
                raise ValueError("Byte nulo detectado no caminho.")
            joined = joined / sp_str
        candidate = joined.resolve(strict=False)
        roots = [base_root] if allowed_roots is None else [Path(r).resolve(strict=False) for r in allowed_roots]
    else:
        raw_str = str(base_or_path).strip()
        if "\x00" in raw_str:
            raise ValueError("Byte nulo detectado no caminho.")
        candidate = Path(raw_str).resolve(strict=False)
        roots = [Path(r).resolve(strict=False) for r in (allowed_roots or [])]

    for root in roots:
        if candidate.is_relative_to(root):
            return candidate

    raise ValueError(f"Path Traversal bloqueado: '{candidate}' está fora da raiz permitida.")


def safe_extract_zip(
    zip_source: Union[zipfile.ZipFile, bytes, bytearray, io.BytesIO],
    target_dir: Path | str,
    max_total_size: int = MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES,
    max_total_bytes: Optional[int] = None,
    max_entries: int = MAX_ZIP_ENTRIES,
    max_ratio: float = MAX_COMPRESSION_RATIO,
) -> List[Path]:
    """
    Extrai um arquivo ZIP com validação estrita contra:
    - Zip-Slip (Path Traversal via nomes de membros contendo '../' ou caminhos absolutos)
    - Zip-Bomb (limite de entradas, tamanho total descompactado e taxa de compressão)
    """
    if max_total_bytes is not None:
        max_total_size = max_total_bytes

    if isinstance(zip_source, (bytes, bytearray)):
        with zipfile.ZipFile(io.BytesIO(zip_source)) as zf:
            return safe_extract_zip(
                zf,
                target_dir=target_dir,
                max_total_size=max_total_size,
                max_entries=max_entries,
                max_ratio=max_ratio,
            )
    elif isinstance(zip_source, io.BytesIO):
        with zipfile.ZipFile(zip_source) as zf:
            return safe_extract_zip(
                zf,
                target_dir=target_dir,
                max_total_size=max_total_size,
                max_entries=max_entries,
                max_ratio=max_ratio,
            )

    zip_file = zip_source
    dest_root = Path(target_dir).resolve(strict=False)
    dest_root.mkdir(parents=True, exist_ok=True)

    infos = zip_file.infolist()
    if len(infos) > max_entries:
        raise ValueError(f"Zip-Bomb bloqueado: número de entradas ({len(infos)}) excede o limite ({max_entries}).")

    total_uncompressed = 0
    extracted_paths: List[Path] = []

    for info in infos:
        member_name = info.filename.replace("\\", "/")
        if (
            not member_name
            or member_name.startswith("/")
            or ".." in Path(member_name).parts
            or "\x00" in member_name
        ):
            raise ValueError(f"Zip-Slip bloqueado: caminho de entrada suspeito no arquivo ZIP ('{info.filename}').")

        # Bloqueia symlinks em arquivos ZIP (S_IFLNK = 0o120000)
        unix_mode = info.external_attr >> 16
        if (unix_mode & 0o170000) == 0o120000:
            raise ValueError(f"Zip-Slip bloqueado: symlink detectado no arquivo ZIP ('{info.filename}').")

        total_uncompressed += max(0, info.file_size)
        if total_uncompressed > max_total_size:
            raise ValueError(
                f"Zip-Bomb bloqueado: tamanho descompactado acumulado ({total_uncompressed} bytes) "
                f"excede o limite de segurança ({max_total_size} bytes)."
            )

        if info.compress_size > 0 and info.file_size > 1024 * 1024:
            ratio = info.file_size / info.compress_size
            if ratio > max_ratio:
                raise ValueError(
                    f"Zip-Bomb bloqueado: taxa de compressão anômala ({ratio:.1f}x) em '{info.filename}'."
                )

        target_path = (dest_root / member_name).resolve(strict=False)
        if not target_path.is_relative_to(dest_root):
            raise ValueError(f"Zip-Slip bloqueado: destino fora do diretório raiz ('{info.filename}').")

        if info.is_dir() or member_name.endswith("/"):
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with zip_file.open(info, "r") as src, open(target_path, "wb") as dst:
            written = 0
            while True:
                chunk = src.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > info.file_size + 1024 or written > max_total_size:
                    raise ValueError(f"Zip-Bomb bloqueado durante leitura de stream em '{info.filename}'.")
                dst.write(chunk)
        extracted_paths.append(target_path)

    return extracted_paths


def safe_read_zip_member(
    zip_source: Union[zipfile.ZipFile, bytes, bytearray, io.BytesIO],
    member_name: str,
    max_size: int = MAX_DOCX_XML_BYTES,
    max_bytes: Optional[int] = None,
) -> bytes:
    """Lê um membro interno de um arquivo ZIP (ex: word/document.xml de DOCX) prevenindo Zip-Bomb."""
    if max_bytes is not None:
        max_size = max_bytes

    if isinstance(zip_source, (bytes, bytearray)):
        with zipfile.ZipFile(io.BytesIO(zip_source)) as zf:
            return safe_read_zip_member(zf, member_name=member_name, max_size=max_size)
    elif isinstance(zip_source, io.BytesIO):
        with zipfile.ZipFile(zip_source) as zf:
            return safe_read_zip_member(zf, member_name=member_name, max_size=max_size)

    zip_file = zip_source
    info = zip_file.getinfo(member_name)
    if info.file_size > max_size:
        raise ValueError(
            f"Zip-Bomb bloqueado: membro '{member_name}' declara {info.file_size} bytes (máx: {max_size})."
        )
    if info.compress_size > 0 and info.file_size > 1024 * 1024:
        if (info.file_size / info.compress_size) > MAX_COMPRESSION_RATIO:
            raise ValueError(f"Zip-Bomb bloqueado: razão de compressão excessiva em '{member_name}'.")

    with zip_file.open(info, "r") as fp:
        data = fp.read(max_size + 1)
        if len(data) > max_size:
            raise ValueError(f"Zip-Bomb bloqueado: tamanho real de '{member_name}' excede {max_size} bytes.")
        return data


def is_valid_pdf_bytes(data: bytes, max_size: int = MAX_DOWNLOAD_SIZE_BYTES) -> bool:
    """Verifica se o payload binário possui tamanho seguro e assinatura mágica '%PDF-'."""
    if not data or not isinstance(data, (bytes, bytearray, memoryview)):
        return False
    raw = bytes(data[:1024])
    if len(data) > max_size:
        return False
    return b"%PDF-" in raw


# ==============================================================================
# 5. IMPOSIÇÃO DE PERMISSÕES DE ARQUIVOS E DIRETÓRIOS (CHMOD 600 / 700)
# ==============================================================================

def enforce_secure_file_permissions(file_path: Path | str, mode: int = 0o600) -> bool:
    """Garante permissões restritas (padrão 0600) em arquivos sensíveis (.env, SQLite DB)."""
    p = Path(file_path)
    if not p.exists() or os.name == "nt":
        return False
    try:
        current_mode = p.stat().st_mode & 0o777
        if current_mode != mode:
            os.chmod(p, mode)
        return True
    except Exception:
        return False


def enforce_secure_dir_permissions(dir_path: Path | str, mode: int = 0o700) -> bool:
    """Garante a existência e permissões restritas (padrão 0700) em diretórios de dados sensíveis."""
    p = Path(dir_path)
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        return False
    try:
        current_mode = p.stat().st_mode & 0o777
        if current_mode != mode:
            os.chmod(p, mode)
        return True
    except Exception:
        return False


# ==============================================================================
# 6. AUTENTICAÇÃO, HOST HEADER, RATE LIMITING E BRUTE-FORCE PROTECTION
# ==============================================================================

class AuthRateLimiter:
    """
    Controlador thread-safe de Rate Limiting e bloqueio contra força bruta (Brute-Force Lockout).
    Bloqueia o identificador do cliente após `max_attempts` falhas dentro de `window_seconds`.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, lockout_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._lock = threading.Lock()
        self._failures: Dict[str, List[float]] = {}
        self._locked_until: Dict[str, float] = {}

    def is_locked(self, client_id: str, now: Optional[float] = None) -> bool:
        ts = now if now is not None else time.time()
        with self._lock:
            unlock_at = self._locked_until.get(client_id, 0.0)
            if unlock_at > ts:
                return True
            if client_id in self._locked_until:
                del self._locked_until[client_id]
            return False

    def record_failure(self, client_id: str, now: Optional[float] = None) -> bool:
        """Registra uma falha de autenticação e retorna True se o cliente entrou em lockout."""
        ts = now if now is not None else time.time()
        with self._lock:
            cutoff = ts - self.window_seconds
            attempts = [t for t in self._failures.get(client_id, []) if t >= cutoff]
            attempts.append(ts)
            self._failures[client_id] = attempts
            if len(attempts) >= self.max_attempts:
                self._locked_until[client_id] = ts + self.lockout_seconds
                return True
            return False

    def reset(self, client_id: str) -> None:
        with self._lock:
            self._failures.pop(client_id, None)
            self._locked_until.pop(client_id, None)


GLOBAL_AUTH_RATE_LIMITER = AuthRateLimiter()


def is_valid_host_header(
    host_header: str,
    env: Optional[Mapping[str, str]] = None,
    allowed_hosts: Optional[Iterable[str]] = None,
) -> bool:
    """
    Valida o cabeçalho HTTP Host contra ataques de Host Header Injection / DNS Rebinding.
    """
    if not host_header or not isinstance(host_header, str):
        return False
    clean_host = host_header.strip().lower()
    if "/" in clean_host or "\\" in clean_host or "@" in clean_host or " " in clean_host:
        return False

    # Separa hostname e porta opcional
    if clean_host.startswith("["):
        # IPv6 literal ex: [::1]:8504
        if "]" not in clean_host:
            return False
        host_part, _, port_part = clean_host[1:].partition("]")
        if port_part.startswith(":"):
            port_part = port_part[1:]
        if port_part and not REGEX_SAFE_PORT.match(port_part):
            return False
    else:
        host_part, _, port_part = clean_host.partition(":")
        if port_part and not REGEX_SAFE_PORT.match(port_part):
            return False

    if allowed_hosts is not None:
        allowed_set = {str(h).strip().lower() for h in allowed_hosts if str(h).strip()}
    else:
        source_env = env if env is not None else os.environ
        allowed_raw = source_env.get("ALLOWED_HOSTS", "localhost,127.0.0.1,::1,verifica-diarios-app")
        allowed_set = {h.strip().lower() for h in allowed_raw.split(",") if h.strip()}

        for url_env in ("APP_LOCAL_URL", "APP_PUBLIC_URL"):
            u_val = source_env.get(url_env, "").strip()
            if u_val:
                parsed = urllib.parse.urlsplit(u_val)
                if parsed.hostname:
                    allowed_set.add(parsed.hostname.lower())

    return host_part in allowed_set


def get_security_headers() -> Dict[str, str]:
    """Retorna os cabeçalhos HTTP defensivos padrão para a WebUI."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'self';"
        ),
    }


class AuthResponse(dict):
    """Dicionário de resultado de autenticação que também suporta desempacotamento (status_code, body)."""

    def __iter__(self):
        yield self["status_code"]
        yield self


def authenticate_request(
    auth_header: Optional[str] = None,
    password_input: Optional[str] = None,
    host_header: Optional[str] = None,
    client_id: str = "default",
    env: Optional[Mapping[str, str]] = None,
    rate_limiter: Optional[AuthRateLimiter] = None,
    headers: Optional[Mapping[str, str]] = None,
    password: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> AuthResponse:
    """
    Valida uma requisição de autenticação (via Bearer Token ou senha de painel) com:
    1. Validação de Host Header (HTTP 400 se inválido)
    2. Verificação de Lockout / Rate Limit (HTTP 429 se bloqueado por brute-force)
    3. Trava Fail-Closed: se nenhuma credencial (APP_ADMIN_PASSWORD / APP_API_TOKEN) estiver
       configurada no ambiente, recusa o acesso (HTTP 503 / FailClosedError)
    4. Comparação em tempo constante (hmac.compare_digest) retornando HTTP 401 para credenciais
       ausentes ou inválidas e HTTP 200 quando autenticado com sucesso.
    """
    limiter = rate_limiter if rate_limiter is not None else GLOBAL_AUTH_RATE_LIMITER
    source_env = env if env is not None else os.environ

    if headers:
        for k, v in headers.items():
            k_low = k.lower()
            if k_low == "host" and host_header is None:
                host_header = v
            elif k_low == "authorization" and auth_header is None:
                auth_header = v

    if password is not None and password_input is None:
        password_input = password
    if client_ip is not None and client_id == "default":
        client_id = client_ip

    if host_header is not None and not is_valid_host_header(host_header, env=source_env):
        return AuthResponse(
            authenticated=False,
            status_code=400,
            error="Bad Request: Host header não autorizado.",
        )

    if limiter.is_locked(client_id):
        return AuthResponse(
            authenticated=False,
            status_code=429,
            error="Too Many Requests: Muitas tentativas inválidas. Aguarde o desbloqueio.",
        )

    expected_password = source_env.get("APP_ADMIN_PASSWORD", "").strip()
    expected_token = source_env.get("APP_API_TOKEN", "").strip()

    # Fail-Closed: nunca autentica se os segredos de referência estiverem vazios
    if not expected_password and not expected_token:
        return AuthResponse(
            authenticated=False,
            status_code=503,
            error="Fail-Closed: Segredos de autenticação (APP_ADMIN_PASSWORD / APP_API_TOKEN) não configurados.",
        )

    candidate = ""
    if auth_header and isinstance(auth_header, str):
        parts = auth_header.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            candidate = parts[1].strip()
        else:
            limiter.record_failure(client_id)
            return AuthResponse(
                authenticated=False,
                status_code=401,
                error="Unauthorized: Cabeçalho Authorization malformado.",
            )
    elif password_input is not None:
        candidate = str(password_input).strip()

    if not candidate:
        limiter.record_failure(client_id)
        return AuthResponse(
            authenticated=False,
            status_code=401,
            error="Unauthorized: Credenciais de autenticação não fornecidas.",
        )

    matched = False
    if expected_token and hmac.compare_digest(candidate.encode("utf-8"), expected_token.encode("utf-8")):
        matched = True
    if expected_password and hmac.compare_digest(candidate.encode("utf-8"), expected_password.encode("utf-8")):
        matched = True

    if not matched:
        locked = limiter.record_failure(client_id)
        return AuthResponse(
            authenticated=False,
            status_code=429 if locked else 401,
            error=(
                "Too Many Requests: Cliente bloqueado por excesso de tentativas."
                if locked
                else "Unauthorized: Credenciais inválidas."
            ),
        )

    limiter.reset(client_id)
    return AuthResponse(
        authenticated=True,
        status_code=200,
        error=None,
    )


def enforce_streamlit_auth() -> None:
    """
    Aplica trava de autenticação Fail-Closed no painel Streamlit quando APP_AUTH_REQUIRED=true.
    Se APP_AUTH_REQUIRED=true e APP_ADMIN_PASSWORD/APP_API_TOKEN estiverem vazios, bloqueia o painel
    imediatamente (Fail-Closed).
    """
    auth_required = os.getenv("APP_AUTH_REQUIRED", "false").strip().lower() in ("1", "true", "yes", "on")
    if not auth_required:
        return

    import streamlit as st

    expected_password = os.getenv("APP_ADMIN_PASSWORD", "").strip()
    expected_token = os.getenv("APP_API_TOKEN", "").strip()
    if not expected_password and not expected_token:
        st.error(
            "🚨 **Bloqueio de Segurança (Fail-Closed)**: `APP_AUTH_REQUIRED=true`, porém "
            "`APP_ADMIN_PASSWORD` / `APP_API_TOKEN` não foram definidos no arquivo `.env`."
        )
        st.stop()
        return

    if st.session_state.get("sec_authenticated") is True:
        return

    st.markdown("### 🔒 Acesso Restrito — Verifica Diários & Central de Editais")
    st.caption("Informe a credencial de acesso configurada no ambiente (`.env`) para acessar o painel.")

    with st.form("sec_login_form"):
        pwd = st.text_input("Senha / Token de Acesso", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")

    if submitted:
        res = authenticate_request(password_input=pwd, client_id="streamlit_webui")
        if res["authenticated"]:
            st.session_state["sec_authenticated"] = True
            st.rerun()
        else:
            st.error(f"❌ {res['error']} (HTTP {res['status_code']})")

    st.stop()
