from uuid import uuid4
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.forms import formset_factory, modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from config.composicion import operaciones
from src.aplicacion.reportes import Reportes, dinero
from src.dominio.reglas import ErrorNegocio
from src.infraestructura.repositorios import DatosORM
from src.infraestructura.persistencia import models as m
from src.presentacion.formularios import (
    campos_accion, formulario_lineas, ProductoForm, ProveedorForm, UbicacionForm,
    UsuarioForm, MinimoForm, FiltroReporte,
)

ADM = {"ADMIN_CD", "ADMIN_MINORISTA"}
TODOS = ADM | {"VENDEDOR"}
SECCIONES = {
    "inventario": (m.ItemInventario, "Inventario", TODOS, "ubicacion_id"),
    "compras": (m.Compra, "Compras", {"ADMIN_CD"}, "centro_id"),
    "ordenes": (m.OrdenReposicion, "Reposiciones", ADM, "destino_id"),
    "remitos": (m.Remito, "Remitos", ADM, "orden__destino_id"),
    "bultos": (m.Bulto, "Bultos", ADM, "detalle_orden__orden__destino_id"),
    "ventas": (m.Venta, "Ventas", TODOS, "caja__local_id"),
    "devoluciones": (m.Devolucion, "Devoluciones", TODOS, "venta__caja__local_id"),
    "cajas": (m.Caja, "Caja y movimientos", TODOS, "local_id"),
    "productos": (m.Producto, "Productos", {"ADMIN_CD"}, None),
    "proveedores": (m.Proveedor, "Proveedores", {"ADMIN_CD"}, None),
    "categorias": (m.Categoria, "Categorías", {"ADMIN_CD"}, None),
    "ubicaciones": (m.Ubicacion, "Ubicaciones", {"ADMIN_CD"}, None),
    "usuarios": (m.Usuario, "Usuarios", {"ADMIN_CD"}, None),
}
MAESTROS = {"productos": ProductoForm, "proveedores": ProveedorForm,
    "ubicaciones": UbicacionForm, "usuarios": UsuarioForm,
    "categorias": modelform_factory(m.Categoria, fields=["nombre"]), "inventario": MinimoForm}
ACCIONES = {
    "compra": ("Emitir compra", "compras", {"ADMIN_CD"}),
    "recibir_compra": ("Registrar llegada", "compras", {"ADMIN_CD"}),
    "verificar_compra": ("Verificar compra", "compras", {"ADMIN_CD"}),
    "cancelar_compra": ("Cancelar compra", "compras", {"ADMIN_CD"}),
    "orden": ("Solicitar reposición", "ordenes", ADM),
    "preparar": ("Preparar bulto", "ordenes", {"ADMIN_CD"}),
    "cancelar_orden": ("Cancelar orden", "ordenes", ADM),
    "precintar": ("Precintar bulto", "bultos", {"ADMIN_CD"}),
    "despachar": ("Despachar remito", "remitos", {"ADMIN_CD"}),
    "recibir": ("Registrar recepción", "remitos", {"ADMIN_MINORISTA"}),
    "controlar": ("Controlar bulto", "bultos", {"ADMIN_MINORISTA"}),
    "cerrar": ("Cerrar verificación del remito", "remitos", {"ADMIN_MINORISTA"}),
    "retornar": ("Enviar de regreso al CD", "bultos", ADM),
    "resolver": ("Revisar devolución en CD", "bultos", {"ADMIN_CD"}),
    "venta": ("Registrar venta", "ventas", {"VENDEDOR"}),
    "devolucion": ("Registrar devolución", "ventas", {"VENDEDOR"}),
    "movimiento": ("Ingresar o retirar efectivo", "cajas", ADM),
}


def permiso(usuario, roles):
    if not usuario.is_active or not usuario.ubicacion.activo or usuario.rol not in roles:
        raise PermissionDenied


def consulta(usuario, tipo):
    if tipo not in SECCIONES:
        raise PermissionDenied
    modelo, _, roles, campo = SECCIONES[tipo]
    permiso(usuario, roles)
    qs = modelo.objects.all()
    if usuario.rol != "ADMIN_CD" and campo:
        qs = qs.filter(**{campo: usuario.ubicacion_id})
    return qs


def url_detalle(tipo, id):
    return reverse("detalle", args=[tipo, id])


def tabla(tipo, qs):
    filas = []
    columnas = {
        "inventario": ["Producto", "Ubicación", "Existencia", "Reservado", "Disponible", "Mínimo"],
        "compras": ["Compra", "Proveedor", "Fecha", "Estado"],
        "ordenes": ["Orden", "Destino", "Fecha", "Estado"],
        "remitos": ["Remito", "Orden", "Destino", "Estado"],
        "bultos": ["Bulto", "Producto", "Cantidad", "Precinto", "Estado"],
        "ventas": ["Venta", "Local", "Fecha", "Medio", "Total"],
        "devoluciones": ["Devolución", "Venta", "Fecha", "Reintegro"],
        "cajas": ["Caja", "Local", "Efectivo disponible"],
        "productos": ["SKU", "Producto", "Categoría", "Proveedor", "Precio", "Activo"],
        "proveedores": ["Proveedor", "CUIT", "Dirección", "Activo"],
        "categorias": ["Categoría"], "ubicaciones": ["Ubicación", "Tipo", "Dirección", "Activa"],
        "usuarios": ["Usuario", "Nombre", "Rol", "Ubicación", "Activo"],
    }[tipo]
    for o in qs:
        if tipo == "inventario": valores = [o.producto, o.ubicacion, o.existencia, o.reservado, o.disponible, o.minimo]
        elif tipo == "compras": valores = [f"#{o.pk}", o.proveedor, o.fecha, o.estado]
        elif tipo == "ordenes": valores = [f"#{o.pk}", o.destino, o.fecha, o.estado]
        elif tipo == "remitos": valores = [f"#{o.pk}", f"#{o.orden_id}", o.orden.destino, o.estado]
        elif tipo == "bultos": valores = [f"#{o.pk}", o.producto, o.cantidad, o.precinto or "Sin colocar", o.estado]
        elif tipo == "ventas": valores = [f"#{o.pk}", o.caja.local, o.fecha, o.get_medio_display(), dinero(o.comprobante.total_centavos)]
        elif tipo == "devoluciones": valores = [f"#{o.pk}", f"#{o.venta_id}", o.fecha, dinero(o.comprobante.total_centavos)]
        elif tipo == "cajas": valores = [f"#{o.pk}", o.local, dinero(o.saldo)]
        elif tipo == "productos": valores = [o.sku, o.nombre, o.categoria, o.proveedor, dinero(o.precio_centavos), "Sí" if o.activo else "No"]
        elif tipo == "proveedores": valores = [o.nombre, o.cuit, o.direccion, "Sí" if o.activo else "No"]
        elif tipo == "categorias": valores = [o.nombre]
        elif tipo == "ubicaciones": valores = [o.nombre, o.get_tipo_display(), o.direccion, "Sí" if o.activo else "No"]
        else: valores = [o.username, o.get_full_name(), o.get_rol_display(), o.ubicacion, "Sí" if o.is_active else "No"]
        enlace = reverse("maestro_editar", args=[tipo, o.pk]) if tipo in MAESTROS and tipo != "inventario" else url_detalle(tipo, o.pk)
        if tipo == "inventario":
            enlace = reverse("maestro_editar", args=[tipo, o.pk]) if o and tipo in MAESTROS else ""
        filas.append({"celdas": valores, "url": enlace})
    return columnas, filas


@login_required
def inicio(request):
    permiso(request.user, TODOS)
    user = request.user
    inv = consulta(user, "inventario")
    ventas = consulta(user, "ventas")
    if user.rol == "VENDEDOR":
        ventas = ventas.filter(usuario=user)
    recientes = ventas.select_related("caja__local", "comprobante").order_by("-pk")[:6]
    columnas, filas = tabla("ventas", recientes)
    tareas = []
    if user.rol in ADM:
        for remito in consulta(user, "remitos").order_by("-pk")[:100]:
            if remito.estado not in {"VERIFICADO", "RECHAZADO", "CANCELADO"}:
                tareas.append({"titulo": f"Remito #{remito.pk}", "texto": f"{remito.orden.destino} · {remito.estado.replace('_', ' ').lower()}", "url": url_detalle("remitos", remito.pk)})
    cajas = consulta(user, "cajas")
    return render(request, "inicio.html", {"titulo": "Resumen operativo", "activo": "inicio",
        "stock": sum(i.disponible for i in inv), "minimos": inv.filter(existencia__lte=F("reservado")+F("minimo")).count(),
        "efectivo": dinero(sum(c.saldo for c in cajas)), "pendientes": len(tareas),
        "tareas": tareas[:5], "columnas": columnas, "filas": filas,
        "principal": "venta" if user.rol == "VENDEDOR" else "compra" if user.rol == "ADMIN_CD" else "orden"})


@login_required
def listado(request, tipo):
    qs = consulta(request.user, tipo).order_by("-pk")
    if request.user.rol == "VENDEDOR" and tipo in {"ventas", "devoluciones"}:
        qs = qs.filter(usuario=request.user)
    buscar = request.GET.get("q", "").strip()
    if buscar:
        if tipo in {"productos", "proveedores", "categorias", "ubicaciones"}:
            qs = qs.filter(nombre__icontains=buscar)
        elif tipo == "inventario":
            qs = qs.filter(producto__nombre__icontains=buscar)
        elif tipo == "usuarios":
            qs = qs.filter(username__icontains=buscar)
        elif buscar.isdigit():
            qs = qs.filter(pk=int(buscar))
        else:
            qs = qs.none()
    from django.core.paginator import Paginator
    pagina = Paginator(qs, 40).get_page(request.GET.get("pagina"))
    columnas, filas = tabla(tipo, pagina)
    if request.user.rol != "ADMIN_CD" and tipo == "inventario":
        for fila in filas:
            fila["url"] = ""
    nueva = {"compras": "compra", "ordenes": "orden", "ventas": "venta", "cajas": "movimiento"}.get(tipo)
    if nueva and request.user.rol not in ACCIONES[nueva][2]:
        nueva = None
    return render(request, "listado.html", {"titulo": SECCIONES[tipo][1], "tipo": tipo, "activo": tipo,
        "columnas": columnas, "filas": filas, "pagina": pagina, "buscar": buscar,
        "nueva": nueva, "nuevo_maestro": tipo in MAESTROS and request.user.rol == "ADMIN_CD" and tipo != "inventario"})


@login_required
def buscar_venta(request):
    permiso(request.user, {"VENDEDOR"})
    numero = request.GET.get("venta_id", "")
    if not numero.isdigit():
        messages.error(request, "Indique un número de venta válido.")
        return redirect("listado", tipo="devoluciones")
    venta = get_object_or_404(consulta(request.user, "ventas"), pk=int(numero))
    return redirect("accion_objeto", accion="devolucion", id=venta.pk)


def acciones_objeto(tipo, objeto, rol):
    estado = getattr(objeto, "estado", None)
    claves = []
    if tipo == "compras":
        claves = {"EMITIDA": ["recibir_compra", "cancelar_compra"], "RECIBIDA": ["verificar_compra"]}.get(estado, [])
    elif tipo == "ordenes" and estado in {"PENDIENTE", "EN_PREPARACION"}:
        claves = ["preparar", "cancelar_orden"]
    elif tipo == "remitos":
        claves = {"EMITIDO": ["despachar"], "EN_TRANSITO": ["recibir"], "RECIBIDO": ["cerrar"]}.get(estado, [])
    elif tipo == "bultos":
        claves = {"PREPARADO": ["precintar"], "RECIBIDO": ["controlar"], "RECHAZADO": ["retornar"], "EN_DEVOLUCION_AL_CD": ["resolver"]}.get(estado, [])
    elif tipo == "ventas": claves = ["devolucion"]
    return [{"url": reverse("accion_objeto", args=[c, objeto.pk]), "titulo": ACCIONES[c][0]} for c in claves if rol in ACCIONES[c][2]]


@login_required
def detalle(request, tipo, id):
    o = get_object_or_404(consulta(request.user, tipo), pk=id)
    info, columnas, filas, enlaces = [], [], [], []
    if tipo in {"compras", "ordenes", "ventas"}:
        columnas = ["Producto", "Cantidad"]
        if tipo == "compras": columnas += ["Costo unitario"]
        if tipo == "ventas": columnas += ["Precio unitario", "Subtotal"]
        for d in o.detalles.select_related("producto"):
            valores = [d.producto, d.cantidad]
            if tipo == "compras": valores += [dinero(d.costo_centavos)]
            if tipo == "ventas": valores += [dinero(d.precio_centavos), dinero(d.precio_centavos*d.cantidad)]
            filas.append({"celdas": valores})
    if tipo == "compras": info = [("Proveedor", o.proveedor), ("Centro", o.centro), ("Emisión", o.fecha)]
    if tipo == "ordenes":
        info = [("Origen", o.origen), ("Destino", o.destino), ("Solicitud", o.fecha)]
        for b in m.Bulto.objects.filter(detalle_orden__orden=o):
            enlaces.append((str(b), url_detalle("bultos", b.pk)))
        if hasattr(o, "remito"):
            enlaces.insert(0, (str(o.remito), url_detalle("remitos", o.remito.pk)))
    if tipo == "remitos":
        info = [("Orden", o.orden), ("Destino", o.orden.destino), ("Despacho", o.fecha_despacho or "Pendiente"), ("Cierre", o.fecha_cierre or "Pendiente")]
        columnas, filas = tabla("bultos", o.bultos.all())
        enlaces.append((str(o.orden), url_detalle("ordenes", o.orden_id)))
    if tipo == "bultos":
        info = [("Producto", o.producto), ("Cantidad", o.cantidad), ("Precinto", o.precinto or "Pendiente"),
            ("Destino", o.detalle_orden.orden.destino), ("Rechazo", o.get_motivo_rechazo_display() or "—"), ("Observaciones", o.observacion or "—")]
        if o.remito_id:
            enlaces.append((str(o.remito), url_detalle("remitos", o.remito_id)))
    if tipo == "ventas": info = [("Local", o.caja.local), ("Vendedor", o.usuario), ("Medio", o.get_medio_display()), ("Total", dinero(o.comprobante.total_centavos))]
    if tipo == "devoluciones":
        info = [("Venta", o.venta), ("Motivo", o.motivo), ("Reintegro", dinero(o.comprobante.total_centavos))]
        columnas = ["Producto", "Cantidad", "Condición"]
        filas = [{"celdas": [d.detalle_venta.producto, d.cantidad, "Apto" if d.apto else "Merma"]} for d in o.detalles.all()]
        enlaces.append((str(o.venta), url_detalle("ventas", o.venta_id)))
    if tipo == "cajas":
        info = [("Local", o.local), ("Saldo de efectivo", dinero(o.saldo))]
        movimientos = o.movimientos.select_related("usuario").order_by("-pk")
        if request.user.rol == "VENDEDOR": movimientos = movimientos.filter(usuario=request.user)
        columnas = ["Fecha", "Tipo", "Medio", "Importe", "Responsable", "Motivo"]
        filas = [{"celdas": [v.fecha, v.get_tipo_display(), v.get_medio_display(), dinero(v.monto_centavos), v.usuario, v.motivo or "—"]} for v in movimientos[:200]]
    return render(request, "detalle.html", {"titulo": f"{SECCIONES[tipo][1]} · #{o.pk}", "activo": tipo, "tipo": tipo,
        "objeto": o, "info": info, "columnas": columnas, "filas": filas, "enlaces": enlaces,
        "eventos": o.eventos.select_related("usuario").all() if hasattr(o, "eventos") else [],
        "acciones": acciones_objeto(tipo, o, request.user.rol), "comprobante": getattr(o, "comprobante", None)})


def ejecutar_accion(accion, usuario, o, datos, lineas):
    s = operaciones()
    id = o.pk if o else None
    if accion == "compra": return s.emitir_compra(usuario, datos["proveedor"].pk, [(d["producto"].pk, d["cantidad"], d["costo"]) for d in lineas])
    if accion.endswith("_compra"):
        return s.avanzar_compra(usuario, id, {"recibir_compra": "RECIBIDA", "verificar_compra": "VERIFICADA", "cancelar_compra": "CANCELADA"}[accion])
    if accion == "orden": return s.solicitar(usuario, datos["local"].pk, [(d["producto"].pk, d["cantidad"]) for d in lineas])
    if accion == "preparar": return s.preparar(usuario, datos["detalle"].pk, datos["cantidad"])
    if accion == "cancelar_orden": return s.cancelar_orden(usuario, id)
    if accion == "precintar": return s.precintar(usuario, id, datos["precinto"])
    if accion == "despachar": return s.despachar(usuario, id)
    if accion == "recibir": return s.recibir(usuario, id)
    if accion == "cerrar": return s.cerrar_remito(usuario, id)
    if accion == "controlar": return s.controlar(usuario, id, datos["aceptar"], datos["precinto_integro"], datos["motivo"], datos["observacion"])
    if accion == "retornar": return s.devolver_bulto(usuario, id)
    if accion == "resolver": return s.resolver_bulto(usuario, id, datos["recuperable"], datos["observacion"])
    if accion == "venta": return s.vender(usuario, datos["medio"], [(d["producto"].pk, d["cantidad"]) for d in lineas], datos["operacion"])
    if accion == "devolucion": return s.devolver_venta(usuario, id, datos["motivo"], [(d["detalle"].pk, d["cantidad"], d["apto"]) for d in lineas], datos["operacion"])
    if accion == "movimiento": return s.mover_caja(usuario, datos["local"].pk, datos["tipo"], datos["monto"], datos["motivo"], datos["operacion"])
    raise ErrorNegocio("Acción inexistente.")


@login_required
def accion(request, accion, id=None):
    if accion not in ACCIONES:
        raise PermissionDenied
    titulo, tipo, roles = ACCIONES[accion]
    permiso(request.user, roles)
    inicial = accion in {"compra", "orden", "venta", "movimiento"}
    if inicial != (id is None):
        raise PermissionDenied
    objeto = get_object_or_404(consulta(request.user, tipo), pk=id) if id else None
    form = campos_accion(accion, request.user, objeto)(request.POST or None)
    formset = None
    productos_info = {}
    if accion in {"compra", "orden", "venta", "devolucion"}:
        FormSet = formset_factory(formulario_lineas(accion, objeto), extra=0, min_num=1, validate_min=True, max_num=100, validate_max=True)
        formset = FormSet(request.POST or None, prefix="lineas")
        if accion == "venta":
            inventarios = {i.producto_id: i.disponible for i in m.ItemInventario.objects.filter(ubicacion=request.user.ubicacion)}
            productos_info = {str(p.pk): {"precio": p.precio_centavos, "stock": inventarios.get(p.pk, 0)}
                for p in m.Producto.objects.filter(activo=True, proveedor__activo=True)}
    if request.method == "POST":
        valido = form.is_valid()
        lineas_validas = formset.is_valid() if formset else True
        if valido and lineas_validas:
            try:
                lineas = [d for d in formset.cleaned_data if d] if formset else []
                resultado = ejecutar_accion(accion, request.user, objeto, form.cleaned_data, lineas)
            except ErrorNegocio as e:
                form.add_error(None, str(e))
            except IntegrityError:
                form.add_error(None, "Los datos entran en conflicto con otro registro. Revise duplicados y vuelva a intentar.")
            except OperationalError:
                form.add_error(None, "La base está ocupada. No se completó la operación; vuelva a intentar.")
            else:
                messages.success(request, "Operación registrada correctamente.")
                destino = {m.Compra: "compras", m.OrdenReposicion: "ordenes", m.Bulto: "bultos", m.Remito: "remitos", m.Venta: "ventas", m.Devolucion: "devoluciones"}.get(type(resultado))
                if destino: return redirect("detalle", tipo=destino, id=resultado.pk)
                return redirect("detalle", tipo="cajas", id=resultado.caja_id)
    return render(request, "formulario.html", {"titulo": titulo, "activo": tipo, "form": form, "formset": formset,
        "objeto": objeto, "volver": url_detalle(tipo, id) if id else reverse("listado", args=[tipo]),
        "productos_info": productos_info, "es_venta": accion == "venta",
        "ayuda": AYUDAS.get(accion, "La operación se registrará con su usuario y fecha actual.")})


AYUDAS = {
    "venta": "El precio se toma del catálogo. Solo se puede vender stock verificado y disponible de su local.",
    "compra": "Seleccione productos del mismo proveedor. La llegada no incorpora stock: debe verificar la compra después.",
    "orden": "Agrupe las necesidades del local. Si repite un producto, sus cantidades se sumarán.",
    "cerrar": "Todos los bultos deben estar controlados. Este cierre incorpora juntos los aceptados al stock vendible.",
    "controlar": "Controlar este bulto no habilita stock. Si el precinto está violado, el rechazo es obligatorio.",
    "devolucion": "Se reintegra por el medio original. El plazo máximo es configurable (30 días inicialmente).",
    "cancelar_orden": "Se cancelarán los bultos y el remito, liberando las reservas. El historial se conservará.",
}


@login_required
def maestro(request, tipo, id=None):
    permiso(request.user, {"ADMIN_CD"})
    if tipo not in MAESTROS:
        raise PermissionDenied
    instancia = get_object_or_404(SECCIONES[tipo][0], pk=id) if id else None
    # Los mínimos modifican ítems existentes; nunca editan existencias manualmente.
    if tipo == "inventario" and not instancia:
        raise PermissionDenied
    form = MAESTROS[tipo](request.POST or None, instance=instancia)
    if tipo == "inventario":
        form.fields["producto"].disabled = True
        form.fields["ubicacion"].disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                o = form.save()
                if tipo == "ubicaciones":
                    if o.tipo == "LOCAL": m.Caja.objects.get_or_create(local=o)
                    for producto in m.Producto.objects.all():
                        m.ItemInventario.objects.get_or_create(producto=producto, ubicacion=o)
                if tipo == "productos":
                    for ubicacion in m.Ubicacion.objects.all():
                        m.ItemInventario.objects.get_or_create(producto=o, ubicacion=ubicacion)
        except IntegrityError:
            form.add_error(None, "Ya existe un registro con esos identificadores.")
        else:
            messages.success(request, "Datos guardados.")
            return redirect("listado", tipo=tipo)
    return render(request, "formulario.html", {"titulo": f"{'Editar' if id else 'Crear'} · {SECCIONES[tipo][1]}",
        "activo": tipo, "form": form, "volver": reverse("listado", args=[tipo]),
        "ayuda": "Los registros históricos se conservan. Use el campo activo para dar de baja cuando corresponda."})


@login_required
def reporte(request, tipo="ingresos"):
    permiso(request.user, ADM)
    form = FiltroReporte(request.GET)
    if tipo == "ingresos":
        del form.fields["categoria"]
        del form.fields["motivo"]
    elif tipo == "margen":
        del form.fields["medio"]
        del form.fields["motivo"]
    elif tipo == "existencias":
        for nombre in ["desde", "hasta", "medio", "motivo"]:
            del form.fields[nombre]
    else:
        del form.fields["medio"]
    if request.user.rol != "ADMIN_CD":
        form.fields["local"].queryset = m.Ubicacion.objects.filter(pk=request.user.ubicacion_id)
    if tipo != "existencias":
        form.fields["local"].queryset = form.fields["local"].queryset.filter(tipo="LOCAL")
    resultado = None
    if form.is_valid():
        d = form.cleaned_data
        try:
            resultado = Reportes(DatosORM(), operaciones()).generar(request.user, tipo, d.get("desde"), d.get("hasta"),
                d["local"].pk if d["local"] else None, d["categoria"].pk if d.get("categoria") else None, d.get("medio"), d.get("motivo"))
        except ErrorNegocio as e:
            form.add_error(None, str(e))
    resumen = []
    etiquetas = {"bruto": "Ventas brutas", "reintegros": "Reintegros", "neto": "Ingreso neto", "margen": "Margen estimado",
        "bultos_rechazados": "Bultos rechazados", "unidades_rechazadas": "Unidades rechazadas", "unidades_merma": "Unidades dadas de baja"}
    if resultado:
        resumen = [(etiquetas[k], dinero(v) if k in {"bruto", "reintegros", "neto", "margen"} else v) for k,v in resultado["totales"].items()]
    return render(request, "reporte.html", {"titulo": resultado["titulo"] if resultado else "Reportes",
        "activo": "reportes", "reporte_tipo": tipo, "form": form, "resultado": resultado, "resumen": resumen})


@login_required
def comprobante(request, id):
    c = get_object_or_404(m.Comprobante, pk=id)
    venta = m.Venta.objects.filter(comprobante=c).first()
    devolucion = m.Devolucion.objects.filter(comprobante=c).first()
    if devolucion: venta = devolucion.venta
    if not venta or (request.user.rol != "ADMIN_CD" and venta.caja.local_id != request.user.ubicacion_id):
        raise PermissionDenied
    permiso(request.user, TODOS)
    if devolucion:
        lineas = [[d.detalle_venta.producto, d.cantidad, dinero(d.detalle_venta.precio_centavos), dinero(d.cantidad*d.detalle_venta.precio_centavos)] for d in devolucion.detalles.all()]
    else:
        lineas = [[d.producto, d.cantidad, dinero(d.precio_centavos), dinero(d.cantidad*d.precio_centavos)] for d in venta.detalles.all()]
    return render(request, "comprobante.html", {"titulo": c.numero, "c": c, "venta": venta,
        "devolucion": devolucion, "lineas": lineas, "total": dinero(c.total_centavos)})
