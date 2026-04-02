from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal


# ── Empresa ──────────────────────────────────────────────────

class EmpresaCreate(BaseModel):
    nombre:     str
    industria:  Optional[str] = None
    email:      EmailStr

class EmpresaResponse(BaseModel):
    id_empresa:     int
    nombre:         str
    industria:      Optional[str]
    email:          str
    fecha_creacion: datetime

    class Config:
        from_attributes = True


# ── Auth ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    nombre:     str
    email:      EmailStr
    password:   str
    empresa_id: int

class LoginRequest(BaseModel):
    email:      EmailStr
    password:   str

class TokenResponse(BaseModel):
    access_token:   str
    token_type:     str = "bearer"
    user_id:        int
    nombre:         str
    email:          str
    empresa_id:     int


# ── Usuario ───────────────────────────────────────────────────

class UserResponse(BaseModel):
    id_user:        int
    nombre:         str
    email:          str
    empresa_id:     int
    fecha_creacion: datetime
    roles:          List[str] = []

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    nombre:     Optional[str]       = None
    email:      Optional[EmailStr]  = None
    password:   Optional[str]       = None


# ── Task ──────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    titulo:         str
    tipo:           str = "CONFIRMACION"
    descripcion:    Optional[str] = None
    url_contenido:  Optional[str] = None
    obligatorio:    bool = True
    orden:          int = 1

class TaskUpdate(BaseModel):
    titulo:         Optional[str]  = None
    tipo:           Optional[str]  = None
    descripcion:    Optional[str]  = None
    url_contenido:  Optional[str]  = None
    obligatorio:    Optional[bool] = None
    orden:          Optional[int]  = None

class TaskResponse(BaseModel):
    id_task:        int
    id_step:        int
    titulo:         str
    tipo:           str
    descripcion:    Optional[str]
    url_contenido:  Optional[str]
    obligatorio:    bool
    orden:          int
    fecha_creacion: datetime
 
    class Config:
        from_attributes = True


# ── Onboarding Step ───────────────────────────────────────────

class StepCreate(BaseModel):
    titulo:         str
    descripcion:    Optional[str] = None
    orden:          int = 1
    duracion_dias:  Optional[int] = None

class StepUpdate(BaseModel):
    titulo:         Optional[str] = None
    descripcion:    Optional[str] = None
    orden:          Optional[int] = None
    duracion_dias:  Optional[int] = None

class StepResponse(BaseModel):
    id_step:        int
    id_plan:        int
    titulo:         str
    descripcion:    Optional[str]
    orden:          int
    duracion_dias:  Optional[int]
    fecha_creacion: datetime
    tasks:          List[TaskResponse] = []

    class Config:
        from_attributes = True


# ── Onboarding Plan ───────────────────────────────────────────

class PlanCreate(BaseModel):
    nombre:         str
    descripcion:    Optional[str] = None
    es_plantilla:   bool = False

class PlanUpdate(BaseModel):
    nombre:         Optional[str]  = None
    descripcion:    Optional[str]  = None
    es_plantilla:   Optional[bool] = None

class PlanResponse(BaseModel):
    id_plan:        int
    id_empresa:     int
    nombre:         str
    descripcion:    Optional[str]
    es_plantilla:   bool
    fecha_creacion: datetime
    mensaje_bienvenida:     Optional[str] = None

    class Config:
        from_attributes = True

class PlanDetailResponse(PlanResponse):
    steps: List[StepResponse] = []

    class Config:
        from_attributes = True


# ── Task Progress ─────────────────────────────────────────────

class TaskProgressResponse(BaseModel):
    id_task_progress:       int
    id_employee_onboarding: int
    id_task:                int
    estado:                 str
    fecha_completada:       Optional[datetime]
    task:                   Optional[TaskResponse] = None

    class Config:
        from_attributes = True



# ── Task Progress con detalle del step (para vista agrupada) ──

class TaskProgressConDetalle(BaseModel):
    """Task progress enriquecido con datos de la task."""
    id_task_progress:       int
    id_task:                int
    id_step:                int
    estado:                 str
    fecha_completada:       Optional[datetime]
    titulo:                 str
    tipo:                   str
    obligatorio:            bool
    orden:                  int
    url_contenido:          Optional[str] = None   # ← nuevo
    descripcion:            Optional[str] = None   # ← nuevo

    class Config:
        from_attributes = True


class StepConProgreso(BaseModel):
    """Step con sus tasks y progreso calculado."""
    id_step:        int
    titulo:         str
    descripcion:    Optional[str]
    orden:          int
    duracion_dias:  Optional[int]
    tasks:          List[TaskProgressConDetalle] = []
    total_tasks:    int = 0
    completadas:    int = 0

    class Config:
        from_attributes = True


# ── Employee Onboarding ───────────────────────────────────────

class AsignarPlanRequest(BaseModel):
    id_user:        int
    id_plan:        int
    fecha_inicio:   Optional[date] = None

class OnboardingResponse(BaseModel):
    id_employee_onboarding: int
    id_plan:                int
    id_user:                int
    estado:                 str
    progreso:               Decimal
    fecha_inicio:           Optional[date]
    fecha_fin:              Optional[date]
    fecha_creacion:         datetime
    # Campos enriquecidos para evitar N+1 en el frontend
    nombre_empleado:        str = ""
    nombre_plan:            str = ""

    class Config:
        from_attributes = True

class OnboardingDetailResponse(OnboardingResponse):
    """Onboarding con el detalle completo de progreso, agrupado por step."""
    steps_con_progreso: List[StepConProgreso] = []
    # Mantenemos task_progresses para compatibilidad con otros endpoints
    task_progresses:    List[TaskProgressResponse] = []

    class Config:
        from_attributes = True

class CompletarTaskRequest(BaseModel):
    estado: str = "COMPLETADO"


# ── Bienvenida ────────────────────────────────────────────────

class BienvenidaUpdate(BaseModel):
    mensaje_bienvenida: Optional[str] = None

class BienvenidaResponse(BaseModel):
    tiene_bienvenida:   bool
    mensaje:            Optional[str]
    id_task:            Optional[int]
    ya_leida:           bool