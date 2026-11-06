"""Modelos de entrada y salida validados por Pydantic."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Campos compartidos para crear, editar y responder facturas.
class FacturaBase(BaseModel):
    """Datos que el usuario ingresa en el formulario."""

    cliente: str = Field(min_length=1, max_length=150)
    proveedor: str | None = Field(default=None, max_length=250)
    nit_proveedor: str | None = Field(default=None, max_length=40)
    fecha: str = Field(min_length=1, max_length=30)
    total: float = Field(ge=0)
    detalles: list["DetalleFacturaCrear"] = Field(default_factory=list)

    @field_validator("cliente", "fecha")
    @classmethod
    def validar_texto(cls, valor):
        """Elimina espacios y rechaza valores de texto vacíos."""
        valor = valor.strip()

        if not valor:
            raise ValueError("El campo no puede estar vacío.")

        return valor


class FacturaCrear(FacturaBase):
    """Datos para crear una factura."""

    pass


class FacturaActualizar(FacturaBase):
    """Datos para actualizar una factura."""

    pass


class FacturaRespuesta(FacturaBase):
    """Datos completos devueltos por la API."""

    id: int
    factura: str
    usuario_id: int | None = None
    proveedor: str | None = None
    nit_proveedor: str | None = None

    model_config = ConfigDict(from_attributes=True)


# Producto que se guarda dentro del detalle de una factura.
class DetalleFacturaCrear(BaseModel):
    """Define un producto y sus valores dentro de una factura."""
    producto_id: int | None = None
    nombre: str = Field(min_length=1, max_length=250)
    descripcion: str = Field(default="", max_length=500)
    cantidad: float = Field(gt=0)
    valor_unitario: float = Field(ge=0)
    costo_adquisicion: float | None = Field(default=None, ge=0)
    descuento: float = Field(default=0, ge=0)
    iva_porcentaje: float = Field(default=0, ge=0, le=100)


# Producto administrable del catálogo.
class ProductoCrear(BaseModel):
    """Define un producto que puede administrarse en el catálogo."""
    codigo: str = Field(min_length=1, max_length=80)
    nombre: str = Field(min_length=1, max_length=250)
    descripcion: str = Field(default="", max_length=500)
    precio: float = Field(ge=0)
    costo_adquisicion: float = Field(default=0, ge=0)
    iva_porcentaje: float = Field(default=0, ge=0, le=100)