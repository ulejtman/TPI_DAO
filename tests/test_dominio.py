from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase
from src.dominio.reglas import ErrorNegocio, Inventario, consolidar, centavos, validar_transicion, validar_devolucion


class ReglasTest(TestCase):
    def test_dinero_exacto(self):
        self.assertEqual(centavos(Decimal("0.29")), 29)
        for valor in ["NaN", "Infinity", "-1", "1.001", "abc"]:
            with self.subTest(valor=valor), self.assertRaises(ErrorNegocio): centavos(valor)

    def test_reservas_y_venta(self):
        i = Inventario(10)
        i.reservar(7)
        self.assertEqual(i.disponible, 3)
        with self.assertRaises(ErrorNegocio): i.reservar(4)
        i.liberar(7, descontar=True)
        self.assertEqual((i.existencia, i.reservado), (3, 0))
        i.vender(3)
        self.assertEqual(i.disponible, 0)

    def test_consolidacion(self):
        self.assertEqual(consolidar([(1, 2), (1, 3)]), {1: 5})
        for lineas in [[], [(1, 0)], [(1, 1.5)], [(1, True)]]:
            with self.assertRaises(ErrorNegocio): consolidar(lineas)

    def test_estados_no_saltan(self):
        validar_transicion("BULTO", "PREPARADO", "PRECINTADO")
        with self.assertRaises(ErrorNegocio): validar_transicion("BULTO", "PREPARADO", "VERIFICADO")

    def test_plazo_inclusivo_y_cantidad(self):
        venta = datetime(2026, 1, 1, tzinfo=timezone.utc)
        validar_devolucion(venta, venta+timedelta(days=30), 30, 3, 1, 2)
        with self.assertRaises(ErrorNegocio): validar_devolucion(venta, venta+timedelta(days=30, seconds=1), 30, 3, 0, 1)
        with self.assertRaises(ErrorNegocio): validar_devolucion(venta, venta, 30, 3, 2, 2)
