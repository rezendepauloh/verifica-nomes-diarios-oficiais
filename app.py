import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

# Importações locais
from database import init_db, save_occurrence, get_occurrences, update_status, update_status_bulk
from scraper import scan_all_sources
from logger_config import logger


# Carrega variáveis de ambiente
load_dotenv()

# Configuração da página Streamlit
st.set_page_config(
    page_title="Rastreador de Concursos e Diários",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa banco de dados
init_db()

def check_scan_running() -> bool:
    """Verifica se a varredura está rodando de forma ativa analisando o arquivo de lock no Windows."""
    import tempfile
    import ctypes
    from pathlib import Path
    
    lock_file = Path(tempfile.gettempdir()) / "diarios_oficiais_scan.lock"
    if not lock_file.exists():
        return False
        
    try:
        with open(lock_file, "r") as f:
            pid = int(f.read().strip())
        
        # Verifica se o processo com esse PID está ativo
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                kernel32.CloseHandle(handle)
                return exit_code.value == 259  # 259 significa STILL_ACTIVE
            kernel32.CloseHandle(handle)
    except:
        pass
    return False

def read_last_log_lines(n: int = 15) -> str:
    """Lê as últimas N linhas do arquivo de log do app."""
    from pathlib import Path
    log_path = Path("logs") / "app.log"
    if not log_path.exists():
        return "Nenhum log gerado ainda. Aguardando início..."
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except Exception as e:
        return f"Erro ao ler arquivo de log: {e}"

# Custom CSS para estética premium (Dark theme, glassmorphism e cards coloridos)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* Global Styles */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Custom header design */
    .header-container {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        position: relative;
        overflow: hidden;
    }
    .header-container::after {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 80%);
        pointer-events: none;
    }
    .header-title {
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-subtitle {
        font-size: 1.1rem;
        font-weight: 300;
        opacity: 0.9;
        margin-top: 0.5rem;
    }
    
    /* Metric Card styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border-left: 5px solid #2a5298;
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-title {
        font-size: 0.9rem;
        color: #6c757d;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #212529;
        margin-top: 0.2rem;
    }
    
    /* Table modifications */
    .stDataFrame {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Recupera nomes configurados no .env
names_env = os.getenv("MONITOR_NAMES", "Paulo Henrique Gonçalves Rezende,Kamila dos Santos Arteman")
monitored_names = [name.strip() for name in names_env.split(",") if name.strip()]

# Título da página
st.markdown("""
<div class="header-container">
    <h1 class="header-title">🔍 Monitor de Diários Oficiais & Concursos</h1>
    <p class="header-subtitle">Varredura automática e centralização de publicações de interesse</p>
</div>
""", unsafe_allow_html=True)

# Sidebar de Configurações
st.sidebar.markdown("### ⚙️ Configurações de Monitoramento")
st.sidebar.write("Selecionar nomes para busca ativa:")
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


# Layout de Colunas para Indicadores / Métricas
occurrences = get_occurrences()
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

# Verifica estado de execução da varredura
varredura_ativa = check_scan_running()

if varredura_ativa:
    st.button("🤖 Varredura em Execução...", disabled=True, key="btn_varredura_ativa")
    with st.expander("🤖 Varredura Rodando em Segundo Plano – Acompanhar Progresso", expanded=False):
        st.info("A varredura está coletando novos diários e editais em segundo plano neste momento. Você pode continuar usando o painel normalmente!")
        logs = read_last_log_lines(100)
        with st.container(height=300):
            st.code(logs, language="text")
        st.button("🔄 Atualizar Progresso", help="Recarrega as últimas linhas de log")
else:
    if st.button("🚀 Iniciar Nova Varredura Completa", key="btn_iniciar_varredura"):
        import subprocess
        import sys
        import json
        logger.info("Botão 'Iniciar Nova Varredura Completa' clicado na interface Streamlit. Iniciando subprocesso...")
        subprocess.Popen([sys.executable, "run_scan.py", json.dumps(selected_sources), json.dumps(active_names)])
        st.toast("🚀 Varredura iniciada em segundo plano!", icon="🔍")
        st.rerun()


@st.dialog("Detalhes da Ocorrência")
def show_occurrence_details(row):

    st.markdown(f"### 👤 {row['Nome']}")
    st.markdown(f"**Fonte:** {row['Fonte']}")
    
    # Formata a data para DD/MM/AAAA
    data_formatada = row['Data da Busca'].strftime("%d/%m/%Y") if not pd.isnull(row['Data da Busca']) else "Sem Data"
    st.markdown(f"**Data da Publicação:** {data_formatada}")
    
    st.markdown("---")
    st.markdown("### 📝 Trecho / Contexto Encontrado")
    
    # Destaca o nome no texto do contexto
    contexto = row['Contexto / Trecho']
    nome = row['Nome']
    import re
    
    def get_accent_insensitive_pattern(text):
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

if total_found > 0:
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
        # Ordena as opções de Mês/Ano de forma decrescente
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
        
    # Prepara links com highlights para o navegador destacar o nome procurado
    def format_highlight_link(row_item):
        link = row_item["Link"]
        if not link:
            return link
        import urllib.parse
        nome_encoded = urllib.parse.quote(row_item["Nome"])
        if link.lower().endswith(".pdf") or "#page=" in link.lower():
            if "#page=" in link:
                return f"{link}&search={nome_encoded}"
            else:
                return f"{link}#search={nome_encoded}"
        else:
            return f"{link}#:~:text={nome_encoded}"
            
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
            # Renderiza tabela interativa com seleção de linhas ativa
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
            
            # Tratamento de clique para exibição de detalhes (Modal)
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
else:
    st.info("Nenhuma ocorrência encontrada até o momento. Clique no botão de varredura acima para buscar.")

