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

- [app.py](file:///d:/PythonProjects/verifica-nomes-diarios-oficiais/app.py): Ponto de entrada da aplicação que gerencia a interface em Streamlit, dialogs, status de leitura e visualização das ocorrências.
- [scraper.py](file:///d:/PythonProjects/verifica-nomes-diarios-oficiais/scraper.py): Motores de crawlers dedicados para cada fonte de dados.
- [database.py](file:///d:/PythonProjects/verifica-nomes-diarios-oficiais/database.py): Funções de criação, verificação e gerenciamento das tabelas SQLite (`occurrences` e `processed_urls`).
- [logger_config.py](file:///d:/PythonProjects/verifica-nomes-diarios-oficiais/logger_config.py): Configuração de logs estruturados em arquivo e terminal.
- `.env`: Configurações de nomes monitorados e links das fontes oficiais.

---

## 📡 Fontes Oficiais Monitoradas

1. **Diário Oficial da União (DOU)** - Varredura via consulta de busca integrada.
2. **Diário Oficial de MS (DO-MS)** - Integração com a API REST oficial do Diário do Estado.
3. **IFMS (SUAP)** - Pesquisa via formulário POST autenticado por token CSRF dinâmico nos Boletins de Serviço.
4. **Sanesul (Concursos)** - Varredura incremental de todos os editais de 2025/2026 com extração e busca de nomes dentro de PDFs e DOCX direto na memória, acelerado por cache de URLs processadas por nome.
5. **MS Gás (Concursos)** - Varredura em páginas de editais de concursos e seleções.
6. **CRBM 1ª Região** - Monitoramento via sistema interno de buscas baseada no WordPress.

---

## ⚙️ Instalação e Configuração

### 1. Clonar o repositório e acessar a pasta do projeto

```powershell
git clone https://github.com/rezendepauloh/verifica-nomes-diarios-oficiais
```

### 2. Configurar o Ambiente Virtual e instalar dependências

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente (`.env`)

Crie um arquivo `.env` na raiz do projeto com o seguinte formato:

```env
# Nomes a serem monitorados separados por vírgula
MONITOR_NAMES="Fulano,Ciclano"

# URLs oficiais
URL_DOU="https://www.in.gov.br/leiturajornal"
URL_DOMS="https://www.diariooficial.ms.gov.br"
URL_IFMS="https://suap.ifms.edu.br/bse/consulta_publica/"
URL_SANESUL="https://www.sanesul.ms.gov.br/concursos-e-processos-seletivos"
URL_MSGAS="https://transparencia.msgas.com.br/Concursos"
URL_CRBM="https://crbm1.gov.br/"
```

---

## 🚀 Como Executar o Painel Streamlit

No terminal do projeto, execute o seguinte comando:

```powershell
.venv\Scripts\streamlit run app.py
```

Acesse o endereço exibido no console (geralmente [http://localhost:8501](http://localhost:8501)) para interagir com o monitor.
