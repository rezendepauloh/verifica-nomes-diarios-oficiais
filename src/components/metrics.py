# -*- coding: utf-8 -*-
"""
Componente de Cards Métricos (Indicadores).
"""
import streamlit as st

def render_metrics(occurrences):
    """Renderiza os cards métricos de Total, Pendentes e Lidos."""
    total_found = len(occurrences)
    pendentes = sum(1 for row in occurrences if row[6] == "Pendente")
    resolvidos = total_found - pendentes

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #2a5298;">
            <div class="metric-title">Total Detectado</div>
            <div class="metric-value">{total_found}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #ffc107;">
            <div class="metric-title">Alertas Pendentes</div>
            <div class="metric-value">{pendentes}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #28a745;">
            <div class="metric-title">Acompanhados / Lidos</div>
            <div class="metric-value">{resolvidos}</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.write("")
