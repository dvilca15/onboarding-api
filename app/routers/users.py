from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import AppUser
from app.schemas import UserResponse, UserUpdate
from app.dependencies import get_current_user, require_admin, get_user_roles
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["Usuarios"])


def build_user_response(user: AppUser, db: Session) -> UserResponse:
    """
    Construye un UserResponse incluyendo los roles del usuario.
    """
    roles = get_user_roles(user, db)
    return UserResponse(
        id_user         = user.id_user,
        nombre          = user.nombre,
        email           = user.email,
        empresa_id      = user.empresa_id,
        fecha_creacion  = user.fecha_creacion,
        roles           = roles
    )


# ── GET /users/me ─────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna el perfil del usuario autenticado junto con sus roles.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    return build_user_response(current_user, db)


# ── GET /users/ ───────────────────────────────────────────────
@router.get("/", response_model=List[UserResponse])
def list_users(
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos los usuarios de la empresa del admin autenticado.
    Solo disponible para ADMIN_EMPRESA.
    """
    users = (
        db.query(AppUser)
        .filter(AppUser.empresa_id == current_user.empresa_id)
        .all()
    )
    return [build_user_response(u, db) for u in users]


# ── GET /users/{id_user} ──────────────────────────────────────
@router.get("/{id_user}", response_model=UserResponse)
def get_user(
    id_user: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene un usuario por ID.
    - ADMIN_EMPRESA: puede ver cualquier usuario de su empresa.
    - EMPLEADO: solo puede verse a sí mismo.
    """
    user = db.query(AppUser).filter(AppUser.id_user == id_user).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Verificar que pertenece a la misma empresa
    if user.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este usuario"
        )

    # Si es empleado, solo puede verse a sí mismo
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles and current_user.id_user != id_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes ver tu propio perfil"
        )

    return build_user_response(user, db)


# ── PUT /users/{id_user} ──────────────────────────────────────
@router.put("/{id_user}", response_model=UserResponse)
def update_user(
    id_user: int,
    data: UserUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza un usuario.
    - ADMIN_EMPRESA: puede actualizar cualquier usuario de su empresa.
    - EMPLEADO: solo puede actualizarse a sí mismo.
    Solo se actualizan los campos enviados (PATCH-style).
    """
    user = db.query(AppUser).filter(AppUser.id_user == id_user).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Verificar empresa
    if user.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar este usuario"
        )

    # Si es empleado, solo puede modificarse a sí mismo
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles and current_user.id_user != id_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes modificar tu propio perfil"
        )

    # Verificar email único si se está cambiando
    if data.email and data.email != user.email:
        existing = db.query(AppUser).filter(AppUser.email == data.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está en uso"
            )

    # Actualizar solo los campos enviados
    if data.nombre is not None:
        user.nombre = data.nombre
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.password = hash_password(data.password)

    db.commit()
    db.refresh(user)
    return build_user_response(user, db)


# ── DELETE /users/{id_user} ───────────────────────────────────
@router.delete("/{id_user}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id_user: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina un usuario.
    Solo disponible para ADMIN_EMPRESA.
    Un admin no puede eliminarse a sí mismo.
    """
    user = db.query(AppUser).filter(AppUser.id_user == id_user).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Verificar empresa
    if user.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este usuario"
        )

    # El admin no puede eliminarse a sí mismo
    if user.id_user == current_user.id_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta"
        )

    db.delete(user)
    db.commit()