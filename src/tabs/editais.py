# -*- coding: utf-8 -*-
"""
Aba Streamlit para gerenciamento de Editais e Concursos:
- Upload e cadastro de Editais
- Cronograma de Datas Importantes e Prazos
- Edital Verticalizado interativo (Checklist Teoria / Resumo / Questões / Revisão)
- Visualizador do PDF do Edital embutido
"""
import base64
from typing import Optional
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd

from src.config import EDITAIS_DIR, ROOT_DIR, get_edital_folder
from src.editais.pdf_parser import resolve_pdf_path
from src.database import (
    save_edital,
    get_all_editais,
    get_edital_by_id,
    update_edital,
    delete_edital,
    save_cronograma_items,
    get_cronograma_by_edital,
    update_cronograma_item_status,
    clear_cronograma_by_edital,
    save_verticalizado_items,
    get_verticalizado_by_edital,
    update_verticalizado_item,
    clear_verticalizado_by_edital,
    save_edital_documento,
    get_documentos_by_edital,
    mark_documento_as_processed
)
from src.editais import (
    inspect_pdf,
    extract_cronograma_local,
    extract_verticalizado_local,
    discover_cargos_in_pdf,
    is_gemini_available,
    extract_cronograma_with_ai,
    extract_verticalizado_with_ai,
    extract_full_text_by_pages
)
from src.editais.updater import (
    check_for_updates,
    download_document,
    process_retificacao_pdf
)
from src.components.sidebar import render_editais_sidebar


def render_pdf_viewer(pdf_path: str):
    """Renderiza a suíte completa oficial do Mozilla PDF.js (viewer.html) com:
    - Rolagem contínua fluida (folha por folha sem interrupção);
    - Painel lateral expansível com miniaturas de páginas e marcadores/índice (outlines);
    - Ferramentas completas de edição/anotação: Destacar texto (Highlighter), Desenho livre (Ink),
      Texto livre (FreeText), Carimbos e Assinatura;
    - Busca de texto com destaque de todas as ocorrências;
    - Zoom dinâmico, rotação e modo apresentação;
    - Botão 'Maximizar Janela' em 100vw/100vh com restauração via botão ou ESC.
    """
    p = resolve_pdf_path(pdf_path)
    if not p or not p.exists():
        st.warning(f"Arquivo PDF não encontrado: {pdf_path}")
        return

    with open(p, "rb") as f:
        pdf_bytes = f.read()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    pdf_viewer_html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Visualizador Oficial PDF.js</title>
      <style>
        * {{
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }}
        html, body {{
          width: 100%;
          height: 100%;
          background: #0e1117;
          overflow: hidden;
        }}
        .viewer-box {{
          position: relative;
          width: 100%;
          height: 870px;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.12);
          overflow: hidden;
          background: #11141b;
          transition: all 0.2s ease;
        }}
        .viewer-box.window-fullscreen {{
          position: fixed !important;
          top: 0 !important;
          left: 0 !important;
          width: 100vw !important;
          height: 100vh !important;
          z-index: 999999999 !important;
          border-radius: 0 !important;
          border: none !important;
        }}
        iframe.pdf-full-frame {{
          width: 100%;
          height: 100%;
          border: none;
          display: block;
        }}
        .btn-fullscreen-toggle {{
          position: absolute;
          top: 0px;
          right: 210px;
          z-index: 10000;
          background: rgba(30, 41, 59, 0.92);
          color: #f8fafc;
          border: 1px solid rgba(59, 130, 246, 0.5);
          padding: 5px 12px;
          border-radius: 5px;
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          backdrop-filter: blur(8px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.4);
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: background 0.15s, border-color 0.15s, transform 0.05s;
        }}
        .btn-fullscreen-toggle:hover {{
          background: #2563eb;
          border-color: #60a5fa;
        }}
        .btn-fullscreen-toggle:active {{
          transform: translateY(1px);
        }}
      </style>
    </head>
    <body>
      <div id="pdf-wrapper" class="viewer-box">
        <button id="toggle-fs-btn" class="btn-fullscreen-toggle" title="Expandir PDF em toda a janela do navegador (ESC para sair)">
          <span id="btn-fs-icon">⛶</span>
          <span id="btn-fs-text">Maximizar Janela</span>
        </button>
        <iframe id="pdf-inner-frame" class="pdf-full-frame" src="./app/static/pdfjs/web/viewer.html"></iframe>
      </div>

      <script>
        const btnFs = document.getElementById('toggle-fs-btn');
        const box = document.getElementById('pdf-wrapper');
        const fsIcon = document.getElementById('btn-fs-icon');
        const fsText = document.getElementById('btn-fs-text');
        const iframe = document.getElementById('pdf-inner-frame');
        const base64Data = "{base64_pdf}";
        const fileName = "{p.name}";

        let isMaximized = false;

        // Envia o PDF em base64 para o viewer.html assim que ele estiver pronto
        function sendPdfToViewer() {{
          if (iframe && iframe.contentWindow) {{
            iframe.contentWindow.postMessage({{
              type: 'LOAD_PDF_BASE64',
              data: base64Data,
              filename: fileName
            }}, '*');
          }}
        }}

        iframe.addEventListener('load', () => {{
          // Envia imediatamente e tenta novamente após 200ms para garantir inicialização
          sendPdfToViewer();
          setTimeout(sendPdfToViewer, 200);
          setTimeout(sendPdfToViewer, 600);
        }});

        window.addEventListener('message', (e) => {{
          if (e.data && e.data.type === 'PDF_VIEWER_READY') {{
            sendPdfToViewer();
          }}
        }});

        // Controle de Maximizar Janela
        btnFs.addEventListener('click', () => {{
          isMaximized = !isMaximized;
          if (isMaximized) {{
            box.classList.add('window-fullscreen');
            fsIcon.innerText = '🗗';
            fsText.innerText = 'Restaurar Janela';
            if (window.frameElement) {{
              window.frameElement.style.position = 'fixed';
              window.frameElement.style.top = '0';
              window.frameElement.style.left = '0';
              window.frameElement.style.width = '100vw';
              window.frameElement.style.height = '100vh';
              window.frameElement.style.zIndex = '999999999';
            }}
          }} else {{
            box.classList.remove('window-fullscreen');
            fsIcon.innerText = '⛶';
            fsText.innerText = 'Maximizar Janela';
            if (window.frameElement) {{
              window.frameElement.style.position = '';
              window.frameElement.style.top = '';
              window.frameElement.style.left = '';
              window.frameElement.style.width = '';
              window.frameElement.style.height = '';
              window.frameElement.style.zIndex = '';
            }}
          }}
        }});

        // Tecla ESC para restaurar
        document.addEventListener('keydown', (e) => {{
          if (e.key === 'Escape' && isMaximized) {{
            btnFs.click();
          }}
        }});
      </script>
    </body>
    </html>
    """
    import streamlit.components.v1 as components
    components.html(pdf_viewer_html, height=890, scrolling=False)


def render_editais_tab():
    EDITAIS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Pré-carrega concurso para obter disciplinas para a sidebar se houver
    editais_todos = get_all_editais()
    initial_edital_id = st.session_state.get("sb_selected_edital_id", editais_todos[0]["id"] if editais_todos else None)
    
    disciplinas_disponiveis = []
    if initial_edital_id:
        topicos_prev = get_verticalizado_by_edital(initial_edital_id)
        if topicos_prev:
            disciplinas_disponiveis = sorted(list({t["disciplina"] for t in topicos_prev}))

    # 2. Renderiza a Sidebar exclusiva de Editais
    sb_params = render_editais_sidebar(disciplinas_disponiveis=disciplinas_disponiveis)
    selected_edital_id = sb_params["edital_id"]

    # 3. Formulário de Novo Edital (aberto quando o usuário clica no botão da sidebar)
    if st.session_state.get("show_new_edital_form", False):
        with st.expander("📝 Formulário de Cadastro de Novo Edital", expanded=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                novo_titulo = st.text_input("Título / Órgão do Concurso *", placeholder="Ex: UFMS, TJMS, MSGÁS, IFMS, TRF3")
                novo_cargo = st.text_input("Cargo Desejado", placeholder="Ex: Professor Visitante - INBIO, Analista de TI")
                novo_banca = st.text_input("Banca Organizadora", placeholder="Ex: FAPEC, FGV, Cebraspe, FCC")
            with col_f2:
                novo_ano = st.number_input("Ano", min_value=2020, max_value=2035, value=2026, step=1)
                novo_interessado = st.selectbox("Interessado(a) *", ["Ambos", "Paulo", "Kamila"])
                novo_link = st.text_input("Link Oficial da Página do Concurso / Editais", placeholder="https://... (onde saem as retificações e comunicados)")
                novo_link_inscricao = st.text_input("Link Direto de Inscrição (Opcional)", placeholder="https://... (portal onde o candidato se inscreve)")

            uploaded_files = st.file_uploader(
                "Arquivos do Edital (.pdf) — Você pode selecionar múltiplos arquivos (Geral + Específicos) *",
                type=["pdf"],
                accept_multiple_files=True
            )

            cargos_detectados = []
            if uploaded_files:
                first_file = uploaded_files[0]
                temp_preview_path = EDITAIS_DIR / f"temp_{first_file.name.replace(' ', '_')}"
                with open(temp_preview_path, "wb") as f:
                    f.write(first_file.getbuffer())
                try:
                    cargos_detectados = discover_cargos_in_pdf(str(temp_preview_path))
                except Exception:
                    cargos_detectados = []

            if cargos_detectados:
                cargo_opcao = st.selectbox(
                    "Cargos detectados no edital principal (Selecione para focar no seu cargo):",
                    options=["Geral / Todos os Cargos"] + cargos_detectados,
                    help="O edital verticalizado focará nos conhecimentos comuns + nos conhecimentos específicos do cargo escolhido."
                )
                if cargo_opcao != "Geral / Todos os Cargos":
                    novo_cargo = cargo_opcao

            if st.button("💾 Salvar e Processar Edital", type="primary"):
                if not novo_titulo:
                    st.error("Informe o Título/Órgão do concurso.")
                elif not uploaded_files:
                    st.error("Faça o upload de ao menos um arquivo PDF do edital.")
                else:
                    concurso_folder = get_edital_folder(titulo=novo_titulo, ano=novo_ano, link_oficial=novo_link)
                    primary_file = uploaded_files[0]
                    safe_primary_name = f"{int(datetime.now().timestamp())}_{primary_file.name.replace(' ', '_')}"
                    dest_path = concurso_folder / safe_primary_name
                    with open(dest_path, "wb") as f:
                        f.write(primary_file.getbuffer())

                    info = inspect_pdf(str(dest_path))

                    edital_id = save_edital(
                        titulo=novo_titulo,
                        cargo=novo_cargo,
                        banca=novo_banca,
                        ano=novo_ano,
                        interessado=novo_interessado,
                        arquivo_nome=primary_file.name,
                        arquivo_path=str(dest_path),
                        link_oficial=novo_link,
                        link_inscricao=novo_link_inscricao,
                        total_paginas=info.get("total_pages", 0)
                    )

                    # Salva arquivos adicionais anexados (ex: edital específico de área / anexo)
                    outros_salvos = 0
                    if len(uploaded_files) > 1:
                        for idx_extra, extra_file in enumerate(uploaded_files[1:], 1):
                            safe_extra_name = f"{int(datetime.now().timestamp())}_{idx_extra}_{extra_file.name.replace(' ', '_')}"
                            dest_extra_path = concurso_folder / safe_extra_name
                            with open(dest_extra_path, "wb") as f_ex:
                                f_ex.write(extra_file.getbuffer())

                            save_edital_documento(
                                edital_id=edital_id,
                                titulo=extra_file.name.replace(".pdf", "").replace(".PDF", ""),
                                tipo="Edital Específico / Anexo",
                                arquivo_nome=extra_file.name,
                                arquivo_path=str(dest_extra_path),
                                data_publicacao=datetime.now().strftime("%d/%m/%Y"),
                                url_origem="",
                                processado=1,
                                resumo="Anexado durante o cadastro do concurso"
                            )
                            outros_salvos += 1

                    with st.spinner("Extraindo cronograma e conteúdo programático localmente..."):
                        crono_items = extract_cronograma_local(str(dest_path))
                        if crono_items:
                            save_cronograma_items(edital_id, crono_items)

                        vert_items = extract_verticalizado_local(str(dest_path), cargo_filtro=novo_cargo)
                        if vert_items:
                            save_verticalizado_items(edital_id, vert_items)

                    msg_extras = f" e {outros_salvos} anexo(s) vinculado(s)" if outros_salvos else ""
                    st.success(f"Edital '{novo_titulo}' cadastrado com sucesso! ({len(crono_items)} datas no cronograma, {len(vert_items)} tópicos encontrados{msg_extras}).")
                    st.session_state.show_new_edital_form = False
                    st.rerun()

    # 4. Verificação de editais cadastrados
    if not selected_edital_id:
        st.info("Nenhum edital cadastrado para os filtros selecionados na barra lateral. Clique em '➕ Novo Edital' para adicionar o primeiro!")
        return

    edital_atual = get_edital_by_id(selected_edital_id)
    if not edital_atual:
        return

    # Formulário Modal/Expander de Edição do Concurso Selecionado
    edit_key = f"show_edit_edital_{selected_edital_id}"
    if st.session_state.get(edit_key, False):
        with st.expander(f"✏️ Editar Informações do Concurso: {edital_atual['titulo']}", expanded=True):
            col_ed1, col_ed2 = st.columns(2)
            with col_ed1:
                edit_titulo = st.text_input("Título / Órgão do Concurso *", value=edital_atual["titulo"], key=f"inp_edit_titulo_{selected_edital_id}")
                edit_cargo = st.text_input("Cargo Desejado", value=edital_atual.get("cargo") or "", key=f"inp_edit_cargo_{selected_edital_id}")
                edit_banca = st.text_input("Banca Organizadora", value=edital_atual.get("banca") or "", key=f"inp_edit_banca_{selected_edital_id}")
                edit_status = st.selectbox(
                    "Status do Concurso",
                    ["Em Andamento", "Finalizado", "Cancelado"],
                    index=["Em Andamento", "Finalizado", "Cancelado"].index(edital_atual.get("status") or "Em Andamento"),
                    key=f"inp_edit_status_{selected_edital_id}"
                )
            with col_ed2:
                edit_ano = st.number_input("Ano", min_value=2020, max_value=2035, value=int(edital_atual.get("ano") or 2026), step=1, key=f"inp_edit_ano_{selected_edital_id}")
                edit_interessado = st.selectbox(
                    "Interessado(a) *",
                    ["Ambos", "Paulo", "Kamila"],
                    index=["Ambos", "Paulo", "Kamila"].index(edital_atual.get("interessado") or "Ambos"),
                    key=f"inp_edit_interessado_{selected_edital_id}"
                )
                edit_link_oficial = st.text_input("Link Oficial da Página do Concurso / Editais", value=edital_atual.get("link_oficial") or "", key=f"inp_edit_link_{selected_edital_id}")
                edit_link_inscricao = st.text_input("Link Direto de Inscrição", value=edital_atual.get("link_inscricao") or "", key=f"inp_edit_link_inscricao_{selected_edital_id}")

            edit_obs = st.text_area("Observações Adicionais", value=edital_atual.get("observacoes") or "", key=f"inp_edit_obs_{selected_edital_id}")

            col_save, col_cancel = st.columns([1, 4])
            with col_save:
                if st.button("💾 Salvar Alterações", type="primary", key=f"btn_save_edital_{selected_edital_id}"):
                    if not edit_titulo:
                        st.error("O título/órgão não pode ficar em branco.")
                    else:
                        ok = update_edital(
                            edital_id=selected_edital_id,
                            titulo=edit_titulo,
                            cargo=edit_cargo,
                            banca=edit_banca,
                            ano=edit_ano,
                            interessado=edit_interessado,
                            status=edit_status,
                            link_oficial=edit_link_oficial,
                            link_inscricao=edit_link_inscricao,
                            observacoes=edit_obs
                        )
                        if ok:
                            st.toast("✅ Dados do concurso atualizados com sucesso!", icon="💾")
                            st.session_state[edit_key] = False
                            st.rerun()
                        else:
                            st.error("Erro ao salvar alterações no banco de dados.")
            with col_cancel:
                if st.button("Cancelar", key=f"btn_cancel_edit_{selected_edital_id}"):
                    st.session_state[edit_key] = False
                    st.rerun()

    # Links Oficiais e Botões de Acesso Externo
    link_oficial = (edital_atual.get("link_oficial") or "").strip()
    link_inscricao = (edital_atual.get("link_inscricao") or "").strip()
    
    col_links, col_edit_btn = st.columns([3.5, 1])
    with col_links:
        badges_html = []
        if link_oficial:
            badges_html.append(
                f'<a href="{link_oficial}" target="_blank" rel="noopener noreferrer" style="'
                f'display: inline-flex; align-items: center; gap: 6px; '
                f'background: linear-gradient(135deg, rgba(37, 99, 235, 0.18), rgba(59, 130, 246, 0.12)); '
                f'border: 1px solid rgba(59, 130, 246, 0.4); color: #60a5fa; padding: 6px 14px; '
                f'border-radius: 6px; text-decoration: none; font-size: 13.5px; font-weight: 500;">'
                f'<span>🌐 Página Oficial / Editais</span><span style="font-size: 11px;">↗</span></a>'
                f'<span style="color: #64748b; font-size: 12px; font-family: monospace;">'
                f'{link_oficial[:45]}{"..." if len(link_oficial) > 45 else ""}</span>'
            )
        if link_inscricao:
            badges_html.append(
                f'<a href="{link_inscricao}" target="_blank" rel="noopener noreferrer" style="'
                f'display: inline-flex; align-items: center; gap: 6px; '
                f'background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.12)); '
                f'border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; padding: 6px 14px; '
                f'border-radius: 6px; text-decoration: none; font-size: 13.5px; font-weight: 500;">'
                f'<span>📝 Portal de Inscrição</span><span style="font-size: 11px;">↗</span></a>'
                f'<span style="color: #64748b; font-size: 12px; font-family: monospace;">'
                f'{link_inscricao[:45]}{"..." if len(link_inscricao) > 45 else ""}</span>'
            )
        if badges_html:
            content_html = " ".join(badges_html)
            st.markdown(
                f'<div style="margin-bottom: 12px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">{content_html}</div>',
                unsafe_allow_html=True
            )

    with col_edit_btn:
        btn_label = "✖️ Fechar Edição" if st.session_state.get(edit_key, False) else "✏️ Editar Concurso"
        if st.button(btn_label, key=f"btn_toggle_edit_{selected_edital_id}", use_container_width=True):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun()

    # Detalhes do Edital Selecionado em Cards Premium
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    with col_d1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Concurso / Órgão</div>
            <div class="metric-value" style="font-size: 20px;">{edital_atual['titulo']}</div>
            <div class="metric-subtext">Ano {edital_atual['ano']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_d2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Cargo / Especialidade</div>
            <div class="metric-value" style="font-size: 18px;">{edital_atual['cargo'] or 'Geral'}</div>
            <div class="metric-subtext">{edital_atual['banca'] or 'Banca N/I'}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_d3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Candidato(a)</div>
            <div class="metric-value" style="font-size: 20px; color: #3b82f6;">{edital_atual['interessado']}</div>
            <div class="metric-subtext">Status: {edital_atual['status']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_d4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Documento PDF</div>
            <div class="metric-value" style="font-size: 20px;">{edital_atual['total_paginas']} págs</div>
            <div class="metric-subtext">{edital_atual['arquivo_nome'][:25]}...</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    from src.components.subtabs import render_subtabs

    # 5. Sub-abas internas estilizadas para o Edital Selecionado
    EDITAIS_SUBTABS = {
        "crono": "📅 Cronograma & Prazos",
        "vert": "🎯 Edital Verticalizado",
        "leitor": "📖 Leitor do PDF",
        "config": "⚙️ Ações & Reprocessamento"
    }
    active_edital_subtab = render_subtabs(EDITAIS_SUBTABS, default_slug="crono", key="editais_internal_subtabs", param_name="subtab")

    # --------------------------------------------------------------------------
    # SUB-ABA 1: CRONOGRAMA & PRAZOS
    # --------------------------------------------------------------------------
    if active_edital_subtab == "crono":
        st.write("##### 🗓️ Cronograma de Atividades e Prazos do Concurso")

        cronograma = get_cronograma_by_edital(selected_edital_id)

        from src.editais.calendar_utils import (
            compute_event_status,
            generate_gcal_url,
            split_period_into_events
        )

        if not cronograma:
            st.warning("Nenhuma data foi extraída automaticamente ainda. Você pode tentar reextrair ou usar o refinamento com IA.")
        else:
            # Enriquecimento com Situação Dinâmica (badges) e links One-Click para Google Calendar
            sigla = edital_atual["titulo"].split('-')[0].split('/')[0].strip()
            rows_display = []
            for item in cronograma:
                ev_nome = item.get("evento", "")
                dt_str = item.get("data_inicio", "")
                obs = item.get("observacao", "")
                
                # Situação Dinâmica
                _, badge_situacao = compute_event_status(dt_str)
                
                # Link rápido para o Google Calendar (Opção B)
                ev_pontuais = split_period_into_events(ev_nome, dt_str, sigla_edital=sigla)
                links_gcal = []
                for ev_p in ev_pontuais:
                    desc_gcal = f"Link: {edital_atual.get('link_oficial', '')}\n\n{ev_nome} - {dt_str}\n{obs}".strip()
                    url_gcal = generate_gcal_url(
                        titulo=ev_p["titulo"],
                        data_ev=ev_p["data_inicio"],
                        descricao=desc_gcal,
                        convidado="kamila_arteman@hotmail.com"
                    )
                    rotulo = "🗓️ Fim" if ev_p["is_fim"] else ("🗓️ Início" if len(ev_pontuais) > 1 else "🗓️ Adicionar")
                    links_gcal.append(f'<a href="{url_gcal}" target="_blank" style="text-decoration: none; background: #1e293b; color: #60a5fa; padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(59, 130, 246, 0.4); font-size: 12px; margin-right: 4px; display: inline-block;">{rotulo}</a>')

                acoes_html = " ".join(links_gcal)

                rows_display.append({
                    "Atividade / Etapa": ev_nome,
                    "Data / Prazo": dt_str,
                    "Situação": badge_situacao,
                    "Google Agenda (1-Click)": acoes_html,
                    "Detalhes": obs
                })

            # Montagem segura do HTML em linha única por elemento sem quebras de linha Markdown
            html_rows = []
            for row in rows_display:
                html_rows.append(
                    f'<tr>'
                    f'<td style="font-weight: 500; color: #f3f4f6;">{row["Atividade / Etapa"]}</td>'
                    f'<td style="color: #cbd5e1; font-family: JetBrains Mono, monospace; font-size: 13px;">{row["Data / Prazo"]}</td>'
                    f'<td>{row["Situação"]}</td>'
                    f'<td style="white-space: nowrap;">{row["Google Agenda (1-Click)"]}</td>'
                    f'<td style="color: #64748b; font-size: 12.5px;">{row["Detalhes"]}</td>'
                    f'</tr>'
                )

            table_component_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8">
              <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
              <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                  background-color: transparent;
                  color: #f3f4f6;
                  font-family: 'Outfit', sans-serif;
                  font-size: 14px;
                  overflow-x: auto;
                }}
                .table-container {{
                  border: 1px solid rgba(255, 255, 255, 0.08);
                  border-radius: 10px;
                  overflow: hidden;
                  background: #11141b;
                  width: 100%;
                }}
                table {{
                  width: 100%;
                  border-collapse: collapse;
                  text-align: left;
                }}
                thead tr {{
                  background: #1a1e27;
                  color: #94a3b8;
                  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }}
                th {{
                  padding: 12px 16px;
                  font-weight: 600;
                  user-select: none;
                  position: relative;
                  cursor: pointer;
                  overflow: visible;
                  white-space: nowrap;
                }}
                th:hover {{
                  color: #60a5fa;
                }}
                td {{
                  padding: 12px 16px;
                  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
                  vertical-align: middle;
                  word-break: break-word;
                }}
                tr:hover td {{
                  background: rgba(255, 255, 255, 0.02);
                }}
                .resizer {{
                  position: absolute;
                  top: 0;
                  right: -3px;
                  width: 8px;
                  cursor: col-resize;
                  user-select: none;
                  height: 100%;
                  z-index: 99;
                }}
                .resizer:hover, .resizing {{
                  background: #3b82f6;
                }}
                a.btn-gcal {{
                  text-decoration: none;
                  background: #1e293b;
                  color: #60a5fa;
                  padding: 4px 8px;
                  border-radius: 6px;
                  border: 1px solid rgba(59, 130, 246, 0.4);
                  font-size: 12px;
                  margin-right: 4px;
                  display: inline-block;
                  transition: background 0.2s, border-color 0.2s;
                }}
                a.btn-gcal:hover {{
                  background: #2563eb;
                  color: #ffffff;
                  border-color: #3b82f6;
                }}
              </style>
            </head>
            <body>
              <div class="table-container">
                <table id="crono-table">
                  <thead>
                    <tr>
                      <th style="width: 38%;" data-col="0">Atividade / Etapa <span id="sort-0">⇅</span></th>
                      <th style="width: 18%;" data-col="1">Data / Prazo <span id="sort-1">⇅</span></th>
                      <th style="width: 14%;" data-col="2">Situação <span id="sort-2">⇅</span></th>
                      <th style="width: 15%; cursor: default;" data-col="3">Google Agenda</th>
                      <th style="width: 15%;" data-col="4">Detalhes <span id="sort-4">⇅</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(html_rows)}
                  </tbody>
                </table>
              </div>

              <script>
                // 1. ORDENAÇÃO DE COLUNAS (ASC / DESC)
                let currentSort = {{ col: -1, dir: 'asc' }};
                const headers = document.querySelectorAll('th[data-col]');

                headers.forEach(th => {{
                  const colIdx = parseInt(th.getAttribute('data-col'));
                  if (colIdx === 3) return; // ignora botões do Google Agenda

                  th.addEventListener('click', (e) => {{
                    if (e.target.classList.contains('resizer')) return;

                    const newDir = (currentSort.col === colIdx && currentSort.dir === 'asc') ? 'desc' : 'asc';
                    currentSort = {{ col: colIdx, dir: newDir }};

                    const table = document.getElementById('crono-table');
                    const tbody = table.querySelector('tbody');
                    const rows = Array.from(tbody.querySelectorAll('tr'));

                    rows.sort((a, b) => {{
                      let valA = a.children[colIdx].innerText.trim().toLowerCase();
                      let valB = b.children[colIdx].innerText.trim().toLowerCase();

                      // Parser de data DD/MM/YYYY para comparação cronológica
                      if (colIdx === 1) {{
                        const parseD = s => {{
                          const m = s.match(/(\\d{{2}})[\\/.-](\\d{{2}})[\\/.-](\\d{{4}})/);
                          return m ? (m[3] + m[2] + m[1]) : s;
                        }};
                        valA = parseD(valA);
                        valB = parseD(valB);
                      }}

                      if (valA < valB) return newDir === 'asc' ? -1 : 1;
                      if (valA > valB) return newDir === 'asc' ? 1 : -1;
                      return 0;
                    }});

                    rows.forEach(r => tbody.appendChild(r));

                    // Atualiza ícones indicadores
                    for (let c = 0; c < 5; c++) {{
                      const icon = document.getElementById('sort-' + c);
                      if (icon) {{
                        icon.innerText = (c === colIdx) ? (newDir === 'asc' ? '▲' : '▼') : '⇅';
                        icon.style.opacity = (c === colIdx) ? '1' : '0.5';
                      }}
                    }}
                  }});
                }});

                // 2. REDIMENSIONAMENTO DE TODAS AS COLUNAS (DRAG & DROP)
                const thElements = Array.from(document.querySelectorAll('th'));
                thElements.forEach((th, idx) => {{
                  // Inicializa larguras absolutas em pixels para permitir redimensionamento sem restrição
                  th.style.width = th.offsetWidth + 'px';

                  const resizer = document.createElement('div');
                  resizer.classList.add('resizer');
                  th.appendChild(resizer);

                  let startX, startW, nextTh, nextStartW;

                  resizer.addEventListener('mousedown', (e) => {{
                    e.stopPropagation();
                    e.preventDefault();
                    startX = e.pageX;
                    startW = th.offsetWidth;
                    nextTh = thElements[idx + 1] || null;
                    if (nextTh) nextStartW = nextTh.offsetWidth;

                    resizer.classList.add('resizing');

                    const onMouseMove = (ev) => {{
                      const diff = ev.pageX - startX;
                      const newW = Math.max(70, startW + diff);
                      th.style.width = newW + 'px';
                      if (nextTh && nextStartW) {{
                        const newNextW = Math.max(70, nextStartW - diff);
                        nextTh.style.width = newNextW + 'px';
                      }}
                    }};

                    const onMouseUp = () => {{
                      resizer.classList.remove('resizing');
                      window.removeEventListener('mousemove', onMouseMove);
                      window.removeEventListener('mouseup', onMouseUp);
                    }};

                    window.addEventListener('mousemove', onMouseMove);
                    window.addEventListener('mouseup', onMouseUp);
                  }});
                }});

                // 3. AUTO-RESIZE: Ajusta altura do iframe dinamicamente conforme conteúdo
                const updateHeight = () => {{
                  const fullHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
                  if (window.parent && window.parent.postMessage) {{
                    window.parent.postMessage({{
                      type: 'streamlit:setFrameHeight',
                      height: fullHeight + 20
                    }}, '*');
                  }}
                }};
                window.addEventListener('load', updateHeight);
                window.addEventListener('resize', updateHeight);
                setTimeout(updateHeight, 200);
              </script>
            </body>
            </html>
            """
            import streamlit.components.v1 as components
            # Altura calculada dinamicamente com folga generosa para textos longos (permite scroll se ultrapassar)
            calc_height = max(500, 100 + (len(rows_display) * 85))
            components.html(table_component_html, height=calc_height, scrolling=True)

    # --------------------------------------------------------------------------
    # SUB-ABA 2: EDITAL VERTICALIZADO (CHECKLIST INTERATIVO)
    # --------------------------------------------------------------------------
    elif active_edital_subtab == "vert":
        st.write("##### 🎯 Edital Verticalizado & Controle de Progresso")
        topicos = get_verticalizado_by_edital(selected_edital_id)

        if not topicos:
            st.warning("Nenhum conteúdo programático foi identificado automaticamente. Acesse a aba 'Ações & Reprocessamento' para reprocessar ou extrair com Gemini.")
        else:
            df_top = pd.DataFrame(topicos)

            # Métricas de Estudo
            total_topicos = len(df_top)
            teoria_concluida = df_top["teoria_concluida"].sum()
            questoes_feitas = df_top["questoes_concluidas"].sum()
            resumos_feitos = df_top["resumo_concluido"].sum()

            pct_teoria = (teoria_concluida / total_topicos * 100) if total_topicos > 0 else 0
            pct_questoes = (questoes_feitas / total_topicos * 100) if total_topicos > 0 else 0

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Total de Tópicos</div>
                    <div class="metric-value">{total_topicos}</div>
                    <div class="metric-subtext">Conteúdo do edital</div>
                </div>
                """, unsafe_allow_html=True)
            with m_col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Teoria Estudada</div>
                    <div class="metric-value" style="color: #3b82f6;">{teoria_concluida}/{total_topicos}</div>
                    <div class="metric-subtext">{pct_teoria:.1f}% concluído</div>
                </div>
                """, unsafe_allow_html=True)
            with m_col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Questões Feitas</div>
                    <div class="metric-value">{questoes_feitas}/{total_topicos}</div>
                    <div class="metric-subtext">{pct_questoes:.1f}% praticado</div>
                </div>
                """, unsafe_allow_html=True)
            with m_col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Resumos Feitos</div>
                    <div class="metric-value">{resumos_feitos}/{total_topicos}</div>
                    <div class="metric-subtext">Material próprio</div>
                </div>
                """, unsafe_allow_html=True)

            st.progress(pct_teoria / 100, text=f"Progresso Geral da Teoria: {pct_teoria:.1f}%")

            # Aplica o filtro de disciplina vindo da sidebar
            sel_disc = sb_params.get("disciplina", "Todas")
            if sel_disc and sel_disc != "Todas":
                df_top = df_top[df_top["disciplina"] == sel_disc]

            # Editor interativo de dados (Data Editor)
            st.caption("Marque as caixas abaixo para registrar seu estudo (salvamento automático):")
            
            display_cols = ["id", "disciplina", "topico", "subtopico", "teoria_concluida", "resumo_concluido", "questoes_concluidas", "revisao_1"]
            df_edit = df_top[display_cols].copy()
            df_edit["teoria_concluida"] = df_edit["teoria_concluida"].astype(bool)
            df_edit["resumo_concluido"] = df_edit["resumo_concluido"].astype(bool)
            df_edit["questoes_concluidas"] = df_edit["questoes_concluidas"].astype(bool)
            df_edit["revisao_1"] = df_edit["revisao_1"].astype(bool)

            edited_df = st.data_editor(
                df_edit,
                column_config={
                    "id": None,
                    "disciplina": st.column_config.TextColumn("Disciplina", disabled=True),
                    "topico": st.column_config.TextColumn("Tópico de Estudo", disabled=True),
                    "subtopico": st.column_config.TextColumn("Desdobramento / Subtópico", disabled=True),
                    "teoria_concluida": st.column_config.CheckboxColumn("📖 Teoria", default=False),
                    "resumo_concluido": st.column_config.CheckboxColumn("✍️ Resumo", default=False),
                    "questoes_concluidas": st.column_config.CheckboxColumn("📝 Questões", default=False),
                    "revisao_1": st.column_config.CheckboxColumn("🔁 R1", default=False),
                },
                use_container_width=True,
                hide_index=True,
                key=f"editor_vert_{selected_edital_id}_{sel_disc}"
            )

            if not edited_df.equals(df_edit):
                for idx, row in edited_df.iterrows():
                    orig_row = df_edit.loc[idx]
                    for col in ["teoria_concluida", "resumo_concluido", "questoes_concluidas", "revisao_1"]:
                        if row[col] != orig_row[col]:
                            update_verticalizado_item(row["id"], col, 1 if row[col] else 0)
                st.toast("Progresso atualizado com sucesso!", icon="✅")
                st.rerun()

    # --------------------------------------------------------------------------
    # SUB-ABA 3: LEITOR DO PDF
    # --------------------------------------------------------------------------
    elif active_edital_subtab == "leitor":
        # Verifica se o usuário selecionou um PDF específico na barra lateral (Edital Original ou Retificação)
        pdf_file = st.session_state.get("leitor_selected_pdf_path") or edital_atual.get("arquivo_path")
        pdf_title = st.session_state.get("leitor_selected_pdf_title") or f"Edital Original ({edital_atual['arquivo_nome']})"

        st.write(f"##### 📖 Leitura do Documento: {pdf_title}")
        resolved_file = resolve_pdf_path(pdf_file)
        if resolved_file and resolved_file.exists():
            render_pdf_viewer(str(resolved_file))
        else:
            st.error(f"Arquivo PDF não encontrado no disco: {pdf_file}")

    # --------------------------------------------------------------------------
    # SUB-ABA 4: AÇÕES & REPROCESSAMENTO (LOCAL OU GEMINI IA)
    # --------------------------------------------------------------------------
    elif active_edital_subtab == "config":
        st.write("##### ⚙️ Retificações, Manutenção e Atualizações do Edital")

        # ----------------------------------------------------------------------
        # SEÇÃO 1: ROBÔ DE ATUALIZAÇÕES DA BANCA (AUTOMÁTICO)
        # ----------------------------------------------------------------------
        st.markdown("###### 🤖 1. Atualizações e Retificações no Portal da Banca")
        link_banca = edital_atual.get("link_oficial", "").strip()

        if not link_banca:
            st.info("💡 Este edital não possui um **Link Oficial da Página do Concurso** cadastrado. Para buscar atualizações automaticamente, edite o concurso e adicione o link.")
        else:
            col_b1, col_b2 = st.columns([2, 1])
            with col_b1:
                st.caption(f"Portal monitorado: `{link_banca}`")
            with col_b2:
                btn_check = st.button("🔍 Verificar Novos Editais / Retificações", type="primary", use_container_width=True)

            if btn_check or st.session_state.get(f"show_updates_{selected_edital_id}", False):
                st.session_state[f"show_updates_{selected_edital_id}"] = True
                with st.spinner("Conectando ao portal da banca e mapeando documentos publicados..."):
                    novos_docs, docs_existentes = check_for_updates(selected_edital_id)

                if not novos_docs:
                    st.success("Tudo atualizado! Nenhum novo edital de retificação pendente no portal da banca.")
                else:
                    st.info(f"Foram encontrados **{len(novos_docs)}** novos documentos disponíveis no portal da banca:")
                    for idx, doc in enumerate(novos_docs):
                        with st.container():
                            col_doc1, col_doc2, col_doc3 = st.columns([3, 1, 1.2])
                            with col_doc1:
                                tipo_badge = "🔴 Retificação" if doc['tipo'] == 'Retificação' else f"📄 {doc['tipo']}"
                                st.markdown(f"**{doc['titulo']}**")
                                st.caption(f"{tipo_badge} • Data: {doc.get('data_publicacao') or 'N/I'}")
                            with col_doc2:
                                st.link_button("🌐 Abrir PDF", doc["url_download"], use_container_width=True)
                            with col_doc3:
                                if st.button("📥 Baixar & Aplicar", key=f"btn_apply_doc_{selected_edital_id}_{idx}", type="primary", use_container_width=True):
                                    with st.spinner(f"Baixando e analisando {doc['titulo']}..."):
                                        saved_path = download_document(
                                            url_download=doc["url_download"],
                                            file_name_hint=doc["arquivo_nome"],
                                            edital_id=selected_edital_id
                                        )
                                        if saved_path:
                                            # Processa retificação e mescla cronograma/disciplinas
                                            res = process_retificacao_pdf(selected_edital_id, saved_path, doc["titulo"])
                                            save_edital_documento(
                                                edital_id=selected_edital_id,
                                                titulo=doc["titulo"],
                                                tipo=doc["tipo"],
                                                arquivo_nome=doc["arquivo_nome"],
                                                arquivo_path=saved_path,
                                                data_publicacao=doc.get("data_publicacao", ""),
                                                url_origem=doc["url_download"],
                                                processado=1,
                                                resumo=res["resumo"]
                                            )
                                            st.toast(f"Retificação aplicada: {res['resumo']}", icon="✅")
                                            st.session_state[f"show_updates_{selected_edital_id}"] = False
                                            st.rerun()
                                        else:
                                            st.error("Falha ao baixar o arquivo da banca.")
                            st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid rgba(255,255,255,0.06);'>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # SEÇÃO 2: UPLOAD MANUAL DE RETIFICAÇÃO (FALLBACK)
        # ----------------------------------------------------------------------
        st.markdown("###### 📤 2. Upload Manual de Edital de Retificação (PDF)")
        with st.expander("Enviar novo edital de retificação manualmente", expanded=False):
            col_up1, col_up2 = st.columns([2, 1])
            with col_up1:
                retif_titulo = st.text_input("Título / Descrição da Retificação", placeholder="Ex: Edital nº 2 - Retificação do Cronograma")
            with col_up2:
                retif_tipo = st.selectbox("Tipo de Documento", ["Retificação", "Edital Complementar", "Comunicado Oficial", "Conteúdo Programático"])

            uploaded_retif = st.file_uploader("Selecione o arquivo da Retificação (.pdf)", type=["pdf"], key=f"upload_retif_{selected_edital_id}")

            if st.button("💾 Processar e Mesclar Retificação", key=f"btn_process_manual_retif_{selected_edital_id}", type="primary"):
                if not uploaded_retif:
                    st.error("Faça o upload do arquivo PDF da retificação.")
                else:
                    concurso_folder = get_edital_folder(
                        titulo=edital_atual.get("titulo", ""),
                        ano=edital_atual.get("ano", 2026),
                        link_oficial=edital_atual.get("link_oficial", "")
                    )
                    safe_name = f"retificacao_{int(datetime.now().timestamp())}_{uploaded_retif.name.replace(' ', '_')}"
                    dest_path = concurso_folder / safe_name
                    with open(dest_path, "wb") as f:
                        f.write(uploaded_retif.getbuffer())

                    tit = retif_titulo.strip() or f"Retificação - {uploaded_retif.name}"
                    with st.spinner("Processando retificação e mesclando alterações com o cronograma..."):
                        res = process_retificacao_pdf(selected_edital_id, str(dest_path), tit)
                        save_edital_documento(
                            edital_id=selected_edital_id,
                            titulo=tit,
                            tipo=retif_tipo,
                            arquivo_nome=uploaded_retif.name,
                            arquivo_path=str(dest_path),
                            data_publicacao=datetime.now().strftime("%d/%m/%Y"),
                            processado=1,
                            resumo=res["resumo"]
                        )
                        st.success(f"Retificação aplicada com sucesso! {res['resumo']}")
                        st.rerun()

        # ----------------------------------------------------------------------
        # SEÇÃO 3: HISTÓRICO DE DOCUMENTOS E RETIFICAÇÕES APLICADAS
        # ----------------------------------------------------------------------
        docs_cadastrados = get_documentos_by_edital(selected_edital_id)
        if docs_cadastrados:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("###### 📚 Histórico de Documentos e Retificações Vinculadas")
            for doc in docs_cadastrados:
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; color: #f3f4f6;">{doc['titulo']}</span>
                        <span style="font-size: 12px; color: #94a3b8; background: rgba(59,130,246,0.15); padding: 2px 8px; border-radius: 4px;">{doc['tipo']}</span>
                    </div>
                    <div style="font-size: 12.5px; color: #94a3b8; margin-top: 4px;">
                        Status: {'✅ Processado' if doc['processado'] else '⏳ Pendente'} • Resumo: {doc.get('resumo') or 'Sem resumo'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # ----------------------------------------------------------------------
        # SEÇÃO 4: REEXTRAÇÃO E MANUTENÇÃO GERAL
        # ----------------------------------------------------------------------
        st.write("##### 🛠️ Manutenção e Enriquecimento por IA")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.write("**Extração Local (Regex / pdfplumber)**")
            if st.button("🔄 Reprocessar Tudo Localmente do Edital Original", key="reprocessar_local_btn"):
                clear_cronograma_by_edital(selected_edital_id)
                clear_verticalizado_by_edital(selected_edital_id)
                c_items = extract_cronograma_local(edital_atual["arquivo_path"])
                save_cronograma_items(selected_edital_id, c_items)
                v_items = extract_verticalizado_local(edital_atual["arquivo_path"], cargo_filtro=edital_atual["cargo"])
                save_verticalizado_items(selected_edital_id, v_items)
                st.success(f"Reprocessado com sucesso! ({len(c_items)} datas, {len(v_items)} tópicos).")
                st.rerun()

        with col_a2:
            st.write("**Extração com IA (Google Gemini)**")
            gemini_pronto = is_gemini_available()
            if not gemini_pronto:
                st.info("💡 Para utilizar o refinamento com IA, adicione `GEMINI_API_KEY=sua_chave` no arquivo `.env`.")
            else:
                if st.button("✨ Refinar Cronograma com Gemini IA", key="gemini_crono_btn"):
                    with st.spinner("Analisando páginas do edital com Gemini..."):
                        pages = extract_full_text_by_pages(edital_atual["arquivo_path"])
                        relevant_text = "\n".join([p["text"] for p in pages if "CRONOGRAMA" in p["text"].upper() or p["page_number"] > len(pages) - 5])
                        ai_crono = extract_cronograma_with_ai(relevant_text)
                        if ai_crono:
                            clear_cronograma_by_edital(selected_edital_id)
                            save_cronograma_items(selected_edital_id, ai_crono)
                            st.success(f"{len(ai_crono)} datas estruturadas com IA!")
                            st.rerun()
                        else:
                            st.warning("O Gemini não retornou novos itens. Verifique o log ou edital.")

        st.markdown("---")
        st.write("**Zona de Perigo**")
        if st.button("🗑️ Excluir este Edital", type="secondary", key="del_edital_btn"):
            delete_edital(selected_edital_id)
            try:
                p = Path(edital_atual["arquivo_path"])
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            st.success(f"Edital {edital_atual['titulo']} excluído com sucesso.")
            st.rerun()
