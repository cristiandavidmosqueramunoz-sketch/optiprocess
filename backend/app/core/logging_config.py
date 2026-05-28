"""
OptiProcess - Configuración del sistema de logging
"""
import logging
import logging.handlers
import os
from app.config import settings


def setup_logging():
    """Configurar logging para toda la aplicación."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Nivel de log
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Handler para archivo con rotación
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        f"logs/{settings.LOG_FILE}",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Configuración raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silenciar logs ruidosos de librerías externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Sistema de logging inicializado - Nivel: {settings.LOG_LEVEL}"
    )
