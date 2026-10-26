from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import inicializar_bd
from routers.facturas import router as facturas_router


# Directorio raíz del proyecto.
BASE_DIR = Path(__file__).resolve().parent.parent

# Directorio que contiene la interfaz.
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Sistema de Facturas",
    description="API para registrar y administrar facturas.",
    version="1.0.0"
)

# Inicializa la tabla sin borrar los registros existentes.
inicializar_bd()

# Publica los archivos CSS y JavaScript.
app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)

# Registra las rutas de facturas.
app.include_router(facturas_router)


@app.get("/", include_in_schema=False)
def inicio():
    """Muestra la interfaz web."""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def verificar_estado():
    """Verifica que la API esté funcionando."""

    return {
        "mensaje": "API de facturas funcionando",
        "version": "1.0.0"
    }