"""
OptiProcess - Módulo de seguridad: hashing, JWT y permisos
Usa bcrypt directamente (sin passlib) para compatibilidad con Python 3.13.
"""
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Roles de usuario disponibles en OptiProcess
USER_ROLES = {
    "administrador": {
        "nivel": 5,
        "permisos": ["*"],
        "descripcion": "Acceso total al sistema",
    },
    "ingeniero_calidad": {
        "nivel": 4,
        "permisos": ["datos", "graficos", "capacidad", "supuestos", "muestreo", "reportes", "fase1", "fase2"],
        "descripcion": "Ingeniero de calidad con acceso completo a módulos técnicos",
    },
    "supervisor": {
        "nivel": 3,
        "permisos": ["datos", "graficos", "capacidad", "reportes", "fase2"],
        "descripcion": "Supervisor con acceso a monitoreo y reportes",
    },
    "analista": {
        "nivel": 2,
        "permisos": ["datos", "graficos", "supuestos", "fase1", "fase2"],
        "descripcion": "Analista con acceso a análisis estadístico",
    },
    "usuario": {
        "nivel": 1,
        "permisos": ["datos", "graficos"],
        "descripcion": "Usuario estándar con acceso básico",
    },
}


def check_permission(user_role: str, required_permission: str) -> bool:
    role = USER_ROLES.get(user_role, USER_ROLES["usuario"])
    if "*" in role["permisos"]:
        return True
    return required_permission in role["permisos"]
