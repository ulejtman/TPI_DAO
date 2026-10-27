from collections import defaultdict
from src.dominio.reglas import exigir


def dinero(centavos):
    signo = "−" if centavos < 0 else ""
    numero = abs(int(centavos))
    return f"{signo}$ {numero // 100:,}".replace(",", ".") + f",{numero % 100:02d}"


class Reportes:
    def __init__(self, datos, operaciones):
        self.db, self.ops = datos, operaciones

    def generar(self, usuario, tipo, desde=None, hasta=None, local_id=None, categoria_id=None, medio=None, motivo=None):
        self.ops.acceso(usuario, {"ADMIN_CD", "ADMIN_MINORISTA"})
        exigir(tipo in {"ingresos", "margen", "existencias", "rechazos"}, "Reporte inexistente.")
        exigir(not (desde and hasta) or desde <= hasta, "El inicio debe ser anterior al fin.")
        if usuario.rol != "ADMIN_CD":
            exigir(local_id is None or local_id == usuario.ubicacion_id, "No puede consultar otro local.")
            local_id = usuario.ubicacion_id

        def filtrar(qs, fecha="fecha", local="caja__local_id", categoria=None):
            datos = {}
            if desde:
                datos[fecha + "__date__gte"] = desde
            if hasta:
                datos[fecha + "__date__lte"] = hasta
            if local_id:
                datos[local] = local_id
            if categoria_id and categoria:
                datos[categoria] = categoria_id
            return qs.filter(**datos)

        if tipo == "ingresos":
            grupos = defaultdict(lambda: [0, 0])
            ventas = filtrar(self.db.listar("Venta"))
            devoluciones = filtrar(self.db.listar("Devolucion"), local="venta__caja__local_id")
            if medio:
                ventas, devoluciones = ventas.filter(medio=medio), devoluciones.filter(venta__medio=medio)
            for venta in ventas.select_related("caja__local", "comprobante"):
                grupos[(str(venta.caja.local), venta.get_medio_display())][0] += venta.comprobante.total_centavos
            for d in devoluciones.select_related("venta__caja__local", "comprobante"):
                grupos[(str(d.venta.caja.local), d.venta.get_medio_display())][1] += d.comprobante.total_centavos
            return {"titulo": "Ventas e ingresos", "columnas": ["Local", "Medio", "Ventas brutas", "Reintegros", "Neto"],
                "filas": [[*k, dinero(v[0]), dinero(v[1]), dinero(v[0]-v[1])] for k,v in sorted(grupos.items())],
                "nota": "Cada operación se imputa a su fecha. Los ingresos y retiros manuales de caja no son ventas.",
                "totales": {"bruto": sum(v[0] for v in grupos.values()), "reintegros": sum(v[1] for v in grupos.values()),
                    "neto": sum(v[0]-v[1] for v in grupos.values())}}

        if tipo == "margen":
            grupos = {}
            ventas = filtrar(self.db.listar("DetalleVenta"), fecha="venta__fecha", local="venta__caja__local_id",
                categoria="producto__categoria_id")
            devoluciones = filtrar(self.db.listar("DetalleDevolucion"), fecha="devolucion__fecha",
                local="devolucion__venta__caja__local_id", categoria="detalle_venta__producto__categoria_id")

            def grupo(d):
                return grupos.setdefault(d.producto_id, {"producto": str(d.producto), "vendidas": 0,
                    "devueltas": 0, "ingreso": 0, "costo": 0, "merma": 0})
            for d in ventas.select_related("producto"):
                g = grupo(d)
                g["vendidas"] += d.cantidad
                g["ingreso"] += d.cantidad*d.precio_centavos
                g["costo"] += d.cantidad*d.costo_centavos
            for r in devoluciones.select_related("detalle_venta__producto"):
                d = r.detalle_venta
                g = grupo(d)
                g["devueltas"] += r.cantidad
                g["ingreso"] -= r.cantidad*d.precio_centavos
                # Solo los productos aptos recuperan costo como existencia vendible.
                if r.apto:
                    g["costo"] -= r.cantidad*d.costo_centavos
                else:
                    g["merma"] += r.cantidad*d.costo_centavos
            ordenados = sorted(grupos.values(), key=lambda g: (-(g["vendidas"]-g["devueltas"]), g["producto"]))
            return {"titulo": "Productos y margen estimado", "columnas": ["Producto", "Vendidas", "Devueltas", "Unidades netas", "Ingreso neto", "Costo consumido", "Margen", "Merma devolución"],
                "filas": [[g["producto"], g["vendidas"], g["devueltas"], g["vendidas"]-g["devueltas"],
                    dinero(g["ingreso"]), dinero(g["costo"]), dinero(g["ingreso"]-g["costo"]), dinero(g["merma"])] for g in ordenados],
                "nota": "Costo histórico congelado al vender. Las devoluciones no aptas no recuperan costo. No incluye gastos operativos ni mermas logísticas.",
                "totales": {"margen": sum(g["ingreso"]-g["costo"] for g in ordenados)}}

        if tipo == "existencias":
            qs = self.db.listar("ItemInventario")
            if local_id:
                qs = qs.filter(ubicacion_id=local_id)
            if categoria_id:
                qs = qs.filter(producto__categoria_id=categoria_id)
            pendientes = defaultdict(int)
            for b in self.db.listar("Bulto", remito__isnull=False).select_related("remito__orden", "detalle_orden"):
                if b.estado in {"EN_TRANSITO", "RECIBIDO", "RECHAZADO", "EN_DEVOLUCION_AL_CD"} or (b.estado == "VERIFICADO" and not b.remito.fecha_cierre):
                    pendientes[(b.detalle_orden.producto_id, b.remito.orden.destino_id)] += b.cantidad
            filas = []
            for i in qs.select_related("producto", "ubicacion").order_by("ubicacion__nombre", "producto__nombre"):
                filas.append([str(i.ubicacion), str(i.producto), i.existencia, i.reservado, i.disponible,
                    pendientes[(i.producto_id, i.ubicacion_id)], i.minimo, "En mínimo" if i.disponible <= i.minimo else "Normal"])
            return {"titulo": "Existencias y stock mínimo", "columnas": ["Ubicación", "Producto", "Existencia contable", "Reservado", "Disponible", "Pendiente de ingreso", "Mínimo", "Situación"],
                "filas": filas, "nota": "Foto actual: no aplica el período. El tránsito sigue contabilizado y reservado en el CD hasta el cierre del remito.", "totales": {}}

        eventos = filtrar(self.db.listar("EventoEstado", ambito="BULTO", estado="RECHAZADO"),
            local="bulto__detalle_orden__orden__destino_id", categoria="bulto__detalle_orden__producto__categoria_id")
        mermas = filtrar(self.db.listar("Merma", bulto__isnull=False), local="ubicacion_id", categoria="producto__categoria_id")
        if motivo:
            eventos, mermas = eventos.filter(bulto__motivo_rechazo=motivo), mermas.filter(bulto__motivo_rechazo=motivo)
        filas = []
        unidades = perdidas = 0
        for e in eventos.select_related("bulto__detalle_orden__orden__destino", "bulto__detalle_orden__producto"):
            b = e.bulto
            unidades += b.cantidad
            filas.append(["Rechazo", e.fecha, b.pk, str(b.detalle_orden.orden.destino), str(b.producto), b.get_motivo_rechazo_display(), b.cantidad])
        for m in mermas.select_related("bulto", "producto", "ubicacion"):
            perdidas += m.cantidad
            filas.append(["Merma confirmada", m.fecha, m.bulto_id, str(m.ubicacion), str(m.producto), m.bulto.get_motivo_rechazo_display(), m.cantidad])
        return {"titulo": "Rechazos y mermas logísticas", "columnas": ["Registro", "Fecha", "Bulto", "Destino", "Producto", "Motivo", "Cantidad"],
            "filas": sorted(filas, key=lambda r: r[1], reverse=True),
            "nota": "Un rechazo no equivale a una pérdida. Las mermas aparecen solo cuando el CD confirma la baja. No incluye devoluciones comerciales.",
            "totales": {"bultos_rechazados": eventos.count(), "unidades_rechazadas": unidades, "unidades_merma": perdidas}}
