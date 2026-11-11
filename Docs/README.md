# 📚 Documentação Técnica — Verifica Diários Oficiais & Central de Editais

> **Central unificada de documentação de engenharia, arquitetura, manuais operacionais e guias práticos do sistema.**  
> Monitoramento inteligente de nomes em diários oficiais e planejamento completo de editais de concursos públicos para **Paulo** e **Kamila**.

---

## 🗂️ Estrutura e Mapa de Navegação da Documentação

```text
Docs/
├── README.md                                  # Este índice central unificado
│
├── 📖 guias/                                  # Manuais práticos de operação e uso
│   ├── central_editais_e_concursos.md         # Como cadastrar editais, verticalizar e usar o leitor
│   ├── cronograma_e_google_agenda.md          # Geração de calendário RFC-5545 (.ics), eventos e status
│   ├── retificacoes_e_robos_de_bancas.md      # Robô Cebraspe (API), FAPEC (scraper) e mesclagem não-destrutiva
│   ├── monitoramento_diarios_e_whatsapp.md    # Como cadastrar nomes, fontes, rotinas cron e CallMeBot
│   ├── deploy_docker_e_homelab.md             # Orquestração local (docker-compose) e deploy no Mini PC (Dockge)
│   └── limpeza_processed_urls.md              # Limpeza e reset do cache de URLs processadas no SQLite via Docker/local
│
├── 🏛️ arquitetura/                            # Decisões fundamentais de engenharia e modelagem
│   ├── modelagem_banco_de_dados.md            # Schema SQLite (results.db), tabelas e migrações defensivas
│   ├── estrutura_de_diretorios_slugs.md       # Organização /uploads/editais/{slug}/ e resolução de caminhos
│   ├── interface_streamlit_e_components.md    # Tema escuro, CSS customizado e componentes HTML isolados
│   └── ciclo_de_vida_scrapers_e_parsers.md    # Engenharia dos scrapers (BeautifulSoup, pdfplumber, APIs)
│
├── 🧪 testes/                                 # Suíte de testes automatizados e integridade
│   └── suite_de_testes_automatizados.md       # Manual do pytest, fixtures, mocks de rede e runner CLI
│
└── 🚨 issues/                                 # Registro de roadmap, pendências e melhorias
    └── convidados_google_agenda.md            # Documentação técnica da Issue #1 (Convidados no Google Agenda)
```

---

## 🚀 Acessos Rápidos Mais Utilizados

### 1. Central de Editais e Concursos
- **Como cadastrar um concurso e extrair matérias:** [Guia da Central de Editais](guias/central_editais_e_concursos.md)
- **Como sincronizar datas com o Google Agenda:** [Cronograma & Google Agenda (.ics)](guias/cronograma_e_google_agenda.md)
- **Como verificar retificações automáticas nas bancas:** [Retificações & Robôs de Bancas](guias/retificacoes_e_robos_de_bancas.md)

### 2. Monitoramento de Diários e Notificações
- **Como configurar o CallMeBot WhatsApp:** [Monitoramento & WhatsApp](guias/monitoramento_diarios_e_whatsapp.md#configuração-do-whatsapp-callmebot)
- **Como programar horários de varredura:** [Agendamento Automático (Cron)](guias/monitoramento_diarios_e_whatsapp.md#agendamento-automático-cron)

### 3. Operação Técnica e Manutenção
- **Como rodar todos os testes automatizados:** [Suíte de Testes](testes/suite_de_testes_automatizados.md)
- **Como funciona a estrutura de pastas dos editais:** [Estrutura de Slugs & Uploads](arquitetura/estrutura_de_diretorios_slugs.md)
- **Subir aplicação via Docker:** [Deploy Docker & Homelab](guias/deploy_docker_e_homelab.md)
- **Resetar cache de leitura de diários oficiais:** [Limpeza de URLs Processadas](guias/limpeza_processed_urls.md)

