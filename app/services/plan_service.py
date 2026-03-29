from sqlalchemy.orm import Session, joinedload
from typing import List
from app.models import OnboardingPlan, OnboardingStep, Task, AppUser, EmployeeOnboarding
from app.schemas import (
    PlanCreate, PlanUpdate, PlanResponse, PlanDetailResponse,
    StepCreate, StepUpdate, StepResponse,
    TaskCreate, TaskUpdate, TaskResponse,
)
from app.exceptions import NotFoundError, ForbiddenError, BadRequestError
from app.models import Task, TaskProgress, EmployeeOnboarding, OnboardingStep
from app.schemas import BienvenidaResponse
from app.exceptions import NotFoundError, ForbiddenError
from datetime import datetime

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

def listar_empleados_plan(id_plan: int, empresa_id: int, db: Session) -> list:
    _get_plan(id_plan, empresa_id, db)
    onboardings = (
        db.query(EmployeeOnboarding)
        .filter(EmployeeOnboarding.id_plan == id_plan)
        .all()
    )
    resultado = []
    for o in onboardings:
        user = db.query(AppUser).filter(AppUser.id_user == o.id_user).first()
        if user:
            resultado.append({
                "id_employee_onboarding": o.id_employee_onboarding,
                "id_user": user.id_user,
                "nombre": user.nombre,
                "email": user.email,
                "estado": o.estado,
                "progreso": float(o.progreso),
            })
    return resultado

def actualizar_bienvenida(
    id_plan: int,
    mensaje: str | None,
    empresa_id: int,
    db
) -> object:
    """
    Actualiza el mensaje de bienvenida del plan.
    Si mensaje es None, lo elimina.
    Si el plan tiene onboardings activos, también crea/elimina
    la task BIENVENIDA en sus TaskProgress.
    """
    from app.models import OnboardingPlan
    plan = db.query(OnboardingPlan).filter(
        OnboardingPlan.id_plan == id_plan,
        OnboardingPlan.id_empresa == empresa_id
    ).first()
    if not plan:
        raise NotFoundError("Plan no encontrado")
 
    plan.mensaje_bienvenida = mensaje
 
    if mensaje:
        # Buscar si ya existe un step de bienvenida
        step_bienvenida = db.query(OnboardingStep).filter(
            OnboardingStep.id_plan == id_plan,
            OnboardingStep.titulo == "__BIENVENIDA__"
        ).first()
 
        if not step_bienvenida:
            # Crear step oculto de bienvenida con orden 0
            step_bienvenida = OnboardingStep(
                id_plan=id_plan,
                titulo="__BIENVENIDA__",
                orden=999,
                duracion_dias=None,
            )
            db.add(step_bienvenida)
            db.flush()
 
        # Buscar si ya existe la task de bienvenida
        task_bienvenida = db.query(Task).filter(
            Task.id_step == step_bienvenida.id_step,
            Task.tipo == "BIENVENIDA"
        ).first()
 
        if not task_bienvenida:
            task_bienvenida = Task(
                id_step=step_bienvenida.id_step,
                titulo="Leer mensaje de bienvenida",
                tipo="BIENVENIDA",
                obligatorio=True,
                orden=1,
            )
            db.add(task_bienvenida)
            db.flush()
 
            # Crear TaskProgress PENDIENTE para todos los onboardings activos del plan
            onboardings_activos = db.query(EmployeeOnboarding).filter(
                EmployeeOnboarding.id_plan == id_plan,
                EmployeeOnboarding.estado != "COMPLETADO"
            ).all()
            for ob in onboardings_activos:
                existe = db.query(TaskProgress).filter(
                    TaskProgress.id_employee_onboarding == ob.id_employee_onboarding,
                    TaskProgress.id_task == task_bienvenida.id_task
                ).first()
                if not existe:
                    db.add(TaskProgress(
                        id_employee_onboarding=ob.id_employee_onboarding,
                        id_task=task_bienvenida.id_task,
                        estado="PENDIENTE",
                    ))
    else:
        # Si se borra el mensaje, eliminar la task BIENVENIDA
        step_bienvenida = db.query(OnboardingStep).filter(
            OnboardingStep.id_plan == id_plan,
            OnboardingStep.titulo == "__BIENVENIDA__"
        ).first()
        if step_bienvenida:
            db.delete(step_bienvenida)  # cascade elimina tasks y task_progress
 
    db.commit()
    db.refresh(plan)
    return plan
 
 
def obtener_bienvenida(
    id_plan: int,
    id_onboarding: int,
    empresa_id: int,
    db
) -> BienvenidaResponse:
    """
    Retorna el mensaje de bienvenida y si ya fue leído
    por el empleado en este onboarding.
    """
    from app.models import OnboardingPlan
    plan = db.query(OnboardingPlan).filter(
        OnboardingPlan.id_plan == id_plan,
        OnboardingPlan.id_empresa == empresa_id
    ).first()
    if not plan:
        raise NotFoundError("Plan no encontrado")
 
    if not plan.mensaje_bienvenida:
        return BienvenidaResponse(
            tiene_bienvenida=False,
            mensaje=None,
            id_task=None,
            ya_leida=True,
        )
 
    # Buscar la task BIENVENIDA
    task_bienvenida = (
        db.query(Task)
        .join(OnboardingStep, OnboardingStep.id_step == Task.id_step)
        .filter(
            OnboardingStep.id_plan == id_plan,
            Task.tipo == "BIENVENIDA"
        )
        .first()
    )
    if not task_bienvenida:
        return BienvenidaResponse(
            tiene_bienvenida=True,
            mensaje=plan.mensaje_bienvenida,
            id_task=None,
            ya_leida=True,
        )
 
    # Ver si ya la completó
    tp = db.query(TaskProgress).filter(
        TaskProgress.id_employee_onboarding == id_onboarding,
        TaskProgress.id_task == task_bienvenida.id_task
    ).first()
 
    ya_leida = tp.estado == "COMPLETADO" if tp else False
 
    return BienvenidaResponse(
        tiene_bienvenida=True,
        mensaje=plan.mensaje_bienvenida,
        id_task=task_bienvenida.id_task,
        ya_leida=ya_leida,
    )