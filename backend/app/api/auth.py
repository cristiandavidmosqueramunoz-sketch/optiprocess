"""
OptiProcess - Endpoints de autenticación y gestión de usuarios
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, TokenResponse, UserUpdate, ChangePassword
from app.services.auth_service import auth_service, get_current_user
from app.core.security import hash_password, verify_password
import logging

router = APIRouter(prefix="/auth", tags=["Autenticación"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Registrar nuevo usuario en el sistema."""
    return auth_service.register_user(db, user_data)


@router.post("/login", response_model=TokenResponse)
def login(credentials: dict, db: Session = Depends(get_db)):
    """Login con JSON {email, password}."""
    return auth_service.login(db, credentials.get("email", ""), credentials.get("password", ""))


@router.post("/login/json", response_model=TokenResponse)
def login_json(credentials: dict, db: Session = Depends(get_db)):
    """Login con JSON plano {email, password}."""
    email = credentials.get("email", "")
    password = credentials.get("password", "")
    return auth_service.login(db, email, password)


@router.post("/token", response_model=TokenResponse)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login con form data (compatible OAuth2)."""
    return auth_service.login(db, form_data.username, form_data.password)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Obtener datos del usuario autenticado."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar perfil del usuario actual."""
    return auth_service.update_user(db, current_user.id, update_data, current_user)


@router.post("/change-password")
def change_password(
    data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambiar contraseña del usuario autenticado."""
    if not verify_password(data.password_actual, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    current_user.hashed_password = hash_password(data.password_nuevo)
    current_user.primer_login = False
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente"}


@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar todos los usuarios (solo administradores)."""
    if current_user.rol != "administrador":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden ver todos los usuarios")
    return auth_service.get_all_users(db)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar datos de un usuario (administradores o el propio usuario)."""
    return auth_service.update_user(db, user_id, update_data, current_user)


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desactivar usuario (solo administradores)."""
    if current_user.rol != "administrador":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden desactivar usuarios")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")
    auth_service.deactivate_user(db, user_id)
    return {"mensaje": "Usuario desactivado correctamente"}
