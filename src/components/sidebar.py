# -*- coding: utf-8 -*-
"""
Componente lateral (Sidebar) com filtros de nomes e fontes.
"""
import streamlit as st
from src.database import get_all_monitored_names, get_all_monitored_sources
from src.scrapers import is_scraper_implemented

def render_sidebar():
    """Renderiza as opções de nomes e fontes ativas na barra lateral a partir do SQLite."""
    st.sidebar.markdown("### ⚙️ Configurações de Busca")
    
    # 1. Nomes Ativos
    st.sidebar.markdown("#### 👥 Nomes Ativos")
    all_names = get_all_monitored_names()
    active_names = []
    
    if all_names:
        for item in all_names:
            name_id, name, phone, active, _ = item
            # Pré-marca os que estão ativos no banco
            if st.sidebar.checkbox(name, value=(active == 1), key=f"sb_name_{name_id}"):
                active_names.append(name)
    else:
        st.sidebar.caption("Nenhum nome cadastrado.")

    st.sidebar.markdown("---")
    
    # 2. Fontes de Dados
    st.sidebar.markdown("#### 🔗 Fontes de Dados")
    all_sources = get_all_monitored_sources()
    selected_sources = {}

    if all_sources:
        for item in all_sources:
            src_id, slug, label, url, desc, active, _ = item
            has_bot = is_scraper_implemented(slug)
            ticket = "✓" if has_bot else "❌"
            display_label = f"{label} [{ticket}]"
            
            # Checa se está ativo no banco
            is_checked = st.sidebar.checkbox(
                display_label,
                value=(active == 1),
                key=f"sb_source_{src_id}",
                help=f"Slug: {slug} | Status do Scraper: {'Implementado' if has_bot else 'Aguardando desenvolvimento'}"
            )
            selected_sources[slug] = is_checked
    else:
        st.sidebar.caption("Nenhuma fonte cadastrada.")

    return active_names, selected_sources

