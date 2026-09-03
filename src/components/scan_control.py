# -*- coding: utf-8 -*-
"""
Controle da execução da varredura em background e visualização de progresso.
"""
import sys
import json
import subprocess
import streamlit as st
from src.config import check_scan_running, read_last_log_lines
from src.logger import logger

def render_scan_control(selected_sources, active_names):
    """Renderiza o botão de disparo de varredura ou indicador de progresso ativo."""
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
            logger.info("Botão 'Iniciar Nova Varredura Completa' clicado na interface Streamlit. Iniciando subprocesso...")
            subprocess.Popen([sys.executable, "src/run_scan.py", json.dumps(selected_sources), json.dumps(active_names)])
            st.toast("🚀 Varredura iniciada em segundo plano!", icon="🔍")
            st.rerun()
