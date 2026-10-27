
import os
import sqlite3
import hashlib
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "facturas.db"


def obtener_conexion():
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


def inicializar_bd():
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

        conexion.commit()

    finally:
        conexion.close()


def inicializar_bd_usuarios():
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
