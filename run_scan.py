import sys
import os
import json
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Importações locais
from database import init_db, save_occurrence
from scraper import scan_all_sources
from logger_config import logger

def main():
    # Cria arquivo de lock no Windows
    lock_file = Path(tempfile.gettempdir()) / "diarios_oficiais_scan.lock"
    
    # Grava o PID atual no lock
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Erro ao criar arquivo de lock: {e}")
        sys.exit(1)
        
    try:
        logger.info("Varredora em segundo plano iniciada...")
        
        # Lê os parâmetros passados por argumento
        if len(sys.argv) > 1:
            try:
                selected_sources = json.loads(sys.argv[1])
            except Exception as e:
                logger.error(f"Erro ao parsear selected_sources JSON: {e}")
                selected_sources = None
        else:
            selected_sources = None
            
        # Lê a lista de nomes ativos passados por argumento se disponível
        if len(sys.argv) > 2:
            try:
                monitored_names = json.loads(sys.argv[2])
            except Exception as e:
                logger.error(f"Erro ao parsear selected_names JSON: {e}")
                names_env = os.getenv("MONITOR_NAMES", "Paulo Henrique Gonçalves Rezende,Kamila dos Santos Arteman")
                monitored_names = [name.strip() for name in names_env.split(",") if name.strip()]
        else:
            names_env = os.getenv("MONITOR_NAMES", "Paulo Henrique Gonçalves Rezende,Kamila dos Santos Arteman")
            monitored_names = [name.strip() for name in names_env.split(",") if name.strip()]
        
        init_db()
        found_items = scan_all_sources(monitored_names, selected_sources)
        
        novos = 0
        for item in found_items:
            save_occurrence(item["name"], item["source"], item["date"], item["link"], item["context"])
            novos += 1
            
        logger.success(f"Varredura em segundo plano concluída! {novos} ocorrências mapeadas e sincronizadas.")
        
    except Exception as e:
        logger.error(f"Erro na execução da varredura em segundo plano: {e}")
    finally:
        # Remove arquivo de lock
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception as e:
            logger.error(f"Erro ao remover lock file: {e}")

if __name__ == "__main__":
    main()
