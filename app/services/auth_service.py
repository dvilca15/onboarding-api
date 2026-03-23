from sqlalchemy.orm import Session
from app.models import AppUser, Role, UserRole
from app.schemas import RegisterRequest
from app.security import hash_password, verify_password, create_access_token
from app.exceptions import BadRequestError, UnauthorizedError


def registrar_usuario(data: RegisterRequest, db: Session) -> AppUser:
    """
    Registra un nuevo usuario en la BD.
    - Verifica que el email no esté en uso.
    - Hashea la contraseña.
    - Asigna rol EMPLEADO por defecto.
    """
    if db.query(AppUser).filter(AppUser.email == data.email).first():
        raise BadRequestError("El email ya está registrado")

    nuevo_usuario = AppUser(
        empresa_id  = data.empresa_id,
        nombre      = data.nombre,
        email       = data.email,
        password    = hash_password(data.password)
    )
    db.add(nuevo_usuario)
    db.flush()

    role = db.query(Role).filter(Role.nombre == "EMPLEADO").first()
    if role:
        db.add(UserRole(id_user=nuevo_usuario.id_user, id_role=role.id_role))

    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


def login_usuario(email: str, password: str, db: Session) -> dict:
    """
    Valida las credenciales y devuelve el token JWT junto
    con los datos básicos del usuario.
    """
    usuario = db.query(AppUser).filter(AppUser.email == email).first()
    if not usuario or not verify_password(password, usuario.password):
        raise UnauthorizedError("Email o contraseña incorrectos")

    token = create_access_token(data={
        "sub":        str(usuario.id_user),
        "email":      usuario.email,
        "empresa_id": usuario.empresa_id,
    })

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      usuario.id_user,
        "nombre":       usuario.nombre,
        "email":        usuario.email,
        "empresa_id":   usuario.empresa_id,
    }