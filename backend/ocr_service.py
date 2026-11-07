"""Extracción de texto y campos de facturas mediante OCR local."""

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import zlib
import base64
from html import unescape
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


# Extensiones que el servicio local puede recibir.
EXTENSIONES_OCR = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
    ".pdf", ".docx",
}
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


def _buscar_tesseract() -> str | None:
    """Busca el ejecutable de Tesseract en la configuración y rutas comunes."""
    configurado = os.getenv("TESSERACT_CMD")
    candidatos = [
        configurado,
        "tesseract",
        r"C:\Users\BrandonYesidDelgadoQ\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]

    for candidato in candidatos:
        if not candidato:
            continue
        if (
            candidato == "tesseract" and shutil.which(candidato)
        ) or Path(candidato).is_file():
            return candidato

    return None


def tesseract_disponible() -> bool:
    """Indica si Tesseract está disponible para el proceso OCR."""
    return _buscar_tesseract() is not None


def _extraer_texto_docx(contenido: bytes) -> str:
    """Extrae texto legible del XML principal de un archivo DOCX."""
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(contenido)) as archivo:
            xml = archivo.read("word/document.xml").decode("utf-8")
    except (KeyError, zipfile.BadZipFile, UnicodeDecodeError) as error:
        raise ValueError("El archivo DOCX no es válido.") from error
    texto = re.sub(r"</w:p>", "\n", xml)
    texto = re.sub(r"<w:tab[^>]*/>", "\t", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = unescape(texto).replace("&#13;", "\n").strip()
    if not texto:
        raise ValueError("El documento DOCX no contiene texto legible.")
    return texto


def _extraer_texto_pdf(contenido: bytes) -> str:
    """Extrae texto de streams PDF con texto interno."""
    textos = []
    for inicio in [match.end() for match in re.finditer(rb"stream\r?\n", contenido)]:
        fin = contenido.find(b"endstream", inicio)
        if fin < 0:
            continue
        flujo = contenido[inicio:fin].strip()
        candidatos = [flujo]
        try:
            candidatos.insert(0, zlib.decompress(flujo))
        except zlib.error:
            try:
                candidatos.insert(
                    0,
                    zlib.decompress(
                        base64.a85decode(b"<~" + flujo.rstrip(b"~>") + b"~>", adobe=True)
                    ),
                )
            except (ValueError, zlib.error):
                pass
        for candidato in candidatos:
            for coincidencia in re.findall(rb"\((.*?)(?<!\\)\)\s*Tj", candidato):
                textos.append(
                    coincidencia.decode("latin-1", errors="replace")
                    .replace(r"\(", "(")
                    .replace(r"\)", ")")
                    .replace(r"\n", " ")
                )
    texto = "\n".join(textos).strip()
    if not texto:
        raise RuntimeError(
            "El PDF no contiene texto extraíble para OCR local. "
            "Usa Analizar con IA para PDF o conviértelo a imagen."
        )
    return texto


def _extraer_texto_tesseract(contenido: bytes, extension: str) -> str:
    """Preprocesa el archivo y ejecuta Tesseract para obtener su texto."""
    ejecutable = _buscar_tesseract()
    if not ejecutable:
        raise RuntimeError(
            "Tesseract no está disponible. Configura TESSERACT_CMD "
            "con la ruta de tesseract.exe."
        )
    with tempfile.TemporaryDirectory(prefix="sistema_facturas_") as carpeta:
        entrada = Path(carpeta) / f"documento{extension}"
        entrada.write_bytes(contenido)

        # Los formatos con texto se procesan sin rasterización adicional.
        if extension == ".pdf":
            return _extraer_texto_pdf(contenido)
        if extension == ".docx":
            return _extraer_texto_docx(contenido)

        # Las imágenes se normalizan antes de enviarlas a Tesseract.
        archivo_procesado = entrada
        if extension != ".pdf":
            try:
                with Image.open(entrada) as imagen:
                    imagen.verify()
            except Exception as error:
                raise ValueError("La imagen no es válida o está dañada.") from error
            with Image.open(entrada) as imagen:
                imagen = ImageOps.exif_transpose(imagen).convert("L")
                escala = 2 if max(imagen.size) < 2500 else 1
                if escala > 1:
                    imagen = imagen.resize(
                        (imagen.width * escala, imagen.height * escala),
                        Image.Resampling.LANCZOS,
                    )
                imagen = ImageEnhance.Contrast(imagen).enhance(1.6)
                imagen = imagen.filter(ImageFilter.SHARPEN)
                archivo_procesado = Path(carpeta) / "documento_procesado.png"
                imagen.save(archivo_procesado, "PNG")

        # Ejecuta Tesseract en español e inglés con una configuración estable.
        proceso = subprocess.run(
            [ejecutable, str(archivo_procesado), "stdout", "-l", "spa+eng", "--psm", "6"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )

        if proceso.returncode != 0:
            detalle = proceso.stderr.strip() or "Tesseract no pudo leer el documento."
            raise RuntimeError(detalle)

        texto = proceso.stdout.strip()
        if not texto:
            raise ValueError("No se pudo reconocer texto en el documento.")

        return texto


def _buscar_patron(texto: str, patrones: tuple[str, ...]) -> str | None:
    """Devuelve el primer valor que coincide con los patrones indicados."""
    for patron in patrones:
        coincidencia = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if coincidencia:
            return coincidencia.group(1).strip(" .:-")
    return None
    

def _extraer_proveedor(texto: str) -> str | None:
    """Obtiene el proveedor desde su etiqueta o desde la línea siguiente."""
    etiquetas = re.compile(r"(?:raz[óo]n\s+social|proveedor|empresa)", re.IGNORECASE)
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    for indice, linea in enumerate(lineas):
        coincidencia = etiquetas.search(linea)
        if not coincidencia:
            continue
        valor = linea[coincidencia.end():].strip(" \t:.-")
        valor = re.split(
            r"\s+(?=(?:NIT|fecha|factura|cliente|estado)\b)",
            valor,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        if coincidencia.start() == 0 and linea.lower().startswith("empresa"):
            valor = f"Empresa {valor}".strip()
        if valor and not re.match(r"^(?:NIT|fecha|factura|cliente)\b", valor, re.IGNORECASE):
            return valor
        if indice + 1 < len(lineas):
            siguiente = lineas[indice + 1].strip(" \t:.-")
            if siguiente and not re.match(
                r"^(?:NIT|fecha|factura|cliente)\b", siguiente, re.IGNORECASE
            ):
                return siguiente
    return None


def _convertir_importe(valor: str) -> float | None:
    """Convierte un importe con separadores de miles y decimales."""
    valor = valor.strip().replace(" ", "")
    try:
        if "," in valor and "." in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif "," in valor:
            valor = valor.replace(",", ".")
        return float(valor)
    except ValueError:
        return None


def _extraer_importe_etiquetado(texto: str, etiqueta: str) -> float | None:
    """Extrae un importe ubicado en una línea con etiqueta."""
    patron = re.compile(
        rf"^\s*{etiqueta}\b"
        r"(?:\s+(?:productos|a pagar))?"
        r"(?:\s+\d{1,2}(?:[.,]\d+)?\s*%)?"
        r"\s*[:.]?\s*\$?\s*([\d.,]+)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    coincidencia = patron.search(texto)
    return _convertir_importe(coincidencia.group(1)) if coincidencia else None


def extraer_productos_basicos(texto: str, iva_porcentaje: float | None) -> list[dict]:
    """Extrae todas las líneas de productos reconocibles del documento."""
    # Primero intenta filas completas y luego texto lineal de PDF/OCR.
    productos = []
    ignorar = ("total", "subtotal", "iva", "nit", "fecha", "factura")
    patron_tabla = re.compile(
        r"^\s*(.+?)\s+(\d+(?:[.,]\d+)?)\s+\$?\s*([\d.,]+)"
        r"\s+\$?\s*([\d.,]+)\s+(\d{1,2}(?:[.,]\d+)?)\s*%"
        r"\s+\$?\s*([\d.,]+)\s*$",
        re.IGNORECASE,
    )
    patron_simple = re.compile(
        r"^\s*(.+?)\s+(\d+(?:[.,]\d+)?)\s+\$?\s*([\d.,]+)"
        r"(?:\s+\$?\s*([\d.,]+))?\s*$",
        re.IGNORECASE,
    )
    # Reconoce una fila de tabla por línea.
    for linea in texto.splitlines():
        if any(palabra in linea.lower() for palabra in ignorar):
            continue
        coincidencia = patron_tabla.match(linea)
        es_tabla = coincidencia is not None
        if not coincidencia:
            coincidencia = patron_simple.match(linea)
        if not coincidencia:
            continue
        nombre = coincidencia.group(1).strip(" .:-")
        cantidad = _convertir_importe(coincidencia.group(2))
        unitario = _convertir_importe(coincidencia.group(3))
        descuento = _convertir_importe(coincidencia.group(4)) if es_tabla else 0
        porcentaje = _convertir_importe(coincidencia.group(5)) if es_tabla else iva_porcentaje
        subtotal_grupo = 6 if es_tabla else 4
        subtotal = (
            _convertir_importe(coincidencia.group(subtotal_grupo))
            if coincidencia.group(subtotal_grupo) else None
        )
        if not nombre or cantidad is None or unitario is None or cantidad <= 0:
            continue
        subtotal = subtotal if subtotal is not None else round(cantidad * unitario, 2)
        productos.append({
            "nombre": nombre,
            "descripcion": None,
            "cantidad": cantidad,
            "valor_unitario": unitario,
            "subtotal": subtotal,
            "descuento": descuento or 0,
            "iva_porcentaje": porcentaje,
        })
    # Conserva el resultado tabular cuando ya se detectaron productos.
    if productos:
        return productos
    # Fallback para documentos cuyo texto perdió los saltos de línea.
    texto_lineal = re.sub(r"\s+", " ", texto)
    coincidencias = re.finditer(
        r"\b(?!Producto\s*/)([A-Za-zÁÉÍÓÚáéíóúÑñ][^$]{2,80}?)\s+"
        r"(\d+(?:[.,]\d+)?)\s+\$\s*([\d.,]+)\s+\$\s*([\d.,]+)\s+"
        r"(\d{1,2}(?:[.,]\d+)?)\s*%\s+\$\s*([\d.,]+)"
        r"(?=\s+(?:[A-Za-zÁÉÍÓÚáéíóúÑñ][^$]{2,80}?\s+\d+(?:[.,]\d+)?\s+\$|Subtotal|Descuentos|IVA|TOTAL)(?:\s|$)|$)",
        texto_lineal,
        re.IGNORECASE,
    )
    productos_lineales = []
    for coincidencia in coincidencias:
        nombre = coincidencia.group(1).strip()
        nombre = re.sub(
            r"^.*?Subtotal\s+",
            "",
            nombre,
            flags=re.IGNORECASE,
        ).strip()
        nombre = re.sub(
            r"^.*?\bNIT\s*[0-9.\-\s]+\s+",
            "",
            nombre,
            flags=re.IGNORECASE,
        ).strip()
        cantidad = _convertir_importe(coincidencia.group(2))
        unitario = _convertir_importe(coincidencia.group(3))
        descuento = _convertir_importe(coincidencia.group(4)) or 0
        porcentaje = _convertir_importe(coincidencia.group(5))
        subtotal = _convertir_importe(coincidencia.group(6))
        if cantidad and unitario and subtotal is not None:
            productos_lineales.append({
                "nombre": nombre,
                "descripcion": None,
                "cantidad": cantidad,
                "valor_unitario": unitario,
                "subtotal": subtotal,
                "descuento": descuento,
                "iva_porcentaje": porcentaje,
            })
    return productos_lineales


def extraer_campos_basicos(texto: str) -> dict:
    """Extrae los campos generales mediante patrones de texto."""
    nit = _buscar_patron(
        texto,
        (
            r"\bNIT\s*[:.]?\s*([0-9][0-9.\-\s]{5,20})",
        ),
    )
    fecha = _buscar_patron(
        texto,
        (
            r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",
            r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
        ),
    )
    numero_factura = _buscar_patron(
        texto,
        (
            r"\b(FAC[-\s]+[A-Z0-9][A-Z0-9\-/]*)\b",
            r"(?:n[úu]mero\s+de\s+factura)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/]*)",
        ),
    )
    razon_social = _extraer_proveedor(texto)

    cliente = _buscar_patron(
        texto,
        (r"\bcliente\s*[:\-]?\s*(.+?)(?:\s+estado\b|$)",),
    )
    return {
        "nit": nit,
        "razon_social": razon_social,
        "numero_factura": numero_factura,
        "fecha_emision": fecha,
        "cliente": cliente,
    }


def analizar_documento_ocr(contenido: bytes, nombre_archivo: str) -> dict:
    """Procesa un documento y devuelve sus campos y productos estructurados."""
    extension = Path(nombre_archivo).suffix.lower()
    if extension not in EXTENSIONES_OCR:
        raise ValueError("Formato no permitido para OCR.")
    if not contenido:
        raise ValueError("El archivo está vacío.")

    # Extrae texto y después aplica patrones de factura.
    texto = _extraer_texto_tesseract(contenido, extension)
    campos = extraer_campos_basicos(texto)
    iva_porcentaje = _buscar_patron(
        texto,
        (r"\bIVA\s*(?:[:@\-]?\s*)?(\d{1,2}(?:[.,]\d+)?)\s*%",),
    )
    if iva_porcentaje is None:
        iva_porcentaje = _buscar_patron(
            texto,
            (r"\b(\d{1,2}(?:[.,]\d+)?)\s*%",),
        )
    iva_porcentaje_numero = _convertir_importe(iva_porcentaje) if iva_porcentaje else None
    productos = extraer_productos_basicos(texto, iva_porcentaje_numero)
    subtotal_general = _extraer_importe_etiquetado(texto, "subtotal")
    descuentos = _extraer_importe_etiquetado(texto, "descuentos")
    iva = _extraer_importe_etiquetado(texto, "iva")
    total = _extraer_importe_etiquetado(texto, "total")
    return {
        "texto": texto,
        "campos": campos,
        "datos_estructurados": {
            "cliente": campos["cliente"],
            "fecha": campos["fecha_emision"],
            "total": total,
            "nit_proveedor": campos["nit"],
            "razon_social": campos["razon_social"],
            "numero_factura": campos["numero_factura"],
            "subtotal_general": subtotal_general,
            "descuentos": descuentos,
            "iva": iva,
            "iva_porcentaje": iva_porcentaje_numero,
            "productos": productos,
            "validacion": {
                "coincide": (
                    total is not None
                    and bool(productos)
                    and abs(
                        total - sum(
                            (producto["subtotal"] or 0)
                            * (1 + (producto["iva_porcentaje"] or 0) / 100)
                            for producto in productos
                        )
                    ) <= 0.02
                ),
                "motivo": "Los valores calculados deben revisarse "
                "contra el documento original.",
            },
        },
        "origen": "extraido_por_ocr",
        "advertencias": [
            "Los campos detectados por patrones deben revisarse.",
            "Los valores no identificados se mantienen como null.",
        ],
    }
