# -*- coding: utf-8 -*-
"""
Componente lateral (Sidebar) com filtros de nomes e fontes.
"""
import streamlit as st
from src.config import get_monitored_names

def render_sidebar():
    """Renderiza as opções de nomes e fontes ativas na barra lateral."""
    st.sidebar.markdown("### ⚙️ Configurações de Monitoramento")
    st.sidebar.write("Selecionar nomes para busca ativa:")
    
    monitored_names = get_monitored_names()
    active_names = []
    for name in monitored_names:
        if st.sidebar.checkbox(name, value=True, key=f"name_{name}"):
            active_names.append(name)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔗 Selecionar Fontes Ativas")
    active_dou = st.sidebar.checkbox("Diário Oficial da União (DOU)", value=True)
    active_doms = st.sidebar.checkbox("Diário Oficial do MS (DO-MS)", value=True)
    active_ifms = st.sidebar.checkbox("IFMS (SUAP)", value=True)
    active_sanesul = st.sidebar.checkbox("Sanesul", value=True)
    active_msgas = st.sidebar.checkbox("MS Gás", value=True)
    active_crbm = st.sidebar.checkbox("CRBM 1ª Região", value=True)
    active_dourados = st.sidebar.checkbox("Diário Oficial de Dourados (DO-Dourados)", value=True)

    selected_sources = {
        "dou": active_dou,
        "doms": active_doms,
        "ifms": active_ifms,
        "sanesul": active_sanesul,
        "msgas": active_msgas,
        "crbm": active_crbm,
        "dourados": active_dourados,
    }

    return active_names, selected_sources
