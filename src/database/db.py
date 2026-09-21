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
    # Garante que o diretório pai do banco de dados exista antes de conectar
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        return sqlite3.connect(str(DB_PATH), timeout=30.0)
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
        
        # Migração defensiva: garante que a coluna phone exista caso a tabela já tenha sido criada anteriormente
        try:
            cursor.execute("ALTER TABLE monitored_names ADD COLUMN phone TEXT DEFAULT ''")
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

        # 2. Fontes Padrão
        cursor.execute("SELECT COUNT(*) FROM monitored_sources")
        sources_count = cursor.fetchone()[0]
        if sources_count == 0 or force:
            default_sources = [
                ("dou", "Diário Oficial da União (DOU)", os.getenv("URL_DOU", "https://www.in.gov.br/leiturajornal"), "Busca oficial da Imprensa Nacional"),
                ("doms", "Diário Oficial de MS (DO-MS)", os.getenv("URL_DOMS", "https://www.diariooficial.ms.gov.br"), "API REST do Diário Oficial do Estado de MS"),
                ("ifms", "IFMS (SUAP)", os.getenv("URL_IFMS", "https://suap.ifms.edu.br/bse/consulta_publica/"), "Boletins de serviço e editais do IFMS"),
                ("sanesul", "Sanesul (Concursos)", os.getenv("URL_SANESUL", "https://www.sanesul.ms.gov.br/concursos-e-processos-seletivos"), "Processos seletivos e convocações Sanesul"),
                ("msgas", "MS Gás (Concursos)", os.getenv("URL_MSGAS", "https://transparencia.msgas.com.br/Concursos"), "Editais e chamamentos da MS Gás"),
                ("crbm", "CRBM 1ª Região", os.getenv("URL_CRBM", "https://crbm1.gov.br/"), "Conselho Regional de Biomedicina 1ª Região"),
                ("dourados", "Diário Oficial de Dourados (DO-Dourados)", os.getenv("URL_DOURADOS", "https://do.dourados.ms.gov.br/"), "Edições municipais de Dourados/MS"),
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
    """Retorna todos os nomes cadastrados com id, nome, phone, active e created_at."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, active, created_at FROM monitored_names ORDER BY name ASC")
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

def add_monitored_name(name: str, phone: str = "") -> bool:
    """Cadastra um novo nome monitorado."""
    clean_name = name.strip()
    clean_phone = phone.strip()
    if not clean_name:
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO monitored_names (name, phone, active) VALUES (?, ?, 1)", (clean_name, clean_phone))
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

def update_monitored_name(name_id: int, name: str, phone: str, active: int) -> bool:
    """Atualiza dados de um nome monitorado."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE monitored_names
            SET name = ?, phone = ?, active = ?
            WHERE id = ?
        """, (name.strip(), phone.strip(), active, name_id))
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

def save_occurrence(name, source, date_str, link, context):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO occurrences (name, source, date, link, context)
            VALUES (?, ?, ?, ?, ?)
        """, (name, source, date_str, link, context))
        if cursor.rowcount > 0:
            logger.success(f"Nova ocorrência detectada e salva: {name} em {source}")
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao salvar ocorrência no banco para {name} em {source}: {e}")
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

