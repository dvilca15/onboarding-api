from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import AppUser
from app.schemas import UserResponse, UserUpdate, CambiarPasswordRequest
from app.dependencies import get_current_user, require_admin, get_user_roles
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Usuarios"])


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna el perfil del usuario autenticado con sus roles."""
    return user_service.build_user_response(current_user, db)


@router.get("/", response_model=List[UserResponse])
def list_users(
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista todos los usuarios de la empresa. Solo ADMIN_EMPRESA."""
    return user_service.listar_usuarios(current_user.empresa_id, db)


@router.get("/{id_user}", response_model=UserResponse)
def get_user(
    id_user: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtiene un usuario por ID.
    - ADMIN: puede ver cualquier usuario de su empresa.
    - EMPLEADO: solo puede verse a sí mismo.
    """
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles and current_user.id_user != id_user:
        from app.exceptions import ForbiddenError
        raise ForbiddenError("Solo puedes ver tu propio perfil")
    user = user_service.obtener_usuario(id_user, current_user.empresa_id, db)
    return user_service.build_user_response(user, db)


@router.put("/{id_user}", response_model=UserResponse)
def update_user(
    id_user: int,
    data: UserUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Actualiza un usuario. Solo actualiza los campos enviados.
    - ADMIN: puede actualizar cualquier usuario de su empresa.
    - EMPLEADO: solo puede actualizarse a sí mismo.
    """
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles and current_user.id_user != id_user:
        from app.exceptions import ForbiddenError
        raise ForbiddenError("Solo puedes modificar tu propio perfil")
    user = user_service.actualizar_usuario(id_user, data, current_user, db)
    return user_service.build_user_response(user, db)


@router.delete("/{id_user}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id_user: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina un usuario. Solo ADMIN_EMPRESA."""
    user_service.eliminar_usuario(id_user, current_user, db)


# ── Paso 2: cambio de contraseña con marcado de password_changed ──────────

@router.put("/me/cambiar-password", response_model=UserResponse)
def cambiar_password(
    data: CambiarPasswordRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cambia la contraseña del usuario autenticado y marca
    password_changed = True.

    Valida que:
    - password_actual coincida con el hash almacenado.
    - password_nueva y password_confirmar sean iguales.
    - password_nueva tenga al menos 6 caracteres.
    """
    user = user_service.cambiar_password(current_user, data, db)
    return user_service.build_user_response(user, db)
