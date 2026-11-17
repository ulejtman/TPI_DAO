from datetime import timedelta
from io import StringIO
from uuid import uuid4
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from config.composicion import operaciones
from src.aplicacion.reportes import Reportes
from src.infraestructura.persistencia import models as m
from src.infraestructura.repositorios import DatosORM
from tests import escenario


class CasosAdicionalesTest(escenario.Escenario):
    def test_cierre_atomico_ante_fallo_de_inventario(self):
        _, r, bs = self.enviar()
        self.s.controlar(self.encargado, bs[0].pk, True, True)
        guardar = self.s.inv.guardar
        contador = 0
        def fallar(*args):
            nonlocal contador
            contador += 1
            if contador == 2: raise RuntimeError('Fallo al ingresar en destino')
            return guardar(*args)
        with patch.object(self.s.inv, 'guardar', side_effect=fallar), self.assertRaises(RuntimeError):
            self.s.cerrar_remito(self.encargado, r.pk)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'RECIBIDO')
        self.assertIsNone(r.fecha_cierre)
        self.assertEqual((self.stock(self.cd).existencia, self.stock(self.cd).reservado), (30, 5))
        self.assertEqual(self.stock(self.local).existencia, 0)

    def test_unicidad_sku_cuit_cd_y_evento(self):
        for tipo, datos in [
            (m.Producto, {'sku': self.p.sku, 'nombre': 'Duplicado', 'categoria': self.cat, 'proveedor': self.prov}),
            (m.Proveedor, {'cuit': self.prov.cuit, 'nombre': 'Duplicado', 'direccion': 'D'}),
            (m.Ubicacion, {'tipo': 'CD', 'nombre': 'Otro CD', 'direccion': 'D'}),
            (m.EventoEstado, {'usuario': self.admin, 'ambito': 'BULTO', 'estado': 'PREPARADO'}),
        ]:
            with self.subTest(modelo=tipo.__name__), self.assertRaises(IntegrityError), transaction.atomic():
                tipo.objects.create(**datos)

    def test_usuarios_se_crean_con_clave_y_rol_coherente(self):
        self.client.force_login(self.admin)
        datos = {'username': 'nuevo', 'first_name': 'Nuevo', 'last_name': 'Usuario', 'rol': 'VENDEDOR',
            'ubicacion': self.local.pk, 'is_active': 'on', 'clave': 'ClaveNueva_2026!'}
        self.assertEqual(self.client.post(reverse('maestro_nuevo', args=['usuarios']), datos).status_code, 302)
        user = m.Usuario.objects.get(username='nuevo')
        self.assertTrue(user.check_password('ClaveNueva_2026!'))
        datos.update(username='invalido', ubicacion=self.cd.pk)
        self.assertContains(self.client.post(reverse('maestro_nuevo', args=['usuarios']), datos), 'corresponder al rol')
        self.assertFalse(m.Usuario.objects.filter(username='invalido').exists())

    def test_buscar_venta_sin_ticket_en_mismo_local(self):
        self.habilitar()
        v = self.s.vender(self.vendedor, 'DEBITO', [(self.p.pk, 1)], uuid4())
        self.client.force_login(self.vendedor)
        self.assertRedirects(self.client.get(reverse('buscar_venta'), {'venta_id': v.pk}), reverse('accion_objeto', args=['devolucion', v.pk]))
        self.client.force_login(self.vendedor_otro)
        self.assertEqual(self.client.get(reverse('buscar_venta'), {'venta_id': v.pk}).status_code, 404)

    def test_reintegro_se_imputa_a_otro_periodo(self):
        self.habilitar()
        v = self.s.vender(self.vendedor, 'DEBITO', [(self.p.pk, 2)], uuid4())
        fecha_futura = timezone.now()+timedelta(days=1)
        self.s.ahora = lambda: fecha_futura
        # La fecha de registro se controla en el adaptador para simular el día siguiente.
        crear = self.s.db.crear
        def futuro(entidad, **datos):
            if entidad in {'Devolucion', 'Comprobante', 'MovimientoCaja'}: datos['fecha'] = fecha_futura
            return crear(entidad, **datos)
        with patch.object(self.s.db, 'crear', side_effect=futuro):
            self.s.devolver_venta(self.vendedor, v.pk, 'Día siguiente', [(v.detalles.first().pk, 1, True)], uuid4())
        dia = timezone.localtime(fecha_futura).date()
        r = Reportes(DatosORM(), self.s).generar(self.admin, 'ingresos', desde=dia, hasta=dia)
        self.assertEqual(r['totales'], {'bruto': 0, 'reintegros': 10000, 'neto': -10000})

    def test_ultima_compra_no_verificada_no_cambia_costo(self):
        self.habilitar()
        c = self.s.emitir_compra(self.admin, self.prov.pk, [(self.p.pk, 10, '999')])
        self.s.avanzar_compra(self.admin, c.pk, 'RECIBIDA')
        v = self.s.vender(self.vendedor, 'EFECTIVO', [(self.p.pk, 1)], uuid4())
        self.assertEqual(v.detalles.first().costo_centavos, 5000)


class InicioDemoTest(TestCase):
    def test_demo_crea_recorrido_y_no_sobrescribe(self):
        call_command('datos_demo', stdout=StringIO())
        self.assertEqual(m.Usuario.objects.count(), 5)
        self.assertEqual(m.Venta.objects.count(), 3)
        self.assertEqual(m.Merma.objects.count(), 1)
        antes = m.EventoEstado.objects.count()
        with self.assertRaises(CommandError): call_command('datos_demo', stdout=StringIO())
        self.assertEqual(m.EventoEstado.objects.count(), antes)
