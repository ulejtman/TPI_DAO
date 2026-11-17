from getpass import getpass
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from src.infraestructura.persistencia.models import Ubicacion, Usuario


class Command(BaseCommand):
    help = "Crea el CD y la primera cuenta administradora, sin datos de demostración."

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin_cd')
        parser.add_argument('--nombre-cd', default='Centro de distribución')
        parser.add_argument('--direccion-cd', required=True)

    def handle(self, *args, **options):
        if Usuario.objects.exists():
            raise CommandError('Ya hay usuarios. Utilice la administración dentro de la aplicación.')
        password = getpass('Contraseña de la primera cuenta: ')
        if password != getpass('Repetir contraseña: '):
            raise CommandError('Las contraseñas no coinciden.')
        try:
            validate_password(password, Usuario(username=options['username']))
        except ValidationError as e:
            raise CommandError('; '.join(e.messages)) from e
        with transaction.atomic():
            if Usuario.objects.exists():
                raise CommandError('Ya se inicializó el sistema.')
            cd, _ = Ubicacion.objects.get_or_create(tipo='CD', defaults={
                'nombre': options['nombre_cd'], 'direccion': options['direccion_cd']})
            Usuario.objects.create_user(username=options['username'], password=password, rol='ADMIN_CD', ubicacion=cd)
        self.stdout.write(self.style.SUCCESS('CD y primera cuenta creados. Ya puede ingresar.'))
