# 🧪 Suíte de Testes Automatizados

A estabilidade do sistema é garantida por uma suíte completa de testes automatizados com **pytest**, cobrindo o banco de dados, motores de raspagem, agendamento, extratores de editais e retificações.

---

## 1. Executando os Testes

Para rodar toda a suíte:
```bash
pytest tests/ -v
```

Ou diretamente pelo CLI unificado:
```bash
./00-iniciar.sh --test
```

Para rodar apenas os testes da Central de Editais:
```bash
pytest tests/unit/test_editais.py -v
```

---

## 2. Estrutura dos Testes

```text
tests/
├── conftest.py                   # Setup do banco de dados de testes isolado
├── test_helpers.py               # Utilitários de mock
├── unit/
│   ├── test_database.py          # Testes de persistência SQLite, nomes e ocorrências
│   ├── test_editais.py           # CRUD de editais, retificações, parsers Cebraspe/FAPEC e .ics
│   ├── test_notifications.py     # Mensagens de alerta e CallMeBot WhatsApp
│   ├── test_pagination.py        # Algoritmo de paginação e seletores de itens
│   ├── test_scheduler.py         # Cálculos de agendamento cron e fusos horários
│   └── test_scrapers.py          # Motores de busca em diários oficiais
└── integration/
    └── test_scan_flow.py         # Fluxo completo de varredura e notificação
```

---

## 3. Diretrizes para Novos Testes (Protocolo AGENTS.md)

1. **Sem Chamadas de Rede Externas**:
   - Use sempre `monkeypatch` para simular requisições HTTP (`requests.get`, APIs de bancas, portais de diários).
2. **Nenhum Teste Falhando**:
   - Nenhuma entrega ou modificação de código deve ser finalizada com testes em falha.

