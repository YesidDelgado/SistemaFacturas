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

        # Identificar errores habituales del servicio de Gemini.
        tipo_error = type(error).__name__
        mensaje_error = str(error).lower()

        if (
            "429" in mensaje_error
            or "resourceexhausted" in tipo_error.lower()
            or "quota" in mensaje_error
            or "rate limit" in mensaje_error
        ):
            codigo_http = 429
            mensaje_usuario = (
                "Se alcanzó el límite de uso de Gemini. "
                "Intenta nuevamente más tarde."
            )

        elif (
            "timeout" in tipo_error.lower()
            or "deadline" in mensaje_error
        ):
            codigo_http = 504
            mensaje_usuario = (
                "El servicio de IA tardó demasiado en responder. "
                "Intenta nuevamente."
            )

        elif (
            "503" in mensaje_error
            or "unavailable" in mensaje_error
            or "serviceunavailable" in tipo_error.lower()
            or "servererror" in tipo_error.lower()
        ):
            codigo_http = 503
            mensaje_usuario = (
                "El servicio de IA no está disponible temporalmente. "
                "Intenta nuevamente en unos minutos."
            )

        elif (
            "api key" in mensaje_error
            or "api_key" in mensaje_error
            or "unauthenticated" in mensaje_error
            or "permission_denied" in mensaje_error
        ):
            codigo_http = 502
            mensaje_usuario = (
                "No fue posible autenticar la solicitud con el "
                "servicio de IA. Revisa la configuración de Gemini."
            )

        else:
            codigo_http = 502
            mensaje_usuario = (
                "Ocurrió un error al procesar el documento con el "
                "servicio de IA. Intenta nuevamente."
            )

        raise HTTPException(
            status_code=codigo_http,
            detail=mensaje_usuario
        ) from error

    finally:
        archivo.file.close()
