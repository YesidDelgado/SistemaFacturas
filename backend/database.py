import sqlite3
from pathlib import Path

# Ruta de la base de datos.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "facturas.db"


def obtener_conexion():
    """Crea y devuelve una conexión a SQLite."""

    conexion = sqlite3.connect(DB_PATH, timeout=10)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")

    return conexion


def inicializar_bd():
    """Crea la tabla si todavía no existe."""

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

        conexion.commit()

    finally:
        conexion.close()