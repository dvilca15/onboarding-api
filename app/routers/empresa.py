from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Empresa
from app.schemas import EmpresaCreate, EmpresaResponse
from typing import List

router = APIRouter(prefix="/empresas", tags=["Empresas"])


@router.post("/", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
def crear_empresa(data: EmpresaCreate, db: Session = Depends(get_db)):
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
def listar_empresas(db: Session = Depends(get_db)):
    return db.query(Empresa).all()


@router.get("/{id_empresa}", response_model=EmpresaResponse)
def obtener_empresa(id_empresa: int, db: Session = Depends(get_db)):
    empresa = db.query(Empresa).filter(Empresa.id_empresa == id_empresa).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    return empresa