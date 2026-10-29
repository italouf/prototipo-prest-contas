from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accountability.models import CentroCompetencia, ProjetoFinanceiro
from apps.projects.identity import PILARES
from apps.projects.services import resolver_projeto_importado


class Command(BaseCommand):
    help = "Vincula snapshots sem projeto permanente, sem modificar valores financeiros."

    def handle(self, *args, **options):
        quantidade = 0
        with transaction.atomic():
            list(CentroCompetencia.objects.order_by("pk").select_for_update())
            registros = ProjetoFinanceiro.objects.filter(projeto__isnull=True, pilar__codigo__in=PILARES).select_related("acompanhamento__centro", "pilar")
            for registro in registros:
                projeto = resolver_projeto_importado(registro.acompanhamento.centro,
                    registro.pilar, registro.origem, registro.nome, registro.codigo_projeto_embrapii)
                ProjetoFinanceiro.objects.filter(pk=registro.pk, projeto__isnull=True).update(projeto=projeto)
                quantidade += 1
        self.stdout.write(self.style.SUCCESS(f"{quantidade} registros vinculados ao catálogo permanente."))
