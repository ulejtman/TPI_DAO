"""State logístico puro. Los contextos se reconstruyen desde el historial persistido."""
from src.dominio.reglas import ErrorNegocio, exigir


class EstadoLogistico:
    nombre = None

    def ejecutar(self, accion, **datos):
        metodo = getattr(self, "accion_" + accion, None)
        exigir(metodo is not None,
               f"Acción inválida: {accion} en {self.nombre or 'inicio'}.")
        return metodo(**datos)


class BultoInicial(EstadoLogistico):
    def accion_preparar(self):
        return "PREPARADO"


class BultoPreparado(EstadoLogistico):
    nombre = "PREPARADO"

    def accion_precintar(self):
        return "PRECINTADO"

    def accion_cancelar(self):
        return "CANCELADO"


class BultoPrecintado(EstadoLogistico):
    nombre = "PRECINTADO"

    def accion_despachar(self):
        return "EN_TRANSITO"

    def accion_cancelar(self):
        return "CANCELADO"


class BultoEnTransito(EstadoLogistico):
    nombre = "EN_TRANSITO"

    def accion_recibir(self):
        return "RECIBIDO"


class BultoRecibido(EstadoLogistico):
    nombre = "RECIBIDO"

    def accion_controlar(self, aceptar, precinto_integro, motivo="", observacion=""):
        if not precinto_integro:
            aceptar, motivo = False, "PRECINTO_VIOLADO"
        if not aceptar:
            exigir(motivo in {"PRECINTO_VIOLADO", "ENVIO_ERRONEO", "OTRO"},
                   "Debe indicar un motivo de rechazo.")
            exigir(motivo != "OTRO" or observacion.strip(), "Describa el motivo del rechazo.")
        return "VERIFICADO" if aceptar else "RECHAZADO"


class BultoVerificado(EstadoLogistico):
    nombre = "VERIFICADO"


class BultoRechazado(EstadoLogistico):
    nombre = "RECHAZADO"

    def accion_retornar(self, remito_cerrado):
        exigir(remito_cerrado, "Primero debe cerrar el remito.")
        return "EN_DEVOLUCION_AL_CD"


class BultoEnDevolucion(EstadoLogistico):
    nombre = "EN_DEVOLUCION_AL_CD"

    def accion_resolver(self, recuperable, observacion):
        exigir(bool(observacion.strip()),
               "Registrar el resultado de la revisión del contenido en el CD.")
        return "REINGRESADO" if recuperable else "DADO_DE_BAJA"


class BultoReingresado(EstadoLogistico):
    nombre = "REINGRESADO"


class BultoDadoDeBaja(EstadoLogistico):
    nombre = "DADO_DE_BAJA"


class BultoCancelado(EstadoLogistico):
    nombre = "CANCELADO"


class RemitoInicial(EstadoLogistico):
    def accion_emitir(self):
        return "EMITIDO"


class RemitoEmitido(EstadoLogistico):
    nombre = "EMITIDO"

    def accion_despachar(self):
        return "EN_TRANSITO"

    def accion_cancelar(self):
        return "CANCELADO"


class RemitoEnTransito(EstadoLogistico):
    nombre = "EN_TRANSITO"

    def accion_recibir(self):
        return "RECIBIDO"


class RemitoRecibido(EstadoLogistico):
    nombre = "RECIBIDO"

    def accion_cerrar(self, estados_bultos):
        estados = tuple(estados_bultos)
        exigir(bool(estados) and all(e in {"VERIFICADO", "RECHAZADO"} for e in estados),
               "Debe controlar todos los bultos antes de cerrar el remito.")
        return "VERIFICADO" if "VERIFICADO" in estados else "RECHAZADO"


class RemitoVerificado(EstadoLogistico):
    nombre = "VERIFICADO"


class RemitoRechazado(EstadoLogistico):
    nombre = "RECHAZADO"


class RemitoCancelado(EstadoLogistico):
    nombre = "CANCELADO"


class ContextoLogistico:
    estados = ()

    def __init__(self, nombre=None):
        tipos = {tipo.nombre: tipo for tipo in self.estados}
        exigir(nombre in tipos, f"Estado desconocido: {nombre}.")
        self.estado = tipos[nombre]()

    def ejecutar(self, accion, **datos):
        siguiente = self.estado.ejecutar(accion, **datos)
        self.estado = type(self)(siguiente).estado
        return siguiente


class CicloBulto(ContextoLogistico):
    estados = (BultoInicial, BultoPreparado, BultoPrecintado, BultoEnTransito,
               BultoRecibido, BultoVerificado, BultoRechazado, BultoEnDevolucion,
               BultoReingresado, BultoDadoDeBaja, BultoCancelado)


class CicloRemito(ContextoLogistico):
    estados = (RemitoInicial, RemitoEmitido, RemitoEnTransito, RemitoRecibido,
               RemitoVerificado, RemitoRechazado, RemitoCancelado)


# Adaptación de destinos históricos a acciones; la legalidad reside en cada State.
# Estos datos satisfacen guardas solo para validar el arco, no autorizan un caso de uso.
_DESTINOS_BULTO = {
    "PREPARADO": ("preparar", {}), "PRECINTADO": ("precintar", {}),
    "EN_TRANSITO": ("despachar", {}), "RECIBIDO": ("recibir", {}),
    "CANCELADO": ("cancelar", {}),
    "VERIFICADO": ("controlar", {"aceptar": True, "precinto_integro": True}),
    "RECHAZADO": ("controlar", {"aceptar": False, "precinto_integro": False}),
    "EN_DEVOLUCION_AL_CD": ("retornar", {"remito_cerrado": True}),
    "REINGRESADO": ("resolver", {"recuperable": True, "observacion": "Validar arco"}),
    "DADO_DE_BAJA": ("resolver", {"recuperable": False, "observacion": "Validar arco"}),
}
_DESTINOS_REMITO = {
    "EMITIDO": ("emitir", {}), "EN_TRANSITO": ("despachar", {}),
    "RECIBIDO": ("recibir", {}), "CANCELADO": ("cancelar", {}),
    "VERIFICADO": ("cerrar", {"estados_bultos": ("VERIFICADO",)}),
    "RECHAZADO": ("cerrar", {"estados_bultos": ("RECHAZADO",)}),
}


def validar_arco(ambito, anterior, siguiente):
    ciclo, destinos = ((CicloBulto, _DESTINOS_BULTO) if ambito == "BULTO"
                       else (CicloRemito, _DESTINOS_REMITO))
    try:
        exigir(siguiente in destinos, "Destino desconocido.")
        accion, datos = destinos[siguiente]
        exigir(ciclo(anterior).ejecutar(accion, **datos) == siguiente, "Destino inválido.")
    except ErrorNegocio:
        raise ErrorNegocio(
            f"Transición inválida: {anterior or 'inicio'} → {siguiente}.") from None
