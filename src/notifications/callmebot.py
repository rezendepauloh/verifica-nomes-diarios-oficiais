# -*- coding: utf-8 -*-
"""
Integração com o serviço gratuito CallMeBot para envio de mensagens WhatsApp.
Documentação: https://www.callmebot.com/blog/free-api-whatsapp-messages/
"""
import os
import re
import urllib.parse
import requests
from src.logger import logger

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"

def normalize_phone(raw_phone: str) -> str:
    """
    Normaliza o número de telefone para o padrão internacional exigido pelo CallMeBot (apenas dígitos, sem '+').
    Nota para números celulares do Brasil (+55):
    O WhatsApp internacional registra números celulares brasileiros sem o dígito '9' extra após o DDD
    (ex: +55 67 99247-1379 é registrado como 556792471379 no WhatsApp/CallMeBot).
    Portanto:
      - 11 dígitos com 9 após DDD (ex: 67 9 9247 1379) -> remove o 9 após o DDD -> 556792471379
      - 13 dígitos começando com 55 e 9 após DDD (ex: 55 67 9 9247 1379) -> 556792471379
      - Caso contrário, preserva os dígitos completos com prefixo 55.
    """
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    
    # Se fornecido sem código de país (10 ou 11 dígitos)
    if len(digits) == 11:
        # Padrão celular BR: DDD (2) + 9 + 8 dígitos -> converte para 10 dígitos (DDD + 8 dígitos)
        ddd = digits[:2]
        resto = digits[3:] if digits[2] == '9' else digits[2:]
        return f"55{ddd}{resto}"
    elif len(digits) == 10:
        return f"55{digits}"
    
    # Se já fornecido com DDI 55 (13 dígitos: 55 + DDD + 9 + 8 dígitos)
    if len(digits) == 13 and digits.startswith("55") and digits[4] == '9':
        return f"55{digits[2:4]}{digits[5:]}"
    
    # Fallback genérico se já tiver DDI ou outro padrão
    if not digits.startswith("55") and len(digits) in (8, 9):
        return f"55{digits}"

    return digits

def format_occurrence_message(name: str, source: str, date_str: str, link: str, context: str) -> str:
    """
    Gera o texto formatado para envio no WhatsApp com visual chamativo e organizado.
    """
    # Trunca o contexto se for excessivamente longo para evitar limites de URL do CallMeBot
    clean_context = (context or "").strip()
    if len(clean_context) > 280:
        clean_context = clean_context[:277] + "..."

    msg_lines = [
        "🚨 *ALERTA DE DIÁRIO OFICIAL / CONCURSO* 🚨",
        "",
        f"Nova publicação encontrada para o nome: *{name}*",
        "",
        f"🏛️ *Fonte:* {source}",
        f"📅 *Data:* {date_str}",
    ]

    if link and link.strip():
        msg_lines.append(f"🔗 *Link:* {link.strip()}")

    if clean_context:
        msg_lines.append(f"📝 *Trecho:* \"{clean_context}\"")

    msg_lines.append("")
    msg_lines.append("📌 *Acesse o painel do sistema para gerenciar esta ocorrência.*")

    return "\n".join(msg_lines)

def send_whatsapp_message(phone: str, message: str, apikey: str = None) -> bool:
    """
    Envia uma mensagem de WhatsApp via CallMeBot.
    phone: número do destinatário (qualquer formato legível ou numérico)
    message: texto da mensagem
    apikey: chave da API do CallMeBot (se None, tenta fallback no .env CALLMEBOT_API_KEY)
    
    Retorna True se enviada com sucesso, False caso contrário.
    """
    dest_phone = normalize_phone(phone)
    if not dest_phone:
        logger.warning("Envio de WhatsApp abortado: Telefone não informado ou inválido.")
        return False

    final_apikey = (apikey or "").strip() or os.getenv("CALLMEBOT_API_KEY", "").strip()
    if not final_apikey:
        logger.warning(f"Envio de WhatsApp abortado para {dest_phone}: Nenhuma API Key do CallMeBot informada.")
        return False

    try:
        # Prepara parâmetros e faz a codificação segura da URL
        params = {
            "phone": dest_phone,
            "text": message,
            "apikey": final_apikey
        }
        
        logger.info(f"Disparando WhatsApp via CallMeBot para o número {dest_phone}...")
        response = requests.get(CALLMEBOT_URL, params=params, timeout=15)
        
        # O CallMeBot retorna status 200 com mensagem no corpo HTML/texto (ex: "Message queued", "Success", etc.)
        if response.status_code == 200:
            resp_text = response.text.lower()
            if "error" in resp_text or "invalid apikey" in resp_text or "not registered" in resp_text:
                logger.error(f"Erro reportado pela API do CallMeBot para {dest_phone}: {response.text}")
                return False
            logger.success(f"Notificação WhatsApp enviada com sucesso para {dest_phone} via CallMeBot!")
            return True
        else:
            logger.error(f"Falha ao enviar WhatsApp para {dest_phone}. Status HTTP: {response.status_code}. Resposta: {response.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao conectar com CallMeBot para o número {dest_phone}.")
        return False
    except Exception as e:
        logger.error(f"Exceção ao disparar WhatsApp via CallMeBot para {dest_phone}: {e}")
        return False

def test_callmebot_connection(phone: str, apikey: str) -> tuple[bool, str]:
    """
    Testa a chave e o número enviando uma mensagem de verificação.
    Retorna uma tupla (sucesso: bool, mensagem_retorno: str).
    """
    dest_phone = normalize_phone(phone)
    if not dest_phone:
        return False, "Número de telefone inválido ou em branco."

    final_apikey = (apikey or "").strip() or os.getenv("CALLMEBOT_API_KEY", "").strip()
    if not final_apikey:
        return False, "API Key do CallMeBot não fornecida."

    test_msg = (
        "🤖 *Teste de Integração - Monitor de Diários Oficiais*\n\n"
        "✅ Parabéns! O seu WhatsApp e a sua API Key do CallMeBot estão configurados com sucesso.\n"
        "Você passará a receber alertas automáticos sempre que houver novas publicações com o seu nome."
    )

    try:
        params = {
            "phone": dest_phone,
            "text": test_msg,
            "apikey": final_apikey
        }
        response = requests.get(CALLMEBOT_URL, params=params, timeout=15)
        
        # Limpa eventuais tags HTML do corpo para exibição limpa
        clean_resp = re.sub(r"<[^>]+>", " ", response.text).strip()
        clean_resp = re.sub(r"\s+", " ", clean_resp)

        lower_text = response.text.lower()
        if "invalid apikey" in lower_text or "apikey is invalid" in lower_text:
            return False, "Chave de API inválida para este telefone. Verifique se digitou a chave correta fornecida pelo bot."
        elif "not registered" in lower_text:
            return False, "Telefone não registrado no CallMeBot. Envie a mensagem de ativação antes de testar."
        elif response.status_code == 200 and "queued" in lower_text:
            return True, "Mensagem de teste enviada com sucesso! Verifique seu WhatsApp em instantes."
        elif response.status_code in (200, 201):
            return True, f"Sucesso: {clean_resp}"
        else:
            return False, f"Resposta do CallMeBot: {clean_resp}"
    except requests.exceptions.Timeout:
        return False, "Tempo de resposta esgotado (Timeout de 15s com a API do CallMeBot)."
    except Exception as e:
        return False, f"Falha na comunicação: {str(e)}"
