# -*- coding: utf-8 -*-
"""
Aba de Configurações do Sistema:
- Cadastro e edição de Nomes Monitorados e Telefones via modal (@st.dialog)
- Cadastro e edição de Fontes Oficiais & Diários via modal (@st.dialog)
- Exibição de tickets/badges de status do scraper (✓ Ativo vs ❌ Sem Scraper)
- Seleção de linhas nas tabelas (on_select="rerun") para abrir formulário de edição
- Sincronização / Reimportação a partir do .env
"""
import re
from datetime import datetime
import streamlit as st
import pandas as pd
from src.database import (
    get_all_monitored_names,
    add_monitored_name,
    update_monitored_name,
    delete_monitored_name,
    get_all_monitored_sources,
    add_monitored_source,
    update_monitored_source,
    delete_monitored_source,
    seed_config_from_env_if_empty,
    get_schedule_config,
    save_schedule_config
)
from src.scrapers import is_scraper_implemented
from src.scheduler import calculate_next_run, trigger_manual_test_scan, DAY_LABELS
from src.config import check_scan_running
from src.components.subtabs import render_subtabs
from src.components.metric_cards import render_metric_cards

def format_phone(val: str) -> str:
    """Formata string numérica de telefone para padrão brasileiro (ex: (67) 99247-1379 ou (67) 3345-1234)."""
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val))
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return str(val)

def format_br_datetime(val) -> str:
    """Formata datas ISO ou strings para padrão brasileiro DD/MM/YYYY HH:MM:SS."""
    if not val or pd.isna(val) or str(val).strip().lower() in ["none", "nan", ""]:
        return "-"
    try:
        dt = pd.to_datetime(val)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(val)

CONFIG_SUBTABS = {
    "nomes": "👥 Nomes Monitorados",
    "fontes": "🌐 Fontes & Diários Oficiais",
    "agendamento": "⏰ Agendamento Automático",
    "backup": "💾 Sincronização & Backup"
}


# ==============================================================================
# MODAIS DINÂMICOS DE GESTÃO (@st.dialog)
# ==============================================================================

@st.dialog("👥 Gestão de Nome Monitorado", width="large")
def modal_gerenciar_nome(item: dict = None):
    """Modal unificado para cadastrar ou editar um nome monitorado com suporte a alertas WhatsApp via CallMeBot."""
    from src.notifications import test_callmebot_connection

    is_edit = item is not None and "ID" in item
    
    if is_edit:
        st.markdown(f"### ✏️ Editar: **{item.get('Nome', '')}**")
        st.caption("Modifique os dados, configure notificações via WhatsApp ou exclua o cadastro.")
    else:
        st.markdown("### ➕ Cadastrar Novo Nome")
        st.caption("Preencha o nome completo para pesquisa e os dados de notificação.")

    init_name = item.get("Nome", "") if is_edit else ""
    init_phone = format_phone(item.get("Telefone_raw", "")) if is_edit else ""
    init_apikey = item.get("Callmebot_raw", "") if is_edit else ""
    init_active = bool(item.get("Ativo_raw", 1) == 1) if is_edit else True

    with st.form("form_modal_nome"):
        c1, c2 = st.columns([1.8, 1.2])
        with c1:
            nome_val = st.text_input("Nome Completo *", value=init_name, placeholder="Ex: Paulo Henrique Gonçalves Rezende")
        with c2:
            phone_val = st.text_input("Telefone / WhatsApp (com DDD)", value=init_phone, placeholder="Ex: (67) 99247-1379")
        
        c3, c4 = st.columns([1.8, 1.2])
        with c3:
            apikey_val = st.text_input(
                "Chave de API CallMeBot (WhatsApp)",
                value=init_apikey,
                placeholder="Ex: 1234567",
                type="password",
                help="Chave pessoal obtida gratuitamente enviando uma mensagem para o bot do CallMeBot no WhatsApp."
            )
        with c4:
            status_val = st.checkbox("🟢 Monitoramento Ativo", value=init_active)

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn_salvar, col_btn_del = st.columns([2, 1] if is_edit else [1, 0.01])
        
        with col_btn_salvar:
            submit_label = "💾 Atualizar Dados" if is_edit else "➕ Cadastrar Nome"
            btn_submit = st.form_submit_button(submit_label, width="stretch")

        btn_delete = False
        if is_edit:
            with col_btn_del:
                btn_delete = st.form_submit_button("🗑️ Excluir", width="stretch")

    # Área de Ajuda e Teste do CallMeBot
    with st.expander("📲 Como obter a API Key gratuita do CallMeBot em 30 segundos?"):
        st.markdown("""
        O **CallMeBot** é um serviço gratuito para alertas diretos no WhatsApp:
        1. Adicione o número **+34 694 23 41 84** aos seus contatos do celular (ou abra direto no WhatsApp).
        2. Envie exatamente a seguinte mensagem para ele:  
           `I allow callmebot to send me messages`
        3. O robô responderá imediatamente com sua **API Key** (um número de 6 ou 7 dígitos).
        4. Cole esse código no campo acima e clique em **Atualizar/Cadastrar**.
        """)

    # Botão de Teste em tempo real fora do form
    if phone_val and (apikey_val or is_edit):
        col_test_txt, col_test_btn = st.columns([2.5, 1])
        with col_test_txt:
            st.caption("Quer verificar se seu número já está recebendo alertas?")
        with col_test_btn:
            if st.button("📲 Testar Envio", width="stretch", key="btn_test_callmebot_modal"):
                with st.spinner("Enviando mensagem de teste via CallMeBot..."):
                    key_to_test = apikey_val.strip() if apikey_val else init_apikey
                    ok, msg_ret = test_callmebot_connection(phone_val, key_to_test)
                    if ok:
                        st.success(f"✅ {msg_ret}")
                    else:
                        st.error(f"❌ {msg_ret}")

    if btn_submit:
        if not nome_val.strip():
            st.error("O campo de Nome Completo é obrigatório.")
        else:
            clean_phone_to_save = format_phone(phone_val.strip())
            clean_apikey_to_save = apikey_val.strip()
            if is_edit:
                update_monitored_name(item["ID"], nome_val, clean_phone_to_save, clean_apikey_to_save, 1 if status_val else 0)
                st.toast(f"✅ Nome '{nome_val}' atualizado com sucesso!", icon="👥")
            else:
                success = add_monitored_name(nome_val, clean_phone_to_save, clean_apikey_to_save)
                if not success:
                    st.warning(f"O nome '{nome_val}' já existe no sistema.")
                    return
                st.toast(f"✅ Nome '{nome_val}' cadastrado com sucesso!", icon="👥")
            if "table_names_config" in st.session_state:
                st.session_state["table_names_config"] = {"selection": {"rows": [], "columns": []}}
            st.rerun()

    if btn_delete and is_edit:
        delete_monitored_name(item["ID"])
        st.toast(f"🗑️ Nome '{item['Nome']}' excluído com sucesso!", icon="🗑️")
        if "table_names_config" in st.session_state:
            st.session_state["table_names_config"] = {"selection": {"rows": [], "columns": []}}
        st.rerun()


@st.dialog("🌐 Gestão de Fonte / Diário Oficial", width="large")
def modal_gerenciar_fonte(item: dict = None):
    """Modal unificado para cadastrar ou editar uma fonte de dados."""
    is_edit = item is not None and "ID" in item

    if is_edit:
        has_bot = item.get("has_bot", False)
        badge = "✓ Scraper Ativo" if has_bot else "❌ Sem Scraper"
        st.markdown(f"### ✏️ Editar Fonte: **{item.get('Nome da Fonte', '')}**")
        st.caption(f"Status do Robô no Sistema: **{badge}**")
    else:
        st.markdown("### ➕ Cadastrar Nova Fonte")
        st.caption("Cadastre os dados da nova fonte oficial. O robô web pode ser acoplado posteriormente pelo identificador (slug).")

    init_slug = item.get("Slug", "") if is_edit else ""
    init_name = item.get("Nome da Fonte", "") if is_edit else ""
    init_url = item.get("URL", "") if is_edit else ""
    init_desc = item.get("Descricao_raw", "") if is_edit else ""
    init_active = bool(item.get("Ativo_raw", 1) == 1) if is_edit else True

    with st.form("form_modal_fonte"):
        c1, c2 = st.columns([1, 2])
        with c1:
            slug_val = st.text_input(
                "Identificador Único (slug) *",
                value=init_slug,
                placeholder="Ex: ams, seduc",
                disabled=is_edit,
                help="O identificador (slug) vincula o cadastro à função de coleta em Python."
            )
        with c2:
            nome_val = st.text_input("Nome de Exibição da Fonte *", value=init_name, placeholder="Ex: Diário Oficial de Dourados")
        
        url_val = st.text_input("URL Principal de Consulta *", value=init_url, placeholder="https://exemplo.gov.br")
        desc_val = st.text_area("Descrição / Notas", value=init_desc, placeholder="Publicações de editais e convocações")
        status_val = st.checkbox("🟢 Fonte Ativa para Varredura", value=init_active)

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn_salvar, col_btn_del = st.columns([2, 1] if is_edit else [1, 0.01])

        with col_btn_salvar:
            submit_label = "💾 Atualizar Fonte" if is_edit else "➕ Cadastrar Fonte"
            btn_submit = st.form_submit_button(submit_label, width="stretch")

        btn_delete = False
        if is_edit:
            with col_btn_del:
                btn_delete = st.form_submit_button("🗑️ Excluir", width="stretch")

    if btn_submit:
        if not slug_val.strip() or not nome_val.strip() or not url_val.strip():
            st.error("Preencha todos os campos obrigatórios (Slug, Nome e URL).")
        else:
            if is_edit:
                update_monitored_source(item["ID"], slug_val, nome_val, url_val, desc_val, 1 if status_val else 0)
                st.toast(f"✅ Fonte '{nome_val}' atualizada com sucesso!", icon="🌐")
            else:
                success = add_monitored_source(slug_val, nome_val, url_val, desc_val)
                if not success:
                    st.warning(f"O identificador (slug) '{slug_val}' já existe no sistema.")
                    return
                st.toast(f"✅ Fonte '{nome_val}' cadastrada com sucesso!", icon="🌐")
            if "table_sources_config" in st.session_state:
                st.session_state["table_sources_config"] = {"selection": {"rows": [], "columns": []}}
            st.rerun()

    if btn_delete and is_edit:
        delete_monitored_source(item["ID"])
        st.toast(f"🗑️ Fonte '{item['Nome da Fonte']}' excluída com sucesso!", icon="🗑️")
        if "table_sources_config" in st.session_state:
            st.session_state["table_sources_config"] = {"selection": {"rows": [], "columns": []}}
        st.rerun()


# ==============================================================================
# RENDERIZAÇÃO DA PÁGINA
# ==============================================================================

def render_configuracoes_tab():
    """Renderiza a página visual completa de configurações."""
    st.markdown("""
        <div style="background: var(--metric-bg, #1e293b); padding: 18px 24px; border-radius: 12px; border-left: 6px solid #3b82f6; border-top: 1px solid var(--metric-border, #2d3139); border-right: 1px solid var(--metric-border, #2d3139); border-bottom: 1px solid var(--metric-border, #2d3139); margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2 style="color: var(--metric-value-color, #ffffff); margin: 0; font-size: 24px; font-weight: 700;">⚙️ Configurações & Fontes de Monitoramento</h2>
                <span style="background-color: rgba(59, 130, 246, 0.15); color: #38bdf8; font-size: 13px; font-weight: 600; padding: 4px 12px; border-radius: 20px; border: 1px solid #0284c7;">
                    💾 Armazenamento Relacional SQLite
                </span>
            </div>
            <p style="color: var(--metric-title-color, #94a3b8); margin: 6px 0 0 0; font-size: 14px;">
                Cadastre e gerencie pessoas, contatos telefônicos e diários oficiais. Visualize quais portais já possuem motores de extração automática ativos e quais aguardam desenvolvimento.
            </p>
        </div>
    """, unsafe_allow_html=True)

    selected_subtab = render_subtabs(CONFIG_SUBTABS, default_slug="nomes", key="config_tabs_radio")
    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # SUBTAB 1: NOMES MONITORADOS
    # -------------------------------------------------------------------------
    if selected_subtab == "nomes":
        col_title, col_add = st.columns([3, 1])
        with col_title:
            st.markdown("### 👥 Gestão de Pessoas & Nomes Monitorados")
            st.caption("Clique em qualquer linha da tabela para editar dados, telefone, alternar status ou excluir.")
        with col_add:
            st.write("")
            if st.button("➕ Novo Nome", width="stretch", key="btn_open_modal_novo_nome"):
                # Limpa a seleção anterior da tabela para evitar conflito de IDs
                if "table_names_config" in st.session_state:
                    st.session_state["table_names_config"] = {"selection": {"rows": [], "columns": []}}
                st.session_state["modal_nome_to_open"] = "new"

        names_data = get_all_monitored_names()
        if names_data:
            rows = []
            for item in names_data:
                name_id, name, phone, callmebot_key, active, created_at = item
                formatted_phone = format_phone(phone) if phone else "Não informado"
                formatted_created_at = format_br_datetime(created_at)
                has_whatsapp = bool(phone and callmebot_key)
                rows.append({
                    "ID": name_id,
                    "Nome": name,
                    "Telefone": formatted_phone,
                    "Telefone_raw": phone or "",
                    "Callmebot_raw": callmebot_key or "",
                    "Alertas WhatsApp": "📲 Ativo" if has_whatsapp else ("⚠️ Sem Chave" if phone else "❌ Inativo"),
                    "Status": "🟢 Ativo" if active == 1 else "⚪ Inativo",
                    "Ativo_raw": active,
                    "Cadastrado em": formatted_created_at
                })
            df_names = pd.DataFrame(rows)
            
            st.markdown(f"**Total de Nomes Cadastrados:** `{len(df_names)}`")
            
            selection_event = st.dataframe(
                df_names[["Nome", "Telefone", "Alertas WhatsApp", "Status", "Cadastrado em"]],
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="table_names_config"
            )

            selected_rows = selection_event.selection.rows if hasattr(selection_event, "selection") else []
            if selected_rows:
                row_idx = selected_rows[0]
                st.session_state["modal_nome_to_open"] = df_names.iloc[row_idx].to_dict()

            # Renderiza o modal garantindo no máximo 1 chamada por execução
            if st.session_state.get("modal_nome_to_open"):
                target = st.session_state.pop("modal_nome_to_open")
                modal_gerenciar_nome(None if target == "new" else target)
        else:
            if st.session_state.get("modal_nome_to_open"):
                target = st.session_state.pop("modal_nome_to_open")
                modal_gerenciar_nome(None if target == "new" else target)
            st.info("Nenhum nome cadastrado ainda. Clique no botão '➕ Novo Nome' acima para adicionar!")

    # -------------------------------------------------------------------------
    # SUBTAB 2: FONTES & DIÁRIOS OFICIAIS
    # -------------------------------------------------------------------------
    elif selected_subtab == "fontes":
        col_title, col_add = st.columns([3, 1])
        with col_title:
            st.markdown("### 🌐 Portais, Diários Oficiais & Concursos")
            st.caption("Clique em qualquer linha para editar ou alterar status. Acompanhe a integração dos robôs de coleta.")
        with col_add:
            st.write("")
            if st.button("➕ Nova Fonte", width="stretch", key="btn_open_modal_nova_fonte"):
                if "table_sources_config" in st.session_state:
                    st.session_state["table_sources_config"] = {"selection": {"rows": [], "columns": []}}
                st.session_state["modal_fonte_to_open"] = "new"

        sources_data = get_all_monitored_sources()
        if sources_data:
            rows = []
            for item in sources_data:
                src_id, slug, name, url, desc, active, created_at = item
                has_bot = is_scraper_implemented(slug)
                bot_badge = "✓ Scraper Ativo" if has_bot else "❌ Sem Scraper"
                status_badge = "🟢 Ativa" if active == 1 else "⚪ Inativa"
                formatted_created_at = format_br_datetime(created_at)
                rows.append({
                    "ID": src_id,
                    "Slug": slug,
                    "Nome da Fonte": name,
                    "Integração / Scraper": bot_badge,
                    "URL": url,
                    "Status": status_badge,
                    "Descrição": desc or "-",
                    "Descricao_raw": desc or "",
                    "Ativo_raw": active,
                    "has_bot": has_bot,
                    "Cadastrado em": formatted_created_at
                })
            
            df_sources = pd.DataFrame(rows)

            st.markdown(f"**Total de Fontes Cadastradas:** `{len(df_sources)}`")

            selection_event_src = st.dataframe(
                df_sources[["Slug", "Nome da Fonte", "Integração / Scraper", "Status", "URL", "Descrição"]],
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="table_sources_config",
                column_config={
                    "URL": st.column_config.LinkColumn("URL", display_text="Acessar Portal"),
                    "Integração / Scraper": st.column_config.TextColumn(
                        "Integração / Scraper",
                        help="✓ Scraper Ativo: Robô já programado. ❌ Sem Scraper: Cadastrado para futura implementação."
                    )
                }
            )

            st.info("""
                💡 **Legenda de Integração:**
                - **✓ Scraper Ativo**: O motor do sistema já possui o robô de raspagem implementado e realiza buscas automáticas.
                - **❌ Sem Scraper**: A fonte está cadastrada no sistema, mas ainda não possui algoritmo de coleta programado. Ao programar a rotina correspondente ao `slug`, o ticket muda automaticamente para ativo!
            """)

            selected_src_rows = selection_event_src.selection.rows if hasattr(selection_event_src, "selection") else []
            if selected_src_rows:
                row_idx = selected_src_rows[0]
                st.session_state["modal_fonte_to_open"] = df_sources.iloc[row_idx].to_dict()

            if st.session_state.get("modal_fonte_to_open"):
                target_src = st.session_state.pop("modal_fonte_to_open")
                modal_gerenciar_fonte(None if target_src == "new" else target_src)
        else:
            if st.session_state.get("modal_fonte_to_open"):
                target_src = st.session_state.pop("modal_fonte_to_open")
                modal_gerenciar_fonte(None if target_src == "new" else target_src)
            st.info("Nenhuma fonte cadastrada ainda. Clique no botão '➕ Nova Fonte' acima para adicionar!")

    # -------------------------------------------------------------------------
    # SUBTAB 3: AGENDAMENTO AUTOMÁTICO (CRON / SCHEDULER)
    # -------------------------------------------------------------------------
    elif selected_subtab == "agendamento":
        st.markdown("### ⏰ Agendamento Automático de Varreduras")
        st.caption("Programe os dias da semana e os horários em que o sistema deve coletar os diários e editais em segundo plano de forma autônoma.")

        sched_config = get_schedule_config()
        is_enabled = sched_config.get("enabled", True)
        saved_days = sched_config.get("days_of_week", ["mon", "tue", "wed", "thu", "fri"])
        saved_times = sched_config.get("times", ["08:00"])
        last_run = sched_config.get("last_run")
        next_run = sched_config.get("next_run")

        # Se não houver next_run calculado no banco, calcula em tempo de execução
        if not next_run and is_enabled:
            dt_next = calculate_next_run(saved_days, saved_times)
            next_run = dt_next.strftime("%Y-%m-%d %H:%M:%S") if dt_next else None

        # Métricas visuais do status do agendamento
        status_label = "🟢 Ativo (Rodando em Background)" if is_enabled else "⏸️ Pausado"
        status_color = "#10b981" if is_enabled else "#94a3b8"
        freq_str = f"{len(saved_times)}x ao dia ({', '.join(saved_times)})" if saved_times else "Nenhum horário definido"
        next_run_str = format_br_datetime(next_run) if is_enabled and next_run else ("Pausado" if not is_enabled else "Sem agendamento futuro")
        last_run_str = format_br_datetime(last_run) if last_run else "Nenhuma execução registrada"

        render_metric_cards([
            {"title": "Status do Agendador", "value": status_label, "border_color": status_color},
            {"title": "Frequência Configurada", "value": freq_str, "border_color": "#3b82f6"},
            {"title": "Próxima Varredura Prevista", "value": next_run_str, "border_color": "#f59e0b"},
            {"title": "Última Execução Automática", "value": last_run_str, "border_color": "#8b5cf6"}
        ], cols=4)

        st.markdown("<br>", unsafe_allow_html=True)

        col_form, col_actions = st.columns([2, 1])

        with col_form:
            st.markdown("#### ⚙️ Configurar Parâmetros de Disparo")
            with st.form("form_schedule_settings"):
                enabled_val = st.toggle(
                    "Ativar Agendamento Automático de Varreduras",
                    value=is_enabled,
                    help="Quando ativo, o robô disparará a varredura nos dias e horários selecionados."
                )

                st.markdown("##### 📅 Dias da Semana Permitidos")
                day_options = [
                    ("mon", "Segunda-feira"),
                    ("tue", "Terça-feira"),
                    ("wed", "Quarta-feira"),
                    ("thu", "Quinta-feira"),
                    ("fri", "Sexta-feira"),
                    ("sat", "Sábado"),
                    ("sun", "Domingo")
                ]

                # Mapeamento para multiselect amigável
                day_label_to_code = {label: code for code, label in day_options}
                default_labels = [label for code, label in day_options if code in saved_days]

                selected_day_labels = st.multiselect(
                    "Selecione os dias em que a varredura deve ocorrer:",
                    options=[label for _, label in day_options],
                    default=default_labels,
                    help="Por padrão, segunda a sexta-feira. Você pode adicionar sábados e domingos se desejar."
                )

                st.markdown("##### 🕒 Horários de Execução no Dia")
                st.caption("Digite os horários no formato 24 horas `HH:MM`, separados por vírgula (ex: `08:00` ou `08:00, 14:00, 19:30`).")
                times_input = st.text_input(
                    "Horários de Varredura (24h):",
                    value=", ".join(saved_times),
                    placeholder="08:00 ou 08:00, 14:00"
                )

                st.markdown("<br>", unsafe_allow_html=True)
                btn_save_schedule = st.form_submit_button("💾 Salvar Agendamento", width="stretch")

            if btn_save_schedule:
                # Validação dos dias
                chosen_days = [day_label_to_code[label] for label in selected_day_labels if label in day_label_to_code]
                if not chosen_days and enabled_val:
                    st.error("Selecione ao menos um dia da semana para o agendamento ativo.")
                else:
                    # Validação dos horários
                    parsed_times = []
                    time_error = False
                    for part in times_input.split(","):
                        cleaned = part.strip()
                        if not cleaned:
                            continue
                        if re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", cleaned):
                            # Normaliza para HH:MM com 2 dígitos na hora
                            h, m = cleaned.split(":")
                            parsed_times.append(f"{int(h):02d}:{int(m):02d}")
                        else:
                            st.error(f"Formato de horário inválido: '{cleaned}'. Use o formato HH:MM (ex: 08:00, 14:30).")
                            time_error = True
                            break

                    if not time_error:
                        if not parsed_times and enabled_val:
                            st.error("Informe ao menos um horário de execução válido (ex: 08:00).")
                        else:
                            success = save_schedule_config(enabled_val, chosen_days, sorted(list(set(parsed_times))))
                            if success:
                                st.toast("✅ Configurações de agendamento salvas com sucesso!", icon="⏰")
                                st.rerun()

        with col_actions:
            st.markdown("#### ⚡ Ações Rápidas & Teste")
            st.info("""
                💡 **Como Funciona:**
                - O motor de agendamento monitora os horários no relógio interno do container.
                - Não trava a interface web.
                - Se o sistema já estiver executando uma varredura naquele instante, ele evita disparos concorrentes duplicados.
            """)

            st.markdown("<br>", unsafe_allow_html=True)
            scan_running = check_scan_running()
            if scan_running:
                st.button("🤖 Varredura em Andamento...", disabled=True, width="stretch")
            else:
                if st.button("🚀 Disparar Teste Imediato Agora", width="stretch", help="Executa a rotina de varredura imediatamente como se fosse o agendador."):
                    started = trigger_manual_test_scan()
                    if started:
                        st.toast("🚀 Varredura de teste disparada pelo agendador!", icon="⏰")
                        st.rerun()
                    else:
                        st.warning("Não foi possível iniciar o teste (varredura já em execução).")

    # -------------------------------------------------------------------------
    # SUBTAB 4: SINCRONIZAÇÃO & BACKUP
    # -------------------------------------------------------------------------
    elif selected_subtab == "backup":
        st.markdown("### 💾 Sincronização & Migração de Dados")
        st.caption("Ferramentas de sincronização com o arquivo `.env` e persistência do banco relacional.")

        c_bk1, c_bk2 = st.columns(2)
        with c_bk1:
            st.markdown("#### 🔄 Reimportar Definições do `.env`")
            st.write("Recarrega os nomes de `MONITOR_NAMES` e as URLs padrões existentes no arquivo `.env` para o banco SQLite.")
            if st.button("Reimportar do `.env` Agora", width="stretch"):
                seed_config_from_env_if_empty(force=True)
                st.success("Configurações sincronizadas do .env para o banco com sucesso!")
                st.rerun()

        with c_bk2:
            st.markdown("#### 📊 Status da Persistência")
            st.caption("Banco de dados SQLite ativo: `data/results.db`.")
            all_n = get_all_monitored_names()
            all_s = get_all_monitored_sources()
            
            render_metric_cards([
                {"title": "Total de Nomes Cadastrados", "value": len(all_n), "border_color": "#3b82f6"},
                {"title": "Total de Fontes Cadastradas", "value": len(all_s), "border_color": "#10b981"}
            ], cols=2)
