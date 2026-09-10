"""Testes do seed_demo (idempotência e conteúdo mínimo)."""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase

from apps.accounts.models import User
from apps.crm_at.models import Empresa, Oportunidade
from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.highlights.models import DestaqueMensal
from apps.periods.models import Periodo
from apps.pillars.models import Pilar
from apps.talentos.models import Alocacao, Colaborador, Competencia


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


class SeedDemoTaskBTestes(TestCase):
    """Task B — seeds demo p/ crm_at, talentos e highlights (TDD)."""

    def test_seed_task_b_idempotente_com_contagens_pipeline_e_filtro(self):
        call_command("seed_demo")
        call_command("seed_demo")
        self.assertEqual(Empresa.objects.count(), 4)
        self.assertEqual(Oportunidade.objects.count(), 4)
        self.assertEqual(Competencia.objects.count(), 3)
        self.assertEqual(Colaborador.objects.count(), 3)
        self.assertEqual(Alocacao.objects.count(), 2)
        self.assertEqual(DestaqueMensal.objects.count(), 2)
        pipeline_open = (
            Oportunidade.objects.exclude(fase__in=("FECHAMENTO", "PERDIDO")).aggregate(
                t=Sum("valor_previsto")
            )["t"]
            or Decimal("0")
        )
        self.assertEqual(pipeline_open, Decimal("934597"))
        comp = Competencia.objects.get(nome="Gestão de Eventos")
        nomes = set(
            Colaborador.objects.filter(competencias__pk=comp.pk).values_list(
                "nome", flat=True
            )
        )
        self.assertEqual(nomes, {"Ana Demonstração", "Carla Modelo"})

    def test_seed_task_b_detalha_empresas_talentos_e_destaques(self):
        call_command("seed_demo")
        metalurgica = Empresa.objects.get(nome="Metalúrgica Exemplo S.A.")
        self.assertEqual(metalurgica.cnpj, "11.111.111/0001-11")
        self.assertEqual(metalurgica.status, "ASSOCIADA")
        banco = Empresa.objects.get(nome="Banco Fictício do Sul S.A.")
        self.assertEqual(banco.cnpj, "22.222.222/0001-22")
        self.assertEqual(banco.status, "ASSOCIADA")
        startup = Empresa.objects.get(nome="Startup Demo Quântica LTDA")
        self.assertEqual(startup.cnpj, "33.333.333/0001-33")
        self.assertEqual(startup.status, "PROSPECT")
        encerada = Empresa.objects.get(nome="Consultoria Encerada LTDA")
        self.assertEqual(encerada.cnpj, "44.444.444/0001-44")
        self.assertEqual(encerada.status, "EX_ASSOCIADA")

        renovacoes = Oportunidade.objects.filter(tipo="RENOVACAO").exclude(
            fase__in=("FECHAMENTO", "PERDIDO")
        )
        self.assertEqual(renovacoes.count(), 1)
        self.assertEqual(renovacoes.aggregate(t=Sum("valor_previsto"))["t"], Decimal("220597"))

        ana = Colaborador.objects.get(nome="Ana Demonstração")
        self.assertEqual(ana.cargo, "Analista de Projetos")
        self.assertEqual(ana.pilar_principal.codigo, "AT")
        self.assertEqual(
            ana.lattes_url, "https://lattes.cnpq.br/0000000000000000"
        )
        self.assertEqual(
            {c.nome for c in ana.competencias.all()},
            {"Gestão de Eventos", "Python"},
        )
        aloc_ana = Alocacao.objects.get(
            colaborador=ana,
            projeto_ou_area="Apoio AT — Arena QuIIN",
            data_inicio=date(2026, 6, 1),
        )
        self.assertEqual(aloc_ana.horas_semanais, 10)
        self.assertIsNone(aloc_ana.data_fim)
        bruno = Colaborador.objects.get(nome="Bruno Exemplo")
        self.assertEqual(bruno.pilar_principal.codigo, "PDI")
        self.assertEqual(bruno.lattes_url, "")
        aloc_bruno = Alocacao.objects.get(
            colaborador=bruno,
            projeto_ou_area="Projeto PDI-07",
            data_inicio=date(2026, 1, 5),
        )
        self.assertEqual(aloc_bruno.horas_semanais, 30)
        self.assertEqual(aloc_bruno.data_fim, date(2026, 3, 31))

        periodo_junho = Periodo.objects.get(competencia="2026-06-01")
        erica = User.objects.get(username="erica")
        geral = DestaqueMensal.objects.get(
            titulo="Arena QuIIN reúne 113 empreendedores"
        )
        self.assertEqual(geral.periodo, periodo_junho)
        self.assertIsNone(geral.pilar)
        self.assertEqual(geral.tipo, "DESTAQUE")
        self.assertEqual(geral.criado_por, erica)
        foco = DestaqueMensal.objects.get(
            titulo="Fechar 2 renovações em negociação"
        )
        self.assertEqual(foco.periodo, periodo_junho)
        self.assertEqual(foco.pilar.codigo, "AT")
        self.assertEqual(foco.tipo, "FOCO_30_DIAS")
        self.assertEqual(foco.criado_por, erica)
