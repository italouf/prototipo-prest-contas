"""Testes da view do painel anual do pilar (L13, TDD)."""
from datetime import date
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.indicators.models import Indicador
from apps.periods.models import Periodo
from apps.planning.tests import criar_base_anual


class PilarPainelViewTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pilares = criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="pp_master", password="x"), "Master")

    def url(self, codigo):
        return reverse("core:pilar", args=[self.pilares[codigo].pk])

    def test_painel_padrao_sem_parametros(self):
        self.client.force_login(self.master)
        resposta = self.client.get(self.url("PDI"))
        self.assertEqual(resposta.status_code, 200)
        pp = resposta.context["painel_pilar"]
        self.assertIsNone(pp["ano"])
        self.assertEqual(pp["base"], "financeiro")
        self.assertEqual((pp["previsto"], pp["executado"]), (D(29), D(21)))
        self.assertContains(resposta, "Acumulado 2024 a 2027")
        self.assertContains(resposta, 'id="painel-pilar"')
        self.assertNotContains(resposta, "contexto-anual")

    def test_deep_link_ano_e_base(self):
        self.client.force_login(self.master)
        resposta = self.client.get(self.url("PDI"), {"ano": "2025", "base": "fis"})
        self.assertEqual(resposta.status_code, 200)
        pp = resposta.context["painel_pilar"]
        self.assertEqual((pp["ano"], pp["base"]), (2025, "fisico"))
        self.assertEqual((pp["previsto"], pp["executado"]), (D(6), D(5)))
        self.assertContains(resposta, "Ano 2: 2025")
        self.assertContains(resposta, "quantidade de metas")

    def test_invalido_redireciona_preservando_periodo(self):
        self.client.force_login(self.master)
        pk = self.pilares["PDI"].pk
        resposta = self.client.get(self.url("PDI"), {"ano": "2030"})
        self.assertRedirects(resposta, f"/pilar/{pk}/?ano=todos&base=fin",
                             fetch_redirect_response=False)
        resposta = self.client.get(
            self.url("PDI"), {"ano": "x", "periodo": "2026-06-01"})
        self.assertRedirects(
            resposta, f"/pilar/{pk}/?ano=todos&base=fin&periodo=2026-06-01",
            fetch_redirect_response=False)

    def test_alias_de_base_redireciona_para_canonico(self):
        self.client.force_login(self.master)
        pk = self.pilares["PDI"].pk
        resposta = self.client.get(
            self.url("PDI"), {"ano": "2026", "base": "fisico"})
        self.assertRedirects(resposta, f"/pilar/{pk}/?ano=2026&base=fis",
                             fetch_redirect_response=False)

    def test_hx_request_devolve_somente_o_painel(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            self.url("PDI"), {"ano": "2026", "base": "fin"},
            headers={"HX-Request": "true"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="painel-pilar"')
        self.assertContains(resposta, "hx-swap-oob")
        self.assertNotContains(resposta, 'data-testid="app-header"')

    def test_navegacao_com_boost_recebe_pagina_completa(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            self.url("AT"),
            headers={"HX-Request": "true", "HX-Boosted": "true"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-testid="app-header"')
        self.assertContains(resposta, 'id="painel-pilar"')
        self.assertNotContains(resposta, "hx-swap-oob")

    def test_at_mostra_captado_e_tabela_por_ano(self):
        self.client.force_login(self.master)
        resposta = self.client.get(self.url("AT"))
        self.assertContains(resposta, "Captado")
        self.assertContains(resposta, "Ano 3: 2026")
        self.assertContains(resposta, ">Total<")

    def test_secao_mensal_continua_intacta(self):
        periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")
        Indicador.objects.create(pilar=self.pilares["PDI"], codigo="PDI-X",
                                 nome="X", tipo="QTD")
        self.client.force_login(self.master)
        resposta = self.client.get(
            self.url("PDI"), {"periodo": "2026-06-01"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Indicadores do pilar")
        self.assertContains(resposta, "PDI-X")
        self.assertEqual(resposta.context["periodo"], periodo)

    def test_pagina_do_pilar_cabe_no_orcamento_de_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as capturadas:
            self.client.get(self.url("PDI"))
        self.assertLessEqual(len(capturadas.captured_queries), 25)
