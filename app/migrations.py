"""Mini-migraciones: agrega columnas nuevas a tablas que ya existen.

`Base.metadata.create_all` crea las tablas que faltan, pero NO añade columnas
a las existentes. Mientras el proyecto no use Alembic, las columnas nuevas se
declaran aquí. Es idempotente: si la columna ya existe, no hace nada.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("onboarding.migrations")

# (tabla, columna, definición SQL)
COLUMNAS_NUEVAS = [
    ("documento_conocimiento", "url_archivo", "TEXT"),
]


def asegurar_columnas(engine: Engine) -> None:
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    with engine.begin() as conn:
        for tabla, columna, ddl in COLUMNAS_NUEVAS:
            if tabla not in tablas:
                continue                       # create_all ya la creará completa
            existentes = {c["name"] for c in insp.get_columns(tabla)}
            if columna in existentes:
                continue
            conn.execute(text(f'ALTER TABLE {tabla} ADD COLUMN {columna} {ddl}'))
            logger.info("Columna agregada: %s.%s", tabla, columna)
