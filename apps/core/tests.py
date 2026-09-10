"""Testes do dashboard executivo: gráficos, status e formatação (RF-060 a RF-065)."""
from datetime import date
from unittest import mock

from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries.models import Lancamento
from apps.entries.services import aprovar, salvar_ou_enviar
from apps.finance.models import FinanceiroConsolidado
from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar


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


def _contexto_dashboard(usuario):
    """Chama dashboard via RequestFactory com render mockado (manifest quebrado)."""
    from apps.core.views import dashboard

    fabrica = RequestFactory()
    requisicao = fabrica.get("/")
    requisicao.user = usuario
    with mock.patch("apps.core.views.render") as mock_render:
        mock_render.return_value = HttpResponse()
        dashboard(requisicao)
    return mock_render.call_args[0][2]


class DashboardPilarRBAC(TestCase):
    """RBAC por pilar no dashboard: PontoFocal vê só seus pilares."""

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="master_rbac", password="x"), "Master"
        )
        self.focal_at = adicionar_grupo(
            User.objects.create_user(username="focal_at", password="x"), "PontoFocal"
        )
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)
        self.pilar_pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=2)
        UsuarioPilar.objects.create(usuario=self.focal_at, pilar=self.pilar_at)
        self.ind_cnpjs = Indicador.objects.create(
            pilar=self.pilar_at, codigo="AT-CNPJ-NOVOS", nome="CNPJs novos", tipo="QTD"
        )
        self.ind_artigos = Indicador.objects.create(
            pilar=self.pilar_pdi, codigo="PDI-ARTIGOS", nome="Artigos", tipo="QTD"
        )
        self.ind_pi = Indicador.objects.create(
            pilar=self.pilar_pdi, codigo="PDI-PI", nome="PIs", tipo="QTD"
        )
        self.periodo = Periodo.objects.create(
            competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.master
        )
        FinanceiroConsolidado.objects.create(
            periodo=self.periodo, pilar=self.pilar_at, tipo_recurso="AT",
            valor_captado=1000, valor_executado=200,
        )
        FinanceiroConsolidado.objects.create(
            periodo=self.periodo, pilar=self.pilar_pdi, tipo_recurso="AT",
            valor_captado=5000, valor_executado=9000,
        )
        self.dest_geral = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=None, titulo="Geral", descricao="Geral",
        )
        self.dest_at = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.pilar_at, titulo="Só AT", descricao="AT",
        )
        self.dest_pdi = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.pilar_pdi, titulo="Só PDI", descricao="PDI",
        )

    def test_focal_at_ve_cnpjs_mas_nao_artigos(self):
        contexto = _contexto_dashboard(self.focal_at)
        self.assertIn("cnpjs", contexto["cards"])
        self.assertIsNotNone(contexto["cards"]["cnpjs"])
        self.assertNotIn("artigos", contexto["cards"])
        self.assertNotIn("pi", contexto["cards"])

    def test_focal_at_financeiro_e_consolidado_so_at(self):
        from decimal import Decimal

        contexto = _contexto_dashboard(self.focal_at)
        self.assertEqual(contexto["cards"]["execucao"], Decimal("200"))
        self.assertEqual(contexto["cards"]["captacao_at"], Decimal("1000"))
        codigos_chart = [p["codigo"] for p in contexto["chart_financeiro"]]
        self.assertEqual(codigos_chart, ["AT"])
        self.assertEqual(
            [l["pilar"].codigo for l in contexto["linhas"]], ["AT"]
        )
        titulos = {d.titulo for d in contexto["destaques"]}
        self.assertIn("Geral", titulos)
        self.assertIn("Só AT", titulos)
        self.assertNotIn("Só PDI", titulos)

    def test_master_ve_tudo(self):
        contexto = _contexto_dashboard(self.master)
        self.assertIn("cnpjs", contexto["cards"])
        self.assertIn("artigos", contexto["cards"])
        self.assertIn("pi", contexto["cards"])
        codigos_chart = {p["codigo"] for p in contexto["chart_financeiro"]}
        self.assertEqual(codigos_chart, {"AT", "PDI"})
        titulos = {d.titulo for d in contexto["destaques"]}
        self.assertEqual(titulos, {"Geral", "Só AT", "Só PDI"})