# Contratos de los casos de uso

Todas las operaciones reciben un usuario autenticado. Los identificadores son enteros; las cantidades, enteros positivos; los importes de entrada son Decimal o texto con hasta dos decimales. Los errores de negocio se expresan como `ErrorNegocio` y no dejan cambios parciales.

`Operaciones` se obtiene mediante `config.composicion.operaciones()`. Las operaciones retornan el agregado creado o modificado. La interfaz web muestra los errores y redirige al detalle al confirmar.

| Método | Entradas adicionales | Rol | Resultado y condición principal |
| --- | --- | --- | --- |
| emitir_compra | proveedor_id, [(producto_id, cantidad, costo_pesos)] | ADMIN_CD | Compra emitida, productos de un proveedor |
| avanzar_compra | compra_id, estado | ADMIN_CD | Recibida, verificada o cancelada; verificar incorpora stock |
| solicitar | destino_id, [(producto_id, cantidad)] | Administradores | Orden de un local, productos consolidados |
| preparar | detalle_id, cantidad | ADMIN_CD | Bulto preparado y reserva; no exceder pedido ni disponible |
| precintar | bulto_id, precinto | ADMIN_CD | Bulto precintado y único remito emitido |
| despachar | remito_id | ADMIN_CD | Orden completa y todos los bultos precintados |
| recibir | remito_id | ADMIN_MINORISTA destino | Remito y todos sus bultos recibidos |
| controlar | bulto_id, aceptar, precinto_integro, motivo, observacion | ADMIN_MINORISTA destino | Resultado individual sin transferir stock |
| cerrar_remito | remito_id | ADMIN_MINORISTA destino | Cierre y transferencia atómica de los aceptados |
| devolver_bulto | bulto_id | Administradores | Rechazo con remito cerrado pasa a regreso al CD |
| resolver_bulto | bulto_id, recuperable, observacion | ADMIN_CD | Revisión obligatoria; reingreso o baja y Merma |
| cancelar_orden | orden_id | Administradores | Solo pendiente o en preparación; libera sus reservas |
| vender | medio, [(producto_id, cantidad)], operacion_uuid | VENDEDOR | Venta, comprobante y cobro; stock y costo histórico |
| devolver_venta | venta_id, motivo, [(detalle_id, cantidad, apto)], operacion_uuid | VENDEDOR del local | Devolución, nota, reintegro y stock o Merma |
| mover_caja | local_id, tipo, monto_pesos, motivo, operacion_uuid | Administradores | Ingreso o retiro de efectivo sin saldo negativo |

Los administradores minoristas solo operan sobre su local. ADMIN_CD prepara, precinta y despacha, pero la verificación de destino la realiza ADMIN_MINORISTA. Un vendedor puede tramitar la devolución identificando una venta de su local; no necesita ser quien registró la venta original. Los listados de ventas y devoluciones del vendedor muestran sus propias operaciones.

## Transiciones y finalización

La compra puede cancelarse solo antes de recibir. La orden puede cancelarse antes de despachar. No hay cancelación de ventas: los cambios posteriores se registran como devoluciones. No hay reapertura de remitos ni edición de decisiones de control ya registradas.

La orden finaliza automáticamente cuando su remito está cerrado y todos los bultos tienen estado final VERIFICADO, REINGRESADO o DADO_DE_BAJA. Los bultos rechazados conservan la reserva hasta su resolución en el CD.

## Interfaz HTTP

| Ruta | Método | Función |
| --- | --- | --- |
| /acceso/ | GET, POST | Inicio de sesión |
| /salir/ | POST | Cierre de sesión |
| / | GET | Resumen según rol y ubicación |
| /gestion/{tipo}/ | GET | Listado, búsqueda y paginación |
| /gestion/{tipo}/{id}/ | GET | Detalle, relaciones, historial y acciones válidas |
| /datos/{tipo}/nuevo/ | GET, POST | Alta de catálogo o usuario |
| /datos/{tipo}/{id}/ | GET, POST | Edición de catálogo o mínimo |
| /operar/{accion}/ | GET, POST | Nueva compra, orden, venta o movimiento |
| /operar/{accion}/{id}/ | GET, POST | Acción sobre agregado existente |
| /reportes/{tipo}/ | GET | Reportes con filtros compatibles |
| /comprobantes/{id}/ | GET | Comprobante interno imprimible |

GET nunca confirma operaciones. POST requiere sesión, permiso y CSRF. Los renglones se envían como un formset validado de hasta 100 filas. El UUID permanece en el formulario para soportar reintentos financieros. No se creó un contrato JSON externo ni una API REST independiente.
