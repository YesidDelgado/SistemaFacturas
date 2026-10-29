from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from analizar_factura_ia import analizar_documento_con_gemini


router = APIRouter(
    prefix="/ia",
    tags=["Inteligencia Artificial"]
)

# Tamaño máximo permitido: 10 MB.
TAMANO_MAXIMO = 10 * 1024 * 1024

EXTENSIONES_PERMITIDAS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


@router.post("/analizar-factura")
def analizar_factura(
    request: Request,
    archivo: UploadFile = File(...)
):
    """
    Analiza un documento con Gemini.
    No registra ni modifica facturas en SQLite.
    """

    # Solo los usuarios con sesión iniciada pueden usar Gemini.
    rol = request.session.get("rol")

    if rol not in ("cliente", "admin"):
        raise HTTPException(
            status_code=401,
            detail="Debes iniciar sesión para analizar una factura."
        )

    nombre_archivo = archivo.filename or ""
    extension = nombre_archivo.rsplit(".", 1)

    if len(extension) != 2:
        raise HTTPException(
            status_code=400,
            detail="El archivo no tiene una extensión válida."
        )

    extension_archivo = "." + extension[-1].lower()

    if extension_archivo not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=400,
            detail="Formato no permitido. Usa PDF, PNG, JPG o WEBP."
        )

    try:
        # Leemos como máximo 10 MB más un byte para detectar exceso.
        contenido = archivo.file.read(TAMANO_MAXIMO + 1)

        if not contenido:
            raise HTTPException(
                status_code=400,
                detail="El archivo está vacío."
            )

        if len(contenido) > TAMANO_MAXIMO:
            raise HTTPException(
                status_code=413,
                detail="El archivo supera el límite de 10 MB."
            )

        resultado = analizar_documento_con_gemini(
            contenido=contenido,
            nombre_archivo=nombre_archivo
        )

        return {
            "mensaje": "Documento analizado. Revisa los datos antes de registrar.",
            "datos": resultado
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        ) from error

    except Exception as error:
        print(
            f"Error al analizar documento con Gemini: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "No fue posible analizar el documento con Gemini. "
                "Verifica la conexión y la configuración de la API."
            )
        ) from error

    finally:
        archivo.file.close()
