# Ciclos de vida

## Bulto

```mermaid
stateDiagram-v2
    [*] --> PREPARADO
    PREPARADO --> PRECINTADO
    PREPARADO --> CANCELADO
    PRECINTADO --> CANCELADO
    PRECINTADO --> EN_TRANSITO
    EN_TRANSITO --> RECIBIDO
    RECIBIDO --> VERIFICADO
    RECIBIDO --> RECHAZADO
    RECHAZADO --> EN_DEVOLUCION_AL_CD
    EN_DEVOLUCION_AL_CD --> REINGRESADO
    EN_DEVOLUCION_AL_CD --> DADO_DE_BAJA
    VERIFICADO --> [*]
    REINGRESADO --> [*]
    DADO_DE_BAJA --> [*]
    CANCELADO --> [*]
```

VERIFICADO expresa el resultado del control individual. **No habilita venta hasta que el remito cierre VERIFICADO**. Esta distinción es deliberada y evita la inconsistencia del borrador. El reingreso y la baja exigen una revisión registrada en el CD.

## Remito

```mermaid
stateDiagram-v2
    [*] --> EMITIDO
    EMITIDO --> CANCELADO
    EMITIDO --> EN_TRANSITO
    EN_TRANSITO --> RECIBIDO
    RECIBIDO --> VERIFICADO: Todos controlados y alguno aceptado
    RECIBIDO --> RECHAZADO: Todos controlados y ninguno aceptado
    VERIFICADO --> [*]
    RECHAZADO --> [*]
    CANCELADO --> [*]
```

## Orden de reposición

```mermaid
stateDiagram-v2
    [*] --> PENDIENTE
    PENDIENTE --> EN_PREPARACION
    PENDIENTE --> CANCELADA
    EN_PREPARACION --> CANCELADA
    EN_PREPARACION --> DESPACHADA
    DESPACHADA --> FINALIZADA: Remito cerrado y todos los bultos resueltos
    FINALIZADA --> [*]
    CANCELADA --> [*]
```

## Compra

```mermaid
stateDiagram-v2
    [*] --> EMITIDA
    EMITIDA --> CANCELADA
    EMITIDA --> RECIBIDA
    RECIBIDA --> VERIFICADA
    VERIFICADA --> [*]
    CANCELADA --> [*]
```

Venta y Devolucion se registran en un paso y son inmutables. Las correcciones comerciales se expresan como devoluciones vinculadas a la venta, sin editar la operación original.
