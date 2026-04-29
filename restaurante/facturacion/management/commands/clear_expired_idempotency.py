from django.core.management.base import BaseCommand
from django.utils import timezone
from facturacion.models import IdempotencyKey

class Command(BaseCommand):
    help = 'Limpia las llaves de idempotencia expiradas (más de 24 horas)'

    def handle(self, *args, **options):
        now = timezone.now()
        expired_keys = IdempotencyKey.objects.filter(expires_at__lt=now)
        count = expired_keys.count()
        expired_keys.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Se eliminaron {count} llaves de idempotencia expiradas.')
        )
