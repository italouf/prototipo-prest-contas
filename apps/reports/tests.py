"""Testes do relatório mensal (RF-090 a RF-097)."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar
from apps.entries.services import aprovar, salvar_ou_enviar


class RelatorioTestes(TestCase):
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
        salvar_ou_enviar(self.periodo, self.pdi, self.erica, {str(self.ind.pk): {"valor": "1", "comentario": "Dois projetos na fila."}}, enviar=True)
        aprovar(self.periodo.lancamentos.get(), self.erica)

    def test_relatorio_mensal_apresenta_indicadores_por_pilar(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("reports:mensal", args=[self.periodo.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Relatório Mensal")
        self.assertContains(resposta, "PDI / FCCT")
        self.assertContains(resposta, "Projetos iniciados")
        self.assertContains(resposta, "50%")
        self.assertContains(resposta, "Dois projetos na fila.")


class RelatorioR5Testes(RelatorioTestes):
    def test_contexto_traz_graficos_e_assinatura(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("reports:mensal", args=[self.periodo.pk]))
        self.assertIn("chart_mensal_json", resposta.context)
        self.assertIn("chart_pilares_json", resposta.context)
        assinatura = resposta.context["assinatura"]
        self.assertEqual(len(assinatura), 16)
        self.assertContains(resposta, 'data-testid="report-capa"')
        self.assertContains(resposta, 'data-testid="report-grafico-captacao"')
        self.assertContains(resposta, assinatura)


class RelatorioRBACTestes(TestCase):
    """Relatório mensal respeita pilares visíveis (L24, decisão 3)."""

    def setUp(self):
        from apps.entries.models import Lancamento
        from apps.finance.models import FinanceiroConsolidado
        from apps.pillars.models import UsuarioPilar

        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="rep_master", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.at = Pilar.objects.create(codigo="AT", nome="AT", ordem=2)
        self.ind_pdi = Indicador.objects.create(
            pilar=self.pdi, codigo="PDI-X", nome="X", tipo="QTD")
        self.ind_at = Indicador.objects.create(
            pilar=self.at, codigo="AT-X", nome="Y", tipo="QTD")
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")
        Lancamento.objects.create(
            periodo=self.periodo, indicador=self.ind_pdi,
            valor_numerico=1, status="APROVADO")
        Lancamento.objects.create(
            periodo=self.periodo, indicador=self.ind_at,
            valor_numerico=2, status="APROVADO")
        FinanceiroConsolidado.objects.create(
            periodo=self.periodo, pilar=self.pdi, tipo_recurso="EMBRAPII",
            valor_captado=0, valor_executado=100)
        FinanceiroConsolidado.objects.create(
            periodo=self.periodo, pilar=self.at, tipo_recurso="AT",
            valor_captado=1000, valor_executado=200)
        self.focal = adicionar_grupo(
            User.objects.create_user(username="rep_focal", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pdi)

    def test_focal_ve_so_propio_pilar_no_financeiro(self):
        from decimal import Decimal

        self.client.force_login(self.focal)
        resposta = self.client.get(reverse("reports:mensal", args=[self.periodo.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["total_executado"], Decimal("100"))
        self.assertEqual(resposta.context["total_aprovados"], 1)
        codigos = {d["codigo"] for d in resposta.context["chart_pilares"]}
        self.assertEqual(codigos, {"PDI"})
