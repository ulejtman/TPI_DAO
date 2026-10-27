from django.conf import settings
from django.utils import timezone
from src.aplicacion.servicios import Operaciones
from src.infraestructura.repositorios import DatosORM, InventarioORM, TransaccionORM


def operaciones():
    return Operaciones(DatosORM(), InventarioORM(), TransaccionORM, timezone.now, settings.PLAZO_DEVOLUCION_DIAS)
