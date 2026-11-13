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
from src.scheduler import start_scheduler_if_not_running
from src.components import render_header, render_dashboard_sidebar, render_metrics, render_scan_control
from src.tabs import render_dashboard_tab, render_configuracoes_tab, render_editais_tab
from src.security import enforce_streamlit_auth

# 0. Guard de autenticação WebUI (Fail-Closed quando APP_AUTH_REQUIRED=true)
enforce_streamlit_auth()

# 1. Inicializa o banco de dados e seed
init_db()

# 2. Inicia o agendador em background (Thread Singleton)
start_scheduler_if_not_running()

# 3. Renderiza o cabeçalho moderno e obtém a página ativa (gerenciada exclusivamente pelo Menu Drawer)
active_main_tab = render_header()

if active_main_tab == "dashboard":
    # 4. Na aba de Dashboard, renderiza os filtros específicos na barra lateral
    from src.components.sidebar import render_dashboard_sidebar
    active_names, selected_sources, items_per_page = render_dashboard_sidebar()

    # 5. Obtém ocorrências e renderiza os cards de métricas
    occurrences = get_occurrences()
    render_metrics(occurrences)

    # 6. Renderiza os controles de varredura (botão / logs de progresso)
    render_scan_control(selected_sources, active_names)

    # 7. Renderiza a tabela de ocorrências e gráfico com paginação
    render_dashboard_tab(occurrences, items_per_page=items_per_page)

elif active_main_tab == "editais":
    # Renderiza a central completa de editais (com sua própria sidebar)
    render_editais_tab()

elif active_main_tab == "configuracoes":
    # Na aba de Configurações, renderiza mensagem informativa na sidebar
    from src.components.sidebar import render_configuracoes_sidebar
    render_configuracoes_sidebar()
    render_configuracoes_tab()

