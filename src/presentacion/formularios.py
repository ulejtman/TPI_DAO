from uuid import uuid4
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from src.dominio.reglas import centavos, ErrorNegocio
from src.infraestructura.persistencia import models as m


def eleccion(modelo, etiqueta, **filtros):
    return forms.ModelChoiceField(queryset=modelo.objects.filter(**filtros), label=etiqueta)


def campos_accion(accion, usuario, objeto=None):
    campos = {}
    if accion == "compra":
        campos["proveedor"] = eleccion(m.Proveedor, "Proveedor", activo=True)
    if accion in {"orden", "movimiento"}:
        qs = m.Ubicacion.objects.filter(tipo="LOCAL", activo=True)
        if usuario.rol != "ADMIN_CD":
            qs = qs.filter(pk=usuario.ubicacion_id)
        campos["local"] = forms.ModelChoiceField(queryset=qs, label="Local")
    if accion == "preparar":
        campos["detalle"] = forms.ModelChoiceField(queryset=objeto.detalles.all(), label="Producto solicitado")
        campos["cantidad"] = forms.IntegerField(min_value=1, label="Cantidad del bulto")
    if accion == "precintar":
        campos["precinto"] = forms.CharField(max_length=80, label="Número de precinto")
    if accion == "controlar":
        campos["precinto_integro"] = forms.BooleanField(required=False, initial=True, label="El precinto llegó íntegro")
        campos["aceptar"] = forms.BooleanField(required=False, initial=True, label="Aceptar el contenido del bulto")
        campos["motivo"] = forms.ChoiceField(required=False, choices=[("", "Seleccionar si se rechaza")] + m.Bulto._meta.get_field("motivo_rechazo").choices, label="Motivo de rechazo")
        campos["observacion"] = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Observaciones")
    if accion == "resolver":
        campos["recuperable"] = forms.BooleanField(required=False, initial=True, label="Contenido revisado y recuperable")
        campos["observacion"] = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Resultado de la revisión del contenido")
    if accion == "venta":
        campos["medio"] = forms.ChoiceField(choices=m.MEDIOS, label="Medio de pago")
    if accion in {"devolucion", "movimiento"}:
        campos["motivo"] = forms.CharField(max_length=250, widget=forms.Textarea(attrs={"rows": 2}), label="Motivo")
    if accion == "movimiento":
        campos["tipo"] = forms.ChoiceField(choices=[("INGRESO", "Ingreso de efectivo"), ("RETIRO", "Retiro de efectivo")], label="Operación")
        campos["monto"] = forms.DecimalField(min_value=0.01, max_digits=14, decimal_places=2, label="Importe en pesos")
    campos["operacion"] = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    return type("FormularioOperacion", (forms.Form,), campos)


def formulario_lineas(accion, objeto=None):
    if accion == "devolucion":
        campos = {"detalle": forms.ModelChoiceField(queryset=objeto.detalles.all(), label="Renglón de la venta"),
            "cantidad": forms.IntegerField(min_value=1, label="Cantidad"),
            "apto": forms.BooleanField(required=False, initial=True, label="Apto para volver a vender")}
    else:
        campos = {"producto": eleccion(m.Producto, "Producto", activo=True, proveedor__activo=True),
            "cantidad": forms.IntegerField(min_value=1, label="Cantidad")}
        if accion == "compra":
            campos["costo"] = forms.DecimalField(min_value=0, max_digits=14, decimal_places=2, label="Costo unitario en pesos")
    return type("FormularioLinea", (forms.Form,), campos)


class ProductoForm(forms.ModelForm):
    precio = forms.DecimalField(min_value=0, max_digits=14, decimal_places=2, label="Precio unitario en pesos")

    class Meta:
        model = m.Producto
        fields = ["sku", "nombre", "categoria", "proveedor", "precio", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            from decimal import Decimal
            self.fields["precio"].initial = Decimal(self.instance.precio_centavos) / 100

    def clean_sku(self):
        return self.cleaned_data["sku"].strip().upper()

    def save(self, commit=True):
        self.instance.precio_centavos = centavos(self.cleaned_data["precio"])
        return super().save(commit)


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = m.Proveedor
        fields = ["nombre", "cuit", "telefono", "direccion", "activo"]

    def clean_cuit(self):
        valor = self.cleaned_data["cuit"].replace("-", "").replace(" ", "")
        if not valor.isascii() or not valor.isdigit() or len(valor) != 11:
            raise forms.ValidationError("El CUIT debe tener once dígitos.")
        return valor


class UbicacionForm(forms.ModelForm):
    class Meta:
        model = m.Ubicacion
        fields = ["nombre", "tipo", "direccion", "telefono", "activo"]

    def clean_tipo(self):
        tipo = self.cleaned_data["tipo"]
        if self.instance.pk and self.instance.tipo != tipo:
            raise forms.ValidationError("No se puede cambiar el tipo de una ubicación existente.")
        return tipo


class UsuarioForm(forms.ModelForm):
    clave = forms.CharField(required=False, widget=forms.PasswordInput, label="Contraseña (vacía para conservar)")

    class Meta:
        model = m.Usuario
        fields = ["username", "first_name", "last_name", "rol", "ubicacion", "is_active"]
        labels = {"is_active": "Usuario activo"}

    def clean(self):
        datos = super().clean()
        rol, ubicacion = datos.get("rol"), datos.get("ubicacion")
        if rol and ubicacion and (rol == "ADMIN_CD") != (ubicacion.tipo == "CD"):
            self.add_error("ubicacion", "La ubicación debe corresponder al rol.")
        clave = datos.get("clave")
        if not self.instance.pk and not clave:
            self.add_error("clave", "La contraseña es obligatoria al crear el usuario.")
        if clave:
            try:
                validate_password(clave, self.instance)
            except ValidationError as e:
                self.add_error("clave", e)
        return datos

    def save(self, commit=True):
        usuario = super().save(False)
        if self.cleaned_data.get("clave"):
            usuario.set_password(self.cleaned_data["clave"])
        if commit:
            usuario.save()
        return usuario


class MinimoForm(forms.ModelForm):
    class Meta:
        model = m.ItemInventario
        fields = ["producto", "ubicacion", "minimo"]


class FiltroReporte(forms.Form):
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Desde")
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Hasta")
    local = forms.ModelChoiceField(queryset=m.Ubicacion.objects.all(), required=False, label="Ubicación")
    categoria = forms.ModelChoiceField(queryset=m.Categoria.objects.all(), required=False, label="Categoría")
    medio = forms.ChoiceField(choices=[("", "Todos")] + m.MEDIOS, required=False, label="Medio de pago")
    motivo = forms.ChoiceField(choices=[("", "Todos")] + m.Bulto._meta.get_field("motivo_rechazo").choices, required=False, label="Motivo logístico")
