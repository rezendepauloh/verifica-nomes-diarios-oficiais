# -*- coding: utf-8 -*-
"""
Ponto de entrada do Painel Streamlit.
Importa a estilização e inicializa os módulos organizados em `src/`.
"""
import sys
from pathlib import Path
import streamlit as st

# Garante a raiz do projeto e 'src' no sys.path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

# Configuração da página Streamlit
st.set_page_config(
    page_title="Rastreador de Concursos e Diários",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Carrega arquivo de estilos CSS globais
css_path = ROOT_DIR / "assets" / "css" / "styles.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Importações dos módulos estruturados em src
from src.database import init_db, get_occurrences
from src.components import render_header, render_sidebar, render_metrics, render_scan_control
from src.tabs import render_dashboard_tab

# 1. Inicializa o banco de dados
init_db()

# 2. Renderiza o cabeçalho
render_header()

# 3. Renderiza a barra lateral e obtém os filtros
active_names, selected_sources = render_sidebar()

# 4. Obtém ocorrências e renderiza os cards de métricas
occurrences = get_occurrences()
render_metrics(occurrences)

# 5. Renderiza os controles de varredura (botão / logs de progresso)
render_scan_control(selected_sources, active_names)

# 6. Renderiza a tabela de ocorrências e gráfico
render_dashboard_tab(occurrences)
