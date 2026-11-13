# -*- coding: utf-8 -*-
"""
Módulo de monitoramento e integração de atualizações e editais de retificação.
Suporta:
- Bancas modernas com API (ex: Cebraspe - apis.cebraspe.org.br)
- Portais genéricos com links HTML (BeautifulSoup / requests)
- Download e persistência de documentos de retificação
- Mesclagem inteligente de cronogramas e tópicos verticalizados sem perder dados anteriores
"""
import re
import os
import requests
from urllib.parse import urlparse, urljoin
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.logger import logger
from src.config import EDITAIS_DIR, get_edital_folder
from src.database.db import (
    get_connection,
    get_edital_by_id,
    save_edital_documento,
    get_documentos_by_edital,
    get_cronograma_by_edital,
    save_cronograma_items,
    get_verticalizado_by_edital,
    save_verticalizado_items
)
from src.editais.extractor_local import (
    extract_cronograma_local,
    extract_verticalizado_local,
    discover_cargos_in_pdf
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def sanitize_friendly_filename(titulo: str, max_len: int = 120) -> str:
    """Gera um nome de arquivo amigável, limpo e legível a partir do título do documento."""
    import unicodedata
    t = unicodedata.normalize('NFKD', titulo or "documento").encode('ASCII', 'ignore').decode('utf-8')
    t = re.sub(r'[\\/*?:\'\"<>|]', '_', t)
    t = re.sub(r'[\s_]+', '_', t).strip('._')
    base = t[:max_len] if t else "documento"
    return f"{base}.pdf"


def is_cebraspe_url(url: str) -> bool:
    """Verifica se a URL pertence ao portal Cebraspe."""
    return "cebraspe.org.br" in (url or "").lower()


def is_fapec_url(url: str) -> bool:
    """Verifica se a URL pertence ao portal da FAPEC."""
    return "fapec.org" in (url or "").lower() or "fundacaofapec.org.br" in (url or "").lower()


def is_ufms_concursos_url(url: str) -> bool:
    """Verifica se a URL pertence ao portal oficial de concursos da UFMS."""
    return "concursos.ufms.br" in (url or "").lower()


def extract_cebraspe_slug(url: str) -> Optional[str]:
    """
    Extrai o slug do concurso da URL do Cebraspe com validação alfanumérica estrita.
    Ex: 'https://www.cebraspe.org.br/concursos/cgu_26_affc' -> 'cgu_26_affc'
    """
    match = re.search(r'/concursos/([^/?#]+)', url or "", re.IGNORECASE)
    if match:
        cand = match.group(1).strip()
        if re.fullmatch(r'[A-Za-z0-9_-]{2,80}', cand):
            return cand
    return None


def fetch_cebraspe_documents(url: str) -> List[Dict[str, Any]]:
    """
    Consulta a API oficial do Cebraspe para obter todos os editais,
    retificações e comunicados em PDF.
    """
    slug = extract_cebraspe_slug(url)
    if not slug:
        logger.warning(f"Não foi possível extrair o slug da URL Cebraspe: {url}")
        return []

    api_url = f"https://apis.cebraspe.org.br/cebraspe/eventos/{slug}"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        arquivos = data.get("arquivosEdital", [])

        docs = []
        for arq in arquivos:
            ext = str(arq.get("tipoExtensaoArquivo", "")).lower().replace("_.", ".").strip()
            # Focamos em arquivos PDF
            if ext != ".pdf":
                continue

            nome_arquivo = arq.get("nomeArquivo", "").strip()
            descricao = arq.get("descricaoArquivo", "").strip()
            data_arq = arq.get("dataArquivo", "").strip()

            # URL pública do CDN do Cebraspe
            download_url = f"https://cdn.cebraspe.org.br/concursos/{slug}/arquivos/{nome_arquivo}"

            # Classificação semântica do tipo de documento
            desc_lower = descricao.lower()
            tipo = "Outro"
            if "retifica" in desc_lower:
                tipo = "Retificação"
            elif "abertura" in desc_lower or "edital nº 1" in desc_lower or "edital de abertura" in desc_lower:
                tipo = "Edital de Abertura"
            elif "comunicado" in desc_lower or "aviso" in desc_lower:
                tipo = "Comunicado"
            elif "gabarito" in desc_lower:
                tipo = "Gabarito"
            elif "resultado" in desc_lower:
                tipo = "Resultado"

            friendly_filename = sanitize_friendly_filename(descricao)

            docs.append({
                "titulo": descricao,
                "tipo": tipo,
                "arquivo_nome": friendly_filename,
                "data_publicacao": data_arq,
                "url_download": download_url,
                "banca": "Cebraspe"
            })

        return docs
    except Exception as e:
        logger.error(f"Erro ao buscar documentos Cebraspe ({api_url}): {e}")
        return []


def fetch_fapec_documents(url: str) -> List[Dict[str, Any]]:
    """
    Scraper especializado para a FAPEC (portal.concurso.fundacaofapec.org.br ou fundacaofapec.org.br).
    Extrai editais, retificações e comunicados listados na página do concurso.
    """
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        docs = []
        items = soup.find_all(class_="list-group-item")
        for it in items:
            a = it.find("a", href=lambda h: h and ("arquivo.php" in h or ".pdf" in h.lower()))
            if not a:
                continue

            raw_text = it.get_text(" ", strip=True)
            clean_t = re.sub(r'\s*DOWNLOAD\s*', '', raw_text, flags=re.IGNORECASE).strip()
            
            # Extrai data inicial se presente (ex: "30/10/2026 EDITAL...")
            data_pub = ""
            m_date = re.match(r'^(\d{2}/\d{2}/\d{4})\s*(.*)', clean_t)
            if m_date:
                data_pub, titulo = m_date.groups()
            else:
                titulo = clean_t or a.get_text(strip=True) or "Documento FAPEC"

            href = a["href"].strip()
            download_url = urljoin(url, href)

            desc_lower = titulo.lower()
            tipo = "Outro"
            if "retifica" in desc_lower:
                tipo = "Retificação"
            elif "abertura" in desc_lower or "edital nº 1" in desc_lower:
                tipo = "Edital de Abertura"
            elif "comunicado" in desc_lower or "aviso" in desc_lower:
                tipo = "Comunicado"
            elif "gabarito" in desc_lower:
                tipo = "Gabarito"
            elif "resultado" in desc_lower:
                tipo = "Resultado"

            docs.append({
                "titulo": titulo,
                "tipo": tipo,
                "arquivo_nome": sanitize_friendly_filename(titulo),
                "data_publicacao": data_pub,
                "url_download": download_url,
                "banca": "FAPEC"
            })
        return docs
    except Exception as e:
        logger.error(f"Erro ao buscar documentos FAPEC ({url}): {e}")
        return []


def _extract_ufms_news_documents(news_url: str) -> List[Dict[str, Any]]:
    """Extrai documentos PDF associados a uma página de notícia específica de concursos.ufms.br."""
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(news_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        docs = []
        # Localiza a data de publicação no rodapé se disponível
        data_pub = ""
        footer_text = soup.get_text()
        date_match = re.search(r'divulgada\s+em\s+(\d{2}-\d{2}-\d{4})', footer_text, re.IGNORECASE)
        if date_match:
            data_pub = date_match.group(1).replace("-", "/")

        # Contexto textual da notícia (título da notícia e resumo)
        news_title = ""
        panel_body = soup.find("div", class_="panel-body")
        if panel_body:
            h4_info = panel_body.find("h4", class_="text-info")
            if h4_info:
                news_title = h4_info.get_text(" ", strip=True)

        for tr in soup.find_all("tr"):
            link_a = tr.find("a", href=lambda h: h and "documents/download" in h)
            if not link_a:
                continue
            download_url = urljoin(news_url, link_a["href"].strip())

            # O título fica na coluna TD ao lado ou no texto da linha
            tds = tr.find_all("td")
            doc_label = ""
            if len(tds) >= 2:
                doc_label = tds[1].get_text(strip=True)
            if not doc_label:
                doc_label = tr.get_text(" ", strip=True)

            # Título completo e descritivo
            if news_title and news_title.lower() not in doc_label.lower():
                titulo = f"{doc_label} - {news_title}".strip(" -")
            else:
                titulo = doc_label or news_title or "Documento UFMS"

            # Classificação semântica considerando tanto o nome do arquivo quanto o assunto da notícia
            combined_text = f"{doc_label} {news_title}".lower()
            tipo = "Outro"
            if "retifica" in combined_text:
                tipo = "Retificação"
            elif "indeferid" in combined_text or "deferid" in combined_text or "inscri" in combined_text:
                tipo = "Inscrições"
            elif "atendimento especial" in combined_text:
                tipo = "Atendimento Especial"
            elif "pcd" in combined_text or "autodeclara" in combined_text:
                tipo = "Cotas / PcD"
            elif "isenção" in combined_text or "isencao" in combined_text:
                tipo = "Isenção"
            elif "gabarito" in combined_text:
                tipo = "Gabarito"
            elif "resultado" in combined_text or "classifica" in combined_text:
                tipo = "Resultado"
            elif "convoca" in combined_text:
                tipo = "Convocação"
            elif "regulamento" in combined_text:
                tipo = "Regulamento"
            elif "abertura" in combined_text or "edital nº 1" in combined_text or "edital de abertura" in combined_text:
                tipo = "Edital de Abertura"
            elif "edital" in combined_text:
                tipo = "Edital"

            docs.append({
                "titulo": titulo,
                "tipo": tipo,
                "arquivo_nome": sanitize_friendly_filename(titulo),
                "data_publicacao": data_pub,
                "url_download": download_url,
                "banca": "UFMS"
            })
        return docs
    except Exception as e:
        logger.error(f"Erro ao extrair documentos da notícia UFMS ({news_url}): {e}")
        return []


def fetch_ufms_concursos_documents(url: str) -> List[Dict[str, Any]]:
    """
    Scraper oficial para o portal de concursos da UFMS (concursos.ufms.br).
    Suporta URLs de notícias (front/news/view/<id>), setup de concurso (front/setup/<id>)
    ou a página de eventos/editais (front/events).
    """
    try:
        from bs4 import BeautifulSoup
        clean_url = (url or "").strip()
        all_docs: List[Dict[str, Any]] = []
        seen_downloads = set()

        # Caso 1: URL direta de notícia (/front/news/view/<id>)
        if "news/view" in clean_url:
            news_docs = _extract_ufms_news_documents(clean_url)
            for d in news_docs:
                if d["url_download"] not in seen_downloads:
                    seen_downloads.add(d["url_download"])
                    all_docs.append(d)

            # Tenta descobrir o setup pai ou links correlatos via front/events se disponível
            try:
                events_resp = requests.get("https://www.concursos.ufms.br/front/events", headers=HEADERS, timeout=10)
                if events_resp.status_code == 200:
                    ev_soup = BeautifulSoup(events_resp.text, "html.parser")
                    # Encontra a linha que referencia esta notícia
                    target_id = clean_url.split("/")[-1]
                    for tr in ev_soup.find_all("tr"):
                        if f"news/view/{target_id}" in str(tr):
                            setup_link = tr.find("a", href=lambda h: h and "setup/" in h)
                            if setup_link:
                                setup_url = urljoin("https://www.concursos.ufms.br", setup_link["href"])
                                # Busca notícias adicionais dentro desse setup
                                sub_docs = fetch_ufms_concursos_documents(setup_url)
                                for sd in sub_docs:
                                    if sd["url_download"] not in seen_downloads:
                                        seen_downloads.add(sd["url_download"])
                                        all_docs.append(sd)
                            break
            except Exception as e:
                logger.debug(f"Não foi possível obter setup associado à notícia {clean_url}: {e}")

            return all_docs

        # Caso 2: URL de Setup (/front/setup/<id>)
        if "setup/" in clean_url:
            resp = requests.get(clean_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Itera sobre todas as notícias listadas no setup
            news_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if "news/view" in href:
                    full_news = urljoin(clean_url, href)
                    if full_news not in news_links:
                        news_links.append(full_news)

            for n_url in news_links:
                docs = _extract_ufms_news_documents(n_url)
                for d in docs:
                    if d["url_download"] not in seen_downloads:
                        seen_downloads.add(d["url_download"])
                        all_docs.append(d)

            return all_docs

        # Caso 3: URL genérica ou /front/events
        resp = requests.get(clean_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tr in soup.find_all("tr"):
            for a in tr.find_all("a", href=lambda h: h and "documents/download" in h):
                d_url = urljoin(clean_url, a["href"].strip())
                if d_url not in seen_downloads:
                    seen_downloads.add(d_url)
                    tit = tr.get_text(" ", strip=True)[:120]
                    all_docs.append({
                        "titulo": tit,
                        "tipo": "Edital",
                        "arquivo_nome": sanitize_friendly_filename(tit),
                        "data_publicacao": "",
                        "url_download": d_url,
                        "banca": "UFMS"
                    })
        return all_docs
    except Exception as e:
        logger.error(f"Erro ao buscar documentos UFMS Concursos ({url}): {e}")
        return []


def fetch_generic_html_documents(url: str) -> List[Dict[str, Any]]:
    """
    Crawler genérico para portais de concursos que expõem links HTML diretos para PDFs.
    """
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        docs = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)
            if not text:
                continue

            if href.lower().endswith(".pdf") or "download" in href.lower() or "arquivo" in href.lower():
                full_url = urljoin(url, href)
                text_lower = text.lower()
                tipo = "Outro"
                if "retifica" in text_lower:
                    tipo = "Retificação"
                elif "abertura" in text_lower or "edital" in text_lower:
                    tipo = "Edital"
                elif "cronograma" in text_lower:
                    tipo = "Cronograma"
                elif "comunicado" in text_lower:
                    tipo = "Comunicado"

                docs.append({
                    "titulo": text[:150],
                    "tipo": tipo,
                    "arquivo_nome": sanitize_friendly_filename(text[:120]),
                    "data_publicacao": "",
                    "url_download": full_url,
                    "banca": "Outra"
                })
        return docs
    except Exception as e:
        logger.error(f"Erro ao buscar documentos via HTML genérico ({url}): {e}")
        return []


def is_document_same_as_original(doc: Dict[str, Any], edital: Dict[str, Any]) -> bool:
    """
    Verifica se um documento retornado pelo portal da banca corresponde
    ao edital original de abertura que já foi cadastrado no sistema.
    """
    nome_original = (edital.get("arquivo_nome") or "").lower().strip()
    caminho_original = edital.get("arquivo_path") or ""
    
    # 1. Comparação direta de nomes de arquivo sanitizados
    doc_arq = (doc.get("arquivo_nome") or "").lower().strip()
    if nome_original:
        orig_clean = re.sub(r'[\W_]+', '', nome_original.replace(".pdf", ""))
        doc_clean = re.sub(r'[\W_]+', '', doc_arq.replace(".pdf", ""))
        if orig_clean and doc_clean and (orig_clean in doc_clean or doc_clean in orig_clean):
            return True

    # 2. Tipo explícito como Edital de Abertura / Edital Inicial
    tipo_doc = (doc.get("tipo") or "").lower().strip()
    tit_doc = (doc.get("titulo") or "").lower().strip()
    
    eh_tipo_abertura = (
        tipo_doc == "edital de abertura" or
        "abertura" in tit_doc or
        "edital nº 1" in tit_doc or
        "edital n. 001" in tit_doc or
        "edital nº 001" in tit_doc or
        "edital 01" in tit_doc or
        "edital n.º 001" in tit_doc or
        "edital progep/ufms" in tit_doc
    )

    # Não pode ser marcado como abertura se for explicitamente retificação
    if "retifica" in tit_doc or "retificação" in tipo_doc:
        eh_tipo_abertura = False

    if eh_tipo_abertura:
        # Se na página da banca o documento é a abertura e o edital já tem um PDF original cadastrado
        if caminho_original:
            return True

    return False


def check_for_updates(edital_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Verifica atualizações e retificações para um edital.
    Retorna: (novos_documentos, documentos_ja_registrados)
    """
    edital = get_edital_by_id(edital_id)
    if not edital or not edital.get("link_oficial"):
        return [], []

    url = edital["link_oficial"].strip()
    if is_cebraspe_url(url):
        remote_docs = fetch_cebraspe_documents(url)
    elif is_fapec_url(url):
        remote_docs = fetch_fapec_documents(url)
    elif is_ufms_concursos_url(url):
        remote_docs = fetch_ufms_concursos_documents(url)
    else:
        remote_docs = fetch_generic_html_documents(url)

    registrados = get_documentos_by_edital(edital_id)
    urls_registradas = {d["url_origem"] for d in registrados if d.get("url_origem")}
    titulos_registrados = {d["titulo"].strip().lower() for d in registrados}

    novos = []
    for doc in remote_docs:
        url_d = doc["url_download"]
        tit = doc["titulo"].strip().lower()
        if url_d in urls_registradas or tit in titulos_registrados:
            continue
        # Se for o próprio edital de abertura original já cadastrado, ignora
        if is_document_same_as_original(doc, edital):
            continue
        novos.append(doc)

    return novos, registrados


def download_document(url_download: str, file_name_hint: str, edital_id: Optional[int] = None) -> Optional[str]:
    """
    Faz download de um arquivo e salva no subdiretório do concurso (ex: uploads/editais/{slug}/) com nome seguro.
    Inclui validação anti-SSRF, sanitização contra Path Traversal e limite de tamanho contra DoS.
    Retorna o caminho absoluto do arquivo salvo.
    """
    from src.security import is_safe_external_url, sanitize_filename, resolve_safe_path, MAX_DOWNLOAD_BYTES

    try:
        if not is_safe_external_url(url_download):
            logger.error(f"Download bloqueado por política anti-SSRF: {url_download}")
            return None

        resp = requests.get(url_download, headers=HEADERS, timeout=30)
        resp.raise_for_status()

        content = resp.content or b""
        if len(content) > MAX_DOWNLOAD_BYTES:
            logger.error(f"Arquivo excedeu o limite máximo permitido ({MAX_DOWNLOAD_BYTES} bytes): {url_download}")
            return None

        clean_hint = sanitize_filename(file_name_hint or "documento.pdf", default_ext=".pdf")
        safe_name = f"{int(datetime.now().timestamp())}_{clean_hint}"
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"

        # Determina a pasta de destino do concurso
        if edital_id:
            edital_info = get_edital_by_id(edital_id)
            if edital_info:
                target_dir = get_edital_folder(
                    titulo=edital_info.get("titulo", ""),
                    ano=edital_info.get("ano", 2026),
                    link_oficial=edital_info.get("link_oficial", "")
                )
            else:
                target_dir = EDITAIS_DIR
        else:
            target_dir = EDITAIS_DIR

        dest_path = resolve_safe_path(target_dir, safe_name)
        with open(dest_path, "wb") as f:
            f.write(content)

        return str(dest_path)
    except Exception as e:
        logger.error(f"Erro ao baixar documento ({url_download}): {e}")
        return None


def merge_retificacao_cronograma(edital_id: int, new_items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Mescla novos itens de cronograma extraídos de uma retificação:
    - Se um evento já existe (similaridade de texto ou correspondência de palavras-chave),
      atualiza a data e marca com a tag '[Retificado]'.
    - Se for um evento novo (ex: Atendimento Especializado que não constava), insere.
    Retorna estatísticas: {'atualizados': n, 'inseridos': n}
    """
    current_items = get_cronograma_by_edital(edital_id)
    stats = {"atualizados": 0, "inseridos": 0}

    # Normalizador semântico para matching de eventos
    def norm(text: str) -> str:
        t = re.sub(r'\[retificado\]', '', text, flags=re.IGNORECASE)
        t = re.sub(r'[^\w\s]', ' ', t.lower())
        return ' '.join(t.split())

    conn = get_connection()
    cursor = conn.cursor()

    try:
        for new_item in new_items:
            n_ev = new_item.get("evento", "").strip()
            if not n_ev or n_ev in ["[...]", "..."]:
                continue

            n_norm = norm(n_ev)
            tokens_n = set(n_norm.split())

            matched_id = None
            best_score = 0.0

            for curr in current_items:
                c_ev = curr.get("evento", "")
                c_norm = norm(c_ev)
                tokens_c = set(c_norm.split())

                # Se for idêntico
                if n_norm == c_norm:
                    matched_id = curr["id"]
                    best_score = 1.0
                    break

                # Diferenciador semântico essencial:
                # Eventos de "atendimento especializado" NUNCA podem casar com "isenção de taxa"
                if ("atendimento especializado" in n_norm) != ("atendimento especializado" in c_norm):
                    continue
                if ("isenção" in n_norm or "isencao" in n_norm) != ("isenção" in c_norm or "isencao" in c_norm):
                    continue
                if ("gabarito" in n_norm) != ("gabarito" in c_norm):
                    continue
                if ("discursiva" in n_norm) != ("discursiva" in c_norm):
                    continue

                # Jaccard similarity entre os tokens
                intersection = tokens_n.intersection(tokens_c)
                union = tokens_n.union(tokens_c)
                score = len(intersection) / len(union) if union else 0.0

                if score > best_score and score >= 0.60:
                    best_score = score
                    matched_id = curr["id"]

            if matched_id:
                # Atualiza apenas os eventos que foram alterados pela retificação
                novo_evento_tit = n_ev if "[Retificado]" in n_ev else f"{n_ev} [Retificado]"
                cursor.execute("""
                    UPDATE edital_cronograma
                    SET evento = ?,
                        data_inicio = ?,
                        data_fim = ?,
                        data_limite = ?,
                        observacao = ?
                    WHERE id = ?
                """, (
                    novo_evento_tit,
                    new_item.get("data_inicio", ""),
                    new_item.get("data_fim", ""),
                    new_item.get("data_limite", ""),
                    f"Retificado em documento anexo. {new_item.get('observacao', '')}".strip(),
                    matched_id
                ))
                stats["atualizados"] += 1
            else:
                # Insere novo evento no cronograma se realmente for inédito
                novo_evento_tit = n_ev if "[Retificado]" in n_ev else f"{n_ev} [Retificado]"
                cursor.execute("""
                    INSERT INTO edital_cronograma (
                        edital_id, evento, data_inicio, data_fim, data_limite, status, observacao, ordem
                    ) VALUES (?, ?, ?, ?, ?, 'Previsto', ?, ?)
                """, (
                    edital_id,
                    novo_evento_tit,
                    new_item.get("data_inicio", ""),
                    new_item.get("data_fim", ""),
                    new_item.get("data_limite", ""),
                    f"Adicionado via retificação. {new_item.get('observacao', '')}".strip(),
                    len(current_items) + stats["inseridos"] + 1
                ))
                stats["inseridos"] += 1

        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao mesclar retificação no cronograma do edital {edital_id}: {e}")
    finally:
        conn.close()

    return stats


def merge_retificacao_verticalizado(edital_id: int, new_topics: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Mescla novos tópicos ao edital verticalizado sem apagar o progresso de estudos já existente.
    Retorna estatísticas: {'adicionados': n, 'ja_existentes': n}
    """
    current_topics = get_verticalizado_by_edital(edital_id)
    existing_keys = {
        (t.get("disciplina", "").strip().lower(), t.get("topico", "").strip().lower())
        for t in current_topics
    }

    stats = {"adicionados": 0, "ja_existentes": 0}
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for t in new_topics:
            disc = t.get("disciplina", "").strip()
            topico = t.get("topico", "").strip()
            if not disc or not topico:
                continue

            key = (disc.lower(), topico.lower())
            if key in existing_keys:
                stats["ja_existentes"] += 1
                continue

            cursor.execute("""
                INSERT INTO edital_verticalizado (
                    edital_id, disciplina, topico, subtopico, peso,
                    questoes_previstas, teoria_concluida, resumo_concluido,
                    questoes_concluidas, revisao_1, revisao_2, revisao_3,
                    observacao, ordem
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, ?, ?)
            """, (
                edital_id,
                disc,
                f"{topico} [Novo/Retificado]",
                t.get("subtopico", ""),
                t.get("peso", 1.0),
                t.get("questoes_previstas", 0),
                f"Incluído via retificação. {t.get('observacao', '')}".strip(),
                len(current_topics) + stats["adicionados"] + 1
            ))
            existing_keys.add(key)
            stats["adicionados"] += 1

        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao mesclar retificação no verticalizado do edital {edital_id}: {e}")
    finally:
        conn.close()

    return stats


def process_retificacao_pdf(edital_id: int, pdf_path: str, doc_titulo: str) -> Dict[str, Any]:
    """
    Processa um PDF de retificação (local ou recém baixado) e aplica as atualizações
    no cronograma e no conteúdo programático.
    """
    edital = get_edital_by_id(edital_id)
    cargo_filtro = edital.get("cargo", "") if edital else ""

    # Extrai cronograma e verticalizado
    crono_items = extract_cronograma_local(pdf_path)
    vert_items = extract_verticalizado_local(pdf_path, cargo_filtro=cargo_filtro)

    crono_stats = {"atualizados": 0, "inseridos": 0}
    if crono_items:
        crono_stats = merge_retificacao_cronograma(edital_id, crono_items)

    vert_stats = {"adicionados": 0, "ja_existentes": 0}
    if vert_items:
        vert_stats = merge_retificacao_verticalizado(edital_id, vert_items)

    resumo_parts = []
    if crono_stats["atualizados"] or crono_stats["inseridos"]:
        resumo_parts.append(f"Cronograma: {crono_stats['atualizados']} atualizados, {crono_stats['inseridos']} novos")
    if vert_stats["adicionados"]:
        resumo_parts.append(f"Verticalizado: {vert_stats['adicionados']} tópicos adicionados")

    resumo = "; ".join(resumo_parts) if resumo_parts else "Nenhuma alteração detectada nas seções de cronograma/disciplinas."
    return {
        "crono_stats": crono_stats,
        "vert_stats": vert_stats,
        "resumo": resumo
    }

