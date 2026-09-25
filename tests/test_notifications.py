# -*- coding: utf-8 -*-
"""
Testes unitários para o módulo de notificações via WhatsApp (CallMeBot).
"""
import pytest
from unittest.mock import patch, MagicMock
from src.notifications.callmebot import (
    normalize_phone,
    format_occurrence_message,
    send_whatsapp_message,
    test_callmebot_connection as api_test_callmebot
)

class TestNormalizePhone:
    """Valida as regras de normalização de telefone brasileiro e internacional."""

    def test_empty_or_none(self):
        assert normalize_phone("") == ""
        assert normalize_phone(None) == ""

    def test_br_phone_with_formatting(self):
        # 11 dígitos com o '9' após DDD -> remove o '9' para padrão CallMeBot/WhatsApp
        assert normalize_phone("(67) 99247-1379") == "556792471379"
        assert normalize_phone("+55 67 99247-1379") == "556792471379"
        assert normalize_phone("67992471379") == "556792471379"

    def test_br_phone_already_8_digits(self):
        # 10 dígitos (DDD + 8 dígitos) -> adiciona DDI 55
        assert normalize_phone("(67) 3345-1234") == "556733451234"
        assert normalize_phone("6733451234") == "556733451234"

    def test_br_phone_with_ddi_13_digits(self):
        # 13 dígitos: 55 + 67 + 9 + 8 dígitos -> 5567 + 8 dígitos
        assert normalize_phone("5567998538804") == "556798538804"


class TestFormatMessage:
    """Valida a geração visual e textual do alerta para WhatsApp."""

    def test_format_occurrence_message(self):
        msg = format_occurrence_message(
            name="Paulo Henrique",
            source="DO-MS",
            date_str="24/09/2026",
            link="https://diario.ms.gov.br",
            context="Candidato aprovado em primeiro lugar"
        )
        assert "🚨 *ALERTA DE DIÁRIO OFICIAL / CONCURSO* 🚨" in msg
        assert "*Paulo Henrique*" in msg
        assert "DO-MS" in msg
        assert "24/09/2026" in msg
        assert "https://diario.ms.gov.br" in msg
        assert "Candidato aprovado" in msg

    def test_format_message_long_context_truncation(self):
        long_text = "A" * 500
        msg = format_occurrence_message("Paulo", "DOU", "24/09/2026", "", long_text)
        assert "..." in msg
        assert len(msg) < 500


class TestSendWhatsAppMessage:
    """Testa o disparo HTTP para o CallMeBot usando mocks."""

    @patch("requests.get")
    def test_send_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Message queued."
        mock_get.return_value = mock_resp

        result = send_whatsapp_message("(67) 99247-1379", "Mensagem de teste", apikey="123456")
        assert result is True
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["phone"] == "556792471379"
        assert kwargs["params"]["apikey"] == "123456"

    def test_send_missing_phone(self):
        assert send_whatsapp_message("", "Texto", apikey="123456") is False

    def test_send_missing_apikey(self, monkeypatch):
        monkeypatch.delenv("CALLMEBOT_API_KEY", raising=False)
        assert send_whatsapp_message("(67) 99247-1379", "Texto", apikey="") is False

    @patch("requests.get")
    def test_send_invalid_apikey_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 203
        mock_resp.text = "APIKey is invalid"
        mock_get.return_value = mock_resp

        result = send_whatsapp_message("(67) 99247-1379", "Teste", apikey="errada")
        assert result is False


class TestTestCallMeBotConnection:
    """Testa a função de verificação imediata."""

    @patch("requests.get")
    def test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<p>Message queued. You will receive it in a few seconds."
        mock_get.return_value = mock_resp

        ok, msg = api_test_callmebot("(67) 99247-1379", "3587903")
        assert ok is True
        assert "sucesso" in msg.lower()

    @patch("requests.get")
    def test_connection_invalid_key(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 203
        mock_resp.text = "<p>APIKey is invalid. Please create a new one."
        mock_get.return_value = mock_resp

        ok, msg = api_test_callmebot("(67) 99247-1379", "errada")
        assert ok is False
        assert "inválida" in msg.lower()
