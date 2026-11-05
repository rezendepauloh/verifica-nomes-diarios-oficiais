# -*- coding: utf-8 -*-
"""
Extrator avançado e robusto para editais de concursos públicos:
- Suporta bancas de estilo Cebraspe (tópicos numerados 1, 1.1, 2...),
  FAPEC/Vunesp/FGV/Consulplan (disciplinas gerais e cargos específicos),
  e editais com cronogramas em formato tabular ou descritivo.
- Permite auto-descoberta de cargos disponíveis no PDF.
"""
import re
from typing import List, Dict, Any, Tuple
from src.logger import logger
from src.editais.pdf_parser import extract_full_text_by_pages

MESES_BR = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06",
    "julho": "07", "agosto": "08", "setembro": "09",
    "outubro": "10", "novembro": "11", "dezembro": "12"
}

REGEX_PERIODO = re.compile(
    r'(\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)?)\s*(?:a|à|e|ate|até)\s*(\d{1,2}/\d{1,2}/\d{4})',
    re.IGNORECASE
)

REGEX_DATA_EXTENSO = re.compile(
    r'(\d{1,2})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(\d{4}))?',
    re.IGNORECASE
)

REGEX_DATA_NUMERICA = re.compile(
    r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b'
)

def parse_date_smart(val: str) -> Tuple[str, str, str]:
    """
    Interpreta datas simples, intervalos ou datas por extenso.
    Retorna: (data_inicio, data_fim, data_exibicao)
    """
    if not val:
        return "", "", ""
    val_clean = val.strip().replace("\n", " ")

    # 1. Intervalos do tipo: '10 a 16/10/2026', '10/10 a 4/11/2026', '27 e 28/10/2026'
    m_range = REGEX_PERIODO.search(val_clean)
    if m_range:
        inicio_raw, fim_raw = m_range.groups()
        parts_fim = fim_raw.split('/')
        ano = parts_fim[2]
        if len(ano) == 2:
            ano = "20" + ano
        mes_fim = f"{int(parts_fim[1]):02d}"
        dia_fim = f"{int(parts_fim[0]):02d}"

        if '/' in inicio_raw:
            p_ini = inicio_raw.split('/')
            dia_ini = f"{int(p_ini[0]):02d}"
            mes_ini = f"{int(p_ini[1]):02d}"
            if len(p_ini) > 2:
                ano_ini = p_ini[2]
                if len(ano_ini) == 2:
                    ano_ini = "20" + ano_ini
                ano = ano_ini
        else:
            dia_ini = f"{int(inicio_raw):02d}"
            mes_ini = mes_fim

        dt_inicio = f"{dia_ini}/{mes_ini}/{ano}"
        dt_fim = f"{dia_fim}/{mes_fim}/{ano}"
        return dt_inicio, dt_fim, f"{dt_inicio} a {dt_fim}"

    # 2. Data numérica única DD/MM/YYYY
    m_single = REGEX_DATA_NUMERICA.search(val_clean)
    if m_single:
        dia, mes, ano = m_single.groups()
        if len(ano) == 2:
            ano = "20" + ano
        dt = f"{int(dia):02d}/{int(mes):02d}/{ano}"
        return dt, dt, dt

    # 3. Data por extenso: '15 de setembro de 2025'
    m_ext = REGEX_DATA_EXTENSO.search(val_clean)
    if m_ext:
        dia, mes_nome, ano = m_ext.groups()
        mes_cod = MESES_BR.get(mes_nome.lower(), "01")
        ano_val = ano if ano else "2026"
        dt = f"{int(dia):02d}/{mes_cod}/{ano_val}"
        return dt, dt, dt

    return val_clean[:15], val_clean[:15], val_clean[:30]


def clean_event_text(text: str) -> str:
    """Limpa e formata o texto de um evento do cronograma."""
    cleaned = re.sub(r'^\s*\d+[\.\)]\s*', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# ==============================================================================
# 1. EXTRAÇÃO DE CRONOGRAMA
# ==============================================================================

def is_cronograma_page(text: str) -> bool:
    """Verifica se a página pertence ao cronograma oficial do edital."""
    text_up = text.upper()
    keywords = [
        "CRONOGRAMA PREVISTO", "ANEXO I\nCRONOGRAMA", "ANEXO I - CRONOGRAMA",
        "ANEXO II - CRONOGRAMA", "ANEXO II\nCRONOGRAMA", "CALENDÁRIO DE ATIVIDADES",
        "CRONOGRAMA"
    ]
    return any(k in text_up for k in keywords)


def find_table_cols(table: List[List[str]]) -> Tuple[int, int]:
    """Descobre confiavelmente as colunas de Evento e de Data de uma tabela de cronograma."""
    event_col = -1
    date_col = -1

    for row in table[:3]:
        row_clean = [str(c or '').strip().lower() for c in row if c is not None]
        for c_idx, val in enumerate(row_clean):
            if val in ['atividade', 'etapa', 'evento', 'fase', 'descrição', 'atividades', 'etapas', 'item']:
                if val != 'item':
                    event_col = c_idx
            elif any(k in val for k in ['datas previstas', 'período', 'periodo', 'data', 'datas', 'prazo']):
                if c_idx != event_col:
                    date_col = c_idx

    if event_col != -1 and date_col != -1 and event_col != date_col:
        return event_col, date_col

    # Fallback por inspeção dos dados
    for row in table:
        non_empty = [c for c in row if c and str(c).strip()]
        if len(non_empty) >= 2:
            e_candidate = -1
            d_candidate = -1
            for i, val in enumerate(row):
                if not val:
                    continue
                v_str = str(val).strip()
                if any(k in v_str.lower() for k in ['inscriç', 'prova', 'gabarito', 'resultado', 'isenç', 'recurso']):
                    e_candidate = i
                if REGEX_DATA_NUMERICA.search(v_str) or REGEX_PERIODO.search(v_str):
                    d_candidate = i
            if e_candidate != -1 and d_candidate != -1 and e_candidate != d_candidate:
                return e_candidate, d_candidate

    return -1, -1


def extract_cronograma_from_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    """Extrai linhas estruturadas de cronograma a partir de tabelas."""
    items = []
    for table in tables:
        if not table or len(table) < 2:
            continue

        event_col, date_col = find_table_cols(table)
        if event_col == -1 or date_col == -1:
            continue

        for row in table:
            if len(row) <= max(event_col, date_col):
                continue
            evento_raw = str(row[event_col] or "").strip().replace("\n", " ")
            data_raw = str(row[date_col] or "").strip().replace("\n", " ")

            if not evento_raw or not data_raw:
                continue

            # Pula linha de cabeçalho ou marcadores de elipse [...]
            if evento_raw.lower() in ["atividade", "etapa", "evento", "descrição", "atividades", "etapas"] or evento_raw in ["[...]", "..."]:
                continue

            dt_inicio, dt_fim, dt_exibicao = parse_date_smart(data_raw)
            if not dt_inicio or dt_inicio.lower() in ["datas previstas", "data", "datas", "período"]:
                continue

            evento = clean_event_text(evento_raw)
            items.append({
                "evento": evento,
                "data_inicio": dt_exibicao,
                "data_fim": dt_fim,
                "data_limite": dt_fim or dt_inicio,
                "status": "Previsto",
                "observacao": f"Extraído de: {data_raw}"
            })
    return items


def extract_cronograma_local(pdf_path: str) -> List[Dict[str, Any]]:
    """Extrai o cronograma completo analisando o PDF."""
    pages = extract_full_text_by_pages(pdf_path)
    all_items = []
    seen_events = set()

    for p in pages:
        txt = p["text"]
        if is_cronograma_page(txt):
            items_table = extract_cronograma_from_tables(p["tables"])
            for it in items_table:
                # Normaliza chave usando o evento completo (sem truncar em 40 chars)
                chave = re.sub(r'[^\w\s]', '', it["evento"].lower()).strip()
                if chave not in seen_events and len(it["evento"]) >= 5:
                    seen_events.add(chave)
                    all_items.append(it)

    return all_items


# ==============================================================================
# 2. EXTRAÇÃO E AUTO-DESCOBERTA DE CARGOS DO EDITAL
# ==============================================================================

def discover_cargos_in_pdf(pdf_path: str) -> List[str]:
    """Identifica automaticamente todos os cargos mencionados no conteúdo programático."""
    pages = extract_full_text_by_pages(pdf_path)
    cargos = []
    seen = set()

    for p in pages:
        txt = p["text"]
        if not txt:
            continue

        # Cebraspe: 'CARGO 1: AUDITOR FEDERAL...'
        m1 = re.findall(r'CARGO\s+\d+:\s*([^\n]+)', txt)
        for c in m1:
            c_clean = c.strip(" :.-")
            if len(c_clean) > 3 and c_clean.upper() not in seen and len(c_clean) < 120:
                seen.add(c_clean.upper())
                cargos.append(c_clean)

        # FAPEC/UFMS: 'ADMINISTRADOR (CÓDIGO 500)'
        m2 = re.findall(r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s/–-]+)\s*\(CÓDIGO\s*\d+\)', txt)
        for c in m2:
            lines = [l.strip() for l in c.split("\n") if l.strip()]
            c_clean = lines[-1].strip(" :.-") if lines else c.strip()
            if len(c_clean) > 3 and c_clean.upper() not in seen and len(c_clean) < 120:
                if not any(k in c_clean.upper() for k in ["CARGOS DE", "NÍVEL SUPERIOR", "NÍVEL MÉDIO"]):
                    seen.add(c_clean.upper())
                    cargos.append(c_clean)

    return cargos


# ==============================================================================
# 3. EXTRAÇÃO DO EDITAL VERTICALIZADO (CONTEÚDO PROGRAMÁTICO)
# ==============================================================================

def clean_topic_string(text: str) -> str:
    """Higieniza tópicos removendo números de tópicos ou pontuação."""
    t = re.sub(r'^\s*\d+[\.\)]\s*', '', text)
    t = re.sub(r'^[•\-\*]\s*', '', t)
    t = re.sub(r'\s+', ' ', t).strip(' ;.,')
    return t


def parse_numbered_topics_block(disciplina: str, block_text: str) -> List[Dict[str, Any]]:
    """Interpreta blocos numerados no padrão Cebraspe (1 Tópico. 1.1 Subtópico. 2 Outro tópico)."""
    items = []
    tokens = re.split(r'(?:^|\s+)(\d+(?:\.\d+)*)\s+', block_text)
    if len(tokens) <= 1:
        parts = [p.strip() for p in re.split(r'[;.]\s+', block_text) if len(p.strip()) > 3]
        for p in parts:
            items.append({
                "disciplina": disciplina,
                "topico": clean_topic_string(p),
                "subtopico": "",
                "peso": 1.0,
                "questoes_previstas": 0,
                "observacao": ""
            })
        return items

    i = 1
    current_parent = ""
    while i < len(tokens):
        num = tokens[i]
        txt = tokens[i+1].strip(' .;\n') if i+1 < len(tokens) else ''
        if len(txt) > 2:
            if "." in num:
                items.append({
                    "disciplina": disciplina,
                    "topico": current_parent if current_parent else txt,
                    "subtopico": f"{num} {txt}",
                    "peso": 1.0,
                    "questoes_previstas": 0,
                    "observacao": ""
                })
            else:
                current_parent = f"{num} {txt}"
                items.append({
                    "disciplina": disciplina,
                    "topico": f"{num} {txt}",
                    "subtopico": "",
                    "peso": 1.0,
                    "questoes_previstas": 0,
                    "observacao": ""
                })
        i += 2
    return items


def extract_verticalizado_local(pdf_path: str, cargo_filtro: str = "") -> List[Dict[str, Any]]:
    """Extrai o conteúdo programático do edital com alta precisão."""
    pages = extract_full_text_by_pages(pdf_path)
    full_text = "\n".join([p["text"] for p in pages if p["text"]])

    start_pos = -1
    for trigger in ["15 DOS OBJETOS DE AVALIAÇÃO", "DOS OBJETOS DE AVALIAÇÃO", "ANEXO V - CONTEÚDO PROGRAMÁTICO", "CONTEÚDO PROGRAMÁTICO"]:
        pos = full_text.find(trigger)
        if pos != -1:
            start_pos = pos
            break

    if start_pos == -1:
        start_pos = int(len(full_text) * 0.5)

    content_area = full_text[start_pos:]

    for end_trigger in ["ANEXO VI", "ANEXO VII", "MODELO DE LAUDO", "MODELO DE DECLARAÇÃO"]:
        end_pos = content_area.find(end_trigger)
        if end_pos != -1:
            content_area = content_area[:end_pos]
            break

    verticalizado = []
    seen = set()

    is_cebraspe = "15.2.2 CONHECIMENTOS BÁSICOS" in content_area or "CARGO 1:" in content_area

    if is_cebraspe:
        cargo_target = "CARGO 1:"
        if cargo_filtro:
            m_c = re.search(r'CARGO\s+\d+:\s*' + re.escape(cargo_filtro), content_area, re.IGNORECASE)
            if m_c:
                cargo_target = m_c.group(0)

        cargo_pos = content_area.find(cargo_target)
        if cargo_pos != -1:
            common_block = content_area[:cargo_pos]
            cargo_block = content_area[cargo_pos:]
            next_cargo_m = re.search(r'\nCARGO\s+\d+:', cargo_block[len(cargo_target):])
            if next_cargo_m:
                cargo_block = cargo_block[:len(cargo_target) + next_cargo_m.start()]
            target_content = common_block + "\n" + cargo_block
        else:
            c2_pos = content_area.find("CARGO 2:")
            target_content = content_area[:c2_pos] if c2_pos != -1 else content_area

        disc_pattern = r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s,–-]{4,}):\s*(?=\d+\s+[A-Z])'
        parts = re.split(disc_pattern, target_content)

        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                disc_raw = parts[i].strip()
                body = parts[i+1].strip()
                disc_name = disc_raw.replace("15.2.2 CONHECIMENTOS BÁSICOS", "").replace("15.2.3 CONHECIMENTOS COMPLEMENTARES", "").replace("15.2.4 CONHECIMENTOS ESPECÍFICOS", "").strip(" \n-–:")
                if not disc_name or len(disc_name) < 3:
                    disc_name = "Conhecimentos Gerais"

                items = parse_numbered_topics_block(disc_name.title(), body)
                for it in items:
                    chave = f"{it['disciplina']}:{it['topico'].lower()}:{it['subtopico'].lower()}"
                    if chave not in seen:
                        seen.add(chave)
                        verticalizado.append(it)
        else:
            items = parse_numbered_topics_block("Conhecimentos Gerais", target_content)
            verticalizado.extend(items)

    else:
        # Padrão FAPEC / UFMS / Vunesp
        pos_especificos = content_area.find("2. CONHECIMENTOS ESPECÍFICOS")
        if pos_especificos != -1:
            gerais_text = content_area[:pos_especificos]
            especificos_text = content_area[pos_especificos:]
        else:
            gerais_text = content_area
            especificos_text = ""

        # Processa Gerais
        for disc in ["LÍNGUA PORTUGUESA", "LEGISLAÇÃO", "RACIOCÍNIO LÓGICO", "LÍNGUA INGLESA", "NOÇÕES DE INFORMÁTICA"]:
            idx = gerais_text.find(disc)
            if idx != -1:
                sub = gerais_text[idx + len(disc):]
                next_indices = [sub.find(d) for d in ["LÍNGUA PORTUGUESA", "LEGISLAÇÃO", "RACIOCÍNIO LÓGICO", "LÍNGUA INGLESA", "NOÇÕES DE INFORMÁTICA"] if sub.find(d) > 0]
                disc_body = sub[:min(next_indices)] if next_indices else sub[:2000]
                topics = [t.strip() for t in re.split(r'\.\s+', disc_body) if len(t.strip()) > 3]
                for t in topics:
                    clean_t = clean_topic_string(t)
                    chave = f"{disc}:{clean_t.lower()}"
                    if len(clean_t) > 4 and chave not in seen:
                        seen.add(chave)
                        verticalizado.append({
                            "disciplina": disc.title(),
                            "topico": clean_t,
                            "subtopico": "",
                            "peso": 1.0,
                            "questoes_previstas": 0,
                            "observacao": ""
                        })

        # Processa Específicos
        if especificos_text:
            cargo_block = ""
            if cargo_filtro:
                idx_c = especificos_text.find(cargo_filtro)
                if idx_c != -1:
                    cargo_block = especificos_text[idx_c:]

            if not cargo_block:
                m_primeiro = re.search(r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s/–-]+)\s*\(CÓDIGO\s*\d+\)', especificos_text)
                if m_primeiro:
                    cargo_block = especificos_text[m_primeiro.start():]
                else:
                    cargo_block = especificos_text

            # Descobre nome do cargo para o título da disciplina
            m_cargo_title = re.search(r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s/–-]+)\s*\(CÓDIGO\s*\d+\)', cargo_block[:150])
            cargo_label = m_cargo_title.group(1).replace("CARGOS DE NÍVEL SUPERIOR", "").strip(" \n-–") if m_cargo_title else "Conhecimentos Específicos"

            m_prox = re.search(r'\n[A-ZÁÉÍÓÚÂÊÔÃÕÇ\s/–-]+\s*\(CÓDIGO\s*\d+\)', cargo_block[50:])
            if m_prox:
                cargo_block = cargo_block[:50 + m_prox.start()]

            tokens = re.split(r'(?:^|\s+)(\d+)\.\s+', cargo_block)
            i = 1
            while i < len(tokens):
                num = tokens[i]
                body = tokens[i+1].strip() if i+1 < len(tokens) else ''
                m_colon = re.match(r'([^:]+):\s*(.*)', body, re.DOTALL)
                if m_colon:
                    top_title = clean_topic_string(m_colon.group(1))
                    sub_details = clean_topic_string(m_colon.group(2)[:200])
                    chave = f"Específicos:{top_title.lower()}"
                    if chave not in seen:
                        seen.add(chave)
                        verticalizado.append({
                            "disciplina": f"Específicos ({cargo_label.title()})",
                            "topico": f"{num}. {top_title}",
                            "subtopico": sub_details,
                            "peso": 2.0,
                            "questoes_previstas": 0,
                            "observacao": ""
                        })
                else:
                    top_title = clean_topic_string(body[:80])
                    if len(top_title) > 4:
                        verticalizado.append({
                            "disciplina": f"Específicos ({cargo_label.title()})",
                            "topico": f"{num}. {top_title}",
                            "subtopico": "",
                            "peso": 2.0,
                            "questoes_previstas": 0,
                            "observacao": ""
                        })
                i += 2

    return verticalizado
