"""Testes do seed_demo (idempotência e conteúdo mínimo)."""
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.periods.models import Periodo
from apps.pillars.models import Pilar


class SeedDemoTestes(TestCase):
    def test_seed_demo_e_idempotente_e_gera_base_minima(self):
        call_command("seed_demo")
        call_command("seed_demo")
        self.assertEqual(User.objects.count(), 8)
        self.assertEqual(Pilar.objects.count(), 6)
        self.assertEqual(Periodo.objects.filter(competencia__year=2026).count(), 7)
        self.assertIsNotNone(Periodo.objects.get(competencia="2026-06-01"))
        self.assertTrue(Lancamento.objects.filter(periodo__competencia="2026-06-01").exists())
        self.assertTrue(FinanceiroConsolidado.objects.exists())

    def test_periodos_demo_tem_status_esperado(self):
        call_command("seed_demo")
        self.assertEqual(Periodo.objects.get(competencia="2026-05-01").status, "FECHADO")
        self.assertEqual(Periodo.objects.get(competencia="2026-06-01").status, "ABERTO")

    def test_erica_e_superusuario_e_clarissa_nao(self):
        call_command("seed_demo")
        erica = User.objects.get(username="erica")
        clarissa = User.objects.get(username="clarissa")
        self.assertTrue(erica.is_staff)
        self.assertTrue(erica.is_superuser)
        self.assertFalse(clarissa.is_staff)
        self.assertFalse(clarissa.is_superuser)
        self.assertTrue(erica.groups.filter(name="Master").exists())
