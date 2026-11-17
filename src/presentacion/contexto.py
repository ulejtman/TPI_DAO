def navegacion(request):
    from src.presentacion.vistas import SECCIONES
    usuario = request.user
    if not usuario.is_authenticated:
        return {}
    return {"menu": [(clave, datos[1]) for clave, datos in SECCIONES.items() if usuario.rol in datos[2]]}
