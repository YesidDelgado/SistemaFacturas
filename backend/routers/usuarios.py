
"""Endpoints de ingreso, sesión y gestión de clientes."""

import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from database import obtener_conexion, verificar_contrasena

# Router y modelos de autenticación de clientes y administradores.
router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


# Datos que identifica un cliente al ingresar al sistema.
class ClienteIngreso(BaseModel):
    """Define los datos mínimos para ingresar como cliente."""
    nombre: str = Field(min_length=1, max_length=150)
    identificacion: str = Field(min_length=1, max_length=50)


# Credenciales utilizadas para autenticar al administrador.
class AdminIngreso(BaseModel):
    """Define las credenciales de ingreso administrativo."""
    user: str = Field(min_length=1, max_length=100)
    contrasena: str = Field(min_length=1, max_length=200)


# Datos editables de un cliente existente.
class UsuarioActualizar(BaseModel):
    """Define los campos editables de un cliente."""
    nombre: str = Field(min_length=1, max_length=150)
    identificacion: str = Field(min_length=1, max_length=50)

# Verifica que la sesión tenga permisos administrativos.
def exigir_admin(request: Request):
    """Exige una sesión de administrador."""
    if request.session.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede realizar esta acción.")


@router.post("/ingresar-cliente")
# Registra o reconoce un cliente y crea su sesión.
def ingresar_cliente(datos: ClienteIngreso, request: Request):
    """Inicia sesión o registra al cliente por identificación."""
    nombre = datos.nombre.strip()
    identificacion = datos.identificacion.strip()

    if not nombre or not identificacion:
        raise HTTPException(
            status_code=422,
            detail="Ingresa el nombre y la identificación."
        )

    conexion = obtener_conexion()

    try:
        usuario = conexion.execute("""
            SELECT id, nombre
            FROM usuarios
            WHERE identificacion = ?
        """, (identificacion,)).fetchone()

        nuevo = usuario is None

        if nuevo:
            conexion.execute("""
                INSERT INTO usuarios (nombre, identificacion)
                VALUES (?, ?)
            """, (nombre, identificacion))
            conexion.commit()

            usuario = conexion.execute("""
                SELECT id, nombre
                FROM usuarios
                WHERE identificacion = ?
            """, (identificacion,)).fetchone()

        request.session.clear()
        request.session.update({
            "rol": "cliente",
            "usuario_id": usuario["id"],
            "nombre": usuario["nombre"]
        })

        return {
            "mensaje": (
                "Cliente creado correctamente."
                if nuevo else "Cliente reconocido correctamente."
            ),
            "bienvenida": (
                f"¡Bienvenido, {usuario['nombre']}! "
                "Registre sus facturas."
            ),
            "nuevo": nuevo,
            "nombre": usuario["nombre"],
            "rol": "cliente"
        }

    except sqlite3.IntegrityError:
        conexion.rollback()
        raise HTTPException(
            status_code=409,
            detail="No fue posible registrar el cliente."
        )

    finally:
        conexion.close()


@router.post("/ingresar-admin")
# Valida las credenciales y crea la sesión administrativa.
def ingresar_admin(datos: AdminIngreso, request: Request):
    """Autentica al administrador con su contraseña."""
    conexion = obtener_conexion()

    try:
        admin = conexion.execute("""
            SELECT id, user, contrasena
            FROM administradores
            WHERE user = ?
        """, (datos.user.strip(),)).fetchone()

        if (
            admin is None
            or not verificar_contrasena(
                datos.contrasena,
                admin["contrasena"]
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="Usuario o contraseña incorrectos."
            )

        request.session.clear()
        request.session.update({
            "rol": "admin",
            "admin_id": admin["id"],
            "nombre": admin["user"]
        })

        return {
            "mensaje": "Ingreso de administrador correcto.",
            "nombre": admin["user"],
            "rol": "admin"
        }

    finally:
        conexion.close()


@router.get("/sesion")
# Consulta si existe una sesión autenticada.
def consultar_sesion(request: Request):
    """Devuelve el estado de la sesión actual."""
    sesion = request.session

    if not sesion.get("rol"):
        return {"autenticado": False}

    return {
        "autenticado": True,
        "rol": sesion["rol"],
        "nombre": sesion["nombre"]
    }


@router.post("/salir")
# Elimina todos los datos de la sesión actual.
def cerrar_sesion(request: Request):
    """Cierra la sesión actual."""
    request.session.clear()
    return {"mensaje": "Sesión cerrada correctamente."}


@router.get("/listar")
# Devuelve clientes con cantidad y valor de sus facturas.
def listar_usuarios(request: Request):
    """Lista clientes y el resumen de sus facturas."""
    exigir_admin(request)
    conexion = obtener_conexion()
    try:
        filas = conexion.execute("""
            SELECT u.id, u.nombre, u.identificacion,
                   COUNT(f.id) AS cantidad_facturas,
                   COALESCE(SUM(f.total), 0) AS total_facturado
            FROM usuarios u
            LEFT JOIN facturas f ON f.usuario_id = u.id
            GROUP BY u.id, u.nombre, u.identificacion
            ORDER BY u.id DESC
        """).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


@router.get("/{usuario_id}/facturas")
# Devuelve las facturas y datos básicos de un cliente para el panel administrativo.
def listar_facturas_usuario_admin(usuario_id: int, request: Request):
    """Lista las facturas de un cliente autenticado como administrador."""
    exigir_admin(request)
    conexion = obtener_conexion()
    try:
        usuario = conexion.execute(
            "SELECT id FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        if usuario is None:
            raise HTTPException(status_code=404, detail="El usuario no existe.")
        filas = conexion.execute("""
            SELECT f.id, f.factura, f.cliente, f.fecha, f.total,
                   f.proveedor, f.nit_proveedor, u.identificacion
            FROM facturas f
            JOIN usuarios u ON u.id = f.usuario_id
            WHERE f.usuario_id = ?
            ORDER BY f.id DESC
        """, (usuario_id,)).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


@router.put("/{usuario_id}")
# Actualiza nombre e identificación de un cliente.
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    request: Request,
):
    """Actualiza los datos básicos de un cliente."""
    exigir_admin(request)
    nombre = datos.nombre.strip()
    identificacion = datos.identificacion.strip()
    if not nombre or not identificacion:
        raise HTTPException(
            status_code=422,
            detail="El nombre y la identificación no pueden estar vacíos.",
        )
    conexion = obtener_conexion()
    try:
        cursor = conexion.execute("""
            UPDATE usuarios
            SET nombre = ?, identificacion = ?
            WHERE id = ?
        """, (nombre, identificacion, usuario_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="El usuario no existe.")
        conexion.commit()
        return {"mensaje": "Usuario actualizado correctamente."}
    except sqlite3.IntegrityError as error:
        conexion.rollback()
        raise HTTPException(
            status_code=409,
            detail="La identificación ya está registrada.",
        ) from error
    finally:
        conexion.close()
