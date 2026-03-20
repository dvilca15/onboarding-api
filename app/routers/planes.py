from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.database import get_db
from app.models import OnboardingPlan, OnboardingStep, Task
from app.schemas import PlanCreate, PlanUpdate, PlanResponse, PlanDetailResponse
from app.dependencies import get_current_user, require_admin
from app.models import AppUser

router = APIRouter(prefix="/planes", tags=["Planes de Onboarding"])


def verify_plan_belongs_to_empresa(plan: OnboardingPlan, empresa_id: int):
    """Verifica que el plan pertenece a la empresa del usuario autenticado."""
    if plan.id_empresa != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este plan"
        )


# ── POST /planes/ ─────────────────────────────────────────────
@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def crear_plan(
    data: PlanCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo plan de onboarding para la empresa del admin.
    Solo ADMIN_EMPRESA puede crear planes.
    """
    nuevo_plan = OnboardingPlan(
        id_empresa      = current_user.empresa_id,
        nombre          = data.nombre,
        descripcion     = data.descripcion,
        es_plantilla    = data.es_plantilla
    )
    db.add(nuevo_plan)
    db.commit()
    db.refresh(nuevo_plan)
    return nuevo_plan


# ── GET /planes/ ──────────────────────────────────────────────
@router.get("/", response_model=List[PlanResponse])
def listar_planes(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos los planes de la empresa del usuario autenticado.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    planes = (
        db.query(OnboardingPlan)
        .filter(OnboardingPlan.id_empresa == current_user.empresa_id)
        .order_by(OnboardingPlan.fecha_creacion.desc())
        .all()
    )
    return planes


# ── GET /planes/{id_plan} ─────────────────────────────────────
@router.get("/{id_plan}", response_model=PlanDetailResponse)
def obtener_plan(
    id_plan: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene un plan con todos sus steps y tasks anidados.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    plan = (
        db.query(OnboardingPlan)
        .options(
            joinedload(OnboardingPlan.steps)
            .joinedload(OnboardingStep.tasks)
        )
        .filter(OnboardingPlan.id_plan == id_plan)
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan no encontrado"
        )

    verify_plan_belongs_to_empresa(plan, current_user.empresa_id)

    # Ordenar steps y tasks por orden
    plan.steps = sorted(plan.steps, key=lambda s: s.orden)
    for step in plan.steps:
        step.tasks = sorted(step.tasks, key=lambda t: t.orden)

    return plan


# ── PUT /planes/{id_plan} ─────────────────────────────────────
@router.put("/{id_plan}", response_model=PlanResponse)
def actualizar_plan(
    id_plan: int,
    data: PlanUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Actualiza los datos de un plan.
    Solo ADMIN_EMPRESA puede actualizar planes.
    Solo se actualizan los campos enviados.
    """
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == id_plan).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan no encontrado"
        )

    verify_plan_belongs_to_empresa(plan, current_user.empresa_id)

    if data.nombre is not None:
        plan.nombre = data.nombre
    if data.descripcion is not None:
        plan.descripcion = data.descripcion
    if data.es_plantilla is not None:
        plan.es_plantilla = data.es_plantilla

    db.commit()
    db.refresh(plan)
    return plan


# ── DELETE /planes/{id_plan} ──────────────────────────────────
@router.delete("/{id_plan}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_plan(
    id_plan: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina un plan y todos sus steps y tasks en cascada.
    Solo ADMIN_EMPRESA puede eliminar planes.
    No se puede eliminar si tiene empleados asignados.
    """
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == id_plan).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan no encontrado"
        )

    verify_plan_belongs_to_empresa(plan, current_user.empresa_id)

    # Verificar que no tenga empleados asignados activos
    if plan.onboardings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un plan con empleados asignados"
        )

    db.delete(plan)
    db.commit()