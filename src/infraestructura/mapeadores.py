from src.dominio.catalogo import CategoriaProducto, Producto, Proveedor
from src.dominio.ubicaciones import CentroDistribucion, LocalMinorista


def producto_dominio(modelo):
    proveedor = Proveedor(modelo.proveedor_id, modelo.proveedor.nombre, modelo.proveedor.cuit, modelo.proveedor.activo)
    categoria = CategoriaProducto(modelo.categoria_id, modelo.categoria.nombre)
    return Producto(modelo.pk, modelo.sku, modelo.nombre, modelo.precio_centavos, proveedor, categoria, modelo.activo)


def ubicacion_dominio(modelo):
    clase = CentroDistribucion if modelo.tipo == "CD" else LocalMinorista
    return clase(modelo.pk, modelo.nombre, modelo.direccion, modelo.telefono, modelo.activo)
