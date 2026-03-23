from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppUser, UserRole, Role
from app.security import verify_token

# Esquema de seguridad Bearer token
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> AppUser:
    """
    Dependencia base — verifica el token JWT y retorna el usuario autenticado.
    Usar en cualquier endpoint que requiera estar logueado.
    """
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido"
        )

    user = db.query(AppUser).filter(AppUser.id_user == int(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )

    return user


def get_user_roles(user: AppUser, db: Session) -> list[str]:
    """
    Retorna la lista de nombres de roles del usuario.
    Ej: ['ADMIN_EMPRESA', 'EMPLEADO']
    """
    user_roles = (
        db.query(Role.nombre)
        .join(UserRole, UserRole.id_role == Role.id_role)
        .filter(UserRole.id_user == user.id_user)
        .all()
    )
    return [r.nombre for r in user_roles]


def require_admin(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AppUser:
    """
    Dependencia — solo permite acceso a usuarios con rol ADMIN_EMPRESA.
    Usar en endpoints exclusivos del administrador.
    """
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol ADMIN_EMPRESA"
        )
    return current_user


def require_same_empresa(
    target_user: AppUser,
    current_user: AppUser,
    db: Session
) -> None:
    """
    Verifica que el usuario autenticado y el usuario objetivo
    pertenezcan a la misma empresa. Evita que un admin de una
    empresa pueda modificar usuarios de otra empresa.
    """
    if current_user.empresa_id != target_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a usuarios de otra empresa"
        )