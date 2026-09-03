# -*- coding: utf-8 -*-
"""
Aba principal com Lista de Ocorrências e Gráfico por Fonte/Status.
"""
import urllib.parse
from datetime import datetime
import pandas as pd
import streamlit as st
from src.database import update_status_bulk
from src.components.details_modal import show_occurrence_details

def format_highlight_link(row_item):
    link = row_item["Link"]
    if not link:
        return link
    nome_encoded = urllib.parse.quote(row_item["Nome"])
    if link.lower().endswith(".pdf") or "#page=" in link.lower():
        if "#page=" in link:
            return f"{link}&search={nome_encoded}"
        else:
            return f"{link}#search={nome_encoded}"
    else:
        return f"{link}#:~:text={nome_encoded}"

def render_dashboard_tab(occurrences):
    """Renderiza os filtros, tabela e gráficos das ocorrências."""
    if not occurrences:
        st.info("Nenhuma ocorrência encontrada até o momento. Clique no botão de varredura acima para buscar.")
        return

    # Cria dataframe a partir das ocorrências
    df = pd.DataFrame(occurrences, columns=["ID", "Nome", "Fonte", "Data da Busca", "Link", "Contexto / Trecho", "Status", "Registrado em"])
    
    # Converte para datetime para ordenação correta
    df["Data da Busca"] = pd.to_datetime(df["Data da Busca"], format="%d/%m/%Y", errors="coerce")
    
    # Ordenação padrão (mais recente primeiro)
    df = df.sort_values(by="Data da Busca", ascending=False)
    
    # Cria a coluna auxiliar 'Mês/Ano' formatada para o filtro
    df["Mês/Ano"] = df["Data da Busca"].dt.strftime("%m/%Y")
    df["Mês/Ano"] = df["Mês/Ano"].fillna("Sem Data")

    # Filtros interativos dispostos horizontalmente
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        nome_filter = st.selectbox("Filtrar por Nome:", ["Todos"] + list(df["Nome"].unique()))
    with col_f2:
        fonte_filter = st.selectbox("Filtrar por Fonte:", ["Todas"] + list(df["Fonte"].unique()))
    with col_f3:
        mes_ano_opts = sorted(
            [opt for opt in df["Mês/Ano"].unique() if opt != "Sem Data"],
            key=lambda x: datetime.strptime(x, "%m/%Y"),
            reverse=True
        )
        if "Sem Data" in df["Mês/Ano"].unique():
            mes_ano_opts.append("Sem Data")
        mes_filter = st.selectbox("Filtrar por Mês/Ano:", ["Todos"] + mes_ano_opts)
    with col_f4:
        status_filter = st.selectbox("Filtrar por Status:", ["Pendente", "Lido", "Todos"], index=0)
    
    filtered_df = df.copy()
    if nome_filter != "Todos":
        filtered_df = filtered_df[filtered_df["Nome"] == nome_filter]
    if fonte_filter != "Todas":
        filtered_df = filtered_df[filtered_df["Fonte"] == fonte_filter]
    if mes_filter != "Todos":
        filtered_df = filtered_df[filtered_df["Mês/Ano"] == mes_filter]
    if status_filter != "Todos":
        filtered_df = filtered_df[filtered_df["Status"] == status_filter]
        
    if not filtered_df.empty:
        filtered_df["Link"] = filtered_df.apply(format_highlight_link, axis=1)

    # Criação das abas para visualização compacta e dinâmica
    tab_tabela, tab_grafico = st.tabs(["📋 Lista de Ocorrências", "📊 Gráfico por Fonte"])

    with tab_tabela:
        col_act, col_exp = st.columns([2, 1])
        with col_act:
            pendentes_filtrados = filtered_df[filtered_df["Status"] == "Pendente"] if not filtered_df.empty else pd.DataFrame()
            if not pendentes_filtrados.empty:
                if st.button(f"✅ Marcar estes {len(pendentes_filtrados)} como Lidos", width='stretch'):
                    ids_to_update = pendentes_filtrados["ID"].tolist()
                    update_status_bulk(ids_to_update, "Lido")
                    st.success(f"{len(ids_to_update)} ocorrências atualizadas!")
                    st.rerun()
            else:
                st.button("✅ Sem pendências para marcar nesta visualização", disabled=True, width='stretch')
                
        with col_exp:
            if not filtered_df.empty:
                csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 Exportar para CSV",
                    data=csv_data,
                    file_name=f"ocorrencias_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width='stretch'
                )
            else:
                st.button("📥 Sem dados para exportar", disabled=True, width='stretch')
            
        st.caption("💡 Clique em uma linha da tabela abaixo para abrir os detalhes completos em um modal.")
        
        if not filtered_df.empty:
            selection_event = st.dataframe(
                filtered_df[["Nome", "Fonte", "Data da Busca", "Link", "Status"]],
                width='stretch',
                on_select="rerun",
                selection_mode="single-row",
                key="occurrences_table",
                column_config={
                    "Data da Busca": st.column_config.DateColumn("Data da Busca", format="DD/MM/YYYY"),
                    "Link": st.column_config.LinkColumn("Link", display_text="Abrir Link"),
                }
            )
            
            selected_rows = selection_event.selection.rows if hasattr(selection_event, "selection") else []
            if selected_rows:
                row_idx = selected_rows[0]
                row_data = filtered_df.iloc[row_idx]
                show_occurrence_details(row_data)
        else:
            st.info("Nenhuma ocorrência corresponde aos filtros aplicados.")

    with tab_grafico:
        st.markdown("### 📊 Ocorrências por Fonte e Status")
        if not filtered_df.empty:
            df_chart = filtered_df.groupby(["Fonte", "Status"]).size().reset_index(name="Quantidade")
            st.bar_chart(df_chart, x="Fonte", y="Quantidade", color="Status", stack=True, width='stretch')
        else:
            st.info("Nenhum dado com os filtros aplicados para exibir no gráfico.")
