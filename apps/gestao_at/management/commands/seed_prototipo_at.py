from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.gestao_at.seed import carregar_prototipo

class Command(BaseCommand):
    help = "Completa os dados demonstrativos da Gestão da AT sem sobrescrever edições."
    def handle(self, *args, **options):
        with transaction.atomic():
            resumo = carregar_prototipo(apps)
        self.stdout.write(self.style.SUCCESS(str(resumo)))
