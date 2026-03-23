from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import auth, empresa, users, planes, steps, tasks, onboarding

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sistema de Onboarding para Mipymes",
    description="API para gestion del proceso de onboarding de empleados",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(empresa.router)
app.include_router(users.router)
app.include_router(planes.router)
app.include_router(steps.router)
app.include_router(tasks.router)
app.include_router(onboarding.router)

@app.get("/")
def root():
    return {"message": "API de Onboarding funcionando correctamente"}