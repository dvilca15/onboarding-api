from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import AppUser
from app.schemas import StepCreate, StepUpdate, StepResponse
from app.dependencies import get_current_user, require_admin
from app.services import plan_service

router = APIRouter(prefix="/planes/{id_plan}/steps", tags=["Steps de Onboarding"])


@router.post("/", response_model=StepResponse, status_code=status.HTTP_201_CREATED)
def crear_step(
    id_plan: int,
    data: StepCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Crea un step en un plan. Solo ADMIN_EMPRESA."""
    return plan_service.crear_step(id_plan, data, current_user.empresa_id, db)


@router.get("/", response_model=List[StepResponse])
def listar_steps(
    id_plan: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista los steps de un plan ordenados por campo orden."""
    return plan_service.listar_steps(id_plan, current_user.empresa_id, db)


@router.put("/{id_step}", response_model=StepResponse)
def actualizar_step(
    id_plan: int,
    id_step: int,
    data: StepUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Actualiza un step. Solo ADMIN_EMPRESA."""
    return plan_service.actualizar_step(id_step, id_plan, data, current_user.empresa_id, db)


@router.delete("/{id_step}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_step(
    id_plan: int,
    id_step: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Elimina un step y sus tasks en cascada. Solo ADMIN_EMPRESA."""
    plan_service.eliminar_step(id_step, id_plan, current_user.empresa_id, db)