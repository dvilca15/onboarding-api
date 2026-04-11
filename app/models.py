from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Empresa(Base):
    __tablename__ = "empresa"

    id_empresa      = Column(Integer, primary_key=True, index=True)
    nombre          = Column(String(150), nullable=False)
    industria       = Column(String(100))
    email           = Column(String(150), nullable=False, unique=True)
    fecha_creacion  = Column(DateTime, nullable=False, default=func.now())
    fecha_act       = Column(DateTime, nullable=False, default=func.now())

    usuarios        = relationship("AppUser", back_populates="empresa")
    planes          = relationship("OnboardingPlan", back_populates="empresa")


class Role(Base):
    __tablename__ = "role"

    id_role         = Column(Integer, primary_key=True, index=True)
    nombre          = Column(String(80), nullable=False, unique=True)
    descripcion     = Column(String(300))
    fecha_creacion  = Column(DateTime, nullable=False, default=func.now())
    fecha_act       = Column(DateTime, nullable=False, default=func.now())

    user_roles      = relationship("UserRole", back_populates="role")


class AppUser(Base):
    __tablename__ = "app_user"

    id_user             = Column(Integer, primary_key=True, index=True)
    empresa_id          = Column(Integer, ForeignKey("empresa.id_empresa"), nullable=False)
    nombre              = Column(String(150), nullable=False)
    email               = Column(String(150), nullable=False, unique=True)
    password            = Column(String(255), nullable=False)
    # ── Paso 2: indica si el empleado ya cambió su contraseña inicial ──
    password_changed    = Column(Boolean, nullable=False, default=False)
    fecha_creacion      = Column(DateTime, nullable=False, default=func.now())
    fecha_act           = Column(DateTime, nullable=False, default=func.now())

    empresa             = relationship("Empresa", back_populates="usuarios")
    user_roles          = relationship("UserRole", back_populates="user",
                                       cascade="all, delete-orphan")
    onboardings         = relationship("EmployeeOnboarding", back_populates="user",
                                       cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_role"

    id_user_role        = Column(Integer, primary_key=True, index=True)
    id_user             = Column(Integer, ForeignKey("app_user.id_user"), nullable=False)
    id_role             = Column(Integer, ForeignKey("role.id_role"), nullable=False)
    fecha_asignacion    = Column(DateTime, nullable=False, default=func.now())
    fecha_act           = Column(DateTime, nullable=False, default=func.now())

    user                = relationship("AppUser", back_populates="user_roles")
    role                = relationship("Role", back_populates="user_roles")


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plan"

    id_plan             = Column(Integer, primary_key=True, index=True)
    id_empresa          = Column(Integer, ForeignKey("empresa.id_empresa"), nullable=False)
    nombre              = Column(String(150), nullable=False)
    descripcion         = Column(String(300))
    es_plantilla        = Column(Boolean, nullable=False, default=False)
    mensaje_bienvenida  = Column(Text, nullable=True)
    fecha_creacion      = Column(DateTime, nullable=False, default=func.now())
    fecha_act           = Column(DateTime, nullable=False, default=func.now())

    empresa             = relationship("Empresa", back_populates="planes")
    steps               = relationship("OnboardingStep", back_populates="plan",
                                       cascade="all, delete-orphan")
    onboardings         = relationship("EmployeeOnboarding", back_populates="plan")


class OnboardingStep(Base):
    __tablename__ = "onboarding_step"

    id_step         = Column(Integer, primary_key=True, index=True)
    id_plan         = Column(Integer, ForeignKey("onboarding_plan.id_plan"), nullable=False)
    titulo          = Column(String(150), nullable=False)
    descripcion     = Column(String(300))
    orden           = Column(Integer, nullable=False, default=1)
    duracion_dias   = Column(Integer)
    fecha_creacion  = Column(DateTime, nullable=False, default=func.now())
    fecha_act       = Column(DateTime, nullable=False, default=func.now())

    plan            = relationship("OnboardingPlan", back_populates="steps")
    tasks           = relationship("Task", back_populates="step",
                                   cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "task"

    id_task         = Column(Integer, primary_key=True, index=True)
    id_step         = Column(Integer, ForeignKey("onboarding_step.id_step"), nullable=False)
    titulo          = Column(String(200), nullable=False)
    descripcion     = Column(Text, nullable=True)
    tipo            = Column(String(50), nullable=False, default="CONFIRMACION")
    url_contenido   = Column(Text, nullable=True)
    obligatorio     = Column(Boolean, nullable=False, default=True)
    orden           = Column(Integer, nullable=False, default=1)
    fecha_creacion  = Column(DateTime, nullable=False, default=func.now())
    fecha_act       = Column(DateTime, nullable=False, default=func.now())

    step            = relationship("OnboardingStep", back_populates="tasks")
    progresos       = relationship("TaskProgress", back_populates="task",
                                   cascade="all, delete-orphan")
    respuestas      = relationship("TaskRespuesta", back_populates="task",
                                   cascade="all, delete-orphan")


class EmployeeOnboarding(Base):
    __tablename__ = "employee_onboarding"

    id_employee_onboarding  = Column(Integer, primary_key=True, index=True)
    id_plan                 = Column(Integer, ForeignKey("onboarding_plan.id_plan"), nullable=False)
    id_user                 = Column(Integer, ForeignKey("app_user.id_user"), nullable=False)
    estado                  = Column(String(50), nullable=False, default="PENDIENTE")
    progreso                = Column(Numeric(5, 2), nullable=False, default=0.00)
    fecha_inicio            = Column(Date)
    fecha_fin               = Column(Date)
    fecha_creacion          = Column(DateTime, nullable=False, default=func.now())
    fecha_act               = Column(DateTime, nullable=False, default=func.now())

    plan                    = relationship("OnboardingPlan", back_populates="onboardings")
    user                    = relationship("AppUser", back_populates="onboardings")
    task_progresos          = relationship("TaskProgress", back_populates="onboarding",
                                           cascade="all, delete-orphan")
    conversacion            = relationship("Conversation", back_populates="onboarding",
                                           cascade="all, delete-orphan")


class TaskProgress(Base):
    __tablename__ = "task_progress"

    id_task_progress        = Column(Integer, primary_key=True, index=True)
    id_employee_onboarding  = Column(Integer, ForeignKey("employee_onboarding.id_employee_onboarding"), nullable=False)
    id_task                 = Column(Integer, ForeignKey("task.id_task"), nullable=False)
    estado                  = Column(String(50), nullable=False, default="PENDIENTE")
    fecha_completada        = Column(DateTime)
    fecha_act               = Column(DateTime, nullable=False, default=func.now())

    onboarding              = relationship("EmployeeOnboarding", back_populates="task_progresos")
    task                    = relationship("Task", back_populates="progresos")


class TaskRespuesta(Base):
    __tablename__ = "task_respuesta"

    id_respuesta        = Column(Integer, primary_key=True, index=True)
    id_task_progress    = Column(Integer, ForeignKey("task_progress.id_task_progress"), nullable=False)
    id_task             = Column(Integer, ForeignKey("task.id_task"), nullable=False)
    pregunta            = Column(Text, nullable=False)
    respuesta           = Column(Text, nullable=False)
    fecha_creacion      = Column(DateTime, nullable=False, default=func.now())

    task                = relationship("Task", back_populates="respuestas")


class Conversation(Base):
    __tablename__ = "conversation"

    id_conversation         = Column(Integer, primary_key=True, index=True)
    id_employee_onboarding  = Column(Integer, ForeignKey("employee_onboarding.id_employee_onboarding"), nullable=False)
    fecha_creacion          = Column(DateTime, nullable=False, default=func.now())
    fecha_act               = Column(DateTime, nullable=False, default=func.now())

    onboarding              = relationship("EmployeeOnboarding", back_populates="conversacion")
    mensajes                = relationship("Message", back_populates="conversacion")


class Message(Base):
    __tablename__ = "message"

    id_message      = Column(Integer, primary_key=True, index=True)
    id_conversation = Column(Integer, ForeignKey("conversation.id_conversation"), nullable=False)
    sender_type     = Column(String(20), nullable=False)
    contenido       = Column(Text, nullable=False)
    fecha_envio     = Column(DateTime, nullable=False, default=func.now())

    conversacion    = relationship("Conversation", back_populates="mensajes")
