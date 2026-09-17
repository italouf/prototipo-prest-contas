"""Testes da view do painel anual: filtros, deep-link e redirects (L3, TDD)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.planning.tests import criar_base_anual


class PainelAnualViewTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="erica", password="erica123"), "Master")
        self.lider = adicionar_grupo(
            User.objects.create_user(username="lider", password="lider123"), "Lideranca")

    def test_estado_padrao_sem_parametros(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.context["painel"]["ano"])
        self.assertEqual(resposta.context["painel"]["base"], "financeiro")
        self.assertContains(resposta, "Acumulado 2024 a 2027")
        self.assertRegex(resposta.content.decode(), r"R\$\s*</span>\s*40\s*<span")
        self.assertContains(resposta, "67%")

    def test_deep_link_ano_e_base(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"), {"ano": "2025", "base": "fis"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["painel"]["ano"], 2025)
        self.assertEqual(resposta.context["painel"]["base"], "fisico")
        self.assertContains(resposta, "Ano 2: 2025")
        self.assertContains(resposta, "quantidade de metas")

    def test_parametro_invalido_redireciona_para_padrao(self):
        self.client.force_login(self.master)
        for params in ({"ano": "2030"}, {"base": "x"}, {"ano": "abc", "base": "fis"}):
            with self.subTest(params=params):
                resposta = self.client.get(reverse("core:dashboard"), params)
                self.assertRedirects(resposta, "/?ano=todos&base=fin", fetch_redirect_response=False)

    def test_alias_de_base_redireciona_para_canonico(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"), {"ano": "2026", "base": "fisico"})
        self.assertRedirects(resposta, "/?ano=2026&base=fis", fetch_redirect_response=False)

    def test_url_mensal_antiga_redireciona_301(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"), {"periodo": "2026-06-01"})
        self.assertEqual(resposta.status_code, 301)
        self.assertEqual(resposta["Location"], "/?ano=2026&base=fin")
        resposta = self.client.get(reverse("core:dashboard"), {"periodo": "2023-01-01"})
        self.assertEqual(resposta["Location"], "/?ano=todos&base=fin")

    def test_hx_request_devolve_somente_o_painel(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            reverse("core:dashboard"), {"ano": "2026", "base": "fin"},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="dashboard-panel"')
        self.assertContains(resposta, 'hx-swap-oob')
        self.assertContains(resposta, 'Ano 3: 2026')
        self.assertNotContains(resposta, 'data-testid="app-header"')

    def test_toolbar_respeita_papel(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertContains(resposta, "Editar dados")
        self.client.force_login(self.lider)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(resposta, "Editar dados")

    def test_exige_login(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/accounts/login/", resposta["Location"])

    def test_mensal_preserva_dashboard_antigo(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:mensal"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Dashboard Executivo")

    def test_tabela_farol_e_modal_metodologia(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertContains(resposta, 'data-testid="pilares-table"')
        self.assertContains(resposta, "4.1 PPI: projetado x executado")
        self.assertContains(resposta, "Meta atingida")
        self.assertContains(resposta, "Execução parcial")
        self.assertContains(resposta, "Execução crítica")
        self.assertContains(resposta, "Farol de execução: metodologia e leitura")
        self.assertContains(resposta, "% Executado = (Valor executado")
