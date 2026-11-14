"""RAG: base de conocimiento por empresa.

Flujo:
  subir documento -> extraer texto -> dividir en fragmentos -> embeddings
  -> guardar en la BD (con empresa_id)
  pregunta -> embedding de la pregunta -> fragmentos más parecidos de ESA empresa
  -> se pasan a la IA como contexto.

Los embeddings se calculan con Gemini (gemini-embedding-001) y se guardan como
listas JSON; la similitud se calcula en Python, suficiente para una Mipyme.
"""
import asyncio
import io
import logging
import math
import os
import re
from typing import Iterable

import httpx
from sqlalchemy.orm import Session

from app.models import DocumentoConocimiento, FragmentoConocimiento

logger = logging.getLogger("onboarding.rag")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMS = 768            # el modelo devuelve 3072; 768 ocupa 4 veces menos
OBJETIVO_CARACTERES = 1100      # tamaño aproximado de cada fragmento
SOLAPE_CARACTERES = 150         # se repite el final del anterior para no cortar ideas
MAX_FRAGMENTOS_POR_DOC = 300
MAX_CARACTERES_DOC = 400_000
CONCURRENCIA = 5

EXTENSIONES = {".pdf": "pdf", ".txt": "txt", ".md": "md"}


class RagError(Exception):
    """Error mostrable al usuario (archivo inválido, sin texto, etc.)."""


# ── 1. Extracción de texto ────────────────────────────────────

def extraer_texto(nombre_archivo: str, contenido: bytes) -> tuple[str, str]:
    """Devuelve (texto, tipo). Lanza RagError si no se puede leer."""
    ext = os.path.splitext(nombre_archivo or "")[1].lower()
    tipo = EXTENSIONES.get(ext)
    if not tipo:
        raise RagError("Formato no permitido. Usa PDF, TXT o MD.")

    if tipo == "pdf":
        try:
            from pypdf import PdfReader
            lector = PdfReader(io.BytesIO(contenido))
            if lector.is_encrypted:
                try:
                    lector.decrypt("")
                except Exception:
                    raise RagError("El PDF está protegido con contraseña.")
            paginas = [(p.extract_text() or "") for p in lector.pages]
        except RagError:
            raise
        except Exception:
            raise RagError("No se pudo leer el PDF. Puede estar dañado.")
        texto = "\n\n".join(paginas)
    else:
        try:
            texto = contenido.decode("utf-8")
        except UnicodeDecodeError:
            texto = contenido.decode("latin-1", errors="replace")

    texto = limpiar_texto(texto)
    if len(texto) < 50:
        raise RagError(
            "El documento no contiene texto legible. Si es un PDF escaneado "
            "(imágenes), conviértelo antes a un PDF con texto."
        )
    return texto[:MAX_CARACTERES_DOC], tipo


def limpiar_texto(texto: str) -> str:
    texto = texto.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"-\n(?=[a-záéíóúñ])", "", texto)       # palabras partidas por guion
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


# ── 2. Fragmentación ──────────────────────────────────────────

def dividir_en_fragmentos(texto: str) -> list[str]:
    """Agrupa párrafos hasta ~OBJETIVO_CARACTERES, con un pequeño solape."""
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    # un párrafo gigante se parte por oraciones
    piezas: list[str] = []
    for p in parrafos:
        if len(p) <= OBJETIVO_CARACTERES:
            piezas.append(p)
        else:
            oraciones = re.split(r"(?<=[.!?])\s+", p)
            actual = ""
            for o in oraciones:
                if len(actual) + len(o) + 1 > OBJETIVO_CARACTERES and actual:
                    piezas.append(actual.strip())
                    actual = ""
                actual += o + " "
            if actual.strip():
                piezas.append(actual.strip())

    fragmentos: list[str] = []
    actual = ""
    for pieza in piezas:
        if actual and len(actual) + len(pieza) + 2 > OBJETIVO_CARACTERES:
            fragmentos.append(actual.strip())
            cola = actual[-SOLAPE_CARACTERES:]
            # empezar el siguiente en un límite de palabra
            cola = cola[cola.find(" ") + 1:] if " " in cola else ""
            actual = cola + "\n\n" if cola else ""
        actual += pieza + "\n\n"
    if actual.strip():
        fragmentos.append(actual.strip())

    fragmentos = [f for f in fragmentos if len(f) >= 40]
    if len(fragmentos) > MAX_FRAGMENTOS_POR_DOC:
        raise RagError(
            f"El documento es demasiado grande (más de {MAX_FRAGMENTOS_POR_DOC} "
            "fragmentos). Divídelo en partes más pequeñas."
        )
    return fragmentos


# ── 3. Embeddings (Gemini) ────────────────────────────────────

def _normalizar(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


async def _embed_uno(
    cliente: httpx.AsyncClient, api_key: str, texto: str, tarea: str
) -> list[float]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent"
    cuerpo = {
        "content": {"parts": [{"text": texto}]},
        "taskType": tarea,
        "outputDimensionality": EMBEDDING_DIMS,
    }
    ultimo = ""
    for intento in range(4):
        r = await cliente.post(url, json=cuerpo, headers={"x-goog-api-key": api_key})
        if r.status_code == 200:
            return _normalizar(r.json()["embedding"]["values"])
        ultimo = f"HTTP {r.status_code}"
        if r.status_code in (429, 500, 502, 503, 504):
            await asyncio.sleep(1.5 * (intento + 1))
            continue
        break
    raise RagError(f"No se pudo generar el índice de búsqueda ({ultimo}).")


async def embeddings(textos: Iterable[str], tarea: str) -> list[list[float]]:
    """tarea: RETRIEVAL_DOCUMENT para guardar, RETRIEVAL_QUERY para preguntas."""
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RagError("Falta GEMINI_API_KEY para generar embeddings.")
    textos = list(textos)
    sem = asyncio.Semaphore(CONCURRENCIA)

    async with httpx.AsyncClient(timeout=40) as cliente:
        async def uno(t: str):
            async with sem:
                return await _embed_uno(cliente, api_key, t, tarea)
        return await asyncio.gather(*(uno(t) for t in textos))


# ── 4. Indexar un documento ───────────────────────────────────

async def indexar_documento(
    db: Session,
    *,
    empresa_id: int,
    nombre: str,
    nombre_archivo: str,
    contenido: bytes,
) -> DocumentoConocimiento:
    texto, tipo = extraer_texto(nombre_archivo, contenido)
    fragmentos = dividir_en_fragmentos(texto)
    if not fragmentos:
        raise RagError("No se encontró contenido útil en el documento.")
    vectores = await embeddings(fragmentos, "RETRIEVAL_DOCUMENT")

    doc = DocumentoConocimiento(
        id_empresa=empresa_id,
        nombre=nombre[:200],
        nombre_archivo=(nombre_archivo or "documento")[:255],
        tipo=tipo,
        num_fragmentos=len(fragmentos),
        num_caracteres=len(texto),
    )
    db.add(doc)
    db.flush()
    for i, (t, v) in enumerate(zip(fragmentos, vectores)):
        db.add(FragmentoConocimiento(
            id_documento=doc.id_documento,
            id_empresa=empresa_id,
            orden=i,
            texto=t,
            embedding=v,
        ))
    db.commit()
    db.refresh(doc)
    return doc


# ── 5. Búsqueda ───────────────────────────────────────────────

# Por debajo de este parecido el fragmento no se considera relevante.
# Se calibró con preguntas de prueba (ver tests); ajústalo con RAG_UMBRAL.
UMBRAL = float(os.getenv("RAG_UMBRAL", "0.62"))


def _similitud(a: list[float], b: list[float]) -> float:
    # ambos vectores están normalizados: el producto punto es el coseno
    return sum(x * y for x, y in zip(a, b))


async def buscar(
    db: Session, empresa_id: int, pregunta: str, k: int = 4
) -> list[dict]:
    """Fragmentos más relevantes de ESTA empresa (nunca de otra)."""
    filas = (
        db.query(FragmentoConocimiento, DocumentoConocimiento.nombre)
        .join(DocumentoConocimiento,
              DocumentoConocimiento.id_documento == FragmentoConocimiento.id_documento)
        .filter(FragmentoConocimiento.id_empresa == empresa_id)
        .all()
    )
    if not filas:
        return []

    try:
        consulta = (await embeddings([pregunta], "RETRIEVAL_QUERY"))[0]
    except RagError:
        logger.warning("No se pudo calcular el embedding de la pregunta", exc_info=True)
        return []

    puntuados = [
        (_similitud(consulta, f.embedding), f, nombre) for f, nombre in filas
    ]
    puntuados.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "documento": nombre,
            "id_documento": f.id_documento,
            "texto": f.texto,
            "puntaje": round(p, 3),
        }
        for p, f, nombre in puntuados[:k]
        if p >= UMBRAL
    ]
