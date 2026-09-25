# -*- coding: utf-8 -*-
"""
Testes unitários para utilitários de scraping (limpeza de texto, caminhos locais e dicionário de robôs).
"""
import os
from src.scrapers.engine import clean_text, extract_json_array, get_local_file_path, is_scraper_implemented, AVAILABLE_SCRAPERS

class TestScraperHelpers:
    """Valida funções auxiliares de tratamento de dados dos scrapers."""

    def test_clean_text(self):
        html_sample = "  <p>Convocação do candidato <b>Paulo</b></p>&lt;tag&gt;   "
        cleaned = clean_text(html_sample)
        assert "<p>" not in cleaned
        assert "<b>" not in cleaned
        assert "<tag>" in cleaned
        assert "  " not in cleaned

    def test_extract_json_array(self):
        html = '<div>prefix{"jsonArray":[{"id":1,"title":"Edital"}]}suffix</div>'
        extracted = extract_json_array(html)
        assert extracted == '{"jsonArray":[{"id":1,"title":"Edital"}]}'

    def test_extract_json_array_not_found(self):
        assert extract_json_array("<div>Sem json aqui</div>") is None

    def test_get_local_file_path(self):
        url = "https://exemplo.com/editais/resultado_final.pdf"
        path = get_local_file_path("sanesul", url)
        assert "uploads" in path
        assert "sanesul" in path
        assert path.endswith(".pdf")

    def test_scraper_registered(self):
        # DOU e DO-MS devem estar implementados
        assert is_scraper_implemented("dou") is True
        assert is_scraper_implemented("doms") is True
        assert is_scraper_implemented("sanesul") is True
        # Fonte inexistente
        assert is_scraper_implemented("fonte_inexistente_xyz") is False
