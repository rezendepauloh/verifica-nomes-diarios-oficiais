# -*- coding: utf-8 -*-
"""
Componente reutilizável para renderização de sub-abas estilizadas no Streamlit,
com sincronização automática via st.query_params.
"""
import streamlit as st

def render_subtabs(
    tab_map: dict,
    default_slug: str,
    key: str = "main_subtabs",
    param_name: str = "subtab"
) -> str:
    """
    Renderiza um st.radio estilizado como abas nativas e sincroniza a escolha com st.query_params[param_name].

    Args:
        tab_map (dict): Mapeamento de slug para título da aba (ex: {"nomes": "👥 Nomes", "fontes": "🌐 Fontes"}).
        default_slug (str): Slug padrão a ser utilizado se a URL não possuir um slug válido.
        key (str): Chave única para o componente st.radio.
        param_name (str): Nome do parâmetro de URL (ex: 'tab' ou 'subtab'). Padrão 'subtab'.

    Returns:
        str: O slug da aba selecionada.
    """
    subtab_slugs = list(tab_map.keys())

    # Lê o slug da URL ou define pelo default_slug
    current_slug_url = st.query_params.get(param_name, default_slug)
    if current_slug_url not in subtab_slugs:
        current_slug_url = default_slug

    default_index = subtab_slugs.index(current_slug_url)

    selected_slug = st.radio(
        label=f"{param_name}_nav",
        options=subtab_slugs,
        format_func=lambda slug: tab_map[slug],
        index=default_index,
        horizontal=True,
        label_visibility="collapsed",
        key=key,
    )

    if selected_slug != current_slug_url:
        st.query_params[param_name] = selected_slug

    return selected_slug

