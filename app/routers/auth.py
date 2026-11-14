from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services import auth_service
from app.dependencies import require_admin
from app.models import AppUser

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Crea un empleado (rol EMPLEADO). Solo ADMIN_EMPRESA, y siempre dentro
    de la empresa del admin (el empresa_id del body se ignora).
    """
    data.empresa_id = current_user.empresa_id
    return auth_service.registrar_usuario(data, db)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Valida credenciales y devuelve token JWT."""
    return auth_service.login_usuario(data.email, data.password, db)