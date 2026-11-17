from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from config.composicion import operaciones
from src.aplicacion.reportes import Reportes
from src.dominio.reglas import ErrorNegocio
from src.infraestructura.repositorios import DatosORM
from src.infraestructura.persistencia import models as m


class Escenario(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cd = m.Ubicacion.objects.create(nombre="CD", tipo="CD", direccion="CD")
        cls.local = m.Ubicacion.objects.create(nombre="Local", tipo="LOCAL", direccion="Local")
        cls.otro = m.Ubicacion.objects.create(nombre="Otro", tipo="LOCAL", direccion="Otro")
        cls.caja = m.Caja.objects.create(local=cls.local)
        m.Caja.objects.create(local=cls.otro)
        cls.admin = m.Usuario.objects.create_user(username="cd", password="Prueba_2026!", rol="ADMIN_CD", ubicacion=cls.cd)
        cls.encargado = m.Usuario.objects.create_user(username="local", password="Prueba_2026!", rol="ADMIN_MINORISTA", ubicacion=cls.local)
        cls.vendedor = m.Usuario.objects.create_user(username="vende", password="Prueba_2026!", rol="VENDEDOR", ubicacion=cls.local)
        cls.vendedor_otro = m.Usuario.objects.create_user(username="otro", password="Prueba_2026!", rol="VENDEDOR", ubicacion=cls.otro)
        cls.prov = m.Proveedor.objects.create(nombre="Prov", cuit="30712345678", direccion="P")
        cls.cat = m.Categoria.objects.create(nombre="Cat")
        cls.p = m.Producto.objects.create(nombre="Producto", sku="P1", proveedor=cls.prov, categoria=cls.cat, precio_centavos=10000)
        cls.p2 = m.Producto.objects.create(nombre="Producto 2", sku="P2", proveedor=cls.prov, categoria=cls.cat, precio_centavos=15000)
        for p in [cls.p, cls.p2]:
            for u in [cls.cd, cls.local, cls.otro]: m.ItemInventario.objects.create(producto=p, ubicacion=u, minimo=5)

    def setUp(self):
        self.s = operaciones()

    def stock(self, ubicacion, producto=None):
        return m.ItemInventario.objects.get(producto=producto or self.p, ubicacion=ubicacion)

    def comprar(self, cantidad=30, costo="50", producto=None):
        c = self.s.emitir_compra(self.admin, self.prov.pk, [((producto or self.p).pk, cantidad, costo)])
        self.s.avanzar_compra(self.admin, c.pk, "RECIBIDA")
        self.s.avanzar_compra(self.admin, c.pk, "VERIFICADA")
        return c

    def enviar(self, cantidades=(5,)):
        self.comprar()
        orden = self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, sum(cantidades))])
        bultos = []
        for n in cantidades:
            b = self.s.preparar(self.admin, orden.detalles.first().pk, n)
            self.s.precintar(self.admin, b.pk, f"P-{b.pk}")
            bultos.append(b)
        remito = orden.remito
        self.s.despachar(self.admin, remito.pk)
        self.s.recibir(self.encargado, remito.pk)
        return orden, remito, bultos

    def habilitar(self, cantidad=5):
        orden, remito, bultos = self.enviar((cantidad,))
        self.s.controlar(self.encargado, bultos[0].pk, True, True)
        self.s.cerrar_remito(self.encargado, remito.pk)
        return orden, remito, bultos

    def vender(self, cantidad=2, medio="EFECTIVO"):
        return self.s.vender(self.vendedor, medio, [(self.p.pk, cantidad)], uuid4())

