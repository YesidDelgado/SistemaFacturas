"""Transformaciones entre filas SQLite y respuestas de la API."""

def fila_a_diccionario(fila):
    """Convierte una fila de SQLite en un diccionario."""

    if fila is None:
        return None

    return {
        "id": fila["id"],
        "factura": fila["factura"],
        "cliente": fila["cliente"],
        "fecha": fila["fecha"],
        "total": fila["total"],
        "usuario_id": fila["usuario_id"] if "usuario_id" in fila.keys() else None,
        "proveedor": fila["proveedor"] if "proveedor" in fila.keys() else None,
        "nit_proveedor": fila["nit_proveedor"] if "nit_proveedor" in fila.keys() else None,
        "identificacion": fila["identificacion"] if "identificacion" in fila.keys() else None,
    }