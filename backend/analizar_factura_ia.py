
import json
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pathlib import Path

# Cargar las variables del archivo .env ubicado en la raíz del proyecto.

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROYECTO / ".env")

# Tipos de documentos permitidos.
TIPOS_DOCUMENTO = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


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
            "Formato no permitido. Utiliza PDF, PNG, JPG o WEBP."
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

    # Convertimos el archivo en una parte que Gemini puede analizar.
    documento = types.Part.from_bytes(
        data=contenido,
        mime_type=tipo_mime
    )

    instrucciones = """
Analiza el documento adjunto y extrae únicamente estos datos:

- cliente: nombre del cliente.
- fecha: fecha de la factura en formato YYYY-MM-DD.
- total: valor total de la factura, expresado como una cadena
  de dígitos sin puntos, comas ni símbolos de moneda.

IMPORTANTE:
- No extraigas el número de factura impreso en el documento.
- No incluyas ningún código o número de factura en la respuesta.
- Si cliente o fecha no se identifican con seguridad,
  devuelve una cadena vacía.
- Si el total no se identifica con seguridad,
  devuelve una cadena vacía.
- No inventes datos.
- Devuelve exclusivamente un JSON con las claves cliente,
  fecha y total.
"""

    # Solo solicitamos los tres campos que necesitamos.
    # El total se recibe como texto y luego se valida en Python.
    esquema = {
        "type": "OBJECT",
        "properties": {
            "cliente": {"type": "STRING"},
            "fecha": {"type": "STRING"},
            "total": {"type": "STRING"}
        },
        "required": ["cliente", "fecha", "total"]
    }

    respuesta = cliente.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            instrucciones,
            documento,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=esquema,
            temperature=0,
        ),
    )

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

    # Validamos que los campos tengan el tipo esperado.
    cliente_extraido = datos.get("cliente", "")
    fecha_extraida = datos.get("fecha", "")
    total_texto = datos.get("total", "")

    if not isinstance(cliente_extraido, str):
        cliente_extraido = ""

    if not isinstance(fecha_extraida, str):
        fecha_extraida = ""

    # El total puede llegar como texto o como número.
    # Solo aceptamos dígitos para evitar registrar valores incorrectos.
    if isinstance(total_texto, int) and not isinstance(total_texto, bool):
        total_texto = str(total_texto)

    if not isinstance(total_texto, str):
        raise ValueError(
            "Gemini devolvió un formato no válido para el total."
        )

    total_texto = total_texto.strip()

    if total_texto and not re.fullmatch(r"\d+", total_texto):
        raise ValueError(
            "No se pudo interpretar el total de la factura."
        )

    total = int(total_texto) if total_texto else None

    # No devolvemos el número de factura impreso en el documento.
    return {
        "cliente": cliente_extraido,
        "fecha": fecha_extraida,
        "total": total
    }
