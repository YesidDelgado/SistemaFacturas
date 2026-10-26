def fila_a_diccionario(fila):
    """Convierte una fila de SQLite en un diccionario."""

    if fila is None:
        return None

    return {
        "id": fila["id"],
        "factura": fila["factura"],
        "cliente": fila["cliente"],
        "fecha": fila["fecha"],
        "total": fila["total"]
    }