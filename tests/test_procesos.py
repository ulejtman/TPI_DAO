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


from tests import escenario


class ProcesosTest(escenario.Escenario):
    def test_compra_solo_verificada_suma(self):
        c = self.s.emitir_compra(self.admin, self.prov.pk, [(self.p.pk, 10, "40")])
        self.s.avanzar_compra(self.admin, c.pk, "RECIBIDA")
        self.assertEqual(self.stock(self.cd).existencia, 0)
        self.s.avanzar_compra(self.admin, c.pk, "VERIFICADA")
        with self.assertRaises(ErrorNegocio): self.s.avanzar_compra(self.admin, c.pk, "VERIFICADA")
        self.assertEqual(self.stock(self.cd).existencia, 10)

    def test_rechaza_otro_proveedor(self):
        proveedor = m.Proveedor.objects.create(nombre="Otro", cuit="30712345679", direccion="O")
        with self.assertRaises(ErrorNegocio): self.s.emitir_compra(self.admin, proveedor.pk, [(self.p.pk, 1, "40")])
        self.assertFalse(m.Compra.objects.exists())

    def test_cierre_remito_es_barrera_stock(self):
        orden, remito, bs = self.enviar((3, 2))
        self.s.controlar(self.encargado, bs[0].pk, True, True)
        self.assertEqual(self.stock(self.local).existencia, 0)
        self.assertEqual((self.stock(self.cd).existencia, self.stock(self.cd).reservado), (30, 5))
        with self.assertRaises(ErrorNegocio): self.s.cerrar_remito(self.encargado, remito.pk)
        with self.assertRaises(ErrorNegocio): self.vender(1)
        self.s.controlar(self.encargado, bs[1].pk, True, True)
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.assertEqual(self.stock(self.local).existencia, 5)
        self.assertEqual((self.stock(self.cd).existencia, self.stock(self.cd).reservado), (25, 0))
        self.assertEqual(orden.estado, "FINALIZADA")
        with self.assertRaises(ErrorNegocio): self.s.cerrar_remito(self.encargado, remito.pk)
        self.assertEqual(self.stock(self.local).existencia, 5)

    def test_rechazo_total_reingreso(self):
        orden, remito, bs = self.enviar()
        self.s.controlar(self.encargado, bs[0].pk, True, False)
        self.assertEqual(bs[0].estado, "RECHAZADO")
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.assertEqual(remito.estado, "RECHAZADO")
        self.assertEqual(self.stock(self.local).existencia, 0)
        self.s.devolver_bulto(self.encargado, bs[0].pk)
        self.s.resolver_bulto(self.admin, bs[0].pk, True, "Revisado, apto")
        self.assertEqual((self.stock(self.cd).existencia, self.stock(self.cd).reservado), (30, 0))
        self.assertFalse(m.Merma.objects.exists())
        self.assertEqual(orden.estado, "FINALIZADA")
        self.assertTrue(bs[0].eventos.filter(estado="RECHAZADO").exists())

    def test_rechazo_mixto_baja(self):
        orden, remito, bs = self.enviar((3, 2))
        self.s.controlar(self.encargado, bs[0].pk, True, True)
        self.s.controlar(self.encargado, bs[1].pk, False, False)
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.assertEqual(self.stock(self.local).existencia, 3)
        self.s.devolver_bulto(self.encargado, bs[1].pk)
        self.s.resolver_bulto(self.admin, bs[1].pk, False, "Contenido dañado")
        self.assertEqual((self.stock(self.cd).existencia, self.stock(self.cd).reservado), (25, 0))
        self.assertEqual(m.Merma.objects.get().origen, "LOGISTICA_PRECINTO")

    def test_cancelacion_libera_reservas(self):
        self.comprar()
        orden = self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, 10)])
        b = self.s.preparar(self.admin, orden.detalles.first().pk, 5)
        self.s.precintar(self.admin, b.pk, "X")
        self.s.preparar(self.admin, orden.detalles.first().pk, 2)
        self.s.cancelar_orden(self.encargado, orden.pk)
        self.assertEqual(self.stock(self.cd).reservado, 0)
        self.assertEqual(orden.remito.estado, "CANCELADO")
        self.assertTrue(all(b.estado == "CANCELADO" for b in m.Bulto.objects.all()))
        with self.assertRaises(ErrorNegocio): self.s.cancelar_orden(self.admin, orden.pk)

    def test_no_despacho_parcial_ni_cancelacion_despachada(self):
        self.comprar()
        orden = self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, 10)])
        b = self.s.preparar(self.admin, orden.detalles.first().pk, 5)
        self.s.precintar(self.admin, b.pk, "X")
        with self.assertRaises(ErrorNegocio): self.s.despachar(self.admin, orden.remito.pk)
        b = self.s.preparar(self.admin, orden.detalles.first().pk, 5)
        self.s.precintar(self.admin, b.pk, "Y")
        self.s.despachar(self.admin, orden.remito.pk)
        with self.assertRaises(ErrorNegocio): self.s.cancelar_orden(self.admin, orden.pk)

    def test_no_sobre_reservar(self):
        self.comprar(3)
        o = self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, 5)])
        self.s.preparar(self.admin, o.detalles.first().pk, 3)
        with self.assertRaises(ErrorNegocio): self.s.preparar(self.admin, o.detalles.first().pk, 1)
        self.assertEqual(self.stock(self.cd).reservado, 3)

    def test_venta_idempotente_y_precios_historicos(self):
        self.habilitar()
        id = uuid4()
        v = self.s.vender(self.vendedor, "EFECTIVO", [(self.p.pk, 2)], id)
        self.s.vender(self.vendedor, "EFECTIVO", [(self.p.pk, 2)], id)
        self.assertEqual(m.Venta.objects.count(), 1)
        self.assertEqual(self.stock(self.local).existencia, 3)
        self.assertEqual(self.caja.saldo, 20000)
        self.p.precio_centavos = 20000
        self.p.save()
        self.comprar(costo="70")
        d = v.detalles.get()
        self.assertEqual((d.precio_centavos, d.costo_centavos), (10000, 5000))

    def test_electronico_no_modifica_efectivo(self):
        self.habilitar()
        v = self.vender(medio="DEBITO")
        self.assertEqual(self.caja.saldo, 0)
        self.s.devolver_venta(self.vendedor, v.pk, "Prueba", [(v.detalles.first().pk, 1, True)], uuid4())
        self.assertEqual(self.caja.saldo, 0)
        self.assertEqual(self.caja.movimientos.count(), 2)

    def test_devoluciones_acumuladas_y_merma(self):
        self.habilitar()
        v = self.vender(3)
        d = v.detalles.first()
        id = uuid4()
        self.s.devolver_venta(self.vendedor, v.pk, "Apto", [(d.pk, 1, True)], id)
        self.s.devolver_venta(self.vendedor, v.pk, "Apto", [(d.pk, 1, True)], id)
        self.s.devolver_venta(self.vendedor, v.pk, "Dañado", [(d.pk, 2, False)], uuid4())
        self.assertEqual(self.stock(self.local).existencia, 3)
        self.assertEqual(m.Merma.objects.get().cantidad, 2)
        self.assertEqual(self.caja.saldo, 0)
        with self.assertRaises(ErrorNegocio): self.s.devolver_venta(self.vendedor, v.pk, "Exceso", [(d.pk, 1, True)], uuid4())
        self.assertEqual(m.Devolucion.objects.count(), 2)

    def test_devolucion_saldo_insuficiente_no_deja_efectos(self):
        self.habilitar()
        v = self.vender()
        self.s.mover_caja(self.encargado, self.local.pk, "RETIRO", "200", "Retiro", uuid4())
        with self.assertRaises(ErrorNegocio): self.s.devolver_venta(self.vendedor, v.pk, "Prueba", [(v.detalles.first().pk, 1, True)], uuid4())
        self.assertFalse(m.Devolucion.objects.exists())
        self.assertEqual(self.stock(self.local).existencia, 3)
        self.assertEqual(m.Comprobante.objects.count(), 1)

    def test_plazo_y_venta_ajena(self):
        self.habilitar()
        v = self.vender()
        with self.assertRaises(ErrorNegocio): self.s.devolver_venta(self.vendedor_otro, v.pk, "Otro local", [(v.detalles.first().pk, 1, True)], uuid4())
        self.s.ahora = lambda: timezone.now()+timedelta(days=31)
        with self.assertRaises(ErrorNegocio): self.s.devolver_venta(self.vendedor, v.pk, "Tarde", [(v.detalles.first().pk, 1, True)], uuid4())

    def test_rollback_fallo_intermedio(self):
        self.habilitar()
        original = self.s.db.crear
        def fallar(entidad, **kwargs):
            if entidad == "MovimientoCaja": raise RuntimeError("Fallo simulado")
            return original(entidad, **kwargs)
        with patch.object(self.s.db, "crear", side_effect=fallar), self.assertRaises(RuntimeError): self.vender()
        self.assertEqual(self.stock(self.local).existencia, 5)
        self.assertFalse(m.Venta.objects.exists())
        self.assertFalse(m.Comprobante.objects.exists())

    def test_historial_no_se_edita(self):
        c = self.comprar()
        e = c.eventos.first()
        with self.assertRaises(ValueError): e.save()
        with self.assertRaises(ValueError): e.delete()
        with self.assertRaises(ValueError): c.eventos.update(estado="X")
        with self.assertRaises(ValueError): c.eventos.all().delete()

    def test_permisos_de_servicio(self):
        with self.assertRaises(ErrorNegocio): self.s.emitir_compra(self.vendedor, self.prov.pk, [(self.p.pk, 1, "1")])
        with self.assertRaises(ErrorNegocio): self.s.solicitar(self.encargado, self.otro.pk, [(self.p.pk, 1)])

    def test_reportes_importes_y_costos(self):
        self.habilitar()
        v = self.vender(3)
        self.s.devolver_venta(self.vendedor, v.pk, "Prueba", [(v.detalles.first().pk, 1, True)], uuid4())
        r = Reportes(DatosORM(), self.s)
        ingreso = r.generar(self.admin, "ingresos")
        self.assertEqual(ingreso["totales"], {"bruto": 30000, "reintegros": 10000, "neto": 20000})
        self.assertEqual(r.generar(self.admin, "margen")["totales"]["margen"], 10000)
        with self.assertRaises(ErrorNegocio): r.generar(self.encargado, "ingresos", local_id=self.otro.pk)
        with self.assertRaises(ErrorNegocio): r.generar(self.vendedor, "ingresos")

    def test_reportes_rechazo_conserva_historia_y_separa_merma(self):
        _, remito, bs = self.enviar()
        self.s.controlar(self.encargado, bs[0].pk, False, False)
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.s.devolver_bulto(self.encargado, bs[0].pk)
        self.s.resolver_bulto(self.admin, bs[0].pk, False, "Roto")
        r = Reportes(DatosORM(), self.s).generar(self.admin, "rechazos")
        self.assertEqual(r["totales"], {"bultos_rechazados": 1, "unidades_rechazadas": 5, "unidades_merma": 5})
        self.assertEqual(len(r["filas"]), 2)

    def test_stock_minimo_reporte_y_transito(self):
        _, _, bs = self.enviar()
        r = Reportes(DatosORM(), self.s).generar(self.encargado, "existencias")
        producto = next(f for f in r["filas"] if f[1] == str(self.p))
        self.assertEqual(producto[5], 5)
        self.assertEqual(producto[-1], "En mínimo")
