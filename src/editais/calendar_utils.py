# -*- coding: utf-8 -*-
"""
Utilitários de Calendário e Cronograma:
- Cálculo dinâmico da situação de eventos (Concluído, Em Andamento, Previsto)
- Decomposição de períodos em eventos pontuais (Abertura / Início e Encerramento / Fim)
- Geração de arquivo iCalendar (.ics) para importação em lote na agenda do Google
- Geração de URLs One-Click para o Google Calendar
"""
from datetime import datetime, date, timedelta, timezone
import re
from typing import List, Dict, Any, Tuple
import urllib.parse

from src.editais.extractor_local import parse_date_smart

def parse_iso_date(date_str: str) -> date | None:
    """Converte string de data no formato DD/MM/YYYY para objeto date."""
    if not date_str:
        return None
    try:
        parts = date_str.strip().split('/')
        if len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return date(year, month, day)
    except Exception:
        pass
    return None

def compute_event_status(data_str: str, today: date | None = None) -> Tuple[str, str]:
    """
    Calcula dinamicamente a situação e a badge correspondente a partir da string de data.
    
    Retorna:
        Tuple[str, str]: (status_text, badge_label)
        Exemplos de status_text: 'Concluído', 'Em Andamento', 'Hoje', 'Previsto'
        Exemplos de badge_label: '⚪ Concluído', '🟢 Em Andamento', '⚡ Hoje', '🔵 Previsto'
    """
    if today is None:
        today = date.today()

    dt_inicio_str, dt_fim_str, _ = parse_date_smart(data_str)
    dt_inicio = parse_iso_date(dt_inicio_str)
    dt_fim = parse_iso_date(dt_fim_str) or dt_inicio

    if not dt_inicio or not dt_fim:
        return "Previsto", "🔵 Previsto"

    if dt_fim < today:
        return "Concluído", "⚪ Concluído"
    elif dt_inicio <= today <= dt_fim:
        if dt_inicio == dt_fim:
            return "Hoje", "⚡ Hoje"
        return "Em Andamento", "🟢 Em Andamento"
    else:
        return "Previsto", "🔵 Previsto"

def format_smart_event_title(evento: str, is_fim: bool = False, is_period: bool = True, sigla_edital: str = "") -> str:
    """
    Formata o título do evento com precisão semântica e objetividade idêntica ao padrão de estudo:
    Ex: [CGU] Início das inscrições e isenção, [CGU] Fim da isenção, [CGU] Ensalamento,
    [CGU] Prova objetiva e discursiva, [CGU] Gabarito preliminar, [CGU] Recursos contra indeferimento da isenção.
    """
    ev = evento.strip()
    ev_lower = ev.lower()
    prefix = f"[{sigla_edital.strip()}] " if sigla_edital else ""

    # 1. Recursos (prioridade sobre termos isolados como 'isenção')
    if "recurso" in ev_lower:
        alvo = ""
        if "isenç" in ev_lower or "isencao" in ev_lower:
            alvo = " contra indeferimento da isenção" if "indeferimento" in ev_lower else " contra isenção"
        elif "gabarito" in ev_lower and "discursiva" in ev_lower:
            alvo = " contra gabarito preliminar e discursiva"
        elif "gabarito" in ev_lower:
            alvo = " contra gabarito preliminar"
        elif "discursiva" in ev_lower:
            alvo = " contra prova discursiva"
        elif any(k in ev_lower for k in ["heteroidentificaç", "pcd", "negro", "cota"]):
            alvo = " contra heteroidentificação"
        elif "resultado" in ev_lower:
            alvo = " contra resultado preliminar"

        if is_period:
            base = f"Fim dos recursos{alvo}" if is_fim else f"Recursos{alvo}"
        else:
            base = f"Recursos{alvo}"
        return f"{prefix}{base}"

    # 2. Consultas e Resultados de Isenção (antes de inscrições gerais)
    if ("isenç" in ev_lower or "isencao" in ev_lower) and any(k in ev_lower for k in ["consulta", "situaç", "resultado"]):
        if "provisóri" in ev_lower or "preliminar" in ev_lower:
            base = "Resultado preliminar isenção"
        elif "final" in ev_lower or "definitiv" in ev_lower:
            base = "Resultado final isenção"
        else:
            base = "Situação da isenção"
        if is_period and is_fim:
            base = f"Fim da consulta: {base}"
        return f"{prefix}{base}"

    # 3. Inscrições e Isenção combinadas (período inicial de inscrições com isenção)
    if ("inscriç" in ev_lower or "inscricao" in ev_lower) and ("isenç" in ev_lower or "isencao" in ev_lower):
        if is_period:
            base = "Fim da isenção" if is_fim else "Início das inscrições e isenção"
        else:
            base = "Inscrições e isenção"
        return f"{prefix}{base}"

    # 4. Ensalamento / Locais de Prova
    if any(k in ev_lower for k in ["local de prova", "locais de prova", "ensalamento", "consulta aos locais"]):
        return f"{prefix}Ensalamento"

    # 5. Provas (Objetiva / Discursiva)
    if ("aplicaç" in ev_lower and "prova" in ev_lower) or ev_lower.startswith("prova"):
        if "discursiva" in ev_lower and "objetiva" in ev_lower:
            return f"{prefix}Prova objetiva e discursiva"
        elif "discursiva" in ev_lower:
            return f"{prefix}Prova discursiva"
        elif "objetiva" in ev_lower:
            return f"{prefix}Prova objetiva"
        return f"{prefix}Aplicação das provas"

    # 6. Gabaritos
    if "gabarito" in ev_lower:
        tipo = "definitivo" if "definitivo" in ev_lower or ("oficia" in ev_lower and "preliminar" not in ev_lower) else "preliminar"
        if is_period and is_fim:
            return f"{prefix}Fim da consulta ao gabarito {tipo}"
        return f"{prefix}Gabarito {tipo}"

    # 7. Padrão de respostas discursiva
    if "padrão" in ev_lower and "discursiva" in ev_lower:
        return f"{prefix}Padrão preliminar discursiva"

    # 8. Link para foto
    if "foto" in ev_lower:
        if is_period and is_fim:
            return f"{prefix}Prazo final link para foto"
        return f"{prefix}Link para foto"

    # 9. Pagamento da taxa
    if "pagamento" in ev_lower:
        return f"{prefix}Último dia para pagamento da taxa de inscrição"

    # 10. Inscrições gerais
    if "inscriç" in ev_lower or "inscricao" in ev_lower:
        if "homologa" in ev_lower:
            return f"{prefix}Homologação das inscrições"
        if "deferimento" in ev_lower:
            return f"{prefix}Deferimento das inscrições"
        if is_period:
            base = "Fim das inscrições" if is_fim else "Início das inscrições"
        else:
            base = "Inscrições"
        return f"{prefix}{base}"

    # 11. Resultado Final / Preliminar
    if "resultado final" in ev_lower:
        return f"{prefix}Resultado final"
    if "resultado preliminar" in ev_lower:
        return f"{prefix}Resultado preliminar"

    # Fallback limpo
    clean = re.sub(r'^(?:per[ií]odo\s+de\s+(?:solicitaç[aã]o\s+de\s+)?|prazo\s+para\s+(?:a\s+)?|divulgaç[ãa]o\s+d[oe]\s+)', '', ev, flags=re.IGNORECASE).strip()
    clean = clean[0].upper() + clean[1:] if clean else ev
    if is_period:
        base = f"Fim: {clean}" if is_fim else f"Início: {clean}"
    else:
        base = clean
    return f"{prefix}{base}"

def split_period_into_events(evento: str, data_str: str, sigla_edital: str = "") -> List[Dict[str, Any]]:
    """
    Decompõe eventos com período (ex: '10/10/2026 a 04/11/2026') em dois eventos pontuais:
    - Um evento de Abertura / Início
    - Um evento de Encerramento / Fim
    Se for apenas uma data única, mantém como um evento pontual.
    """
    dt_inicio_str, dt_fim_str, _ = parse_date_smart(data_str)
    dt_inicio = parse_iso_date(dt_inicio_str)
    dt_fim = parse_iso_date(dt_fim_str)

    # Se início e fim forem válidos e diferentes, divide em dois eventos pontuais
    if dt_inicio and dt_fim and dt_inicio != dt_fim:
        nome_inicio = format_smart_event_title(evento, is_fim=False, is_period=True, sigla_edital=sigla_edital)
        nome_fim = format_smart_event_title(evento, is_fim=True, is_period=True, sigla_edital=sigla_edital)

        return [
            {
                "titulo": nome_inicio,
                "data_inicio": dt_inicio,
                "data_fim": dt_inicio,
                "is_fim": False
            },
            {
                "titulo": nome_fim,
                "data_inicio": dt_fim,
                "data_fim": dt_fim,
                "is_fim": True
            }
        ]
    else:
        data_ev = dt_inicio or dt_fim or date.today()
        titulo_unico = format_smart_event_title(evento, is_fim=False, is_period=False, sigla_edital=sigla_edital)

        return [
            {
                "titulo": titulo_unico,
                "data_inicio": data_ev,
                "data_fim": data_ev,
                "is_fim": False
            }
        ]

def generate_gcal_url(
    titulo: str,
    data_ev: date,
    descricao: str = "",
    convidado: str = "kamila_arteman@hotmail.com"
) -> str:
    """
    Gera uma URL de criação de evento One-Click no Google Calendar para dia inteiro.
    """
    # No Google Calendar para all-day, dates=YYYYMMDD/YYYYMMDD (fim é dia exclusivo, soma 1)
    d_start = data_ev.strftime("%Y%m%d")
    d_end = (data_ev + timedelta(days=1)).strftime("%Y%m%d")
    dates_param = f"{d_start}/{d_end}"

    params = {
        "action": "TEMPLATE",
        "text": titulo,
        "dates": dates_param,
        "details": descricao,
    }
    if convidado:
        params["add"] = convidado

    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

def generate_ics_calendar(
    edital_titulo: str,
    cronograma_items: List[Dict[str, Any]],
    link_oficial: str = "",
    convidado: str = "kamila_arteman@hotmail.com"
) -> str:
    """
    Gera o conteúdo de um arquivo iCalendar (.ics) contendo todos os eventos pontuais
    do concurso, pronto para ser importado na agenda 'Concursos' do Google Calendar.
    """
    sigla = edital_titulo
    if len(sigla) > 15:
        # Tenta pegar apenas as primeiras palavras ou sigla
        sigla = sigla.split('-')[0].split('/')[0].strip()

    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Verifica Diarios Oficiais//Concursos Calendar//PT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Concursos - {sigla}",
        "X-WR-TIMEZONE:America/Campo_Grande",
    ]

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for idx, item in enumerate(cronograma_items):
        evento_nome = item.get("evento", "Etapa do Concurso")
        data_str = item.get("data_inicio", "")
        obs = item.get("observacao", "")

        eventos_pontuais = split_period_into_events(evento_nome, data_str, sigla_edital=sigla)

        # Monta a descrição com link oficial e período original com quebra dupla de linhas
        desc_parts = []
        if link_oficial:
            desc_parts.append(f"Link: {link_oficial}")
        desc_parts.append(f"{evento_nome} - {data_str}")
        if obs:
            desc_parts.append(obs)
        descricao_evento = "\\n\\n".join(desc_parts).replace("\r", "")

        for p_idx, ev in enumerate(eventos_pontuais):
            uid = f"edital-{idx}-{p_idx}-{now_stamp}-{ev['data_inicio'].strftime('%Y%m%d')}@verificadiarios"
            dt_start_str = ev["data_inicio"].strftime("%Y%m%d")
            dt_end_str = (ev["data_fim"] + timedelta(days=1)).strftime("%Y%m%d")

            linhas.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{dt_start_str}",
                f"DTEND;VALUE=DATE:{dt_end_str}",
                f"SUMMARY:{ev['titulo']}",
                f"DESCRIPTION:{descricao_evento}",
            ])
            if convidado:
                cal_org = "7a35c3f50e2017d2bfb868668ad9cd26e249b41b5b86f0e4cb62e0992e3353d2@group.calendar.google.com"
                linhas.extend([
                    f"ORGANIZER;CN={cal_org}:mailto:{cal_org}",
                    f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;CN={convidado};X-NUM-GUESTS=0:mailto:{convidado}"
                ])
            linhas.append("END:VEVENT")

    linhas.append("END:VCALENDAR")
    
    # Aplica o padrão RFC-5545 de quebra de linhas longas (Line Folding a cada 75 caracteres)
    folded_lines = []
    for line in linhas:
        if len(line) <= 75:
            folded_lines.append(line)
        else:
            folded_lines.append(line[:75])
            resto = line[75:]
            while resto:
                folded_lines.append(" " + resto[:74])
                resto = resto[74:]

    return "\r\n".join(folded_lines)