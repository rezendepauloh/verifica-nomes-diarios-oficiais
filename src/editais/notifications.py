# -*- coding: utf-8 -*-
"""
src/editais/notifications.py
Módulo responsável por monitorar os prazos dos editais (edital_cronograma) e disparar
alertas via WhatsApp (CallMeBot) para datas que vencem 'Hoje' ou 'Amanhã',
com links configurados via APP_LOCAL_URL e APP_PUBLIC_URL no .env.
"""

import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from src.logger import logger
from src.database import (
    get_all_active_cronogramas,
    get_whatsapp_notification_recipients,
    has_cronograma_alert_been_sent,
    record_cronograma_alert_sent,
)
from src.editais.calendar_utils import compute_event_status, parse_date_smart, parse_iso_date
from src.notifications import format_cronograma_deadline_message, send_whatsapp_message


def _is_recipient_interested(recipient_name: str, interessado_edital: str) -> bool:
    """Verifica se o destinatário cadastrado deve receber notificações do edital."""
    if not interessado_edital or interessado_edital.lower() == "ambos":
        return True
    
    rec_clean = recipient_name.strip().lower()
    int_clean = interessado_edital.strip().lower()
    
    # Se o nome cadastrado contém "paulo" e o edital é para Paulo, ou "kamila" e é para Kamila
    if int_clean in rec_clean or rec_clean in int_clean:
        return True
    return False


def check_and_notify_cronograma_deadlines(
    force_all: bool = False,
    include_tomorrow: bool = True,
    edital_id_filter: Optional[int] = None
) -> Dict[str, Any]:
    """
    Varre todos os cronogramas de editais ativos, calcula a situação atual de cada evento
    e dispara alertas WhatsApp para os prazos que são HOJE ou AMANHÃ.

    - force_all: se True, ignora histórico e dispara (em teste manual, se não houver prazos hoje/amanhã,
      envia apenas 1 evento representativo de teste para não inundar o WhatsApp com dezenas de mensagens).
    - include_tomorrow: se True, também envia lembrete com aviso prévio de 1 dia.
    - edital_id_filter: opcional, filtra apenas eventos de um edital específico.

    Retorna relatório do processo: total analisado, enviados, ignorados e erros.
    """
    logger.info("📅 [Cronograma Notifier] Iniciando verificação de prazos e etapas de editais...")
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")

    recipients = get_whatsapp_notification_recipients()
    if not recipients:
        logger.warning("📅 [Cronograma Notifier] Nenhum destinatário WhatsApp ativo cadastrado. Verificação cancelada.")
        return {"status": "no_recipients", "alerts_sent": 0, "events_checked": 0}

    all_cronos = get_all_active_cronogramas()
    if edital_id_filter:
        all_cronos = [c for c in all_cronos if c["edital_id"] == edital_id_filter]

    if not all_cronos:
        logger.info("📅 [Cronograma Notifier] Nenhum evento de cronograma encontrado no banco de dados.")
        return {"status": "no_events", "alerts_sent": 0, "events_checked": 0}

    alerts_sent = 0
    events_today = 0
    events_tomorrow = 0
    manual_test_dispatched = False

    for item in all_cronos:
        crono_id = item["cronograma_id"]
        edital_id = item["edital_id"]
        evento = item["evento"]
        d_inicio = item.get("data_inicio")
        d_fim = item.get("data_fim")
        # d_inicio no banco pode ser a string inteira de período ou a data inicial
        data_referencia = d_inicio or d_fim or ""
        dt_inicio_iso, dt_fim_iso, _ = parse_date_smart(data_referencia)
        d_ini_obj = parse_iso_date(dt_inicio_iso)
        d_fim_obj = parse_iso_date(dt_fim_iso) or d_ini_obj

        # Calcula a situação em tempo real (Concluído, Em Andamento, Hoje, Previsto)
        situacao_texto, badge_situacao = compute_event_status(data_referencia, today=today)

        # Monta a string legível do prazo
        if dt_inicio_iso and dt_fim_iso and dt_inicio_iso != dt_fim_iso:
            prazo_str = f"{dt_inicio_iso} a {dt_fim_iso}"
        elif d_inicio and d_fim and d_inicio != d_fim and d_fim not in d_inicio:
            prazo_str = f"{d_inicio} a {d_fim}"
        else:
            prazo_str = data_referencia or "A definir"

        # Identifica se é HOJE ou AMANHÃ
        tipo_alerta = None
        alerta_situacao = badge_situacao

        if situacao_texto.lower() == "hoje":
            tipo_alerta = "hoje"
            alerta_situacao = "🚨 Vence Hoje!"
            events_today += 1
        elif situacao_texto.lower() == "em andamento":
            # Se hoje é exatamente o primeiro dia ou o último dia do período
            if d_fim_obj == today:
                tipo_alerta = "hoje"
                alerta_situacao = "🚨 Último dia Hoje!"
                events_today += 1
            elif d_ini_obj == today:
                tipo_alerta = "hoje"
                alerta_situacao = "🟢 Começa Hoje!"
                events_today += 1
            elif include_tomorrow and d_fim_obj == tomorrow:
                tipo_alerta = "amanha"
                alerta_situacao = "⏳ Encerra Amanhã"
                events_tomorrow += 1
        elif include_tomorrow:
            # Eventos previstos que começam amanhã
            if d_ini_obj == tomorrow or (not d_ini_obj and d_fim_obj == tomorrow):
                tipo_alerta = "amanha"
                alerta_situacao = "⏳ Prazo Amanhã"
                events_tomorrow += 1

        # Se não há gatilho para hoje nem para amanhã:
        if not tipo_alerta:
            if force_all and not manual_test_dispatched:
                # Dispara apenas 1 evento como teste único para validação
                tipo_alerta = "teste_manual"
                alerta_situacao = f"Teste / {badge_situacao}"
            else:
                continue

        # Dispara para cada destinatário elegível
        interessado = item.get("edital_interessado", "Ambos")
        sent_in_this_item = False
        for rec in recipients:
            if not _is_recipient_interested(rec["name"], interessado):
                continue

            phone = rec["phone"]
            apikey = rec.get("callmebot_apikey")

            # Verifica se já foi enviado hoje para este telefone
            if not force_all and has_cronograma_alert_been_sent(crono_id, tipo_alerta, today_str, phone):
                logger.debug(f"Alerta {tipo_alerta} para cronograma {crono_id} já enviado para {phone} hoje.")
                continue

            # Monta mensagem
            msg = format_cronograma_deadline_message(
                edital_titulo=item["edital_titulo"],
                evento=evento,
                prazo_str=prazo_str,
                situacao=alerta_situacao,
                interessado=interessado,
                cargo=item.get("edital_cargo", ""),
                detalhes=item.get("observacao", ""),
                link_inscricao=item.get("link_inscricao", "")
            )

            logger.info(f"📲 Disparando alerta de cronograma ({tipo_alerta}) para {rec['name']} ({phone})...")
            ok = send_whatsapp_message(phone=phone, message=msg, apikey=apikey)
            if ok:
                record_cronograma_alert_sent(crono_id, edital_id, tipo_alerta, today_str, phone)
                alerts_sent += 1
                sent_in_this_item = True
                time.sleep(1)  # Pausa de cortesia entre mensagens CallMeBot

        if tipo_alerta == "teste_manual" and sent_in_this_item:
            manual_test_dispatched = True

    logger.success(f"📅 [Cronograma Notifier] Concluído! {alerts_sent} alertas disparados.")
    return {
        "status": "success",
        "alerts_sent": alerts_sent,
        "events_checked": len(all_cronos),
        "events_today": events_today,
        "events_tomorrow": events_tomorrow
    }
