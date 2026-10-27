# Instalación y manual de uso

## Instalación

Requiere Python 3.12 o superior. Desde la raíz del proyecto, ejecutar los comandos del README para crear `.venv`, instalar `requirements.txt` y aplicar migraciones. No requiere Node.js ni un servidor de base de datos aparte.

Hay dos formas de comenzar, ambas sobre una base vacía:

- **Demostración académica:** `python manage.py datos_demo`. Crea datos ficticios, cinco cuentas y operaciones de ejemplo. Si ya existen ubicaciones o usuarios, se detiene sin modificar datos.
- **Sistema vacío:** `python manage.py inicializar --direccion-cd "Dirección del centro"`. Solicita dos veces una contraseña válida, sin mostrarla. Crea el CD y la primera cuenta ADMIN_CD; después las altas se realizan desde las pantallas.

En estos comandos, `python` debe ser `.venv\Scripts\python.exe`. Iniciar con `manage.py runserver 127.0.0.1:8000` y abrir la dirección local. `iniciar.ps1` aplica migraciones e inicia el servidor desde la carpeta correcta. Para detenerlo usar Ctrl+C en su terminal.

El archivo `db.sqlite3` se conserva entre reinicios y está excluido de Git. Para respaldarlo, detener el servidor y copiar el archivo completo a otra ubicación. Los comandos de demostración e inicialización no contienen opciones de borrado.

## Preparación de catálogos

Con ADMIN_CD, crear locales en Ubicaciones; cada local recibe automáticamente su caja. Crear categorías y proveedores; el CUIT se normaliza sin guiones ni espacios. Crear productos con SKU, proveedor, categoría y precio en pesos. El sistema crea automáticamente los ítems de inventario de cada producto y ubicación.

Para cambiar mínimos, abrir Inventario y editar el registro producto–ubicación. No se editan manualmente existencias ni reservas. ADMIN_CD administra las cuentas desde Usuarios: el rol CD debe ubicarse en el CD y los otros roles, en un local. Para deshabilitar una cuenta o catálogo usar su indicador de activo.

## Compra e ingreso al CD

1. Ingresar como ADMIN_CD y elegir Compras → Nueva operación.
2. Seleccionar proveedor y cargar uno o varios productos con cantidad y costo unitario en pesos.
3. Confirmar la emisión. Abrir la compra y registrar llegada.
4. Después del control, verificar la compra. Recién entonces el stock queda disponible en el CD.

La compra emitida puede cancelarse. Una compra recibida se verifica; la primera versión no contempla recepción parcial ni rechazo de una compra.

## Reposición y logística

1. Como ADMIN_MINORISTA, consultar Inventario y crear una reposición con las necesidades del local. Si se repite un producto se suman las cantidades.
2. Como ADMIN_CD, abrir la orden y preparar uno o varios bultos de cada renglón. La suma no puede superar lo pedido ni el disponible.
3. Abrir cada bulto y precintarlo con un número único. El primer precintado emite el remito de esa orden.
4. Abrir el remito. Solo se podrá despachar después de preparar y precintar todas las cantidades.
5. Como administrador del destino, abrir el remito y registrar recepción.
6. Abrir cada bulto y controlar precinto y contenido. Si se desmarca precinto íntegro, el sistema lo rechaza por precinto violado aunque se hubiera indicado aceptar.
7. Volver al remito y cerrar la verificación. Solo en ese momento se transfiere al local el stock de los aceptados.

Si todos se rechazan, el remito cierra RECHAZADO y no incorpora stock. Con aceptación mixta, cierra VERIFICADO, pero cada rechazo conserva su historia y su reserva. Antes del despacho se puede cancelar la orden; se cancelan sus bultos y remito y se liberan todas sus reservas.

## Devolución logística

Después de cerrar el remito, abrir un bulto rechazado y enviarlo de regreso al CD. ADMIN_CD revisa físicamente su contenido y registra una observación obligatoria. Si es recuperable, reingresa y libera la reserva. Si no, se da de baja, se descuenta del CD y se registra Merma.

La orden finaliza cuando sus bultos quedan resueltos. La reposición de las cantidades rechazadas se solicita en una orden nueva.

## Venta, comprobante y devolución

Como VENDEDOR, elegir Ventas → Nueva operación. Seleccionar productos, cantidades y un medio de pago. Antes de confirmar se muestra precio, disponible y total. El servidor recalcula y valida al confirmar; nunca acepta el total enviado por el navegador. La venta genera stock descontado, movimiento de cobro y ticket interno.

Abrir Ver comprobante para imprimir o usar Guardar como PDF del navegador. No hay integración fiscal ni bancaria.

Para devolver, abrir la venta y elegir Registrar devolución. También puede irse a Devoluciones y buscar por número de venta del local, sin comprobante. Indicar motivo, renglones, cantidades y si cada producto es apto para volver a vender. El reintegro usa el medio original y los precios originales. No se supera lo vendido menos devoluciones anteriores ni el plazo configurable.

Si se reintegra efectivo y no alcanza la caja, la devolución se bloquea completa. Lo apto vuelve a stock; lo no apto genera Merma. La nota de crédito y todos los efectos se confirman juntos. Las ventas registradas no se editan ni se borran.

## Caja

La caja comienza en cero. El administrador del local puede ingresar un fondo de efectivo o registrar un retiro con importe y motivo. ADMIN_CD puede hacerlo en cualquier local. No se permiten retiros que dejen saldo negativo.

Los cobros y reintegros electrónicos aparecen como movimientos, pero no afectan el saldo de efectivo. El vendedor consulta el saldo de su caja y sus propios movimientos; no registra ajustes manuales.

## Reportes y filtros

Los administradores acceden a Ventas e ingresos, Productos y margen, Existencias, Rechazos y mermas. ADMIN_CD tiene alcance global y ADMIN_MINORISTA solo su local. Se muestran únicamente filtros aplicables a cada reporte. Los reportes se pueden imprimir desde el navegador.

Una consulta sin resultados muestra un estado vacío, sin valores inventados. En Existencias no se elige período, porque representa el estado actual. En Rechazos no se suman rechazo y merma como si fueran dos pérdidas.

## Recorrido de demostración preparado

1. Ingresar como `admin_cd` con `DemoNexo2026!`: revisar el resumen, inventario, compras y los cuatro reportes.
2. Revisar la orden de Local Sur todavía en preparación y su remito emitido.
3. Revisar el remito mixto de Local Norte: un bulto aceptado, una baja por precinto y otro en retorno al CD. Abrir sus historiales.
4. Ingresar como `admin_norte`: observar que solo se consulta y opera sobre Local Norte.
5. Ingresar como `vendedor_norte`: registrar venta, consultar total, imprimir ticket y devolver un renglón.
6. Consultar el reporte de ingresos y comparar bruto, reintegros y neto; revisar que el medio electrónico no cambió el efectivo físico.

Los datos son ficticios y se identifican como demostración. La asignación e incorporación de dos patrones y los datos administrativos del grupo siguen pendientes.
