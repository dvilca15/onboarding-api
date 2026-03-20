from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import OnboardingPlan, OnboardingStep, Task, AppUser
from app.schemas import TaskCreate, TaskUpdate, TaskResponse
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/steps/{id_step}/tasks", tags=["Tasks"])

TIPOS_VALIDOS = ["DOCUMENTO", "VIDEO", "FORMULARIO", "CONFIRMACION"]


def get_step_or_404(id_step: int, empresa_id: int, db: Session) -> OnboardingStep:
    """Obtiene el step y verifica que pertenece a la empresa."""
    step = db.query(OnboardingStep).filter(OnboardingStep.id_step == id_step).first()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step no encontrado"
        )
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id_plan == step.id_plan).first()
    if not plan or plan.id_empresa != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este step"
        )
    return step


# ── POST /steps/{id_step}/tasks/ ─────────────────────────────
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def crear_task(
    id_step: int,
    data: TaskCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Crea una nueva task dentro de un step.
    Solo ADMIN_EMPRESA puede crear tasks.
    """
    get_step_or_404(id_step, current_user.empresa_id, db)

    # Validar tipo
    if data.tipo.upper() not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo inválido. Valores permitidos: {TIPOS_VALIDOS}"
        )

    nueva_task = Task(
        id_step     = id_step,
        titulo      = data.titulo,
        tipo        = data.tipo.upper(),
        obligatorio = data.obligatorio,
        orden       = data.orden
    )
    db.add(nueva_task)
    db.commit()
    db.refresh(nueva_task)
    return nueva_task


# ── GET /steps/{id_step}/tasks/ ──────────────────────────────
@router.get("/", response_model=List[TaskResponse])
def listar_tasks(
    id_step: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todas las tasks de un step ordenadas por campo orden.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    get_step_or_404(id_step, current_user.empresa_id, db)

    tasks = (
        db.query(Task)
        .filter(Task.id_step == id_step)
        .order_by(Task.orden)
        .all()
    )
    return tasks


# ── GET /steps/{id_step}/tasks/{id_task} ─────────────────────
@router.get("/{id_task}", response_model=TaskResponse)
def obtener_task(
    id_step: int,
    id_task: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene una task específica.
    Disponible para ADMIN_EMPRESA y EMPLEADO.
    """
    get_step_or_404(id_step, current_user.empresa_id, db)

    task = db.query(Task).filter(
        Task.id_task == id_task,
        Task.id_step == id_step
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task no encontrada"
        )
    return task


# ── PUT /steps/{id_step}/tasks/{id_task} ─────────────────────
@router.put("/{id_task}", response_model=TaskResponse)
def actualizar_task(
    id_step: int,
    id_task: int,
    data: TaskUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Actualiza una task.
    Solo ADMIN_EMPRESA puede actualizar tasks.
    Solo se actualizan los campos enviados.
    """
    get_step_or_404(id_step, current_user.empresa_id, db)

    task = db.query(Task).filter(
        Task.id_task == id_task,
        Task.id_step == id_step
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task no encontrada"
        )

    if data.titulo is not None:
        task.titulo = data.titulo
    if data.tipo is not None:
        if data.tipo.upper() not in TIPOS_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo inválido. Valores permitidos: {TIPOS_VALIDOS}"
            )
        task.tipo = data.tipo.upper()
    if data.obligatorio is not None:
        task.obligatorio = data.obligatorio
    if data.orden is not None:
        task.orden = data.orden

    db.commit()
    db.refresh(task)
    return task


# ── DELETE /steps/{id_step}/tasks/{id_task} ──────────────────
@router.delete("/{id_task}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_task(
    id_step: int,
    id_task: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina una task.
    Solo ADMIN_EMPRESA puede eliminar tasks.
    """
    get_step_or_404(id_step, current_user.empresa_id, db)

    task = db.query(Task).filter(
        Task.id_task == id_task,
        Task.id_step == id_step
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task no encontrada"
        )

    db.delete(task)
    db.commit()