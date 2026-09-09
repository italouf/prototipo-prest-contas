"""Testes do seed de indicadores operacionais (LOOP 1)."""
from django.core.management import call_command
from django.test import TestCase

from apps.indicators.models import Indicador, Meta
from apps.pillars.models import Pilar


ESPERADOS = [
    ("PDI", "PDI-PUB-SUB", "Publicações submetidas", "QTD", "un"),
    ("PDI", "PDI-COLAB-NAC", "Colaborações nacionais", "QTD", "un"),
    ("PDI", "PDI-COLAB-INT", "Colaborações internacionais", "QTD", "un"),
    ("FORMACAO", "FCRH-TURMA-LATO", "Turmas Lato Sensu em andamento", "QTD", "un"),
    ("FORMACAO", "FCRH-TURMA-AND", "Turmas em andamento", "QTD", "un"),
    ("FORMACAO", "FCRH-CURTA-DUR", "Cursos de curta duração", "QTD", "un"),
    ("STARTUPS", "ACS-EMPREENDEDOR", "Empreendedores participantes", "QTD", "un"),
    ("STARTUPS", "ACS-CERTIFICADOS", "Total certificados", "QTD", "un"),
    ("STARTUPS", "ACS-ARENA-TIMES", "Times no Arena QuIIN", "QTD", "un"),
    ("STARTUPS", "ACS-VB-STARTUPS", "Startups criadas (Venture Building)", "QTD", "un"),
    ("AT", "AT-RENOVACAO-AND", "Renovações em andamento", "QTD", "un"),
    ("AT", "AT-PIPELINE-OPEN", "Pipeline open", "MON", "BRL"),
]


class SeedOperacionaisTestes(TestCase):
    def setUp(self):
        Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        Pilar.objects.create(codigo="FORMACAO", nome="Formação e Capacitação de RH", ordem=2)
        Pilar.objects.create(codigo="STARTUPS", nome="Atração e Criação de Startups", ordem=3)
        Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=4)

    def test_seed_cria_12_indicadores_sem_metas(self):
        call_command("seed_operacionais")

        self.assertEqual(Indicador.objects.count(), 12)
        self.assertEqual(Meta.objects.count(), 0)
        for pilar_cod, codigo, nome, tipo, unidade in ESPERADOS:
            ind = Indicador.objects.get(codigo=codigo)
            self.assertEqual(ind.pilar.codigo, pilar_cod)
            self.assertEqual(ind.nome, nome)
            self.assertEqual(ind.tipo, tipo)
            self.assertEqual(ind.unidade, unidade)
            self.assertTrue(ind.ativo)

    def test_seed_e_idempotente_nao_duplica(self):
        call_command("seed_operacionais")
        call_command("seed_operacionais")

        self.assertEqual(Indicador.objects.count(), 12)
        self.assertEqual(Meta.objects.count(), 0)
