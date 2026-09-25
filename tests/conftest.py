# -*- coding: utf-8 -*-
"""
Configurações e fixtures globais de teste para o pytest.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Garante raiz do projeto e src/ no sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """
    Garante que cada teste utilize um banco SQLite temporário isolado em tmp_path,
    sem carregar nomes do .env nem tocar no results.db do ambiente real.
    """
    test_db_path = tmp_path / "test_results.db"
    monkeypatch.setattr("src.database.db.DB_PATH", test_db_path)
    monkeypatch.setattr("src.config.DB_PATH", test_db_path)
    monkeypatch.setenv("MONITOR_NAMES", "")
    
    from src.database.db import init_db
    init_db()
    
    yield test_db_path
