# -*- coding: utf-8 -*-
"""
Camada de acesso e gerenciamento do banco de dados SQLite.
"""
import sqlite3
import os
from pathlib import Path
from src.logger import logger
from src.config import DB_PATH

def get_connection():
    # Garante que o diretório pai do banco de dados exista antes de conectar com permissão restrita (0700)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        from src.security import enforce_secure_dir_permissions, enforce_secure_file_permissions
        enforce_secure_dir_permissions(DB_PATH.parent, mode=0o700)
        conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
        if DB_PATH.exists():
            enforce_secure_file_permissions(DB_PATH, mode=0o600)
        return conn
    except Exception as e:
        logger.error(f"Falha ao conectar no SQLite [DB_PATH={DB_PATH}]: {e}")
        raise

def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                date TEXT NOT NULL,
                link TEXT,
                context TEXT,
                status TEXT DEFAULT 'Pendente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, source, link)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_urls (
                url TEXT,
                name TEXT,
                PRIMARY KEY (url, name)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitored_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                phone TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitored_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                description TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_schedule (
                id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                days_of_week TEXT DEFAULT '["mon","tue","wed","thu","fri"]',
                times TEXT DEFAULT '["08:00"]',
                last_run TIMESTAMP,
                next_run TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trigger_type TEXT DEFAULT 'automático',
                new_records INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                details TEXT DEFAULT ''
            )
        """)

        # Tabelas para o módulo de Editais e Concursos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS editais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                cargo TEXT DEFAULT '',
                banca TEXT DEFAULT '',
                ano INTEGER DEFAULT 2026,
                interessado TEXT DEFAULT 'Ambos',
                status TEXT DEFAULT 'Em Andamento',
                arquivo_nome TEXT NOT NULL,
                arquivo_path TEXT NOT NULL,
                link_oficial TEXT DEFAULT '',
                link_inscricao TEXT DEFAULT '',
                total_paginas INTEGER DEFAULT 0,
                observacoes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edital_cronograma (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edital_id INTEGER NOT NULL,
                evento TEXT NOT NULL,
                data_inicio TEXT,
                data_fim TEXT,
                data_limite TEXT,
                status TEXT DEFAULT 'Previsto',
                observacao TEXT DEFAULT '',
                ordem INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edital_verticalizado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edital_id INTEGER NOT NULL,
                disciplina TEXT NOT NULL,
                topico TEXT NOT NULL,
                subtopico TEXT DEFAULT '',
                peso REAL DEFAULT 1.0,
                questoes_previstas INTEGER DEFAULT 0,
                teoria_concluida INTEGER DEFAULT 0,
                resumo_concluido INTEGER DEFAULT 0,
                questoes_concluidas INTEGER DEFAULT 0,
                revisao_1 INTEGER DEFAULT 0,
                revisao_2 INTEGER DEFAULT 0,
                revisao_3 INTEGER DEFAULT 0,
                observacao TEXT DEFAULT '',
                ordem INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edital_documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edital_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                tipo TEXT DEFAULT 'Retificação',
                arquivo_nome TEXT NOT NULL,
                arquivo_path TEXT NOT NULL,
                data_publicacao TEXT DEFAULT '',
                url_origem TEXT DEFAULT '',
                processado INTEGER DEFAULT 0,
                resumo TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
            )
        """)

        # Tabela de histórico de notificações do cronograma de editais para evitar duplicidades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cronograma_alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cronograma_id INTEGER NOT NULL,
                edital_id INTEGER NOT NULL,
                tipo_alerta TEXT NOT NULL, -- 'hoje', 'amanha', 'manual'
                data_alvo TEXT NOT NULL,   -- 'YYYY-MM-DD'
                phone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cronograma_id) REFERENCES edital_cronograma (id) ON DELETE CASCADE,
                FOREIGN KEY (edital_id) REFERENCES editais (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crono_alert ON cronograma_alert_history (cronograma_id, tipo_alerta, data_alvo, phone)")
        
        # Migração defensiva: garante que a coluna phone e callmebot_apikey existam
        try:
            cursor.execute("ALTER TABLE monitored_names ADD COLUMN phone TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Coluna já existe

        try:
            cursor.execute("ALTER TABLE monitored_names ADD COLUMN callmebot_apikey TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Coluna já existe

        # Migração defensiva: garante que a coluna link_inscricao exista na tabela editais
        try:
            cursor.execute("ALTER TABLE editais ADD COLUMN link_inscricao TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Coluna já existe

        # Garante registro inicial de agendamento se não existir
        cursor.execute("SELECT COUNT(*) FROM scan_schedule")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO scan_schedule (id, enabled, days_of_week, times)
                VALUES (1, 1, '["mon","tue","wed","thu","fri"]', '["08:00"]')
            """)

        conn.commit()
        logger.info("Banco de dados SQLite inicializado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao inicializar o banco de dados: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

    # Popula inicialmente a partir das variáveis de ambiente se as tabelas estiverem vazias
    seed_config_from_env_if_empty()

def seed_config_from_env_if_empty(force: bool = False):
    """Popula monitored_names e monitored_sources com base no .env caso as tabelas estejam vazias ou sob force=True."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Nomes
        cursor.execute("SELECT COUNT(*) FROM monitored_names")
        names_count = cursor.fetchone()[0]
        if names_count == 0 or force:
            env_names = os.getenv("MONITOR_NAMES", "")
            for raw_name in env_names.split(","):
                name = raw_name.strip()
                if name:
                    cursor.execute("""
                        INSERT INTO monitored_names (name, phone, active)
                        VALUES (?, '', 1)
                        ON CONFLICT(name) DO UPDATE SET active=1
                    """, (name,))

        # 2. Fontes Padrão (garante que fontes adicionadas ao código entrem no banco)
        default_sources = [
            ("dou", "Diário Oficial da União (DOU)", os.getenv("URL_DOU", "https://www.in.gov.br/leiturajornal"), "Busca oficial da Imprensa Nacional"),
            ("doms", "Diário Oficial de MS (DO-MS)", os.getenv("URL_DOMS", "https://www.diariooficial.ms.gov.br"), "API REST do Diário Oficial do Estado de MS"),
            ("ifms", "IFMS (SUAP)", os.getenv("URL_IFMS", "https://suap.ifms.edu.br/bse/consulta_publica/"), "Boletins de serviço e editais do IFMS"),
            ("sanesul", "Sanesul (Concursos)", os.getenv("URL_SANESUL", "https://www.sanesul.ms.gov.br/concursos-e-processos-seletivos"), "Processos seletivos e convocações Sanesul"),
            ("msgas", "MS Gás (Concursos)", os.getenv("URL_MSGAS", "https://transparencia.msgas.com.br/Concursos"), "Editais e chamamentos da MS Gás"),
            ("crbm", "CRBM 1ª Região", os.getenv("URL_CRBM", "https://crbm1.gov.br/"), "Conselho Regional de Biomedicina 1ª Região"),
            ("dourados", "Diário Oficial de Dourados (DO-Dourados)", os.getenv("URL_DOURADOS", "https://do.dourados.ms.gov.br/"), "Edições municipais de Dourados/MS"),
            ("mpms", "Ministério Público de MS (MPMS)", os.getenv("URL_MPMS", "https://www.mpms.mp.br/atos-e-normas"), "Atos e Normas Oficiais do MPMS"),
        ]
        for slug, label, url, desc in default_sources:
            if url:
                cursor.execute("""
                    INSERT INTO monitored_sources (slug, name, url, description, active)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(slug) DO UPDATE SET url=excluded.url, name=excluded.name
                """, (slug, label, url, desc))

        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao sincronizar configurações do .env para o SQLite: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# ==============================================================================
# OPERAÇÕES DE NOMES MONITORADOS
# ==============================================================================

def get_all_monitored_names():
    """Retorna todos os nomes cadastrados com id, nome, phone, callmebot_apikey, active e created_at."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, callmebot_apikey, active, created_at FROM monitored_names ORDER BY name ASC")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro ao buscar nomes monitorados: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_active_monitored_names():
    """Retorna lista de nomes com active=1."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM monitored_names WHERE active = 1 ORDER BY name ASC")
        rows = cursor.fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Erro ao buscar nomes ativos: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_whatsapp_notification_recipients():
    """
    Retorna todos os destinatários ativos que possuem telefone e API Key cadastrados
    (ou chave global definida no .env).
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, phone, callmebot_apikey 
            FROM monitored_names 
            WHERE active = 1 AND phone != '' AND (callmebot_apikey != '' OR ? != '')
        """, (os.getenv("CALLMEBOT_API_KEY", "").strip(),))
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "phone": r[2],
                "callmebot_apikey": r[3]
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar destinatários de WhatsApp: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def add_monitored_name(name: str, phone: str = "", callmebot_apikey: str = "") -> bool:
    """Cadastra um novo nome monitorado."""
    clean_name = name.strip()
    clean_phone = phone.strip()
    clean_key = callmebot_apikey.strip()
    if not clean_name:
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO monitored_names (name, phone, callmebot_apikey, active) VALUES (?, ?, ?, 1)", (clean_name, clean_phone, clean_key))
        conn.commit()
        logger.success(f"Nome monitorado cadastrado: {clean_name}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Nome já cadastrado: {clean_name}")
        return False
    except Exception as e:
        logger.error(f"Erro ao cadastrar nome monitorado {clean_name}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def update_monitored_name(name_id: int, name: str, phone: str, callmebot_apikey: str, active: int) -> bool:
    """Atualiza dados de um nome monitorado."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE monitored_names
            SET name = ?, phone = ?, callmebot_apikey = ?, active = ?
            WHERE id = ?
        """, (name.strip(), phone.strip(), callmebot_apikey.strip(), active, name_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar nome monitorado ID {name_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def toggle_monitored_name(name_id: int, current_active: int) -> bool:
    """Alterna o status ativo/inativo de um nome."""
    new_status = 0 if current_active == 1 else 1
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE monitored_names SET active = ? WHERE id = ?", (new_status, name_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao alternar status do nome ID {name_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def delete_monitored_name(name_id: int) -> bool:
    """Remove um nome monitorado."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM monitored_names WHERE id = ?", (name_id,))
        conn.commit()
        logger.success(f"Nome monitorado ID {name_id} excluído com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao excluir nome monitorado ID {name_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

# ==============================================================================
# OPERAÇÕES DE FONTES MONITORADAS
# ==============================================================================

def get_all_monitored_sources():
    """Retorna todas as fontes cadastradas com id, slug, name, url, description, active e created_at."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, slug, name, url, description, active, created_at FROM monitored_sources ORDER BY name ASC")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro ao buscar fontes monitoradas: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_active_monitored_sources():
    """Retorna dict com {slug: url} das fontes com active=1."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT slug, url FROM monitored_sources WHERE active = 1")
        return {r[0]: r[1] for r in cursor.fetchall()}
    except Exception as e:
        logger.error(f"Erro ao buscar fontes ativas: {e}")
        return {}
    finally:
        if 'conn' in locals():
            conn.close()

def add_monitored_source(slug: str, name: str, url: str, description: str = "") -> bool:
    """Cadastra uma nova fonte oficial de dados."""
    clean_slug = slug.strip().lower()
    clean_name = name.strip()
    clean_url = url.strip()
    if not clean_slug or not clean_name or not clean_url:
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO monitored_sources (slug, name, url, description, active)
            VALUES (?, ?, ?, ?, 1)
        """, (clean_slug, clean_name, clean_url, description.strip()))
        conn.commit()
        logger.success(f"Fonte monitorada cadastrada: [{clean_slug}] {clean_name}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Fonte com slug '{clean_slug}' já existe.")
        return False
    except Exception as e:
        logger.error(f"Erro ao cadastrar fonte monitorada {clean_name}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def update_monitored_source(source_id: int, slug: str, name: str, url: str, description: str, active: int) -> bool:
    """Atualiza dados de uma fonte monitorada."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE monitored_sources
            SET slug = ?, name = ?, url = ?, description = ?, active = ?
            WHERE id = ?
        """, (slug.strip().lower(), name.strip(), url.strip(), description.strip(), active, source_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar fonte ID {source_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def toggle_monitored_source(source_id: int, current_active: int) -> bool:
    """Alterna o status ativo/inativo de uma fonte."""
    new_status = 0 if current_active == 1 else 1
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE monitored_sources SET active = ? WHERE id = ?", (new_status, source_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao alternar status da fonte ID {source_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def delete_monitored_source(source_id: int) -> bool:
    """Remove uma fonte monitorada."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM monitored_sources WHERE id = ?", (source_id,))
        conn.commit()
        logger.success(f"Fonte ID {source_id} excluída com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao excluir fonte ID {source_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def is_url_processed(url, name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_urls WHERE url = ? AND name = ?", (url, name))
        row = cursor.fetchone()
        return row is not None
    except Exception as e:
        logger.error(f"Erro ao verificar URL processada: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def mark_url_processed(url, name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO processed_urls (url, name) VALUES (?, ?)", (url, name))
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao marcar URL como processada: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def save_occurrence(name, source, date_str, link, context) -> bool:
    """
    Salva uma ocorrência no banco.
    Retorna True se for uma ocorrência inédita (inserida com sucesso),
    ou False se já existia (ignorada por duplicidade) ou em caso de erro.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO occurrences (name, source, date, link, context)
            VALUES (?, ?, ?, ?, ?)
        """, (name, source, date_str, link, context))
        is_new = cursor.rowcount > 0
        if is_new:
            logger.success(f"Nova ocorrência detectada e salva: {name} em {source}")
        conn.commit()
        return is_new
    except Exception as e:
        logger.error(f"Erro ao salvar ocorrência no banco para {name} em {source}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_occurrences():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, source, date, link, context, status, created_at FROM occurrences ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logger.error(f"Erro ao buscar ocorrências no banco: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def update_status(occurrence_id, status):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE occurrences SET status = ? WHERE id = ?", (status, occurrence_id))
        conn.commit()
        logger.success(f"Status da ocorrência {occurrence_id} atualizado para {status}.")
    except Exception as e:
        logger.error(f"Erro ao atualizar status da ocorrência {occurrence_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def update_status_bulk(ids, status):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.executemany("UPDATE occurrences SET status = ? WHERE id = ?", [(status, occ_id) for occ_id in ids])
        conn.commit()
        logger.success(f"Status de {len(ids)} ocorrências atualizado em lote para {status}.")
    except Exception as e:
        logger.error(f"Erro ao atualizar ocorrências em lote: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_schedule_config():
    """Retorna a configuração de agendamento automático salva no SQLite."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT enabled, days_of_week, times, last_run, next_run FROM scan_schedule WHERE id = 1")
        row = cursor.fetchone()
        if row:
            import json
            enabled, days_json, times_json, last_run, next_run = row
            return {
                "enabled": bool(enabled == 1),
                "days_of_week": json.loads(days_json) if days_json else ["mon", "tue", "wed", "thu", "fri"],
                "times": json.loads(times_json) if times_json else ["08:00"],
                "last_run": last_run,
                "next_run": next_run
            }
        return {
            "enabled": True,
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "times": ["08:00"],
            "last_run": None,
            "next_run": None
        }
    except Exception as e:
        logger.error(f"Erro ao buscar configuração de agendamento: {e}")
        return {
            "enabled": True,
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "times": ["08:00"],
            "last_run": None,
            "next_run": None
        }
    finally:
        if 'conn' in locals():
            conn.close()

def save_schedule_config(enabled: bool, days_of_week: list, times: list):
    """Salva a configuração de agendamento no banco de dados SQLite."""
    try:
        import json
        conn = get_connection()
        cursor = conn.cursor()
        days_json = json.dumps(days_of_week)
        times_json = json.dumps(times)
        cursor.execute("""
            INSERT INTO scan_schedule (id, enabled, days_of_week, times, updated_at)
            VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                enabled = excluded.enabled,
                days_of_week = excluded.days_of_week,
                times = excluded.times,
                updated_at = CURRENT_TIMESTAMP
        """, (1 if enabled else 0, days_json, times_json))
        conn.commit()
        logger.success("Configurações de agendamento atualizadas com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar configuração de agendamento: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def update_schedule_execution_times(last_run: str = None, next_run: str = None):
    """Atualiza as datas de última e próxima execução no banco."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if last_run and next_run:
            cursor.execute("UPDATE scan_schedule SET last_run = ?, next_run = ? WHERE id = 1", (last_run, next_run))
        elif last_run:
            cursor.execute("UPDATE scan_schedule SET last_run = ? WHERE id = 1", (last_run,))
        elif next_run:
            cursor.execute("UPDATE scan_schedule SET next_run = ? WHERE id = 1", (next_run,))
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao atualizar datas de execução do scheduler: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def record_scan_execution(trigger_type: str = "automático", new_records: int = 0, success: bool = True, details: str = "") -> bool:
    """Registra uma execução de varredura no histórico de execuções do SQLite."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scan_history (trigger_type, new_records, success, details)
            VALUES (?, ?, ?, ?)
        """, (trigger_type, new_records, 1 if success else 0, details))
        conn.commit()
        logger.info(f"Histórico de execução registrado: tipo='{trigger_type}', novos={new_records}, sucesso={success}")
        return True
    except Exception as e:
        logger.error(f"Erro ao registrar histórico de execução: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_scan_history(limit: int = 200) -> list:
    """Retorna os últimos registros do histórico de execuções do cron/varredura."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, executed_at, trigger_type, new_records, success, details
            FROM scan_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de execuções: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


# ==============================================================================
# CRUD & MÉTODOS DO MÓDULO DE EDITAIS E CONCURSOS
# ==============================================================================

def save_edital(titulo: str, cargo: str, banca: str, ano: int, interessado: str,
                arquivo_nome: str, arquivo_path: str, link_oficial: str = "",
                total_paginas: int = 0, observacoes: str = "", status: str = "Em Andamento",
                link_inscricao: str = "") -> int:
    """Salva um novo edital no banco de dados e retorna o id gerado."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO editais (
                titulo, cargo, banca, ano, interessado, status,
                arquivo_nome, arquivo_path, link_oficial, link_inscricao, total_paginas, observacoes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (titulo, cargo, banca, ano, interessado, status,
              arquivo_nome, arquivo_path, link_oficial, link_inscricao, total_paginas, observacoes))
        edital_id = cursor.lastrowid
        conn.commit()
        logger.info(f"Edital '{titulo}' inserido com sucesso (ID {edital_id}).")
        return edital_id
    except Exception as e:
        logger.error(f"Erro ao salvar edital '{titulo}': {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def get_all_editais(interessado: str = "Todos", status: str = "Todos") -> list:
    """Retorna a lista de editais cadastrados, aplicando filtros opcionais."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM editais WHERE 1=1"
        params = []
        if interessado and interessado != "Todos":
            query += " AND (interessado = ? OR interessado = 'Ambos')"
            params.append(interessado)
        if status and status != "Todos":
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC"
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.error(f"Erro ao buscar editais: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_edital_by_id(edital_id: int):
    """Busca os dados de um edital específico pelo ID."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM editais WHERE id = ?", (edital_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Erro ao buscar edital {edital_id}: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def update_edital(edital_id: int, titulo: str, cargo: str, banca: str, ano: int,
                  interessado: str, status: str, link_oficial: str = "", observacoes: str = "",
                  link_inscricao: str = "") -> bool:
    """Atualiza as informações cadastrais de um edital."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE editais
            SET titulo = ?, cargo = ?, banca = ?, ano = ?, interessado = ?,
                status = ?, link_oficial = ?, link_inscricao = ?, observacoes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (titulo, cargo, banca, ano, interessado, status, link_oficial, link_inscricao, observacoes, edital_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar edital {edital_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def delete_edital(edital_id: int) -> bool:
    """Exclui o edital e todos os dados associados (cronograma e verticalizado)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM edital_cronograma WHERE edital_id = ?", (edital_id,))
        cursor.execute("DELETE FROM edital_verticalizado WHERE edital_id = ?", (edital_id,))
        cursor.execute("DELETE FROM editais WHERE id = ?", (edital_id,))
        conn.commit()
        logger.info(f"Edital {edital_id} e seus dados excluídos com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao excluir edital {edital_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

# --- Cronograma ---

def save_cronograma_items(edital_id: int, items: list) -> bool:
    """
    Insere uma lista de itens de cronograma para o edital.
    Cada item é um dict com: evento, data_inicio, data_fim, data_limite, observacao, status.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for idx, item in enumerate(items):
            cursor.execute("""
                INSERT INTO edital_cronograma (
                    edital_id, evento, data_inicio, data_fim, data_limite, status, observacao, ordem
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                edital_id,
                item.get("evento", ""),
                item.get("data_inicio", ""),
                item.get("data_fim", ""),
                item.get("data_limite", ""),
                item.get("status", "Previsto"),
                item.get("observacao", ""),
                item.get("ordem", idx)
            ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar cronograma do edital {edital_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_cronograma_by_edital(edital_id: int) -> list:
    """Retorna todos os eventos do cronograma de um edital ordenados."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM edital_cronograma
            WHERE edital_id = ?
            ORDER BY ordem ASC, id ASC
        """, (edital_id,))
        return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Erro ao buscar cronograma do edital {edital_id}: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def has_cronograma_alert_been_sent(cronograma_id: int, tipo_alerta: str, data_alvo: str, phone: str) -> bool:
    """Verifica se um determinado alerta de cronograma já foi enviado para o telefone na data alvo."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM cronograma_alert_history
            WHERE cronograma_id = ? AND tipo_alerta = ? AND data_alvo = ? AND phone = ?
        """, (cronograma_id, tipo_alerta, data_alvo, phone))
        return cursor.fetchone()[0] > 0
    except Exception as e:
        logger.error(f"Erro ao verificar envio de alerta de cronograma: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def record_cronograma_alert_sent(cronograma_id: int, edital_id: int, tipo_alerta: str, data_alvo: str, phone: str) -> bool:
    """Registra o envio de um alerta de cronograma no banco."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cronograma_alert_history (cronograma_id, edital_id, tipo_alerta, data_alvo, phone)
            VALUES (?, ?, ?, ?, ?)
        """, (cronograma_id, edital_id, tipo_alerta, data_alvo, phone))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao registrar histórico de alerta de cronograma: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_cronograma_alert_history(limit: int = 500) -> list:
    """Retorna o histórico de alertas de cronograma enviados via WhatsApp enriquecido com dados do edital."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                h.id,
                h.created_at,
                h.tipo_alerta,
                h.data_alvo,
                h.phone,
                e.id as edital_id,
                COALESCE(e.titulo, 'Edital Removido') as edital_titulo,
                COALESCE(e.cargo, '') as edital_cargo,
                COALESCE(e.interessado, 'Ambos') as edital_interessado,
                COALESCE(c.evento, 'Evento Removido') as evento,
                COALESCE(c.data_inicio, '') as data_inicio,
                COALESCE(c.data_fim, '') as data_fim
            FROM cronograma_alert_history h
            LEFT JOIN editais e ON e.id = h.edital_id
            LEFT JOIN edital_cronograma c ON c.id = h.cronograma_id
            ORDER BY h.id DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de alertas de cronograma: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_all_active_cronogramas() -> list:
    """Retorna todos os eventos de cronograma de editais ativos com os dados do edital associado."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id as cronograma_id,
                c.evento,
                c.data_inicio,
                c.data_fim,
                c.data_limite,
                c.status,
                c.observacao,
                e.id as edital_id,
                e.titulo as edital_titulo,
                e.cargo as edital_cargo,
                e.banca as edital_banca,
                e.ano as edital_ano,
                e.interessado as edital_interessado,
                e.link_oficial,
                e.link_inscricao
            FROM edital_cronograma c
            JOIN editais e ON c.edital_id = e.id
            ORDER BY c.data_inicio ASC, c.ordem ASC
        """)
        return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Erro ao buscar cronogramas ativos: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def update_cronograma_item_status(item_id: int, status: str) -> bool:
    """Atualiza o status de um item de cronograma (ex: 'Concluído', 'Pendente', 'Cancelado')."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE edital_cronograma SET status = ? WHERE id = ?", (status, item_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar status do cronograma {item_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def clear_cronograma_by_edital(edital_id: int) -> bool:
    """Limpa todos os eventos de cronograma do edital para reextração."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM edital_cronograma WHERE edital_id = ?", (edital_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao limpar cronograma do edital {edital_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

# --- Edital Verticalizado ---

def save_verticalizado_items(edital_id: int, items: list) -> bool:
    """
    Insere uma lista de itens do edital verticalizado.
    Cada item é um dict: disciplina, topico, subtopico, peso, questoes_previstas, observacao, ordem.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for idx, item in enumerate(items):
            cursor.execute("""
                INSERT INTO edital_verticalizado (
                    edital_id, disciplina, topico, subtopico, peso, questoes_previstas, observacao, ordem
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                edital_id,
                item.get("disciplina", "Geral"),
                item.get("topico", ""),
                item.get("subtopico", ""),
                item.get("peso", 1.0),
                item.get("questoes_previstas", 0),
                item.get("observacao", ""),
                item.get("ordem", idx)
            ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar itens verticalizados do edital {edital_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_verticalizado_by_edital(edital_id: int) -> list:
    """Retorna todos os tópicos verticalizados de um edital."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM edital_verticalizado
            WHERE edital_id = ?
            ORDER BY disciplina ASC, ordem ASC, id ASC
        """, (edital_id,))
        return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Erro ao obter edital verticalizado {edital_id}: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def update_verticalizado_item(item_id: int, field: str, value: int) -> bool:
    """Atualiza o estado de estudo (ex: teoria_concluida, resumo_concluido, etc.) de um tópico."""
    allowed_fields = {
        "teoria_concluida", "resumo_concluido", "questoes_concluidas",
        "revisao_1", "revisao_2", "revisao_3"
    }
    if field not in allowed_fields:
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE edital_verticalizado
            SET {field} = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if value else 0, item_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar verticalizado {item_id} [{field}={value}]: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def clear_verticalizado_by_edital(edital_id: int) -> bool:
    """Limpa os tópicos verticalizados de um edital para reprocessamento."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM edital_verticalizado WHERE edital_id = ?", (edital_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao limpar edital verticalizado {edital_id}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


# ----------------------------------------------------------------------
# DOCUMENTOS / RETIFICAÇÕES DE EDITAIS
# ----------------------------------------------------------------------

def save_edital_documento(edital_id: int, titulo: str, tipo: str, arquivo_nome: str,
                          arquivo_path: str, data_publicacao: str = "", url_origem: str = "",
                          processado: int = 0, resumo: str = "") -> int:
    """Salva ou registra um documento anexo ou edital de retificação."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO edital_documentos (
                edital_id, titulo, tipo, arquivo_nome, arquivo_path,
                data_publicacao, url_origem, processado, resumo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (edital_id, titulo, tipo, arquivo_nome, arquivo_path,
              data_publicacao, url_origem, processado, resumo))
        doc_id = cursor.lastrowid
        conn.commit()
        return doc_id
    except Exception as e:
        logger.error(f"Erro ao salvar edital_documento para edital {edital_id}: {e}")
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

def get_documentos_by_edital(edital_id: int) -> list:
    """Retorna os documentos e retificações vinculados a um edital."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM edital_documentos
            WHERE edital_id = ?
            ORDER BY id DESC
        """, (edital_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Erro ao buscar documentos do edital {edital_id}: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def mark_documento_as_processed(doc_id: int, resumo: str = "") -> bool:
    """Marca documento como processado com sucesso."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE edital_documentos
            SET processado = 1, resumo = ?
            WHERE id = ?
        """, (resumo, doc_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao marcar documento {doc_id} como processado: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()




