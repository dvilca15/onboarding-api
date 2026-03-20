from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import OnboardingPlan, OnboardingStep, AppUser
from app.schemas import StepCreate, StepUpdate, StepResponse
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/planes/{id_plan}/steps", tags=["Steps de Onboarding"])


def get_plan_or_404(id_plan: int, empresa_id: int, db: Session) -> OnboardingPlan:
    """Obtiene el plan y verifica que pertenece a la empresa."""
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == id_plan).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan no encontrado"
        )
    if plan.id_empresa != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este plan"
        )
    return plan


# ── POST /planes/{id_plan}/steps/ ────────────────────────────
@router.post("/", response_model=StepResponse, status_code=status.HTTP_201_CREATED)
def crear_step(
    id_plan: int,
    data: StepCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo step dentro de un plan.
    Solo ADMIN_EMPRESA puede crear steps.
    """
    get_plan_or_404(id_plan, current_user.empresa_id, db)

    nuevo_step = OnboardingStep(
        id_plan         = id_plan,
        titulo          = data.titulo,
        descripcion     = data.descripcion,
        orden           = data.orden,
        duracion_dias   = data.duracion_dias
    )
    db.add(nuevo_step)
    db.commit()
    db.refresh(nuevo_step)
    return nuevo_step


# ── GET /planes/{id_plan}/steps/ ─────────────────────────────
@router.get("/", response_model=List[StepResponse])
def listar_steps(
    id_plan: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos los steps de un plan ordenados por campo orden.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    get_plan_or_404(id_plan, current_user.empresa_id, db)

    steps = (
        db.query(OnboardingStep)
        .filter(OnboardingStep.id_plan == id_plan)
        .order_by(OnboardingStep.orden)
        .all()
    )
    return steps


# ── GET /planes/{id_plan}/steps/{id_step} ────────────────────
@router.get("/{id_step}", response_model=StepResponse)
def obtener_step(
    id_plan: int,
    id_step: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene un step específico con sus tasks.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    get_plan_or_404(id_plan, current_user.empresa_id, db)

    step = db.query(OnboardingStep).filter(
        OnboardingStep.id_step == id_step,
        OnboardingStep.id_plan == id_plan
    ).first()

    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step no encontrado"
        )

    step.tasks = sorted(step.tasks, key=lambda t: t.orden)
    return step


# ── PUT /planes/{id_plan}/steps/{id_step} ────────────────────
@router.put("/{id_step}", response_model=StepResponse)
def actualizar_step(
    id_plan: int,
    id_step: int,
    data: StepUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Actualiza un step.
    Solo ADMIN_EMPRESA puede actualizar steps.
    Solo se actualizan los campos enviados.
    """
    get_plan_or_404(id_plan, current_user.empresa_id, db)

    step = db.query(OnboardingStep).filter(
        OnboardingStep.id_step == id_step,
        OnboardingStep.id_plan == id_plan
    ).first()

    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step no encontrado"
        )

    if data.titulo is not None:
        step.titulo = data.titulo
    if data.descripcion is not None:
        step.descripcion = data.descripcion
    if data.orden is not None:
        step.orden = data.orden
    if data.duracion_dias is not None:
        step.duracion_dias = data.duracion_dias

    db.commit()
    db.refresh(step)
    return step


# ── DELETE /planes/{id_plan}/steps/{id_step} ─────────────────
@router.delete("/{id_step}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_step(
    id_plan: int,
    id_step: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina un step y todas sus tasks en cascada.
    Solo ADMIN_EMPRESA puede eliminar steps.
    """
    get_plan_or_404(id_plan, current_user.empresa_id, db)

    step = db.query(OnboardingStep).filter(
        OnboardingStep.id_step == id_step,
        OnboardingStep.id_plan == id_plan
    ).first()

    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step no encontrado"
        )

    db.delete(step)
    db.commit()