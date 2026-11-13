# 🔍 Verifica Nomes em Diários Oficiais & Central de Editais

Aplicação Python/Streamlit desenvolvida para realizar varreduras automatizadas em diversas fontes oficiais em busca de nomes monitorados, além de oferecer uma **Central de Editais & Planejamento Inteligente de Concursos Públicos** para **Paulo** e **Kamila**.

As ocorrências e editais são armazenados de forma incremental em um banco de dados relacional SQLite (`data/results.db`) e exibidos em uma interface web rica, moderna e responsiva.

---

## 🛠️ Tecnologias Utilizadas

- **Core**: Python 3.12+
- **Interface Gráfica**: Streamlit com paleta escura (#0e1117 / #11141b) e acentos azuis (#2563eb / #3b82f6), cards métricos, menus contextuais e modais.
- **Banco de Dados**: SQLite Relacional com migrações automáticas e integridade referencial (`data/results.db`).
- **Parsing de PDFs & Editais**: `pdfplumber` para extração de textos e tabelas estruturadas; heurísticas e regex para cronogramas e disciplinas; suporte opcional à **API do Google Gemini** para refinamento com IA.
- **Integração com Bancas**:
  - API REST oficial do **Cebraspe** (`apis.cebraspe.org.br`) para mapeamento automático de retificações e comunicados.
  - Scraper especializado para o portal da **FAPEC** (`portal.concurso.fundacaofapec.org.br`).
  - Crawler genérico com `BeautifulSoup` para bancas tradicionais.
- **Notificações**: Integração leve com a API do **CallMeBot** para envio de alertas instantâneos no WhatsApp.
- **Exportação de Calendários**: Gerador RFC-5545 (`.ics`) compatível com o Google Agenda e atalhos de 1 clique para agendamento web.
- **Infraestrutura**: Docker & Docker Compose com suporte a deploy no Homelab / Mini PC (Dockge).

---

## 📚 Central de Documentação Técnica (`Docs/`)

O repositório conta com uma central de documentação rica e modular no diretório [`Docs/`](Docs/README.md):

- 📖 **[Central de Editais e Planejamento de Concursos](Docs/guias/central_editais_e_concursos.md)**: Manual de cadastro, verticalização e visualizador de PDFs.
- 📅 **[Cronograma & Integração com Google Agenda](Docs/guias/cronograma_e_google_agenda.md)**: Fatiamento de períodos, padrão de títulos e exportação `.ics`.
- 🤖 **[Robô de Retificações & Bancas](Docs/guias/retificacoes_e_robos_de_bancas.md)**: Funcionamento das APIs, scrapers e mesclagem não-destrutiva de dados.
- 🏛️ **[Estrutura de Slugs & Uploads](Docs/arquitetura/estrutura_de_diretorios_slugs.md)**: Armazenamento em `uploads/editais/{slug}/` e nomes amigáveis de arquivos.
- 🏛️ **[Modelagem do Banco de Dados](Docs/arquitetura/modelagem_banco_de_dados.md)**: Schemas das tabelas SQLite e histórico de documentos.
- 🧪 **[Suíte de Testes Automatizados](Docs/testes/suite_de_testes_automatizados.md)**: Guia de execução dos testes com pytest.
- 🚨 **[Registro da Issue #1 (Google Agenda)](Docs/issues/convidados_google_agenda.md)**: Documentação técnica da pendência de convidados via `.ics`.
- 🤖 **[Diretrizes para Agentes de IA (AGENTS.md)](AGENTS.md)**: Protocolo de engenharia e regras de desenvolvimento autônomo.

---

## 📂 Estrutura do Repositório

```text
├── app.py                      # Ponto de entrada Streamlit (navegação entre abas)
├── AGENTS.md                   # Protocolo obrigatório para agentes de IA (Antigravity/Claude/Gemini)
├── Docs/                       # Central unificada de documentação técnica e guias
├── 00-iniciar.sh               # CLI unificado para Linux/WSL (Docker, Testes e Homelab)
├── 00-iniciar.cmd              # Script de inicialização rápida para Windows
├── Dockerfile                  # Imagem Docker endurecida (non-root appuser, Fail-Closed PORT)
├── docker-compose.yml          # Orquestrador local com bind restrito (127.0.0.1:${PORT}:${PORT})
├── data/
│   └── results.db              # Banco de dados SQLite persistente (permissão 0600)
├── uploads/
│   └── editais/
│       └── {slug_concurso}/    # Editais originais e retificações organizados por concurso
├── assets/
│   └── css/styles.css          # Folhas de estilo personalizadas (Tema escuro)
├── tests/                      # Suíte de testes automatizados (pytest + auditoria contínua SecOps)
│   ├── conftest.py             # Fixtures e isolamento de banco temporário
│   ├── run_all.py              # Runner de testes standalone colorido
│   ├── unit/                   # Testes unitários (segurança, editais, banco, scrapers, scheduler)
│   └── integration/            # Testes de integração de fluxo
└── src/
    ├── config.py               # Constantes, timezone, slugs validados e diretórios
    ├── security.py             # Núcleo SecOps (Fail-Closed, SSRF, Zip-Bomb, Path Traversal, Auth/RateLimit)
    ├── logger.py               # Logging centralizado com loguru
    ├── terminal.py             # Utilitários de saída colorida ANSI
    ├── database/               # Camada SQLite (CRUD de ocorrências, nomes e editais)
    ├── scrapers/               # Motores de busca nos diários oficiais (DOU, DO-MS, etc.)
    ├── notifications/          # Integração com WhatsApp (CallMeBot)
    ├── scheduler/              # Agendador cron autônomo em segundo plano
    ├── editais/                # Módulo da Central de Editais
    │   ├── pdf_parser.py       # Extração de textos e tabelas via pdfplumber
    │   ├── extractor_local.py  # Regex e heurísticas para cronograma e verticalizado
    │   ├── extractor_ai.py     # Refinamento opcional com Gemini IA
    │   ├── calendar_utils.py   # Gerador .ics RFC-5545 e status dinâmico
    │   └── updater.py          # Robô Cebraspe (API), FAPEC (scraper) e merge
    └── tabs/                   # Telas Streamlit (dashboard, editais, configuracoes)
```

---

## 🚀 Instalação e Execução (Docker)

### 1. Clonar o repositório
```bash
git clone https://github.com/rezendepauloh/verifica-nomes-diarios-oficiais
cd verifica-nomes-diarios-oficiais
```

### 2. Configurar o `.env` (com permissões restritas)
```bash
cp .env-example .env
chmod 600 .env
```

### 3. Iniciar com Docker Compose
```bash
docker compose up -d --build
```
Acesse o painel web em: `http://127.0.0.1:8504` (ou `http://localhost:8504`).

---

## 🔒 Padrão de Segurança e Hardening (SecOps)

- **Zero Secrets/PII em Arquivos Rastreados**: Chaves CallMeBot, chaves Gemini, telefones pessoais, e-mails, IDs de agenda e IPs de Homelab residem exclusivamente no `.env` (`chmod 600`), validado continuamente por `tests/unit/test_security.py`.
- **Travas Fail-Closed**: `Dockerfile`, `docker-compose.yml`, `00-iniciar.sh` e `src/security.py` recusam inicialização ou deploy caso variáveis obrigatórias (`PORT`, credenciais quando `APP_AUTH_REQUIRED=true` ou variáveis `HOMELAB_*`) estejam ausentes.
- **Bind Local Restrito & Hardening de Container**: Portas mapeadas exclusivamente em `127.0.0.1:${PORT}:${PORT}`, execução sob usuário não-privilegiado (`appuser`) e `security_opt: ["no-new-privileges:true"]`.
- **Proteções WebUI & Parsers**: Proteção CSRF/XSRF e CORS ativas (`.streamlit/config.toml`), validação de `Host` header, Rate Limiting contra força bruta (`HTTP 429`), guarda anti-SSRF, anti-Path Traversal e anti-Zip-Bomb/Zip-Slip.

### 4. Executar os Testes Automatizados
```bash
pytest tests/ -v
# ou via runner local:
./00-iniciar.sh --test
```
