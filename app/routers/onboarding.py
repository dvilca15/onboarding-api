from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import AppUser
from app.schemas import (
    AsignarPlanRequest, OnboardingResponse,
    OnboardingDetailResponse, CompletarTaskRequest
)
from app.dependencies import get_current_user, require_admin, get_user_roles
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["Employee Onboarding"])


@router.post("/asignar", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
def asignar_plan(
    data: AsignarPlanRequest,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Asigna un plan a un empleado. Solo ADMIN_EMPRESA."""
    return onboarding_service.asignar_plan(data, current_user, db)


@router.get("/", response_model=List[OnboardingResponse])
def listar_onboardings(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista onboardings según el rol."""
    roles = get_user_roles(current_user, db)
    return onboarding_service.listar_onboardings(current_user, roles, db)


@router.get("/{id_onboarding}/progreso", response_model=OnboardingDetailResponse)
def ver_progreso(
    id_onboarding: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle completo del progreso agrupado por step."""
    roles = get_user_roles(current_user, db)
    return onboarding_service.ver_progreso(id_onboarding, current_user, roles, db)


@router.post("/{id_onboarding}/tasks/{id_task}/completar", response_model=OnboardingResponse)
def completar_task(
    id_onboarding: int,
    id_task: int,
    data: CompletarTaskRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambia el estado de una task y recalcula el progreso."""
    roles = get_user_roles(current_user, db)
    return onboarding_service.completar_task(
        id_onboarding, id_task, data, current_user, roles, db
    )

@router.delete("/{id_onboarding}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_onboarding(
    id_onboarding: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Elimina un onboarding asignado. Solo ADMIN_EMPRESA."""
    roles = get_user_roles(current_user, db)
    onboarding_service.eliminar_onboarding(id_onboarding, current_user, roles, db)