from dataclasses import dataclass
from src.dominio.reglas import exigir


@dataclass(frozen=True)
class CategoriaProducto:
    id: int
    nombre: str


@dataclass(frozen=True)
class Proveedor:
    id: int
    nombre: str
    cuit: str
    activo: bool = True


@dataclass(frozen=True)
class Producto:
    id: int
    sku: str
    nombre: str
    precio_centavos: int
    proveedor: Proveedor
    categoria: CategoriaProducto
    activo: bool = True

    def validar_vigencia(self):
        exigir(self.activo and self.proveedor.activo, "Producto o proveedor inactivo.")

    def validar_proveedor(self, proveedor_id):
        exigir(self.proveedor.id == proveedor_id, "Todos los productos deben ser del proveedor elegido.")
