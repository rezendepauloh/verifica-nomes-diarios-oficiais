# -*- coding: utf-8 -*-
"""
Testes unitários para utilitários de scraping (limpeza de texto, caminhos locais e dicionário de robôs).
Compatível tanto com pytest quanto com unittest runner.
"""
import os
import unittest

import tests.test_helpers
from src.scrapers.engine import clean_text, extract_json_array, get_local_file_path, is_scraper_implemented, AVAILABLE_SCRAPERS

class TestScraperHelpers(unittest.TestCase):
    """Valida funções auxiliares de tratamento de dados dos scrapers."""

    def test_clean_text(self):
        html_sample = "  <p>Convocação do candidato <b>Paulo</b></p>&lt;tag&gt;   "
        cleaned = clean_text(html_sample)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("<b>", cleaned)
        self.assertIn("<tag>", cleaned)
        self.assertNotIn("  ", cleaned)

    def test_extract_json_array(self):
        html = '<div>prefix{"jsonArray":[{"id":1,"title":"Edital"}]}suffix</div>'
        extracted = extract_json_array(html)
        self.assertEqual(extracted, '{"jsonArray":[{"id":1,"title":"Edital"}]}')

    def test_extract_json_array_not_found(self):
        self.assertIsNone(extract_json_array("<div>Sem json aqui</div>"))

    def test_get_local_file_path(self):
        url = "https://exemplo.com/editais/resultado_final.pdf"
        path = get_local_file_path("sanesul", url)
        self.assertIn("uploads", path)
        self.assertIn("sanesul", path)
        self.assertTrue(path.endswith(".pdf"))

    def test_scraper_registered(self):
        # DOU e DO-MS devem estar implementados
        self.assertTrue(is_scraper_implemented("dou"))
        self.assertTrue(is_scraper_implemented("doms"))
        self.assertTrue(is_scraper_implemented("sanesul"))
        self.assertTrue(is_scraper_implemented("mpms"))
        # Fonte inexistente
        self.assertFalse(is_scraper_implemented("fonte_inexistente_xyz"))

if __name__ == '__main__':
    unittest.main()
