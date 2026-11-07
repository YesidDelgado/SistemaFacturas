# Sistema de Facturación

Aplicación web desarrollada con Python y FastAPI para gestionar clientes, administradores, productos y facturas. Integra una base de datos SQLite, generación de documentos PDF, reconocimiento óptico de caracteres (OCR) e inteligencia artificial mediante Gemini para analizar y estructurar información de facturas.

El sistema permite registrar y consultar facturas, administrar productos, procesar documentos individuales y masivos, revisar la información extraída y validar los datos antes de registrarlos.

## Tecnologías utilizadas

- Python 3.13
- FastAPI
- SQLite
- HTML5
- CSS3
- JavaScript
- Tesseract OCR
- Gemini API
- Google Gen AI SDK (`google-genai`)
- ReportLab
- OpenPyXL
- PyMuPDF

## Funcionalidades

### 1. Gestión de usuarios

- Acceso de clientes mediante nombre e identificación.
- Acceso de administradores mediante usuario y contraseña.
- Gestión de sesiones.
- Control de funcionalidades según el rol del usuario.

### 2. Gestión de facturas

- Registro de facturas.
- Generación automática de códigos internos.
- Asociación de facturas con clientes.
- Consulta de información.
- Edición y eliminación según los permisos del usuario.
- Generación de documentos PDF.

### 3. Catálogo de productos

Permite administrar productos para utilizarlos en la elaboración de facturas.

- Creación individual de productos.
- Consulta de productos registrados.
- Importación de productos desde archivos CSV y XLSX.
- Gestión de códigos, nombres, descripciones, precios e impuestos.

El archivo de importación admite las siguientes columnas:

| Columna | Descripción |
|---|---|
| `codigo` | Código del producto |
| `nombre` | Nombre del producto |
| `descripcion` | Descripción opcional |
| `precio` | Precio del producto |
| `iva_porcentaje` | Porcentaje de IVA opcional |

### 4. Facturación detallada

Las facturas pueden contener diferentes líneas de productos con:

- Código y nombre del producto.
- Cantidad.
- Valor unitario.
- Descuento.
- IVA.
- Subtotal.

El backend realiza los cálculos correspondientes y valida que la suma de los productos e impuestos coincida con el total enviado.

### 5. Reconocimiento óptico de caracteres (OCR)

El sistema utiliza Tesseract OCR para reconocer texto en documentos e imágenes sin depender de inteligencia artificial generativa.

El endpoint autenticado `POST /ocr/extraer` permite procesar imágenes en los siguientes formatos:

- PNG
- JPG
- JPEG
- WEBP
- BMP
- TIFF

El procesamiento permite obtener:

- Texto completo reconocido.
- Campos básicos identificados mediante patrones.
- Valores `null` para los campos que no se reconocen.

El OCR realiza el reconocimiento de caracteres, pero no registra ni modifica facturas automáticamente.

**Nota:** el procesamiento OCR de PDF escaneados requiere adicionalmente un rasterizador PDF.

### 6. Análisis de facturas mediante inteligencia artificial

El sistema integra Gemini mediante la biblioteca `google-genai`.

El endpoint autenticado `POST /ia/analizar-factura` permite analizar documentos PDF e imágenes para identificar y estructurar información relevante de las facturas.

Los campos que se buscan identificar incluyen:

- NIT.
- Razón social o proveedor.
- Número de factura.
- Fecha de emisión.
- Productos o artículos.
- Cantidades.
- Precios unitarios.
- Subtotal.
- IVA.
- Total.

La información obtenida mediante inteligencia artificial debe revisarse antes de incorporarse a la base de datos.

### 7. Procesamiento individual y masivo de facturas

El sistema incorpora un módulo independiente mediante una ventana emergente para facilitar el procesamiento de documentos individuales y múltiples facturas.

El flujo de trabajo contempla:

1. Selección y carga de uno o varios documentos.
2. Procesamiento de los documentos mediante OCR e inteligencia artificial.
3. Extracción de información de cada factura.
4. Visualización individual de los resultados, factura por factura.
5. Revisión de los datos identificados.
6. Corrección manual de la información extraída.
7. Registro individual de las facturas verificadas.
8. Registro masivo de los documentos previamente revisados.

La información que se busca extraer incluye NIT, proveedor, fecha, productos, cantidades, precios unitarios, impuestos y total.

Este módulo funciona de manera independiente del flujo habitual de facturación, con el propósito de conservar las operaciones existentes.

## Requisitos previos

Antes de instalar el proyecto, se necesita:

- Windows 10 o superior.
- Python 3.13.
- Conexión a internet para instalar dependencias y utilizar Gemini.
- Una clave API de Gemini para las funcionalidades de inteligencia artificial.
- Tesseract OCR instalado para el reconocimiento local de imágenes.

## Instalación y configuración

### 1. Crear el entorno virtual

Desde PowerShell, ubicarse en la carpeta raíz del proyecto y ejecutar:

```powershell
python -m venv .venv
```

### 2. Instalar las dependencias

Ejecutar:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 3. Configurar la clave API de Gemini

Para utilizar las funcionalidades de inteligencia artificial es necesario obtener una clave API.

1. Ingresar a [Google AI Studio](https://aistudio.google.com/).
2. Iniciar sesión con una cuenta de Google.
3. Acceder a la sección de claves API.
4. Crear una nueva clave.
5. Copiar la clave generada.

Crear un archivo llamado `.env` en la raíz del proyecto y agregar:

```env
GEMINI_API_KEY=TU_CLAVE_API_DE_GEMINI
```

Reemplazar `TU_CLAVE_API_DE_GEMINI` por la clave real obtenida en Google AI Studio.

**Importante:** el archivo `.env` contiene información privada. No debe publicarse ni compartirse en GitHub.

### 4. Instalar Tesseract OCR desde PowerShell

Abrir PowerShell y ejecutar:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

Una vez finalizada la instalación, comprobar que Tesseract esté disponible:

```powershell
tesseract --version
```

Consultar los idiomas instalados:

```powershell
tesseract --list-langs
```

Se recomienda verificar que esté disponible el idioma español (`spa`) para reconocer correctamente documentos y facturas en español.

Si PowerShell no reconoce el comando `tesseract`, cerrar y volver a abrir la terminal. Si el problema continúa, verificar que la instalación esté incluida en la variable de entorno PATH de Windows.

El proyecto utiliza la configuración de la ruta de Tesseract definida en su código.

## Ejecución del sistema

### Opción 1. Inicio automático

Desde Windows, ejecutar el archivo:

```powershell
.\iniciar_sistema.bat
```

También se puede iniciar mediante doble clic sobre el archivo `iniciar_sistema.bat`.

Este mecanismo utiliza el entorno virtual del proyecto y prepara las dependencias necesarias según su configuración.

### Opción 2. Inicio manual

Desde la raíz del proyecto, ejecutar:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Una vez iniciado el servidor, abrir el navegador e ingresar a:

http://127.0.0.1:8000

## Documentación de la API

FastAPI proporciona documentación interactiva para consultar y probar los endpoints disponibles.

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

Desde Swagger se pueden consultar los servicios, métodos HTTP, parámetros y respuestas de la API.

### Endpoints de procesamiento documental

| Método | Endpoint | Funcionalidad |
|---|---|---|
| POST | `/ocr/extraer` | Reconocimiento de texto mediante OCR local. |
| POST | `/ia/analizar-factura` | Análisis de documentos mediante Gemini. |

Los endpoints requieren la autenticación y los permisos definidos por el sistema.

## Base de datos

El proyecto utiliza SQLite para almacenar la información de clientes, usuarios, facturas y productos, de acuerdo con los modelos implementados.

La inicialización y las operaciones de persistencia se gestionan desde el backend.

La información obtenida mediante OCR o inteligencia artificial debe pasar por el proceso de revisión correspondiente antes de registrarse.

## Seguridad y buenas prácticas

- Mantener las claves API fuera del código fuente.
- No publicar el archivo `.env`.
- No compartir credenciales ni información privada.
- Mantener el entorno virtual fuera del repositorio.
- Revisar los datos extraídos antes de registrar facturas.
- Utilizar una clave de sesión segura cuando la aplicación lo requiera.

Se recomienda incluir en `.gitignore`:

```gitignore
.venv/
venv/
__pycache__/
*.py[cod]
.env
.env.*
!.env.example
backend/facturas.db
backend/facturas.db-*
```

## Consideraciones

- La precisión del OCR depende de la calidad y legibilidad de los documentos.
- La inteligencia artificial puede generar resultados que requieren validación manual.
- Los campos no identificados correctamente deben revisarse antes del registro.
- El análisis documental y el registro de facturas son procesos diferentes.
- El procesamiento OCR de PDF escaneados requiere herramientas adicionales para convertir las páginas en imágenes.

## Objetivo del proyecto

Desarrollar una solución de facturación que integre Python, automatización, reconocimiento óptico de caracteres e inteligencia artificial para facilitar la gestión de facturas, el procesamiento documental y la extracción de información comercial mediante una aplicación web.