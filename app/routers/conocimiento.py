import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.dependencies import require_admin
from app.exceptions import NotFoundError
from app.models import AppUser, DocumentoConocimiento
from app.services import rag_service

router = APIRouter(prefix="/conocimiento", tags=["Base de conocimiento"])

TAMANO_MAXIMO_MB = 10
UPLOAD_DIR = "static/uploads"
MAX_DOCUMENTOS_POR_EMPRESA = 30


class DocumentoResponse(BaseModel):
    id_documento:    int
    nombre:          str
    nombre_archivo:  str
    tipo:            str
    num_fragmentos:  int
    num_caracteres:  int
    tiene_archivo:   bool = False
    fecha_creacion:  datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[DocumentoResponse])
def listar_documentos(
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Documentos de la base de conocimiento de la empresa. Solo ADMIN_EMPRESA."""
    return (
        db.query(DocumentoConocimiento)
        .filter(DocumentoConocimiento.id_empresa == current_user.empresa_id)
        .order_by(DocumentoConocimiento.fecha_creacion.desc())
        .all()
    )


@router.post("/", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def subir_documento(
    archivo: UploadFile = File(...),
    nombre: Optional[str] = Form(None),
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Sube un documento (PDF, TXT o MD), lo divide en fragmentos y genera su
    índice de búsqueda. Solo ADMIN_EMPRESA.
    """
    total = (
        db.query(DocumentoConocimiento)
        .filter(DocumentoConocimiento.id_empresa == current_user.empresa_id)
        .count()
    )
    if total >= MAX_DOCUMENTOS_POR_EMPRESA:
        raise HTTPException(
            status_code=400,
            detail=f"Alcanzaste el límite de {MAX_DOCUMENTOS_POR_EMPRESA} documentos. "
                   "Elimina alguno antes de subir otro.",
        )

    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el límite de {TAMANO_MAXIMO_MB}MB",
        )
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    nombre_archivo = archivo.filename or "documento"
    titulo = (nombre or "").strip() or nombre_archivo.rsplit(".", 1)[0]

    try:
        doc = await rag_service.indexar_documento(
            db,
            empresa_id=current_user.empresa_id,
            nombre=titulo,
            nombre_archivo=nombre_archivo,
            contenido=contenido,
        )
    except rag_service.RagError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # Se guarda también el archivo original para poder adjuntarlo a tareas.
    # Si falla, el documento sigue sirviendo para el asistente (solo sin adjunto).
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(nombre_archivo)[1].lower()
        nombre_fisico = f"kb_{uuid.uuid4().hex}{ext}"
        with open(os.path.join(UPLOAD_DIR, nombre_fisico), "wb") as f:
            f.write(contenido)
        doc.url_archivo = f"/static/uploads/{nombre_fisico}"
        db.commit()
        db.refresh(doc)
    except OSError:
        db.rollback()
    return doc


@router.delete("/{id_documento}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_documento(
    id_documento: int,
    current_user: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina un documento y todos sus fragmentos. Solo ADMIN_EMPRESA."""
    doc = (
        db.query(DocumentoConocimiento)
        .filter(
            DocumentoConocimiento.id_documento == id_documento,
            DocumentoConocimiento.id_empresa == current_user.empresa_id,
        )
        .first()
    )
    if not doc:
        raise NotFoundError("Documento no encontrado")
    ruta = (doc.url_archivo or "").lstrip("/")
    db.delete(doc)
    db.commit()
    # Las tareas que ya lo tienen adjunto conservan su propia copia.
    if ruta.startswith("static/uploads/kb_") and os.path.exists(ruta):
        os.remove(ruta)
