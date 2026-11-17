# Clases y responsabilidades

El siguiente diagrama distingue entidades puras, coordinación y adaptadores. El DER contiene todos los agregados persistentes y sus atributos. No se presenta una tabla SQL como si fuera una implementación pura del dominio.

```mermaid
classDiagram
    class Ubicacion {
        <<abstract>>
        +int id
        +str nombre
        +str direccion
        +bool activo
        +tipo()
    }
    class CentroDistribucion {
        +tipo() CD
    }
    class LocalMinorista {
        +tipo() LOCAL
    }
    Ubicacion <|-- CentroDistribucion
    Ubicacion <|-- LocalMinorista
    class Proveedor {
        +int id
        +str cuit
        +bool activo
    }
    class CategoriaProducto {
        +int id
        +str nombre
    }
    class Producto {
        +int id
        +str sku
        +int precio_centavos
        +validar_vigencia()
        +validar_proveedor(id)
    }
    Proveedor "1" <-- "0..*" Producto
    CategoriaProducto "1" <-- "0..*" Producto
    class Inventario {
        +int existencia
        +int reservado
        +int minimo
        +disponible()
        +reservar(cantidad)
        +liberar(cantidad, descontar)
        +vender(cantidad)
    }
    class DetalleVenta {
        +int producto_id
        +int cantidad
        +int precio_centavos
        +int costo_centavos
        +subtotal()
        +margen()
    }
    class Venta {
        +tuple detalles
        +str medio
        +total_centavos()
    }
    Venta "1" *-- "1..*" DetalleVenta
    class Operaciones {
        +emitir_compra()
        +solicitar()
        +preparar()
        +precintar()
        +despachar()
        +recibir()
        +controlar()
        +cerrar_remito()
        +vender()
        +devolver_venta()
        +mover_caja()
    }
    class Reportes {
        +generar(usuario, tipo, filtros)
    }
    class DatosORM {
        +obtener(entidad, id)
        +listar(entidad, filtros)
        +crear(entidad, datos)
        +guardar(objeto)
        +producto_dominio(id)
    }
    class InventarioORM {
        +obtener(producto, ubicacion)
        +guardar(producto, ubicacion, inventario)
    }
    class TransaccionORM {
        +__enter__()
        +__exit__()
    }
    Operaciones --> Inventario
    Operaciones --> Venta
    Operaciones --> Producto
    Operaciones --> DatosORM : inyectado
    Operaciones --> InventarioORM : inyectado
    Operaciones --> TransaccionORM : inyectado
    Reportes --> DatosORM : lectura
```

Los nombres Venta, Producto y DetalleVenta existen también en persistencia: son modelos distintos, ubicados en otro módulo. Los mapeadores convierten los datos del catálogo a entidades puras; al vender se construye la Venta de dominio para validar renglones y calcular el total exacto, y después se persiste el resultado en una transacción.

Los catálogos cerrados de rol, medio de pago, tipo de movimiento y tipo de comprobante se implementan mediante opciones enumeradas; no necesitan altas de usuario ni clases vacías por valor.

## Participantes de los patrones

```mermaid
classDiagram
    class ContextoLogistico {
        +EstadoLogistico estado
        +ejecutar(accion, datos)
    }
    class CicloBulto
    class CicloRemito
    class EstadoLogistico {
        +ejecutar(accion, datos)
    }
    class BultoPreparado {
        +accion_precintar()
        +accion_cancelar()
    }
    class BultoRecibido {
        +accion_controlar(aceptar, precinto_integro, motivo, observacion)
    }
    class RemitoRecibido {
        +accion_cerrar(estados_bultos)
    }
    ContextoLogistico <|-- CicloBulto
    ContextoLogistico <|-- CicloRemito
    ContextoLogistico *-- EstadoLogistico : estado vigente
    EstadoLogistico <|-- BultoPreparado
    EstadoLogistico <|-- BultoRecibido
    EstadoLogistico <|-- RemitoRecibido
    Operaciones --> ContextoLogistico : reconstruye y ejecuta
    class Reportes {
        +generar(usuario, tipo, filtros)
    }
    class EstrategiaReporte {
        <<interface>>
        +generar(datos, filtros)
    }
    class FiltrosReporte {
        <<immutable>>
    }
    EstrategiaReporte <|.. ReporteIngresos
    EstrategiaReporte <|.. ReporteMargen
    EstrategiaReporte <|.. ReporteExistencias
    EstrategiaReporte <|.. ReporteRechazos
    Reportes o-- EstrategiaReporte : registro inyectable
    Reportes --> FiltrosReporte : normaliza
    EstrategiaReporte --> FiltrosReporte : consulta
```

Se muestran tres estados representativos para facilitar la lectura; los demás estados concretos de ambos ciclos están enumerados en [patrones](../patrones.md). Los resultados de reportes conservan su diccionario público con título, columnas, filas, nota y totales.
