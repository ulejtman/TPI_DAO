# Ventas e inventario entre centro de distribución y locales

Trabajo práctico integrador de Desarrollo de Aplicaciones con Objetos, tema 3. Aplicación web con Python, Django, plantillas HTML y SQLite. La interfaz usa el nombre de demostración **Nexo**.

Incluye compras, inventario, reposición, bultos, remitos, recepción, devoluciones logísticas, ventas, cobros, comprobantes internos, devoluciones comerciales, caja y cuatro reportes. Los patrones de diseño exigidos por la cátedra **siguen pendientes de asignación**; no se considera completado ese requisito académico.

## Inicio en Windows

Desde esta carpeta, con Python 3.12 o superior:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py datos_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Abrir [la aplicación local](http://127.0.0.1:8000/). Si el entorno y los datos ya están preparados, basta el último comando. También puede ejecutarse `iniciar.ps1`.

El comando `datos_demo` exige una base vacía y nunca elimina ni reinicia información existente. Crea cinco cuentas de ejemplo:

| Usuario | Rol | Ubicación |
| --- | --- | --- |
| admin_cd | Administrador CD | Centro de distribución |
| admin_norte | Administrador local | Local Norte |
| vendedor_norte | Vendedor | Local Norte |
| admin_sur | Administrador local | Local Sur |
| vendedor_sur | Vendedor | Local Sur |

Contraseña de las cuentas de demostración: `DemoNexo2026!`. Se puede elegir otra al cargar el escenario con `manage.py datos_demo --password "UnaClaveDeDemostracion"`.

## Estructura

```text
config/                   Configuración Django y composición de adaptadores
src/dominio/              Entidades y reglas Python independientes de Django
src/aplicacion/           Casos de uso, puertos y reportes
src/infraestructura/      DAO, mapeadores, unidad de trabajo y modelos ORM
src/presentacion/         Vistas, formularios, rutas, plantillas y estilos
tests/                    Pruebas unitarias, procesos, web y concurrencia
docs/                     Análisis, decisiones, modelos, contratos y manual
docs/fuentes/             Copias sin modificar de los cuatro archivos originales
```

La separación se implementa por responsabilidad, sin crear paquetes vacíos para cada entidad. Los agregados persistentes están agrupados en los modelos ORM; las reglas puras y entidades de dominio usadas por los servicios están en módulos de dominio. Los detalles del límite entre ambos están documentados en [arquitectura](docs/arquitectura.md).

## Verificación

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test tests
```

Las pruebas usan una base de datos de prueba y no cambian la demostración. Cubren permisos, stock, barrera de verificación del remito, rechazos, cancelaciones, devoluciones, atomicidad, inmutabilidad, reintentos, reportes y competencia por el último stock.

## Documentación

- [Análisis completo del material](docs/analisis.md).
- [Decisiones confirmadas](docs/decisiones.md).
- [Arquitectura y límites de dependencia](docs/arquitectura.md).
- [Contratos de los casos de uso](docs/casos-de-uso.md).
- [DER actualizado y diagramas](docs/modelo/README.md).
- [Trazabilidad contra la consigna](docs/trazabilidad.md).
- [Manual y recorrido de demostración](docs/manual.md).
- [Resultados de verificación](docs/verificacion.md).

## Configuración

`.env.example` documenta las variables disponibles; se configuran en el entorno de PowerShell, no se cargan automáticamente desde un archivo. El plazo de devolución es de 30 días y la zona horaria es Buenos Aires. Los importes se guardan en centavos enteros.

La configuración incluida sirve para desarrollo y demostración local. No se realizó publicación en Internet ni integración con ARCA, bancos, tarjetas, correo u otros servicios externos. Los pagos electrónicos son registros internos; los comprobantes no tienen validez fiscal. Para ejecución sin `DEBUG` se exige una clave privada configurada en el entorno.
