from database import obtener_conexion
from models import fila_a_diccionario


def generar_numero_factura(conexion):
    """Genera el siguiente código FAC-0001, FAC-0002, etc."""

    cursor = conexion.cursor()

    cursor.execute("""
        SELECT MAX(CAST(SUBSTR(factura, 5) AS INTEGER))
        FROM facturas
        WHERE factura GLOB 'FAC-[0-9]*'
    """)

    resultado = cursor.fetchone()
    ultimo_numero = resultado[0] or 0

    return f"FAC-{ultimo_numero + 1:04d}"


def obtener_proximo_numero_factura():
    """Consulta el código que se mostraría como siguiente."""

    conexion = obtener_conexion()

    try:
        return generar_numero_factura(conexion)

    finally:
        conexion.close()


def listar_facturas():
    """Obtiene todas las facturas."""

    conexion = obtener_conexion()

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT id, factura, cliente, fecha, total
            FROM facturas
            ORDER BY id DESC
        """)

        return [
            fila_a_diccionario(fila)
            for fila in cursor.fetchall()
        ]

    finally:
        conexion.close()


def obtener_factura(id_factura):
    """Consulta una factura por su ID interno."""

    conexion = obtener_conexion()

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT id, factura, cliente, fecha, total
            FROM facturas
            WHERE id = ?
        """, (id_factura,))

        return fila_a_diccionario(cursor.fetchone())

    finally:
        conexion.close()


def crear_factura(datos):
    """Crea la factura con un código generado por el backend."""

    conexion = obtener_conexion()

    try:
        # Bloquea las escrituras concurrentes durante la generación.
        conexion.execute("BEGIN IMMEDIATE")

        codigo = generar_numero_factura(conexion)

        cursor = conexion.cursor()

        cursor.execute("""
            INSERT INTO facturas (factura, cliente, fecha, total)
            VALUES (?, ?, ?, ?)
        """, (
            codigo,
            datos.cliente,
            datos.fecha,
            datos.total
        ))

        id_factura = cursor.lastrowid
        conexion.commit()

        return obtener_factura(id_factura)

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()


def actualizar_factura(id_factura, datos):
    """Actualiza los datos sin cambiar el código de factura."""

    conexion = obtener_conexion()

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            UPDATE facturas
            SET cliente = ?, fecha = ?, total = ?
            WHERE id = ?
        """, (
            datos.cliente,
            datos.fecha,
            datos.total,
            id_factura
        ))

        conexion.commit()

        if cursor.rowcount == 0:
            return None

        return obtener_factura(id_factura)

    finally:
        conexion.close()


def eliminar_factura(id_factura):
    """Elimina una factura por su ID interno."""

    conexion = obtener_conexion()

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            DELETE FROM facturas
            WHERE id = ?
        """, (id_factura,))

        conexion.commit()

        return cursor.rowcount > 0

    finally:
        conexion.close()