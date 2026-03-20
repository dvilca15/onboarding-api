from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppUser, Role, UserRole
from app.schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    # Verificar si el email ya existe
    existing = db.query(AppUser).filter(AppUser.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    # Crear usuario con contraseña hasheada
    new_user = AppUser(
        empresa_id  = data.empresa_id,
        nombre      = data.nombre,
        email       = data.email,
        password    = hash_password(data.password)
    )
    db.add(new_user)
    db.flush()  # Para obtener el id_user antes del commit

    # Asignar rol EMPLEADO por defecto
    role = db.query(Role).filter(Role.nombre == "EMPLEADO").first()
    if role:
        user_role = UserRole(id_user=new_user.id_user, id_role=role.id_role)
        db.add(user_role)

    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    # Buscar usuario por email
    user = db.query(AppUser).filter(AppUser.email == data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos"
        )

    # Verificar contraseña
    if not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos"
        )

    # Generar token JWT
    token = create_access_token(data={
        "sub":          str(user.id_user),
        "email":        user.email,
        "empresa_id":   user.empresa_id
    })

    return TokenResponse(
        access_token    = token,
        user_id         = user.id_user,
        nombre          = user.nombre,
        email           = user.email,
        empresa_id      = user.empresa_id
    )