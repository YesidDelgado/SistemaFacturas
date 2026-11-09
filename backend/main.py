"""Punto de entrada de FastAPI y registro de routers."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from database import (
    inicializar_bd,
    inicializar_bd_usuarios,
    inicializar_bd_admin,
    inicializar_bd_catalogo,
)
from routers.facturas import router as facturas_router
from routers.usuarios import router as usuarios_router
from routers.ia import router as ia_router
from routers.ocr import router as ocr_router
from routers.catalogo import router as catalogo_router
from routers.finanzas import router as finanzas_router

FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Sistema de Facturas",
    description="API para registrar y administrar facturas.",
    version="1.0.0"
)

# Inicializa las tablas antes de registrar las rutas.
inicializar_bd_usuarios()
inicializar_bd()
inicializar_bd_admin()
inicializar_bd_catalogo()

# Configura sesiones firmadas y su política de cookies.
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
app.include_router(ia_router)
app.include_router(ocr_router)
app.include_router(catalogo_router)
app.include_router(finanzas_router)


@app.get("/", include_in_schema=False)
def inicio():
    """Sirve la página principal de la aplicación."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def verificar_estado():
    """Confirma que la API está disponible."""
    return {
        "mensaje": "API de facturas funcionando",
        "version": "1.0.0"
    }
