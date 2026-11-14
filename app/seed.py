"""Script de arranque: crea los roles, una empresa y su administrador.

Uso (desde la carpeta onboarding-api, con el entorno virtual activo):

    python -m app.seed                       # pregunta los datos
    python -m app.seed --empresa "Mi Pyme" --industria Servicios \
        --admin-nombre "Ana Pérez" --admin-email ana@mipyme.com

La contraseña se pide por teclado (no se guarda en el historial).
Es seguro ejecutarlo varias veces: no duplica roles ni empresas.
Para añadir otro admin a una empresa existente usa --empresa-id.
"""
import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import AppUser, Empresa, Role, UserRole
from app.security import hash_password

ROLES = {
    "ADMIN_EMPRESA": "Administrador de la empresa",
    "EMPLEADO": "Empleado",
}


def _pedir(texto: str, valor: str | None, secreto: bool = False) -> str:
    if valor:
        return valor.strip()
    leer = getpass.getpass if secreto else input
    return leer(f"{texto}: ").strip()


def _validar_password(pw: str) -> str | None:
    if len(pw) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        return "La contraseña debe combinar letras y números."
    return None


def asegurar_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for nombre, descripcion in ROLES.items():
        rol = db.query(Role).filter(Role.nombre == nombre).first()
        if not rol:
            rol = Role(nombre=nombre, descripcion=descripcion)
            db.add(rol)
            db.flush()
            print(f"  + Rol creado: {nombre}")
        roles[nombre] = rol
    return roles


def crear_admin(
    db: Session,
    *,
    empresa_nombre: str | None,
    industria: str | None,
    empresa_id: int | None,
    admin_nombre: str,
    admin_email: str,
    password: str,
) -> tuple[Empresa, AppUser]:
    roles = asegurar_roles(db)

    if db.query(AppUser).filter(AppUser.email == admin_email).first():
        raise ValueError(f"Ya existe un usuario con el email {admin_email}.")

    if empresa_id is not None:
        empresa = db.query(Empresa).filter(Empresa.id_empresa == empresa_id).first()
        if not empresa:
            raise ValueError(f"No existe la empresa con id {empresa_id}.")
    else:
        if not empresa_nombre:
            raise ValueError("Falta el nombre de la empresa.")
        # El email de la empresa es único: usamos el del administrador.
        empresa = db.query(Empresa).filter(Empresa.email == admin_email).first()
        if empresa:
            print(f"  = La empresa '{empresa.nombre}' ya existía, se reutiliza.")
        else:
            empresa = Empresa(
                nombre=empresa_nombre, industria=industria or None, email=admin_email
            )
            db.add(empresa)
            db.flush()
            print(f"  + Empresa creada: {empresa.nombre} (id {empresa.id_empresa})")

    admin = AppUser(
        empresa_id=empresa.id_empresa,
        nombre=admin_nombre,
        email=admin_email,
        password=hash_password(password),
        password_changed=True,  # el admin elige su contraseña aquí
    )
    db.add(admin)
    db.flush()
    db.add(UserRole(id_user=admin.id_user, id_role=roles["ADMIN_EMPRESA"].id_role))
    print(f"  + Administrador creado: {admin.nombre} <{admin.email}>")
    db.commit()
    return empresa, admin


def main() -> int:
    ap = argparse.ArgumentParser(description="Crea empresa + administrador inicial.")
    ap.add_argument("--empresa", help="Nombre de la empresa nueva")
    ap.add_argument("--industria", help="Industria (opcional)")
    ap.add_argument("--empresa-id", type=int, help="Añadir el admin a una empresa existente")
    ap.add_argument("--admin-nombre", help="Nombre del administrador")
    ap.add_argument("--admin-email", help="Email del administrador")
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)

    print("== Alta de empresa y administrador ==")
    empresa_nombre = None
    if args.empresa_id is None:
        empresa_nombre = _pedir("Nombre de la empresa", args.empresa)
    admin_nombre = _pedir("Nombre del administrador", args.admin_nombre)
    admin_email = _pedir("Email del administrador", args.admin_email).lower()
    if "@" not in admin_email:
        print("Error: email inválido.")
        return 1

    password = _pedir("Contraseña (mín. 8, letras y números)", None, secreto=True)
    error = _validar_password(password)
    if error:
        print(f"Error: {error}")
        return 1
    if password != getpass.getpass("Repite la contraseña: "):
        print("Error: las contraseñas no coinciden.")
        return 1

    db = SessionLocal()
    try:
        empresa, admin = crear_admin(
            db,
            empresa_nombre=empresa_nombre,
            industria=args.industria,
            empresa_id=args.empresa_id,
            admin_nombre=admin_nombre,
            admin_email=admin_email,
            password=password,
        )
    except ValueError as e:
        db.rollback()
        print(f"Error: {e}")
        return 1
    finally:
        db.close()

    print(f"\nListo. Entra a la app con {admin_email} y elige 'Administrador'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
