# 🔍 Monitor de Diários Oficiais & Concursos

Aplicação premium em Python e Streamlit desenvolvida para realizar varreduras automatizadas, em tempo real, em diversas fontes oficiais em busca de nomes cadastrados no sistema. As ocorrências encontradas são salvas de forma incremental em um banco de dados local SQLite e exibidas em uma interface web rica.

---

## 🛠️ Tecnologias Utilizadas

- **Core**: Python 3.11+
- **Interface Gráfica**: Streamlit (estética premium, suporte a temas escuros, cards métricos e filtros dinâmicos)
- **Banco de Dados**: SQLite (persistência local e incremental)
- **Web Scraping & Parsing**:
  - `requests` (Requisições HTTP robustas com persistência de sessão e suporte a POST/CSRF)
  - `beautifulsoup4` (Parsing de estruturas de páginas HTML)
  - `pdfplumber` (Extração em memória e varredura de textos em arquivos PDF)
  - `zipfile` (Parsing nativo em memória de documentos do Microsoft Word `.docx`)

---

## 📂 Estrutura do Projeto

```text
├── app.py                      # Ponto de entrada leve (orquestra a interface e módulos de src/)
├── 00-iniciar.sh               # CLI unificado para Linux/WSL (Docker Manager)
├── 00-iniciar.cmd              # Script de inicialização rápida para Windows
├── Dockerfile                  # Imagem Docker otimizada baseada em Python 3.12-slim
├── docker-compose.yml          # Orquestrador com volumes e porta dinâmica
├── requirements.txt            # Dependências Python do projeto
├── results.db                  # Banco de dados SQLite persistente local
├── .env                        # Variáveis de ambiente (Porta, nomes e URLs oficiais)
├── assets/
│   └── css/
│       └── styles.css          # Estilos CSS modernos e fontes (Outfit)
└── src/
    ├── run_scan.py             # Script de varredura em segundo plano (CLI / Subprocesso)
    ├── config.py               # Variáveis de ambiente, caminhos e controle de lock/processos
    ├── logger.py               # Logging com SafeStreamWrapper e ANSIColoredFormatter
    ├── terminal.py             # Utilitário de cores ANSI, molduras e formatação no console
    ├── database/
    │   ├── __init__.py
    │   └── db.py               # Camada de banco de dados SQLite (occurrences e processed_urls)
    ├── scrapers/
    │   ├── __init__.py
    │   └── engine.py           # Motores de busca/crawlers das fontes oficiais monitoradas
    ├── components/
    │   ├── __init__.py
    │   ├── header.py           # Cabeçalho visual com gradiente e títulos
    │   ├── sidebar.py          # Barra lateral com filtros de nomes e fontes ativas
    │   ├── metrics.py          # Cards de indicadores (Total, Pendentes e Lidos)
    │   ├── scan_control.py     # Botão e visualizador de progresso da varredura
    │   └── details_modal.py    # Modal de detalhes e gerenciamento de status
    └── tabs/
        ├── __init__.py
        └── dashboard.py        # Tabela interativa com filtros dinâmicos e gráfico por fonte
```


---

## 📡 Fontes Oficiais Monitoradas

1. **Diário Oficial da União (DOU)** - Varredura via consulta de busca integrada.
2. **Diário Oficial de MS (DO-MS)** - Integração com a API REST oficial do Diário do Estado.
3. **IFMS (SUAP)** - Pesquisa via formulário POST autenticado por token CSRF dinâmico nos Boletins de Serviço.
4. **Sanesul (Concursos)** - Varredura incremental de todos os editais de 2025/2026 com extração e busca de nomes dentro de PDFs e DOCX direto na memória, acelerado por cache de URLs processadas por nome.
5. **MS Gás (Concursos)** - Varredura em páginas de editais de concursos e seleções.
6. **CRBM 1ª Região** - Monitoramento via sistema interno de buscas baseada no WordPress.
7. **Diário Oficial de Dourados (DO-Dourados)** - Busca textual em edições com download automático de PDFs.

---

## ⚙️ Instalação e Configuração

### 1. Clonar o repositório e acessar a pasta do projeto

```bash
git clone https://github.com/rezendepauloh/verifica-nomes-diarios-oficiais
cd verifica-nomes-diarios-oficiais
```

### 2. Configurar Variáveis de Ambiente (`.env`)

Copie o arquivo de exemplo `.env-example` para `.env` ou crie-o na raiz:

```bash
cp .env-example .env
```

Edite o arquivo `.env` com as configurações desejadas:

```env
# Nomes a serem monitorados separados por vírgula
MONITOR_NAMES="Fulano,Ciclano"

# URLs das fontes de dados oficiais
URL_DOU="https://www.in.gov.br/leiturajornal"
URL_DOMS="https://www.diariooficial.ms.gov.br"
URL_IFMS="https://suap.ifms.edu.br/bse/consulta_publica/"
URL_SANESUL="https://www.sanesul.ms.gov.br/concursos-e-processos-seletivos"
URL_MSGAS="https://transparencia.msgas.com.br/Concursos"
URL_CRBM="https://crbm1.gov.br/"
URL_DOURADOS="https://do.dourados.ms.gov.br/"

# Porta de execução da aplicação (obrigatória)
PORT=8503
```

---

## 🚀 Como Executar a Aplicação (Docker)

O projeto é 100% containerizado com Docker e Docker Compose, sem necessidade de gerenciar ambientes virtuais locais (`.venv`).

### No Linux / WSL (CLI Unificado)

Execute o script de gerenciamento:

```bash
./00-iniciar.sh
```

Ou execute diretamente através dos atalhos:
- `./00-iniciar.sh --start` : Inicia a aplicação e abre o navegador automaticamente na porta configurada.
- `./00-iniciar.sh --scan` : Executa uma varredura manual em segundo plano dentro do container.
- `./00-iniciar.sh --logs` : Acompanha os logs em tempo real do container.
- `./00-iniciar.sh --rebuild` : Reconstrói a imagem Docker sem cache.
- `./00-iniciar.sh --down` : Encerra os containers.

### No Windows

Basta dar dois cliques no arquivo:
```bat
00-iniciar.cmd
```

### Via Docker Compose Diretamente

```bash
# Iniciar em segundo plano com build automático
docker compose up -d --build

# Parar os containers
docker compose down
```

Acesse o painel web no navegador em: `http://localhost:<PORT>` (ex: [http://localhost:8503](http://localhost:8503)).

