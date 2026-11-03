
"""Integración con Gemini para estructurar facturas y validar totales."""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from ocr_service import _extraer_texto_docx


# Carga la configuración local sin sobrescribir variables del entorno.

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROYECTO / ".env")

# Tipos MIME aceptados por Gemini.
TIPOS_DOCUMENTO = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _convertir_numero(valor: str) -> float:
    """Convierte un importe con formato local a número decimal."""
    valor = valor.strip().replace(" ", "")
    if "," in valor and "." in valor:
        valor = valor.replace(".", "").replace(",", ".")
    elif "," in valor:
        valor = valor.replace(",", ".")
    return float(valor)


def analizar_documento_con_gemini(
    contenido: bytes,
    nombre_archivo: str
) -> dict:
    """
    Envía un PDF o una imagen a Gemini y extrae los datos
    de la factura sin registrarla en la base de datos.
    """

    extension = os.path.splitext(nombre_archivo)[1].lower()

    if extension not in TIPOS_DOCUMENTO:
        raise ValueError(
            "Formato no permitido. Utiliza PDF, DOCX, PNG, JPG o WEBP."
        )

    if not contenido:
        raise ValueError("El archivo está vacío.")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No se encontró la variable de entorno GEMINI_API_KEY."
        )

    cliente = genai.Client(api_key=api_key)
    tipo_mime = TIPOS_DOCUMENTO[extension]

    # Convierte DOCX a texto y los demás formatos a contenido multimodal.
    documento = (
        _extraer_texto_docx(contenido)
        if extension == ".docx"
        else types.Part.from_bytes(data=contenido, mime_type=tipo_mime)
    )

    # Solicita campos generales, productos y ausencia explícita de invenciones.
    instrucciones = """
Analiza el documento adjunto como una factura real y extrae estos datos:

- cliente: nombre del cliente.
- fecha: fecha de la factura en formato YYYY-MM-DD.
- total: valor total de la factura, expresado como una cadena
  de dígitos sin puntos, comas ni símbolos de moneda.
- nit_proveedor: NIT del proveedor.
- razon_social: razón social o proveedor.
- numero_factura: número impreso en el documento.
- subtotal_general: subtotal antes de impuestos.
- descuentos: descuento total.
- iva: valor total del IVA.
- iva_porcentaje: porcentaje de IVA si aparece.
- productos: lista de productos con nombre, descripción, cantidad,
  valor_unitario, subtotal, descuento e iva_porcentaje.

IMPORTANTE:
- Si un dato no aparece o no se identifica con seguridad, devuelve null.
- No inventes datos.
- Devuelve exclusivamente un JSON válido.
"""

    # Esquema estricto para que la respuesta sea JSON consistente.
    esquema = {
        "type": "OBJECT",
        "properties": {
            "cliente": {"type": "STRING"},
            "fecha": {"type": "STRING"},
            "total": {"type": "STRING"},
            "nit_proveedor": {"type": ["STRING", "NULL"]},
            "razon_social": {"type": ["STRING", "NULL"]},
            "numero_factura": {"type": ["STRING", "NULL"]},
            "subtotal_general": {"type": ["NUMBER", "NULL"]},
            "descuentos": {"type": ["NUMBER", "NULL"]},
            "iva": {"type": ["NUMBER", "NULL"]},
            "iva_porcentaje": {"type": ["NUMBER", "NULL"]},
            "productos": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "nombre": {"type": "STRING"},
                        "descripcion": {"type": ["STRING", "NULL"]},
                        "cantidad": {"type": ["NUMBER", "NULL"]},
                        "valor_unitario": {"type": ["NUMBER", "NULL"]},
                        "subtotal": {"type": ["NUMBER", "NULL"]},
                        "descuento": {"type": ["NUMBER", "NULL"]},
                        "iva_porcentaje": {"type": ["NUMBER", "NULL"]},
                    },
                    "required": ["nombre", "descripcion", "cantidad",
                                 "valor_unitario", "subtotal", "descuento",
                                 "iva_porcentaje"],
                },
            },
        },
        "required": [
            "cliente", "fecha", "total", "nit_proveedor", "razon_social",
            "numero_factura", "subtotal_general", "descuentos", "iva",
            "iva_porcentaje", "productos",
        ]
    }

    modelo_configurado = os.getenv("GEMINI_MODEL")
    modelos = [
        modelo_configurado or "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
    ]
    modelos = list(dict.fromkeys(modelos))
    configuracion = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=esquema,
        temperature=0,
    )
    ultimo_error = None
    for modelo in modelos:
        try:
            respuesta = cliente.models.generate_content(
                model=modelo,
                contents=[
                    instrucciones,
                    documento,
                ],
                config=configuracion,
            )
            break
        except Exception as error:
            mensaje_error = str(error).lower()
            if (
                "404" not in mensaje_error
                and "not_found" not in mensaje_error
                and "503" not in mensaje_error
                and "unavailable" not in mensaje_error
            ):
                raise
            ultimo_error = error
    else:
        raise RuntimeError(
            "Los modelos configurados de Gemini no están disponibles "
            "temporalmente."
        ) from ultimo_error

    if not respuesta.text:
        raise ValueError(
            "Gemini no devolvió información. Intenta con otro documento."
        )

    try:
        datos = json.loads(respuesta.text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Gemini no devolvió un JSON válido."
        ) from error

    # Normaliza los campos generales recibidos por el modelo.
    cliente_extraido = datos.get("cliente", "")
    fecha_extraida = datos.get("fecha", "")
    total_texto = datos.get("total", "")

    if not isinstance(cliente_extraido, str):
        cliente_extraido = ""

    if not isinstance(fecha_extraida, str):
        fecha_extraida = ""

    # Normaliza y valida el total antes de convertirlo.
    if isinstance(total_texto, int) and not isinstance(total_texto, bool):
        total_texto = str(total_texto)

    if not isinstance(total_texto, str):
        raise ValueError(
            "Gemini devolvió un formato no válido para el total."
        )

    total_texto = total_texto.strip()

    if total_texto and not re.fullmatch(r"\d+(?:[.,]\d{1,2})?", total_texto):
        raise ValueError(
            "No se pudo interpretar el total de la factura."
        )

    total = (
        _convertir_numero(total_texto)
        if total_texto else None
    )

    # Normaliza los importes de cada producto.
    productos = datos.get("productos")
    if not isinstance(productos, list):
        productos = []
    for producto in productos:
        if not isinstance(producto, dict):
            continue
        for campo in (
            "cantidad", "valor_unitario", "subtotal", "descuento",
            "iva_porcentaje"
        ):
            valor = producto.get(campo)
            if isinstance(valor, str):
                try:
                    producto[campo] = _convertir_numero(valor)
                except ValueError:
                    producto[campo] = None

    # Construye la respuesta común para la interfaz y la API.
    resultado = {
        "cliente": cliente_extraido,
        "fecha": fecha_extraida,
        "total": total,
        "nit_proveedor": datos.get("nit_proveedor"),
        "razon_social": datos.get("razon_social"),
        "numero_factura": datos.get("numero_factura"),
        "subtotal_general": datos.get("subtotal_general"),
        "descuentos": datos.get("descuentos"),
        "iva": datos.get("iva"),
        "iva_porcentaje": datos.get("iva_porcentaje"),
        "productos": productos,
    }
    resultado["advertencias"] = [
        "NIT y proveedor solo se muestran si aparecen en el documento."
    ]
    resultado["validacion"] = validar_totales(resultado)
    return resultado


def validar_totales(datos: dict) -> dict:
    """Compara los totales extraídos con la suma de sus productos."""
    productos = datos.get("productos") or []
    subtotal_calculado = 0.0
    impuesto_calculado = 0.0
    for producto in productos:
        cantidad = producto.get("cantidad")
        unitario = producto.get("valor_unitario")
        descuento = producto.get("descuento") or 0
        iva_porcentaje = producto.get("iva_porcentaje") or 0
        if isinstance(cantidad, (int, float)) and isinstance(unitario, (int, float)):
            subtotal = max(0, cantidad * unitario - descuento)
            subtotal_calculado += subtotal
            if isinstance(iva_porcentaje, (int, float)):
                impuesto_calculado += subtotal * iva_porcentaje / 100
    total = datos.get("total")
    diferencia = None
    if isinstance(total, (int, float)):
        diferencia = round(total - subtotal_calculado - impuesto_calculado, 2)
    return {
        "subtotal_productos_calculado": round(subtotal_calculado, 2),
        "iva_productos_calculado": round(impuesto_calculado, 2),
        "diferencia_con_total": diferencia,
        "coincide": diferencia is not None and abs(diferencia) <= 0.02,
        "origen_subtotal": "calculado",
        "origen_total": "extraido",
    }
