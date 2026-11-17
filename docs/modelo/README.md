# Modelo actualizado

- [DER con atributos y relaciones](der.md), generado desde los modelos reales de persistencia.
- [Fuente Mermaid del DER](der.mmd), para importar en herramientas compatibles.
- [Clases y responsabilidades](clases.md).
- [Ciclos de vida](estados.md).

Regenerar el DER después de modificar modelos con `python manage.py exportar_modelo`, usando el Python del entorno del proyecto. Los diagramas se pueden visualizar en un editor compatible con Mermaid. No dependen del HTML original ni de sus bibliotecas remotas.

## Restricciones que un DER no expresa por sí solo

- Ubicacion usa un discriminador CD/LOCAL y permite como máximo un CD. El dominio conserva la jerarquía de clases.
- Caja se relaciona uno a uno con un local; el servicio de alta crea la caja automáticamente y el CD no recibe caja.
- ItemInventario es único por producto y ubicación; reservado no puede superar existencia.
- Una orden tiene como máximo un remito. La existencia de una relación no habilita despachos parciales.
- Bulto puede no tener remito ni precinto mientras está preparado. Precinto es único cuando existe.
- EventoEstado tiene exactamente una referencia entre compra, orden, remito y bulto; el ámbito debe coincidir.
- Comprobante está vinculado a una venta o a una devolución mediante los casos de uso. Toda operación registrada tiene uno.
- Merma tiene exactamente una referencia de origen: bulto o detalle de devolución.
- MovimientoCaja de venta tiene una venta; el de devolución, una devolución; los manuales no tienen ninguna de esas referencias y usan efectivo.
- Las cantidades son positivas; precios y costos son no negativos; importes monetarios en centavos.
- Historial y registros financieros no se modifican desde el sistema después de crearse.
