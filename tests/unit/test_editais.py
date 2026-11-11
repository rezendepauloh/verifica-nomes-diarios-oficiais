# -*- coding: utf-8 -*-
"""
Testes unitários para o módulo de editais, banco de dados e extratores.
"""
import pytest
from pathlib import Path
from src.database import (
    init_db,
    save_edital,
    get_all_editais,
    get_edital_by_id,
    delete_edital,
    save_cronograma_items,
    get_cronograma_by_edital,
    save_verticalizado_items,
    get_verticalizado_by_edital,
    update_verticalizado_item,
    save_edital_documento,
    get_documentos_by_edital,
    mark_documento_as_processed
)
from src.editais.extractor_local import parse_date_smart, clean_event_text, clean_topic_string
from src.editais.updater import (
    is_cebraspe_url,
    is_fapec_url,
    is_ufms_concursos_url,
    extract_cebraspe_slug,
    fetch_cebraspe_documents,
    fetch_fapec_documents,
    fetch_ufms_concursos_documents,
    check_for_updates,
    merge_retificacao_cronograma,
    merge_retificacao_verticalizado
)
from src.config import get_concurso_slug, get_edital_folder

class TestEditaisDatabase:
    def setup_method(self):
        init_db()

    def test_save_and_retrieve_edital(self):
        edital_id = save_edital(
            titulo="Concurso TJ Teste",
            cargo="Analista de TI",
            banca="FGV",
            ano=2026,
            interessado="Paulo",
            arquivo_nome="tj_teste.pdf",
            arquivo_path="/tmp/tj_teste.pdf",
            link_oficial="https://conhecimento.fgv.br/concursos",
            total_paginas=40
        )
        assert edital_id > 0

        edital = get_edital_by_id(edital_id)
        assert edital is not None
        assert edital["titulo"] == "Concurso TJ Teste"
        assert edital["interessado"] == "Paulo"

        # Listagem com filtro
        editais_paulo = get_all_editais(interessado="Paulo")
        assert any(e["id"] == edital_id for e in editais_paulo)

        editais_kamila = get_all_editais(interessado="Kamila")
        assert not any(e["id"] == edital_id for e in editais_kamila)

        # Limpeza
        delete_edital(edital_id)

    def test_documentos_and_retificacoes_workflow(self):
        edital_id = save_edital(
            titulo="Concurso Teste Retificações",
            cargo="Auditor",
            banca="Cebraspe",
            ano=2026,
            interessado="Paulo",
            arquivo_nome="edital_original.pdf",
            arquivo_path="/tmp/edital_original.pdf",
            link_oficial="https://www.cebraspe.org.br/concursos/cgu_26_affc",
            total_paginas=50
        )
        assert edital_id > 0

        # Adiciona cronograma inicial
        itens_iniciais = [
            {"evento": "Período de Inscrição", "data_inicio": "10/10/2026", "data_fim": "20/10/2026", "data_limite": "20/10/2026", "status": "Previsto", "observacao": ""},
            {"evento": "Aplicação das Provas", "data_inicio": "01/12/2026", "data_fim": "01/12/2026", "data_limite": "01/12/2026", "status": "Previsto", "observacao": ""}
        ]
        save_cronograma_items(edital_id, itens_iniciais)

        # Registra documento de retificação
        doc_id = save_edital_documento(
            edital_id=edital_id,
            titulo="Edital nº 2 - Retificação do Cronograma",
            tipo="Retificação",
            arquivo_nome="edital_2_retif.pdf",
            arquivo_path="/tmp/edital_2_retif.pdf",
            data_publicacao="15/10/2026",
            url_origem="https://cdn.cebraspe.org.br/retif.pdf",
            processado=0
        )
        assert doc_id > 0

        docs = get_documentos_by_edital(edital_id)
        assert len(docs) == 1
        assert docs[0]["titulo"] == "Edital nº 2 - Retificação do Cronograma"

        # Mescla retificação no cronograma: altera data da prova e adiciona novo evento
        novos_itens = [
            {"evento": "Aplicação das Provas", "data_inicio": "15/12/2026", "data_fim": "15/12/2026", "data_limite": "15/12/2026", "observacao": "Nova data"},
            {"evento": "Novo Evento: Atendimento Especializado", "data_inicio": "25/10/2026", "data_fim": "26/10/2026", "data_limite": "26/10/2026", "observacao": ""}
        ]
        stats = merge_retificacao_cronograma(edital_id, novos_itens)
        assert stats["atualizados"] == 1
        assert stats["inseridos"] == 1

        crono_atualizado = get_cronograma_by_edital(edital_id)
        assert len(crono_atualizado) == 3
        prova_item = next(it for it in crono_atualizado if "Aplicação das Provas" in it["evento"])
        assert "[Retificado]" in prova_item["evento"]
        assert prova_item["data_inicio"] == "15/12/2026"

        mark_documento_as_processed(doc_id, resumo="1 atualizado, 1 novo")
        docs_updated = get_documentos_by_edital(edital_id)
        assert docs_updated[0]["processado"] == 1

        # Testa URLs cebraspe e fapec
        assert is_cebraspe_url("https://www.cebraspe.org.br/concursos/cgu_26_affc")
        assert not is_cebraspe_url("https://conhecimento.fgv.br/concursos")
        assert extract_cebraspe_slug("https://www.cebraspe.org.br/concursos/cgu_26_affc") == "cgu_26_affc"

        assert is_fapec_url("https://portal.concurso.fundacaofapec.org.br/edital/ver/22")
        assert is_fapec_url("https://fundacaofapec.org.br/concurso/id/200")
        assert not is_fapec_url("https://cebraspe.org.br")

        # Testa criação de subdiretório e slug do concurso
        slug_cebraspe = get_concurso_slug("CGU", 2026, "https://www.cebraspe.org.br/concursos/cgu_26_affc")
        assert slug_cebraspe == "cgu_26_affc"

        slug_fallback = get_concurso_slug("Técnico MPE MS", 2026, "")
        assert slug_fallback == "tecnico_mpe_ms_2026"

        pasta = get_edital_folder("CGU Teste", 2026, "https://www.cebraspe.org.br/concursos/cgu_26_affc")
        assert pasta.name == "cgu_26_affc"
        assert pasta.exists()

        delete_edital(edital_id)

    def test_banca_parsers_mocked(self, monkeypatch):
        class MockResponse:
            def __init__(self, json_data=None, text="", status_code=200):
                self._json_data = json_data
                self.text = text
                self.status_code = status_code
            def json(self):
                return self._json_data
            def raise_for_status(self):
                pass

        # Mock Cebraspe API
        mock_cebraspe_json = {
            "arquivosEdital": [
                {
                    "tipoExtensaoArquivo": "_.pdf",
                    "nomeArquivo": "retif_1.pdf",
                    "descricaoArquivo": "Edital nº 2 - Retificação do Cronograma",
                    "dataArquivo": "15/10/2026 10:00"
                },
                {
                    "tipoExtensaoArquivo": "_.html",
                    "nomeArquivo": "item.html",
                    "descricaoArquivo": "Item em libras"
                }
            ]
        }
        monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse(json_data=mock_cebraspe_json))
        cebraspe_docs = fetch_cebraspe_documents("https://www.cebraspe.org.br/concursos/cgu_26_affc")
        assert len(cebraspe_docs) == 1
        assert cebraspe_docs[0]["tipo"] == "Retificação"
        assert "retif_1.pdf" in cebraspe_docs[0]["url_download"]

        # Mock FAPEC Scraper
        mock_fapec_html = """
        <div class="list-group-item">
            <a href="https://concurso.fundacaofapec.org.br/arquivo.php?file=edital_abertura.pdf">DOWNLOAD</a>
            <span>30/10/2026 EDITAL PROGEP/UFMS N. 001/2026 - Edital de Abertura</span>
        </div>
        """
        monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse(text=mock_fapec_html))
        fapec_docs = fetch_fapec_documents("https://portal.concurso.fundacaofapec.org.br/edital/ver/22")
        assert len(fapec_docs) == 1
        assert fapec_docs[0]["tipo"] == "Edital de Abertura"
        assert fapec_docs[0]["data_publicacao"] == "30/10/2026"
        assert "arquivo.php" in fapec_docs[0]["url_download"]

        # Mock UFMS Concursos Scraper (concursos.ufms.br)
        assert is_ufms_concursos_url("https://www.concursos.ufms.br/front/news/view/3421")
        assert is_ufms_concursos_url("https://www.concursos.ufms.br/front/setup/121")
        mock_ufms_html = """
        <div class="panel-heading"><h4 class="text-center">Processo Seletivo Professor Visitante UFMS 2026</h4></div>
        <div class="panel-body"><h4 class="text-info">Divulgado Edital para seleção de Professor Visitante</h4></div>
        <table>
            <tr>
                <td><a href="https://www.concursos.ufms.br/front/documents/download/3766">Baixar</a></td>
                <td>Edital PROGEP 147/2026</td>
                <td>4.775</td>
            </tr>
        </table>
        <small>Informação divulgada em 23-10-2026 07:50:28</small>
        """
        def mock_ufms_get(url, *args, **kwargs):
            if "events" in url:
                return MockResponse(text="""
                <tr>
                    <td><a href="https://www.concursos.ufms.br/front/setup/121">Setup</a></td>
                    <td><a href="https://www.concursos.ufms.br/front/news/view/3421">Notícia 3421</a></td>
                </tr>
                """)
            if "setup/121" in url:
                return MockResponse(text="""
                <a href="https://www.concursos.ufms.br/front/news/view/3421">Edital 147</a>
                <a href="https://www.concursos.ufms.br/front/news/view/3426">Retificação 01</a>
                """)
            if "news/view/3426" in url:
                return MockResponse(text="""
                <div class="panel-body"><h4 class="text-info">Retificação do Cronograma</h4></div>
                <table>
                    <tr>
                        <td><a href="https://www.concursos.ufms.br/front/documents/download/3770">Baixar</a></td>
                        <td>Edital PROGEP 150/2026</td>
                    </tr>
                </table>
                """)
            return MockResponse(text=mock_ufms_html)

        monkeypatch.setattr("requests.get", mock_ufms_get)
        ufms_docs = fetch_ufms_concursos_documents("https://www.concursos.ufms.br/front/news/view/3421")
        assert len(ufms_docs) >= 1
        assert any("147/2026" in d["titulo"] for d in ufms_docs)
        assert any(d["url_download"] == "https://www.concursos.ufms.br/front/documents/download/3766" for d in ufms_docs)

        # Testa filtro inteligente: se o edital original já é a abertura, não o lista como "novo"
        edital_id_ufms = save_edital(
            titulo="UFMS Teste",
            cargo="Técnico",
            banca="FAPEC",
            ano=2026,
            interessado="Kamila",
            arquivo_nome="Edital Concurso UFMS.pdf",
            arquivo_path="/tmp/Edital_Concurso_UFMS.pdf",
            link_oficial="https://portal.concurso.fundacaofapec.org.br/edital/ver/22"
        )
        novos, reg = check_for_updates(edital_id_ufms)
        assert len(novos) == 0  # Edital de abertura já cadastrado é ignorado
        delete_edital(edital_id_ufms)

    def test_merge_retificacao_avoids_wrong_matches(self):
        edital_id = save_edital(
            titulo="Concurso Semantica Teste",
            cargo="Auditor",
            banca="Cebraspe",
            ano=2026,
            interessado="Paulo",
            arquivo_nome="teste.pdf",
            arquivo_path="/tmp/teste.pdf"
        )

        itens_iniciais = [
            {"evento": "Consulta à situação provisória da solicitação de isenção de taxa de inscrição", "data_inicio": "26/10/2026 a 28/10/2026", "data_limite": "28/10/2026"},
            {"evento": "Consulta à situação provisória da solicitação de atendimento especializado", "data_inicio": "16/10/2026 a 18/10/2026", "data_limite": "18/10/2026"}
        ]
        save_cronograma_items(edital_id, itens_iniciais)

        # Retificação apenas de atendimento especializado
        itens_retificados = [
            {"evento": "Consulta à situação provisória da solicitação de atendimento especializado", "data_inicio": "16/11/2026 a 18/11/2026", "data_limite": "18/11/2026"}
        ]
        stats = merge_retificacao_cronograma(edital_id, itens_retificados)
        assert stats["atualizados"] == 1
        assert stats["inseridos"] == 0

        crono = get_cronograma_by_edital(edital_id)
        assert len(crono) == 2

        # Verifica se o item de isenção permaneceu intacto
        isencao = next(it for it in crono if "isenção" in it["evento"])
        assert isencao["data_inicio"] == "26/10/2026 a 28/10/2026"
        assert "[Retificado]" not in isencao["evento"]

        # Verifica se o de atendimento especializado foi atualizado
        atend = next(it for it in crono if "atendimento especializado" in it["evento"])
        assert atend["data_inicio"] == "16/11/2026 a 18/11/2026"
        assert "[Retificado]" in atend["evento"]

        delete_edital(edital_id)

        assert get_edital_by_id(edital_id) is None

    def test_cronograma_and_verticalizado_workflow(self):
        edital_id = save_edital(
            titulo="Concurso MPE Teste",
            cargo="Técnico",
            banca="Cebraspe",
            ano=2026,
            interessado="Ambos",
            arquivo_nome="mpe.pdf",
            arquivo_path="/tmp/mpe.pdf"
        )

        # Cronograma
        crono_mock = [
            {"evento": "Inscrições Abertas", "data_inicio": "10/05/2026", "data_limite": "30/05/2026", "status": "Previsto"}
        ]
        assert save_cronograma_items(edital_id, crono_mock) is True
        crono_salvo = get_cronograma_by_edital(edital_id)
        assert len(crono_salvo) == 1
        assert crono_salvo[0]["evento"] == "Inscrições Abertas"

        # Verticalizado
        vert_mock = [
            {"disciplina": "Português", "topico": "Crase", "subtopico": "Casos proibidos"}
        ]
        assert save_verticalizado_items(edital_id, vert_mock) is True
        vert_salvo = get_verticalizado_by_edital(edital_id)
        assert len(vert_salvo) == 1
        assert vert_salvo[0]["topico"] == "Crase"

        # Update de estudo
        item_id = vert_salvo[0]["id"]
        assert update_verticalizado_item(item_id, "teoria_concluida", 1) is True
        vert_atualizado = get_verticalizado_by_edital(edital_id)
        assert vert_atualizado[0]["teoria_concluida"] == 1

        delete_edital(edital_id)

class TestExtractorHelpers:
    def test_parse_date_smart(self):
        dt_ini, dt_fim, dt_exib = parse_date_smart("15/09/2025")
        assert dt_ini == "15/09/2025"

        dt_ini, dt_fim, dt_exib = parse_date_smart("10 a 16/10/2026")
        assert dt_ini == "10/10/2026"
        assert dt_fim == "16/10/2026"
        assert "a" in dt_exib

        dt_ini, dt_fim, dt_exib = parse_date_smart("15 de setembro de 2025")
        assert dt_ini == "15/09/2025"

    def test_clean_event_text(self):
        assert clean_event_text("01. Site do Concurso") == "Site do Concurso"
        assert clean_event_text("  04) Término das Inscrições  ") == "Término das Inscrições"

    def test_clean_topic_string(self):
        assert clean_topic_string("1. Concordância verbal;") == "Concordância verbal"
        assert clean_topic_string("• Regência nominal.") == "Regência nominal"



class TestCalendarUtils:
    def test_compute_event_status_logic(self):
        from src.editais.calendar_utils import compute_event_status
        from datetime import date
        today = date(2026, 11, 4)
        
        # Passado
        st_past, badge_past = compute_event_status("10/10/2026 a 16/10/2026", today=today)
        assert st_past == "Concluído"
        assert "Concluído" in badge_past

        # Em andamento (hoje é 04/11/2026)
        st_current, badge_current = compute_event_status("10/10/2026 a 04/11/2026", today=today)
        assert st_current == "Em Andamento"
        assert "Em Andamento" in badge_current

        # Futuro
        st_fut, badge_fut = compute_event_status("13/12/2026", today=today)
        assert st_fut == "Previsto"
        assert "Previsto" in badge_fut

    def test_split_period_into_events(self):
        from src.editais.calendar_utils import split_period_into_events
        
        events = split_period_into_events(
            "Período de solicitação de inscrições",
            "10/10/2026 a 04/11/2026",
            sigla_edital="CGU"
        )
        assert len(events) == 2
        assert events[0]["titulo"] == "[CGU] Início das inscrições"
        assert events[0]["data_inicio"].day == 10
        assert events[0]["data_inicio"].month == 10
        assert events[1]["titulo"] == "[CGU] Fim das inscrições"
        assert events[1]["data_inicio"].day == 4
        assert events[1]["data_inicio"].month == 11
        assert events[1]["is_fim"] is True

    def test_generate_ics_calendar(self):
        from src.editais.calendar_utils import generate_ics_calendar
        items = [{
            "evento": "Período de solicitação de inscrições com isenção",
            "data_inicio": "10/10/2026 a 16/10/2026",
            "observacao": "Via internet"
        }]
        ics = generate_ics_calendar("CGU", items, link_oficial="https://cebraspe.org.br", convidado="kamila_arteman@hotmail.com")
        assert "BEGIN:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        assert "[CGU]" in ics
        assert "kamila_arteman@hotmail.com" in ics
        assert "END:VCALENDAR" in ics
