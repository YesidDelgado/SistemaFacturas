"""Consultas y reportes del análisis financiero y comercial."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
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


def _formatear_columnas(hoja) -> None:
    """Aplica formato común a las hojas tabulares del libro."""
    encabezado = PatternFill("solid", fgColor="283C91")
    for celda in hoja[1]:
        celda.fill = encabezado
        celda.font = Font(color="FFFFFF", bold=True)
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    for columna in range(1, hoja.max_column + 1):
        hoja.column_dimensions[get_column_letter(columna)].width = 22
    for fila in hoja.iter_rows():
        for celda in fila:
            celda.alignment = Alignment(vertical="center")


def generar_excel_financiero(datos: dict) -> bytes:
    """Genera un libro XLSX con hojas, formato y gráficos del análisis."""
    libro = Workbook()
    resumen_hoja = libro.active
    resumen_hoja.title = "Resumen"
    resumen = datos["resumen"]
    resumen_hoja.append(["Informe financiero y comercial", None])
    resumen_hoja.append(["Periodo", f"{datos['periodo'].get('desde') or 'Inicio'} - {datos['periodo'].get('hasta') or 'Actual'}"])
    resumen_hoja.append([])
    resumen_hoja.append(["Indicador", "Valor"])
    for nombre, valor in [
        ("Facturas", resumen["facturas"]), ("Ventas", resumen["ventas"]),
        ("Subtotal", resumen["subtotal"]), ("IVA", resumen["iva"]),
        ("Costos", resumen["costos"]), ("Utilidad", resumen["utilidad"]),
        ("Pérdida", resumen["perdida"]),
    ]:
        resumen_hoja.append([nombre, float(valor)])
    resumen_hoja["A1"].font = Font(size=16, bold=True, color="283C91")
    resumen_hoja["A4"].fill = PatternFill("solid", fgColor="283C91")
    resumen_hoja["B4"].fill = PatternFill("solid", fgColor="283C91")
    resumen_hoja["A4"].font = Font(color="FFFFFF", bold=True)
    resumen_hoja["B4"].font = Font(color="FFFFFF", bold=True)
    for fila in resumen_hoja.iter_rows(min_row=5, min_col=2, max_col=2):
        fila[0].number_format = '$#,##0.00'

    productos_hoja = libro.create_sheet("Productos")
    productos_hoja.append(["Producto", "Unidades", "Ventas", "Costos", "Utilidad"])
    for fila in datos["productos"]:
        productos_hoja.append([
            str(fila["nombre"]), float(fila["unidades"]), float(fila["ventas"]),
            float(fila["costos"]), float(fila["utilidad"]),
        ])
    periodos_hoja = libro.create_sheet("Periodos")
    periodos_hoja.append(["Periodo", "Ventas", "Costos", "Utilidad"])
    for fila in datos["mensual"]:
        periodos_hoja.append([
            str(fila["periodo"]), float(fila["ventas"]), float(fila["costos"]),
            float(fila["ventas"]) - float(fila["costos"]),
        ])
    _formatear_columnas(productos_hoja)
    _formatear_columnas(periodos_hoja)
    for hoja in (productos_hoja, periodos_hoja):
        for fila in hoja.iter_rows(min_row=2, min_col=2):
            for celda in fila:
                celda.number_format = '$#,##0.00'
    for fila in productos_hoja.iter_rows(min_row=2, min_col=2, max_col=2):
        fila[0].number_format = '0.00'

    if productos_hoja.max_row > 1:
        grafico = BarChart()
        grafico.type = "bar"
        grafico.style = 10
        grafico.title = "Ventas, costos y utilidad por producto"
        grafico.add_data(Reference(productos_hoja, min_col=3, max_col=5, min_row=1, max_row=productos_hoja.max_row), titles_from_data=True)
        grafico.set_categories(Reference(productos_hoja, min_col=1, min_row=2, max_row=productos_hoja.max_row))
        grafico.height = 8
        grafico.width = 15
        resumen_hoja.add_chart(grafico, "D4")
    if periodos_hoja.max_row > 1:
        grafico = BarChart()
        grafico.style = 11
        grafico.title = "Ventas, costos y utilidad por periodo"
        grafico.add_data(Reference(periodos_hoja, min_col=2, max_col=4, min_row=1, max_row=periodos_hoja.max_row), titles_from_data=True)
        grafico.set_categories(Reference(periodos_hoja, min_col=1, min_row=2, max_row=periodos_hoja.max_row))
        grafico.height = 8
        grafico.width = 15
        resumen_hoja.add_chart(grafico, "D20")
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _grafico_pdf(titulo: str, etiquetas: list[str], valores: list[float], color: str) -> Drawing:
    """Construye un gráfico de barras compatible con ReportLab."""
    dibujo = Drawing(500, 220)
    grafico = VerticalBarChart()
    grafico.x = 45
    grafico.y = 35
    grafico.height = 150
    grafico.width = 430
    grafico.valueAxis.valueMin = 0
    grafico.valueAxis.valueMax = max(max(valores, default=0) * 1.15, 1)
    grafico.valueAxis.valueStep = grafico.valueAxis.valueMax / 5
    grafico.categoryAxis.labels.boxAnchor = "ne"
    grafico.categoryAxis.labels.angle = 35
    grafico.categoryAxis.categoryNames = etiquetas
    grafico.data = [valores or [0]]
    grafico.bars[0].fillColor = colors.HexColor(color)
    dibujo.add(grafico)
    dibujo.add(String(45, 205, titulo, fontSize=11, fontName="Helvetica-Bold"))
    return dibujo


def generar_pdf_financiero(datos: dict) -> bytes:
    """Genera un PDF con indicadores, tablas y gráficos integrados."""
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
            f"{datos['periodo'].get('hasta') or 'Actual'}", estilos["Normal"],
        ),
        Spacer(1, 0.3 * cm),
    ]
    indicadores = [["Indicador", "Valor"]] + [
        [nombre.title(), f"$ {float(valor):,.2f}"]
        for nombre, valor in [
            ("Facturas", resumen["facturas"]), ("Ventas", resumen["ventas"]),
            ("IVA", resumen["iva"]), ("Costos", resumen["costos"]),
            ("Utilidad", resumen["utilidad"]), ("Pérdida", resumen["perdida"]),
        ]
    ]
    tabla_indicadores = Table(indicadores, colWidths=[8 * cm, 8 * cm])
    tabla_indicadores.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283c91")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd4ef")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    historia.extend([tabla_indicadores, Spacer(1, 0.35 * cm)])
    historia.append(_grafico_pdf(
        "Ventas y utilidad por producto",
        [str(fila["nombre"])[:18] for fila in datos["productos"][:10]],
        [float(fila["ventas"]) for fila in datos["productos"][:10]],
        "#283c91",
    ))
    historia.append(_grafico_pdf(
        "Ventas y costos por periodo",
        [str(fila["periodo"]) for fila in datos["mensual"]],
        [float(fila["ventas"]) for fila in datos["mensual"]],
        "#10b981",
    ))
    productos = [["Producto", "Unidades", "Ventas", "Costos", "Utilidad"]]
    productos.extend([
        [fila["nombre"], str(fila["unidades"]), f"$ {float(fila['ventas']):,.2f}",
         f"$ {float(fila['costos']):,.2f}", f"$ {float(fila['utilidad']):,.2f}"]
        for fila in datos["productos"]
    ])
    tabla_productos = Table(productos, colWidths=[6.5 * cm, 2 * cm, 2.7 * cm, 2.7 * cm, 2.7 * cm], repeatRows=1)
    tabla_productos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10b981")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd4ef")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    historia.append(tabla_productos)
    documento.build(historia)
    return buffer.getvalue()
