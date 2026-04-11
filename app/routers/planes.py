from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import AppUser
from app.schemas import (
    PlanCreate, PlanUpdate, PlanResponse, PlanDetailResponse,
    UserResponse, BienvenidaUpdate, BienvenidaResponse
)
from app.dependencies import get_current_user, require_admin, get_user_roles
from app.services import plan_service
from app.models import EmployeeOnboarding

router = APIRouter(prefix="/planes", tags=["Planes de Onboarding"])


@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def crear_plan(
    data: PlanCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Crea un nuevo plan. Solo ADMIN_EMPRESA."""
    return plan_service.crear_plan(data, current_user.empresa_id, db)


@router.get("/", response_model=List[PlanResponse])
def listar_planes(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista planes de la empresa del usuario autenticado."""
    return plan_service.listar_planes(current_user.empresa_id, db)


@router.get("/{id_plan}", response_model=PlanDetailResponse)
def obtener_plan(
    id_plan: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene un plan con sus steps y tasks anidados."""
    return plan_service.obtener_plan_detalle(id_plan, current_user.empresa_id, db)


@router.put("/{id_plan}", response_model=PlanResponse)
def actualizar_plan(
    id_plan: int,
    data: PlanUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Actualiza un plan. Solo ADMIN_EMPRESA."""
    return plan_service.actualizar_plan(id_plan, data, current_user.empresa_id, db)


@router.delete("/{id_plan}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_plan(
    id_plan: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Elimina un plan. Solo ADMIN_EMPRESA."""
    plan_service.eliminar_plan(id_plan, current_user.empresa_id, db)

@router.get("/{id_plan}/empleados")
def listar_empleados_plan(
    id_plan: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Lista los empleados asignados a este plan con su onboarding."""
    return plan_service.listar_empleados_plan(id_plan, current_user.empresa_id, db)

# ── Bienvenida ────────────────────────────────────────────────
 
@router.put("/{id_plan}/bienvenida", response_model=PlanResponse)
def actualizar_bienvenida(
    id_plan: int,
    data: BienvenidaUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Actualiza el mensaje de bienvenida de un plan. Solo ADMIN_EMPRESA."""
    return plan_service.actualizar_bienvenida(id_plan, data.mensaje_bienvenida, current_user.empresa_id, db)
 
 
@router.get("/{id_plan}/bienvenida/{id_onboarding}", response_model=BienvenidaResponse)
def obtener_bienvenida(
    id_plan: int,
    id_onboarding: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna el mensaje de bienvenida del plan y si ya fue leído
    por el empleado en este onboarding específico.
    """
    return plan_service.obtener_bienvenida(id_plan, id_onboarding, current_user.empresa_id, db)

@router.get("/{id_plan}/tiene-empleados-activos")
def tiene_empleados_activos(
    id_plan: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Retorna cuántos empleados tienen un onboarding activo (no COMPLETADO)
    en este plan. Se usa para mostrar advertencia antes de eliminar.
    """
    count = (
        db.query(EmployeeOnboarding)
        .filter(
            EmployeeOnboarding.id_plan == id_plan,
            EmployeeOnboarding.estado != "COMPLETADO",
        )
        .count()
    )
    return {"count": count, "tiene_activos": count > 0}