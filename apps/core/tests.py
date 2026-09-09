"""Testes do dashboard executivo: gráficos, status e formatação (RF-060 a RF-065)."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries.models import Lancamento
from apps.entries.services import aprovar, salvar_ou_enviar
from apps.finance.models import FinanceiroConsolidado
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar


class DashboardExecutivoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = User.objects.create_user(username="erica", password="erica123")
        self.erica = adicionar_grupo(self.erica, "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.ind = Indicador.objects.create(pilar=self.pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1), competencia_fim=date(2026, 12, 31),
            periodicidade="MENSAL", valor=2,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        salvar_ou_enviar(self.periodo, self.pdi, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)
        aprovar(self.periodo.lancamentos.get(), self.erica)
        FinanceiroConsolidado.objects.create(
            periodo=self.periodo, pilar=self.pdi, tipo_recurso="EMBRAPII",
            valor_captado=0, valor_executado=500000,
        )
        self.client.force_login(self.erica)

    def test_dashboard_carrega_dados_de_graficos(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resposta.status_code, 200)
        contexto = resposta.context
        self.assertIn("chart_financeiro", contexto)
        self.assertIn("chart_mensal", contexto)
        self.assertIn("status_counts", contexto)
        self.assertTrue(contexto["chart_financeiro"])
        self.assertEqual(contexto["status_counts"]["APROVADO"]["quantidade"], 1)

    def test_dashboard_exibe_escala_executiva_de_valores(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertContains(resposta, "R$ 500 mil")
        self.assertContains(resposta, "R$ 500.000,00")

    def test_dashboard_exibe_graficos_no_html(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertContains(resposta, "Evolução financeira mensal")
        self.assertContains(resposta, "Captação × execução por pilar")
        self.assertContains(resposta, "chart-columns")
        self.assertContains(resposta, "segbar")