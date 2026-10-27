# Análisis del trabajo práctico

## Objetivo y material de partida

El sistema debe integrar abastecimiento, logística interna, ventas e inventario de un comercio con varios locales. La condición central es que el local no pueda vender mercadería que todavía no haya pasado la verificación logística. El trabajo también debe evidenciar diseño orientado a objetos, dos patrones y al menos cuatro reportes no triviales.

Se revisaron los cuatro archivos compartidos. `tema3.pdf` tiene dos páginas y contiene la consigna. `arquitectura sistema propuesta.pdf` tiene diecinueve páginas y desarrolla la propuesta del grupo. `der_completo_ventas_inventario.html` contiene un DER Mermaid con entidades, atributos y relaciones. `Presentacion-grupo.docx` es una plantilla con apartados de grupo, objetivos, alcance y modelo, todavía sin completar. No existía código en el repositorio.

Los documentos se trataron como fuentes de requisitos y análisis. Sus recomendaciones no se tomaron como autorizaciones para elegir tecnologías, patrones o reglas abiertas: esas decisiones se consultaron en el chat. Los originales se conservaron sin cambios en `fuentes/`.

## Procesos requeridos y su interpretación

1. **Ubicaciones:** un único CD y varios locales; cada local tiene una caja, el CD no. Las ubicaciones referenciadas se desactivan, sin eliminar historia.
2. **Catálogo:** productos identificados por SKU y proveedores por CUIT; categorías y precio de venta global; mínimo por producto y ubicación. Cada producto pertenece a un proveedor y una categoría.
3. **Reposición:** el administrador reúne manualmente las necesidades de un local. Una orden identifica CD de origen y local de destino. No se mezclan destinos en una misma orden; productos repetidos se consolidan.
4. **Empaquetado:** cada bulto contiene un producto y una cantidad. Una línea de orden puede dividirse en varios bultos. La preparación reserva stock y el precintado asigna un identificador único y un remito.
5. **Despacho:** exige completar todas las cantidades y precintar todos los bultos. Se admite un remito por orden y no se realizan despachos parciales.
6. **Recepción:** se registra llegada, se controla cada bulto y se cierra el remito. Un precinto violado obliga al rechazo. Solo el cierre habilita los bultos aceptados para venta.
7. **Venta y devolución:** ventas con varios productos y un medio de pago, comprobante obligatorio, control de disponible, reintegros y recuperación de stock o registro de merma.

Las compras forman parte del contexto y de la propuesta del grupo: EMITIDA → RECIBIDA → VERIFICADA. La llegada no incorpora stock; la verificación sí. No se implementan cuentas por pagar ni pagos a proveedores, que no están desarrollados como requisitos de esta entrega.

## Qué estaba bien resuelto

La propuesta identifica los principales agregados y separa ubicación, producto e inventario. No guarda el stock global directamente en el producto. Conserva el precio de la venta, relaciona devoluciones con renglones originales y diferencia inventario físico contable de reserva. También identifica operaciones atómicas, responsabilidades por rol y el ciclo de retorno de mercadería rechazada. Los cuatro reportes propuestos se corresponden con los sugeridos por la consigna.

El ciclo ampliado del bulto permite resolver qué ocurre después del rechazo. Sin reingreso o baja, las reservas quedarían indefinidas. La entidad Merma permite separar un rechazo —que puede recuperarse— de una pérdida confirmada.

## Inconsistencias y resolución acordada

| Hallazgo | Resolución |
| --- | --- |
| Verificar un bulto sumaba stock aunque el remito siguiera sin verificar | El resultado individual se registra primero; la transferencia ocurre al cerrar el remito |
| El remito no contemplaba rechazo total | Cierra RECHAZADO si ningún bulto es aceptado; VERIFICADO si alguno es aceptado y todos fueron controlados |
| Existencia era llamada física aunque incluía mercadería ya despachada | Se conserva como existencia contable del CD y se distinguen reservas y pendientes de ingreso |
| Historial inmutable pero con actualización de fecha de fin | Eventos que solo se agregan; la duración se deriva del siguiente evento |
| El DER admitía varios remitos y el texto recomendaba uno | Relación uno a cero o uno; sin despachos parciales |
| Bulto obligatorio bajo remito desde su creación | Remito y precinto son opcionales hasta precintar |
| Fecha de despacho parecía obligatoria al emitir remito | Es opcional hasta registrar el despacho |
| No se explicaba la cancelación con bultos reservados | Se conservan los registros, se cancelan y se liberan reservas |
| Comprobante de venta opcional en el modelo | Obligatorio al registrar una venta |
| Caja mezclaba efectivo y medios electrónicos | El saldo suma solo movimientos de efectivo; los demás también se registran |
| Todos los movimientos debían referenciar venta o devolución | Se agregan ingresos y retiros manuales con motivo y responsable |
| Valores monetarios con float | Centavos enteros en persistencia y Decimal al convertir importes |
| Margen calculado desde compras futuras podía cambiar la historia | El costo vigente se congela en cada detalle de venta |
| Historial con cuatro FK opcionales sin exclusión declarada | Restricción de un único dueño y ámbito compatible |

## Reglas de stock definitivas

| Operación | Existencia CD | Reserva CD | Existencia local |
| --- | --- | --- | --- |
| Verificar compra | +cantidad | Sin cambio | Sin cambio |
| Preparar bulto | Sin cambio | +cantidad | Sin cambio |
| Precintar, despachar, recibir o controlar | Sin cambio | Sin cambio | Sin cambio |
| Cerrar remito, por cada bulto aceptado | −cantidad | −cantidad | +cantidad |
| Reingresar bulto rechazado | Sin cambio | −cantidad | Sin cambio |
| Dar de baja bulto rechazado | −cantidad | −cantidad | Sin cambio |
| Cancelar orden antes del despacho | Sin cambio | −reservas de sus bultos | Sin cambio |
| Vender | Sin cambio | Sin cambio | −cantidad |
| Devolución comercial apta | Sin cambio | Sin cambio | +cantidad |
| Devolución no apta | Sin cambio | Sin cambio | Sin cambio; genera Merma |

Disponible = existencia − reservado. Las reservas de los locales permanecen en cero porque la venta se confirma en una sola operación y no hay carritos persistentes ni pedidos de clientes.

## Reportes y significado económico

**Ventas e ingresos:** agrupa bruto, reintegros y neto por local y medio, con período inclusivo según la fecha de cada operación en Buenos Aires. Una devolución de una venta de otro período reduce el ingreso del período del reintegro. Los movimientos manuales de efectivo no son ingresos comerciales.

**Productos y margen:** ordena por unidades netas y muestra vendidas, devueltas, ingreso neto, costo consumido y margen. El costo se toma de la última compra verificada al vender. Una devolución apta recupera costo; una no apta devuelve el precio al cliente pero conserva el costo consumido y muestra su merma. Es un margen estimado: no incluye gastos operativos ni pérdidas logísticas.

**Existencias:** foto actual por ubicación y categoría, con existencia, reserva, disponible, mínimos y mercadería pendiente de ingreso. No representa una reconstrucción histórica y no tiene filtro de período.

**Rechazos y mermas:** consulta el evento histórico de rechazo, aunque el bulto ya haya reingresado o sido dado de baja. Las mermas logísticas se presentan como registros distintos; las devoluciones comerciales no se mezclan. Cada registro se imputa a su propia fecha.

## Alcance y pendientes

No se agregan promociones, clientes frecuentes, cuentas corrientes, lotes, vencimientos, conciliaciones físicas ni sugerencias automáticas de compra. La reposición se carga manualmente, asistida por la consulta de mínimos. Los comprobantes y medios de pago son internos, sin integración fiscal ni bancaria.

La demostración utiliza datos ficticios. No se inventaron integrantes, número de grupo ni compromisos de entrega. La plantilla de presentación original sigue disponible para completarla cuando el grupo aporte esos datos.

Los docentes todavía deben asignar los patrones. La solución tiene límites explícitos para transiciones, cálculos, repositorios y composición, pero no se presenta una tabla de transiciones o un DAO como cumplimiento automático de los dos patrones académicos.
