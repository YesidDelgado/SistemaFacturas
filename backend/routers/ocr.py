"""Endpoint autenticado para ejecutar OCR local."""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from ocr_service import analizar_documento_ocr


# Router y límite común para archivos OCR.
router = APIRouter(prefix="/ocr", tags=["OCR"])
TAMANO_MAXIMO = 10 * 1024 * 1024


@router.post("/extraer")
def extraer_ocr(
    request: Request,
    archivo: UploadFile = File(...),
):
    """Extrae y estructura los datos de un documento mediante OCR local."""
    if request.session.get("rol") not in ("cliente", "admin"):
        raise HTTPException(
            status_code=401,
            detail="Debes iniciar sesión para usar el OCR.",
        )

    try:
        contenido = archivo.file.read(TAMANO_MAXIMO + 1)
        if not contenido:
            raise HTTPException(status_code=400, detail="El archivo está vacío.")
        if len(contenido) > TAMANO_MAXIMO:
            raise HTTPException(status_code=413, detail="El archivo supera 10 MB.")

        return {
            "mensaje": "OCR completado. Revisa los campos detectados.",
            "datos": analizar_documento_ocr(contenido, archivo.filename or ""),
        }
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        archivo.file.close()
