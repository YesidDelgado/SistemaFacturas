from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def formatear_pesos(valor):
    """150000 -> $ 150.000"""
    return "$ " + f"{valor:,.0f}".replace(",", ".")


def generar_pdf_factura(factura):
    """Devuelve el PDF de una factura en bytes."""

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    # Banda superior
    pdf.setFillColor(colors.HexColor("#3cbea9"))
    pdf.rect(0, alto - 4 * cm, ancho, 4 * cm, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(2 * cm, alto - 2.2 * cm, "Sistema de Facturas")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(2 * cm, alto - 3.1 * cm, f"Factura {factura['factura']}")

    # Datos de la factura
    datos = [
        ("Código", factura["factura"]),
        ("Cliente", factura["cliente"]),
        ("Fecha", factura["fecha"]),
        ("Total", formatear_pesos(factura["total"])),
    ]

    pdf.setFillColor(colors.black)
    y = alto - 6 * cm

    for etiqueta, valor in datos:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(2 * cm, y, f"{etiqueta}:")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(6 * cm, y, str(valor))
        y -= 1 * cm

    # Línea y pie de página
    pdf.setStrokeColor(colors.lightgrey)
    pdf.line(2 * cm, y - 0.5 * cm, ancho - 2 * cm, y - 0.5 * cm)

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.setFillColor(colors.grey)
    pdf.drawString(2 * cm, 2 * cm, "Documento generado por el Sistema de Facturas")

    pdf.showPage()
    pdf.save()

    return buffer.getvalue()