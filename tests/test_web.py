from uuid import uuid4
from django.test import Client
from django.urls import reverse
from tests import escenario
from src.infraestructura.persistencia import models as m
from src.dominio.reglas import ErrorNegocio


class PantallasTest(escenario.Escenario):
    def login(self, usuario=None):
        self.client.force_login(usuario or self.admin)

    def test_acceso_y_salir_por_post(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertContains(self.client.get('/acceso/'), 'Ingresar al sistema')
        self.assertTrue(self.client.login(username='cd', password='Prueba_2026!'))
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/salir/').status_code, 405)
        self.assertEqual(self.client.post('/salir/').status_code, 302)

    def test_listados_y_formularios_admin(self):
        self.login()
        from src.presentacion.vistas import SECCIONES, MAESTROS
        for tipo in SECCIONES:
            with self.subTest(tipo=tipo): self.assertEqual(self.client.get(reverse('listado', args=[tipo])).status_code, 200)
        for tipo in MAESTROS:
            if tipo != 'inventario':
                with self.subTest(formulario=tipo): self.assertEqual(self.client.get(reverse('maestro_nuevo', args=[tipo])).status_code, 200)
        for accion in ['compra', 'orden', 'movimiento']:
            self.assertEqual(self.client.get(reverse('accion', args=[accion])).status_code, 200)

    def test_detalles_y_cuatro_reportes(self):
        o, r, bs = self.habilitar()
        v = self.vender()
        self.login()
        objetos = [('compras', m.Compra.objects.first().pk), ('ordenes', o.pk), ('remitos', r.pk), ('bultos', bs[0].pk), ('ventas', v.pk), ('cajas', self.caja.pk)]
        for tipo, id in objetos:
            with self.subTest(tipo=tipo): self.assertEqual(self.client.get(reverse('detalle', args=[tipo, id])).status_code, 200)
        for tipo in ['ingresos', 'margen', 'existencias', 'rechazos']:
            with self.subTest(reporte=tipo): self.assertEqual(self.client.get(reverse('reporte', args=[tipo])).status_code, 200)
        self.assertContains(self.client.get(reverse('comprobante', args=[v.comprobante_id])), 'Sin validez fiscal')

    def test_venta_desde_formulario_y_reintento(self):
        self.habilitar()
        self.login(self.vendedor)
        datos = {'medio': 'EFECTIVO', 'operacion': str(uuid4()), 'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0', 'lineas-MIN_NUM_FORMS': '1', 'lineas-MAX_NUM_FORMS': '100',
            'lineas-0-producto': str(self.p.pk), 'lineas-0-cantidad': '2'}
        response = self.client.post(reverse('accion', args=['venta']), datos)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(m.Venta.objects.count(), 1)
        self.client.post(reverse('accion', args=['venta']), datos)
        self.assertEqual(m.Venta.objects.count(), 1)
        v = m.Venta.objects.get()
        datos = {'motivo': 'Prueba', 'operacion': str(uuid4()), 'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0', 'lineas-MIN_NUM_FORMS': '1', 'lineas-MAX_NUM_FORMS': '100',
            'lineas-0-detalle': str(v.detalles.first().pk), 'lineas-0-cantidad': '1', 'lineas-0-apto': 'on'}
        response = self.client.post(reverse('accion_objeto', args=['devolucion', v.pk]), datos)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(m.Devolucion.objects.count(), 1)
        self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_stock_insuficiente_muestra_error(self):
        self.login(self.vendedor)
        datos = {'medio': 'EFECTIVO', 'operacion': str(uuid4()), 'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0', 'lineas-0-producto': str(self.p.pk), 'lineas-0-cantidad': '2'}
        respuesta = self.client.post(reverse('accion', args=['venta']), datos)
        self.assertContains(respuesta, 'Stock disponible insuficiente')
        self.assertFalse(m.Venta.objects.exists())

    def test_permisos_y_manipulacion_ids(self):
        _, r, _ = self.habilitar()
        v = self.vender()
        self.login(self.vendedor_otro)
        for url in [reverse('accion', args=['compra']), reverse('reporte', args=['ingresos']), reverse('maestro_nuevo', args=['productos'])]:
            self.assertEqual(self.client.get(url).status_code, 403)
        for url in [reverse('detalle', args=['ventas', v.pk]), reverse('comprobante', args=[v.comprobante_id])]:
            self.assertIn(self.client.get(url).status_code, [403, 404])
        self.login(self.encargado)
        respuesta = self.client.get(reverse('reporte', args=['ingresos']), {'local': self.otro.pk})
        self.assertContains(respuesta, 'opción válida')

    def test_csrf_real_y_no_mutaciones_get(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('accion', args=['compra']), {}).status_code, 403)
        self.client.force_login(self.admin)
        self.client.get(reverse('accion', args=['compra']))
        self.assertFalse(m.Compra.objects.exists())

    def test_formularios_maestros_precio_normalizacion_y_minimo(self):
        self.login()
        response = self.client.post(reverse('maestro_nuevo', args=['productos']), {
            'sku': ' nuevo-1 ', 'nombre': 'Nuevo', 'categoria': self.cat.pk,
            'proveedor': self.prov.pk, 'precio': '12.30', 'activo': 'on'})
        self.assertEqual(response.status_code, 302)
        p = m.Producto.objects.get(sku='NUEVO-1')
        self.assertEqual(p.precio_centavos, 1230)
        self.assertEqual(m.ItemInventario.objects.filter(producto=p).count(), 3)
        i = self.stock(self.local)
        self.client.post(reverse('maestro_editar', args=['inventario', i.pk]), {'producto': self.p.pk, 'ubicacion': self.local.pk, 'minimo': '8', 'existencia': '999'})
        i.refresh_from_db()
        self.assertEqual((i.minimo, i.existencia), (8, 0))

    def test_formulario_control_y_cierre(self):
        _, r, bs = self.enviar()
        self.login(self.encargado)
        self.assertEqual(self.client.get(reverse('accion_objeto', args=['controlar', bs[0].pk])).status_code, 200)
        response = self.client.post(reverse('accion_objeto', args=['controlar', bs[0].pk]), {
            'precinto_integro': 'on', 'aceptar': 'on', 'operacion': str(uuid4()), 'motivo': '', 'observacion': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.stock(self.local).existencia, 0)
        response = self.client.post(reverse('accion_objeto', args=['cerrar', r.pk]), {'operacion': str(uuid4())})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.stock(self.local).existencia, 5)

    def test_inmutabilidad_financiera(self):
        self.habilitar()
        v = self.vender()
        for obj in [v, v.comprobante, v.detalles.first(), self.caja.movimientos.first()]:
            with self.subTest(modelo=type(obj).__name__), self.assertRaises(ValueError): obj.save()
