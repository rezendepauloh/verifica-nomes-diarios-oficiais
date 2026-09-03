import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Define o nível customizado SUCCESS (25)
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)

logging.Logger.success = success


class SafeStreamWrapper:
    """Wrapper para streams que previne travamentos por UnicodeEncodeError em qualquer ambiente (Windows/Linux/Docker)."""
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        try:
            self.stream.write(data)
        except UnicodeEncodeError:
            try:
                encoding = getattr(self.stream, "encoding", None) or "utf-8"
                safe_data = data.encode(encoding, errors="replace").decode(encoding)
                self.stream.write(safe_data)
            except Exception:
                safe_data = data.encode("ascii", errors="replace").decode("ascii")
                self.stream.write(safe_data)

    def flush(self):
        if hasattr(self.stream, "flush"):
            self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


class ANSIColoredFormatter(logging.Formatter):
    """Formatador com cores ANSI dinâmicas e ícones temáticos para o terminal."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Estilos de cores: (cor_tag_e_icone, icone, cor_texto_mensagem)
    LEVEL_STYLES = {
        logging.DEBUG: ("\033[90m", "⚙️ ", "\033[90m"),                      # Tag Cinza, Texto Cinza
        logging.INFO: ("\033[36m\033[1m", "ℹ️ ", "\033[97m"),                # Tag Ciano Negrito, Texto Branco Claro
        SUCCESS_LEVEL_NUM: ("\033[32m\033[1m", "✅ ", "\033[32m"),           # Tag Verde Negrito, Texto Verde
        logging.WARNING: ("\033[33m\033[1m", "⚠️ ", "\033[93m"),            # Tag Amarelo Negrito, Texto Amarelo Claro
        logging.ERROR: ("\033[31m\033[1m", "❌ ", "\033[91m"),              # Tag Vermelho Negrito, Texto Vermelho Claro
        logging.CRITICAL: ("\033[41m\033[37m\033[1m", "🚨 ", "\033[91m\033[1m"), # Tag Fundo Vermelho, Texto Vermelho Negrito
    }

    def format(self, record):
        tag_color, symbol, msg_color = self.LEVEL_STYLES.get(record.levelno, (self.RESET, "", self.RESET))
        date_str = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        formatted_header = f"{tag_color}[{date_str}] [{symbol}{record.levelname}]{self.RESET}"
        formatted_message = f"{msg_color}{record.getMessage()}{self.RESET}"
        return f"{formatted_header} {formatted_message}"



class PlainBracketFormatter(logging.Formatter):
    """Formatador limpo sem códigos ANSI para persistência em disco."""
    def format(self, record):
        date_str = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"[{date_str}] [{record.levelname}] {record.getMessage()}"


def setup_logging(log_file: Path = None, name: str = "DiarioMonitor") -> logging.Logger:
    """Configura o logging rotativo em arquivo e colorido no console com proteção Unicode."""
    if log_file is None:
        log_file = Path("logs") / "app.log"
        
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Limpa handlers anteriores para evitar duplicações
    
    # Handler de Arquivo (Persistência limpa para leitura no app Streamlit)
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(PlainBracketFormatter())
    logger.addHandler(file_handler)
    
    # Handler de Console (Terminal / Docker logs com cores ANSI e emojis protegidos)
    safe_stdout = SafeStreamWrapper(sys.stdout)
    stream_handler = logging.StreamHandler(safe_stdout)
    stream_handler.setFormatter(ANSIColoredFormatter())
    logger.addHandler(stream_handler)
    
    logger.propagate = False
    return logger


def get_logger():
    return setup_logging()

logger = get_logger()
