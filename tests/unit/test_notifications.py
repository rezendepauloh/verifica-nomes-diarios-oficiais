# -*- coding: utf-8 -*-
"""
Testes unitários para o módulo de notificações via WhatsApp (CallMeBot).
Compatível tanto com pytest quanto com unittest runner.
"""
import unittest
from unittest.mock import patch, MagicMock

from src.notifications.callmebot import (
    normalize_phone,
    format_occurrence_message,
    send_whatsapp_message,
    test_callmebot_connection as api_test_callmebot
)

class TestNormalizePhone(unittest.TestCase):
    """Valida as regras de normalização de telefone brasileiro e internacional."""

    def test_empty_or_none(self):
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_br_phone_with_formatting(self):
        # 11 dígitos com o '9' após DDD -> remove o '9' para padrão CallMeBot/WhatsApp
        self.assertEqual(normalize_phone("(67) 99247-1379"), "556792471379")
        self.assertEqual(normalize_phone("+55 67 99247-1379"), "556792471379")
        self.assertEqual(normalize_phone("67992471379"), "556792471379")

    def test_br_phone_already_8_digits(self):
        # 10 dígitos (DDD + 8 dígitos) -> adiciona DDI 55
        self.assertEqual(normalize_phone("(67) 3345-1234"), "556733451234")
        self.assertEqual(normalize_phone("6733451234"), "556733451234")

    def test_br_phone_with_ddi_13_digits(self):
        # 13 dígitos: 55 + 67 + 9 + 8 dígitos -> 5567 + 8 dígitos
        self.assertEqual(normalize_phone("5567998538804"), "556798538804")


class TestFormatMessage(unittest.TestCase):
    """Valida a geração visual e textual do alerta para WhatsApp."""

    def test_format_occurrence_message(self):
        msg = format_occurrence_message(
            name="Paulo Henrique",
            source="DO-MS",
            date_str="24/09/2026",
            link="https://diario.ms.gov.br",
            context="Candidato aprovado em primeiro lugar"
        )
        self.assertIn("🚨 *ALERTA DE DIÁRIO OFICIAL / CONCURSO* 🚨", msg)
        self.assertIn("*Paulo Henrique*", msg)
        self.assertIn("DO-MS", msg)
        self.assertIn("24/09/2026", msg)
        self.assertIn("https://diario.ms.gov.br", msg)
        self.assertIn("Candidato aprovado", msg)

    def test_format_message_long_context_truncation(self):
        long_text = "A" * 500
        msg = format_occurrence_message("Paulo", "DOU", "24/09/2026", "", long_text)
        self.assertIn("...", msg)
        self.assertLess(len(msg), 500)


class TestSendWhatsAppMessage(unittest.TestCase):
    """Testa o disparo HTTP para o CallMeBot usando mocks."""

    @patch("requests.get")
    def test_send_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Message queued."
        mock_get.return_value = mock_resp

        result = send_whatsapp_message("(67) 99247-1379", "Mensagem de teste", apikey="123456")
        self.assertTrue(result)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["phone"], "556792471379")
        self.assertEqual(kwargs["params"]["apikey"], "123456")

    def test_send_missing_phone(self):
        self.assertFalse(send_whatsapp_message("", "Texto", apikey="123456"))

    @patch.dict("os.environ", {}, clear=True)
    def test_send_missing_apikey(self):
        self.assertFalse(send_whatsapp_message("(67) 99247-1379", "Texto", apikey=""))

    @patch("requests.get")
    def test_send_invalid_apikey_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 203
        mock_resp.text = "APIKey is invalid"
        mock_get.return_value = mock_resp

        result = send_whatsapp_message("(67) 99247-1379", "Teste", apikey="errada")
        self.assertFalse(result)


class TestTestCallMeBotConnection(unittest.TestCase):
    """Testa a função de verificação imediata."""

    @patch("requests.get")
    def test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<p>Message queued. You will receive it in a few seconds."
        mock_get.return_value = mock_resp

        ok, msg = api_test_callmebot("(67) 99247-1379", "3587903")
        self.assertTrue(ok)
        self.assertIn("sucesso", msg.lower())

    @patch("requests.get")
    def test_connection_invalid_key(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 203
        mock_resp.text = "<p>APIKey is invalid. Please create a new one."
        mock_get.return_value = mock_resp

        ok, msg = api_test_callmebot("(67) 99247-1379", "errada")
        self.assertFalse(ok)
        self.assertIn("inválida", msg.lower())

if __name__ == '__main__':
    unittest.main()
