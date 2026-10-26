from pydantic import BaseModel, ConfigDict, Field, field_validator


class FacturaBase(BaseModel):
    """Datos que el usuario ingresa en el formulario."""

    cliente: str = Field(min_length=1, max_length=150)
    fecha: str = Field(min_length=1, max_length=30)
    total: float = Field(ge=0)

    @field_validator("cliente", "fecha")
    @classmethod
    def validar_texto(cls, valor):
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

    model_config = ConfigDict(from_attributes=True)