from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, date
from decimal import Decimal
from app.database import get_db
from app.models import (
    AppUser, OnboardingPlan, OnboardingStep,
    Task, EmployeeOnboarding, TaskProgress
)
from app.schemas import (
    AsignarPlanRequest, OnboardingResponse,
    OnboardingDetailResponse, TaskProgressResponse,
    CompletarTaskRequest
)
from app.dependencies import get_current_user, require_admin, get_user_roles

router = APIRouter(prefix="/onboarding", tags=["Employee Onboarding"])


def calcular_progreso(id_employee_onboarding: int, db: Session) -> Decimal:
    """
    Calcula el porcentaje de progreso basado en tasks obligatorias completadas.
    Fórmula: (tasks obligatorias completadas / total tasks obligatorias) * 100
    """
    onboarding = db.query(EmployeeOnboarding).filter(
        EmployeeOnboarding.id_employee_onboarding == id_employee_onboarding
    ).first()

    if not onboarding:
        return Decimal("0.00")

    total_obligatorias = (
        db.query(Task)
        .join(OnboardingStep, OnboardingStep.id_step == Task.id_step)
        .filter(
            OnboardingStep.id_plan == onboarding.id_plan,
            Task.obligatorio == True
        )
        .count()
    )

    if total_obligatorias == 0:
        return Decimal("100.00")

    completadas = (
        db.query(TaskProgress)
        .join(Task, Task.id_task == TaskProgress.id_task)
        .filter(
            TaskProgress.id_employee_onboarding == id_employee_onboarding,
            TaskProgress.estado == "COMPLETADO",
            Task.obligatorio == True
        )
        .count()
    )

    progreso = Decimal(str(round((completadas / total_obligatorias) * 100, 2)))
    return progreso


# ── POST /onboarding/asignar ──────────────────────────────────
@router.post("/asignar", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
def asignar_plan(
    data: AsignarPlanRequest,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Asigna un plan de onboarding a un empleado.
    Solo ADMIN_EMPRESA puede asignar planes.
    Crea automáticamente los registros de TaskProgress para cada task del plan.
    """
    # Verificar que el empleado existe y pertenece a la misma empresa
    empleado = db.query(AppUser).filter(AppUser.id_user == data.id_user).first()
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    if empleado.empresa_id != current_user.empresa_id:
        raise HTTPException(status_code=403, detail="El empleado no pertenece a tu empresa")

    # Verificar que el plan existe y pertenece a la empresa
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == data.id_plan).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    if plan.id_empresa != current_user.empresa_id:
        raise HTTPException(status_code=403, detail="El plan no pertenece a tu empresa")

    # Verificar que el empleado no tenga ya ese plan asignado
    existente = db.query(EmployeeOnboarding).filter(
        EmployeeOnboarding.id_user == data.id_user,
        EmployeeOnboarding.id_plan == data.id_plan
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="El empleado ya tiene este plan asignado")

    fecha_inicio = data.fecha_inicio or datetime.now().date()

    nuevo_onboarding = EmployeeOnboarding(
        id_plan         = data.id_plan,
        id_user         = data.id_user,
        estado          = "EN_PROGRESO" if data.fecha_inicio else "PENDIENTE",
        progreso        = Decimal("0.00"),
        fecha_inicio    = fecha_inicio
    )
    db.add(nuevo_onboarding)
    db.flush()

    # Crear automáticamente TaskProgress para cada task del plan
    tasks = (
        db.query(Task)
        .join(OnboardingStep, OnboardingStep.id_step == Task.id_step)
        .filter(OnboardingStep.id_plan == data.id_plan)
        .all()
    )
    for task in tasks:
        task_progress = TaskProgress(
            id_employee_onboarding  = nuevo_onboarding.id_employee_onboarding,
            id_task                 = task.id_task,
            estado                  = "PENDIENTE"
        )
        db.add(task_progress)

    db.commit()
    db.refresh(nuevo_onboarding)
    return nuevo_onboarding


# ── GET /onboarding/ ──────────────────────────────────────────
@router.get("/", response_model=List[OnboardingResponse])
def listar_onboardings(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista onboardings según el rol:
    - ADMIN_EMPRESA: ve todos los onboardings de su empresa
    - EMPLEADO: ve solo sus propios onboardings
    """
    roles = get_user_roles(current_user, db)

    if "ADMIN_EMPRESA" in roles:
        onboardings = (
            db.query(EmployeeOnboarding)
            .join(AppUser, AppUser.id_user == EmployeeOnboarding.id_user)
            .filter(AppUser.empresa_id == current_user.empresa_id)
            .order_by(EmployeeOnboarding.fecha_creacion.desc())
            .all()
        )
    else:
        onboardings = (
            db.query(EmployeeOnboarding)
            .filter(EmployeeOnboarding.id_user == current_user.id_user)
            .order_by(EmployeeOnboarding.fecha_creacion.desc())
            .all()
        )

    return onboardings


# ── GET /onboarding/{id}/progreso ─────────────────────────────
@router.get("/{id_onboarding}/progreso", response_model=OnboardingDetailResponse)
def ver_progreso(
    id_onboarding: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el detalle completo del progreso de un onboarding.
    Incluye el estado de cada task.
    - ADMIN_EMPRESA: puede ver el progreso de cualquier empleado de su empresa.
    - EMPLEADO: solo puede ver su propio progreso.
    """
    onboarding = (
        db.query(EmployeeOnboarding)
        .options(
            joinedload(EmployeeOnboarding.task_progresos)
            .joinedload(TaskProgress.task)
        )
        .filter(EmployeeOnboarding.id_employee_onboarding == id_onboarding)
        .first()
    )

    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding no encontrado")

    # Verificar permisos
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles and onboarding.id_user != current_user.id_user:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este onboarding")

    empleado = db.query(AppUser).filter(AppUser.id_user == onboarding.id_user).first()
    if empleado.empresa_id != current_user.empresa_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este onboarding")

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == onboarding.id_plan).first()

    return OnboardingDetailResponse(
        id_employee_onboarding  = onboarding.id_employee_onboarding,
        id_plan                 = onboarding.id_plan,
        id_user                 = onboarding.id_user,
        estado                  = onboarding.estado,
        progreso                = onboarding.progreso,
        fecha_inicio            = onboarding.fecha_inicio,
        fecha_fin               = onboarding.fecha_fin,
        fecha_creacion          = onboarding.fecha_creacion,
        nombre_empleado         = empleado.nombre,
        nombre_plan             = plan.nombre if plan else "",
        task_progresses         = onboarding.task_progresos
    )


# ── POST /onboarding/{id}/tasks/{id_task}/completar ───────────
@router.post("/{id_onboarding}/tasks/{id_task}/completar", response_model=OnboardingResponse)
def completar_task(
    id_onboarding: int,
    id_task: int,
    data: CompletarTaskRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marca una task como completada (o cambia su estado).
    - EMPLEADO: solo puede completar tasks de su propio onboarding.
    - ADMIN_EMPRESA: puede actualizar cualquier task de su empresa.
    Estados válidos: PENDIENTE, EN_PROGRESO, COMPLETADO, OMITIDO
    """
    ESTADOS_VALIDOS = ["PENDIENTE", "EN_PROGRESO", "COMPLETADO", "OMITIDO"]
    if data.estado.upper() not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Valores permitidos: {ESTADOS_VALIDOS}"
        )

    onboarding = db.query(EmployeeOnboarding).filter(
        EmployeeOnboarding.id_employee_onboarding == id_onboarding
    ).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding no encontrado")

    # Verificar permisos
    roles = get_user_roles(current_user, db)
    if "ADMIN_EMPRESA" not in roles and onboarding.id_user != current_user.id_user:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar este onboarding")

    # Obtener el task_progress
    task_progress = db.query(TaskProgress).filter(
        TaskProgress.id_employee_onboarding == id_onboarding,
        TaskProgress.id_task == id_task
    ).first()
    if not task_progress:
        raise HTTPException(status_code=404, detail="Task no encontrada en este onboarding")

    # Actualizar estado de la task
    task_progress.estado = data.estado.upper()
    if data.estado.upper() == "COMPLETADO":
        task_progress.fecha_completada = datetime.now()
    else:
        task_progress.fecha_completada = None

    # Recalcular progreso
    db.flush()
    nuevo_progreso = calcular_progreso(id_onboarding, db)
    onboarding.progreso = nuevo_progreso

    # Actualizar estado del onboarding según progreso
    if nuevo_progreso >= 100:
        onboarding.estado = "COMPLETADO"
        # ✅ FIX: fecha_fin debe ser >= fecha_inicio
        fecha_hoy = datetime.now().date()
        onboarding.fecha_fin = max(fecha_hoy, onboarding.fecha_inicio)
    elif nuevo_progreso > 0:
        onboarding.estado = "EN_PROGRESO"
        onboarding.fecha_fin = None

    db.commit()
    db.refresh(onboarding)
    return onboarding