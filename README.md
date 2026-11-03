# Sistema de Facturas

Aplicación web para registrar, consultar, editar y eliminar facturas.

## Tecnologías

- Python
- FastAPI
- SQLite
- HTML
- CSS
- JavaScript

## Instalación

Desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

## OCR local

El sistema incluye el endpoint autenticado `POST /ocr/extraer` para imágenes
PNG, JPG, JPEG, WEBP, BMP y TIFF. Usa el ejecutable Tesseract instalado en
Windows y devuelve el texto completo junto con campos básicos detectados por
patrones. Los campos no reconocidos se devuelven como `null`; el OCR no
registra ni modifica facturas.

Si Tesseract no está en una ruta estándar, configura `TESSERACT_CMD` con la
ruta completa a `tesseract.exe`. El análisis actual de Gemini en
`POST /ia/analizar-factura` se conserva para PDF e imágenes. El OCR local de
PDF escaneado requiere adicionalmente un rasterizador PDF, que no forma parte
del entorno actual.

## Productos y facturas detalladas

El administrador dispone de un catálogo en la interfaz. Puede crear productos
individualmente o importar un archivo CSV/XLSX con las columnas `codigo`,
`nombre`, `descripcion` opcional, `precio` e `iva_porcentaje` opcional.
Las facturas pueden incluir líneas con cantidad, valor unitario, descuento e
IVA. El backend calcula cada subtotal y rechaza una factura detallada si la
suma de productos más impuestos no coincide con el total enviado.