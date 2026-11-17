"""Contratos de State y Strategy y regresión de sus efectos observables."""
from datetime import date, datetime, timedelta, timezone as tz
from types import SimpleNamespace
from unittest import TestCase as PruebaPura
from unittest.mock import Mock, patch
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone

from src.aplicacion.reportes import FiltrosReporte, Reportes
from src.dominio.estados import CicloBulto, CicloRemito, BultoPreparado, RemitoRecibido
from src.dominio.reglas import ErrorNegocio, validar_transicion
from src.infraestructura.persistencia import models as m
from src.infraestructura.repositorios import DatosORM
from tests.escenario import Escenario


class StateTest(PruebaPura):
    # Oráculo independiente: ciclos acordados en la documentación del negocio.
    arcos = {
        "BULTO": {
            None: {"PREPARADO"}, "PREPARADO": {"PRECINTADO", "CANCELADO"},
            "PRECINTADO": {"EN_TRANSITO", "CANCELADO"}, "EN_TRANSITO": {"RECIBIDO"},
            "RECIBIDO": {"VERIFICADO", "RECHAZADO"}, "RECHAZADO": {"EN_DEVOLUCION_AL_CD"},
            "EN_DEVOLUCION_AL_CD": {"REINGRESADO", "DADO_DE_BAJA"},
            "VERIFICADO": set(), "REINGRESADO": set(), "DADO_DE_BAJA": set(), "CANCELADO": set(),
        },
        "REMITO": {
            None: {"EMITIDO"}, "EMITIDO": {"EN_TRANSITO", "CANCELADO"},
            "EN_TRANSITO": {"RECIBIDO"}, "RECIBIDO": {"VERIFICADO", "RECHAZADO"},
            "VERIFICADO": set(), "RECHAZADO": set(), "CANCELADO": set(),
        },
    }

    def test_matriz_completa_de_transiciones(self):
        for ambito, arcos in self.arcos.items():
            for anterior in [*arcos, "DESCONOCIDO"]:
                for siguiente in [*arcos, "DESCONOCIDO"]:
                    with self.subTest(ambito=ambito, anterior=anterior, siguiente=siguiente):
                        if siguiente in arcos.get(anterior, set()):
                            validar_transicion(ambito, anterior, siguiente)
                        else:
                            with self.assertRaises(ErrorNegocio):
                                validar_transicion(ambito, anterior, siguiente)

    def test_contexto_delega_y_cambia_su_estado(self):
        ciclo = CicloBulto("PREPARADO")
        with patch.object(BultoPreparado, "accion_precintar", return_value="PRECINTADO") as accion:
            self.assertEqual(ciclo.ejecutar("precintar"), "PRECINTADO")
        accion.assert_called_once_with()
        self.assertEqual(ciclo.estado.nombre, "PRECINTADO")
        self.assertEqual(ciclo.ejecutar("despachar"), "EN_TRANSITO")
        with self.assertRaises(ErrorNegocio):
            ciclo.ejecutar("cancelar")
        self.assertEqual(ciclo.estado.nombre, "EN_TRANSITO")
        remito = CicloRemito("RECIBIDO")
        with patch.object(RemitoRecibido, "accion_cerrar", return_value="RECHAZADO") as cerrar:
            self.assertEqual(remito.ejecutar("cerrar", estados_bultos=["RECHAZADO"]), "RECHAZADO")
        cerrar.assert_called_once_with(estados_bultos=["RECHAZADO"])

    def test_estados_y_acciones_desconocidos(self):
        for ciclo in (CicloBulto, CicloRemito):
            with self.assertRaises(ErrorNegocio):
                ciclo("DESCONOCIDO")
            with self.assertRaises(ErrorNegocio):
                ciclo().ejecutar("inventada")
        with self.assertRaises(ErrorNegocio):
            validar_transicion("INVENTADO", None, "PREPARADO")

    def test_control_precinto_y_motivos(self):
        for aceptar, integro, motivo, observacion, esperado in [
            (True, True, "", "", "VERIFICADO"),
            (True, False, "", "", "RECHAZADO"),
            (False, True, "ENVIO_ERRONEO", "", "RECHAZADO"),
            (False, True, "OTRO", "Detalle", "RECHAZADO"),
        ]:
            with self.subTest(aceptar=aceptar, integro=integro, motivo=motivo):
                self.assertEqual(CicloBulto("RECIBIDO").ejecutar("controlar", aceptar=aceptar,
                    precinto_integro=integro, motivo=motivo, observacion=observacion), esperado)
        for motivo in ("", "INVALIDO", "OTRO"):
            ciclo = CicloBulto("RECIBIDO")
            with self.assertRaises(ErrorNegocio):
                ciclo.ejecutar("controlar", aceptar=False, precinto_integro=True, motivo=motivo)
            self.assertEqual(ciclo.estado.nombre, "RECIBIDO")

    def test_cierre_todos_controlados_y_resultado(self):
        for estados, esperado in [(["VERIFICADO"], "VERIFICADO"),
                                 (["RECHAZADO"], "RECHAZADO"),
                                 (["VERIFICADO", "RECHAZADO"], "VERIFICADO")]:
            self.assertEqual(CicloRemito("RECIBIDO").ejecutar("cerrar", estados_bultos=estados), esperado)
        for estados in ([], ["RECIBIDO"], ["VERIFICADO", "RECIBIDO"], ["CANCELADO"]):
            ciclo = CicloRemito("RECIBIDO")
            with self.assertRaises(ErrorNegocio):
                ciclo.ejecutar("cerrar", estados_bultos=estados)
            self.assertEqual(ciclo.estado.nombre, "RECIBIDO")

    def test_retorno_y_revision_obligatorios(self):
        with self.assertRaises(ErrorNegocio):
            CicloBulto("RECHAZADO").ejecutar("retornar", remito_cerrado=False)
        ciclo = CicloBulto("RECHAZADO")
        self.assertEqual(ciclo.ejecutar("retornar", remito_cerrado=True), "EN_DEVOLUCION_AL_CD")
        with self.assertRaises(ErrorNegocio):
            ciclo.ejecutar("resolver", recuperable=True, observacion=" ")
        self.assertEqual(ciclo.estado.nombre, "EN_DEVOLUCION_AL_CD")
        self.assertEqual(ciclo.ejecutar("resolver", recuperable=False, observacion="Roto"), "DADO_DE_BAJA")


class StrategyTest(PruebaPura):
    def setUp(self):
        self.datos = object()
        self.ops = Mock()
        self.estrategia = Mock()
        self.resultado = {"titulo": "Prueba", "columnas": [], "filas": [], "nota": "", "totales": {}}
        self.estrategia.generar.return_value = self.resultado
        self.reportes = Reportes(self.datos, self.ops, {"prueba": self.estrategia})
        self.usuario = SimpleNamespace(rol="ADMIN_MINORISTA", ubicacion_id=7)

    def test_estrategia_sustituible_recibe_filtros_normalizados(self):
        resultado = self.reportes.generar(self.usuario, "prueba", desde=date(2026, 1, 1),
            categoria_id=3, medio="DEBITO", motivo="OTRO")
        self.assertIs(resultado, self.resultado)
        self.estrategia.generar.assert_called_once_with(self.datos,
            FiltrosReporte(date(2026, 1, 1), None, 7, 3, "DEBITO", "OTRO"))
        self.ops.acceso.assert_called_once_with(self.usuario, {"ADMIN_CD", "ADMIN_MINORISTA"})

    def test_errores_se_rechazan_antes_de_invocar_estrategia(self):
        for kwargs in ({"local_id": 8}, {"desde": date(2026, 2, 1), "hasta": date(2026, 1, 1)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ErrorNegocio):
                self.reportes.generar(self.usuario, "prueba", **kwargs)
        with self.assertRaises(ErrorNegocio):
            self.reportes.generar(self.usuario, "desconocido")
        self.ops.acceso.side_effect = ErrorNegocio("Sin permiso")
        with self.assertRaises(ErrorNegocio):
            self.reportes.generar(self.usuario, "prueba")
        self.estrategia.generar.assert_not_called()
        with self.assertRaises(ErrorNegocio):
            Reportes(self.datos, Mock(), {}).generar(self.usuario, "ingresos")


class IntegracionPatronesTest(Escenario):
    def reportar(self, tipo, usuario=None, **filtros):
        return Reportes(DatosORM(), self.s).generar(usuario or self.admin, tipo, **filtros)

    def fotografia(self):
        return {modelo.__name__: list(modelo.objects.order_by("pk").values()) for modelo in (
            m.EventoEstado, m.ItemInventario, m.Bulto, m.Remito, m.OrdenReposicion, m.Merma)}

    def test_cancelacion_fallida_revierte_estados_y_reservas(self):
        self.comprar()
        orden = self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, 5)])
        for cantidad in (2, 3):
            b = self.s.preparar(self.admin, orden.detalles.first().pk, cantidad)
            self.s.precintar(self.admin, b.pk, f"P-{b.pk}")
        antes = self.fotografia()
        guardar = self.s.inv.guardar
        llamadas = 0
        def fallar(*args):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("Fallo de reserva")
            return guardar(*args)
        with patch.object(self.s.inv, "guardar", side_effect=fallar), self.assertRaises(RuntimeError):
            self.s.cancelar_orden(self.encargado, orden.pk)
        self.assertEqual(self.fotografia(), antes)
        self.s.cancelar_orden(self.encargado, orden.pk)
        self.assertEqual(self.stock(self.cd).reservado, 0)
        antes = self.fotografia()
        with self.assertRaises(ErrorNegocio):
            self.s.cancelar_orden(self.encargado, orden.pk)
        self.assertEqual(self.fotografia(), antes)

    def test_baja_fallida_revierte_evento_inventario_y_observacion(self):
        orden, remito, bs = self.enviar()
        self.s.controlar(self.encargado, bs[0].pk, True, False)
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.s.devolver_bulto(self.encargado, bs[0].pk)
        antes = self.fotografia()
        crear = self.s.db.crear
        def fallar(entidad, **datos):
            if entidad == "Merma":
                raise RuntimeError("Fallo de merma")
            return crear(entidad, **datos)
        with patch.object(self.s.db, "crear", side_effect=fallar), self.assertRaises(RuntimeError):
            self.s.resolver_bulto(self.admin, bs[0].pk, False, "No apto")
        self.assertEqual(self.fotografia(), antes)
        self.s.resolver_bulto(self.admin, bs[0].pk, False, "No apto")
        self.assertEqual(orden.estado, "FINALIZADA")
        self.assertEqual((self.stock(self.cd).existencia, self.stock(self.cd).reservado), (25, 0))
        antes = self.fotografia()
        with self.assertRaises(ErrorNegocio):
            self.s.resolver_bulto(self.admin, bs[0].pk, False, "Otra revisión")
        self.assertEqual(self.fotografia(), antes)

    def test_control_repetido_y_retorno_prematuro_no_dejan_efectos(self):
        _, remito, bs = self.enviar()
        self.s.controlar(self.encargado, bs[0].pk, True, False)
        self.assertEqual(bs[0].estado, "RECHAZADO")
        bs[0].refresh_from_db()
        self.assertEqual(bs[0].motivo_rechazo, "PRECINTO_VIOLADO")
        antes = self.fotografia()
        for accion in (lambda: self.s.controlar(self.encargado, bs[0].pk, True, True),
                       lambda: self.s.devolver_bulto(self.encargado, bs[0].pk)):
            with self.assertRaises(ErrorNegocio):
                accion()
            self.assertEqual(self.fotografia(), antes)
        self.assertEqual(self.stock(self.local).disponible, 0)

    def test_despacho_y_recepcion_fallidos_revierten_todos_los_eventos(self):
        self.comprar()
        orden = self.s.solicitar(self.encargado, self.local.pk, [(self.p.pk, 5)])
        for cantidad in (2, 3):
            b = self.s.preparar(self.admin, orden.detalles.first().pk, cantidad)
            self.s.precintar(self.admin, b.pk, f"P-{b.pk}")
        remito = orden.remito
        for accion in (lambda: self.s.despachar(self.admin, remito.pk),
                       lambda: self.s.recibir(self.encargado, remito.pk)):
            antes = self.fotografia()
            crear = self.s.db.crear
            def fallar(entidad, **datos):
                if entidad == "EventoEstado" and datos.get("bulto"):
                    raise RuntimeError("Fallo después del evento de remito")
                return crear(entidad, **datos)
            with patch.object(self.s.db, "crear", side_effect=fallar), self.assertRaises(RuntimeError):
                accion()
            self.assertEqual(self.fotografia(), antes)
            accion()
        self.assertEqual(remito.estado, "RECIBIDO")
        self.assertEqual(self.stock(self.local).disponible, 0)

    def test_orden_de_eventos_con_igual_fecha_y_reconstruccion(self):
        self.s.ahora = lambda: datetime(2026, 11, 17, 12, tzinfo=tz.utc)
        _, remito, bs = self.enviar()
        # Todos los eventos tienen la misma fecha; prevalece el identificador.
        self.assertEqual(m.Bulto.objects.get(pk=bs[0].pk).estado, "RECIBIDO")
        self.s.controlar(self.encargado, bs[0].pk, True, True)
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.assertEqual(m.Remito.objects.get(pk=remito.pk).estado, "VERIFICADO")
        self.assertEqual(self.stock(self.local).disponible, 5)

    def test_reportes_vacios_y_permisos_para_los_cuatro(self):
        totales = {"ingresos": {"bruto": 0, "reintegros": 0, "neto": 0},
                   "margen": {"margen": 0}, "existencias": {},
                   "rechazos": {"bultos_rechazados": 0, "unidades_rechazadas": 0, "unidades_merma": 0}}
        for tipo, esperado in totales.items():
            with self.subTest(tipo=tipo):
                r = self.reportar(tipo)
                self.assertEqual(set(r), {"titulo", "columnas", "filas", "nota", "totales"})
                self.assertEqual(r["totales"], esperado)
                if tipo != "existencias":
                    self.assertEqual(r["filas"], [])
                for usuario, filtros in ((self.vendedor, {}), (self.encargado, {"local_id": self.otro.pk})):
                    with self.assertRaises(ErrorNegocio):
                        self.reportar(tipo, usuario, **filtros)

    def test_ingresos_resultado_completo_y_filtros(self):
        self.habilitar()
        venta = self.vender(3)
        self.s.devolver_venta(self.vendedor, venta.pk, "Apto", [(venta.detalles.get().pk, 1, True)], uuid4())
        self.vender(1, "DEBITO")
        self.s.mover_caja(self.encargado, self.local.pk, "INGRESO", "20", "Fondo", uuid4())
        esperado = {
            "titulo": "Ventas e ingresos",
            "columnas": ["Local", "Medio", "Ventas brutas", "Reintegros", "Neto"],
            "filas": [[str(self.local), "Efectivo", "$ 300,00", "$ 100,00", "$ 200,00"]],
            "nota": "Cada operación se imputa a su fecha. Los ingresos y retiros manuales de caja no son ventas.",
            "totales": {"bruto": 30000, "reintegros": 10000, "neto": 20000},
        }
        dia = timezone.localtime(venta.fecha).date()
        self.assertEqual(self.reportar("ingresos", medio="EFECTIVO", desde=dia, hasta=dia), esperado)
        self.assertEqual(self.reportar("ingresos", self.encargado, medio="EFECTIVO"), esperado)
        self.assertEqual(self.reportar("ingresos", local_id=self.otro.pk)["filas"], [])
        self.assertEqual(self.reportar("ingresos", hasta=dia-timedelta(days=1))["filas"], [])

    def test_margen_resultado_completo_aptos_no_aptos_y_categoria(self):
        self.habilitar()
        venta = self.vender(3)
        self.s.devolver_venta(self.vendedor, venta.pk, "Mixto", [(venta.detalles.get().pk, 1, True)], uuid4())
        self.s.devolver_venta(self.vendedor, venta.pk, "Roto", [(venta.detalles.get().pk, 1, False)], uuid4())
        self.p.precio_centavos = 99999
        self.p.save()
        self.comprar(costo="999")
        esperado = {
            "titulo": "Productos y margen estimado",
            "columnas": ["Producto", "Vendidas", "Devueltas", "Unidades netas", "Ingreso neto", "Costo consumido", "Margen", "Merma devolución"],
            "filas": [[str(self.p), 3, 2, 1, "$ 100,00", "$ 100,00", "$ 0,00", "$ 50,00"]],
            "nota": "Costo histórico congelado al vender. Las devoluciones no aptas no recuperan costo. No incluye gastos operativos ni mermas logísticas.",
            "totales": {"margen": 0},
        }
        self.assertEqual(self.reportar("margen", categoria_id=self.cat.pk), esperado)
        otra = m.Categoria.objects.create(nombre="Otra")
        self.assertEqual(self.reportar("margen", categoria_id=otra.pk)["filas"], [])
        self.assertEqual(self.reportar("margen", local_id=self.otro.pk)["filas"], [])

    def test_existencias_resultado_completo_antes_y_despues_de_cierre(self):
        _, remito, bs = self.enviar()
        self.s.controlar(self.encargado, bs[0].pk, True, True)
        esperado = {
            "titulo": "Existencias y stock mínimo",
            "columnas": ["Ubicación", "Producto", "Existencia contable", "Reservado", "Disponible", "Pendiente de ingreso", "Mínimo", "Situación"],
            "filas": [[str(self.local), str(self.p), 0, 0, 0, 5, 5, "En mínimo"],
                      [str(self.local), str(self.p2), 0, 0, 0, 0, 5, "En mínimo"]],
            "nota": "Foto actual: no aplica el período. El tránsito sigue contabilizado y reservado en el CD hasta el cierre del remito.",
            "totales": {},
        }
        self.assertEqual(self.reportar("existencias", self.encargado, desde=date(2000, 1, 1), hasta=date(2000, 1, 2)), esperado)
        cd = self.reportar("existencias", local_id=self.cd.pk)
        self.assertEqual(cd["filas"][0][2:6], [30, 5, 25, 0])
        self.s.cerrar_remito(self.encargado, remito.pk)
        esperado["filas"][0][2:6] = [5, 0, 5, 0]
        self.assertEqual(self.reportar("existencias", self.encargado), esperado)
        otra = m.Categoria.objects.create(nombre="Otra")
        self.assertEqual(self.reportar("existencias", categoria_id=otra.pk)["filas"], [])

    def test_margen_periodo_de_reintegro_y_orden_por_unidades_netas(self):
        self.habilitar()
        self.comprar(producto=self.p2)
        orden = self.s.solicitar(self.encargado, self.local.pk, [(self.p2.pk, 2)])
        bulto = self.s.preparar(self.admin, orden.detalles.get().pk, 2)
        self.s.precintar(self.admin, bulto.pk, f"P-{bulto.pk}")
        self.s.despachar(self.admin, orden.remito.pk)
        self.s.recibir(self.encargado, orden.remito.pk)
        self.s.controlar(self.encargado, bulto.pk, True, True)
        self.s.cerrar_remito(self.encargado, orden.remito.pk)
        self.s.vender(self.vendedor, "DEBITO", [(self.p2.pk, 2)], uuid4())
        venta = self.vender(3)
        futuro = timezone.now() + timedelta(days=1)
        self.s.ahora = lambda: futuro
        self.s.devolver_venta(self.vendedor, venta.pk, "Apto", [(venta.detalles.get().pk, 2, True)], uuid4())
        filas = self.reportar("margen")["filas"]
        self.assertEqual([fila[0] for fila in filas], [str(self.p2), str(self.p)])
        dia = timezone.localtime(futuro).date()
        resultado = self.reportar("margen", desde=dia, hasta=dia)
        self.assertEqual(resultado["filas"], [
            [str(self.p), 0, 2, -2, "−$ 200,00", "−$ 100,00", "−$ 100,00", "$ 0,00"]])
        self.assertEqual(resultado["totales"], {"margen": -10000})

    def test_rechazos_resultado_completo_con_fechas_motivo_y_merma(self):
        _, remito, bs = self.enviar((3, 2))
        self.s.controlar(self.encargado, bs[0].pk, True, False)
        self.s.controlar(self.encargado, bs[1].pk, False, True, "ENVIO_ERRONEO")
        self.s.cerrar_remito(self.encargado, remito.pk)
        self.s.devolver_bulto(self.encargado, bs[0].pk)
        self.s.resolver_bulto(self.admin, bs[0].pk, False, "Roto")
        evento = bs[0].eventos.get(estado="RECHAZADO")
        merma = m.Merma.objects.get()
        esperado = {
            "titulo": "Rechazos y mermas logísticas",
            "columnas": ["Registro", "Fecha", "Bulto", "Destino", "Producto", "Motivo", "Cantidad"],
            "filas": [["Merma confirmada", merma.fecha, bs[0].pk, str(self.local), str(self.p), "Precinto violado", 3],
                      ["Rechazo", evento.fecha, bs[0].pk, str(self.local), str(self.p), "Precinto violado", 3]],
            "nota": "Un rechazo no equivale a una pérdida. Las mermas aparecen solo cuando el CD confirma la baja. No incluye devoluciones comerciales.",
            "totales": {"bultos_rechazados": 1, "unidades_rechazadas": 3, "unidades_merma": 3},
        }
        dia = timezone.localtime(evento.fecha).date()
        self.assertEqual(self.reportar("rechazos", self.encargado, motivo="PRECINTO_VIOLADO",
            categoria_id=self.cat.pk, desde=dia, hasta=dia), esperado)
        self.assertEqual(self.reportar("rechazos", motivo="ENVIO_ERRONEO")["totales"],
            {"bultos_rechazados": 1, "unidades_rechazadas": 2, "unidades_merma": 0})
        self.assertEqual(self.reportar("rechazos", local_id=self.otro.pk)["filas"], [])
        self.assertEqual(self.reportar("rechazos", hasta=dia-timedelta(days=1))["filas"], [])

    def test_http_precinto_violado_cierre_y_reintento(self):
        _, remito, bs = self.enviar()
        self.client.force_login(self.encargado)
        url = reverse("accion_objeto", args=["controlar", bs[0].pk])
        datos = {"aceptar": "on", "observacion": "Precinto roto", "operacion": str(uuid4())}
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        bs[0].refresh_from_db()
        self.assertEqual((bs[0].estado, bs[0].motivo_rechazo), ("RECHAZADO", "PRECINTO_VIOLADO"))
        antes = self.fotografia()
        self.assertContains(self.client.post(url, datos), "Acción inválida")
        self.assertEqual(self.fotografia(), antes)
        url_cierre = reverse("accion_objeto", args=["cerrar", remito.pk])
        self.assertEqual(self.client.post(url_cierre, {"operacion": str(uuid4())}).status_code, 302)
        self.assertEqual(remito.estado, "RECHAZADO")
        antes = self.fotografia()
        self.assertContains(self.client.post(url_cierre, {"operacion": str(uuid4())}), "Acción inválida")
        self.assertEqual(self.fotografia(), antes)
        self.assertEqual(self.stock(self.local).disponible, 0)

    def test_http_los_cuatro_reportes_muestran_resultados(self):
        self.habilitar()
        self.vender(1)
        self.client.force_login(self.encargado)
        for tipo in ("ingresos", "margen", "existencias", "rechazos"):
            with self.subTest(tipo=tipo):
                respuesta = self.client.get(reverse("reporte", args=[tipo]))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context["resultado"], self.reportar(tipo, self.encargado))
