# 🏛️ Modelagem do Banco de Dados SQLite (results.db)

O banco de dados utiliza SQLite 3 com persistência no arquivo local `./data/results.db` (mapeado como volume no container Docker).

---

## 1. Schema das Tabelas Principais

### Tabela `editais`
Armazena os concursos cadastrados na Central de Editais:
```sql
CREATE TABLE editais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    cargo TEXT DEFAULT '',
    banca TEXT DEFAULT '',
    ano INTEGER DEFAULT 2026,
    interessado TEXT DEFAULT 'Ambos',
    status TEXT DEFAULT 'Em Andamento',
    arquivo_nome TEXT NOT NULL,
    arquivo_path TEXT NOT NULL,
    link_oficial TEXT DEFAULT '',
    total_paginas INTEGER DEFAULT 0,
    observacoes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Tabela `edital_cronograma`
Armazena os eventos e datas críticas extraídos dos editais:
```sql
CREATE TABLE edital_cronograma (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edital_id INTEGER NOT NULL,
    evento TEXT NOT NULL,
    data_inicio TEXT,
    data_fim TEXT,
    data_limite TEXT,
    status TEXT DEFAULT 'Previsto',
    observacao TEXT DEFAULT '',
    ordem INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
);
```

### Tabela `edital_verticalizado`
Armazena a grade de conteúdo programático e progresso de estudo:
```sql
CREATE TABLE edital_verticalizado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edital_id INTEGER NOT NULL,
    disciplina TEXT NOT NULL,
    topico TEXT NOT NULL,
    subtopico TEXT DEFAULT '',
    peso REAL DEFAULT 1.0,
    questoes_previstas INTEGER DEFAULT 0,
    teoria_concluida INTEGER DEFAULT 0,
    resumo_concluido INTEGER DEFAULT 0,
    questoes_concluidas INTEGER DEFAULT 0,
    revisao_1 INTEGER DEFAULT 0,
    revisao_2 INTEGER DEFAULT 0,
    revisao_3 INTEGER DEFAULT 0,
    observacao TEXT DEFAULT '',
    ordem INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
);
```

### Tabela `edital_documentos`
Armazena os documentos anexos, retificações e comunicados vinculados a cada concurso:
```sql
CREATE TABLE edital_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edital_id INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    tipo TEXT DEFAULT 'Retificação',
    arquivo_nome TEXT NOT NULL,
    arquivo_path TEXT NOT NULL,
    data_publicacao TEXT DEFAULT '',
    url_origem TEXT DEFAULT '',
    processado INTEGER DEFAULT 0,
    resumo TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
);
```

