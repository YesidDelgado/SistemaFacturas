"""Endpoints administrativos para consultar e importar productos."""

import csv
import io
import sqlite3
import zipfile
from xml.etree import ElementTree

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from database import obtener_conexion
from schemas import ProductoCrear


# Router del catálogo y validación de permisos.
router = APIRouter(prefix="/catalogo", tags=["Catálogo"])


class BorradoCatalogo(BaseModel):
    """Define el alcance y confirmación de un borrado de catálogo."""

    modo: str = Field(pattern="^(todos|seleccionados)$")
    codigos: list[str] = Field(default_factory=list, max_length=500)
    confirmacion: str


def _admin(request: Request):
    """Exige una sesión de administrador para modificar el catálogo."""
    if request.session.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede usar el catálogo.")


def _guardar_productos(productos: list[dict]) -> int:
    """Inserta o actualiza productos y devuelve la cantidad procesada."""
    conexion = obtener_conexion()
    try:
        for producto in productos:
            conexion.execute("""
                INSERT INTO productos (
                    codigo, nombre, descripcion, precio, costo_adquisicion, iva_porcentaje
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(codigo) DO UPDATE SET
                    nombre=excluded.nombre, descripcion=excluded.descripcion,
                        precio=excluded.precio, costo_adquisicion=excluded.costo_adquisicion,
                        iva_porcentaje=excluded.iva_porcentaje
                """, (
                    producto["codigo"], producto["nombre"], producto.get("descripcion", ""),
                    float(producto["precio"]),
                    float(producto.get("costo_adquisicion", 0) or 0),
                    float(producto.get("iva_porcentaje", 0) or 0),
                ))
        conexion.commit()
        return len(productos)
    finally:
        conexion.close()


def _filas_xlsx(contenido: bytes) -> list[list[str]]:
    """Lee las filas de la primera hoja de un archivo XLSX."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        strings = []
        if "xl/sharedStrings.xml" in archivo.namelist():
            raiz = ElementTree.fromstring(archivo.read("xl/sharedStrings.xml"))
            strings = [
                "".join(n.text or "" for n in item.iter())
                for item in raiz
            ]
        hoja = ElementTree.fromstring(archivo.read("xl/worksheets/sheet1.xml"))
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        resultado = []
        for fila in hoja.findall(".//x:row", ns):
            valores = []
            for celda in fila.findall("x:c", ns):
                valor = celda.find("x:v", ns)
                texto = "" if valor is None else (valor.text or "")
                if celda.get("t") == "s" and texto.isdigit():
                    texto = strings[int(texto)]
                valores.append(texto)
            resultado.append(valores)
        return resultado


def _importar_tabla(contenido: bytes, nombre: str) -> list[dict]:
    """Normaliza un CSV o XLSX al formato interno del catálogo."""
    if nombre.lower().endswith(".xlsx"):
        filas = _filas_xlsx(contenido)
    else:
        filas = list(csv.reader(io.StringIO(contenido.decode("utf-8-sig"))))
    if not filas:
        raise ValueError("El archivo no contiene filas.")
    encabezados = [str(x).strip().lower() for x in filas[0]]
    requeridos = {"codigo", "nombre", "precio"}
    if not requeridos.issubset(encabezados):
        raise ValueError("El archivo debe tener columnas codigo, nombre y precio.")
    indices = {nombre: encabezados.index(nombre) for nombre in encabezados}
    resultado = []
    for fila in filas[1:]:
        if len(fila) < len(encabezados) or not any(fila):
            continue
        resultado.append({
            "codigo": fila[indices["codigo"]].strip(),
            "nombre": fila[indices["nombre"]].strip(),
            "descripcion": fila[indices["descripcion"]].strip() if "descripcion" in indices else "",
            "precio": fila[indices["precio"]].replace(",", ".").strip(),
            "costo_adquisicion": fila[indices["costo_adquisicion"]].replace(",", ".").strip()
                if "costo_adquisicion" in indices else "0",
            "iva_porcentaje": fila[indices["iva_porcentaje"]].replace(",", ".").strip()
                if "iva_porcentaje" in indices else "0",
        })
    return resultado


@router.get("/productos")
def listar_productos(request: Request):
    """Lista los productos activos para usuarios autenticados."""
    if request.session.get("rol") not in ("admin", "cliente"):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    conexion = obtener_conexion()
    try:
        return [dict(fila) for fila in conexion.execute(
            "SELECT * FROM productos WHERE activo = 1 ORDER BY nombre"
        ).fetchall()]
    finally:
        conexion.close()


@router.post("/productos")
def crear_producto(datos: ProductoCrear, request: Request):
    """Crea o actualiza un producto del catálogo."""
    _admin(request)
    try:
        cantidad = _guardar_productos([datos.model_dump()])
        return {"mensaje": "Producto guardado.", "cantidad": cantidad}
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/borrar")
def borrar_catalogo(datos: BorradoCatalogo, request: Request):
    """Borra productos seleccionados o todo el catálogo con confirmación."""
    _admin(request)
    esperado = "BORRAR TODO" if datos.modo == "todos" else "BORRAR SELECCIONADOS"
    if datos.confirmacion.strip().upper() != esperado:
        raise HTTPException(
            status_code=400,
            detail=f"Escribe exactamente «{esperado}» para confirmar.",
        )
    if datos.modo == "seleccionados" and not datos.codigos:
        raise HTTPException(status_code=400, detail="Selecciona al menos un código.")

    conexion = obtener_conexion()
    try:
        if datos.modo == "todos":
            filtro = "1 = 1"
            parametros = ()
        else:
            marcadores = ",".join("?" for _ in datos.codigos)
            filtro = f"codigo IN ({marcadores})"
            parametros = tuple(datos.codigos)
        referenciados = conexion.execute(
            f"SELECT DISTINCT producto_id FROM factura_detalles "
            f"WHERE producto_id IS NOT NULL AND producto_id IN "
            f"(SELECT id FROM productos WHERE {filtro})",
            parametros,
        ).fetchall()
        ids_protegidos = {fila["producto_id"] for fila in referenciados}
        if ids_protegidos:
            marcadores = ",".join("?" for _ in ids_protegidos)
            conexion.execute(
                f"UPDATE productos SET activo = 0 WHERE id IN ({marcadores})",
                tuple(ids_protegidos),
            )
        parametros_borrado = parametros
        eliminados = conexion.execute(
            f"DELETE FROM productos WHERE {filtro}"
            + (" AND id NOT IN (" + ",".join("?" for _ in ids_protegidos) + ")"
               if ids_protegidos else ""),
            parametros_borrado + tuple(ids_protegidos),
        ).rowcount
        conexion.commit()
        return {
            "mensaje": "Catálogo procesado.",
            "eliminados": eliminados,
            "protegidos": len(ids_protegidos),
        }
    finally:
        conexion.close()


@router.post("/importar")
def importar_catalogo(request: Request, archivo: UploadFile = File(...)):
    """Importa productos desde un archivo CSV o XLSX."""
    _admin(request)
    try:
        contenido = archivo.file.read(5 * 1024 * 1024 + 1)
        if len(contenido) > 5 * 1024 * 1024:
            raise ValueError("El archivo supera 5 MB.")
        productos = _importar_tabla(contenido, archivo.filename or "")
        cantidad = _guardar_productos(productos)
        return {"mensaje": "Catálogo importado.", "cantidad": cantidad}
    except (
        ValueError,
        KeyError,
        UnicodeDecodeError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
        sqlite3.IntegrityError,
    ) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        archivo.file.close()
