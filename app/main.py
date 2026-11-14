import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
load_dotenv()

from app.database import Base, engine
from app.routers import auth, empresa, users, planes, steps, tasks, onboarding, chat, conocimiento

Base.metadata.create_all(bind=engine)
from app.migrations import asegurar_columnas
asegurar_columnas(engine)

app = FastAPI(
    title="Sistema de Onboarding para Mipymes",
    description="API para gestion del proceso de onboarding de empleados",
    version="1.0.0"
)

logger = logging.getLogger("onboarding.api")


# Se registra ANTES que CORS para quedar por dentro: así los errores 500 también
# llevan cabeceras CORS y la app muestra el mensaje en vez de "Failed to fetch".
@app.middleware("http")
async def capturar_errores(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor. Revisa los logs del backend."},
        )


# Orígenes permitidos: CORS_ORIGINS="https://app.ejemplo.com,http://localhost:3000"
# Si no se define, se permite cualquiera pero SIN credenciales (auth es por Bearer, no cookies).
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=bool(_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos (uploads)
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router)
app.include_router(empresa.router)
app.include_router(users.router)
app.include_router(planes.router)
app.include_router(steps.router)
app.include_router(tasks.router)
app.include_router(onboarding.router)
app.include_router(chat.router)
app.include_router(conocimiento.router)

@app.get("/")
def root():
    return {"message": "API de Onboarding funcionando correctamente"}