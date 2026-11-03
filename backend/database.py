
"""Conexiones, seguridad de contraseñas y migraciones SQLite."""

import os
import sqlite3
import hashlib
import secrets
from pathlib import Path

# Ubicación única de la base de datos del sistema.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "facturas.db"


def obtener_conexion():
    """Abre una conexión SQLite con filas accesibles por nombre."""
    conexion = sqlite3.connect(DB_PATH, timeout=10)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def generar_hash(contrasena):
    """Guarda la contraseña mediante PBKDF2, no como texto plano."""
    sal = secrets.token_hex(16)
    resultado = hashlib.pbkdf2_hmac(
        "sha256",
        contrasena.encode("utf-8"),
        sal.encode("utf-8"),
        600000
    ).hex()
    return f"{sal}${resultado}"


def verificar_contrasena(contrasena, hash_guardado):
    """Comprueba una contraseña contra su hash."""
    try:
        sal, resultado_guardado = hash_guardado.split("$", 1)
        resultado = hashlib.pbkdf2_hmac(
            "sha256",
            contrasena.encode("utf-8"),
            sal.encode("utf-8"),
            600000
        ).hex()
        return secrets.compare_digest(resultado, resultado_guardado)
    except (ValueError, AttributeError):
        return False


# Creación y actualización de las tablas relacionadas con facturas.
def inicializar_bd():
    """Crea y actualiza las tablas principales de facturas."""
    conexion = obtener_conexion()

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura TEXT NOT NULL UNIQUE,
                cliente TEXT NOT NULL,
                fecha TEXT NOT NULL,
                total REAL NOT NULL CHECK (total >= 0)
            )
        """)

        columnas = {
            fila["name"]
            for fila in conexion.execute(
                "PRAGMA table_info(facturas)"
            ).fetchall()
        }

        # Vincula las facturas nuevas con el cliente que las registra.
        # Las facturas anteriores se conservan.
        if "usuario_id" not in columnas:
            conexion.execute("""
                ALTER TABLE facturas
                ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)
            """)
        if "nit_proveedor" not in columnas:
            conexion.execute("""
                ALTER TABLE facturas ADD COLUMN nit_proveedor TEXT
            """)
        if "proveedor" not in columnas:
            conexion.execute("""
                ALTER TABLE facturas ADD COLUMN proveedor TEXT
            """)

        conexion.commit()

    finally:
        conexion.close()


def inicializar_bd_usuarios():
    """Crea la tabla de clientes si todavía no existe."""
    conexion = obtener_conexion()

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                identificacion TEXT NOT NULL UNIQUE
            )
        """)
        conexion.commit()

    finally:
        conexion.close()


def inicializar_bd_admin():
    """Crea la tabla de administradores y el administrador configurado."""
    conexion = obtener_conexion()

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS administradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL UNIQUE,
                contrasena TEXT NOT NULL
            )
        """)

        # El primer administrador se configura mediante variables
        # de entorno. No se crea una cuenta con contraseña pública.
        usuario = os.getenv("ADMIN_USER")
        contrasena = os.getenv("ADMIN_PASSWORD")

        if usuario and contrasena:
            existente = conexion.execute(
                "SELECT id FROM administradores WHERE user = ?",
                (usuario,)
            ).fetchone()

            if existente is None:
                conexion.execute("""
                    INSERT INTO administradores (user, contrasena)
                    VALUES (?, ?)
                """, (usuario, generar_hash(contrasena)))

            # No se cambia automáticamente la contraseña existente.

        conexion.commit()

    finally:
        conexion.close()


def inicializar_bd_catalogo():
    """Crea las tablas de productos y detalles de factura."""
    conexion = obtener_conexion()

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                precio REAL NOT NULL CHECK (precio >= 0),
                iva_porcentaje REAL NOT NULL DEFAULT 0 CHECK (
                    iva_porcentaje >= 0 AND iva_porcentaje <= 100
                ),
                activo INTEGER NOT NULL DEFAULT 1
            )
        """)
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS factura_detalles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura_id INTEGER NOT NULL REFERENCES facturas(id)
                    ON DELETE CASCADE,
                producto_id INTEGER REFERENCES productos(id),
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                cantidad REAL NOT NULL CHECK (cantidad > 0),
                valor_unitario REAL NOT NULL CHECK (valor_unitario >= 0),
                descuento REAL NOT NULL DEFAULT 0 CHECK (descuento >= 0),
                iva_porcentaje REAL NOT NULL DEFAULT 0 CHECK (
                    iva_porcentaje >= 0 AND iva_porcentaje <= 100
                ),
                subtotal REAL NOT NULL CHECK (subtotal >= 0)
            )
        """)
        conexion.commit()
    finally:
        conexion.close()
