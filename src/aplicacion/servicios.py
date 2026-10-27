"""Casos de uso con adaptadores inyectados desde config.composicion.

No importa Django. El adaptador de datos implementa el acceso a agregados;
las reglas de cantidades, dinero, inventario y estados viven en dominio.
"""
from functools import wraps
from uuid import uuid4
from src.dominio.ventas import DetalleVenta as RenglonVenta, Venta as VentaDominio
from src.dominio.reglas import (
    ErrorNegocio, exigir, consolidar, centavos, validar_transicion,
    validar_devolucion, FINALES_BULTO,
)


def atomica(funcion):
    @wraps(funcion)
    def ejecutar(self, *args, **kwargs):
        with self.unidad():
            return funcion(self, *args, **kwargs)
    return ejecutar


class Operaciones:
    def __init__(self, datos, inventario, unidad, reloj, plazo=30):
        self.db, self.inv, self.unidad = datos, inventario, unidad
        self.ahora, self.plazo = reloj, plazo

    def crear(self, entidad, **datos):
        if entidad in {"Compra", "OrdenReposicion", "Remito", "Comprobante", "Venta", "Devolucion", "MovimientoCaja", "Merma"}:
            datos.setdefault("fecha", self.ahora())
        return self.db.crear(entidad, **datos)

    def acceso(self, usuario, roles, ubicacion=None):
        exigir(usuario.is_authenticated and usuario.is_active and usuario.ubicacion.activo,
            "El usuario o su ubicación no están habilitados.")
        exigir(usuario.rol in roles, "No tiene permiso para realizar esta operación.")
        if ubicacion is not None:
            exigir(usuario.rol == "ADMIN_CD" or usuario.ubicacion_id == ubicacion,
                "No puede operar sobre otro local.")
        exigir((usuario.rol == "ADMIN_CD") == (usuario.ubicacion.tipo == "CD"),
            "El rol no corresponde a la ubicación del usuario.")

    def cambiar(self, objeto, estado, usuario):
        validar_transicion(objeto.ambito, objeto.estado, estado)
        campo = {"COMPRA": "compra", "ORDEN": "orden", "REMITO": "remito", "BULTO": "bulto"}[objeto.ambito]
        self.crear("EventoEstado", ambito=objeto.ambito, estado=estado, usuario=usuario,
            fecha=self.ahora(), **{campo: objeto})

    def producto(self, id):
        producto = self.db.producto_dominio(id)
        producto.validar_vigencia()
        return producto

    def cd(self):
        cd = self.db.listar("Ubicacion", tipo="CD", activo=True).first()
        exigir(cd is not None, "Primero debe registrar el centro de distribución.")
        return cd

    def caja(self, local):
        exigir(local.tipo == "LOCAL" and local.activo, "Debe seleccionar un local activo.")
        caja = self.db.listar("Caja", local=local).first()
        exigir(caja is not None, "El local no tiene caja.")
        return caja

    @atomica
    def emitir_compra(self, usuario, proveedor_id, lineas):
        self.acceso(usuario, {"ADMIN_CD"})
        proveedor = self.db.obtener("Proveedor", proveedor_id)
        exigir(proveedor.activo, "El proveedor está inactivo.")
        exigir(bool(lineas), "La compra debe contener productos.")
        preparados = []
        ids = set()
        for producto_id, cantidad, costo in lineas:
            producto = self.producto(producto_id)
            exigir(producto_id not in ids, "No repetir productos en la compra.")
            ids.add(producto_id)
            consolidar([(producto_id, cantidad)])
            producto.validar_proveedor(proveedor.pk)
            preparados.append((producto, cantidad, centavos(costo)))
        compra = self.crear("Compra", proveedor=proveedor, centro=self.cd(), usuario=usuario)
        for producto, cantidad, costo in preparados:
            self.crear("DetalleCompra", compra=compra, producto_id=producto.id, cantidad=cantidad, costo_centavos=costo)
        self.cambiar(compra, "EMITIDA", usuario)
        return compra

    @atomica
    def avanzar_compra(self, usuario, compra_id, estado):
        self.acceso(usuario, {"ADMIN_CD"})
        exigir(estado in {"RECIBIDA", "VERIFICADA", "CANCELADA"}, "Acción de compra inválida.")
        compra = self.db.obtener("Compra", compra_id)
        self.cambiar(compra, estado, usuario)
        if estado == "VERIFICADA":
            for d in compra.detalles.all():
                item = self.inv.obtener(d.producto_id, compra.centro_id)
                item.existencia += d.cantidad
                self.inv.guardar(d.producto_id, compra.centro_id, item)
            compra.fecha_verificacion = self.ahora()
            self.db.guardar(compra)
        return compra

    @atomica
    def solicitar(self, usuario, destino_id, lineas):
        self.acceso(usuario, {"ADMIN_CD", "ADMIN_MINORISTA"}, destino_id)
        destino = self.db.obtener("Ubicacion", destino_id)
        exigir(destino.tipo == "LOCAL" and destino.activo, "El destino debe ser un local activo.")
        cantidades = consolidar(lineas)
        for id in cantidades:
            self.producto(id)
        orden = self.crear("OrdenReposicion", origen=self.cd(), destino=destino, usuario=usuario)
        for id, cantidad in cantidades.items():
            self.crear("DetalleOrden", orden=orden, producto_id=id, cantidad=cantidad)
        self.cambiar(orden, "PENDIENTE", usuario)
        return orden

    @atomica
    def preparar(self, usuario, detalle_id, cantidad):
        self.acceso(usuario, {"ADMIN_CD"})
        detalle = self.db.obtener("DetalleOrden", detalle_id)
        orden = detalle.orden
        exigir(orden.estado in {"PENDIENTE", "EN_PREPARACION"}, "La orden ya no admite preparación.")
        consolidar([(detalle.producto_id, cantidad)])
        armado = sum(b.cantidad for b in detalle.bultos.all() if b.estado != "CANCELADO")
        exigir(armado + cantidad <= detalle.cantidad, "La cantidad supera lo solicitado en la orden.")
        item = self.inv.obtener(detalle.producto_id, orden.origen_id)
        item.reservar(cantidad)
        self.inv.guardar(detalle.producto_id, orden.origen_id, item)
        bulto = self.crear("Bulto", detalle_orden=detalle, cantidad=cantidad)
        if orden.estado == "PENDIENTE":
            self.cambiar(orden, "EN_PREPARACION", usuario)
        self.cambiar(bulto, "PREPARADO", usuario)
        return bulto

    @atomica
    def precintar(self, usuario, bulto_id, precinto):
        self.acceso(usuario, {"ADMIN_CD"})
        bulto = self.db.obtener("Bulto", bulto_id)
        exigir(bulto.estado == "PREPARADO", "Solo puede precintar un bulto preparado.")
        precinto = precinto.strip()
        exigir(bool(precinto) and len(precinto) <= 80, "Indicar un precinto de hasta 80 caracteres.")
        exigir(not self.db.listar("Bulto", precinto=precinto).exists(), "El precinto ya está utilizado.")
        orden = bulto.detalle_orden.orden
        remito = self.db.listar("Remito", orden=orden).first()
        if remito is None:
            remito = self.crear("Remito", orden=orden)
            self.cambiar(remito, "EMITIDO", usuario)
        bulto.remito, bulto.precinto = remito, precinto
        self.db.guardar(bulto)
        self.cambiar(bulto, "PRECINTADO", usuario)
        return bulto

    @atomica
    def despachar(self, usuario, remito_id):
        self.acceso(usuario, {"ADMIN_CD"})
        remito = self.db.obtener("Remito", remito_id)
        exigir(remito.estado == "EMITIDO", "El remito no está disponible para despacho.")
        orden = remito.orden
        for detalle in orden.detalles.all():
            bultos = list(detalle.bultos.all())
            exigir(sum(b.cantidad for b in bultos) == detalle.cantidad, "Hay cantidades pendientes de preparar.")
            exigir(all(b.estado == "PRECINTADO" and b.remito_id == remito.pk for b in bultos),
                "Todos los bultos deben estar precintados y asignados al remito.")
        self.cambiar(remito, "EN_TRANSITO", usuario)
        self.cambiar(orden, "DESPACHADA", usuario)
        remito.fecha_despacho = self.ahora()
        self.db.guardar(remito)
        for bulto in remito.bultos.all():
            self.cambiar(bulto, "EN_TRANSITO", usuario)
        return remito

    @atomica
    def recibir(self, usuario, remito_id):
        remito = self.db.obtener("Remito", remito_id)
        self.acceso(usuario, {"ADMIN_MINORISTA"}, remito.orden.destino_id)
        self.cambiar(remito, "RECIBIDO", usuario)
        for bulto in remito.bultos.all():
            self.cambiar(bulto, "RECIBIDO", usuario)
            bulto.fecha_recepcion = self.ahora()
            self.db.guardar(bulto)
        return remito

    @atomica
    def controlar(self, usuario, bulto_id, aceptar, precinto_integro, motivo="", observacion=""):
        bulto = self.db.obtener("Bulto", bulto_id)
        orden = bulto.detalle_orden.orden
        self.acceso(usuario, {"ADMIN_MINORISTA"}, orden.destino_id)
        exigir(bulto.remito is not None and bulto.remito.estado == "RECIBIDO", "El remito no está en recepción.")
        if not precinto_integro:
            aceptar, motivo = False, "PRECINTO_VIOLADO"
        if not aceptar:
            exigir(motivo in {"PRECINTO_VIOLADO", "ENVIO_ERRONEO", "OTRO"}, "Debe indicar un motivo de rechazo.")
            exigir(motivo != "OTRO" or observacion.strip(), "Describa el motivo del rechazo.")
        self.cambiar(bulto, "VERIFICADO" if aceptar else "RECHAZADO", usuario)
        bulto.motivo_rechazo = "" if aceptar else motivo
        bulto.observacion = observacion.strip()
        self.db.guardar(bulto)
        return bulto

    @atomica
    def cerrar_remito(self, usuario, remito_id):
        remito = self.db.obtener("Remito", remito_id)
        orden = remito.orden
        self.acceso(usuario, {"ADMIN_MINORISTA"}, orden.destino_id)
        exigir(remito.estado == "RECIBIDO", "El remito no admite cierre.")
        bultos = list(remito.bultos.all())
        exigir(bool(bultos) and all(b.estado in {"VERIFICADO", "RECHAZADO"} for b in bultos),
            "Debe controlar todos los bultos antes de cerrar el remito.")
        aceptados = [b for b in bultos if b.estado == "VERIFICADO"]
        self.cambiar(remito, "VERIFICADO" if aceptados else "RECHAZADO", usuario)
        remito.fecha_cierre = self.ahora()
        self.db.guardar(remito)
        for bulto in aceptados:
            id = bulto.producto.pk
            cd = self.inv.obtener(id, orden.origen_id)
            cd.liberar(bulto.cantidad, descontar=True)
            local = self.inv.obtener(id, orden.destino_id)
            local.existencia += bulto.cantidad
            self.inv.guardar(id, orden.origen_id, cd)
            self.inv.guardar(id, orden.destino_id, local)
        self.finalizar_si_resuelta(orden, usuario)
        return remito

    def finalizar_si_resuelta(self, orden, usuario):
        remito = self.db.listar("Remito", orden=orden).first()
        if remito and remito.fecha_cierre and orden.estado == "DESPACHADA":
            if all(b.estado in FINALES_BULTO for b in remito.bultos.all()):
                self.cambiar(orden, "FINALIZADA", usuario)

    @atomica
    def devolver_bulto(self, usuario, bulto_id):
        bulto = self.db.obtener("Bulto", bulto_id)
        self.acceso(usuario, {"ADMIN_CD", "ADMIN_MINORISTA"}, bulto.detalle_orden.orden.destino_id)
        exigir(bulto.remito.fecha_cierre is not None, "Primero debe cerrar el remito.")
        self.cambiar(bulto, "EN_DEVOLUCION_AL_CD", usuario)
        return bulto

    @atomica
    def resolver_bulto(self, usuario, bulto_id, recuperable, observacion):
        self.acceso(usuario, {"ADMIN_CD"})
        bulto = self.db.obtener("Bulto", bulto_id)
        exigir(bool(observacion.strip()), "Registrar el resultado de la revisión del contenido en el CD.")
        self.cambiar(bulto, "REINGRESADO" if recuperable else "DADO_DE_BAJA", usuario)
        orden = bulto.detalle_orden.orden
        item = self.inv.obtener(bulto.producto.pk, orden.origen_id)
        item.liberar(bulto.cantidad, descontar=not recuperable)
        self.inv.guardar(bulto.producto.pk, orden.origen_id, item)
        bulto.observacion += "\nRevisión CD: " + observacion.strip()
        self.db.guardar(bulto)
        if not recuperable:
            self.crear("Merma", producto=bulto.producto, ubicacion=orden.destino, cantidad=bulto.cantidad,
                origen="LOGISTICA_PRECINTO" if bulto.motivo_rechazo == "PRECINTO_VIOLADO" else "LOGISTICA_OTRO", bulto=bulto)
        self.finalizar_si_resuelta(orden, usuario)
        return bulto

    @atomica
    def cancelar_orden(self, usuario, orden_id):
        orden = self.db.obtener("OrdenReposicion", orden_id)
        self.acceso(usuario, {"ADMIN_CD", "ADMIN_MINORISTA"}, orden.destino_id)
        self.cambiar(orden, "CANCELADA", usuario)
        for detalle in orden.detalles.all():
            for bulto in detalle.bultos.all():
                self.cambiar(bulto, "CANCELADO", usuario)
                item = self.inv.obtener(detalle.producto_id, orden.origen_id)
                item.liberar(bulto.cantidad)
                self.inv.guardar(detalle.producto_id, orden.origen_id, item)
        remito = self.db.listar("Remito", orden=orden).first()
        if remito:
            self.cambiar(remito, "CANCELADO", usuario)
        return orden

    def ultimo_costo(self, producto_id):
        detalle = self.db.listar("DetalleCompra", producto_id=producto_id,
            compra__fecha_verificacion__isnull=False).order_by("-compra__fecha_verificacion", "-pk").first()
        exigir(detalle is not None, "No hay una compra verificada para determinar el costo del producto.")
        return detalle.costo_centavos

    @atomica
    def vender(self, usuario, medio, lineas, operacion):
        self.acceso(usuario, {"VENDEDOR"})
        previa = self.db.listar("Venta", operacion=operacion).first()
        if previa:
            exigir(previa.usuario_id == usuario.pk, "Identificador de operación inválido.")
            return previa
        exigir(medio in {"EFECTIVO", "DEBITO", "CREDITO", "TRANSFERENCIA"}, "Medio de pago inválido.")
        cantidades = consolidar(lineas)
        caja = self.caja(usuario.ubicacion)
        preparados = []
        for id, cantidad in cantidades.items():
            producto = self.producto(id)
            item = self.inv.obtener(id, usuario.ubicacion_id)
            item.vender(cantidad)
            preparados.append((producto, cantidad, self.ultimo_costo(id)))
            self.inv.guardar(id, usuario.ubicacion_id, item)
        venta_dominio = VentaDominio(tuple(RenglonVenta(p.id, c, p.precio_centavos, costo) for p, c, costo in preparados), medio)
        total = venta_dominio.total_centavos
        comprobante = self.crear("Comprobante", tipo="TICKET", total_centavos=total)
        venta = self.crear("Venta", caja=caja, usuario=usuario, medio=medio, comprobante=comprobante, operacion=operacion)
        for producto, cantidad, costo in preparados:
            self.crear("DetalleVenta", venta=venta, producto_id=producto.id, cantidad=cantidad,
                precio_centavos=producto.precio_centavos, costo_centavos=costo)
        self.crear("MovimientoCaja", caja=caja, usuario=usuario, tipo="VENTA", medio=medio,
            monto_centavos=total, venta=venta, operacion=uuid4())
        return venta

    @atomica
    def devolver_venta(self, usuario, venta_id, motivo, lineas, operacion):
        venta = self.db.obtener("Venta", venta_id)
        self.acceso(usuario, {"VENDEDOR"}, venta.caja.local_id)
        previa = self.db.listar("Devolucion", operacion=operacion).first()
        if previa:
            exigir(previa.usuario_id == usuario.pk and previa.venta_id == venta.pk, "Identificador de operación inválido.")
            return previa
        exigir(bool(motivo.strip()), "El motivo de devolución es obligatorio.")
        exigir(bool(lineas), "Debe indicar al menos un renglón.")
        preparados, ids = [], set()
        for detalle_id, cantidad, apto in lineas:
            exigir(detalle_id not in ids, "No repetir renglones en la devolución.")
            ids.add(detalle_id)
            detalle = self.db.obtener("DetalleVenta", detalle_id)
            exigir(detalle.venta_id == venta.pk, "El renglón no pertenece a la venta.")
            consolidar([(detalle_id, cantidad)])
            devuelta = sum(d.cantidad for d in detalle.devoluciones.all())
            validar_devolucion(venta.fecha, self.ahora(), self.plazo, detalle.cantidad, devuelta, cantidad)
            preparados.append((detalle, cantidad, bool(apto)))
        total = sum(d.precio_centavos * c for d, c, _ in preparados)
        if venta.medio == "EFECTIVO":
            exigir(venta.caja.saldo >= total, "El efectivo de caja no alcanza para el reintegro.")
        comprobante = self.crear("Comprobante", tipo="NOTA_CREDITO", total_centavos=total)
        devolucion = self.crear("Devolucion", venta=venta, usuario=usuario, motivo=motivo.strip(),
            comprobante=comprobante, operacion=operacion)
        for detalle, cantidad, apto in preparados:
            d = self.crear("DetalleDevolucion", devolucion=devolucion, detalle_venta=detalle, cantidad=cantidad, apto=apto)
            if apto:
                item = self.inv.obtener(detalle.producto_id, venta.caja.local_id)
                item.existencia += cantidad
                self.inv.guardar(detalle.producto_id, venta.caja.local_id, item)
            else:
                self.crear("Merma", producto=detalle.producto, ubicacion=venta.caja.local,
                    cantidad=cantidad, origen="DEVOLUCION_NO_APTA", detalle_devolucion=d)
        self.crear("MovimientoCaja", caja=venta.caja, usuario=usuario, tipo="DEVOLUCION",
            medio=venta.medio, monto_centavos=-total, devolucion=devolucion, operacion=uuid4())
        return devolucion

    @atomica
    def mover_caja(self, usuario, local_id, tipo, monto, motivo, operacion):
        self.acceso(usuario, {"ADMIN_CD", "ADMIN_MINORISTA"}, local_id)
        previa = self.db.listar("MovimientoCaja", operacion=operacion).first()
        if previa:
            exigir(previa.usuario_id == usuario.pk, "Identificador de operación inválido.")
            return previa
        exigir(tipo in {"INGRESO", "RETIRO"}, "Tipo de movimiento inválido.")
        importe = centavos(monto)
        exigir(importe > 0 and bool(motivo.strip()), "Indicar importe positivo y motivo.")
        caja = self.caja(self.db.obtener("Ubicacion", local_id))
        exigir(tipo != "RETIRO" or caja.saldo >= importe, "El efectivo de caja es insuficiente.")
        return self.crear("MovimientoCaja", caja=caja, usuario=usuario, tipo=tipo, medio="EFECTIVO",
            monto_centavos=importe if tipo == "INGRESO" else -importe, motivo=motivo.strip(), operacion=operacion)
