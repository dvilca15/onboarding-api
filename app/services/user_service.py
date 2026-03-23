from sqlalchemy.orm import Session
from typing import List
from app.models import AppUser, Role, UserRole
from app.schemas import UserUpdate, UserResponse
from app.security import hash_password
from app.exceptions import NotFoundError, ForbiddenError, BadRequestError


def get_user_roles(user: AppUser, db: Session) -> List[str]:
    """Retorna la lista de nombres de roles del usuario."""
    rows = (
        db.query(Role.nombre)
        .join(UserRole, UserRole.id_role == Role.id_role)
        .filter(UserRole.id_user == user.id_user)
        .all()
    )
    return [r.nombre for r in rows]


def build_user_response(user: AppUser, db: Session) -> UserResponse:
    """Construye un UserResponse enriquecido con los roles."""
    return UserResponse(
        id_user        = user.id_user,
        nombre         = user.nombre,
        email          = user.email,
        empresa_id     = user.empresa_id,
        fecha_creacion = user.fecha_creacion,
        roles          = get_user_roles(user, db),
    )


def listar_usuarios(empresa_id: int, db: Session) -> List[UserResponse]:
    """Lista todos los usuarios de una empresa."""
    usuarios = (
        db.query(AppUser)
        .filter(AppUser.empresa_id == empresa_id)
        .all()
    )
    return [build_user_response(u, db) for u in usuarios]


def obtener_usuario(id_user: int, empresa_id: int, db: Session) -> AppUser:
    """
    Obtiene un usuario por ID verificando que pertenezca
    a la empresa indicada.
    """
    user = db.query(AppUser).filter(AppUser.id_user == id_user).first()
    if not user:
        raise NotFoundError("Usuario no encontrado")
    if user.empresa_id != empresa_id:
        raise ForbiddenError("No tienes permiso para ver este usuario")
    return user


def actualizar_usuario(
    id_user: int,
    data: UserUpdate,
    current_user: AppUser,
    db: Session
) -> AppUser:
    """
    Actualiza los datos de un usuario.
    Solo actualiza los campos enviados (PATCH-style).
    Verifica unicidad del email si se cambia.
    """
    user = obtener_usuario(id_user, current_user.empresa_id, db)

    if data.email and data.email != user.email:
        if db.query(AppUser).filter(AppUser.email == data.email).first():
            raise BadRequestError("El email ya está en uso")
        user.email = data.email

    if data.nombre is not None:
        user.nombre = data.nombre
    if data.password is not None:
        user.password = hash_password(data.password)

    db.commit()
    db.refresh(user)
    return user


def eliminar_usuario(id_user: int, current_user: AppUser, db: Session) -> None:
    """
    Elimina un usuario.
    Un admin no puede eliminarse a sí mismo.
    """
    user = obtener_usuario(id_user, current_user.empresa_id, db)

    if user.id_user == current_user.id_user:
        raise BadRequestError("No puedes eliminar tu propia cuenta")

    db.delete(user)
    db.commit()