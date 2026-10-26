from fastapi import APIRouter, HTTPException, Response, status

from schemas import FacturaCrear, FacturaActualizar, FacturaRespuesta

from crud import (
    listar_facturas,
    obtener_factura,
    obtener_proximo_numero_factura,
    crear_factura,
    actualizar_factura,
    eliminar_factura,
)
from reportes import generar_pdf_factura

router = APIRouter(
    prefix="/facturas",
    tags=["Facturas"]
)


@router.get("/proximo-codigo")
def consultar_proximo_codigo():
    """Devuelve el próximo código para mostrarlo en el formulario."""

    return {
        "factura": obtener_proximo_numero_factura()
    }


@router.get("", response_model=list[FacturaRespuesta])
def consultar_facturas():
    """Lista todas las facturas."""

    return listar_facturas()


@router.get("/{id_factura}", response_model=FacturaRespuesta)
def consultar_una_factura(id_factura: int):
    """Consulta una factura por su ID interno."""

    factura = obtener_factura(id_factura)

    if factura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )

    return factura

@router.get("/{id_factura}/pdf")
def generar_pdf(id_factura: int, descargar: bool = False):
    """Genera el PDF de una factura (ver o descargar)."""

    factura = obtener_factura(id_factura)

    if factura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )

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
def registrar_factura(datos: FacturaCrear):
    """Registra una factura con código automático."""

    try:
        return crear_factura(datos)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la factura."
        )


@router.put("/{id_factura}", response_model=FacturaRespuesta)
def modificar_factura(
    id_factura: int,
    datos: FacturaActualizar
):
    """Actualiza cliente, fecha y total."""

    factura = actualizar_factura(id_factura, datos)

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
def borrar_factura(id_factura: int):
    """Elimina una factura."""

    eliminada = eliminar_factura(id_factura)

    if not eliminada:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La factura no existe."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)