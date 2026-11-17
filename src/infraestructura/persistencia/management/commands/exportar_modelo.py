from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models


class Command(BaseCommand):
    help = 'Regenera el DER Mermaid desde los modelos persistentes de esta aplicación.'

    def handle(self, *args, **options):
        destino = settings.BASE_DIR / 'docs/modelo'
        destino.mkdir(parents=True, exist_ok=True)
        entidades = list(apps.get_app_config('persistencia').get_models())
        lineas = ['erDiagram']
        for entidad in entidades:
            nombre = entidad.__name__
            lineas.append(f'  {nombre} {{')
            for campo in entidad._meta.local_fields:
                if campo.name in {'password', 'last_login', 'is_superuser', 'is_staff', 'date_joined', 'email'}:
                    continue
                tipo = 'int' if isinstance(campo, (models.IntegerField, models.ForeignKey)) else 'datetime' if isinstance(campo, models.DateTimeField) else 'boolean' if isinstance(campo, models.BooleanField) else 'uuid' if isinstance(campo, models.UUIDField) else 'string'
                clave = ' PK' if campo.primary_key else ' FK' if isinstance(campo, models.ForeignKey) else ' UK' if campo.unique else ''
                lineas.append(f'    {tipo} {campo.attname}{clave}')
            lineas.append('  }')
        for entidad in entidades:
            for campo in entidad._meta.local_fields:
                if isinstance(campo, models.ForeignKey):
                    padre = campo.related_model.__name__
                    lado_padre = '|o' if campo.null else '||'
                    lado_hijo = 'o|' if campo.one_to_one else 'o{'
                    lineas.append(f'  {padre} {lado_padre}--{lado_hijo} {entidad.__name__} : {campo.name}')
        mermaid = '\n'.join(lineas) + '\n'
        (destino / 'der.mmd').write_text(mermaid, encoding='utf-8')
        (destino / 'der.md').write_text('# DER de la implementación\n\nGenerado desde los modelos Django. Se omiten campos internos de autenticación y tablas de sesiones. Las restricciones adicionales se explican en README.md.\n\n```mermaid\n' + mermaid + '```\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'DER generado en {destino}'))
