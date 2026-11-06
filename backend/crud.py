"""Operaciones de persistencia para facturas y sus detalles."""

from database import obtener_conexion
from models import fila_a_diccionario


# Generación y consulta de consecutivos de factura.
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


# Consultas generales de facturas.
def listar_facturas():
    """Obtiene todas las facturas."""

    conexion = obtener_conexion()

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT id, factura, cliente, fecha, total, usuario_id, proveedor, nit_proveedor
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
            SELECT id, factura, cliente, fecha, total, usuario_id, proveedor, nit_proveedor
            FROM facturas
            WHERE id = ?
        """, (id_factura,))

        return fila_a_diccionario(cursor.fetchone())

    finally:
        conexion.close()


# Alta, actualización y eliminación de facturas.
def crear_factura(datos, usuario_id=None):
    """Crea la factura con un código generado por el backend."""

    conexion = obtener_conexion()

    try:
        # Bloquea las escrituras concurrentes durante la generación.
        conexion.execute("BEGIN IMMEDIATE")

        codigo = generar_numero_factura(conexion)

        cursor = conexion.cursor()

        cursor.execute("""
            INSERT INTO facturas (
                factura, cliente, fecha, total, usuario_id, proveedor, nit_proveedor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            codigo,
            datos.cliente,
            datos.fecha,
            datos.total,
            usuario_id,
            datos.proveedor,
            datos.nit_proveedor,
        ))

        id_factura = cursor.lastrowid
        total_calculado = 0.0
        for detalle in datos.detalles:
            costo_adquisicion = detalle.costo_adquisicion
            if costo_adquisicion is None and detalle.producto_id:
                fila_producto = cursor.execute(
                    "SELECT costo_adquisicion FROM productos WHERE id = ?",
                    (detalle.producto_id,),
                ).fetchone()
                costo_adquisicion = (
                    float(fila_producto["costo_adquisicion"])
                    if fila_producto else 0
                )
            costo_adquisicion = float(costo_adquisicion or 0)
            subtotal = round(
                detalle.cantidad * detalle.valor_unitario
                - detalle.descuento,
                2,
            )
            if subtotal < 0:
                raise ValueError("El descuento no puede superar el subtotal.")
            total_calculado += subtotal * (1 + detalle.iva_porcentaje / 100)
            cursor.execute("""
                INSERT INTO factura_detalles (
                    factura_id, producto_id, nombre, descripcion,
                    cantidad, valor_unitario, costo_adquisicion, descuento,
                    iva_porcentaje, subtotal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_factura, detalle.producto_id, detalle.nombre,
                detalle.descripcion, detalle.cantidad, detalle.valor_unitario,
                costo_adquisicion, detalle.descuento, detalle.iva_porcentaje,
                subtotal,
            ))
        if datos.detalles and abs(total_calculado - datos.total) > 0.02:
            raise ValueError(
                "El total no coincide con la suma de productos e impuestos."
            )
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
            SET cliente = ?, fecha = ?, total = ?, proveedor = ?, nit_proveedor = ?
            WHERE id = ?
        """, (
            datos.cliente,
            datos.fecha,
            datos.total,
            datos.proveedor,
            datos.nit_proveedor,
            id_factura
        ))

        if datos.detalles:
            cursor.execute(
                "DELETE FROM factura_detalles WHERE factura_id = ?",
                (id_factura,),
            )
            total_calculado = 0.0
            for detalle in datos.detalles:
                costo_adquisicion = detalle.costo_adquisicion
                if costo_adquisicion is None and detalle.producto_id:
                    fila_producto = cursor.execute(
                        "SELECT costo_adquisicion FROM productos WHERE id = ?",
                        (detalle.producto_id,),
                    ).fetchone()
                    costo_adquisicion = (
                        float(fila_producto["costo_adquisicion"])
                        if fila_producto else 0
                    )
                costo_adquisicion = float(costo_adquisicion or 0)
                subtotal = round(
                    detalle.cantidad * detalle.valor_unitario
                    - detalle.descuento,
                    2,
                )
                if subtotal < 0:
                    raise ValueError("El descuento no puede superar el subtotal.")
                total_calculado += subtotal * (1 + detalle.iva_porcentaje / 100)
                cursor.execute("""
                    INSERT INTO factura_detalles (
                        factura_id, producto_id, nombre, descripcion,
                        cantidad, valor_unitario, costo_adquisicion, descuento,
                        iva_porcentaje, subtotal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_factura, detalle.producto_id, detalle.nombre,
                    detalle.descripcion, detalle.cantidad, detalle.valor_unitario,
                    costo_adquisicion, detalle.descuento, detalle.iva_porcentaje,
                    subtotal,
                ))
            if abs(total_calculado - datos.total) > 0.02:
                raise ValueError(
                    "El total no coincide con la suma de productos e impuestos."
                )

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


# Consultas de productos asociados y facturas por cliente.
def obtener_detalles_factura(id_factura):
    """Obtiene los productos asociados a una factura."""
    conexion = obtener_conexion()
    try:
        filas = conexion.execute("""
            SELECT id, producto_id, nombre, descripcion, cantidad,
                   valor_unitario, costo_adquisicion, descuento,
                   iva_porcentaje, subtotal
            FROM factura_detalles
            WHERE factura_id = ?
            ORDER BY id
        """, (id_factura,)).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


def listar_facturas_usuario(usuario_id):
    """Lista las facturas pertenecientes a un cliente."""
    conexion = obtener_conexion()
    try:
        filas = conexion.execute("""
            SELECT id, factura, cliente, fecha, total, usuario_id, proveedor, nit_proveedor
            FROM facturas
            WHERE usuario_id = ?
            ORDER BY id DESC
        """, (usuario_id,)).fetchall()
        return [fila_a_diccionario(fila) for fila in filas]
    finally:
        conexion.close()