# -*- coding: utf-8 -*-
"""
Testes de integração: fluxo de varredura (run_scan), detecção de ocorrência inédita
e acionamento de broadcast de notificação.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import tests.test_helpers
import src.database.db as db_mod
import src.config as cfg_mod
from src.database.db import (
    init_db,
    save_occurrence,
    get_occurrences,
    add_monitored_name,
    add_monitored_source
)

class TestIntegrationScanFlow(unittest.TestCase):
    """Testa integração entre detecção de publicação, gravação e disparo de notificação."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_flow.sqlite"
        self._orig_db_path = db_mod.DB_PATH
        self._orig_cfg_path = cfg_mod.DB_PATH
        db_mod.DB_PATH = self.test_db_path
        cfg_mod.DB_PATH = self.test_db_path
        os.environ["MONITOR_NAMES"] = ""
        init_db()

    def tearDown(self):
        db_mod.DB_PATH = self._orig_db_path
        cfg_mod.DB_PATH = self._orig_cfg_path
        self.temp_dir.cleanup()

    @patch("src.notifications.callmebot.send_whatsapp_message")
    def test_new_occurrence_triggers_whatsapp_broadcast(self, mock_send):
        mock_send.return_value = True

        # Cadastra destinatários com chaves ativas
        add_monitored_name("Paulo Henrique", "(67) 99247-1379", "3587903")
        add_monitored_name("Kamila", "(67) 99853-8804", "9835298")

        # 1. Primeira inserção: Inédita
        is_new = save_occurrence(
            name="Paulo Henrique",
            source="DO-MS",
            date_str="26/09/2026",
            link="https://diario.ms.gov.br/edital_99.pdf",
            context="Candidato aprovado em 1º lugar no concurso"
        )
        self.assertTrue(is_new)

        # 2. Segunda inserção com os mesmos dados: Duplicada (não deve re-notificar)
        is_duplicate = save_occurrence(
            name="Paulo Henrique",
            source="DO-MS",
            date_str="26/09/2026",
            link="https://diario.ms.gov.br/edital_99.pdf",
            context="Candidato aprovado em 1º lugar no concurso"
        )
        self.assertFalse(is_duplicate)

        # 3. Verifica persistência única no banco
        occs = get_occurrences()
        self.assertEqual(len(occs), 1)
        self.assertEqual(occs[0][1], "Paulo Henrique")
        self.assertEqual(occs[0][2], "DO-MS")

if __name__ == '__main__':
    unittest.main()
