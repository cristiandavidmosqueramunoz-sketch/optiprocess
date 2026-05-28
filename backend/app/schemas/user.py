"""
OptiProcess - Schemas de Usuario (Pydantic)
"""
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole
import re


class UserCreate(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    password: str
    empresa: Optional[str] = None
    cargo: Optional[str] = None
    rol: UserRole = UserRole.usuario

    @validator("nombre", "apellido")
    def nombres_validos(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v.strip()

    @validator("password")
    def password_seguro(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    recordar: bool = False


class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    empresa: Optional[str] = None
    cargo: Optional[str] = None
    rol: Optional[UserRole] = None
    activo: Optional[bool] = None


class ChangePassword(BaseModel):
    password_actual: str
    password_nuevo: str

    @validator("password_nuevo")
    def password_seguro(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UserResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    empresa: Optional[str]
    cargo: Optional[str]
    rol: str
    activo: bool
    primer_login: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UserResponse
