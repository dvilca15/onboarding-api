from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, date
from decimal import Decimal
from app.models import (
    AppUser, OnboardingPlan, OnboardingStep,
    Task, EmployeeOnboarding, TaskProgress, TaskRespuesta
)
from app.schemas import (
    AsignarPlanRequest, OnboardingResponse,
    OnboardingDetailResponse, StepConProgreso,
    TaskProgressConDetalle, RespuestaDetalle,
    CompletarTaskRequest
)
from app.exceptions import NotFoundError, ForbiddenError, BadRequestError


# ── Helpers ───────────────────────────────────────────────────

def calcular_progreso(id_employee_onboarding: int, db: Session) -> Decimal:
    onboarding = db.query(EmployeeOnboarding).filter(
        EmployeeOnboarding.id_employee_onboarding == id_employee_onboarding
    ).first()
    if not onboarding:
        return Decimal("0.00")

    total = (
        db.query(Task)
        .join(OnboardingStep, OnboardingStep.id_step == Task.id_step)
        .filter(
            OnboardingStep.id_plan == onboarding.id_plan,
            Task.obligatorio == True
        )
        .count()
    )
    if total == 0:
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
    return Decimal(str(round((completadas / total) * 100, 2)))


def _get_onboarding(id_onboarding: int, db: Session) -> EmployeeOnboarding:
    onboarding = db.query(EmployeeOnboarding).filter(
        EmployeeOnboarding.id_employee_onboarding == id_onboarding
    ).first()
    if not onboarding:
        raise NotFoundError("Onboarding no encontrado")
    return onboarding


def _verificar_acceso(
    onboarding: EmployeeOnboarding,
    current_user: AppUser,
    roles: List[str],
    db: Session
) -> None:
    if "ADMIN_EMPRESA" not in roles and onboarding.id_user != current_user.id_user:
        raise ForbiddenError("No tienes permiso para acceder a este onboarding")
    empleado = db.query(AppUser).filter(AppUser.id_user == onboarding.id_user).first()
    if not empleado or empleado.empresa_id != current_user.empresa_id:
        raise ForbiddenError("No tienes permiso para acceder a este onboarding")


def _build_onboarding_response(
    onboarding: EmployeeOnboarding,
    nombre_empleado: str,
    nombre_plan: str
) -> OnboardingResponse:
    return OnboardingResponse(
        id_employee_onboarding = onboarding.id_employee_onboarding,
        id_plan                = onboarding.id_plan,
        id_user                = onboarding.id_user,
        estado                 = onboarding.estado,
        progreso               = onboarding.progreso,
        fecha_inicio           = onboarding.fecha_inicio,
        fecha_fin              = onboarding.fecha_fin,
        fecha_creacion         = onboarding.fecha_creacion,
        nombre_empleado        = nombre_empleado,
        nombre_plan            = nombre_plan,
    )


# ── Servicios ─────────────────────────────────────────────────

def asignar_plan(
    data: AsignarPlanRequest,
    current_user: AppUser,
    db: Session
) -> OnboardingResponse:
    empleado = db.query(AppUser).filter(AppUser.id_user == data.id_user).first()
    if not empleado:
        raise NotFoundError("Empleado no encontrado")
    if empleado.empresa_id != current_user.empresa_id:
        raise ForbiddenError("El empleado no pertenece a tu empresa")

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == data.id_plan).first()
    if not plan:
        raise NotFoundError("Plan no encontrado")
    if plan.id_empresa != current_user.empresa_id:
        raise ForbiddenError("El plan no pertenece a tu empresa")

    existente = db.query(EmployeeOnboarding).filter(
        EmployeeOnboarding.id_user == data.id_user,
        EmployeeOnboarding.id_plan == data.id_plan
    ).first()
    if existente:
        raise BadRequestError("El empleado ya tiene este plan asignado")

    fecha_inicio = data.fecha_inicio or datetime.now().date()
    nuevo = EmployeeOnboarding(
        id_plan      = data.id_plan,
        id_user      = data.id_user,
        estado       = "EN_PROGRESO" if data.fecha_inicio else "PENDIENTE",
        progreso     = Decimal("0.00"),
        fecha_inicio = fecha_inicio,
    )
    db.add(nuevo)
    db.flush()

    tasks = (
        db.query(Task)
        .join(OnboardingStep, OnboardingStep.id_step == Task.id_step)
        .filter(OnboardingStep.id_plan == data.id_plan)
        .all()
    )
    for task in tasks:
        db.add(TaskProgress(
            id_employee_onboarding = nuevo.id_employee_onboarding,
            id_task                = task.id_task,
            estado                 = "PENDIENTE",
        ))

    db.commit()
    db.refresh(nuevo)
    return _build_onboarding_response(nuevo, empleado.nombre, plan.nombre)


def listar_onboardings(
    current_user: AppUser,
    roles: List[str],
    db: Session
) -> List[OnboardingResponse]:
    query = (
        db.query(EmployeeOnboarding, AppUser.nombre, OnboardingPlan.nombre)
        .join(AppUser, AppUser.id_user == EmployeeOnboarding.id_user)
        .join(OnboardingPlan, OnboardingPlan.id_plan == EmployeeOnboarding.id_plan)
    )

    if "ADMIN_EMPRESA" in roles:
        query = query.filter(AppUser.empresa_id == current_user.empresa_id)
    else:
        query = query.filter(EmployeeOnboarding.id_user == current_user.id_user)

    rows = query.order_by(EmployeeOnboarding.fecha_creacion.desc()).all()
    return [
        _build_onboarding_response(onboarding, nombre_empleado, nombre_plan)
        for onboarding, nombre_empleado, nombre_plan in rows
    ]


def ver_progreso(
    id_onboarding: int,
    current_user: AppUser,
    roles: List[str],
    db: Session
) -> OnboardingDetailResponse:
    """
    Retorna el detalle completo del onboarding agrupado por step.
    ── Mejora A: incluye respuestas de formulario por task.
    ── Mejora B: incluye url_contenido para tareas ENTREGA.
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
        raise NotFoundError("Onboarding no encontrado")

    _verificar_acceso(onboarding, current_user, roles, db)

    empleado = db.query(AppUser).filter(AppUser.id_user == onboarding.id_user).first()
    plan = (
        db.query(OnboardingPlan)
        .options(joinedload(OnboardingPlan.steps).joinedload(OnboardingStep.tasks))
        .filter(OnboardingPlan.id_plan == onboarding.id_plan)
        .first()
    )

    # ── Mejora A: cargar todas las respuestas del onboarding de una vez ──
    # Evita N+1: una sola query para todas las respuestas
    task_progress_ids = [tp.id_task_progress for tp in onboarding.task_progresos]
    respuestas_por_progress: dict[int, list[RespuestaDetalle]] = {}
    if task_progress_ids:
        todas_respuestas = (
            db.query(TaskRespuesta)
            .filter(TaskRespuesta.id_task_progress.in_(task_progress_ids))
            .order_by(TaskRespuesta.fecha_creacion)
            .all()
        )
        for r in todas_respuestas:
            if r.id_task_progress not in respuestas_por_progress:
                respuestas_por_progress[r.id_task_progress] = []
            respuestas_por_progress[r.id_task_progress].append(
                RespuestaDetalle(
                    id_respuesta   = r.id_respuesta,
                    pregunta       = r.pregunta,
                    respuesta      = r.respuesta,
                    fecha_creacion = r.fecha_creacion,
                )
            )

    steps_con_progreso = []
    if plan:
        progreso_por_task = {tp.id_task: tp for tp in onboarding.task_progresos}
        for step in sorted(plan.steps, key=lambda s: s.orden):
            tasks_del_step = []
            completadas = 0
            for task in sorted(step.tasks, key=lambda t: t.orden):
                tp = progreso_por_task.get(task.id_task)
                estado_task = tp.estado if tp else "PENDIENTE"
                if estado_task == "COMPLETADO":
                    completadas += 1

                # ── Mejora A: incluir respuestas si la task es FORMULARIO ──
                respuestas = []
                if tp and task.tipo == "FORMULARIO":
                    respuestas = respuestas_por_progress.get(
                        tp.id_task_progress, []
                    )

                tasks_del_step.append(TaskProgressConDetalle(
                    id_task_progress = tp.id_task_progress if tp else 0,
                    id_task          = task.id_task,
                    id_step          = step.id_step,
                    estado           = estado_task,
                    fecha_completada = tp.fecha_completada if tp else None,
                    titulo           = task.titulo,
                    tipo             = task.tipo,
                    obligatorio      = task.obligatorio,
                    orden            = task.orden,
                    url_contenido    = task.url_contenido,
                    descripcion      = task.descripcion,
                    respuestas       = respuestas,
                ))
            steps_con_progreso.append(StepConProgreso(
                id_step       = step.id_step,
                titulo        = step.titulo,
                descripcion   = step.descripcion,
                orden         = step.orden,
                duracion_dias = step.duracion_dias,
                tasks         = tasks_del_step,
                total_tasks   = len(tasks_del_step),
                completadas   = completadas,
            ))

    return OnboardingDetailResponse(
        id_employee_onboarding = onboarding.id_employee_onboarding,
        id_plan                = onboarding.id_plan,
        id_user                = onboarding.id_user,
        estado                 = onboarding.estado,
        progreso               = onboarding.progreso,
        fecha_inicio           = onboarding.fecha_inicio,
        fecha_fin              = onboarding.fecha_fin,
        fecha_creacion         = onboarding.fecha_creacion,
        nombre_empleado        = empleado.nombre if empleado else "",
        nombre_plan            = plan.nombre if plan else "",
        steps_con_progreso     = steps_con_progreso,
        task_progresses        = onboarding.task_progresos,
    )


def completar_task(
    id_onboarding: int,
    id_task: int,
    data: CompletarTaskRequest,
    current_user: AppUser,
    roles: List[str],
    db: Session
) -> OnboardingResponse:
    ESTADOS_VALIDOS = ["PENDIENTE", "EN_PROGRESO", "COMPLETADO", "OMITIDO"]
    if data.estado.upper() not in ESTADOS_VALIDOS:
        raise BadRequestError(
            f"Estado inválido. Valores permitidos: {ESTADOS_VALIDOS}"
        )

    onboarding = _get_onboarding(id_onboarding, db)
    _verificar_acceso(onboarding, current_user, roles, db)

    task_progress = db.query(TaskProgress).filter(
        TaskProgress.id_employee_onboarding == id_onboarding,
        TaskProgress.id_task == id_task
    ).first()
    if not task_progress:
        raise NotFoundError("Task no encontrada en este onboarding")

    task_progress.estado = data.estado.upper()
    task_progress.fecha_completada = (
        datetime.now() if data.estado.upper() == "COMPLETADO" else None
    )

    db.flush()
    nuevo_progreso = calcular_progreso(id_onboarding, db)
    onboarding.progreso = nuevo_progreso

    if nuevo_progreso >= 100:
        onboarding.estado    = "COMPLETADO"
        fecha_hoy            = datetime.now().date()
        onboarding.fecha_fin = max(fecha_hoy, onboarding.fecha_inicio)
    elif nuevo_progreso > 0:
        onboarding.estado    = "EN_PROGRESO"
        onboarding.fecha_fin = None

    db.commit()
    db.refresh(onboarding)

    empleado = db.query(AppUser).filter(
        AppUser.id_user == onboarding.id_user
    ).first()
    plan = db.query(OnboardingPlan).filter(
        OnboardingPlan.id_plan == onboarding.id_plan
    ).first()
    return _build_onboarding_response(
        onboarding,
        empleado.nombre if empleado else "",
        plan.nombre if plan else "",
    )


def eliminar_onboarding(
    id_onboarding: int,
    current_user: AppUser,
    roles: List[str],
    db: Session
) -> None:
    onboarding = _get_onboarding(id_onboarding, db)
    _verificar_acceso(onboarding, current_user, roles, db)
    db.delete(onboarding)
    db.commit()
