# Decisiones confirmadas

Registro de las respuestas del usuario durante la planificación. Las recomendaciones originales del PDF no equivalían a decisiones; las siguientes sí fueron confirmadas.

| Tema | Decisión |
| --- | --- |
| Entrega | Proyecto funcional completo |
| Backend | Python |
| Aplicación | Web con Django y plantillas |
| Persistencia | SQLite |
| Reglas del grupo | Se conservan un CD, una caja por local, un proveedor por producto y un producto por bulto |
| D-1 Estados del remito | Propios; verificado con algún aceptado, rechazado si todos se rechazan, después de controlar todos |
| D-2 Remitos por orden | Uno; se despacha la orden completa |
| D-3 Merma | Entidad propia |
| D-4 Faltante por rechazo | Nueva orden; la original finaliza al resolver sus bultos |
| D-5 Efectivo insuficiente | Bloquear devolución sin cambios parciales |
| D-6 Costo para margen | Último costo de compra verificada, congelado al vender |
| D-7 Devoluciones | Plazo configurable de 30 días |
| D-8 Ingresos | Bruto, reintegros y neto separados; fecha de cada operación |
| D-9 Persistencia | SQLite |
| D-10 Presentación | Django con plantillas |
| Habilitación de stock | Esperar el cierre del remito; no basta el control del bulto |
| Stock en tránsito | Sigue en existencia contable del CD, reservado |
| Cancelación en preparación | Cancelar bultos y remito, conservar historia y liberar reservas |
| Historial | Eventos que solo se agregan, sin fecha de fin editable |
| Consolidación de necesidades | Carga manual; agrupar productos repetidos |
| Caja | Solo efectivo físico; registrar también los medios electrónicos |
| Fondos de caja | Ingresos y retiros manuales con motivo y responsable |
| Medios de pago | Efectivo, débito, crédito y transferencia; uno por venta |
| Comprobantes | Internos imprimibles; PDF mediante impresión del navegador |
| Acceso | Usuario y contraseña; ADMIN_CD administra cuentas; sin registro público |
| Reportes | CD consulta todo; administrador minorista su local; vendedor sin reportes gerenciales |
| Opcionales | Basarse en el material compartido; no agregar procesos opcionales |
| Patrones | Pendientes de asignación docente |

## Convenciones técnicas de implementación

Estas convenciones concretan el plan sin alterar sus reglas: Django 5.2.18; importes enteros en centavos; identificadores autogenerados; UUID para reintentos de ventas, devoluciones y caja; transacciones SQLite IMMEDIATE; sesiones Django y CSRF; fechas con zona horaria; baja lógica de catálogos; numeración interna de comprobantes derivada de su identificador.

El plazo de 30 días es una ventana inclusiva de 30 × 24 horas desde la venta. El costo de un producto se toma de la compra verificada más recientemente, no de una compra emitida o solo recibida. El valor de venta actual del catálogo y el costo son globales, como en el modelo compartido.
