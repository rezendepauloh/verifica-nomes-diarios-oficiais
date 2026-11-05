# -*- coding: utf-8 -*-
"""
Componente de Header moderno da aplicação:
- Títulos e subtítulos dinâmicos baseados na aba ativa
- Menu Drawer / Popover suspenso no canto superior direito (idêntico ao paulo-investimentos-pessoais)
- Sincronização limpa com URL (?tab=slug)
"""
import streamlit as st
from src.logger import logger

PAGES_CONFIG = [
    {"id": "dashboard", "slug": "dashboard", "label": "📋 Painel & Ocorrências"},
    {"id": "editais", "slug": "editais", "label": "📚 Editais & Concursos"},
    {"id": "configuracoes", "slug": "configuracoes", "label": "⚙️ Configurações & Fontes"}
]

PAGE_HEADER_INFO = {
    "dashboard": {
        "title": "📋 Monitoramento de Diários Oficiais",
        "subtitle": "Rastreamento automatizado em tempo real de nomes de interesse no DOU, DOE/MS, IFMS, Sanesul e municípios."
    },
    "editais": {
        "title": "📚 Central de Editais & Planejamento de Concursos",
        "subtitle": "Gestão de editais em PDF, cronograma inteligente de prazos e edital verticalizado interativo."
    },
    "configuracoes": {
        "title": "⚙️ Configurações do Sistema & Fontes",
        "subtitle": "Gerenciamento de pessoas monitoradas, notificações via WhatsApp, agendamento de cron e fontes de dados."
    }
}

SLUG_TO_PAGE = {p["slug"]: p["id"] for p in PAGES_CONFIG}
PAGE_TO_SLUG = {p["id"]: p["slug"] for p in PAGES_CONFIG}

def render_header() -> str:
    """
    Renderiza o cabeçalho superior e o menu popover no canto direito.
    Retorna o ID da página ativa.
    """
    url_tab = st.query_params.get("tab")
    if url_tab and url_tab in SLUG_TO_PAGE:
        st.session_state.current_page = SLUG_TO_PAGE[url_tab]
    elif "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"

    current_slug = PAGE_TO_SLUG.get(st.session_state.current_page, "dashboard")
    if st.query_params.get("tab") != current_slug:
        st.query_params["tab"] = current_slug

    def set_page(page_id: str):
        st.session_state.current_page = page_id
        st.query_params["tab"] = PAGE_TO_SLUG.get(page_id, "dashboard")
        if "subtab" in st.query_params:
            del st.query_params["subtab"]
        st.rerun()

    header_info = PAGE_HEADER_INFO.get(st.session_state.current_page, PAGE_HEADER_INFO["dashboard"])

    header_col1, header_col2 = st.columns([8.2, 1.8], vertical_alignment="center")

    with header_col1:
        st.markdown(f"""
        <div class="dashboard-header-left">
            <h1 class="dashboard-title">{header_info['title']}</h1>
            <p class="dashboard-subtitle">{header_info['subtitle']}</p>
        </div>
        """, unsafe_allow_html=True)

    with header_col2:
        with st.popover("☰ Menu", use_container_width=True):
            st.markdown('<div class="menu-popover-title">📌 Módulos do Sistema</div>', unsafe_allow_html=True)
            for page in PAGES_CONFIG:
                is_active = (st.session_state.current_page == page["id"])
                btn_type = "primary" if is_active else "secondary"
                if st.button(page["label"], key=f"nav_btn_{page['id']}", use_container_width=True, type=btn_type):
                    set_page(page["id"])

    st.markdown("<div class='header-divider'></div>", unsafe_allow_html=True)
    return st.session_state.current_page
