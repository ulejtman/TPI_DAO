from django.db import transaction
from src.dominio.reglas import Inventario
from src.infraestructura.persistencia.models import ItemInventario
from src.infraestructura.persistencia import models
from src.dominio.reglas import exigir


class InventarioORM:
    def obtener(self, producto_id, ubicacion_id):
        item, _ = ItemInventario.objects.get_or_create(producto_id=producto_id, ubicacion_id=ubicacion_id)
        return Inventario(item.existencia, item.reservado, item.minimo)

    def guardar(self, producto_id, ubicacion_id, inventario):
        ItemInventario.objects.update_or_create(producto_id=producto_id, ubicacion_id=ubicacion_id,
            defaults={"existencia": inventario.existencia, "reservado": inventario.reservado,
                "minimo": inventario.minimo})


class TransaccionORM:
    def __enter__(self):
        self.contexto = transaction.atomic()
        return self.contexto.__enter__()

    def __exit__(self, *args):
        return self.contexto.__exit__(*args)


class DatosORM:
    """Adaptador de acceso a los agregados; no decide reglas de negocio."""
    def obtener(self, entidad, id):
        modelo = getattr(models, entidad)
        try:
            return modelo.objects.get(pk=id)
        except (modelo.DoesNotExist, ValueError, TypeError):
            exigir(False, f"No existe {entidad} con ese identificador.")

    def listar(self, entidad, **filtros):
        return getattr(models, entidad).objects.filter(**filtros)

    def crear(self, entidad, **datos):
        return getattr(models, entidad).objects.create(**datos)

    def guardar(self, objeto):
        objeto.save()

    def producto_dominio(self, id):
        from src.infraestructura.mapeadores import producto_dominio
        return producto_dominio(self.obtener("Producto", id))
