from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Empresa, AppUser
from app.schemas import EmpresaCreate, EmpresaResponse
from app.dependencies import get_current_user, require_admin
from typing import List

router = APIRouter(prefix="/empresas", tags=["Empresas"])


@router.post("/", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
def crear_empresa(
    data: EmpresaCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(Empresa).filter(Empresa.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una empresa con ese email"
        )
    nueva = Empresa(
        nombre      = data.nombre,
        industria   = data.industria,
        email       = data.email
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


@router.get("/", response_model=List[EmpresaResponse])
def listar_empresas(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Solo devuelve la empresa del usuario autenticado."""
    return db.query(Empresa).filter(
        Empresa.id_empresa == current_user.empresa_id
    ).all()


@router.get("/{id_empresa}", response_model=EmpresaResponse)
def obtener_empresa(
    id_empresa: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if id_empresa != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver otra empresa"
        )
    empresa = db.query(Empresa).filter(Empresa.id_empresa == id_empresa).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    return empresa
