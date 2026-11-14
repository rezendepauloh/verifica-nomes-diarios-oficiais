# -*- coding: utf-8 -*-
"""
Suíte de Testes de Segurança (SecOps — SAST/DAST/Hardening):
Valida continuamente:
  a) Varredura de segredos, credenciais e PII em todos os arquivos rastreados pelo Git (`git ls-files`).
  b) Comportamento Fail-Closed (falha imediata quando variáveis/credenciais obrigatórias estão ausentes).
  c) Sintaxe de scripts shell (`bash -n`), políticas de Compose (`127.0.0.1`, `no-new-privileges`),
     proteções WebUI (`.streamlit/config.toml`) e permissões de arquivos críticos (`0600`/`0700`).
  d) Testes negativos de autenticação (HTTP 401/400/429/503), anti-SSRF, anti-Path Traversal,
     anti-Zip-Slip/Zip-Bomb e sanitização contra XSS.
"""
import io
import os
import re
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.config import ROOT_DIR, DB_PATH, get_concurso_slug
from src.security import (
    FailClosedError,
    validate_fail_closed_env,
    validate_runtime_port,
    validate_homelab_deploy_env,
    validate_slug,
    sanitize_filename,
    sanitize_html,
    is_safe_external_url,
    resolve_safe_path,
    safe_extract_zip,
    safe_read_zip_member,
    is_valid_pdf_bytes,
    enforce_secure_file_permissions,
    enforce_secure_dir_permissions,
    AuthRateLimiter,
    is_valid_host_header,
    get_security_headers,
    authenticate_request,
)
from src.editais.pdf_parser import resolve_pdf_path
from src.scrapers.engine import get_local_file_path, safe_download


class TestGitSecretsAndPiiScanner(unittest.TestCase):
    """a) Varredura contínua de segredos e PII em todos os arquivos rastreados pelo Git."""

    FORBIDDEN_PATTERNS = [
        (r"AIza[0-9A-Za-z_-]{35}", "Google/Gemini API Key real"),
        (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Chave privada SSH/TLS"),
        (r"\b(?:3587903|9835298)\b", "CallMeBot API Key pessoal vazada"),
        (r"99247-?1379|92471379|99853-?8804|98538804", "Telefone pessoal vazado"),
        (r"kamila_arteman@hotmail\.com", "E-mail pessoal hardcoded"),
        (
            r"7a35c3f50e2017d2bfb868668ad9cd26e249b41b5b86f0e4cb62e0992e3353d2@group\.calendar\.google\.com",
            "ID privado do Google Calendar hardcoded",
        ),
        (r"diarios-paulo\.shares\.zrok\.io", "Endpoint público zrok hardcoded"),
        (r"diarios\.pk\.local", "Domínio interno local hardcoded"),
        (r"\b192\.168\.0\.8\b", "IP privado do Homelab hardcoded"),
        (r"umbrelos-scripts", "Caminho interno do servidor Homelab hardcoded"),
    ]

    def _list_repo_tracked_files(self):
        import shutil
        if shutil.which("git") and (ROOT_DIR / ".git").exists():
            proc = subprocess.run(
                ["git", "ls-files"],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=True,
            )
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

        # Fallback dentro do container slim (sem binário git): varre a árvore do repositório respeitando .gitignore
        ignored_dirs = {".git", "data", "logs", "uploads", "static", "temp", "__pycache__", ".pytest_cache", "venv", ".venv"}
        ignored_files = {".env"}
        files = []
        for p in ROOT_DIR.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT_DIR)
            if any(part in ignored_dirs for part in rel.parts):
                continue
            if rel.name in ignored_files or rel.name.endswith((".pyc", ".db", ".sqlite", ".log")):
                continue
            files.append(str(rel).replace("\\", "/"))
        return sorted(files)

    def test_no_secrets_or_pii_in_git_tracked_files(self):
        tracked_files = self._list_repo_tracked_files()
        self.assertGreater(len(tracked_files), 10, "Lista de arquivos do repositório inesperadamente vazia.")

        # Nenhum arquivo .env real ou banco .db deve estar rastreado pelo git
        for rel_path in tracked_files:
            self.assertNotEqual(rel_path, ".env", "O arquivo .env NUNCA deve ser rastreado pelo Git.")
            self.assertFalse(rel_path.endswith(".db"), f"Banco SQLite rastreado indevidamente: {rel_path}")

        violations = []
        for rel_path in tracked_files:
            # Ignora este próprio arquivo de teste onde as assinaturas de detecção estão declaradas
            if rel_path.endswith("tests/unit/test_security.py"):
                continue
            full_path = ROOT_DIR / rel_path
            if not full_path.exists() or not full_path.is_file():
                continue
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, label in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, content):
                    violations.append(f"{rel_path}: detectado '{label}' (pattern={pattern})")

        self.assertEqual(
            violations,
            [],
            "Vazamento de segredos/PII detectado em arquivos rastreados pelo Git:\n" + "\n".join(violations),
        )


class TestFailClosedGuards(unittest.TestCase):
    """b) Testes de travas Fail-Closed para variáveis de ambiente, portas e deploy."""

    def test_validate_fail_closed_env_raises_on_missing_or_empty(self):
        with self.assertRaises(FailClosedError):
            validate_fail_closed_env(["VAR_OBRIGATORIA_A", "VAR_OBRIGATORIA_B"], env={"VAR_OBRIGATORIA_A": "ok"})

        with self.assertRaises(FailClosedError):
            validate_fail_closed_env(["VAR_VAZIA"], env={"VAR_VAZIA": "   "})

    def test_validate_fail_closed_env_succeeds_when_all_present(self):
        env = {"PORT": "8504", "TZ": "America/Campo_Grande"}
        res = validate_fail_closed_env(["PORT", "TZ"], env=env)
        self.assertEqual(res["PORT"], "8504")
        self.assertEqual(res["TZ"], "America/Campo_Grande")

    def test_validate_runtime_port_fail_closed(self):
        with self.assertRaises(FailClosedError):
            validate_runtime_port(env={})

        with self.assertRaises(FailClosedError):
            validate_runtime_port(env={"PORT": "abc"})

        with self.assertRaises(FailClosedError):
            validate_runtime_port(env={"PORT": "70000"})

        with self.assertRaises(FailClosedError):
            validate_runtime_port(env={"PORT": "0"})

        self.assertEqual(validate_runtime_port(env={"PORT": "8504"}), 8504)

    def test_validate_homelab_deploy_env_fail_closed(self):
        # Deve falhar se qualquer variável obrigatória do homelab estiver ausente
        with self.assertRaises(FailClosedError):
            validate_homelab_deploy_env(env={"HOMELAB_HOST": "10.0.0.10"})

        # Deve falhar se houver tentativa de injeção de comando no usuário ou host
        with self.assertRaises(FailClosedError):
            validate_homelab_deploy_env(
                env={
                    "HOMELAB_HOST": "10.0.0.10; rm -rf /",
                    "HOMELAB_USER": "deploy",
                    "HOMELAB_PORT": "22",
                    "HOMELAB_DEST_DIR": "/opt/app",
                    "HOMELAB_SSH_KEY": "~/.ssh/id_ed25519",
                    "HOMELAB_PORT_APP": "8093",
                }
            )

        valid_env = {
            "HOMELAB_HOST": "10.0.0.10",
            "HOMELAB_USER": "deploy_user",
            "HOMELAB_PORT": "22",
            "HOMELAB_DEST_DIR": "/opt/verifica-diarios",
            "HOMELAB_SSH_KEY": "~/.ssh/id_ed25519",
            "HOMELAB_PORT_APP": "8093",
        }
        cfg = validate_homelab_deploy_env(env=valid_env)
        self.assertEqual(cfg["HOMELAB_HOST"], "10.0.0.10")


class TestInfrastructureSyntaxAndPermissions(unittest.TestCase):
    """c) Validação de sintaxe de scripts, configurações Docker/Streamlit e permissões de arquivos."""

    def test_bash_script_syntax_is_valid(self):
        script_path = ROOT_DIR / "00-iniciar.sh"
        self.assertTrue(script_path.exists())
        proc = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Erro de sintaxe em 00-iniciar.sh: {proc.stderr}")

        script_text = script_path.read_text(encoding="utf-8")
        self.assertNotIn("chmod -R 777", script_text, "Proibido usar chmod 777 em scripts de deploy.")

    def test_docker_compose_files_enforce_localhost_bind_and_no_new_privileges(self):
        for fname in ("docker-compose.yml", "docker-compose.server.yml"):
            fpath = ROOT_DIR / fname
            self.assertTrue(fpath.exists(), f"{fname} não encontrado")
            content = fpath.read_text(encoding="utf-8")
            self.assertIn("127.0.0.1:${PORT:?", content, f"{fname} deve fazer bind estrito em 127.0.0.1 e exigir PORT (Fail-Closed)")
            self.assertIn("no-new-privileges:true", content, f"{fname} deve conter security_opt no-new-privileges:true")

    def test_streamlit_config_enforces_xsrf_and_cors_and_hides_stacktraces(self):
        cfg_path = ROOT_DIR / ".streamlit" / "config.toml"
        self.assertTrue(cfg_path.exists())
        content = cfg_path.read_text(encoding="utf-8")
        self.assertIn("enableXsrfProtection = true", content)
        self.assertIn("enableCORS = true", content)
        self.assertIn("showErrorDetails = false", content)
        self.assertNotIn("enableXsrfProtection = false", content)

    def test_secure_filesystem_permissions_helper_and_real_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp) / "sec_data"
            tmp_file = tmp_dir / "secret.env"
            enforce_secure_dir_permissions(tmp_dir, mode=0o700)
            tmp_file.write_text("SECRET=1\n", encoding="utf-8")
            enforce_secure_file_permissions(tmp_file, mode=0o600)

            dir_mode = stat.S_IMODE(tmp_dir.stat().st_mode)
            file_mode = stat.S_IMODE(tmp_file.stat().st_mode)
            self.assertEqual(dir_mode, 0o700)
            self.assertEqual(file_mode, 0o600)

        env_path = ROOT_DIR / ".env"
        if env_path.exists():
            enforce_secure_file_permissions(env_path, mode=0o600)
            self.assertEqual(stat.S_IMODE(env_path.stat().st_mode), 0o600)

        if DB_PATH.exists():
            enforce_secure_file_permissions(DB_PATH, mode=0o600)
            self.assertEqual(stat.S_IMODE(DB_PATH.stat().st_mode), 0o600)


class TestNegativeAuthenticationAndWebProtections(unittest.TestCase):
    """d) Testes negativos de autenticação (401, 400, 429, 503) e proteções de parsers/downloads."""

    def test_authentication_negative_401_missing_and_invalid_credentials(self):
        env = {
            "APP_AUTH_REQUIRED": "true",
            "APP_ADMIN_PASSWORD": "StrongPassword!2026",
            "APP_API_TOKEN": "tok_secret_999",
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
        }
        limiter = AuthRateLimiter(max_attempts=5, window_seconds=60, lockout_seconds=120)

        # Sem credenciais -> 401 Unauthorized
        status, body = authenticate_request(
            headers={"Host": "localhost:8504"},
            client_ip="127.0.0.1",
            env=env,
            rate_limiter=limiter,
        )
        self.assertEqual(status, 401)
        self.assertIn("Unauthorized", body["error"])

        # Senha inválida -> 401 Unauthorized
        status2, _ = authenticate_request(
            headers={"Host": "localhost:8504"},
            password="wrong_password",
            client_ip="127.0.0.1",
            env=env,
            rate_limiter=limiter,
        )
        self.assertEqual(status2, 401)

        # Bearer token inválido -> 401 Unauthorized
        status3, _ = authenticate_request(
            headers={"Host": "localhost:8504", "Authorization": "Bearer invalid_token"},
            client_ip="127.0.0.1",
            env=env,
            rate_limiter=limiter,
        )
        self.assertEqual(status3, 401)

        # Credencial válida -> 200 OK
        status_ok, _ = authenticate_request(
            headers={"Host": "localhost:8504", "Authorization": "Bearer tok_secret_999"},
            client_ip="127.0.0.1",
            env=env,
            rate_limiter=limiter,
        )
        self.assertEqual(status_ok, 200)

    def test_authentication_fail_closed_503_when_credentials_missing_in_env(self):
        # APP_AUTH_REQUIRED=true mas sem senha/token configurados -> Fail-Closed (503)
        env = {"APP_AUTH_REQUIRED": "true", "APP_ADMIN_PASSWORD": "", "APP_API_TOKEN": ""}
        status, body = authenticate_request(
            headers={"Host": "localhost"},
            password="any",
            env=env,
        )
        self.assertEqual(status, 503)
        self.assertIn("Fail-Closed", body["error"])

    def test_authentication_brute_force_lockout_429(self):
        env = {
            "APP_AUTH_REQUIRED": "true",
            "APP_ADMIN_PASSWORD": "AdminSecretPassword",
            "ALLOWED_HOSTS": "localhost",
        }
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=120)

        for i in range(3):
            st_code, _ = authenticate_request(
                headers={"Host": "localhost"},
                password="bad",
                client_ip="10.10.10.5",
                env=env,
                rate_limiter=limiter,
            )
            self.assertEqual(st_code, 429 if i == 2 else 401)

        # 4ª tentativa deve retornar 429 Too Many Requests mesmo com a senha correta
        st_locked, _ = authenticate_request(
            headers={"Host": "localhost"},
            password="AdminSecretPassword",
            client_ip="10.10.10.5",
            env=env,
            rate_limiter=limiter,
        )
        self.assertEqual(st_locked, 429)

    def test_host_header_validation_blocks_spoofing_400(self):
        env = {
            "APP_AUTH_REQUIRED": "false",
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
        }
        status, _ = authenticate_request(
            headers={"Host": "evil.attacker.com"},
            env=env,
        )
        self.assertEqual(status, 400)
        self.assertFalse(is_valid_host_header("evil.attacker.com", allowed_hosts=["localhost", "127.0.0.1"]))
        self.assertTrue(is_valid_host_header("127.0.0.1:8504", allowed_hosts=["localhost", "127.0.0.1"]))

    def test_ssrf_protection_blocks_internal_and_non_http_urls(self):
        self.assertFalse(is_safe_external_url("http://127.0.0.1:8080/admin"))
        self.assertFalse(is_safe_external_url("http://localhost/secret"))
        self.assertFalse(is_safe_external_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_external_url("http://192.168.1.1/router"))
        self.assertFalse(is_safe_external_url("file:///etc/passwd"))
        self.assertFalse(is_safe_external_url("ftp://ftp.example.com/file.pdf"))
        self.assertTrue(is_safe_external_url("https://www.cebraspe.org.br/concursos/cgu_26"))

        with self.assertRaises(ValueError):
            safe_download("http://169.254.169.254/latest/meta-data/", pause=0)

    def test_path_traversal_and_zip_slip_zip_bomb_protections(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(ValueError):
                resolve_safe_path(base, "../../etc/passwd")

            # resolve_pdf_path deve bloquear caminhos fora dos diretórios permitidos
            self.assertIsNone(resolve_pdf_path("../../etc/passwd"))
            self.assertIsNone(resolve_pdf_path("/etc/passwd"))

            # Zip-Slip: arquivo com ../ no nome dentro do zip deve levantar ValueError
            zip_slip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_slip_buf, "w") as zf:
                zf.writestr("../../evil.sh", b"echo pwned")
            with self.assertRaises(ValueError):
                safe_extract_zip(zip_slip_buf.getvalue(), base)

            # Zip-Bomb: membro que excede max_member_bytes deve levantar ValueError
            zip_bomb_buf = io.BytesIO()
            with zipfile.ZipFile(zip_bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("word/document.xml", b"A" * 2048)
            with self.assertRaises(ValueError):
                safe_read_zip_member(zip_bomb_buf.getvalue(), "word/document.xml", max_bytes=512)

    def test_slug_and_html_sanitization_and_gemini_header(self):
        self.assertEqual(sanitize_filename("../../meu edital<script>.pdf", default_ext=".pdf"), "meu_edital_script.pdf")
        self.assertNotIn("..", get_concurso_slug("Teste", 2026, "https://site.com/concursos/..%2F..%2Fetc"))
        with self.assertRaises(ValueError):
            get_local_file_path("../etc", "https://site.com/a.pdf")

        escaped = sanitize_html('<img src=x onerror="alert(1)">')
        self.assertNotIn("<img", escaped)
        self.assertIn("&lt;img", escaped)

        headers = get_security_headers()
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")

        self.assertTrue(is_valid_pdf_bytes(b"%PDF-1.7\n..."))
        self.assertFalse(is_valid_pdf_bytes(b"<html>not a pdf</html>"))

        # Verifica que Gemini API envia a chave via header x-goog-api-key e nunca na URL
        dummy_test_key = "fake_gemini_test_key_12345"
        with patch("src.editais.extractor_ai.GEMINI_API_KEY", dummy_test_key), \
             patch("src.editais.extractor_ai.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}
            mock_post.return_value = mock_resp
            from src.editais.extractor_ai import call_gemini_json
            res = call_gemini_json("teste")
            self.assertEqual(res, {"ok": True})
            called_url = mock_post.call_args[0][0]
            called_headers = mock_post.call_args[1]["headers"]
            self.assertNotIn("key=", called_url)
            self.assertEqual(called_headers.get("x-goog-api-key"), dummy_test_key)


if __name__ == "__main__":
    unittest.main()
