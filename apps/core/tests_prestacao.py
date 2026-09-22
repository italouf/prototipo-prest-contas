"""Testes do serviço da prestação mensal no padrão do painel anual (L20, TDD)."""
from datetime import date
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar


def _base(master):
    pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
    at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=2)
    ind = Indicador.objects.create(
        pilar=pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
    Meta.objects.create(
        indicador=ind, competencia_inicio=date(2026, 1, 1),
        competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=10)
    junho = Periodo.objects.create(
        competencia=date(2026, 6, 1), status="ABERTO", aberto_por=master)
    julho = Periodo.objects.create(competencia=date(2026, 7, 1), status="PLANEJADO")
    return pdi, at, ind, junho, julho


class PainelMensalTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="pm_master", password="x"), "Master")
        self.pdi, self.at, self.ind, self.junho, self.julho = _base(self.master)

    def _contexto(self, periodo=None, destaque=""):
        from apps.core.prestacao import contexto_mensal

        return contexto_mensal(periodo or self.junho, self.master, destaque)

    def test_contexto_traz_painel_geometrias_e_chaves_legadas(self):
        FinanceiroConsolidado.objects.create(
            periodo=self.junho, pilar=self.pdi, tipo_recurso="EMBRAPII",
            valor_captado=D(1000), valor_executado=D(200))
        ctx = self._contexto()
        self.assertEqual(ctx["painel_mensal"]["rotulo_periodo"], "2026-06")
        self.assertEqual(ctx["painel_mensal"]["status"], "ABERTO")
        self.assertEqual(len(ctx["geo_mensal"]["grupos"]), 12)
        self.assertEqual(
            [i for i, gr in enumerate(ctx["geo_mensal"]["grupos"]) if gr["destaque"]],
            [5])
        self.assertEqual(
            [gr["eixo"][0] for gr in ctx["geo_pilares"]["grupos"]], ["PDI"])
        for chave in ("linhas", "cards", "kpis", "heatmap", "avisos",
                      "status_counts", "chart_mensal", "chart_financeiro",
                      "destaques", "pendencias"):
            self.assertIn(chave, ctx)

    def test_kpi_e_heatmap_usam_farol_anual(self):
        Lancamento.objects.create(
            periodo=self.junho, indicador=self.ind, valor_numerico=D(4),
            status="APROVADO")
        ctx = self._contexto()
        kpi = next(k for k in ctx["kpis"] if k["pilar"].codigo == "PDI")
        self.assertEqual(kpi["faixa"], "critica")  # 40% < 50 (antes: ok/atencao)
        celula = next(
            c for g in ctx["heatmap"] if g["pilar"].codigo == "PDI"
            for c in g["celulas"])
        self.assertEqual(celula["faixa"], "critica")
        Lancamento.objects.filter(pk=Lancamento.objects.get().pk).update(
            valor_numerico=D(10))
        ctx = self._contexto()
        kpi = next(k for k in ctx["kpis"] if k["pilar"].codigo == "PDI")
        self.assertEqual(kpi["faixa"], "ok")  # 100% ≥ 90

    def test_financeiro_em_milhoes_nas_geometrias(self):
        from apps.core import prestacao

        FinanceiroConsolidado.objects.create(
            periodo=self.junho, pilar=self.pdi, tipo_recurso="EMBRAPII",
            valor_captado=D(2000000), valor_executado=D(500000))
        ctx = self._contexto()
        junho = ctx["geo_mensal"]["grupos"][5]
        self.assertEqual((junho["a"]["valor"], junho["b"]["valor"]), (2.0, 0.5))
        self.assertEqual(ctx["cards"]["execucao"], D(500000))

    def test_resolver_periodo(self):
        from apps.core.prestacao import resolver_periodo

        estado, periodo = resolver_periodo({})
        self.assertEqual((estado, periodo), ("padrao", self.junho))
        estado, periodo = resolver_periodo({"periodo": "2026-07-01"})
        self.assertEqual((estado, periodo.pk), ("ok", self.julho.pk))
        for bruto in ("2026-13-01", "junho", "2025-01-01"):
            estado, periodo = resolver_periodo({"periodo": bruto})
            self.assertEqual((estado, periodo), ("invalido", self.junho))

    def test_destaque_invalido_ignorado_e_rbac_respeitado(self):
        from apps.core.prestacao import resolver_destaque

        DestaqueMensal.objects.create(
            periodo=self.junho, pilar=self.at, titulo="Só AT", descricao="A")
        self.assertEqual(resolver_destaque({"destaque_pilar": "x"}, self.master), "")
        self.assertEqual(
            resolver_destaque({"destaque_pilar": str(self.at.pk)}, self.master),
            str(self.at.pk))
        focal = adicionar_grupo(
            User.objects.create_user(username="pm_focal", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=focal, pilar=self.pdi)
        self.assertEqual(
            resolver_destaque({"destaque_pilar": str(self.at.pk)}, focal), "")

    def test_focal_ve_so_seu_pilar(self):
        FinanceiroConsolidado.objects.create(
            periodo=self.junho, pilar=self.pdi, tipo_recurso="EMBRAPII",
            valor_captado=D(1000), valor_executado=D(200))
        focal = adicionar_grupo(
            User.objects.create_user(username="pm_focal2", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=focal, pilar=self.pdi)
        from apps.core.prestacao import contexto_mensal

        ctx = contexto_mensal(self.junho, focal)
        self.assertEqual([l["pilar"].codigo for l in ctx["linhas"]], ["PDI"])
        self.assertEqual(len(ctx["geo_pilares"]["grupos"]), 1)


class MensalContratoUrlTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="pm_url", password="x"), "Master")
        self.junho = Periodo.objects.create(
            competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.master)

    def test_periodo_invalido_redireciona_para_canonico(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:mensal"), {"periodo": "2026-13-01"})
        self.assertRedirects(
            resposta, "/prestacao/mensal/?periodo=2026-06-01",
            fetch_redirect_response=False)

    def test_hx_request_devolve_fragmento_com_oob_espelhado(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            reverse("core:mensal"), {"periodo": "2026-06-01"},
            headers={"HX-Request": "true"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="painel-mensal"')
        self.assertContains(resposta, "hx-swap-oob")
        self.assertContains(resposta, 'data-testid="dashboard-controls"')
        self.assertNotContains(resposta, 'data-testid="app-header"')

    def test_navegacao_com_boost_recebe_pagina_completa(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            reverse("core:mensal"),
            headers={"HX-Request": "true", "HX-Boosted": "true"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-testid="app-header"')
        self.assertContains(resposta, 'id="painel-mensal"')
        self.assertNotContains(resposta, "hx-swap-oob")
