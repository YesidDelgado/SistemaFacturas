
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from database import obtener_conexion, verificar_contrasena

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


class ClienteIngreso(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    identificacion: str = Field(min_length=1, max_length=50)


class AdminIngreso(BaseModel):
    user: str = Field(min_length=1, max_length=100)
    contrasena: str = Field(min_length=1, max_length=200)


@router.post("/ingresar-cliente")
def ingresar_cliente(datos: ClienteIngreso, request: Request):
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
def ingresar_admin(datos: AdminIngreso, request: Request):
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
def consultar_sesion(request: Request):
    sesion = request.session

    if not sesion.get("rol"):
        return {"autenticado": False}

    return {
        "autenticado": True,
        "rol": sesion["rol"],
        "nombre": sesion["nombre"]
    }


@router.post("/salir")
def cerrar_sesion(request: Request):
    request.session.clear()
    return {"mensaje": "Sesión cerrada correctamente."}
