from django.core.management.base import BaseCommand

from apps.accountability.models import CentroCompetencia
from apps.projects.at_services import inicializar_produtos_at


class Command(BaseCommand):
    help = "Inicializa os produtos padrão da AT sem alterar produtos já cadastrados."

    def handle(self, *args, **options):
        quantidade = 0
        for centro in CentroCompetencia.objects.order_by("pk"):
            inicializar_produtos_at(centro)
            quantidade += 1
        self.stdout.write(self.style.SUCCESS(f"Produtos da AT conferidos em {quantidade} centros."))
