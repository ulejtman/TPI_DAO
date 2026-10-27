from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Ubicacion(models.Model):
    TIPOS = [("CD", "Centro de distribución"), ("LOCAL", "Local minorista")]
    nombre = models.CharField(max_length=120, unique=True)
    tipo = models.CharField(max_length=5, choices=TIPOS)
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["tipo", "nombre"]
        constraints = [models.UniqueConstraint(fields=["tipo"], condition=Q(tipo="CD"), name="un_solo_cd")]

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    ROLES = [("ADMIN_CD", "Administrador CD"), ("ADMIN_MINORISTA", "Administrador local"), ("VENDEDOR", "Vendedor")]
    rol = models.CharField(max_length=20, choices=ROLES)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT)

    def __str__(self):
        return self.get_full_name() or self.username


class Proveedor(models.Model):
    nombre = models.CharField(max_length=120)
    cuit = models.CharField(max_length=11, unique=True)
    telefono = models.CharField(max_length=40, blank=True)
    direccion = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=140)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    precio_centavos = models.PositiveBigIntegerField(default=0, verbose_name="Precio en centavos")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.sku} · {self.nombre}"


class ItemInventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT)
    existencia = models.PositiveIntegerField(default=0)
    reservado = models.PositiveIntegerField(default=0)
    minimo = models.PositiveIntegerField(default=0)

    @property
    def disponible(self):
        return self.existencia - self.reservado

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["producto", "ubicacion"], name="inventario_producto_ubicacion"),
            models.CheckConstraint(condition=Q(reservado__lte=F("existencia")), name="reserva_no_supera_existencia"),
        ]


class Caja(models.Model):
    local = models.OneToOneField(Ubicacion, on_delete=models.PROTECT)

    @property
    def saldo(self):
        return self.movimientos.filter(medio="EFECTIVO").aggregate(s=models.Sum("monto_centavos"))["s"] or 0

    def __str__(self):
        return f"Caja · {self.local}"


class ConHistorial(models.Model):
    class Meta:
        abstract = True

    @property
    def estado(self):
        evento = self.eventos.order_by("-fecha", "-pk").first()
        return evento.estado if evento else None


class Compra(ConHistorial):
    ambito = "COMPRA"
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    centro = models.ForeignKey(Ubicacion, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Compra #{self.pk}"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, related_name="detalles", on_delete=models.PROTECT)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    costo_centavos = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="compra_cantidad_positiva")]


class OrdenReposicion(ConHistorial):
    ambito = "ORDEN"
    origen = models.ForeignKey(Ubicacion, related_name="ordenes_salida", on_delete=models.PROTECT)
    destino = models.ForeignKey(Ubicacion, related_name="ordenes_entrada", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Orden #{self.pk} · {self.destino}"


class DetalleOrden(models.Model):
    orden = models.ForeignKey(OrdenReposicion, related_name="detalles", on_delete=models.PROTECT)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["orden", "producto"], name="producto_unico_orden"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="orden_cantidad_positiva")]

    def __str__(self):
        return f"{self.producto} · pedido {self.cantidad}"


class Remito(ConHistorial):
    ambito = "REMITO"
    orden = models.OneToOneField(OrdenReposicion, related_name="remito", on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    fecha_despacho = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Remito #{self.pk}"


class Bulto(ConHistorial):
    ambito = "BULTO"
    detalle_orden = models.ForeignKey(DetalleOrden, related_name="bultos", on_delete=models.PROTECT)
    remito = models.ForeignKey(Remito, related_name="bultos", null=True, blank=True, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precinto = models.CharField(max_length=80, unique=True, null=True, blank=True)
    fecha_recepcion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.CharField(max_length=30, blank=True, choices=[
        ("PRECINTO_VIOLADO", "Precinto violado"), ("ENVIO_ERRONEO", "Envío erróneo"), ("OTRO", "Otro")])
    observacion = models.TextField(blank=True)

    @property
    def producto(self):
        return self.detalle_orden.producto

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="bulto_cantidad_positiva")]

    def __str__(self):
        return f"Bulto #{self.pk} · {self.producto} × {self.cantidad}"


class EventosQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("El historial es inmutable.")

    def delete(self):
        raise ValueError("El historial es inmutable.")


class EventoEstado(models.Model):
    ambito = models.CharField(max_length=10)
    estado = models.CharField(max_length=30)
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    compra = models.ForeignKey(Compra, related_name="eventos", null=True, on_delete=models.PROTECT)
    orden = models.ForeignKey(OrdenReposicion, related_name="eventos", null=True, on_delete=models.PROTECT)
    remito = models.ForeignKey(Remito, related_name="eventos", null=True, on_delete=models.PROTECT)
    bulto = models.ForeignKey(Bulto, related_name="eventos", null=True, on_delete=models.PROTECT)
    objects = EventosQuerySet.as_manager()

    class Meta:
        ordering = ["fecha", "pk"]
        constraints = [models.CheckConstraint(condition=(
            Q(ambito="COMPRA", compra__isnull=False, orden__isnull=True, remito__isnull=True, bulto__isnull=True) |
            Q(ambito="ORDEN", compra__isnull=True, orden__isnull=False, remito__isnull=True, bulto__isnull=True) |
            Q(ambito="REMITO", compra__isnull=True, orden__isnull=True, remito__isnull=False, bulto__isnull=True) |
            Q(ambito="BULTO", compra__isnull=True, orden__isnull=True, remito__isnull=True, bulto__isnull=False)
        ), name="evento_un_dueno_ambito")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("El historial es inmutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("El historial es inmutable.")


MEDIOS = [("EFECTIVO", "Efectivo"), ("DEBITO", "Tarjeta de débito"),
    ("CREDITO", "Tarjeta de crédito"), ("TRANSFERENCIA", "Transferencia")]


class RegistroInmutable(models.Model):
    objects = EventosQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("La operación registrada es inmutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("La operación registrada es inmutable.")


class Comprobante(RegistroInmutable):
    tipo = models.CharField(max_length=20, choices=[("TICKET", "Ticket interno"), ("NOTA_CREDITO", "Nota de crédito")])
    fecha = models.DateTimeField(default=timezone.now)
    total_centavos = models.PositiveBigIntegerField()

    @property
    def numero(self):
        return f"{'NC' if self.tipo == 'NOTA_CREDITO' else 'TI'}-{self.pk:08d}"


class Venta(RegistroInmutable):
    fecha = models.DateTimeField(default=timezone.now)
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    medio = models.CharField(max_length=20, choices=MEDIOS)
    comprobante = models.OneToOneField(Comprobante, on_delete=models.PROTECT)
    operacion = models.UUIDField(unique=True)

    def __str__(self):
        return f"Venta #{self.pk}"


class DetalleVenta(RegistroInmutable):
    venta = models.ForeignKey(Venta, related_name="detalles", on_delete=models.PROTECT)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_centavos = models.PositiveBigIntegerField()
    costo_centavos = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="venta_cantidad_positiva")]

    def __str__(self):
        return f"{self.producto} · vendido {self.cantidad}"


class Devolucion(RegistroInmutable):
    venta = models.ForeignKey(Venta, related_name="devoluciones", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    motivo = models.TextField()
    comprobante = models.OneToOneField(Comprobante, on_delete=models.PROTECT)
    operacion = models.UUIDField(unique=True)

    def __str__(self):
        return f"Devolución #{self.pk}"


class DetalleDevolucion(RegistroInmutable):
    devolucion = models.ForeignKey(Devolucion, related_name="detalles", on_delete=models.PROTECT)
    detalle_venta = models.ForeignKey(DetalleVenta, related_name="devoluciones", on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    apto = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="devolucion_cantidad_positiva")]


class Merma(RegistroInmutable):
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    origen = models.CharField(max_length=30)
    fecha = models.DateTimeField(default=timezone.now)
    bulto = models.OneToOneField(Bulto, null=True, blank=True, on_delete=models.PROTECT)
    detalle_devolucion = models.OneToOneField(DetalleDevolucion, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            Q(bulto__isnull=False, detalle_devolucion__isnull=True) |
            Q(bulto__isnull=True, detalle_devolucion__isnull=False)), name="merma_un_origen"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="merma_cantidad_positiva")]


class MovimientoCaja(RegistroInmutable):
    caja = models.ForeignKey(Caja, related_name="movimientos", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=20, choices=[("VENTA", "Venta"), ("DEVOLUCION", "Devolución"),
        ("INGRESO", "Ingreso manual"), ("RETIRO", "Retiro manual")])
    medio = models.CharField(max_length=20, choices=MEDIOS)
    monto_centavos = models.BigIntegerField()
    motivo = models.CharField(max_length=250, blank=True)
    venta = models.OneToOneField(Venta, null=True, blank=True, on_delete=models.PROTECT)
    devolucion = models.OneToOneField(Devolucion, null=True, blank=True, on_delete=models.PROTECT)
    operacion = models.UUIDField(unique=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            Q(tipo="VENTA", venta__isnull=False, devolucion__isnull=True, monto_centavos__gte=0) |
            Q(tipo="DEVOLUCION", venta__isnull=True, devolucion__isnull=False, monto_centavos__lte=0) |
            Q(tipo="INGRESO", venta__isnull=True, devolucion__isnull=True, medio="EFECTIVO", monto_centavos__gt=0) |
            Q(tipo="RETIRO", venta__isnull=True, devolucion__isnull=True, medio="EFECTIVO", monto_centavos__lt=0)
        ), name="movimiento_tipo_referencias_signo")]
