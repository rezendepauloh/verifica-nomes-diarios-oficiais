# -*- coding: utf-8 -*-
"""
Testes unitários para o componente de paginação reutilizável (pagination.py).
"""
import unittest
from unittest.mock import MagicMock
import tests.test_helpers
from src.components.pagination import paginate_items, render_items_per_page_selector

class TestPaginationComponent(unittest.TestCase):
    """Testa lógica pura de fatiamento e gerenciamento de páginas."""

    def test_paginate_items_empty(self):
        items = []
        slice_res, current_page, total_pages, total_items = paginate_items(items, page_key="test_empty", items_per_page=10)
        self.assertEqual(len(slice_res), 0)
        self.assertEqual(current_page, 1)
        self.assertEqual(total_pages, 0)
        self.assertEqual(total_items, 0)

    def test_paginate_items_slicing(self):
        import streamlit as st
        st.session_state = {}

        items = list(range(1, 26))  # 25 itens
        # Página 1 (itens 1 a 10)
        slice_1, cur_p1, total_p, total_it = paginate_items(items, page_key="test_seq", items_per_page=10)
        self.assertEqual(len(slice_1), 10)
        self.assertEqual(slice_1[0], 1)
        self.assertEqual(slice_1[-1], 10)
        self.assertEqual(cur_p1, 1)
        self.assertEqual(total_p, 3)
        self.assertEqual(total_it, 25)

        # Página 2 (itens 11 a 20)
        st.session_state["test_seq_current_page"] = 2
        slice_2, cur_p2, _, _ = paginate_items(items, page_key="test_seq", items_per_page=10)
        self.assertEqual(len(slice_2), 10)
        self.assertEqual(slice_2[0], 11)
        self.assertEqual(cur_p2, 2)

        # Página 3 (itens 21 a 25)
        st.session_state["test_seq_current_page"] = 3
        slice_3, cur_p3, _, _ = paginate_items(items, page_key="test_seq", items_per_page=10)
        self.assertEqual(len(slice_3), 5)
        self.assertEqual(slice_3[-1], 25)
        self.assertEqual(cur_p3, 3)

    def test_paginate_items_clamp_overflow(self):
        import streamlit as st
        items = list(range(1, 15))  # 2 páginas de 10
        st.session_state["overflow_current_page"] = 99  # página inexistente

        slice_res, cur_p, total_p, _ = paginate_items(items, page_key="overflow", items_per_page=10)
        self.assertEqual(cur_p, 2)
        self.assertEqual(total_p, 2)
        self.assertEqual(len(slice_res), 4)

    def test_render_items_per_page_selector_custom_container(self):
        mock_container = MagicMock()
        mock_container.selectbox.return_value = 50
        val = render_items_per_page_selector(
            key_prefix="test_sel",
            options=[10, 20, 50, "Todos"],
            container=mock_container
        )
        self.assertEqual(val, 50)
        mock_container.selectbox.assert_called_once()

    def test_render_items_per_page_selector_todos_option(self):
        mock_container = MagicMock()
        mock_container.selectbox.return_value = "Todos"
        val = render_items_per_page_selector(
            key_prefix="test_sel_all",
            options=[10, 20, "Todos"],
            container=mock_container
        )
        self.assertEqual(val, 999999)

if __name__ == '__main__':
    unittest.main()
