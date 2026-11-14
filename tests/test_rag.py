"""Pruebas del RAG que no usan internet: los embeddings se simulan."""
import asyncio
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app import models  # noqa: F401  (registra las tablas)
from app.models import Empresa
from app.services import rag_service as rag
from app.services.chat_service import _dice_no_encontrado, _fuentes_citadas


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def vec(*xs):
    n = sum(x * x for x in xs) ** 0.5
    return [x / n for x in xs]


@pytest.fixture()
def embeddings_falsos(monkeypatch):
    """Cada texto se convierte en un vector según una palabra clave."""
    async def falso(textos, tarea):
        out = []
        for t in textos:
            t = t.lower()
            if "vacaciones" in t:
                out.append(vec(1, 0, 0))
            elif "caja chica" in t:
                out.append(vec(0, 1, 0))
            else:
                out.append(vec(0, 0, 1))
        return out
    monkeypatch.setattr(rag, "embeddings", falso)


def run(c):
    return asyncio.run(c)


# ── Extracción y fragmentación ────────────────────────────────

def test_extraer_texto_rechaza_formato_no_permitido():
    with pytest.raises(rag.RagError, match="Formato no permitido"):
        rag.extraer_texto("virus.exe", b"MZ")


def test_extraer_texto_rechaza_vacio_o_escaneado():
    with pytest.raises(rag.RagError, match="no contiene texto"):
        rag.extraer_texto("a.txt", b"   ")


def test_extraer_texto_rechaza_pdf_danado():
    with pytest.raises(rag.RagError, match="PDF"):
        rag.extraer_texto("a.pdf", b"%PDF-1.4 basura")


def test_extraer_txt_latin1():
    texto, tipo = rag.extraer_texto("a.txt", ("Política de vacaciones " * 10).encode("latin-1"))
    assert tipo == "txt" and "Política" in texto


def test_fragmentos_no_exceden_tamano_y_cubren_todo():
    parrafos = [f"Párrafo {i}. " + "texto de relleno " * 30 for i in range(20)]
    frag = rag.dividir_en_fragmentos("\n\n".join(parrafos))
    assert len(frag) > 1
    assert all(len(f) <= rag.OBJETIVO_CARACTERES + rag.SOLAPE_CARACTERES + 50 for f in frag)
    unido = " ".join(frag)
    assert all(f"Párrafo {i}." in unido for i in range(20))


def test_parrafo_gigante_se_divide_por_oraciones():
    gigante = ". ".join(f"Oración número {i} con algo de contenido" for i in range(200)) + "."
    frag = rag.dividir_en_fragmentos(gigante)
    assert len(frag) > 1


def test_documento_demasiado_grande_se_rechaza():
    enorme = "\n\n".join("x" * 600 for _ in range(rag.MAX_FRAGMENTOS_POR_DOC * 2))
    with pytest.raises(rag.RagError, match="demasiado grande"):
        rag.dividir_en_fragmentos(enorme)


# ── Búsqueda y aislamiento entre empresas ─────────────────────

def _empresa(db, n):
    e = Empresa(nombre=f"E{n}", email=f"e{n}@x.com")
    db.add(e)
    db.commit()
    return e


def test_busqueda_devuelve_lo_relevante_y_ordenado(db, embeddings_falsos):
    e = _empresa(db, 1)
    run(rag.indexar_documento(
        db, empresa_id=e.id_empresa, nombre="Reglamento", nombre_archivo="r.txt",
        contenido=("Las vacaciones son 30 días por año completo de servicios. " * 3
                   + "\n\nLa caja chica tiene un monto máximo de 300 soles por rendición. " * 3).encode()))
    r = run(rag.buscar(db, e.id_empresa, "¿cuántas vacaciones tengo?", k=3))
    assert r and "vacaciones" in r[0]["texto"].lower()
    assert r[0]["documento"] == "Reglamento"


def test_pregunta_fuera_del_documento_no_devuelve_nada(db, embeddings_falsos):
    e = _empresa(db, 1)
    run(rag.indexar_documento(
        db, empresa_id=e.id_empresa, nombre="R", nombre_archivo="r.txt",
        contenido=("Las vacaciones son 30 días por año. " * 5).encode()))
    # la pregunta cae en otro "tema" -> similitud 0 < umbral
    assert run(rag.buscar(db, e.id_empresa, "capital de Francia", k=3)) == []


def test_aislamiento_una_empresa_nunca_ve_documentos_de_otra(db, embeddings_falsos):
    a, b = _empresa(db, 1), _empresa(db, 2)
    run(rag.indexar_documento(
        db, empresa_id=a.id_empresa, nombre="Secreto de A", nombre_archivo="a.txt",
        contenido=("Las vacaciones en A son 30 días. " * 5).encode()))
    assert run(rag.buscar(db, b.id_empresa, "vacaciones", k=5)) == []
    assert len(run(rag.buscar(db, a.id_empresa, "vacaciones", k=5))) >= 1


# ── Citas y "no encontré" ─────────────────────────────────────

FRAGS = [
    {"documento": "Reglamento", "texto": "Texto uno " * 40, "puntaje": 0.8},
    {"documento": "Políticas", "texto": "Texto dos", "puntaje": 0.7},
]


def test_fuentes_citadas_solo_las_usadas_y_sin_duplicar():
    f = _fuentes_citadas("Son 30 días [1]. Y se programan antes [1][2]. Falso [9].", FRAGS)
    assert [x["numero"] for x in f] == [1, 2]
    assert f[0]["documento"] == "Reglamento"
    assert f[0]["extracto"].endswith("…")        # extracto recortado


@pytest.mark.parametrize("t", [
    "No encontré esa información en los documentos de la empresa.",
    "No he encontrado información sobre eso.",
    "Lamentablemente no tengo información sobre salarios.",
])
def test_detecta_respuestas_de_no_encontrado(t):
    assert _dice_no_encontrado(t)


def test_no_marca_como_no_encontrado_una_respuesta_normal():
    assert not _dice_no_encontrado("Tienes 30 días de vacaciones [1].")


# ── Chat del admin ────────────────────────────────────────────

from app.services.chat_service import _bloque_conocimiento_admin, _quitar_citas


def test_plan_no_lleva_marcadores_de_cita():
    plan = {
        "titulo": "Plan [1]",
        "mensaje_bienvenida": "Bienvenido al equipo [2].",
        "etapas": [{"nombre": "Inducción [1]", "tareas": [{"titulo": "Leer el reglamento [3]", "orden": 1}]}],
    }
    limpio = _quitar_citas(plan)
    import re
    assert not re.search(r"\[\d{1,2}\]", str(limpio))
    assert limpio["etapas"][0]["tareas"][0]["orden"] == 1     # no toca valores no texto


def test_prompt_admin_sin_documentos_no_inventa_y_remite_a_conocimiento():
    b = _bloque_conocimiento_admin([], [])
    assert "no ha subido documentos" in b and "Conocimiento" in b


def test_prompt_admin_con_documentos_lista_nombres_y_fragmentos():
    b = _bloque_conocimiento_admin(
        ["Reglamento Interno"],
        [{"documento": "Reglamento Interno", "texto": "30 días de vacaciones", "puntaje": 0.8}],
    )
    assert "«Reglamento Interno»" in b and "[1] (Documento: Reglamento Interno)" in b
    assert "NUNCA pongas [n] dentro del plan" in b


# ── Adjuntar documentos a tareas ──────────────────────────────

from types import SimpleNamespace
from app.services.chat_service import _buscar_documento_para_tarea
from app.migrations import asegurar_columnas


def _doc(nombre, url="/static/uploads/kb_x.pdf"):
    return SimpleNamespace(nombre=nombre, url_archivo=url)


DOCS = [_doc("Reglamento Interno"), _doc("Política de Caja Chica"), _doc("Manual de Bienvenida")]


@pytest.mark.parametrize("tarea,esperado", [
    ({"titulo": "x", "documento": "Reglamento Interno"}, "Reglamento Interno"),          # nombre exacto
    ({"titulo": "x", "documento": "reglamento   interno"}, "Reglamento Interno"),        # sin mayúsculas
    ({"titulo": "x", "documento": "Politica de caja chica"}, "Política de Caja Chica"),  # sin tildes
    ({"titulo": "Leer el Reglamento Interno de Trabajo"}, "Reglamento Interno"),         # por el título
    ({"titulo": "Revisar la política de caja chica"}, "Política de Caja Chica"),
])
def test_empareja_tarea_con_documento(tarea, esperado):
    assert _buscar_documento_para_tarea(tarea, DOCS).nombre == esperado


@pytest.mark.parametrize("tarea", [
    {"titulo": "Leer el reglamento"},                              # incompleto: no se adivina
    {"titulo": "Ver el video institucional"},
    {"titulo": "x", "documento": "Documento que no existe"},
    {"titulo": "Revisar el manual"},
])
def test_no_adjunta_si_no_hay_coincidencia_clara(tarea):
    assert _buscar_documento_para_tarea(tarea, DOCS) is None


def test_no_adjunta_documentos_sin_archivo_original():
    docs = [_doc("Reglamento Interno", url=None)]      # subido antes de esta función
    assert _buscar_documento_para_tarea({"titulo": "Leer el Reglamento Interno"}, docs) is None


def test_migracion_agrega_columna_a_tabla_existente():
    from sqlalchemy import inspect, text
    eng = create_engine("sqlite://", poolclass=StaticPool)
    with eng.begin() as c:       # tabla "vieja", sin url_archivo
        c.execute(text("CREATE TABLE documento_conocimiento (id_documento INTEGER PRIMARY KEY, nombre TEXT)"))
        c.execute(text("INSERT INTO documento_conocimiento (nombre) VALUES ('viejo')"))
    asegurar_columnas(eng)
    asegurar_columnas(eng)       # idempotente
    cols = {c["name"] for c in inspect(eng).get_columns("documento_conocimiento")}
    assert "url_archivo" in cols
    with eng.connect() as c:     # los datos existentes se conservan
        assert c.execute(text("SELECT nombre FROM documento_conocimiento")).scalar() == "viejo"
