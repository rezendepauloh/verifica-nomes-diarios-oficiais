import sqlite3
import os
from logger_config import logger

DB_PATH = os.path.join(os.path.dirname(__file__), "results.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
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
        conn.commit()
        logger.info("Banco de dados SQLite inicializado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao inicializar o banco de dados: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def is_url_processed(url, name):
    try:
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO processed_urls (url, name) VALUES (?, ?)", (url, name))
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao marcar URL como processada: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def save_occurrence(name, source, date_str, link, context):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
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
        conn.close()

def get_occurrences():
    try:
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.executemany("UPDATE occurrences SET status = ? WHERE id = ?", [(status, occ_id) for occ_id in ids])
        conn.commit()
        logger.success(f"Status de {len(ids)} ocorrências atualizado em lote para {status}.")
    except Exception as e:
        logger.error(f"Erro ao atualizar ocorrências em lote: {e}")
    finally:
        if 'conn' in locals():
            conn.close()



