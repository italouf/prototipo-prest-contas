"""Contrato da visão financeira do Dashboard Geral com apenas FINANCEIRO GERAL."""
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.core.templatetags.core_extras import escala_precisa_ptbr
from apps.pillars.models import Pilar

from .. import panel, services
from ..models import Acompanhamento, ResumoFinanceiro


FINANCEIRO = (Path(__file__).resolve().parents[3] / "mockup" /
              "exemplos_arquivos" / "FINANCEIRO GERAL - REFAT.xlsx")


class DashboardFinanceiroGeralTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        usuario = get_user_model().objects.create_user(username="dashboard-fin", password="x")
        cls.usuario = adicionar_grupo(usuario, "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Centro QuIIN", "2T/2024", cls.usuario)
        cls.acomp = Acompanhamento.objects.get()

    def test_valores_consolidados_e_lacunas_da_planilha_real(self):
        visao = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        self.assertEqual([c["titulo"] for c in visao["cards"]], [
            "Recursos PPI", "Captação AT", "Outras fontes", "Execução consolidada"])
        tab1 = visao["tabela_tab1"]["linhas"]
        tab11 = visao["tabela_tab11"]["linhas"]
        self.assertEqual([r["rotulo"] for r in tab1], [
            "AFCCT / PD&I", "FCRH", "ACS", "INFRAESTRUTURA", "TOTAL"])
        self.assertEqual(tab1[-1]["recurso"], Decimal("60000000"))
        self.assertEqual(tab1[-1]["realizado"], Decimal("34975229.95"))
        self.assertEqual(tab1[-1]["diferenca"], Decimal("25024770.05"))
        self.assertEqual(tab1[-1]["faixa"], "parcial")
        self.assertIsNone(tab1[-1]["projetado"])
        self.assertEqual(tab11[-1]["recurso"], Decimal("60000000"))
        self.assertIsNone(tab11[-1]["realizado_2024"])
        self.assertIsNone(tab11[-1]["combinado"])
        self.assertEqual(tab11[-1]["faixa"], "neutra")
        self.assertEqual(visao["graficos_ciclo"]["outras"]["pct_meta_inteiro"], 162)
        self.assertEqual(visao["graficos_ciclo"]["outras"]["anel_meta"], 100)
        self.assertEqual(escala_precisa_ptbr(Decimal("34975229.95")), "R$ 34,97 mi")
        self.assertEqual(escala_precisa_ptbr(Decimal("5616700")), "R$ 5,61 mi")

    def test_dashboard_renderiza_ciclo_sem_eixo_anual_ou_grafico_obsoleto(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(f"/?ano=todos&base=fin&acompanhamento={self.acomp.pk}")
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode("utf-8")
        for texto in ("R$ 34,97 mi", "R$ 5,61 mi", "R$ 10,22 mi",
                      "58,29%", "RECURSO PPI TOTAL", "REALIZADO 2026 (YTD)",
                      "PROJETADO 2027",
                      'data-testid="tabela-anual-ppi"',
                      'data-testid="recursos-ppi-info-abrir"', "AFCCT / PD&amp;I",
                      "Infraestrutura"):
            self.assertIn(texto, html)
        for grafico in ("chart-fonte-ppi", "chart-fonte-at", "chart-fonte-outras",
                        "Execução por fonte de recursos", "Recursos PPI: projetado x executado",
                        'data-testid="consolidado-ppi"', "Consolidado PPI"):
            self.assertNotIn(grafico, html)
        self.assertNotIn('data-testid="year-select"', html)
        self.assertNotIn("Consolidado por fonte e por ano", html)
        self.assertNotIn("Ano 1: 2024", html)

    def test_ano_da_url_e_normalizado_para_ciclo(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(f"/?ano=2026&base=fin&acompanhamento={self.acomp.pk}")
        self.assertRedirects(
            resposta, f"/?ano=todos&base=fin&acompanhamento={self.acomp.pk}")

    def test_base_fisica_mantem_filtro_e_sem_grafico_obsoleto(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(f"/?ano=2026&base=fis&acompanhamento={self.acomp.pk}")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-testid="year-select"')
        self.assertNotContains(resposta, 'data-testid="chart-consolidado"')
        self.assertContains(resposta, 'data-testid="chart-fonte-ppi"')

    def test_tabela_anual_recalcula_quando_ha_dados(self):
        pdi = Pilar.objects.get(codigo="PDI")
        resumo = ResumoFinanceiro.objects.get(
            acompanhamento=self.acomp, origem="TAB. 1.1", pilar=pdi, ano=None)
        resumo.projetado = Decimal("400")
        resumo.save(update_fields=["projetado"])
        for ano, realizado, projetado in ((2024, "100", None),
                                          (2025, "200", None),
                                          (2026, "300", "400")):
            ResumoFinanceiro.objects.create(
                acompanhamento=self.acomp, origem="TAB. 1.1", pilar=pdi,
                ano=ano, realizado=Decimal(realizado),
                projetado=Decimal(projetado) if projetado else None)
        linha = panel.painel_acompanhamento(None, "financeiro", self.acomp)["tabela_tab11"]["linhas"][0]
        self.assertEqual(linha["projetado_total"], Decimal("400"))
        self.assertEqual(linha["combinado"], Decimal("1000"))
        self.assertEqual(linha["diferenca"], Decimal("28999000"))
        self.assertEqual(linha["faixa"], "critica")

    def test_meta_zero_nao_inventa_percentual(self):
        ResumoFinanceiro.objects.filter(
            acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="AT"
        ).update(recurso_ou_meta=0)
        bloco = panel.painel_acompanhamento(None, "financeiro", self.acomp)["graficos_ciclo"]["at"]
        self.assertIsNone(bloco["pct_meta"])
        self.assertEqual(bloco["anel_meta"], 0)

    def test_upload_anual_2027_renderiza_e_exporta_com_calculos_atuais(self):
        import tempfile
        from django.urls import reverse
        from .fixtures_financeiro import workbook_financeiro, preencher_tabela

        wb = workbook_financeiro()
        preencher_tabela(wb, "tbl_VisaoGeral", [{
            "AÇÃO": "AFCCT / PD&I", "RECURSO PPI TOTAL": 29000000,
            "REALIZADO 2024": 100, "REALIZADO 2025": 200,
            "REALIZADO 2026 (YTD)": 300, "PROJETADO 2026": 400,
            "PROJETADO 2027": 50,
        }])
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "ano-2027.xlsx"
            wb.save(caminho)
            services.ingestar("FINANCEIRO_GERAL", caminho, "Centro QuIIN", "2T/2024", self.usuario)
        wb.close()
        p2027 = ResumoFinanceiro.objects.get(acompanhamento=self.acomp, origem="TAB. 1.1", ano=2027)
        self.assertEqual(p2027.projetado, Decimal("50"))
        self.assertIsNone(p2027.realizado)
        tabela = panel.painel_acompanhamento(None, "fin", self.acomp)["tabela_tab11"]
        self.assertEqual(tabela["linhas"][0]["projetado_2027"], Decimal("50"))
        self.assertEqual(tabela["total"]["projetado_total"], Decimal("450"))
        self.assertEqual(tabela["total"]["combinado"], Decimal("1050"))
        self.assertEqual(tabela["total"]["diferenca"], Decimal("59998950"))
        self.client.force_login(self.usuario)
        for url in (f"/?ano=todos&base=fin&acompanhamento={self.acomp.pk}",
                    reverse("planning:export_html") + f"?ano=todos&base=fin&acompanhamento={self.acomp.pk}"):
            resposta = self.client.get(url)
            self.assertContains(resposta, "PROJETADO 2027")
            self.assertContains(resposta, "R$ 50,00")

    def test_projetado_total_informado_tem_prioridade_e_historico_sem_2027(self):
        pdi = Pilar.objects.get(codigo="PDI")
        ResumoFinanceiro.objects.filter(acompanhamento=self.acomp, origem="TAB. 1.1", pilar=pdi, ano=None).update(projetado=999)
        ResumoFinanceiro.objects.create(acompanhamento=self.acomp, origem="TAB. 1.1", pilar=pdi, ano=2027, projetado=50)
        linha = panel.painel_acompanhamento(None, "fin", self.acomp)["tabela_tab11"]["linhas"][0]
        self.assertEqual(linha["projetado_total"], Decimal("999"))
        ResumoFinanceiro.objects.filter(acompanhamento=self.acomp, origem="TAB. 1.1", ano=2027).delete()
        linha = panel.painel_acompanhamento(None, "fin", self.acomp)["tabela_tab11"]["linhas"][0]
        self.assertIsNone(linha["projetado_2027"])

    def test_importacao_antiga_sem_resumo_tab11_mantem_recurso(self):
        ResumoFinanceiro.objects.filter(
            acompanhamento=self.acomp, origem="TAB. 1.1").delete()
        linhas = panel.painel_acompanhamento(None, "financeiro", self.acomp)["tabela_tab11"]["linhas"]
        self.assertEqual(linhas[-1]["recurso"], Decimal("60000000"))
        self.assertIsNone(linhas[-1]["combinado"])
