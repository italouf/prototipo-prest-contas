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


def _base_semestre(master):
    pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
    at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=2)
    ind = Indicador.objects.create(
        pilar=pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
    Meta.objects.create(
        indicador=ind, competencia_inicio=date(2026, 1, 1),
        competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=10)
    anual = Indicador.objects.create(
        pilar=pdi, codigo="PDI-ANUAL", nome="Anual", tipo="QTD")
    Meta.objects.create(
        indicador=anual, competencia_inicio=date(2026, 1, 1),
        competencia_fim=date(2026, 12, 31), periodicidade="ANUAL", valor=100)
    maio = Periodo.objects.create(competencia=date(2026, 5, 1), status="FECHADO")
    junho = Periodo.objects.create(
        competencia=date(2026, 6, 1), status="ABERTO", aberto_por=master)
    julho = Periodo.objects.create(competencia=date(2026, 7, 1), status="PLANEJADO")
    return pdi, at, ind, anual, maio, junho, julho


class SemestreServicoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="ps_master", password="x"), "Master")
        (self.pdi, self.at, self.ind, self.anual,
         self.maio, self.junho, self.julho) = _base_semestre(self.master)

    def test_itens_por_periodo_em_lote(self):
        from apps.core.calculos import itens_por_periodo

        Lancamento.objects.create(
            periodo=self.maio, indicador=self.ind, valor_numerico=D(10),
            status="APROVADO")
        mapa = itens_por_periodo([self.ind], [self.maio, self.junho])
        self.assertEqual(set(mapa), {self.maio.pk, self.junho.pk})
        self.assertEqual(mapa[self.maio.pk][0]["percentual"], D(100))
        self.assertIsNone(mapa[self.junho.pk][0]["realizado"])

    def test_itens_por_periodo_ytd_acumula_no_ano(self):
        from apps.core.calculos import itens_por_periodo

        Lancamento.objects.create(
            periodo=self.maio, indicador=self.anual, valor_numerico=D(20),
            status="APROVADO")
        Lancamento.objects.create(
            periodo=self.junho, indicador=self.anual, valor_numerico=D(30),
            status="APROVADO")
        mapa = itens_por_periodo([self.anual], [self.maio, self.junho])
        self.assertEqual(mapa[self.maio.pk][0]["realizado"], D(20))
        self.assertEqual(mapa[self.junho.pk][0]["realizado"], D(50))

    def test_painel_semestral_agrega_meses(self):
        from apps.core.prestacao import painel_semestral

        Lancamento.objects.create(
            periodo=self.maio, indicador=self.ind, valor_numerico=D(10),
            status="APROVADO")
        Lancamento.objects.create(
            periodo=self.junho, indicador=self.ind, valor_numerico=D(4),
            status="APROVADO")
        FinanceiroConsolidado.objects.create(
            periodo=self.maio, pilar=self.pdi, tipo_recurso="EMBRAPII",
            valor_captado=D(1000), valor_executado=D(200))
        ctx = painel_semestral(2026, 1, self.master)
        self.assertEqual(ctx["painel_semestral"]["rotulo_periodo"], "1º semestre de 2026")
        linha = next(t for t in ctx["tabela"] if t["pilar"].codigo == "PDI")
        self.assertEqual(linha["pct"], D(70))  # média MENSAL dos meses com dado
        self.assertEqual(linha["faixa"], "parcial")
        self.assertEqual((linha["atingidos"], linha["pendentes"]), (1, 1))
        self.assertEqual(linha["meses"], 2)
        self.assertEqual(len(ctx["geo_meses"]["grupos"]), 6)
        self.assertEqual(
            [m.rotulo for m in ctx["meses"]], ["2026-05", "2026-06"])
        self.assertEqual(ctx["status_counts"]["APROVADO"]["quantidade"], 2)

    def test_semestre_vazio_tem_estrutura_neutra(self):
        from apps.core.prestacao import painel_semestral

        ctx = painel_semestral(2026, 2, self.master)
        self.assertEqual(ctx["painel_semestral"]["rotulo_periodo"], "2º semestre de 2026")
        linha_pdi = next(t for t in ctx["tabela"] if t["pilar"].codigo == "PDI")
        self.assertIsNone(linha_pdi["pct"])  # sem lançamento no semestre
        self.assertEqual(linha_pdi["faixa"], "neutra")
        linha_at = next(t for t in ctx["tabela"] if t["pilar"].codigo == "AT")
        self.assertIsNone(linha_at["pct"])  # sem indicadores = sem denominador
        self.assertEqual(linha_at["faixa"], "neutra")
        self.assertEqual(len(ctx["geo_meses"]["grupos"]), 6)
        self.assertEqual(
            [m.rotulo for m in ctx["meses"]], ["2026-07"])

    def test_focal_ve_so_seu_pilar_no_semestre(self):
        from apps.core.prestacao import painel_semestral

        focal = adicionar_grupo(
            User.objects.create_user(username="ps_focal", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=focal, pilar=self.pdi)
        ctx = painel_semestral(2026, 1, focal)
        self.assertEqual([t["pilar"].codigo for t in ctx["tabela"]], ["PDI"])


class SemestreUrlTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="ps_url", password="x"), "Master")
        Periodo.objects.create(competencia=date(2026, 5, 1), status="FECHADO")
        Periodo.objects.create(
            competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.master)

    def url(self, qs=""):
        return reverse("core:semestral") + qs

    def test_padrao_eh_semestre_do_periodo_aberto(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:semestral"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["painel_semestral"]["rotulo_periodo"],
                         "1º semestre de 2026")

    def test_invalido_redireciona_para_canonico(self):
        self.client.force_login(self.master)
        resposta = self.client.get(self.url("?ano=2030&semestre=9"))
        self.assertRedirects(
            resposta, "/prestacao/semestral/?ano=2026&semestre=1",
            fetch_redirect_response=False)
        resposta = self.client.get(self.url("?ano=2026"))
        self.assertRedirects(
            resposta, "/prestacao/semestral/?ano=2026&semestre=1",
            fetch_redirect_response=False)

    def test_hx_request_devolve_fragmento_com_oob_espelhado(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            self.url("?ano=2026&semestre=1"), headers={"HX-Request": "true"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="painel-semestral"')
        self.assertContains(resposta, "hx-swap-oob")
        self.assertContains(resposta, 'data-testid="dashboard-controls"')
        self.assertNotContains(resposta, 'data-testid="app-header"')

    def test_navegacao_com_boost_recebe_pagina_completa(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            self.url("?ano=2026&semestre=1"),
            headers={"HX-Request": "true", "HX-Boosted": "true"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-testid="app-header"')
        self.assertContains(resposta, 'id="painel-semestral"')
        self.assertNotContains(resposta, "hx-swap-oob")

    def test_csv_do_semestre_com_bom_e_escopo(self):
        pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        ind = Indicador.objects.create(
            pilar=pdi, codigo="PDI-PROJ-INI", nome="Projetos", tipo="QTD")
        Meta.objects.create(
            indicador=ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=10)
        Lancamento.objects.create(
            periodo=Periodo.objects.get(competencia=date(2026, 5, 1)),
            indicador=ind, valor_numerico=D(10), status="APROVADO")
        self.client.force_login(self.master)
        resposta = self.client.get(
            reverse("core:semestral_csv"), {"ano": "2026", "semestre": "1"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("text/csv", resposta["Content-Type"])
        texto = resposta.content.decode("utf-8-sig")
        linhas = texto.splitlines()
        self.assertEqual(linhas[0], "Mês;Pilar;Indicador;Meta;Realizado;% Executado")
        self.assertIn("2026-05;PDI;PDI-PROJ-INI;10;10;100%", linhas)

    def test_csv_invalido_redireciona_para_canonico(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:semestral_csv"), {"ano": "x"})
        self.assertRedirects(
            resposta, "/prestacao/semestral/dados.csv?ano=2026&semestre=1",
            fetch_redirect_response=False)

    def test_pagina_cabe_no_orcamento_de_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as capturadas:
            self.client.get(self.url("?ano=2026&semestre=1"))
        self.assertLessEqual(len(capturadas.captured_queries), 40)
