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

# Copia os arquivos do projeto
COPY . .

# Healthcheck usando a variável de ambiente PORT vinda do runtime (.env)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:${PORT}/_stcore/health || exit 1

# Inicia a aplicação Streamlit usando estritamente a variável PORT
CMD ["sh", "-c", "streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0"]

