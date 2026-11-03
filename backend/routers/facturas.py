"""Endpoints para registrar, consultar, editar e imprimir facturas."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from schemas import FacturaCrear, FacturaActualizar, FacturaRespuesta

from crud import (
    listar_facturas,
    obtener_factura,
    obtener_proximo_numero_factura,
    crear_factura,
    actualizar_factura,
    eliminar_factura,
    obtener_detalles_factura,
    listar_facturas_usuario,
)
from reportes import generar_pdf_factura

# Router principal de facturación.
router = APIRouter(
    prefix="/facturas",
    tags=["Facturas"]
)


def exigir_acceso_factura(request: Request, factura):
    """Valida la sesión y la pertenencia de una factura al cliente."""
    rol = request.session.get("rol")
    if rol not in ("admin", "cliente"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    if rol == "cliente" and factura.get("usuario_id") != request.session.get("usuario_id"):
        raise HTTPException(status_code=403, detail="No puedes modificar esta factura.")


@router.get("/proximo-codigo")
def consultar_proximo_codigo():
    """Devuelve el próximo código para mostrarlo en el formulario."""

    return {
        "factura": obtener_proximo_numero_factura()
    }


@router.get("", response_model=list[FacturaRespuesta])
def consultar_facturas(request: Request):
    """Lista todas las facturas."""

    if request.session.get("rol") not in ("admin", "cliente"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    if request.session.get("rol") == "cliente":
        usuario_id = request.session.get("usuario_id")
        if not usuario_id:
            raise HTTPException(status_code=401, detail="Sesión de cliente inválida.")
        return listar_facturas_usuario(usuario_id)
    return listar_facturas()


@router.get("/mis-facturas", response_model=list[FacturaRespuesta])
def consultar_mis_facturas(request: Request):
    """Lista únicamente las facturas del cliente autenticado."""
    usuario_id = request.session.get("usuario_id")
    if request.session.get("rol") != "cliente" or not usuario_id:
        raise HTTPException(
            status_code=403,
            detail="Solo un cliente puede consultar sus facturas.",
        )
    return listar_facturas_usuario(usuario_id)


@router.get("/{id_factura}/detalles")
def consultar_detalles(id_factura: int, request: Request):
    """Devuelve los productos de una factura autorizada."""
    if request.session.get("rol") not in ("cliente", "admin"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    factura = obtener_factura(id_factura)
    if factura is None:
        raise HTTPException(status_code=404, detail="La factura no existe.")
    if (
        request.session.get("rol") == "cliente"
        and factura.get("usuario_id") != request.session.get("usuario_id")
    ):
        raise HTTPException(status_code=403, detail="No puedes consultar esta factura.")
    return obtener_detalles_factura(id_factura)


@router.get("/{id_factura}", response_model=FacturaRespuesta)
def consultar_una_factura(id_factura: int, request: Request):
    """Consulta una factura por su ID interno."""

    factura = obtener_factura(id_factura)

    if factura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )
    if request.session.get("rol") not in ("admin", "cliente"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    if (
        request.session.get("rol") == "cliente"
        and factura.get("usuario_id") != request.session.get("usuario_id")
    ):
        raise HTTPException(status_code=403, detail="No puedes consultar esta factura.")

    return factura

@router.get("/{id_factura}/pdf")
def generar_pdf(
    id_factura: int,
    request: Request,
    descargar: bool = False,
):
    """Genera el PDF de una factura (ver o descargar)."""

    factura = obtener_factura(id_factura)

    if factura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )

    rol = request.session.get("rol")
    if rol not in ("admin", "cliente"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    if rol == "cliente" and factura.get("usuario_id") != request.session.get("usuario_id"):
        raise HTTPException(status_code=403, detail="No puedes imprimir esta factura.")

    factura["detalles"] = obtener_detalles_factura(id_factura)
    contenido = generar_pdf_factura(factura)

    # inline = se abre en el navegador; attachment = se descarga
    modo = "attachment" if descargar else "inline"

    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'{modo}; filename="{factura["factura"]}.pdf"'
        }
    )

@router.post(
    "",
    response_model=FacturaRespuesta,
    status_code=status.HTTP_201_CREATED
)
def registrar_factura(datos: FacturaCrear, request: Request):
    """Registra una factura con código automático."""

    if request.session.get("rol") not in ("admin", "cliente"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    usuario_id = (
        request.session.get("usuario_id")
        if request.session.get("rol") == "cliente"
        else None
    )
    try:
        return crear_factura(datos, usuario_id=usuario_id)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la factura."
        ) from error


@router.put("/{id_factura}", response_model=FacturaRespuesta)
def modificar_factura(
    id_factura: int,
    datos: FacturaActualizar,
    request: Request,
):
    """Actualiza cliente, fecha y total."""

    factura_actual = obtener_factura(id_factura)
    if factura_actual is None:
        raise HTTPException(status_code=404, detail="La factura no existe.")
    exigir_acceso_factura(request, factura_actual)
    try:
        factura = actualizar_factura(id_factura, datos)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if factura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )

    return factura


@router.delete(
    "/{id_factura}",
    status_code=status.HTTP_204_NO_CONTENT
)
def borrar_factura(id_factura: int, request: Request):
    """Elimina una factura."""

    factura = obtener_factura(id_factura)
    if factura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )
    exigir_acceso_factura(request, factura)
    eliminada = eliminar_factura(id_factura)

    if not eliminada:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)