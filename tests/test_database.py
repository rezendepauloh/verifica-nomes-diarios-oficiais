# -*- coding: utf-8 -*-
"""
Testes unitários para o banco de dados SQLite (CRUD de ocorrências, nomes, fontes e agendamento).
"""
import pytest
from src.database.db import (
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

class TestOccurrences:
    """Testa armazenamento e integridade de ocorrências."""

    def test_save_new_occurrence(self):
        is_new = save_occurrence("Paulo Henrique", "DO-MS", "24/09/2026", "https://link.com/1", "Contexto de teste")
        assert is_new is True

        occs = get_occurrences()
        assert len(occs) == 1
        assert occs[0][1] == "Paulo Henrique"
        assert occs[0][2] == "DO-MS"
        assert occs[0][6] == "Pendente"

    def test_save_duplicate_occurrence_is_ignored(self):
        is_new1 = save_occurrence("Paulo", "DOU", "24/09/2026", "https://link.com/2", "Contexto")
        is_new2 = save_occurrence("Paulo", "DOU", "24/09/2026", "https://link.com/2", "Contexto")
        assert is_new1 is True
        assert is_new2 is False

        occs = get_occurrences()
        assert len(occs) == 1

    def test_update_status(self):
        save_occurrence("Paulo", "DO-MS", "24/09/2026", "https://link.com/3", "Texto")
        occ_id = get_occurrences()[0][0]

        update_status(occ_id, "Lido")
        updated = get_occurrences()
        assert updated[0][6] == "Lido"

    def test_update_status_bulk(self):
        save_occurrence("Paulo", "DO-MS", "24/09/2026", "https://link.com/4", "Texto 1")
        save_occurrence("Kamila", "DO-MS", "24/09/2026", "https://link.com/5", "Texto 2")
        ids = [row[0] for row in get_occurrences()]

        update_status_bulk(ids, "Lido")
        for row in get_occurrences():
            assert row[6] == "Lido"


class TestMonitoredNames:
    """Testa cadastro, edição e consulta de nomes monitorados."""

    def test_add_and_get_names(self):
        success = add_monitored_name("Paulo Henrique", "(67) 99247-1379", "3587903")
        assert success is True

        all_names = get_all_monitored_names()
        assert len(all_names) == 1
        assert all_names[0][1] == "Paulo Henrique"
        assert all_names[0][2] == "(67) 99247-1379"
        assert all_names[0][3] == "3587903"
        assert all_names[0][4] == 1  # active

    def test_add_duplicate_name_fails(self):
        add_monitored_name("Paulo", "(67) 99247-1379")
        assert add_monitored_name("Paulo", "(67) 99247-1379") is False

    def test_toggle_name_status(self):
        add_monitored_name("Paulo", "(67) 99247-1379")
        name_id = get_all_monitored_names()[0][0]

        toggle_monitored_name(name_id, current_active=1)
        assert len(get_active_monitored_names()) == 0

        toggle_monitored_name(name_id, current_active=0)
        assert len(get_active_monitored_names()) == 1

    def test_delete_name(self):
        add_monitored_name("Paulo", "(67) 99247-1379")
        name_id = get_all_monitored_names()[0][0]
        assert delete_monitored_name(name_id) is True
        assert len(get_all_monitored_names()) == 0

    def test_whatsapp_notification_recipients(self):
        add_monitored_name("Paulo", "(67) 99247-1379", "3587903")
        add_monitored_name("Kamila", "(67) 99853-8804", "9835298")
        add_monitored_name("Sem Chave", "(67) 3345-0000", "")

        recipients = get_whatsapp_notification_recipients()
        assert len(recipients) == 2
        names = [r["name"] for r in recipients]
        assert "Paulo" in names
        assert "Kamila" in names


class TestProcessedUrls:
    """Testa controle de cache de URLs processadas."""

    def test_processed_url_workflow(self):
        url = "https://concursos.ms.gov.br/edital_1.pdf"
        assert is_url_processed(url, "Paulo") is False

        mark_url_processed(url, "Paulo")
        assert is_url_processed(url, "Paulo") is True
        assert is_url_processed(url, "Outro Nome") is False


class TestScheduleConfig:
    """Testa preferências de agendamento automático."""

    def test_default_schedule(self):
        config = get_schedule_config()
        assert config is not None
        assert config["enabled"] == 1
        assert "mon" in config["days_of_week"]

    def test_save_and_retrieve_schedule(self):
        save_schedule_config(
            enabled=1,
            days_of_week=["mon", "wed", "fri"],
            times=["07:30", "15:00"]
        )
        config = get_schedule_config()
        assert config["days_of_week"] == ["mon", "wed", "fri"]
        assert config["times"] == ["07:30", "15:00"]
