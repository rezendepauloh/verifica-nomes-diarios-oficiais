# 🏛️ Estrutura de Slugs & Uploads de Editais

Este documento detalha o padrão arquitetural de armazenamento de arquivos PDF adotado para a **Central de Editais**.

---

## 1. Problema Anterior
No modelo inicial, todos os arquivos PDF (tanto os editais originais cadastrados quanto os editais de retificação baixados pelas APIs das bancas) eram depositados na raiz da pasta `uploads/editais/`.  
Com o acréscimo de concursos com múltiplos aditivos e retificações (Edital 2, Comunicado 1, Retificação de Conteúdo, etc.), a pasta tornava-se desorganizada e sujeita a colisões de nomes ou acúmulo de arquivos órfãos.

---

## 2. Nova Arquitetura com Subdiretórios por Concurso

Cada concurso agora possui uma pasta própria dentro de `uploads/editais/`:

```text
uploads/
└── editais/
    ├── cgu_26_affc/                                                    # Slug do Concurso
    │   ├── 1793822239_Edital_CGU.pdf                                   # Edital Original
    │   └── Edital_no_2_Retificacao_do_subitem_6.2.4_...pdf             # Retificação com nome amigável
    ├── tjms_analista_ti_2026/
    └── progep_ufms_2026/
```

---

## 3. Resolução e Geração de Slugs (`src/config.py`)

A função `get_concurso_slug(titulo, ano, link_oficial)` segue uma política de prioridades:

1. **Slug da Banca (Cebraspe / URLs de Concursos)**:
   - Se o concurso possuir um link como `https://www.cebraspe.org.br/concursos/cgu_26_affc`, o slug extraído é exatamente `cgu_26_affc`.
2. **Slug Fallback por Título e Ano**:
   - Converte o título em ASCII sem acentos, minúsculo, substituindo espaços e caracteres especiais por sublinhados (`_`), anexando o ano:
   - `"Técnico MPE MS"`, `2026` $\rightarrow$ `tecnico_mpe_ms_2026`.

---

## 4. Resolução Resiliente de Caminhos (`resolve_pdf_path`)

Para garantir compatibilidade tanto no host quanto dentro do container Docker:
1. Testa se o caminho informado já existe como absoluto no sistema de arquivos.
2. Testa relativo à raiz do projeto (`ROOT_DIR / path`).
3. Testa na raiz de editais (`EDITAIS_DIR / filename`).
4. **Busca Recursiva**: Executa `EDITAIS_DIR.glob("**/{filename}")` para localizar o arquivo em qualquer subpasta de concurso existente.

