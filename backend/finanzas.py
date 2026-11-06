"""Consultas y reportes del análisis financiero y comercial."""

import html
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from database import obtener_conexion


def _condicion_fechas(desde: str | None, hasta: str | None) -> tuple[str, tuple]:
    """Construye el filtro opcional de fechas para las consultas."""
    filtros = []
    parametros = []
    if desde:
        filtros.append("f.fecha >= ?")
        parametros.append(desde)
    if hasta:
        filtros.append("f.fecha <= ?")
        parametros.append(hasta)
    return (" AND ".join(filtros) or "1 = 1", tuple(parametros))


def obtener_analisis_financiero(
    desde: str | None = None,
    hasta: str | None = None,
) -> dict:
    """Calcula indicadores, productos y evolución mensual de ventas."""
    filtro, parametros = _condicion_fechas(desde, hasta)
    costo_unitario = (
        "COALESCE(NULLIF(d.costo_adquisicion, 0), "
        "p_id.costo_adquisicion, p_nombre.costo_adquisicion, "
        "p_precio.costo_adquisicion, 0)"
    )
    conexion = obtener_conexion()
    try:
        resumen = conexion.execute(
            f"""
            SELECT COUNT(DISTINCT f.id) AS facturas, COALESCE(SUM(d.subtotal), 0) AS ventas
            FROM facturas f
            LEFT JOIN factura_detalles d ON d.factura_id = f.id
            WHERE {filtro}
            """,
            parametros,
        ).fetchone()
        detalles = conexion.execute(
            f"""
            SELECT COALESCE(SUM(d.subtotal), 0) AS subtotal,
                   COALESCE(SUM(d.subtotal * d.iva_porcentaje / 100), 0) AS iva,
                   COALESCE(SUM(d.cantidad * {costo_unitario}), 0) AS costos
            FROM factura_detalles d
            JOIN facturas f ON f.id = d.factura_id
            LEFT JOIN productos p_id ON p_id.id = d.producto_id
            LEFT JOIN productos p_nombre ON p_nombre.nombre = d.nombre
            LEFT JOIN (
                SELECT precio, MAX(costo_adquisicion) AS costo_adquisicion
                FROM productos
                GROUP BY precio
            ) p_precio ON p_precio.precio = d.valor_unitario
            WHERE {filtro}
            """,
            parametros,
        ).fetchone()
        productos = conexion.execute(
            f"""
            SELECT d.nombre,
                   COALESCE(SUM(d.cantidad), 0) AS unidades,
                   COALESCE(SUM(d.subtotal), 0) AS ventas,
                   COALESCE(SUM(d.cantidad * {costo_unitario}), 0) AS costos,
                   COALESCE(SUM(d.subtotal - d.cantidad * {costo_unitario}), 0) AS utilidad
            FROM factura_detalles d
            JOIN facturas f ON f.id = d.factura_id
            LEFT JOIN productos p_id ON p_id.id = d.producto_id
            LEFT JOIN productos p_nombre ON p_nombre.nombre = d.nombre
            LEFT JOIN (
                SELECT precio, MAX(costo_adquisicion) AS costo_adquisicion
                FROM productos
                GROUP BY precio
            ) p_precio ON p_precio.precio = d.valor_unitario
            WHERE {filtro}
            GROUP BY d.nombre
            ORDER BY ventas DESC
            """,
            parametros,
        ).fetchall()
        mensual = conexion.execute(
            f"""
            SELECT substr(f.fecha, 1, 7) AS periodo,
                   COALESCE(SUM(d.subtotal), 0) AS ventas,
                   COALESCE(SUM(d.cantidad * {costo_unitario}), 0) AS costos
            FROM facturas f
            LEFT JOIN factura_detalles d ON d.factura_id = f.id
            LEFT JOIN productos p_id ON p_id.id = d.producto_id
            LEFT JOIN productos p_nombre ON p_nombre.nombre = d.nombre
            LEFT JOIN (
                SELECT precio, MAX(costo_adquisicion) AS costo_adquisicion
                FROM productos
                GROUP BY precio
            ) p_precio ON p_precio.precio = d.valor_unitario
            WHERE {filtro}
            GROUP BY periodo
            ORDER BY periodo
            """,
            parametros,
        ).fetchall()
        datos = {**dict(resumen), **dict(detalles)}
        ventas = float(datos["ventas"] or 0)
        costos = float(datos["costos"] or 0)
        utilidad = ventas - costos
        return {
            "resumen": {
                "facturas": int(datos["facturas"] or 0),
                "ventas": ventas,
                "subtotal": float(datos["subtotal"] or 0),
                "iva": float(datos["iva"] or 0),
                "costos": costos,
                "utilidad": utilidad,
                "perdida": abs(utilidad) if utilidad < 0 else 0,
            },
            "productos": [dict(fila) for fila in productos],
            "mensual": [dict(fila) for fila in mensual],
            "periodo": {"desde": desde, "hasta": hasta},
        }
    finally:
        conexion.close()


def _filas_reporte(datos: dict) -> list[list[str]]:
    """Convierte el análisis en filas tabulares para Excel."""
    resumen = datos["resumen"]
    filas = [
        ["Indicador", "Valor"],
        ["Facturas", str(resumen["facturas"])],
        ["Ventas", f'{resumen["ventas"]:.2f}'],
        ["Subtotal", f'{resumen["subtotal"]:.2f}'],
        ["IVA", f'{resumen["iva"]:.2f}'],
        ["Costos", f'{resumen["costos"]:.2f}'],
        ["Utilidad", f'{resumen["utilidad"]:.2f}'],
        ["Pérdida", f'{resumen["perdida"]:.2f}'],
        [],
        ["Producto", "Unidades", "Ventas", "Costos", "Utilidad"],
    ]
    filas.extend([
        [
            str(fila["nombre"]),
            str(fila["unidades"]),
            f'{float(fila["ventas"]):.2f}',
            f'{float(fila["costos"]):.2f}',
            f'{float(fila["utilidad"]):.2f}',
        ]
        for fila in datos["productos"]
    ])
    filas.extend([[], ["Periodo", "Ventas", "Costos"]])
    filas.extend([
        [str(fila["periodo"]), f'{float(fila["ventas"]):.2f}', f'{float(fila["costos"]):.2f}']
        for fila in datos["mensual"]
    ])
    return filas


def _celda_excel(valor: str) -> str:
    """Genera una celda Excel con texto inline seguro."""
    return f'<c t="inlineStr"><is><t>{html.escape(str(valor))}</t></is></c>'


def generar_excel_financiero(datos: dict) -> bytes:
    """Genera un libro XLSX con resumen, productos y periodos."""
    filas = _filas_reporte(datos)
    sheet_rows = []
    for indice, fila in enumerate(filas, 1):
        celdas = "".join(_celda_excel(valor) for valor in fila)
        sheet_rows.append(f'<row r="{indice}">{celdas}</row>')
    contenido = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as libro:
        libro.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        )
        libro.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        libro.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Análisis" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        libro.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        libro.writestr("xl/worksheets/sheet1.xml", contenido)
    return buffer.getvalue()


def generar_pdf_financiero(datos: dict) -> bytes:
    """Genera un PDF con indicadores y productos rentables o deficitarios."""
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.3 * cm, leftMargin=1.3 * cm,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, title="Informe financiero",
    )
    estilos = getSampleStyleSheet()
    resumen = datos["resumen"]
    historia = [
        Paragraph("Informe financiero y comercial", estilos["Title"]),
        Paragraph(
            f"Periodo: {datos['periodo'].get('desde') or 'Inicio'} - "
            f"{datos['periodo'].get('hasta') or 'Actual'}",
            estilos["Normal"],
        ),
        Spacer(1, 0.3 * cm),
    ]
    indicadores = [["Indicador", "Valor"]] + [
        [nombre.title(), f"$ {float(valor):,.2f}"]
        for nombre, valor in [
            ("Facturas", resumen["facturas"]),
            ("Ventas", resumen["ventas"]),
            ("IVA", resumen["iva"]),
            ("Costos", resumen["costos"]),
            ("Utilidad", resumen["utilidad"]),
            ("Pérdida", resumen["perdida"]),
        ]
    ]
    tabla_indicadores = Table(indicadores, colWidths=[8 * cm, 8 * cm])
    tabla_indicadores.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283c91")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd4ef")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    historia.append(tabla_indicadores)
    historia.append(Spacer(1, 0.35 * cm))
    productos = [["Producto", "Unidades", "Ventas", "Costos", "Utilidad"]]
    productos.extend([
        [
            fila["nombre"], str(fila["unidades"]),
            f"$ {float(fila['ventas']):,.2f}",
            f"$ {float(fila['costos']):,.2f}",
            f"$ {float(fila['utilidad']):,.2f}",
        ]
        for fila in datos["productos"]
    ])
    tabla_productos = Table(productos, colWidths=[6.5 * cm, 2 * cm, 2.7 * cm, 2.7 * cm, 2.7 * cm])
    tabla_productos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10b981")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd4ef")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    historia.append(tabla_productos)
    documento.build(historia)
    return buffer.getvalue()
