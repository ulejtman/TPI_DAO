# State y Strategy

Elección confirmada por el grupo el 17 de noviembre de 2026. El enunciado exige al menos dos patrones y cuatro reportes no triviales. Se eligieron estos patrones por sus responsabilidades en el sistema, sin interpretar la imagen de sugerencias como una asignación docente.

## State: ciclo de bultos y remitos

Código: `src/dominio/estados.py`; integración: `Operaciones.actuar` en `src/aplicacion/servicios.py`.

| Participante | Implementación |
| --- | --- |
| Contexto | ContextoLogistico, especializado por CicloBulto y CicloRemito |
| Estado | EstadoLogistico: ejecuta una acción o la rechaza si no está definida |
| Estados de bulto | BultoInicial, BultoPreparado, BultoPrecintado, BultoEnTransito, BultoRecibido, BultoVerificado, BultoRechazado, BultoEnDevolucion, BultoReingresado, BultoDadoDeBaja, BultoCancelado |
| Estados de remito | RemitoInicial, RemitoEmitido, RemitoEnTransito, RemitoRecibido, RemitoVerificado, RemitoRechazado, RemitoCancelado |
| Cliente | Operaciones reconstruye el contexto desde el último evento y solicita la acción |

Por ejemplo, `CicloBulto("PREPARADO").ejecutar("precintar")` delega en BultoPreparado, retorna PRECINTADO y cambia el objeto de estado del contexto. Esa misma acción en BultoEnTransito se rechaza. El comportamiento varía por polimorfismo; no se consulta una tabla de arcos logísticos.

BultoRecibido decide aceptación o rechazo y valida motivos. El precinto violado obliga al rechazo. RemitoRecibido exige todos los bultos controlados y decide su resultado global. Los estados terminales no implementan acciones salientes. Retornar exige remito cerrado; resolver exige una revisión registrada.

El contexto es transitorio: no se guarda en el ORM ni se cachea entre solicitudes. La aplicación conserva permisos, transacciones, movimientos de stock y creación de mermas. Cada nuevo estado se registra como evento inmutable; el último evento por fecha e identificador determina el estado vigente.

`validar_transicion(ambito, anterior, siguiente)` sigue disponible. Para bulto y remito adapta el destino histórico a una acción de State; esa validación comprueba solo el arco. Las guardas de una operación real se evalúan con sus datos reales mediante `actuar`. Para compras y órdenes usa las tablas existentes. El adaptador no contiene una segunda tabla de arcos.

La verificación individual no habilita venta hasta cerrar el remito. El inventario conserva existencia y reserva simultáneas, por lo que no se le impone un único estado artificial.

## Strategy: algoritmos de reporte

Código: `src/aplicacion/reportes.py`.

| Participante | Implementación |
| --- | --- |
| Contexto | Reportes |
| Interfaz común | EstrategiaReporte, protocolo estructural con generar(datos, filtros) |
| Estrategias concretas | ReporteIngresos, ReporteMargen, ReporteExistencias, ReporteRechazos |
| Parámetros | FiltrosReporte, dataclass inmutable con período, local, categoría, medio y motivo |
| Selección | Registro por tipo; predeterminado o inyectado al construir Reportes |

La firma pública de `Reportes.generar(...)` y sus resultados se conservan. Antes de delegar, la fachada controla rol, período y local autorizado. Las estrategias reciben el local normalizado y contienen consultas, agrupamientos y cálculos propios. Sus instancias no guardan resultados ni filtros entre llamadas.

Una implementación alternativa que exponga `generar(datos, filtros)` puede inyectarse mediante `Reportes(datos, operaciones, estrategias={"ingresos": alternativa})`. No requiere modificar la fachada. El protocolo permite ese reemplazo sin exigir herencia nominal.

Se conservan los cuatro algoritmos y sus filtros aplicables: ingresos por período/local/medio; margen por período/local/categoría; existencias actuales por ubicación/categoría; rechazos por período/local/categoría/motivo. Existencias ignora el período porque representa la foto actual. No se añaden reportes, exportaciones ni dependencias.

## Evidencia de implementación

- `tests/test_patrones.py`: 208 combinaciones de arcos, cambio de estado y delegación, guardas, sustitución de estrategias, resultados completos, filtros, períodos, costos históricos y HTTP.
- Rollback de cancelación, despacho, recepción y baja; la prueba existente de cierre con fallo de inventario sigue vigente.
- `tests/test_concurrencia.py`: dos cierres del mismo remito ingresan stock una sola vez, además de las competencias existentes por venta y reserva.
- La suite completa conserva las comprobaciones de permisos, devoluciones, caja, inmutabilidad y carga de demostración.

Los diagramas de participantes están en [clases](modelo/clases.md) y los ciclos en [estados](modelo/estados.md). El DER no cambia porque los patrones modifican comportamiento, no la estructura persistida.
