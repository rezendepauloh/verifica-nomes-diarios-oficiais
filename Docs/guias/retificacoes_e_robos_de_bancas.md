# 🤖 Robô de Retificações e Integração com Bancas Organizadoras

Concursos públicos frequentemente publicam editais retificadores alterando datas de provas, prazos de recursos ou incluindo novas disciplinas. O sistema foi desenhado para acompanhar essas mudanças de forma **autônoma e não-destrutiva**.

---

## 1. Arquitetura das Integrações por Banca (`src/editais/updater.py`)

Seguindo o mesmo princípio modular dos motores de busca em diários oficiais, as bancas possuem funções dedicadas:

### 🏛️ Cebraspe (`fetch_cebraspe_documents`)
- **Mecanismo**: API REST oficial da banca (`https://apis.cebraspe.org.br/cebraspe/eventos/{slug}`).
- **Comportamento**: A partir da URL do concurso (ex: `https://www.cebraspe.org.br/concursos/cgu_26_affc`), extrai o slug `cgu_26_affc` e consulta o endpoint JSON.
- **Vantagem**: Muito mais rápido e imune a mudanças no layout visual da página (SPA React). Retorna a lista exata de PDFs com tipo, data de publicação e links no CDN.

### 🏛️ FAPEC (`fetch_fapec_documents`)
- **Mecanismo**: Web scraping com `BeautifulSoup` adaptado para o portal da banca (`portal.concurso.fundacaofapec.org.br`).
- **Comportamento**: Varre as listas de arquivos disponíveis (`.list-group-item`), extraindo a data de postagem, título oficial do edital e o link direto para download (`arquivo.php?file=...`).

### 🏛️ UFMS Concursos (`fetch_ufms_concursos_documents`)
- **Mecanismo**: Scraper especializado para o portal de concursos da UFMS (`https://www.concursos.ufms.br/`).
- **Comportamento**: 
  - Reconhece tanto links de notícia direta (`/front/news/view/<id>`), links de setup do concurso (`/front/setup/<id>`) quanto o portal geral de eventos (`/front/events`).
  - Em páginas de notícia, correlaciona o título da publicação com os arquivos disponíveis na tabela de documentos (`/front/documents/download/<id>`) e inspeciona o setup pai correspondente para detectar novos editais e comunicados lançados posteriormente.
  - Classifica semanticamente os documentos em *Edital de Abertura*, *Retificação*, *Inscrições*, *Atendimento Especial*, *Cotas / PcD*, *Isenção*, *Gabarito*, *Resultado*, *Convocação* ou *Regulamento*.

### 🌐 Bancas Genéricas (`fetch_generic_html_documents`)
- **Mecanismo**: Crawler genérico baseado em HTML com resolução de links relativos (`urljoin`).
- **Comportamento**: Identifica links apontando para arquivos `.pdf` e categoriza pelo texto do link (Retificação, Edital, Comunicado, Gabarito, etc.).

---

## 2. Nomenclatura Amigável dos Arquivos Baixados

Para evitar nomes com hashes criptográficos indecifráveis gerados pelos CDNs (ex: `1793838211_8CC969EF9F81DD9088CC93655FE2734C95419BE8A9285A887D96D915605D867C.pdf`), o sistema conta com a função `sanitize_friendly_filename`:
- Converte caracteres para ASCII sem acentos.
- Mantém a identificação original do edital.
- **Exemplo Real**:
  `Edital_no_2_Retificacao_do_subitem_6.2.4_e_do_Anexo_I_Cronograma_Previsto_do_Edital_no_1.pdf`

---

## 3. Diretórios Isolados por Concurso (`/uploads/editais/{slug}/`)

Todos os arquivos pertencentes a um concurso ficam agrupados em uma pasta própria:
```text
uploads/editais/
└── cgu_26_affc/
    ├── 1793822239_Edital_CGU.pdf                                                # Edital Original
    └── Edital_no_2_Retificacao_do_subitem_6.2.4_e_do_Anexo_I_Cronograma_...pdf  # Retificação
```

---

## 4. Mesclagem Não-Destrutiva

Ao processar uma retificação:
1. **Cronograma**:
   - O algoritmo compara os eventos via Jaccard Similarity e semântica rígida: eventos de *"atendimento especializado"* nunca casam com *"isenção de taxa"*.
   - Apenas os eventos alterados têm suas datas atualizadas e recebem a tag `[Retificado]`.
   - Eventos inalterados são preservados intactos.
2. **Edital Verticalizado**:
   - Tópicos novos ou retificados são adicionados no fim da disciplina.
   - **Checkboxes de estudo já concluídos (teoria, resumo, questões) NUNCA são zerados.**

