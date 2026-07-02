import json
import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import re
from datetime import datetime
import urllib.parse
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()
from logger_config import logger

# Configurações de headers para evitar bloqueios
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_text(text):
    if not text:
        return ""
    # Remove marcações de highlight como <span class='highlight'> que o DOU injeta no resumo
    cleaned = re.sub(r'<[^>]+>', '', text)
    cleaned = cleaned.replace("&lt;", "<").replace("&gt;", ">").replace("\\/", "/")
    return re.sub(r'\s+', ' ', cleaned).strip()

def get_local_file_path(source_slug, url):
    """
    Retorna o caminho local para cachear o arquivo de edital/documento.
    Cria os diretórios necessários sob uploads/{source_slug}.
    """
    import hashlib
    
    # Cria a pasta de uploads para o slug específico
    dest_dir = os.path.join("uploads", source_slug)
    os.makedirs(dest_dir, exist_ok=True)
    
    # Extrai o nome do arquivo a partir da URL
    parsed_url = urllib.parse.urlparse(url)
    filename = os.path.basename(parsed_url.path)
    
    # Se não houver nome de arquivo válido ou extensão, gera usando hash md5
    if not filename or "." not in filename:
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        ext = ".pdf"
        if ".docx" in url.lower():
            ext = ".docx"
        filename = f"{url_hash}{ext}"
    else:
        # Previne caracteres inválidos no sistema de arquivos
        filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
        
    return os.path.join(dest_dir, filename)

def extract_json_array(html_content):
    start_idx = html_content.find('{"jsonArray":')
    if start_idx == -1:
        return None
    
    brace_count = 0
    in_string = False
    escape = False
    
    for i in range(start_idx, len(html_content)):
        char = html_content[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return html_content[start_idx:i+1]
    return None

def search_dou(name):
    """
    Pesquisa no Diário Oficial da União (DOU) via página de consulta pública.
    """
    results = []
    encoded_name = urllib.parse.quote_plus(f'"{name}"')
    base_url = os.getenv("URL_DOU")
    if not base_url:
        logger.warning(f"URL_DOU não configurada no .env. Ignorando busca para {name}.")
        return results
        
    # Extrai o host base e monta a URL de busca correta do DOU
    parsed_url = urllib.parse.urlparse(base_url)
    search_base = f"{parsed_url.scheme}://{parsed_url.netloc}/consulta/-/buscar/dou"
    url = f"{search_base}?q={encoded_name}&s=todos&exactDate=all&sortType=0"
        
    logger.info(f"Iniciando busca DOU para {name} na URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            html_content = response.text
            raw_json = extract_json_array(html_content)
            if raw_json:
                data = json.loads(raw_json)
                json_array = data.get("jsonArray", [])
                for item in json_array:
                    title = clean_text(item.get("title", ""))
                    url_title = item.get("urlTitle", "")
                    content_snippet = clean_text(item.get("content", ""))
                    hierarchy = item.get("hierarchyStr", "Diário Oficial da União")
                    pub_date = item.get("pubDate", datetime.today().strftime("%d/%m/%Y"))
                    
                    # Link padrão para o artigo no DOU
                    link = f"https://www.in.gov.br/web/dou/-/{url_title}"
                    
                    results.append({
                        "name": name,
                        "source": f"DOU - {hierarchy}",
                        "date": pub_date,
                        "link": link,
                        "context": f"{title} | {content_snippet}"[:300]
                    })
            logger.info(f"Busca DOU finalizada para {name}. Ocorrências encontradas: {len(results)}")
        else:
            logger.warning(f"Resposta inválida do DOU para {name}: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na busca do DOU para {name}: {e}")
    
    return results

def search_doms(name):
    """
    Pesquisa no Diário Oficial do MS consumindo a API REST de busca.
    """
    results = []
    base_url = os.getenv("URL_DOMS")

    if not base_url:
        logger.warning(f"URL_DOMS não configurada no .env. Ignorando busca para {name}.")
        return results
        
    encoded_name = urllib.parse.quote_plus(name)
    registro_por_pagina = 1000
    # Define 100 registros por página para obter todo o histórico em uma única requisição
    url = f"{base_url.rstrip('/')}/api/diarios/busca-diarios?tipo=1&texto={encoded_name}&pagina=1&registrosPorPagina={registro_por_pagina}"
    
    logger.info(f"Iniciando busca DO-MS para {name} na URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            paginas_diario = data.get("paginasDiario", [])
            for item in paginas_diario:
                numero = item.get("numero")
                descricao = item.get("descricao", f"Diário Oficial n. {numero}")
                pagina = item.get("pagina")
                pdf_url = item.get("caminhoArquivo", "")
                data_publicacao_raw = item.get("dataPublicacao", "")
                
                # Formata a data (de AAAA-MM-DDTHH:MM:SS para DD/MM/AAAA)
                pub_date = datetime.today().strftime("%d/%m/%Y")
                if data_publicacao_raw:
                    try:
                        dt = datetime.fromisoformat(data_publicacao_raw.split("T")[0])
                        pub_date = dt.strftime("%d/%m/%Y")
                    except Exception:
                        pass
                
                # Extrai trecho em destaque
                highlights = item.get("hiHighlight", {})
                highlight_texts = highlights.get("texto", [])
                context = ""
                if highlight_texts:
                    context = clean_text(" | ".join(highlight_texts))
                else:
                    context = f"Edição {numero}, Página {pagina}"
                
                # Cria link direto para o PDF posicionando na página correspondente
                link_com_pagina = f"{pdf_url}#page={pagina}" if pdf_url else base_url
                
                results.append({
                    "name": name,
                    "source": "Diário Oficial de MS",
                    "date": pub_date,
                    "link": link_com_pagina,
                    "context": context[:300]
                })
            logger.info(f"Busca DO-MS finalizada para {name}. Ocorrências encontradas: {len(results)}")
        else:
            logger.warning(f"Resposta inválida do DO-MS para {name}: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na busca do DO-MS para {name}: {e}")
    return results

def parse_pt_date(date_str):
    """
    Converte datas em português (ex: "8 de Junho de 2026") para o formato DD/MM/AAAA.
    """
    date_str = date_str.lower().strip()
    months = {
        "janeiro": "01", "fevereiro": "02", "março": "03", "abril": "04",
        "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
        "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
    }
    # Procura por padrões como "8 de Junho de 2026" ou "08 de junho de 2026"
    match = re.search(r'(\d+)\s+de\s+([a-zçáõ]+)\s+de\s+(\d{4})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month_name = match.group(2)
        year = match.group(3)
        month = months.get(month_name, "01")
        return f"{day}/{month}/{year}"
    return date_str

def search_ifms(name):
    """
    Pesquisa no SUAP/IFMS Consulta Pública.
    """
    results = []
    url = os.getenv("URL_IFMS")
    if not url:
        logger.warning(f"URL_IFMS não configurada no .env. Ignorando busca para {name}.")
        return results

    logger.info(f"Iniciando busca IFMS para {name} na URL: {url}")
    try:
        session = requests.Session()
        # 1. Faz GET para obter o formulário e o token CSRF
        r_get = session.get(url, headers=HEADERS, timeout=15)
        if r_get.status_code != 200:
            logger.warning(f"Não foi possível acessar a página do IFMS: HTTP {r_get.status_code}")
            return results
            
        soup_get = BeautifulSoup(r_get.content, "html.parser")
        csrf_input = soup_get.find("input", attrs={"name": "csrfmiddlewaretoken"})
        csrf_token = csrf_input.get("value") if csrf_input else None
        
        # 2. Configura os dados do formulário e headers
        data = {"pesquisa": name}
        if csrf_token:
            data["csrfmiddlewaretoken"] = csrf_token
            
        post_headers = HEADERS.copy()
        post_headers["Referer"] = url
        
        # 3. Faz POST com a pesquisa
        response = session.post(url, data=data, headers=post_headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            table = soup.find("table", class_="table")
            if table:
                rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
                for row in rows:
                    row_text = row.get_text()
                    if "nenhum resultado encontrado" in row_text.lower():
                        continue
                        
                    cols = row.find_all("td")
                    if len(cols) >= 3:
                        # td[0]: Opções (Visualizar / Baixar)
                        # td[1]: Edição (Boletim de Serviço nº X / Y)
                        # td[2]: Data de publicação
                        
                        # Tenta pegar o link de visualizar ou o link da edição
                        link_tag = cols[1].find("a", href=True) or cols[0].find("a", href=True)
                        link = link_tag["href"] if link_tag else ""
                        if link and not link.startswith("http"):
                            link = urllib.parse.urljoin("https://suap.ifms.edu.br", link)
                            
                        edition_text = clean_text(cols[1].get_text())
                        date_text = clean_text(cols[2].get_text())
                        pub_date = parse_pt_date(date_text)
                        
                        results.append({
                            "name": name,
                            "source": "IFMS SUAP",
                            "date": pub_date,
                            "link": link,
                            "context": f"{edition_text} | Publicado em {date_text}"
                        })
                logger.info(f"Busca IFMS finalizada para {name}. Ocorrências encontradas: {len(results)}")
            else:
                logger.info(f"Nenhum resultado encontrado na tabela do IFMS para {name}")
        else:
            logger.warning(f"Resposta inválida do IFMS para {name} no POST: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na busca do IFMS para {name}: {e}")
    return results

_sanesul_html_cache = None
_sanesul_doc_cache = {}

def search_sanesul(name):
    """
    Varredura na página de Concursos da Sanesul.
    Baixa e lê o conteúdo de novos PDFs/DOCX da listagem de 2025/2026.
    Usa cache em memória para evitar requisições repetidas e erro 429.
    """
    global _sanesul_html_cache, _sanesul_doc_cache
    import zipfile
    from database import is_url_processed, mark_url_processed
    
    results = []
    url = os.getenv("URL_SANESUL")
    if not url:
        logger.warning(f"URL_SANESUL não configurada no .env. Ignorando busca para {name}.")
        return results

    logger.info(f"Iniciando busca Sanesul para {name} na URL: {url}")
    try:
        # 1. Recupera a página principal (usa cache em memória se disponível)
        if _sanesul_html_cache is None:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                _sanesul_html_cache = response.content
            else:
                logger.warning(f"Resposta inválida da Sanesul para {name}: HTTP {response.status_code}")
                return results
        
        soup = BeautifulSoup(_sanesul_html_cache, "html.parser")
        
        # Encontra todos os links de editais de 2025 e 2026
        links_to_check = []
        for a in soup.find_all("a", class_="list-group-item", href=True):
            href = a["href"]
            text = clean_text(a.get_text())
            
            # Filtra por editais ou arquivos de 2025/2026
            if any(year in text or year in href for year in ["2025", "2026"]):
                full_url = urllib.parse.urljoin(url, href)
                links_to_check.append((text, full_url))
        
        logger.info(f"Sanesul: {len(links_to_check)} editais identificados para 2025/2026.")
        
        for doc_title, doc_url in links_to_check:
            # Ignora URLs que já foram processadas para este nome
            if is_url_processed(doc_url, name):
                continue
            
            # 2. Obtém o texto do documento (usa cache em memória ou faz download)
            text_content = ""
            if doc_url in _sanesul_doc_cache:
                text_content = _sanesul_doc_cache[doc_url]
            else:
                local_path = get_local_file_path("sanesul", doc_url)
                file_content = None
                if os.path.exists(local_path):
                    logger.info(f"Sanesul: Carregando arquivo do cache local: {local_path}")
                    try:
                        with open(local_path, "rb") as lf:
                            file_content = lf.read()
                    except Exception as fe:
                        logger.error(f"Erro ao ler arquivo local {local_path}: {fe}")
                
                if file_content is None:
                    logger.info(f"Sanesul: Baixando e analisando novo arquivo: {doc_title}")
                    try:
                        resp = requests.get(doc_url, headers=HEADERS, timeout=15)
                        if resp.status_code == 200:
                            file_content = resp.content
                            try:
                                with open(local_path, "wb") as lf:
                                    lf.write(file_content)
                            except Exception as fe:
                                logger.error(f"Erro ao salvar arquivo cache local {local_path}: {fe}")
                        else:
                            logger.warning(f"Erro ao baixar arquivo {doc_url}: HTTP {resp.status_code}")
                    except Exception as file_err:
                        logger.error(f"Erro ao baixar/processar arquivo {doc_url}: {file_err}")

                if file_content:
                    # Extrai texto com base na extensão
                    if doc_url.lower().endswith(".pdf"):
                        try:
                            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                                text_content = "\n".join([page.extract_text() or "" for page in pdf.pages])
                        except Exception as pdf_err:
                            logger.error(f"Erro ao ler PDF do Sanesul ({doc_url}): {pdf_err}")
                    elif doc_url.lower().endswith(".docx"):
                        try:
                            with zipfile.ZipFile(io.BytesIO(file_content)) as z:
                                xml_content = z.read("word/document.xml").decode("utf-8")
                                text_content = re.sub(r'<[^>]+>', '', xml_content)
                        except Exception as docx_err:
                            logger.error(f"Erro ao ler DOCX do Sanesul ({doc_url}): {docx_err}")
                    
                    # Salva o texto no cache de documentos em memória para os próximos nomes
                    _sanesul_doc_cache[doc_url] = text_content
            
            # 3. Verifica se o nome está presente no texto
            if text_content and name.lower() in text_content.lower():
                lines = text_content.split("\n")
                context_line = doc_title
                for line in lines:
                    if name.lower() in line.lower():
                        context_line = clean_text(line)
                        break
                
                results.append({
                    "name": name,
                    "source": "Sanesul (Concursos)",
                    "date": datetime.today().strftime("%d/%m/%Y"),
                    "link": doc_url,
                    "context": f"{doc_title} | {context_line}"[:300]
                })
            
            # Marca a URL como processada para este nome no banco de dados
            if doc_url in _sanesul_doc_cache:
                mark_url_processed(doc_url, name)
                
        logger.info(f"Busca Sanesul finalizada para {name}. Novas ocorrências encontradas: {len(results)}")
    except Exception as e:
        logger.error(f"Erro na busca da Sanesul para {name}: {e}")
    return results

_msgas_html_cache = None
_msgas_doc_cache = {}

def search_msgas(name):
    """
    Varredura na página de Concursos da MS Gás.
    Baixa e lê o conteúdo de novos PDFs/DOCX da listagem de 2025/2026.
    Usa cache em memória para evitar requisições repetidas e erro 429.
    """
    global _msgas_html_cache, _msgas_doc_cache
    import zipfile
    from database import is_url_processed, mark_url_processed
    
    results = []
    url = os.getenv("URL_MSGAS")
    if not url:
        logger.warning(f"URL_MSGAS não configurada no .env. Ignorando busca para {name}.")
        return results

    logger.info(f"Iniciando busca MS Gás para {name} na URL: {url}")
    try:
        # 1. Recupera a página principal (usa cache em memória se disponível)
        if _msgas_html_cache is None:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                _msgas_html_cache = response.content
            else:
                logger.warning(f"Resposta inválida da MS Gás para {name}: HTTP {response.status_code}")
                return results
        
        soup = BeautifulSoup(_msgas_html_cache, "html.parser")
        
        # Encontra todos os links de editais de 2025 e 2026
        links_to_check = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = clean_text(a.get_text())
            
            # Filtra por arquivos de uploads e restringe aos anos 2025/2026
            if "/Content/uploads/" in href and (href.lower().endswith(".pdf") or href.lower().endswith(".docx")):
                if any(year in text or year in href for year in ["2025", "2026"]):
                    full_url = urllib.parse.urljoin(url, href)
                    links_to_check.append((text, full_url))
        
        logger.info(f"MS Gás: {len(links_to_check)} arquivos identificados para 2025/2026.")
        
        for doc_title, doc_url in links_to_check:
            # Ignora URLs que já foram processadas para este nome
            if is_url_processed(doc_url, name):
                continue
            
            # 2. Obtém o texto do documento (usa cache em memória ou faz download)
            text_content = ""
            if doc_url in _msgas_doc_cache:
                text_content = _msgas_doc_cache[doc_url]
            else:
                local_path = get_local_file_path("msgas", doc_url)
                file_content = None
                if os.path.exists(local_path):
                    logger.info(f"MS Gás: Carregando arquivo do cache local: {local_path}")
                    try:
                        with open(local_path, "rb") as lf:
                            file_content = lf.read()
                    except Exception as fe:
                        logger.error(f"Erro ao ler arquivo local {local_path}: {fe}")
                
                if file_content is None:
                    logger.info(f"MS Gás: Baixando e analisando novo arquivo: {doc_title}")
                    try:
                        resp = requests.get(doc_url, headers=HEADERS, timeout=15)
                        if resp.status_code == 200:
                            file_content = resp.content
                            try:
                                with open(local_path, "wb") as lf:
                                    lf.write(file_content)
                            except Exception as fe:
                                logger.error(f"Erro ao salvar arquivo cache local {local_path}: {fe}")
                        else:
                            logger.warning(f"Erro ao baixar arquivo {doc_url}: HTTP {resp.status_code}")
                    except Exception as file_err:
                        logger.error(f"Erro ao baixar/processar arquivo {doc_url}: {file_err}")

                if file_content:
                    # Extrai texto com base na extensão
                    if doc_url.lower().endswith(".pdf"):
                        try:
                            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                                text_content = "\n".join([page.extract_text() or "" for page in pdf.pages])
                        except Exception as pdf_err:
                            logger.error(f"Erro ao ler PDF da MS Gás ({doc_url}): {pdf_err}")
                    elif doc_url.lower().endswith(".docx"):
                        try:
                            with zipfile.ZipFile(io.BytesIO(file_content)) as z:
                                xml_content = z.read("word/document.xml").decode("utf-8")
                                text_content = re.sub(r'<[^>]+>', '', xml_content)
                        except Exception as docx_err:
                            logger.error(f"Erro ao ler DOCX da MS Gás ({doc_url}): {docx_err}")
                    
                    # Salva o texto no cache de documentos em memória para os próximos nomes
                    _msgas_doc_cache[doc_url] = text_content
            
            # 3. Verifica se o nome está presente no texto
            if text_content and name.lower() in text_content.lower():
                lines = text_content.split("\n")
                context_line = doc_title
                for line in lines:
                    if name.lower() in line.lower():
                        context_line = clean_text(line)
                        break
                
                results.append({
                    "name": name,
                    "source": "MS Gás (Concursos)",
                    "date": datetime.today().strftime("%d/%m/%Y"),
                    "link": doc_url,
                    "context": f"{doc_title} | {context_line}"[:300]
                })
            
            # Marca a URL como processada para este nome no banco de dados
            if doc_url in _msgas_doc_cache:
                mark_url_processed(doc_url, name)
                
        logger.info(f"Busca MS Gás finalizada para {name}. Novas ocorrências encontradas: {len(results)}")
    except Exception as e:
        logger.error(f"Erro na busca da MS Gás para {name}: {e}")
    return results


def search_crbm(name):
    """
    Pesquisa no site do Conselho Regional de Biomedicina 1ª Região (CRBM1).
    Utiliza o sistema de pesquisa interno via query de WordPress.
    """
    results = []
    url = os.getenv("URL_CRBM")
    if not url:
        logger.warning(f"URL_CRBM não configurada no .env. Ignorando busca para {name}.")
        return results

        
    logger.info(f"Iniciando busca CRBM para {name} na URL: {url}")
    try:
        encoded_name = urllib.parse.quote_plus(name)
        search_url = f"{url}?s={encoded_name}"
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            articles = soup.find_all("article") or soup.find_all(class_=re.compile("post|entry|item"))
            for article in articles:
                text = clean_text(article.get_text())
                if name.lower() in text.lower():
                    link_tag = article.find("a", href=True)
                    link = link_tag["href"] if link_tag else search_url
                    results.append({
                        "name": name,
                        "source": "CRBM 1ª Região",
                        "date": datetime.today().strftime("%d/%m/%Y"),
                        "link": link,
                        "context": text[:300] + "..." if len(text) > 300 else text
                    })
            logger.info(f"Busca CRBM finalizada para {name}. Ocorrências encontradas: {len(results)}")
        else:
            logger.warning(f"Resposta inválida do CRBM para {name}: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na busca do CRBM 1 para {name}: {e}")
    return results


def search_dourados(name):
    """
    Pesquisa no Diário Oficial do Município de Dourados/MS.
    Acessa a pesquisa, encontra as páginas das edições correspondentes,
    depois localiza o link de download do PDF e faz a busca do nome no PDF.
    """
    from database import is_url_processed, mark_url_processed
    results = []
    base_url = os.getenv("URL_DOURADOS")
    if not base_url:
        logger.warning(f"URL_DOURADOS não configurada no .env. Ignorando busca para {name}.")
        return results

    encoded_name = urllib.parse.quote_plus(f'"{name}"')
    search_url = f"{base_url.rstrip('/')}/?s={encoded_name}"
    
    logger.info(f"Iniciando busca DO-Dourados para {name} na URL: {search_url}")
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Encontra todos os links de edições nos resultados
            edition_links = []
            for li in soup.select("div.licitacao-mes ul li, div.licitacao-mes li"):
                a_tag = li.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    title = clean_text(a_tag.get_text())
                    edition_links.append((title, href))
            
            # Se não achou na div.licitacao-mes, tenta buscar de forma genérica
            if not edition_links:
                for a_tag in soup.find_all("a", href=True):
                    if "edicao-" in a_tag["href"] or "edição" in a_tag.get_text().lower():
                        title = clean_text(a_tag.get_text())
                        edition_links.append((title, a_tag["href"]))
                        
            # Remove duplicados mantendo a ordem
            seen = set()
            edition_links = [x for x in edition_links if not (x[1] in seen or seen.add(x[1]))]

            logger.info(f"DO-Dourados: {len(edition_links)} edições encontradas para analisar.")
            
            for title_text, ed_url in edition_links:
                try:
                    ed_resp = requests.get(ed_url, headers=HEADERS, timeout=15)
                    if ed_resp.status_code == 200:
                        ed_soup = BeautifulSoup(ed_resp.content, "html.parser")
                        
                        pdf_url = None
                        download_a = ed_soup.find("a", string=re.compile("Download do Arquivo", re.I))
                        if download_a and download_a.get("href"):
                            pdf_url = download_a["href"]
                        else:
                            for a in ed_soup.find_all("a", href=True):
                                if "uploads" in a["href"] and a["href"].lower().endswith(".pdf"):
                                    pdf_url = a["href"]
                                    break
                                    
                        if not pdf_url:
                            logger.warning(f"DO-Dourados: Não foi possível extrair a URL do PDF em {ed_url}")
                            continue
                            
                        if is_url_processed(pdf_url, name):
                            continue
                            
                        pub_date = datetime.today().strftime("%d/%m/%Y")
                        date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', title_text)
                        if date_match:
                            pub_date = date_match.group(0)
                        else:
                            url_date_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', pdf_url)
                            if url_date_match:
                                pub_date = f"{url_date_match.group(1)}/{url_date_match.group(2)}/{url_date_match.group(3)}"
                        
                        local_path = get_local_file_path("dourados", pdf_url)
                        file_content = None
                        if os.path.exists(local_path):
                            logger.info(f"DO-Dourados: Carregando PDF do cache local: {local_path}")
                            try:
                                with open(local_path, "rb") as lf:
                                    file_content = lf.read()
                            except Exception as fe:
                                logger.error(f"Erro ao ler arquivo local {local_path}: {fe}")
                                
                        if file_content is None:
                            logger.info(f"DO-Dourados: Baixando PDF da edição: {pdf_url}")
                            pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=15)
                            if pdf_resp.status_code == 200:
                                file_content = pdf_resp.content
                                try:
                                    with open(local_path, "wb") as lf:
                                        lf.write(file_content)
                                except Exception as fe:
                                    logger.error(f"Erro ao salvar arquivo cache local {local_path}: {fe}")
                            else:
                                logger.warning(f"Erro ao baixar PDF {pdf_url}: HTTP {pdf_resp.status_code}")
                                
                        if file_content:
                            text_content = ""
                            try:
                                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                                    text_content = "\n".join([page.extract_text() or "" for page in pdf.pages])
                            except Exception as pdf_err:
                                logger.error(f"Erro ao ler PDF do DO-Dourados ({pdf_url}): {pdf_err}")
                                
                            if text_content and name.lower() in text_content.lower():
                                lines = text_content.split("\n")
                                context_line = title_text
                                for line in lines:
                                    if name.lower() in line.lower():
                                        context_line = clean_text(line)
                                        break
                                        
                                results.append({
                                    "name": name,
                                    "source": "Diário Oficial de Dourados",
                                    "date": pub_date,
                                    "link": pdf_url,
                                    "context": f"{title_text} | {context_line}"[:300]
                                })
                                
                        mark_url_processed(pdf_url, name)
                except Exception as ed_err:
                    logger.error(f"Erro ao processar edição {ed_url}: {ed_err}")
                    
            logger.info(f"Busca DO-Dourados finalizada para {name}. Ocorrências encontradas: {len(results)}")
        else:
            logger.warning(f"Resposta inválida de DO-Dourados: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na busca do DO-Dourados para {name}: {e}")
    return results


def scan_all_sources(names, active_sources=None):
    """
    Executa a varredura das fontes selecionadas para a lista de nomes fornecida.
    """
    if active_sources is None:
        active_sources = {"dou": True, "doms": True, "ifms": True, "sanesul": True, "msgas": True, "crbm": True, "dourados": True}
        
    all_results = []
    logger.info(f"=== INICIANDO VARREDURA COMPLETA ({len(names)} nomes) ===")
    for name in names:
        name = name.strip()
        if not name:
            continue
        if active_sources.get("dou"):
            all_results.extend(search_dou(name))
        if active_sources.get("doms"):
            all_results.extend(search_doms(name))
        if active_sources.get("ifms"):
            all_results.extend(search_ifms(name))
        if active_sources.get("sanesul"):
            all_results.extend(search_sanesul(name))
        if active_sources.get("msgas"):
            all_results.extend(search_msgas(name))
        if active_sources.get("crbm"):
            all_results.extend(search_crbm(name))
        if active_sources.get("dourados"):
            all_results.extend(search_dourados(name))
    logger.success(f"=== VARREDURA COMPLETA FINALIZADA. TOTAL DE OCORRÊNCIAS ENCONTRADAS: {len(all_results)} ===")
    return all_results


