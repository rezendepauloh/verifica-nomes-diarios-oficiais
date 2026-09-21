# 🔍 Monitor de Diários Oficiais & Concursos

Aplicação premium em Python e Streamlit desenvolvida para realizar varreduras automatizadas, em tempo real, em diversas fontes oficiais em busca de nomes cadastrados no sistema. As ocorrências encontradas são salvas de forma incremental em um banco de dados relacional SQLite (`data/results.db`) e exibidas em uma interface web rica e moderna.

O sistema conta com **Página Central de Configurações** para gestão de pessoas monitoradas (incluindo números de telefone/WhatsApp para futuras notificações) e portais de dados com verificação dinâmica de integração (`✓ Scraper Ativo` vs `❌ Sem Scraper`), além de suporte a deploy automatizado no Homelab / Mini PC com Dockge.

---

## 🛠️ Tecnologias Utilizadas

- **Core**: Python 3.11+
- **Interface Gráfica**: Streamlit (estética premium, suporte a temas claro/escuro, cards métricos, abas nativas e modais)
- **Banco de Dados**: SQLite Relacional com migrações automáticas e volume persistente em `./data/results.db`
- **Web Scraping & Parsing**:
  - `requests` (Requisições HTTP robustas com persistência de sessão e suporte a POST/CSRF)
  - `beautifulsoup4` (Parsing de estruturas de páginas HTML)
  - `pdfplumber` (Extração em memória e varredura de textos em arquivos PDF)
  - `zipfile` (Parsing nativo em memória de documentos do Microsoft Word `.docx`)
- **Infraestrutura & Deploy**:
  - Docker & Docker Compose (ambientes de desenvolvimento e produção desacoplados)
  - Pipeline de Deploy remoto via `rsync` e SSH para Mini PC / Homelab gerenciado via Dockge

---

## 📂 Estrutura do Projeto

```text
├── app.py                      # Ponto de entrada leve (orquestra a interface e abas em src/)
├── 00-iniciar.sh               # CLI unificado para Linux/WSL (Docker Manager e Deploy Homelab)
├── 00-iniciar.cmd              # Script de inicialização rápida para Windows
├── Dockerfile                  # Imagem Docker otimizada baseada em Python 3.12-slim
├── docker-compose.yml          # Orquestrador local com volumes e live-reload
├── docker-compose.server.yml   # Orquestrador de produção para o servidor / Mini PC (Dockge)
├── requirements.txt            # Dependências Python do projeto
├── data/
│   └── results.db              # Banco de dados SQLite persistente (tabelas occurrences, names, sources)
├── .env                        # Variáveis de ambiente (Porta, Homelab SSH, fallback inicial)
├── .env-example                # Modelo de variáveis de ambiente
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
    │   └── db.py               # Camada de banco de dados SQLite (occurrences, names, sources, schedule)
    ├── scheduler/
    │   ├── __init__.py
    │   └── engine.py           # Agendador de varreduras em background (Singleton Thread Daemon)
    ├── scrapers/
    │   ├── __init__.py
    │   └── engine.py           # Motores de busca/crawlers das fontes oficiais monitoradas com AVAILABLE_SCRAPERS
    ├── components/
    │   ├── __init__.py
    │   ├── header.py           # Cabeçalho visual com gradiente e títulos
    │   ├── subtabs.py          # Componente de sub-navegação moderna via query parameters (?subtab=slug)
    │   ├── sidebar.py          # Barra lateral dinâmica com seleção de nomes e fontes ativas
    │   ├── metrics.py          # Cards de indicadores (Total, Pendentes e Lidos)
    │   ├── metric_cards.py     # Componente flexível e adaptável ao tema claro/escuro de cards métricos
    │   ├── scan_control.py     # Botão e visualizador de progresso da varredura em background
    │   └── details_modal.py    # Modal de detalhes da ocorrência e gerenciamento de status
    └── tabs/
        ├── __init__.py
        ├── dashboard.py        # Tabela interativa com filtros dinâmicos e gráfico por fonte
        └── configuracoes.py    # Gestão de Nomes, Telefones, Fontes, Agendamento Automático e Backup
```

---

## ⚙️ Painel de Configurações Dinâmico

O sistema elimina o acoplamento estático com o `.env` através da aba **⚙️ Configurações & Fontes**:

1. **👥 Gestão de Pessoas & Nomes Monitorados**:
   - Cadastro de novos nomes completos e **número de telefone / WhatsApp com DDD** formatado: `(XX) XXXXX-XXXX`.
   - Modais unificados (`@st.dialog`) para cadastro e edição direta ao clicar nas linhas da tabela.
   - Alternância de status ativo/inativo e exclusão com 1 clique.
   - Os nomes ativos alimentam instantaneamente a barra lateral e as rotinas de varredura.
2. **🌐 Fontes & Diários Oficiais**:
   - Cadastro de novos portais oficiais (`slug`, nome, URL e descrição).
   - **Ticket de Status de Scraper**:
     - `✓ Scraper Ativo`: Robô de raspagem web já programado no motor (`engine.py`).
     - `❌ Sem Scraper`: Fonte cadastrada no sistema aguardando desenvolvimento da função de coleta.
3. **⏰ Agendamento Automático (Cron / Scheduler Dinâmico)**:
   - Configuração de dias da semana (ex: Segunda a Sexta, ou incluindo finais de semana).
   - Definição de horários de execução diária no formato 24h (ex: `08:00`, ou múltiplos como `08:00, 14:00`).
   - Monitoramento em background autônomo sem travar a interface web e com prevenção de execuções concorrentes.
   - Botão para disparo de teste manual imediato.
4. **💾 Sincronização & Migração**:
   - Botão para reimportar dados do `.env` caso necessário, com migrações automáticas de schema relacional.

---

## 📡 Fontes Oficiais Pré-Integradas (`✓ Scraper Ativo`)

1. **Diário Oficial da União (DOU)** - Varredura via consulta de busca integrada da Imprensa Nacional.
2. **Diário Oficial de MS (DO-MS)** - Integração com a API REST oficial do Diário do Estado de Mato Grosso do Sul.
3. **IFMS (SUAP)** - Pesquisa via formulário POST autenticado por token CSRF dinâmico nos Boletins de Serviço.
4. **Sanesul (Concursos)** - Varredura incremental de todos os editais de 2025/2026 com extração e busca de nomes dentro de PDFs e DOCX direto na memória, acelerado por cache de URLs processadas.
5. **MS Gás (Concursos)** - Varredura em páginas de editais de concursos e seleções.
6. **CRBM 1ª Região** - Monitoramento via sistema interno de buscas baseada no WordPress.
7. **Diário Oficial de Dourados (DO-Dourados)** - Busca textual em edições com download automático de PDFs.

---

## 🚀 Instalação e Execução (Docker)

### 1. Clonar o repositório
```bash
git clone https://github.com/rezendepauloh/verifica-nomes-diarios-oficiais
cd verifica-nomes-diarios-oficiais
```

### 2. Configurar o `.env`
Copie o arquivo de exemplo:
```bash
cp .env-example .env
```
Defina a porta local (ex: `PORT=8503`) e, se for utilizar deploy no homelab, as variáveis `HOMELAB_*`.

### 3. Iniciar a Aplicação

#### No Linux / WSL (CLI Unificado):
```bash
./00-iniciar.sh
```
Atalhos úteis via CLI:
- `./00-iniciar.sh --start` : Sobe a aplicação local e abre o navegador.
- `./00-iniciar.sh --scan` : Executa uma varredura manual em segundo plano.
- `./00-iniciar.sh --logs` : Acompanha os logs em tempo real do container.
- `./00-iniciar.sh --rebuild` : Reconstrói a imagem Docker.
- `./00-iniciar.sh --deploy` : Executa o pipeline de deploy automatizado no Homelab / Mini PC (Dockge).

#### No Windows:
Dê duplo clique no arquivo:
```bat
00-iniciar.cmd
```

#### Via Docker Compose:
```bash
docker compose up -d --build
```
Acesse o painel web em: `http://localhost:8503`


