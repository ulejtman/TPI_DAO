from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep
from uuid import uuid4
from django.db import close_old_connections, OperationalError
from django.test import TransactionTestCase
from config.composicion import operaciones
from src.dominio.reglas import ErrorNegocio
from src.infraestructura.persistencia import models as m
from tests.escenario import Escenario


class ConcurrenciaTest(TransactionTestCase):
    def setUp(self):
        Escenario.setUpTestData.__func__(type(self))
        self.s = operaciones()
        Escenario.habilitar(self, 1)

    comprar = Escenario.comprar
    enviar = Escenario.enviar
    stock = Escenario.stock

    def test_dos_ventas_compiten_por_ultima_unidad(self):
        barrera = Barrier(2)
        vendedor_id = self.vendedor.pk
        producto_id = self.p.pk
        def intentar():
            close_old_connections()
            usuario = m.Usuario.objects.get(pk=vendedor_id)
            barrera.wait(timeout=10)
            try:
                for intento in range(30):
                    try:
                        operaciones().vender(usuario, 'EFECTIVO', [(producto_id, 1)], uuid4())
                        return 'vendida'
                    except ErrorNegocio:
                        return 'sin_stock'
                    except OperationalError:
                        sleep(0.02)
                return 'ocupada'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: intentar(), range(2)))
        self.assertCountEqual(resultados, ['vendida', 'sin_stock'])
        self.assertEqual(m.Venta.objects.count(), 1)
        self.assertEqual(self.stock(self.local).existencia, 0)

    def test_dos_reservas_compiten_por_stock_disponible(self):
        disponible = self.stock(self.cd).disponible
        ordenes = [self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, disponible)]) for _ in range(2)]
        ids = [o.detalles.first().pk for o in ordenes]
        barrera = Barrier(2)
        admin_id = self.admin.pk
        def intentar(detalle_id):
            close_old_connections()
            usuario = m.Usuario.objects.get(pk=admin_id)
            barrera.wait(timeout=10)
            try:
                for intento in range(30):
                    try:
                        operaciones().preparar(usuario, detalle_id, disponible)
                        return 'reservada'
                    except ErrorNegocio:
                        return 'sin_stock'
                    except OperationalError:
                        sleep(0.02)
                return 'ocupada'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(intentar, ids))
        self.assertCountEqual(resultados, ['reservada', 'sin_stock'])
        self.assertEqual(self.stock(self.cd).disponible, 0)
