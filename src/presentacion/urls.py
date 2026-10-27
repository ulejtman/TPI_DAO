from django.contrib.auth import views as auth
from django.urls import path
from src.presentacion import vistas as v

urlpatterns = [
    path("", v.inicio, name="inicio"),
    path("acceso/", auth.LoginView.as_view(template_name="login.html"), name="login"),
    path("salir/", auth.LogoutView.as_view(), name="logout"),
    path("buscar-venta/", v.buscar_venta, name="buscar_venta"),
    path("operar/<str:accion>/", v.accion, name="accion"),
    path("operar/<str:accion>/<int:id>/", v.accion, name="accion_objeto"),
    path("datos/<str:tipo>/nuevo/", v.maestro, name="maestro_nuevo"),
    path("datos/<str:tipo>/<int:id>/", v.maestro, name="maestro_editar"),
    path("reportes/<str:tipo>/", v.reporte, name="reporte"),
    path("comprobantes/<int:id>/", v.comprobante, name="comprobante"),
    path("gestion/<str:tipo>/", v.listado, name="listado"),
    path("gestion/<str:tipo>/<int:id>/", v.detalle, name="detalle"),
]
