from uuid import uuid4
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from config.composicion import operaciones
from src.infraestructura.persistencia import models as m


class Command(BaseCommand):
    help = "Crea un escenario académico completo en una base vacía. Nunca borra datos."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="DemoNexo2026!", help="Contraseña para las cinco cuentas de demostración")

    @transaction.atomic
    def handle(self, *args, **options):
        if m.Ubicacion.objects.exists() or m.Usuario.objects.exists():
            raise CommandError("La base ya tiene datos. No se modificó nada. Use una base vacía para la demostración.")
        cd = m.Ubicacion.objects.create(nombre="Centro de distribución", tipo="CD", direccion="Av. Central 1200")
        norte = m.Ubicacion.objects.create(nombre="Local Norte", tipo="LOCAL", direccion="Av. Norte 430")
        sur = m.Ubicacion.objects.create(nombre="Local Sur", tipo="LOCAL", direccion="Av. Sur 850")
        for local in [norte, sur]: m.Caja.objects.create(local=local)
        usuarios = {}
        for nombre, rol, ubicacion, apellido in [
            ("admin_cd", "ADMIN_CD", cd, "CD"), ("admin_norte", "ADMIN_MINORISTA", norte, "Norte"),
            ("vendedor_norte", "VENDEDOR", norte, "Norte"), ("admin_sur", "ADMIN_MINORISTA", sur, "Sur"),
            ("vendedor_sur", "VENDEDOR", sur, "Sur"),
        ]:
            usuarios[nombre] = m.Usuario.objects.create_user(username=nombre, password=options["password"],
                first_name="Equipo", last_name=apellido, rol=rol, ubicacion=ubicacion)
        proveedor = m.Proveedor.objects.create(nombre="Distribuidora del Centro", cuit="30712345678", direccion="Ruta 9, km 12")
        alimentos = m.Categoria.objects.create(nombre="Almacén")
        limpieza = m.Categoria.objects.create(nombre="Limpieza")
        productos = []
        for sku, nombre, precio, costo, categoria in [
            ("ALM-001", "Arroz largo fino · 1 kg", 240000, 1500, alimentos),
            ("ALM-002", "Aceite de girasol · 900 ml", 350000, 2100, alimentos),
            ("ALM-003", "Yerba mate · 500 g", 420000, 2800, alimentos),
            ("LIM-001", "Detergente · 750 ml", 210000, 1200, limpieza),
            ("LIM-002", "Jabón líquido · 800 ml", 580000, 3900, limpieza),
        ]:
            p = m.Producto.objects.create(sku=sku, nombre=nombre, precio_centavos=precio, categoria=categoria, proveedor=proveedor)
            productos.append((p, costo))
            for ubicacion in [cd, norte, sur]:
                m.ItemInventario.objects.create(producto=p, ubicacion=ubicacion, minimo=10 if ubicacion == cd else 5)
        ops = operaciones()
        admin = usuarios["admin_cd"]
        compra = ops.emitir_compra(admin, proveedor.pk, [(p.pk, 100, costo) for p, costo in productos])
        ops.avanzar_compra(admin, compra.pk, "RECIBIDA")
        ops.avanzar_compra(admin, compra.pk, "VERIFICADA")
        for sufijo, local in [("norte", norte), ("sur", sur)]:
            encargado = usuarios[f"admin_{sufijo}"]
            orden = ops.solicitar(encargado, local.pk, [(p.pk, 20) for p, _ in productos])
            for detalle in orden.detalles.all():
                b = ops.preparar(admin, detalle.pk, detalle.cantidad)
                ops.precintar(admin, b.pk, f"DEMO-{sufijo}-{b.pk:04}")
            remito = orden.remito
            ops.despachar(admin, remito.pk)
            ops.recibir(encargado, remito.pk)
            for b in remito.bultos.all(): ops.controlar(encargado, b.pk, True, True)
            ops.cerrar_remito(encargado, remito.pk)
            ops.mover_caja(encargado, local.pk, "INGRESO", 50000, "Fondo inicial de demostración", uuid4())
        vendedor = usuarios["vendedor_norte"]
        venta = ops.vender(vendedor, "EFECTIVO", [(productos[0][0].pk, 3), (productos[1][0].pk, 2)], uuid4())
        ops.vender(vendedor, "DEBITO", [(productos[2][0].pk, 4)], uuid4())
        ops.vender(usuarios["vendedor_sur"], "TRANSFERENCIA", [(productos[3][0].pk, 2)], uuid4())
        ops.devolver_venta(vendedor, venta.pk, "Ejemplo de devolución parcial", [(venta.detalles.first().pk, 1, True)], uuid4())
        # Remito mixto: un rechazo queda en regreso y otro se convierte en merma.
        orden = ops.solicitar(usuarios["admin_norte"], norte.pk, [(p.pk, 5) for p, _ in productos[:3]])
        for detalle in orden.detalles.all():
            b = ops.preparar(admin, detalle.pk, detalle.cantidad)
            ops.precintar(admin, b.pk, f"DEMO-REV-{b.pk:04}")
        ops.despachar(admin, orden.remito.pk)
        ops.recibir(usuarios["admin_norte"], orden.remito.pk)
        bultos = list(orden.remito.bultos.all())
        ops.controlar(usuarios["admin_norte"], bultos[0].pk, True, True)
        for b in bultos[1:]: ops.controlar(usuarios["admin_norte"], b.pk, False, False)
        ops.cerrar_remito(usuarios["admin_norte"], orden.remito.pk)
        for b in bultos[1:]: ops.devolver_bulto(usuarios["admin_norte"], b.pk)
        ops.resolver_bulto(admin, bultos[1].pk, False, "Contenido derramado; baja confirmada en la demostración")
        pendiente = ops.solicitar(usuarios["admin_sur"], sur.pk, [(productos[4][0].pk, 8)])
        b = ops.preparar(admin, pendiente.detalles.first().pk, 8)
        ops.precintar(admin, b.pk, f"DEMO-PEND-{b.pk:04}")
        self.stdout.write(self.style.SUCCESS("Escenario de demostración creado."))
        self.stdout.write("Usuarios: " + ", ".join(usuarios))
        self.stdout.write("Contraseña de demostración: " + options["password"])
