from dataclasses import dataclass
from src.dominio.reglas import exigir


@dataclass(frozen=True)
class DetalleVenta:
    producto_id: int
    cantidad: int
    precio_centavos: int
    costo_centavos: int

    def __post_init__(self):
        exigir(self.cantidad > 0 and self.precio_centavos >= 0 and self.costo_centavos >= 0,
            "El detalle de venta contiene cantidades o importes inválidos.")

    @property
    def subtotal(self):
        return self.cantidad * self.precio_centavos

    @property
    def margen(self):
        return self.cantidad * (self.precio_centavos - self.costo_centavos)


@dataclass(frozen=True)
class Venta:
    detalles: tuple[DetalleVenta, ...]
    medio: str

    def __post_init__(self):
        exigir(bool(self.detalles), "Una venta requiere productos.")
        exigir(self.medio in {"EFECTIVO", "DEBITO", "CREDITO", "TRANSFERENCIA"}, "Medio de pago inválido.")

    @property
    def total_centavos(self):
        return sum(d.subtotal for d in self.detalles)
