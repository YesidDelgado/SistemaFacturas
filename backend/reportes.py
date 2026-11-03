"""Generación del PDF estructurado de una factura."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def formatear_pesos(valor):
    """Formatea valores monetarios en pesos colombianos."""
    return "$ " + f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def generar_pdf_factura(factura):
    """Genera una factura PDF legible, tabular y lista para imprimir."""
    # Configuración base del documento y estilos visuales.
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
        title=f"Factura {factura['factura']}",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "FacturaTitulo", parent=estilos["Title"], fontSize=20,
        textColor=colors.HexColor("#283c91"), alignment=TA_CENTER,
        spaceAfter=4,
    )
    etiqueta = ParagraphStyle(
        "FacturaEtiqueta", parent=estilos["Normal"], fontSize=8,
        textColor=colors.HexColor("#5d668c"),
    )
    valor = ParagraphStyle(
        "FacturaValor", parent=estilos["Normal"], fontSize=10,
    )
    derecha = ParagraphStyle(
        "FacturaDerecha", parent=valor, alignment=TA_RIGHT,
    )
    historia = []
    historia.append(Paragraph("SISTEMAFACTURAS", titulo))
    historia.append(Paragraph("FACTURA DE VENTA", ParagraphStyle(
        "FacturaSubtitulo", parent=titulo, fontSize=11, textColor=colors.black,
    )))
    historia.append(Spacer(1, 0.25 * cm))

    # Cabecera con proveedor, cliente, número y fecha.
    datos = [
        [Paragraph("<b>Proveedor</b>", etiqueta), Paragraph(str(factura.get("proveedor") or "No informado"), valor),
         Paragraph("<b>NIT</b>", etiqueta), Paragraph(str(factura.get("nit_proveedor") or "No informado"), valor)],
        [Paragraph("<b>Número de factura</b>", etiqueta), Paragraph(str(factura["factura"]), valor),
         Paragraph("<b>Fecha de emisión</b>", etiqueta), Paragraph(str(factura["fecha"]), valor)],
        [Paragraph("<b>Cliente</b>", etiqueta), Paragraph(str(factura["cliente"]), valor),
         Paragraph("<b>Estado</b>", etiqueta), Paragraph("Registrada", valor)],
    ]
    datos_tabla = Table(datos, colWidths=[3.2 * cm, 6.0 * cm, 3.2 * cm, 4.0 * cm])
    datos_tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f6ff")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd4ef")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e0e3f2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    historia.append(datos_tabla)
    historia.append(Spacer(1, 0.45 * cm))

    # Tabla de productos y cálculo del resumen tributario.
    encabezados = ["Producto / descripción", "Cant.", "Valor unitario", "Desc.", "IVA", "Subtotal"]
    filas = [encabezados]
    subtotal_general = 0.0
    descuentos = 0.0
    iva_general = 0.0
    for detalle in factura.get("detalles", []):
        subtotal = float(detalle.get("subtotal") or 0)
        descuento = float(detalle.get("descuento") or 0)
        impuesto = subtotal * float(detalle.get("iva_porcentaje") or 0) / 100
        subtotal_general += subtotal
        descuentos += descuento
        iva_general += impuesto
        descripcion = str(detalle.get("nombre") or "")
        if detalle.get("descripcion"):
            descripcion += f"<br/><font size='8'>{detalle['descripcion']}</font>"
        filas.append([
            Paragraph(descripcion, valor),
            Paragraph(f"{float(detalle.get('cantidad') or 0):g}", derecha),
            Paragraph(formatear_pesos(detalle.get("valor_unitario")), derecha),
            Paragraph(formatear_pesos(descuento), derecha),
            Paragraph(f"{float(detalle.get('iva_porcentaje') or 0):g}%", derecha),
            Paragraph(formatear_pesos(subtotal), derecha),
        ])
    if len(filas) == 1:
        filas.append([Paragraph("Sin productos registrados", valor), "", "", "", "", ""])
    productos_tabla = Table(
        filas,
        colWidths=[6.5 * cm, 1.4 * cm, 2.8 * cm, 2.2 * cm, 1.4 * cm, 2.8 * cm],
        repeatRows=1,
    )
    productos_tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283c91")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd4ef")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    historia.append(productos_tabla)
    historia.append(Spacer(1, 0.35 * cm))

    # Resumen final y total registrado en la factura.
    total = float(factura.get("total") or 0)
    resumen = [
        [Paragraph("<b>Subtotal productos</b>", valor), Paragraph(formatear_pesos(subtotal_general), derecha)],
        [Paragraph("<b>Descuentos</b>", valor), Paragraph(formatear_pesos(descuentos), derecha)],
        [Paragraph("<b>IVA</b>", valor), Paragraph(formatear_pesos(iva_general), derecha)],
        [Paragraph("<b>TOTAL A PAGAR</b>", valor), Paragraph(f"<b>{formatear_pesos(total)}</b>", derecha)],
    ]
    resumen_tabla = Table(resumen, colWidths=[12.5 * cm, 4.6 * cm], hAlign="RIGHT")
    resumen_tabla.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.7, colors.HexColor("#283c91")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#283c91")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9ebff")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    historia.append(resumen_tabla)
    historia.append(Spacer(1, 0.7 * cm))
    historia.append(Paragraph(
        "Documento generado por SistemaFacturas. Verifique los datos antes de realizar el pago.",
        ParagraphStyle("Pie", parent=etiqueta, alignment=TA_CENTER),
    ))
    documento.build(historia)
    return buffer.getvalue()
