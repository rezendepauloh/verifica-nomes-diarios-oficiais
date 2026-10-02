# -*- coding: utf-8 -*-
"""
Helper universal de testes para o Verificador de Diários Oficiais.
Garante mocks seguros e transparentes de dependências de terceiros (dotenv, pdfplumber, bs4, streamlit, pandas, requests)
permitindo que a suíte inteira rode com 100% de confiabilidade e isolamento tanto no host local
quanto dentro do contêiner Docker.
"""

import importlib.util
import sys
import types
from unittest.mock import MagicMock

def _is_installed(pkg_name: str) -> bool:
    """Verifica se um pacote está instalado sem emitir avisos de import estático para o LSP da IDE."""
    return importlib.util.find_spec(pkg_name) is not None

# 1. Mock seguro de python-dotenv
if _is_installed("dotenv"):
    import dotenv
else:
    mock_dotenv = types.ModuleType("dotenv")
    mock_dotenv.load_dotenv = MagicMock(return_value=True)
    mock_dotenv.dotenv_values = MagicMock(return_value={})
    sys.modules["dotenv"] = mock_dotenv

# 2. Mock seguro de pdfplumber
if _is_installed("pdfplumber"):
    import pdfplumber
else:
    mock_pdfplumber = types.ModuleType("pdfplumber")
    mock_pdf_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text = MagicMock(return_value="Texto de edital simulado")
    mock_pdf_doc.pages = [mock_page]
    mock_pdf_doc.__enter__ = MagicMock(return_value=mock_pdf_doc)
    mock_pdf_doc.__exit__ = MagicMock(return_value=None)
    mock_pdfplumber.open = MagicMock(return_value=mock_pdf_doc)
    sys.modules["pdfplumber"] = mock_pdfplumber

# 3. Mock seguro de BeautifulSoup4
if _is_installed("bs4"):
    import bs4
else:
    mock_bs4 = types.ModuleType("bs4")
    class MockBeautifulSoup(MagicMock):
        def __init__(self, markup="", features="html.parser", *args, **kwargs):
            super().__init__()
            self._text = str(markup)
        def get_text(self, *args, **kwargs):
            import re
            return re.sub(r"<[^>]+>", " ", self._text)
        def find_all(self, *args, **kwargs):
            return []
    mock_bs4.BeautifulSoup = MockBeautifulSoup
    sys.modules["bs4"] = mock_bs4

# 4. Mock seguro de Streamlit
if _is_installed("streamlit"):
    import streamlit as st
else:
    mock_st = types.ModuleType("streamlit")
    mock_st.session_state = {}
    mock_st.query_params = {}

    def _decorator_helper(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn

    mock_st.dialog = _decorator_helper
    mock_st.cache_data = _decorator_helper
    mock_st.cache_resource = _decorator_helper
    mock_st.radio = MagicMock(return_value="dashboard")
    mock_st.button = MagicMock(return_value=False)
    mock_st.selectbox = MagicMock(return_value="Todos")
    mock_st.markdown = MagicMock()
    mock_st.toast = MagicMock()
    mock_st.info = MagicMock()
    mock_st.success = MagicMock()
    mock_st.warning = MagicMock()
    mock_st.error = MagicMock()
    mock_st.columns = MagicMock(side_effect=lambda spec: [MagicMock() for _ in range(len(spec) if isinstance(spec, list) else int(spec))])
    mock_st.tabs = MagicMock(side_effect=lambda tabs: [MagicMock() for _ in range(len(tabs))])
    mock_st.rerun = MagicMock()

    mock_sidebar = MagicMock()
    mock_sidebar.selectbox = MagicMock(return_value=10)
    mock_sidebar.checkbox = MagicMock(return_value=True)
    mock_sidebar.markdown = MagicMock()
    mock_sidebar.caption = MagicMock()
    mock_st.sidebar = mock_sidebar

    mock_comp = types.ModuleType("streamlit.components")
    mock_comp_v1 = types.ModuleType("streamlit.components.v1")
    mock_comp_v1.html = MagicMock()
    mock_comp.v1 = mock_comp_v1
    mock_st.components = mock_comp

    sys.modules["streamlit"] = mock_st
    sys.modules["streamlit.components"] = mock_comp
    sys.modules["streamlit.components.v1"] = mock_comp_v1

# 5. Mock seguro de Pandas
if _is_installed("pandas"):
    import pandas as pd
else:
    mock_pd = types.ModuleType("pandas")

    class MockDataFrame:
        def __init__(self, data=None, columns=None, *args, **kwargs):
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], (list, tuple)):
                cols = list(columns) if columns else [f"col_{i}" for i in range(len(data[0]))]
                self.data = {cols[i]: [row[i] for row in data] for i in range(len(cols))}
                self.columns = cols
            elif isinstance(data, dict):
                self.data = dict(data)
                self.columns = columns or list(self.data.keys())
            else:
                self.data = {}
                self.columns = columns or []
            self.empty = len(self.data) == 0

        def sort_values(self, *args, **kwargs):
            return self

        def copy(self):
            return MockDataFrame(data=dict(self.data), columns=list(self.columns))

    mock_pd.DataFrame = MockDataFrame
    mock_pd.to_datetime = MagicMock(side_effect=lambda x, **kw: x)
    mock_pd.isna = lambda x: x is None or str(x).strip().lower() in ["none", "nan", ""]
    sys.modules["pandas"] = mock_pd
