"""Reglas puras: no importar Django ni acceder a la base de datos aquí."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation


class ErrorNegocio(ValueError):
    pass


def exigir(condicion, mensaje):
    if not condicion:
        raise ErrorNegocio(mensaje)


def centavos(valor):
    try:
        numero = Decimal(str(valor))
        exigir(numero.is_finite() and numero >= 0, "El importe debe ser positivo o cero.")
        exigir(numero == numero.quantize(Decimal("0.01")), "Usar como máximo dos decimales.")
        return int(numero * 100)
    except (InvalidOperation, TypeError):
        raise ErrorNegocio("Importe inválido.") from None


TRANSICIONES = {
    "COMPRA": {None: {"EMITIDA"}, "EMITIDA": {"RECIBIDA", "CANCELADA"}, "RECIBIDA": {"VERIFICADA"}},
    "ORDEN": {None: {"PENDIENTE"}, "PENDIENTE": {"EN_PREPARACION", "CANCELADA"},
        "EN_PREPARACION": {"DESPACHADA", "CANCELADA"}, "DESPACHADA": {"FINALIZADA"}},
    "REMITO": {None: {"EMITIDO"}, "EMITIDO": {"EN_TRANSITO", "CANCELADO"},
        "EN_TRANSITO": {"RECIBIDO"}, "RECIBIDO": {"VERIFICADO", "RECHAZADO"}},
    "BULTO": {None: {"PREPARADO"}, "PREPARADO": {"PRECINTADO", "CANCELADO"},
        "PRECINTADO": {"EN_TRANSITO", "CANCELADO"}, "EN_TRANSITO": {"RECIBIDO"},
        "RECIBIDO": {"VERIFICADO", "RECHAZADO"}, "RECHAZADO": {"EN_DEVOLUCION_AL_CD"},
        "EN_DEVOLUCION_AL_CD": {"REINGRESADO", "DADO_DE_BAJA"}},
}
FINALES_BULTO = {"VERIFICADO", "REINGRESADO", "DADO_DE_BAJA", "CANCELADO"}


def validar_transicion(ambito, anterior, siguiente):
    exigir(siguiente in TRANSICIONES.get(ambito, {}).get(anterior, set()),
        f"Transición inválida: {anterior or 'inicio'} → {siguiente}.")


@dataclass
class Inventario:
    existencia: int
    reservado: int = 0
    minimo: int = 0

    @property
    def disponible(self):
        return self.existencia - self.reservado

    def reservar(self, cantidad):
        exigir(cantidad > 0, "La cantidad debe ser mayor a cero.")
        exigir(cantidad <= self.disponible, "Stock disponible insuficiente.")
        self.reservado += cantidad

    def liberar(self, cantidad, descontar=False):
        exigir(0 < cantidad <= self.reservado, "La reserva no alcanza para esta operación.")
        self.reservado -= cantidad
        if descontar:
            self.existencia -= cantidad

    def vender(self, cantidad):
        exigir(0 < cantidad <= self.disponible, "Stock disponible insuficiente.")
        self.existencia -= cantidad


def validar_devolucion(fecha_venta: datetime, ahora: datetime, plazo: int,
                       vendida: int, devuelta: int, cantidad: int):
    exigir(fecha_venta <= ahora <= fecha_venta + timedelta(days=plazo),
        f"La devolución supera el plazo de {plazo} días.")
    exigir(0 < cantidad <= vendida - devuelta, "La cantidad supera el saldo pendiente de devolución.")


def consolidar(lineas):
    resultado = {}
    for producto, cantidad in lineas:
        exigir(isinstance(cantidad, int) and not isinstance(cantidad, bool) and cantidad > 0,
            "Las cantidades deben ser enteras positivas.")
        resultado[producto] = resultado.get(producto, 0) + cantidad
    exigir(bool(resultado), "Debe indicar al menos un producto.")
    return resultado
