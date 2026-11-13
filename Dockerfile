FROM python:3.12-slim

# Evita criação de arquivos .pyc e força flush imediato do stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Instala dependências de compilação essenciais, certificados e utilitários
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Se existirem certificados adicionais (como proxy/firewall corporativo), instala no sistema e Python
COPY certs* /tmp/certs/
RUN if [ -d /tmp/certs ] && [ -n "$(ls -A /tmp/certs 2>/dev/null)" ]; then \
        cp /tmp/certs/*.crt /usr/local/share/ca-certificates/ 2>/dev/null || true; \
        update-ca-certificates; \
    fi && rm -rf /tmp/certs

# Instala dependências Python primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prepara e instala o Mozilla PDF.js viewer oficial diretamente na imagem
COPY src/security.py /app/src/security.py
COPY src/setup_pdfjs.py /app/src/setup_pdfjs.py
ENV PDFJS_TARGET_DIR=/app/static/pdfjs
RUN python3 /app/src/setup_pdfjs.py

# Copia os arquivos do projeto
COPY . .

# Healthcheck usando a variável de ambiente PORT vinda do runtime (.env) com trava Fail-Closed
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD [ -n "${PORT}" ] && curl --fail http://127.0.0.1:${PORT}/_stcore/health || exit 1

# Inicia a aplicação Streamlit com verificação Fail-Closed obrigatória da variável PORT
CMD ["sh", "-c", "[ -n \"${PORT}\" ] || { echo 'FATAL [Fail-Closed]: Variavel PORT ausente ou vazia!' >&2; exit 1; }; exec streamlit run app.py --server.port \"${PORT}\" --server.address 0.0.0.0"]
