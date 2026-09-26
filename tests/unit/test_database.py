# -*- coding: utf-8 -*-
"""
Testes unitários para o banco de dados SQLite (CRUD de ocorrências, nomes, fontes e agendamento).
Compatível tanto com pytest quanto com unittest runner (ColoredTestRunner).
"""
import os
import tempfile
import unittest
from pathlib import Path

import tests.test_helpers

from src.database.db import (
    init_db,
    save_occurrence,
    get_occurrences,
    update_status,
    update_status_bulk,
    is_url_processed,
    mark_url_processed,
    add_monitored_name,
    get_all_monitored_names,
    get_active_monitored_names,
    update_monitored_name,
    toggle_monitored_name,
    delete_monitored_name,
    get_whatsapp_notification_recipients,
    add_monitored_source,
    get_all_monitored_sources,
    get_active_monitored_sources,
    get_schedule_config,
    save_schedule_config
)
import src.database.db as db_mod
import src.config as cfg_mod

class BaseIsolatedDbTest(unittest.TestCase):
    """Fixture base que isola o SQLite em arquivo temporário por teste."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_db.sqlite"
        self._orig_db_path = db_mod.DB_PATH
        self._orig_cfg_path = cfg_mod.DB_PATH
        db_mod.DB_PATH = self.test_db_path
        cfg_mod.DB_PATH = self.test_db_path
        self._orig_env_names = os.environ.get("MONITOR_NAMES")
        os.environ["MONITOR_NAMES"] = ""
        init_db()

    def tearDown(self):
        db_mod.DB_PATH = self._orig_db_path
        cfg_mod.DB_PATH = self._orig_cfg_path
        if self._orig_env_names is not None:
            os.environ["MONITOR_NAMES"] = self._orig_env_names
        else:
            os.environ.pop("MONITOR_NAMES", None)
        self.temp_dir.cleanup()

class TestOccurrences(BaseIsolatedDbTest):
    """Testa armazenamento e integridade de ocorrências."""

    def test_save_new_occurrence(self):
        is_new = save_occurrence("Paulo Henrique", "DO-MS", "24/09/2026", "https://link.com/1", "Contexto de teste")
        self.assertTrue(is_new)

        occs = get_occurrences()
        self.assertEqual(len(occs), 1)
        self.assertEqual(occs[0][1], "Paulo Henrique")
        self.assertEqual(occs[0][2], "DO-MS")
        self.assertEqual(occs[0][6], "Pendente")

    def test_save_duplicate_occurrence_is_ignored(self):
        is_new1 = save_occurrence("Paulo", "DOU", "24/09/2026", "https://link.com/2", "Contexto")
        is_new2 = save_occurrence("Paulo", "DOU", "24/09/2026", "https://link.com/2", "Contexto")
        self.assertTrue(is_new1)
        self.assertFalse(is_new2)

        occs = get_occurrences()
        self.assertEqual(len(occs), 1)

    def test_update_status(self):
        save_occurrence("Paulo", "DO-MS", "24/09/2026", "https://link.com/3", "Texto")
        occ_id = get_occurrences()[0][0]

        update_status(occ_id, "Lido")
        updated = get_occurrences()
        self.assertEqual(updated[0][6], "Lido")

    def test_update_status_bulk(self):
        save_occurrence("Paulo", "DO-MS", "24/09/2026", "https://link.com/4", "Texto 1")
        save_occurrence("Kamila", "DO-MS", "24/09/2026", "https://link.com/5", "Texto 2")
        ids = [row[0] for row in get_occurrences()]

        update_status_bulk(ids, "Lido")
        for row in get_occurrences():
            self.assertEqual(row[6], "Lido")


class TestMonitoredNames(BaseIsolatedDbTest):
    """Testa cadastro, edição e consulta de nomes monitorados."""

    def test_add_and_get_names(self):
        success = add_monitored_name("Paulo Henrique", "(67) 99247-1379", "3587903")
        self.assertTrue(success)

        all_names = get_all_monitored_names()
        self.assertEqual(len(all_names), 1)
        self.assertEqual(all_names[0][1], "Paulo Henrique")
        self.assertEqual(all_names[0][2], "(67) 99247-1379")
        self.assertEqual(all_names[0][3], "3587903")
        self.assertEqual(all_names[0][4], 1)

    def test_add_duplicate_name_fails(self):
        add_monitored_name("Paulo", "(67) 99247-1379")
        self.assertFalse(add_monitored_name("Paulo", "(67) 99247-1379"))

    def test_toggle_name_status(self):
        add_monitored_name("Paulo", "(67) 99247-1379")
        name_id = get_all_monitored_names()[0][0]

        toggle_monitored_name(name_id, current_active=1)
        self.assertEqual(len(get_active_monitored_names()), 0)

        toggle_monitored_name(name_id, current_active=0)
        self.assertEqual(len(get_active_monitored_names()), 1)

    def test_delete_name(self):
        add_monitored_name("Paulo", "(67) 99247-1379")
        name_id = get_all_monitored_names()[0][0]
        self.assertTrue(delete_monitored_name(name_id))
        self.assertEqual(len(get_all_monitored_names()), 0)

    def test_whatsapp_notification_recipients(self):
        add_monitored_name("Paulo", "(67) 99247-1379", "3587903")
        add_monitored_name("Kamila", "(67) 99853-8804", "9835298")
        add_monitored_name("Sem Chave", "(67) 3345-0000", "")

        recipients = get_whatsapp_notification_recipients()
        self.assertEqual(len(recipients), 2)
        names = [r["name"] for r in recipients]
        self.assertIn("Paulo", names)
        self.assertIn("Kamila", names)


class TestProcessedUrls(BaseIsolatedDbTest):
    """Testa controle de cache de URLs processadas."""

    def test_processed_url_workflow(self):
        url = "https://concursos.ms.gov.br/edital_1.pdf"
        self.assertFalse(is_url_processed(url, "Paulo"))

        mark_url_processed(url, "Paulo")
        self.assertTrue(is_url_processed(url, "Paulo"))
        self.assertFalse(is_url_processed(url, "Outro Nome"))


class TestScheduleConfig(BaseIsolatedDbTest):
    """Testa preferências de agendamento automático."""

    def test_default_schedule(self):
        config = get_schedule_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["enabled"], 1)
        self.assertIn("mon", config["days_of_week"])

    def test_save_and_retrieve_schedule(self):
        save_schedule_config(
            enabled=1,
            days_of_week=["mon", "wed", "fri"],
            times=["07:30", "15:00"]
        )
        config = get_schedule_config()
        self.assertEqual(config["days_of_week"], ["mon", "wed", "fri"])
        self.assertEqual(config["times"], ["07:30", "15:00"])


class TestScanHistory(BaseIsolatedDbTest):
    """Testa persistência e consulta do histórico de execuções do cron."""

    def test_record_and_get_history(self):
        from src.database.db import record_scan_execution, get_scan_history
        # 1. Histórico vazio inicialmente
        self.assertEqual(len(get_scan_history()), 0)

        # 2. Registra disparo automático com sucesso
        ok1 = record_scan_execution(trigger_type="automático", new_records=3, success=True, details="3 editais novos")
        self.assertTrue(ok1)

        # 3. Registra disparo manual com falha simulada
        ok2 = record_scan_execution(trigger_type="manual (painel)", new_records=0, success=False, details="Timeout na conexão")
        self.assertTrue(ok2)

        history = get_scan_history(limit=10)
        self.assertEqual(len(history), 2)
        # Mais recente primeiro
        self.assertEqual(history[0][2], "manual (painel)")
        self.assertEqual(history[0][3], 0)
        self.assertEqual(history[0][4], 0)  # Falha

        self.assertEqual(history[1][2], "automático")
        self.assertEqual(history[1][3], 3)
        self.assertEqual(history[1][4], 1)  # Sucesso

if __name__ == '__main__':
    unittest.main()
