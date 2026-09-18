"""Testes do serviço painel_pilar (L12, TDD) — matriz §9.4 do SDD."""
from decimal import Decimal as D

from django.test import TestCase

from apps.pillars.models import Pilar
from apps.planning import services
from apps.planning.tests import criar_base_anual


class PainelPilarTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pilares = criar_base_anual()

    def painel(self, codigo, ano=None, base="financeiro"):
        return services.painel_pilar(self.pilares[codigo], ano, base)

    def test_pdi_acumulado_financeiro(self):
        p = self.painel("PDI")
        self.assertEqual(p["codigo"], "PDI")
        self.assertEqual(p["rotulo"], "PDI")
        self.assertEqual(p["unidade"], "R$ mi")
        self.assertEqual(p["rotulo_previsto"], "Projetado")
        self.assertEqual(p["rotulo_periodo"], "Acumulado 2024 a 2027")
        self.assertEqual((p["previsto"], p["executado"], p["saldo"]), (D(29), D(21), D(8)))
        self.assertEqual((p["pct"], p["faixa"]), (72, "parcial"))

    def test_at_usado_captado_como_referencia(self):
        p = self.painel("AT")
        self.assertEqual(p["rotulo"], "Associação Tecnológica (AT)")
        self.assertEqual(p["rotulo_previsto"], "Captado")
        self.assertEqual((p["previsto"], p["executado"], p["saldo"]), (D("7.75"), D(2), D("5.75")))
        self.assertEqual((p["pct"], p["faixa"]), (26, "critica"))

    def test_base_fisica_muda_unidade_e_valores(self):
        p = self.painel("PDI", base="fisico")
        self.assertEqual(p["unidade"], "metas")
        self.assertEqual((p["previsto"], p["executado"], p["saldo"]), (D(18), D(13), D(5)))
        self.assertEqual((p["pct"], p["faixa"]), (72, "parcial"))
        at = self.painel("AT", base="fisico")
        self.assertEqual((at["previsto"], at["executado"]), (D(8), D(2)))
        self.assertEqual((at["pct"], at["faixa"]), (25, "critica"))

    def test_filtro_ano_recorta_periodo(self):
        p = self.painel("PDI", ano=2026)
        self.assertEqual(p["rotulo_periodo"], "Ano 3: 2026")
        self.assertEqual((p["previsto"], p["executado"], p["saldo"]), (D(10), D(8), D(2)))
        self.assertEqual((p["pct"], p["faixa"]), (80, "parcial"))
        infra = self.painel("INFRA", ano=2026)
        self.assertEqual((infra["pct"], infra["faixa"]), (100, "ok"))
        at = self.painel("AT", ano=2026, base="fisico")
        self.assertEqual((at["previsto"], at["executado"]), (D(3), D(1)))
        self.assertEqual((at["pct"], at["faixa"]), (33, "critica"))

    def test_series_tem_4_anos_mais_acumulado(self):
        p = self.painel("PDI")
        self.assertEqual(p["serie_previsto"], [D(7), D(10), D(10), D(2), D(29)])
        self.assertEqual(p["serie_executado"], [D(5), D(8), D(8), D(0), D(21)])
        self.assertEqual((p["rodape_pct"], p["rodape_faixa"]), (72, "parcial"))
        p26 = self.painel("PDI", ano=2026)
        self.assertEqual((p26["rodape_pct"], p26["rodape_faixa"]), (80, "parcial"))

    def test_tabela_tem_linhas_por_ano_mais_total(self):
        p = self.painel("PDI")
        rotulos = [l["rotulo"] for l in p["tabela"]]
        self.assertEqual(rotulos, ["Ano 1: 2024", "Ano 2: 2025", "Ano 3: 2026", "Ano 4: 2027", "Total"])
        ano3 = p["tabela"][2]
        self.assertEqual((ano3["previsto"], ano3["executado"], ano3["saldo"]), (D(10), D(8), D(2)))
        self.assertEqual((ano3["pct"], ano3["faixa"]), (80, "parcial"))
        total = p["tabela"][4]
        self.assertTrue(total["total"])
        self.assertEqual((total["previsto"], total["executado"]), (D(29), D(21)))
        self.assertEqual((total["pct"], total["faixa"]), (72, "parcial"))

    def test_tabela_mostra_todos_os_anos_com_destaque_no_filtro(self):
        p = self.painel("PDI", ano=2026)
        rotulos = [l["rotulo"] for l in p["tabela"]]
        self.assertEqual(rotulos, ["Ano 1: 2024", "Ano 2: 2025", "Ano 3: 2026", "Ano 4: 2027", "Total"])
        total = p["tabela"][4]
        self.assertEqual((total["previsto"], total["executado"]), (D(29), D(21)))
        self.assertEqual((total["pct"], total["faixa"]), (72, "parcial"))
        self.assertEqual([l["destaque"] for l in p["tabela"]],
                         [False, False, True, False, False])
        sem_filtro = self.painel("PDI")["tabela"]
        self.assertEqual([l["destaque"] for l in sem_filtro], [False] * 5)

    def test_cards_reaproveitam_formato_do_kpi_card(self):
        p = self.painel("PDI")
        chaves = [c["chave"] for c in p["cards"]]
        self.assertEqual(chaves, ["previsto", "executado", "saldo", "percentual"])
        previsto, executado, saldo, percentual = p["cards"]
        self.assertEqual((previsto["executado"], previsto["denominador"]), (D(29), "projetados"))
        self.assertEqual((executado["executado"], executado["previsto"]), (D(21), D(29)))
        self.assertEqual((executado["pct"], executado["faixa"], executado["barra"]), (72, "parcial", 72))
        self.assertEqual(saldo["executado"], D(8))
        self.assertEqual(percentual["pct"], 72)
        at = self.painel("AT")
        self.assertEqual(at["cards"][0]["denominador"], "captados")
        self.assertEqual(at["cards"][1]["denominador"], "captados")

    def test_pilar_sem_linhas_tolerado_com_neutra(self):
        vazio = Pilar.objects.create(codigo="NOVO", nome="Novo", ordem=99)
        p = services.painel_pilar(vazio, None, "financeiro")
        self.assertEqual((p["previsto"], p["executado"], p["saldo"]), (D(0), D(0), D(0)))
        self.assertEqual((p["pct"], p["faixa"]), (None, "neutra"))
        self.assertEqual([l["pct"] for l in p["tabela"]], [None] * 5)

    def test_rejeita_base_e_ano_invalidos(self):
        with self.assertRaises(ValueError):
            services.painel_pilar(self.pilares["PDI"], None, "invalida")
        with self.assertRaises(ValueError):
            services.painel_pilar(self.pilares["PDI"], 2030, "financeiro")

    def test_painel_pilar_cabe_no_orcamento_de_queries(self):
        with self.assertNumQueries(2):
            services.painel_pilar(self.pilares["PDI"], None, "financeiro")
            services.painel_pilar(self.pilares["AT"], 2026, "fisico")
