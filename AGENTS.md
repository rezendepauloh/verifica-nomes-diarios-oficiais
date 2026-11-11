# 🤖 AGENTS.md — Diretrizes para Agentes de IA & Engenharia Autônoma

> **Instruções operacionais, arquitetura do sistema, convenções de código e protocolo obrigatório de desenvolvimento para Antigravity, Claude Code, Gemini e assistentes de código que operam neste repositório.**  
> *Leia com atenção antes de criar, alterar ou refatorar qualquer arquivo neste projeto.*

---

## 🎯 1. Filosofia e Visão Geral do Sistema
O **Verifica Nomes em Diários Oficiais & Central de Editais de Concursos** é uma plataforma Python/Streamlit voltada ao monitoramento automatizado de nomes em diários oficiais e ao planejamento inteligente de editais de concursos públicos para **Paulo** e **Kamila**.

### Módulos Principais:
1. **Monitoramento de Diários Oficiais**: Varredura periódica e inteligente (DOM-CG, DOE-MS, DOU, AMEMS, Diário da Justiça, etc.) com detecção de nomes monitorados, histórico de ocorrências e notificações via WhatsApp (CallMeBot).
2. **Central de Editais & Planejamento de Concursos**:
   - Cadastro e upload de editais (.pdf).
   - Cronograma interativo com cálculo dinâmico de situação (Concluído, Em Andamento, Hoje, Previsto), exportação `.ics` para Google Agenda e `.csv`.
   - Edital verticalizado com controle interativo de tópicos estudados (Teoria, Resumo, Questões, Revisões) e métricas de estudo em tempo real.
   - Leitor embutido de PDFs com seletor contextual na barra lateral e modo **Maximizar Janela** (`100vw`/`100vh`).
   - Robô de verificação e aplicação de **Retificações** com suporte nativo a APIs (Cebraspe) e scrapers (FAPEC e bancas genéricas), garantindo a mesclagem inteligente de datas e tópicos sem perda de progresso.

---

## 🏗️ 2. Arquitetura do Repositório e Estrutura de Diretórios

```text
.
├── app.py                      # Ponto de entrada Streamlit (navegação entre abas)
├── src/
│   ├── config.py               # Constantes globais, caminhos (DB_PATH, EDITAIS_DIR) e variáveis de ambiente
│   ├── logger.py               # Configuração unificada do loguru com logs coloridos e rotação
│   ├── terminal.py             # Helpers de saída colorida ANSI para o terminal
│   ├── components/             # Componentes modulares reutilizáveis de interface
│   │   ├── header.py           # Cabeçalho com status, relógio e tema
│   │   ├── sidebar.py          # Barra lateral com filtros contextuais para cada sub-aba
│   │   ├── subtabs.py          # Renderizador estilizado de sub-abas internas
│   │   ├── metric_cards.py     # Cards de estatísticas
│   │   └── pagination.py       # Controle de paginação com seletor de itens por página
│   ├── database/               # Camada de persistência SQLite
│   │   ├── db.py               # Schemas DDL, migrações defensivas e queries CRUD
│   │   └── __init__.py         # Exportação pública das funções do banco
│   ├── scrapers/               # Motores de busca em diários oficiais
│   │   └── engine.py           # Download seguro, limpeza de texto e scrapers específicos
│   ├── notifications/          # Notificações externas
│   │   └── whatsapp.py         # Formatação de mensagens e integração com CallMeBot API
│   ├── scheduler/              # Agendamento em segundo plano
│   │   └── cron.py             # Cálculo de próxima execução e runner do scanner
│   ├── editais/                # Módulo da Central de Editais e Concursos
│   │   ├── pdf_parser.py       # Extração de páginas, texto e tabelas via pdfplumber
│   │   ├── extractor_local.py  # Regex/heurísticas para cronograma e edital verticalizado
│   │   ├── extractor_ai.py     # Refinamento opcional com Google Gemini API
│   │   ├── calendar_utils.py   # Gerador RFC-5545 (.ics), fatiamento semântico e status
│   │   └── updater.py          # Robô de retificações (Cebraspe API, FAPEC scraper, merge semântico)
│   └── tabs/                   # Telas principais renderizadas pelo Streamlit
│       ├── dashboard.py        # Dashboard de ocorrências e diários oficiais
│       ├── editais.py          # Aba da Central de Editais & Concursos
│       └── configuracoes.py    # Gerenciamento de nomes, fontes, horários e WhatsApp
├── tests/                      # Suíte de Testes Automatizados (pytest)
│   ├── conftest.py             # Fixtures compartilhadas e setup de ambiente
│   ├── test_helpers.py         # Mocks e utilitários de asserção
│   ├── run_all.py              # Runner de testes standalone
│   ├── unit/                   # Testes unitários de banco, extratores, scrapers e agendamento
│   │   ├── test_database.py
│   │   ├── test_editais.py     # Testes de CRUD, retificações, parsers de bancas e .ics
│   │   ├── test_notifications.py
│   │   ├── test_pagination.py
│   │   ├── test_scheduler.py
│   │   └── test_scrapers.py
│   └── integration/            # Testes de integração end-to-end
│       └── test_scan_flow.py
├── uploads/                    # Diretório de persistência de PDFs originais e retificações
│   └── editais/
├── data/                       # Diretório do banco de dados SQLite (results.db)
├── assets/                     # Folhas de estilo CSS personalizadas
│   └── css/styles.css
├── Dockerfile                  # Imagem Docker da aplicação
└── docker-compose.yml          # Orquestração do container verifica-diarios-app
```

---

## ⚠️ 3. Regras Críticas de Engenharia (NÃO VIOLE)

1. **Persistência e Mesclagem Não-Destrutiva**:
   - **Cronograma**: Ao processar retificações, atualize apenas os eventos que foram explicitamente retificados, marcando-os com `[Retificado]`. Nunca apague o cronograma completo nem duplique eventos sem necessidade.
   - **Edital Verticalizado**: Retificações que adicionam novas matérias ou tópicos devem ser anexadas. **JAMAIS zere ou sobrescreva o status de estudo já concluído** (`teoria_concluida`, `resumo_concluido`, etc.).
   - **Semântica Rígida no Matching**: Eventos de *"atendimento especializado"* nunca podem casar com *"isenção de taxa"*; recursos de prova nunca podem casar com recursos de isenção.
2. **Componentes HTML e Streamlit (`streamlit.components.v1.html`)**:
   - Evite injetar HTML complexo ou scripts interativos com eventos inline (`onclick="..."`) diretamente no `st.markdown` do Streamlit para não acionar o `Minified React error #231`.
   - Para tabelas dinâmicas ou visualizadores complexos, use `components.html()` com eventos vinculados via `addEventListener` nativo e cálculo proporcional de altura (`calc_height` + `postMessage: streamlit:setFrameHeight`).
3. **Padrão de Cores e Estética Visual**:
   - Paleta oficial: Tema escuro (#0e1117 / #11141b) com azul de destaque (#2563eb / #3b82f6) e textos suaves (#f3f4f6 / #94a3b8).
   - Mantenha menus contextuais integrados na barra lateral e divididos por subtab ativa (`st.session_state["editais_internal_subtabs"]`).
4. **Resolução de Caminhos de Arquivo (Docker vs Host)**:
   - Use sempre `resolve_pdf_path()` para lidar com arquivos salvos tanto dentro do container (`/app/uploads/editais/...`) quanto no host (`uploads/editais/...`).
5. **Formatação PT-BR e Números**:
   - Números nos cards, tabelas e gráficos devem usar vírgula como separador decimal e ponto como separador de milhar.
6. **Comunicação Objetiva e Foco Técnico**:
   - Vá direto ao ponto, priorizando códigos limpos, testes automatizados e dados estruturados, sem explicações prolixas desnecessárias.

---

## 🔄 4. Ciclo Obrigatório de Toda Mudança (Checklist do Agente)

Antes de concluir qualquer resposta onde houve alteração de código ou configuração, o agente **DEVE obrigatoriamente** seguir este protocolo:

1. **Criar ou Atualizar Testes Unitários**:
   - Ao adicionar novos módulos, scrapers de bancas ou parsers, crie testes correspondentes em `tests/unit/` com mocks adequados (sem chamadas de rede externas nos testes automáticos).
2. **Executar a Suíte Completa de Testes**:
   - Execute sempre `pytest tests/ -v`.
   - **Nenhuma alteração deve ser finalizada com testes falhando.**
3. **Reiniciar o Container Docker (quando houver alterações em execução)**:
   - Execute `docker restart verifica-diarios-app` para aplicar as modificações no ambiente local ativo em `http://localhost:8504`.
4. **Manter a Documentação Sincronizada**:
   - Se novos fluxos ou comportamentos forem estabelecidos, atualize o `README.md` e este documento `AGENTS.md`.

---

## 🧪 5. Comandos Chave de Referência Rápida

```bash
# 1. Executar a suíte completa de testes automatizados
pytest tests/ -v

# 2. Executar apenas os testes de editais e retificações
pytest tests/unit/test_editais.py -v

# 3. Reiniciar o container da aplicação em background
docker restart verifica-diarios-app

# 4. Inspecionar logs em tempo real do container
docker logs -f verifica-diarios-app

# 5. Inspecionar o status das migrações do banco de dados SQLite
python3 -c "from src.database.db import init_db; init_db()"
```

