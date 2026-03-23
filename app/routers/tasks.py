from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import AppUser
from app.schemas import TaskCreate, TaskUpdate, TaskResponse
from app.dependencies import get_current_user, require_admin
from app.services import plan_service

router = APIRouter(prefix="/steps/{id_step}/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def crear_task(
    id_step: int,
    data: TaskCreate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Crea una task en un step. Solo ADMIN_EMPRESA."""
    return plan_service.crear_task(id_step, data, current_user.empresa_id, db)


@router.get("/", response_model=List[TaskResponse])
def listar_tasks(
    id_step: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista las tasks de un step ordenadas por campo orden."""
    return plan_service.listar_tasks(id_step, current_user.empresa_id, db)


@router.put("/{id_task}", response_model=TaskResponse)
def actualizar_task(
    id_step: int,
    id_task: int,
    data: TaskUpdate,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Actualiza una task. Solo ADMIN_EMPRESA."""
    return plan_service.actualizar_task(id_task, id_step, data, current_user.empresa_id, db)


@router.delete("/{id_task}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_task(
    id_step: int,
    id_task: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Elimina una task. Solo ADMIN_EMPRESA."""
    plan_service.eliminar_task(id_task, id_step, current_user.empresa_id, db)