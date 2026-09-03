# -*- coding: utf-8 -*-
"""
Componente de Header da aplicação.
"""
import streamlit as st

def render_header():
    """Renderiza o cabeçalho moderno com gradiente e títulos."""
    st.markdown("""
    <div class="header-container">
        <h1 class="header-title">🔍 Monitor de Diários Oficiais & Concursos</h1>
        <p class="header-subtitle">Varredura automática e centralização de publicações de interesse</p>
    </div>
    """, unsafe_allow_html=True)
