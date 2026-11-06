"""Endpoints administrativos del análisis financiero y comercial."""

from fastapi import APIRouter, HTTPException, Request, Response

from finanzas import (
    generar_excel_financiero,
    generar_pdf_financiero,
    obtener_analisis_financiero,
)

router = APIRouter(prefix="/finanzas", tags=["Finanzas"])


def _exigir_admin(request: Request):
    """Exige una sesión administrativa para consultar información financiera."""
    if request.session.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede consultar finanzas.")


def _exigir_periodo(desde: str | None, hasta: str | None):
    """Evita consultar o exportar todo el histórico sin un periodo elegido."""
    if not desde or not hasta:
        raise HTTPException(
            status_code=400,
            detail="Selecciona las fechas Desde y Hasta para consultar el análisis.",
        )
    if desde > hasta:
        raise HTTPException(status_code=400, detail="La fecha Desde no puede ser posterior a Hasta.")


@router.get("/analisis")
def analizar_finanzas(request: Request, desde: str | None = None, hasta: str | None = None):
    """Devuelve indicadores, productos y evolución mensual."""
    _exigir_admin(request)
    _exigir_periodo(desde, hasta)
    return obtener_analisis_financiero(desde, hasta)


@router.get("/reporte.pdf")
def reporte_pdf(request: Request, desde: str | None = None, hasta: str | None = None):
    """Descarga el informe financiero en PDF."""
    _exigir_admin(request)
    _exigir_periodo(desde, hasta)
    contenido = generar_pdf_financiero(obtener_analisis_financiero(desde, hasta))
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=informe-financiero.pdf"},
    )


@router.get("/reporte.xlsx")
def reporte_excel(request: Request, desde: str | None = None, hasta: str | None = None):
    """Descarga el informe financiero en Excel."""
    _exigir_admin(request)
    _exigir_periodo(desde, hasta)
    contenido = generar_excel_financiero(obtener_analisis_financiero(desde, hasta))
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=informe-financiero.xlsx"},
    )
