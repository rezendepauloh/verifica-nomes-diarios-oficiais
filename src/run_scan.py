import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Adiciona a raiz do projeto e src/ no path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))


# Carrega variáveis de ambiente
load_dotenv()

# Importações dos módulos estruturados em src
from src.database import init_db, save_occurrence
from src.scrapers import scan_all_sources
from src.logger import logger
from src.config import get_lock_file, get_monitored_names

def main():
    lock_file = get_lock_file()
    
    # Grava o PID atual no lock
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Erro ao criar arquivo de lock: {e}")
        sys.exit(1)

        
    try:
        logger.info("Varredora em segundo plano iniciada...")
        
        init_db()

        # Lê os parâmetros passados por argumento ou carrega do SQLite
        if len(sys.argv) > 1 and sys.argv[1] != "null":
            try:
                selected_sources = json.loads(sys.argv[1])
            except Exception as e:
                logger.error(f"Erro ao parsear selected_sources JSON: {e}")
                selected_sources = None
        else:
            selected_sources = None

        if selected_sources is None:
            from src.database import get_active_monitored_sources
            active_src_dict = get_active_monitored_sources()
            selected_sources = {slug: True for slug in active_src_dict.keys()}
            
        # Lê a lista de nomes ativos passados por argumento se disponível
        if len(sys.argv) > 2 and sys.argv[2] != "null":
            try:
                monitored_names = json.loads(sys.argv[2])
            except Exception as e:
                logger.error(f"Erro ao parsear selected_names JSON: {e}")
                monitored_names = get_monitored_names()
        else:
            monitored_names = get_monitored_names()

        found_items = scan_all_sources(monitored_names, selected_sources)
        
        novos = 0
        notificados = 0
        from src.database import get_whatsapp_notification_recipients
        from src.notifications import send_whatsapp_message, format_occurrence_message

        # Obtém todos os contatos ativos que devem receber alertas
        recipients = get_whatsapp_notification_recipients()

        for item in found_items:
            is_new = save_occurrence(item["name"], item["source"], item["date"], item["link"], item["context"])
            if is_new:
                novos += 1
                if recipients:
                    msg_text = format_occurrence_message(
                        name=item["name"],
                        source=item["source"],
                        date_str=item["date"],
                        link=item.get("link", ""),
                        context=item.get("context", "")
                    )
                    # Dispara alerta imediato para cada pessoa cadastrada (Broadcast)
                    for rec in recipients:
                        try:
                            sent = send_whatsapp_message(
                                phone=rec["phone"],
                                message=msg_text,
                                apikey=rec.get("callmebot_apikey")
                            )
                            if sent:
                                notificados += 1
                        except Exception as ex_notif:
                            logger.error(f"Erro ao disparar WhatsApp para '{rec['name']}' ({rec['phone']}): {ex_notif}")

        logger.success(f"Varredura concluída! {novos} novas ocorrências detectadas ({notificados} alertas WhatsApp enviados).")
        
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
