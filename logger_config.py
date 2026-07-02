import os
import logging
from logging.handlers import RotatingFileHandler

# Define o nível SUCCESS (25)
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)

logging.Logger.success = success

class BracketFormatter(logging.Formatter):
    def format(self, record):
        date_str = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"[{date_str}] [{record.levelname}] {record.getMessage()}"

def get_logger():
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("DiarioMonitor")
    logger.setLevel(logging.INFO)
    
    # Evita duplicar handlers se o logger já estiver configurado
    if not logger.handlers:
        log_path = os.path.join("logs", "app.log")
        # 3 MB = 3 * 1024 * 1024 bytes, mantém até 3 arquivos de backup
        handler = RotatingFileHandler(log_path, maxBytes=3 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(BracketFormatter())
        logger.addHandler(handler)
        
    return logger

logger = get_logger()
