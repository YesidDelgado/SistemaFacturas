import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from database import (
    inicializar_bd,
    inicializar_bd_usuarios,
    inicializar_bd_admin,
)
from routers.facturas import router as facturas_router
from routers.usuarios import router as usuarios_router

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Sistema de Facturas",
    description="API para registrar y administrar facturas.",
    version="1.0.0"
)

# Inicializar primero las tablas relacionadas.
inicializar_bd_usuarios()
inicializar_bd()
inicializar_bd_admin()

# En producción, configura SESSION_SECRET como variable de entorno.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get(
        "SESSION_SECRET",
        "CAMBIAR-ESTA-CLAVE-ANTES-DE-PUBLICAR-EL-SISTEMA"
    ),
    same_site="lax",
    https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
)

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)

app.include_router(usuarios_router)
app.include_router(facturas_router)


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def verificar_estado():
    return {
        "mensaje": "API de facturas funcionando",
        "version": "1.0.0"
    }
