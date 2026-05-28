"""
OptiProcess - Servicio de autenticación y gestión de usuarios
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, TokenResponse
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, USER_ROLES,
)
import logging

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class AuthService:

    def register_user(self, db: Session, user_data: UserCreate) -> User:
        """Registrar nuevo usuario con validaciones."""
        existing = db.query(User).filter(User.email == user_data.email.lower()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con ese correo electrónico",
            )

        user = User(
            nombre=user_data.nombre,
            apellido=user_data.apellido,
            email=user_data.email.lower(),
            empresa=user_data.empresa,
            cargo=user_data.cargo,
            hashed_password=hash_password(user_data.password),
            rol=user_data.rol.value if hasattr(user_data.rol, "value") else user_data.rol,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Usuario registrado: {user.email} | Rol: {user.rol}")
        return user

    def login(self, db: Session, email: str, password: str) -> TokenResponse:
        """Autenticar usuario y generar tokens JWT."""
        user = db.query(User).filter(User.email == email.lower()).first()

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos",
            )

        if not user.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu cuenta está desactivada. Contacta al administrador.",
            )

        # Actualizar último login
        user.last_login = datetime.utcnow()
        db.commit()

        token_data = {"sub": str(user.id), "email": user.email, "rol": user.rol}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        logger.info(f"Login exitoso: {user.email}")

        from app.schemas.user import UserResponse
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            usuario=UserResponse.from_orm(user),
        )

    def get_current_user(self, token: str, db: Session) -> User:
        """Obtener usuario actual desde token JWT."""
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.activo:
            raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
        return user

    def get_all_users(self, db: Session) -> list:
        return db.query(User).all()

    def update_user(self, db: Session, user_id: int, update_data: UserUpdate, current_user: User) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if current_user.rol != "administrador" and current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Sin permisos para modificar este usuario")

        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(user, field, value)

        db.commit()
        db.refresh(user)
        return user

    def deactivate_user(self, db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        user.activo = False
        db.commit()
        return user

    def create_default_admin(self, db: Session):
        """Crear usuario administrador por defecto si no existe."""
        admin = db.query(User).filter(User.email == "admin@optiprocess.com").first()
        if not admin:
            admin = User(
                nombre="Administrador",
                apellido="OptiProcess",
                email="admin@optiprocess.com",
                empresa="OptiProcess",
                cargo="Administrador del Sistema",
                hashed_password=hash_password("Admin2024!"),
                rol="administrador",
                primer_login=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Usuario administrador por defecto creado: admin@optiprocess.com / Admin2024!")


auth_service = AuthService()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    return auth_service.get_current_user(token, db)


def require_role(*roles):
    """Decorator para requerir rol específico."""
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.rol not in roles and current_user.rol != "administrador":
            raise HTTPException(
                status_code=403,
                detail=f"Acceso restringido. Roles permitidos: {', '.join(roles)}",
            )
        return current_user
    return dependency
