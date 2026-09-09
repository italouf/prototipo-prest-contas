"""Seed idempotente dos 12 indicadores operacionais (LOOP 1).

Uso:
    python manage.py seed_operacionais

Cria os indicadores de acompanhamento interno (sem metas formais)
vinculados aos pilares existentes. É seguro rodar várias vezes:
usa ``get_or_create`` e nunca duplica registros.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.indicators.models import Indicador
from apps.pillars.models import Pilar

# (codigo_pilar, codigo, nome, tipo, unidade, descricao)
INDICADORES_OPERACIONAIS = [
    ("PDI", "PDI-PUB-SUB", "Publicações submetidas", "QTD", "un",
     "Publicações submetidas pelo pilar PDI."),
    ("PDI", "PDI-COLAB-NAC", "Colaborações nacionais", "QTD", "un",
     "Colaborações nacionais do pilar PDI."),
    ("PDI", "PDI-COLAB-INT", "Colaborações internacionais", "QTD", "un",
     "Colaborações internacionais do pilar PDI."),
    ("FORMACAO", "FCRH-TURMA-LATO", "Turmas Lato Sensu em andamento", "QTD", "un",
     "Turmas Lato Sensu em andamento (Formação)."),
    ("FORMACAO", "FCRH-TURMA-AND", "Turmas em andamento", "QTD", "un",
     "Turmas em andamento (Formação)."),
    ("FORMACAO", "FCRH-CURTA-DUR", "Cursos de curta duração", "QTD", "un",
     "Cursos de curta duração (Formação)."),
    ("STARTUPS", "ACS-EMPREENDEDOR", "Empreendedores participantes", "QTD", "un",
     "Empreendedores participantes (Startups)."),
    ("STARTUPS", "ACS-CERTIFICADOS", "Total certificados", "QTD", "un",
     "Total de certificados (Startups)."),
    ("STARTUPS", "ACS-ARENA-TIMES", "Times no Arena QuIIN", "QTD", "un",
     "Times participantes do Arena QuIIN."),
    ("STARTUPS", "ACS-VB-STARTUPS", "Startups criadas (Venture Building)", "QTD", "un",
     "Startups criadas via Venture Building."),
    ("AT", "AT-RENOVACAO-AND", "Renovações em andamento", "QTD", "un",
     "Renovações de associação em andamento."),
    ("AT", "AT-PIPELINE-OPEN", "Pipeline open", "MON", "BRL",
     "Valor do pipeline aberto (Associação Tecnológica)."),
]


class Command(BaseCommand):
    help = "Cria os 12 indicadores operacionais (idempotente, sem metas iniciais)."

    def handle(self, *args, **options):
        criados = 0
        existentes = 0
        for pilar_codigo, codigo, nome, tipo, unidade, descricao in INDICADORES_OPERACIONAIS:
            try:
                pilar = Pilar.objects.get(codigo=pilar_codigo)
            except Pilar.DoesNotExist:
                raise CommandError(
                    f"Pilar '{pilar_codigo}' não encontrado. "
                    f"Execute 'python manage.py seed_demo' antes para criar os pilares."
                )
            _, criado = Indicador.objects.get_or_create(
                pilar=pilar,
                codigo=codigo,
                defaults={
                    "nome": nome,
                    "tipo": tipo,
                    "unidade": unidade,
                    "descricao": descricao,
                    "ativo": True,
                    "acumulado": False,
                },
            )
            if criado:
                criados += 1
            else:
                existentes += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Indicadores operacionais prontos: {criados} criado(s), "
                f"{existentes} já existente(s), sem metas iniciais."
            )
        )
