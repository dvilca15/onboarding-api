from sqlalchemy.orm import Session, joinedload
from typing import List
from app.models import OnboardingPlan, OnboardingStep, Task, AppUser
from app.schemas import (
    PlanCreate, PlanUpdate, PlanResponse, PlanDetailResponse,
    StepCreate, StepUpdate, StepResponse,
    TaskCreate, TaskUpdate, TaskResponse,
)
from app.exceptions import NotFoundError, ForbiddenError, BadRequestError

TIPOS_VALIDOS = ["DOCUMENTO", "VIDEO", "FORMULARIO", "CONFIRMACION"]


# ── Helpers ───────────────────────────────────────────────────

def _get_plan(id_plan: int, empresa_id: int, db: Session) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == id_plan).first()
    if not plan:
        raise NotFoundError("Plan no encontrado")
    if plan.id_empresa != empresa_id:
        raise ForbiddenError("No tienes permiso para acceder a este plan")
    return plan


def _get_step(id_step: int, id_plan: int, empresa_id: int, db: Session) -> OnboardingStep:
    _get_plan(id_plan, empresa_id, db)
    step = db.query(OnboardingStep).filter(
        OnboardingStep.id_step == id_step,
        OnboardingStep.id_plan == id_plan
    ).first()
    if not step:
        raise NotFoundError("Step no encontrado")
    return step


def _get_step_by_id(id_step: int, empresa_id: int, db: Session) -> OnboardingStep:
    """Obtiene un step verificando que pertenezca a la empresa."""
    step = db.query(OnboardingStep).filter(OnboardingStep.id_step == id_step).first()
    if not step:
        raise NotFoundError("Step no encontrado")
    _get_plan(step.id_plan, empresa_id, db)
    return step


def _get_task(id_task: int, id_step: int, empresa_id: int, db: Session) -> Task:
    _get_step_by_id(id_step, empresa_id, db)
    task = db.query(Task).filter(
        Task.id_task == id_task,
        Task.id_step == id_step
    ).first()
    if not task:
        raise NotFoundError("Task no encontrada")
    return task


# ── Planes ────────────────────────────────────────────────────

def crear_plan(data: PlanCreate, empresa_id: int, db: Session) -> OnboardingPlan:
    plan = OnboardingPlan(
        id_empresa   = empresa_id,
        nombre       = data.nombre,
        descripcion  = data.descripcion,
        es_plantilla = data.es_plantilla,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def listar_planes(empresa_id: int, db: Session) -> List[OnboardingPlan]:
    return (
        db.query(OnboardingPlan)
        .filter(OnboardingPlan.id_empresa == empresa_id)
        .order_by(OnboardingPlan.fecha_creacion.desc())
        .all()
    )


def obtener_plan_detalle(id_plan: int, empresa_id: int, db: Session) -> OnboardingPlan:
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
        raise NotFoundError("Plan no encontrado")
    if plan.id_empresa != empresa_id:
        raise ForbiddenError("No tienes permiso para acceder a este plan")

    plan.steps = sorted(plan.steps, key=lambda s: s.orden)
    for step in plan.steps:
        step.tasks = sorted(step.tasks, key=lambda t: t.orden)
    return plan


def actualizar_plan(
    id_plan: int, data: PlanUpdate, empresa_id: int, db: Session
) -> OnboardingPlan:
    plan = _get_plan(id_plan, empresa_id, db)
    if data.nombre is not None:
        plan.nombre = data.nombre
    if data.descripcion is not None:
        plan.descripcion = data.descripcion
    if data.es_plantilla is not None:
        plan.es_plantilla = data.es_plantilla
    db.commit()
    db.refresh(plan)
    return plan


def eliminar_plan(id_plan: int, empresa_id: int, db: Session) -> None:
    plan = _get_plan(id_plan, empresa_id, db)
    if plan.onboardings:
        raise BadRequestError("No se puede eliminar un plan con empleados asignados")
    db.delete(plan)
    db.commit()


# ── Steps ─────────────────────────────────────────────────────

def crear_step(
    id_plan: int, data: StepCreate, empresa_id: int, db: Session
) -> OnboardingStep:
    _get_plan(id_plan, empresa_id, db)
    step = OnboardingStep(
        id_plan       = id_plan,
        titulo        = data.titulo,
        descripcion   = data.descripcion,
        orden         = data.orden,
        duracion_dias = data.duracion_dias,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def listar_steps(id_plan: int, empresa_id: int, db: Session) -> List[OnboardingStep]:
    _get_plan(id_plan, empresa_id, db)
    return (
        db.query(OnboardingStep)
        .filter(OnboardingStep.id_plan == id_plan)
        .order_by(OnboardingStep.orden)
        .all()
    )


def actualizar_step(
    id_step: int, id_plan: int, data: StepUpdate, empresa_id: int, db: Session
) -> OnboardingStep:
    step = _get_step(id_step, id_plan, empresa_id, db)
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


def eliminar_step(
    id_step: int, id_plan: int, empresa_id: int, db: Session
) -> None:
    step = _get_step(id_step, id_plan, empresa_id, db)
    db.delete(step)
    db.commit()


# ── Tasks ─────────────────────────────────────────────────────

def crear_task(
    id_step: int, data: TaskCreate, empresa_id: int, db: Session
) -> Task:
    _get_step_by_id(id_step, empresa_id, db)
    if data.tipo.upper() not in TIPOS_VALIDOS:
        raise BadRequestError(f"Tipo inválido. Valores permitidos: {TIPOS_VALIDOS}")
    task = Task(
        id_step     = id_step,
        titulo      = data.titulo,
        tipo        = data.tipo.upper(),
        obligatorio = data.obligatorio,
        orden       = data.orden,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def listar_tasks(id_step: int, empresa_id: int, db: Session) -> List[Task]:
    _get_step_by_id(id_step, empresa_id, db)
    return (
        db.query(Task)
        .filter(Task.id_step == id_step)
        .order_by(Task.orden)
        .all()
    )


def actualizar_task(
    id_task: int, id_step: int, data: TaskUpdate, empresa_id: int, db: Session
) -> Task:
    task = _get_task(id_task, id_step, empresa_id, db)
    if data.titulo is not None:
        task.titulo = data.titulo
    if data.tipo is not None:
        if data.tipo.upper() not in TIPOS_VALIDOS:
            raise BadRequestError(f"Tipo inválido. Valores permitidos: {TIPOS_VALIDOS}")
        task.tipo = data.tipo.upper()
    if data.obligatorio is not None:
        task.obligatorio = data.obligatorio
    if data.orden is not None:
        task.orden = data.orden
    db.commit()
    db.refresh(task)
    return task


def eliminar_task(
    id_task: int, id_step: int, empresa_id: int, db: Session
) -> None:
    task = _get_task(id_task, id_step, empresa_id, db)
    db.delete(task)
    db.commit()