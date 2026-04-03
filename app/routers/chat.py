from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import AppUser
from app.dependencies import get_current_user, require_admin
from app.services.chat_service import (
    chat_admin_mensaje, crear_plan_desde_sugerencia, chat_empleado_mensaje
)
from app.schemas import PlanResponse
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat IA"])


# ── Schemas ───────────────────────────────────────────────────

class ChatEmpleadoRequest(BaseModel):
    mensaje:        str
    historial:      list = []
    id_onboarding:  int
 
class ChatEmpleadoResponse(BaseModel):
    texto: str

class MensajeHistorial(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class AdminMensajeRequest(BaseModel):
    mensaje: str
    historial: List[MensajeHistorial] = []

class AdminMensajeResponse(BaseModel):
    texto: str
    plan: Optional[dict] = None

class CrearPlanRequest(BaseModel):
    sugerencia: dict  # el objeto "plan" que devolvió la IA


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/admin/mensaje", response_model=AdminMensajeResponse)
async def admin_mensaje(
    data: AdminMensajeRequest,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Envía un mensaje al asistente de planes y recibe una sugerencia de plan en JSON.
    El frontend debe mantener y enviar el historial en cada request.
    """
    historial = [{"role": m.role, "content": m.content} for m in data.historial]
    resultado = await chat_admin_mensaje(
        mensaje=data.mensaje,
        historial=historial,
    )
    return AdminMensajeResponse(
        texto=resultado.get("texto", ""),
        plan=resultado.get("plan"),
    )


@router.post("/admin/crear-plan", response_model=PlanResponse)
async def admin_crear_plan(
    data: CrearPlanRequest,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Crea un plan completo en la BD a partir de la sugerencia generada por la IA.
    Recibe el objeto 'plan' tal como lo devolvió el endpoint /chat/admin/mensaje.
    """
    plan = await crear_plan_desde_sugerencia(
        sugerencia=data.sugerencia,
        empresa_id=current_user.empresa_id,
        current_user=current_user,
        db=db,
    )
    return plan

@router.post("/empleado/mensaje", response_model=ChatEmpleadoResponse)
async def chat_empleado(
    data: ChatEmpleadoRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Chat del empleado — responde preguntas sobre su onboarding con contexto real.
    """
    texto = await chat_empleado_mensaje(
        mensaje=data.mensaje,
        historial=data.historial,
        id_onboarding=data.id_onboarding,
        current_user=current_user,
        db=db,
    )
    return ChatEmpleadoResponse(texto=texto)