import os
import uuid
import shutil
from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models import AppUser, Task, TaskProgress, TaskRespuesta
from app.schemas import TaskCreate, TaskUpdate, TaskResponse
from app.dependencies import get_current_user, require_admin
from app.services import plan_service
from app.exceptions import NotFoundError, BadRequestError

router = APIRouter(prefix="/steps/{id_step}/tasks", tags=["Tasks"])

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

EXTENSIONES_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
TAMANO_MAXIMO_MB = 10


# ── Schemas locales ───────────────────────────────────────────

class RespuestaFormulario(BaseModel):
    pregunta: str
    respuesta: str

class EnviarRespuestasRequest(BaseModel):
    respuestas: List[RespuestaFormulario]


# ── CRUD básico ───────────────────────────────────────────────

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


# ── Subir archivo (DOCUMENTO) ─────────────────────────────────

@router.post("/{id_task}/upload", response_model=TaskResponse)
async def subir_archivo_task(
    id_step: int,
    id_task: int,
    archivo: UploadFile = File(...),
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Sube un archivo PDF/imagen para una task de tipo DOCUMENTO.
    Reemplaza el archivo anterior si existía.
    Solo ADMIN_EMPRESA.
    """
    # Verificar extensión
    nombre_original = archivo.filename or ""
    ext = os.path.splitext(nombre_original)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no permitida. Use: {', '.join(EXTENSIONES_PERMITIDAS)}"
        )

    # Verificar tamaño
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el límite de {TAMANO_MAXIMO_MB}MB"
        )

    # Obtener task y verificar que sea DOCUMENTO
    task = db.query(Task).filter(Task.id_task == id_task).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    if task.tipo != "DOCUMENTO":
        raise HTTPException(status_code=400, detail="Solo tasks de tipo DOCUMENTO admiten archivos")

    # Eliminar archivo anterior si existe
    if task.url_contenido:
        ruta_anterior = task.url_contenido.lstrip("/")
        if os.path.exists(ruta_anterior):
            os.remove(ruta_anterior)

    # Guardar nuevo archivo con nombre único
    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    ruta_guardado = os.path.join(UPLOAD_DIR, nombre_unico)
    with open(ruta_guardado, "wb") as f:
        f.write(contenido)

    # Actualizar url_contenido en la task
    task.url_contenido = f"/static/uploads/{nombre_unico}"
    db.commit()
    db.refresh(task)
    return task


# ── Guardar URL (VIDEO) ───────────────────────────────────────

@router.put("/{id_task}/url", response_model=TaskResponse)
def actualizar_url_task(
    id_step: int,
    id_task: int,
    url: str,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Guarda la URL del video para una task de tipo VIDEO.
    Solo ADMIN_EMPRESA.
    """
    task = db.query(Task).filter(Task.id_task == id_task).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    if task.tipo != "VIDEO":
        raise HTTPException(status_code=400, detail="Solo tasks de tipo VIDEO admiten URL")

    task.url_contenido = url
    db.commit()
    db.refresh(task)
    return task


# ── Guardar preguntas del formulario (FORMULARIO) ─────────────

@router.put("/{id_task}/preguntas", response_model=TaskResponse)
def actualizar_preguntas_formulario(
    id_step: int,
    id_task: int,
    preguntas: str,  # JSON string con lista de preguntas
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Guarda las preguntas del formulario en el campo descripcion.
    preguntas: JSON string, ej: ["¿Cuál es tu área?", "¿Tienes experiencia previa?"]
    Solo ADMIN_EMPRESA.
    """
    task = db.query(Task).filter(Task.id_task == id_task).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    if task.tipo != "FORMULARIO":
        raise HTTPException(status_code=400, detail="Solo tasks de tipo FORMULARIO admiten preguntas")

    task.descripcion = preguntas
    db.commit()
    db.refresh(task)
    return task


# ── Enviar respuestas del formulario (empleado) ───────────────

@router.post("/{id_task}/respuestas", status_code=status.HTTP_201_CREATED)
def enviar_respuestas_formulario(
    id_step: int,
    id_task: int,
    id_onboarding: int,
    data: EnviarRespuestasRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    El empleado envía sus respuestas al formulario.
    Guarda las respuestas y marca la task como COMPLETADO.
    """
    task = db.query(Task).filter(Task.id_task == id_task).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    if task.tipo != "FORMULARIO":
        raise HTTPException(status_code=400, detail="Esta task no es un formulario")

    tp = db.query(TaskProgress).filter(
        TaskProgress.id_employee_onboarding == id_onboarding,
        TaskProgress.id_task == id_task,
    ).first()
    if not tp:
        raise HTTPException(status_code=404, detail="Progreso no encontrado")

    # Guardar respuestas
    for r in data.respuestas:
        db.add(TaskRespuesta(
            id_task_progress=tp.id_task_progress,
            id_task=id_task,
            pregunta=r.pregunta,
            respuesta=r.respuesta,
        ))

    # Marcar como completado
    from datetime import datetime
    tp.estado = "COMPLETADO"
    tp.fecha_completada = datetime.now()
    db.commit()

    return {"mensaje": "Respuestas guardadas correctamente"}


# ── Ver respuestas del formulario (admin) ─────────────────────

@router.get("/{id_task}/respuestas/{id_onboarding}")
def ver_respuestas_formulario(
    id_step: int,
    id_task: int,
    id_onboarding: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    El admin ve las respuestas del empleado a un formulario.
    Solo ADMIN_EMPRESA.
    """
    tp = db.query(TaskProgress).filter(
        TaskProgress.id_employee_onboarding == id_onboarding,
        TaskProgress.id_task == id_task,
    ).first()
    if not tp:
        raise HTTPException(status_code=404, detail="Progreso no encontrado")

    respuestas = db.query(TaskRespuesta).filter(
        TaskRespuesta.id_task_progress == tp.id_task_progress
    ).all()

    return {
        "id_task": id_task,
        "id_onboarding": id_onboarding,
        "respuestas": [
            {"pregunta": r.pregunta, "respuesta": r.respuesta, "fecha": r.fecha_creacion}
            for r in respuestas
        ]
    }