"""
OptiProcess - Modelo de Usuario
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    administrador = "administrador"
    ingeniero_calidad = "ingeniero_calidad"
    supervisor = "supervisor"
    analista = "analista"
    usuario = "usuario"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    empresa = Column(String(200), nullable=True)
    cargo = Column(String(150), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    rol = Column(String(50), default=UserRole.usuario, nullable=False)
    activo = Column(Boolean, default=True)
    primer_login = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
