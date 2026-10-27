# Trazabilidad de requisitos y pruebas

| Requisito | Implementación | Evidencia automatizada principal |
| --- | --- | --- |
| Administrar CD y locales | Ubicacion, Caja, UbicacionForm | test_formularios_maestros_precio_normalizacion_y_minimo; restricciones SQL de CD |
| Productos, categorías, precios, mínimos y proveedores | Modelos y formularios de catálogo | test_formularios_maestros_precio_normalizacion_y_minimo |
| Consolidar reposición con origen y destino | solicitar, consolidar | test_consolidacion; test_permisos_de_servicio |
| Armar bultos, remito y precinto | preparar, precintar | test_cancelacion_libera_reservas; test_no_sobre_reservar |
| Despachar | despachar | test_no_despacho_parcial_ni_cancelacion_despachada |
| Recibir y verificar precintos | recibir, controlar, cerrar_remito | test_cierre_remito_es_barrera_stock; test_formulario_control_y_cierre |
| Ventas, cobro, comprobantes y devoluciones | vender, devolver_venta, comprobante | test_venta_desde_formulario_y_reintento; test_devoluciones_acumuladas_y_merma |
| Remito y bulto verificados antes de venta | Barrera explícita en cerrar_remito | test_cierre_remito_es_barrera_stock |
| Precinto violado implica rechazo | Control obligatorio en dominio de aplicación | test_rechazo_total_reingreso; test_rechazo_mixto_baja |
| Historial inmutable | EventoEstado, RegistroInmutable | test_historial_no_se_edita; test_inmutabilidad_financiera |
| No vender sobre disponible | Inventario.vender y transacción IMMEDIATE | test_dos_ventas_compiten_por_ultima_unidad |
| No reservar sobre disponible | Inventario.reservar y transacción IMMEDIATE | test_dos_reservas_compiten_por_stock_disponible |
| Sin duplicados de producto/proveedor | SKU y CUIT únicos, normalización | Validación ModelForm y restricciones SQL |
| Devolución solo sobre venta y cantidad válidas | Referencia al detalle, plazo, acumulados | test_plazo_y_venta_ajena; test_devoluciones_acumuladas_y_merma |
| Caja insuficiente | Validación y rollback | test_devolucion_saldo_insuficiente_no_deja_efectos |
| Atomicidad | Unidad de trabajo | test_rollback_fallo_intermedio |
| Reintentos sin doble efecto | UUID únicos de operaciones financieras | test_venta_idempotente_y_precios_historicos; test_venta_desde_formulario_y_reintento |
| Reporte 1 ingresos | Reportes.generar ingresos | test_reportes_importes_y_costos |
| Reporte 2 productos y margen | Reportes.generar margen | test_reportes_importes_y_costos; costo congelado |
| Reporte 3 stock y mínimos | Reportes.generar existencias | test_stock_minimo_reporte_y_transito |
| Reporte 4 rechazos y mermas | Reportes.generar rechazos | test_reportes_rechazo_conserva_historia_y_separa_merma |
| Acceso por rol y local | Selección de ámbito y acceso en servicio | test_permisos_y_manipulacion_ids; test_permisos_de_servicio |
| CSRF y mutaciones solo POST | Middleware, formularios y rutas | test_csrf_real_y_no_mutaciones_get |
| Dos patrones | Pendiente de asignación docente | No se declara cumplido |

## Cómo verificar

Ejecutar desde la raíz `.venv\Scripts\python.exe manage.py test tests`. El conteo final y el resultado se informan en consola; las pruebas no dependen de la base de demostración. Los diagramas de persistencia se generan desde los modelos con `manage.py exportar_modelo`.

La validación visual se realiza en un navegador real en tamaños de escritorio y móvil, revisando navegación, formularios con renglones dinámicos, reportes y ausencia de desborde global. Esa revisión complementa las pruebas HTTP; no las reemplaza.
