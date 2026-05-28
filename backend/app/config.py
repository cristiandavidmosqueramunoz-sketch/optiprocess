"""
OptiProcess - Configuración centralizada del sistema
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Aplicación
    APP_NAME: str = "OptiProcess"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Sistema Profesional de Control Estadístico de Procesos"
    DEBUG: bool = False

    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Base de datos
    DATABASE_URL: str = "sqlite:///./optiprocess.db"

    # Seguridad JWT
    SECRET_KEY: str = "optiprocess-secret-key-2024-enterprise-spc-platform-secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Archivos
    MAX_FILE_SIZE_MB: int = 50
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reports_output"

    # Límites de análisis
    MIN_SUBGROUP_SIZE: int = 2
    MAX_SUBGROUP_SIZE: int = 25
    MIN_SUBGROUPS_PHASE1: int = 20
    MIN_OBSERVATIONS_IMR: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "optiprocess.log"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
