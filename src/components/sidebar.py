# -*- coding: utf-8 -*-
"""
Componente lateral (Sidebar) dinâmico:
- Tab 'dashboard': exibe seleção de nomes monitorados, fontes de dados e paginação.
- Tab 'editais': exibe filtros de candidatos, status, seletor do concurso, botão de novo edital e filtro de disciplina.
- Tab 'configuracoes': mensagem simples de direcionamento para as configurações centrais.
"""
from typing import Tuple, List, Dict, Any, Optional
import streamlit as st
from src.database import get_all_monitored_names, get_all_monitored_sources, get_all_editais
from src.scrapers import is_scraper_implemented
from src.components.pagination import render_items_per_page_selector


def render_dashboard_sidebar() -> Tuple[List[str], Dict[str, bool], Any]:
    """Renderiza os filtros exclusivos do monitor de diários oficiais."""
    st.sidebar.markdown("### 🔍 Filtros do Monitor")
    
    # 1. Nomes Ativos
    st.sidebar.markdown("#### 👥 Nomes Ativos")
    all_names = get_all_monitored_names()
    active_names = []
    
    if all_names:
        for item in all_names:
            name_id, name, phone, callmebot_key, active, _ = item
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
            
            is_checked = st.sidebar.checkbox(
                display_label,
                value=(active == 1),
                key=f"sb_source_{src_id}",
                help=f"Slug: {slug} | Status do Scraper: {'Implementado' if has_bot else 'Aguardando desenvolvimento'}"
            )
            selected_sources[slug] = is_checked
    else:
        st.sidebar.caption("Nenhuma fonte cadastrada.")

    st.sidebar.markdown("---")

    # 3. Paginação de Ocorrências
    items_per_page = render_items_per_page_selector(
        key_prefix="occurrences",
        options=[10, 20, 50, 100, "Todos"],
        default_index=1,
        label="📄 Ocorrências por página:"
    )

    return active_names, selected_sources, items_per_page


def render_editais_sidebar(disciplinas_disponiveis: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Renderiza os filtros e seletores exclusivos da Central de Editais:
    - Filtro por Candidato(a)
    - Filtro por Status do Concurso
    - Seletor do Concurso Ativo
    - Botão para Abrir Formulário de Novo Edital
    - Filtro por Disciplina (para o Edital Verticalizado)
    """
    st.sidebar.markdown("### 📚 Gestão de Editais")

    # Botão de Novo Edital no topo da sidebar
    if "show_new_edital_form" not in st.session_state:
        st.session_state.show_new_edital_form = False

    if st.sidebar.button("➕ Novo Edital (Upload)", use_container_width=True, type="primary"):
        st.session_state.show_new_edital_form = not st.session_state.show_new_edital_form

    st.sidebar.markdown("---")

    # Filtros de Listagem
    filtro_interessado = st.sidebar.selectbox(
        "Filtrar por Candidato(a):",
        ["Todos", "Paulo", "Kamila", "Ambos"],
        index=0,
        key="sb_filtro_interessado"
    )

    filtro_status = st.sidebar.selectbox(
        "Status do Concurso:",
        ["Todos", "Em Andamento", "Finalizado", "Cancelado"],
        index=0,
        key="sb_filtro_status"
    )

    editais = get_all_editais(interessado=filtro_interessado, status=filtro_status)
    selected_edital_id = None

    if editais:
        opcoes_editais = {e["id"]: f"{e['titulo']} - {e['cargo'] or 'Geral'} ({e['interessado']})" for e in editais}
        selected_edital_id = st.sidebar.selectbox(
            "Concurso Ativo:",
            options=list(opcoes_editais.keys()),
            format_func=lambda x: opcoes_editais[x],
            key="sb_selected_edital_id"
        )
        if selected_edital_id:
            edit_key = f"show_edit_edital_{selected_edital_id}"
            is_editing = st.session_state.get(edit_key, False)
            btn_txt = "✖️ Fechar Edição" if is_editing else "✏️ Editar Concurso"
            if st.sidebar.button(btn_txt, key=f"sb_btn_edit_edital_{selected_edital_id}", use_container_width=True):
                st.session_state[edit_key] = not is_editing
                st.rerun()
    else:
        st.sidebar.info("Nenhum edital encontrado.")

    # Controles contextuais da subtab de verticalizado ('vert')
    filtro_disciplina = "Todas"
    current_subtab = st.session_state.get("editais_internal_subtabs") or st.query_params.get("subtab", "crono")
    if current_subtab == "vert":
        if disciplinas_disponiveis or selected_edital_id:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 🎯 Edital Verticalizado")
            if disciplinas_disponiveis:
                filtro_disciplina = st.sidebar.selectbox(
                    "Filtrar por Disciplina:",
                    ["Todas"] + disciplinas_disponiveis,
                    key="sb_filtro_disciplina"
                )

            # Botão de exportação CSV do Verticalizado
            if selected_edital_id:
                from src.database import get_verticalizado_by_edital, get_edital_by_id
                import pandas as pd

                topicos_vert = get_verticalizado_by_edital(selected_edital_id)
                edital_info = get_edital_by_id(selected_edital_id)
                if topicos_vert and edital_info:
                    df_v = pd.DataFrame(topicos_vert)
                    if filtro_disciplina and filtro_disciplina != "Todas":
                        df_v = df_v[df_v["disciplina"] == filtro_disciplina]
                    csv_data = df_v.to_csv(index=False).encode('utf-8')
                    st.sidebar.download_button(
                        label="📥 Exportar Verticalizado (CSV)",
                        data=csv_data,
                        file_name=f"edital_verticalizado_{edital_info['titulo']}_{filtro_disciplina}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="sb_download_verticalizado_csv"
                    )

    # Controles contextuais da subtab de cronograma ('crono')
    elif current_subtab == "crono" and selected_edital_id:
        from src.database import get_cronograma_by_edital, get_edital_by_id, clear_cronograma_by_edital, save_cronograma_items
        from src.editais.calendar_utils import generate_ics_calendar
        from src.editais.extractor_local import extract_cronograma_local

        cronograma = get_cronograma_by_edital(selected_edital_id)
        edital_info = get_edital_by_id(selected_edital_id)
        if edital_info:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📅 Cronograma & Prazos")

            # Botão Reextrair Localmente
            if st.sidebar.button("🔄 Reextrair Localmente", key="sb_reextrair_crono_local", use_container_width=True):
                clear_cronograma_by_edital(selected_edital_id)
                novos = extract_cronograma_local(edital_info["arquivo_path"])
                save_cronograma_items(selected_edital_id, novos)
                st.sidebar.success(f"Reextraído: {len(novos)} itens.")
                st.rerun()

            # Botão Exportar .ics
            if cronograma:
                ics_content = generate_ics_calendar(
                    edital_titulo=edital_info["titulo"],
                    cronograma_items=cronograma,
                    link_oficial=edital_info.get("link_oficial", ""),
                    convidado="kamila_arteman@hotmail.com"
                )
                nome_arquivo_ics = f"cronograma_{edital_info['titulo'].lower().replace(' ', '_')}.ics"
                st.sidebar.download_button(
                    label="📅 Exportar (.ics Google)",
                    data=ics_content,
                    file_name=nome_arquivo_ics,
                    mime="text/calendar",
                    use_container_width=True,
                    help="Baixa o arquivo de calendário formatado no padrão da sua agenda 'Concursos'. Basta importar no Google Agenda!",
                    key="sb_download_ics"
                )

            # Botão Testar Alertas no WhatsApp
            if st.sidebar.button(
                "📲 Testar Alertas no WhatsApp",
                key="sb_btn_test_crono_whatsapp",
                use_container_width=True,
                help="Verifica os prazos de hoje/amanhã e dispara notificação via CallMeBot para os candidatos deste edital."
            ):
                from src.editais.notifications import check_and_notify_cronograma_deadlines
                with st.spinner("Analisando datas e enviando lembretes no WhatsApp..."):
                    res = check_and_notify_cronograma_deadlines(force_all=True, edital_id_filter=selected_edital_id)
                    if res["alerts_sent"] > 0:
                        st.toast(f"✅ {res['alerts_sent']} alerta(s) de cronograma disparado(s) via CallMeBot!", icon="📲")
                    elif res.get("status") == "no_recipients":
                        st.sidebar.warning("Nenhum destinatário de WhatsApp com telefone e API Key cadastrado no menu Configurações.")
                    else:
                        st.sidebar.info("Nenhuma data pendente de notificação hoje.")

    # Controles contextuais da subtab de leitura de PDF ('leitor')
    elif current_subtab == "leitor" and selected_edital_id:
        from src.database import get_edital_by_id, get_documentos_by_edital

        edital_info = get_edital_by_id(selected_edital_id)
        if edital_info:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📖 Documentos para Leitura")

            # Monta lista de PDFs disponíveis para este concurso
            docs_disponiveis = [
                {
                    "label": f"📄 Edital Original ({edital_info['arquivo_nome']})",
                    "path": edital_info["arquivo_path"]
                }
            ]

            outros_docs = get_documentos_by_edital(selected_edital_id)
            for d in outros_docs:
                tipo_tag = d.get("tipo", "Documento")
                docs_disponiveis.append({
                    "label": f"📎 [{tipo_tag}] {d['titulo']}",
                    "path": d["arquivo_path"]
                })

            opcoes_map = {idx: d["label"] for idx, d in enumerate(docs_disponiveis)}
            sel_idx = st.sidebar.selectbox(
                "Selecionar PDF para Visualização:",
                options=list(opcoes_map.keys()),
                format_func=lambda x: opcoes_map[x],
                key="sb_selected_pdf_index"
            )
            # Salva o arquivo selecionado no session_state para consumo na tab
            selected_pdf_path = docs_disponiveis[sel_idx]["path"]
            st.session_state["leitor_selected_pdf_path"] = selected_pdf_path
            st.session_state["leitor_selected_pdf_title"] = docs_disponiveis[sel_idx]["label"]

            # Botão Baixar PDF selecionado
            from src.editais.pdf_parser import resolve_pdf_path
            resolved_pdf = resolve_pdf_path(selected_pdf_path)
            if resolved_pdf and resolved_pdf.exists():
                with open(resolved_pdf, "rb") as f_down:
                    st.sidebar.download_button(
                        label="💾 Baixar PDF",
                        data=f_down.read(),
                        file_name=resolved_pdf.name,
                        mime="application/pdf",
                        use_container_width=True,
                        key="sb_download_pdf_leitor"
                    )

    return {
        "interessado": filtro_interessado,
        "status": filtro_status,
        "edital_id": selected_edital_id,
        "disciplina": filtro_disciplina
    }


def render_configuracoes_sidebar():
    """
    Renderiza os controles da barra lateral para a página de configurações,
    contextualizados para a subtab ativa (nomes, fontes, agendamento, sync).
    """
    from src.components.pagination import render_items_per_page_selector

    current_subtab = st.session_state.get("config_tabs_radio") or st.query_params.get("subtab", "nomes")
    
    st.sidebar.markdown("### ⚙️ Configurações Gerais")

    if current_subtab == "nomes":
        st.sidebar.markdown("#### 👥 Pessoas & Nomes")
        st.sidebar.caption("Cadastre ou gerencie pessoas e telefones para notificações.")
        if st.sidebar.button("➕ Novo Nome", use_container_width=True, type="primary", key="sb_btn_novo_nome"):
            if "table_names_config" in st.session_state:
                st.session_state["table_names_config"] = {"selection": {"rows": [], "columns": []}}
            st.session_state["modal_nome_to_open"] = "new"
            st.rerun()

    elif current_subtab == "fontes":
        st.sidebar.markdown("#### 🌐 Fontes & Diários")
        st.sidebar.caption("Cadastre e habilite novos portais ou diários oficiais.")
        if st.sidebar.button("➕ Nova Fonte", use_container_width=True, type="primary", key="sb_btn_nova_fonte"):
            if "table_sources_config" in st.session_state:
                st.session_state["table_sources_config"] = {"selection": {"rows": [], "columns": []}}
            st.session_state["modal_fonte_to_open"] = "new"
            st.rerun()

    elif current_subtab == "agendamento":
        st.sidebar.markdown("#### ⏰ Histórico do Agendador")
        render_items_per_page_selector(
            key_prefix="cron_hist",
            options=[10, 20, 50, 100, "Todos"],
            default_index=0,
            label="📄 Registros por página:",
            container=st.sidebar
        )

    else:
        st.sidebar.info("Utilize as abas centrais da página para gerenciar pessoas, fontes de dados, agendamento de varredura e logs do sistema.")

# Alias de compatibilidade retroativa
render_sidebar = render_dashboard_sidebar
