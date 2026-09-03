# -*- coding: utf-8 -*-
"""
Modal / Diálogo com detalhes completos e gestão de status da ocorrência.
"""
import re
import pandas as pd
import streamlit as st
from src.database import update_status

def get_accent_insensitive_pattern(text: str) -> str:
    accent_map = {
        'a': '[aáàâãä]', 'á': '[aáàâãä]', 'à': '[aáàâãä]', 'â': '[aáàâãä]', 'ã': '[aáàâãä]', 'ä': '[aáàâãä]',
        'e': '[eéèêë]', 'é': '[eéèêë]', 'è': '[eéèêë]', 'ê': '[eéèêë]', 'ë': '[eéèêë]',
        'i': '[iíìîï]', 'í': '[iíìîï]', 'ì': '[iíìîï]', 'î': '[iíìîï]', 'ï': '[iíìîï]',
        'o': '[oóòôõö]', 'ó': '[oóòôõö]', 'ò': '[oóòôõö]', 'ô': '[oóòôõö]', 'õ': '[oóòôõö]', 'ö': '[oóòôõö]',
        'u': '[uúùûü]', 'ú': '[uúùûü]', 'ù': '[uúùûü]', 'û': '[uúùûü]', 'ü': '[uúùûü]',
        'c': '[cç]', 'ç': '[cç]',
        'n': '[nñ]', 'ñ': '[nñ]'
    }
    pattern = ""
    for char in text:
        char_lower = char.lower()
        if char_lower in accent_map:
            pattern += accent_map[char_lower]
        else:
            pattern += re.escape(char)
    return pattern

def highlight_match(match):
    return f'<mark style="background-color: #ffc107; color: #212529; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{match.group(0)}</mark>'

@st.dialog("Detalhes da Ocorrência")
def show_occurrence_details(row):
    st.markdown(f"### 👤 {row['Nome']}")
    st.markdown(f"**Fonte:** {row['Fonte']}")
    
    data_formatada = row['Data da Busca'].strftime("%d/%m/%Y") if not pd.isnull(row['Data da Busca']) else "Sem Data"
    st.markdown(f"**Data da Publicação:** {data_formatada}")
    
    st.markdown("---")
    st.markdown("### 📝 Trecho / Contexto Encontrado")
    
    contexto = row['Contexto / Trecho']
    nome = row['Nome']
    
    pattern = get_accent_insensitive_pattern(nome)
    contexto_html = re.sub(pattern, highlight_match, contexto, flags=re.IGNORECASE)
    st.markdown(f'<div style="background-color: #f8f9fa; color: #212529; padding: 1.2rem; border-radius: 8px; border-left: 5px solid #2a5298; font-size: 1.05rem; line-height: 1.6; border-right: 1px solid #dee2e6; border-top: 1px solid #dee2e6; border-bottom: 1px solid #dee2e6;">{contexto_html}</div>', unsafe_allow_html=True)
    
    if row['Link']:
        st.markdown("---")
        st.link_button("🔗 Abrir Link Oficial / PDF", row['Link'], width='stretch')
        
    st.markdown("---")
    st.markdown("#### ⚙️ Gerenciar Status")
    status_novo = st.radio("Alterar status deste registro:", ["Pendente", "Lido"], index=0 if row['Status'] == "Pendente" else 1, horizontal=True)
    
    col_salvar, col_fechar = st.columns(2)
    with col_salvar:
        if st.button("💾 Salvar Status", width='stretch'):
            update_status(row['ID'], status_novo)
            if "occurrences_table" in st.session_state:
                st.session_state["occurrences_table"] = {"selection": {"rows": [], "columns": []}}
            st.success("Status atualizado!")
            st.rerun()
    with col_fechar:
        if st.button("Fechar", width='stretch'):
            if "occurrences_table" in st.session_state:
                st.session_state["occurrences_table"] = {"selection": {"rows": [], "columns": []}}
            st.rerun()
