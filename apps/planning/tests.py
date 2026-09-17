"""Testes do app planning (L2) — painel anual 2024–2027 (TDD).

Matriz canônica: Anexo A do prompt, confirmada no L0
(docs/retrofit/evidencias/dashboard-anual/loop-0/matriz-estados.md).
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.pillars.models import Pilar
from apps.planning import charts, services
from apps.planning.models import PlanoAnual

D = Decimal

# (exec_ppi, prev_ppi, pct_ppi, exec_at, prev_at, pct_at,
#  exec_ou, prev_ou, pct_ou, exec_tot, prev_tot, pct_tot)
CARDS_ESPERADOS = {
    ("todos", "financeiro"): (D(40), D(60), 67, D(2), D("7.75"), 26, D(0), D("7.75"), 0, D(42), D("75.5"), 56),
    (2024, "financeiro"): (D(10), D(15), 67, D(0), D(1), 0, D(0), D(1), 0, D(10), D(17), 59),
    (2025, "financeiro"): (D(15), D(20), 75, D(1), D(2), 50, D(0), D(2), 0, D(16), D(24), 67),
    (2026, "financeiro"): (D(15), D(20), 75, D(1), D(3), 33, D(0), D(3), 0, D(16), D(26), 62),
    (2027, "financeiro"): (D(0), D(5), 0, D(0), D("1.75"), 0, D(0), D("1.75"), 0, D(0), D("8.5"), 0),
    ("todos", "fisico"): (D(32), D(52), 62, D(2), D(8), 25, D(0), D(8), 0, D(34), D(68), 50),
    (2024, "fisico"): (D(8), D(11), 73, D(0), D(1), 0, D(0), D(1), 0, D(8), D(13), 62),
    (2025, "fisico"): (D(12), D(17), 71, D(1), D(2), 50, D(0), D(2), 0, D(13), D(21), 62),
    (2026, "fisico"): (D(12), D(18), 67, D(1), D(3), 33, D(0), D(3), 0, D(13), D(24), 54),
    (2027, "fisico"): (D(0), D(6), 0, D(0), D(2), 0, D(0), D(2), 0, D(0), D(10), 0),
}

# (rotulo, previsto, executado, pct|None, faixa) — acumulado por base
TABELA_TODOS_FIN = [
    ("PDI", D(29), D(21), 72, "parcial"),
    ("Formação FCRH", D(14), D(7), 50, "parcial"),
    ("ACS", D(7), D(3), 43, "critica"),
    ("Infraestrutura", D(10), D(9), 90, "ok"),
    ("Total PPI", D(60), D(40), 67, "parcial"),
    ("Associação Tecnológica (AT)", D("7.75"), D(2), 26, "critica"),
    ("Outras fontes", D("7.75"), D(0), 0, "critica"),
]
TABELA_TODOS_FIS = [
    ("PDI", D(18), D(13), 72, "parcial"),
    ("Formação FCRH", D(15), D(7), 47, "critica"),
    ("ACS", D(9), D(3), 33, "critica"),
    ("Infraestrutura", D(10), D(9), 90, "ok"),
    ("Total PPI", D(52), D(32), 62, "parcial"),
    ("Associação Tecnológica (AT)", D(8), D(2), 25, "critica"),
    ("Outras fontes", D(8), D(0), 0, "critica"),
]

PLANO_FIXTURE = [
    # (codigo_pilar, base, previsto[2024..2027], executado[2024..2027])
    ("PDI", "financeiro", (7, 10, 10, 2), (5, 8, 8, 0)),
    ("FORMACAO", "financeiro", (4, 5, 4, 1), (2, 3, 2, 0)),
    ("STARTUPS", "financeiro", (2, 2, 2, 1), (1, 1, 1, 0)),
    ("INFRA", "financeiro", (2, 3, 4, 1), (2, 3, 4, 0)),
    ("AT", "financeiro", (1, 2, 3, 1.75), (0, 1, 1, 0)),
    ("OUTRASFONTES", "financeiro", (1, 2, 3, 1.75), (0, 0, 0, 0)),
    ("PDI", "fisico", (4, 6, 6, 2), (3, 5, 5, 0)),
    ("FORMACAO", "fisico", (3, 5, 5, 2), (2, 3, 2, 0)),
    ("STARTUPS", "fisico", (2, 3, 3, 1), (1, 1, 1, 0)),
    ("INFRA", "fisico", (2, 3, 4, 1), (2, 3, 4, 0)),
    ("AT", "fisico", (1, 2, 3, 2), (0, 1, 1, 0)),
    ("OUTRASFONTES", "fisico", (1, 2, 3, 2), (0, 0, 0, 0)),
]

PILARES_FIXTURE = [
    ("PDI", "PDI / FCCT", 1),
    ("FORMACAO", "Formação e Capacitação de RH", 2),
    ("STARTUPS", "Atração e Criação de Startups", 3),
    ("AT", "Associação Tecnológica", 4),
    ("INFRA", "Infraestrutura", 5),
    ("OUTRASFONTES", "Financeiro e Outras Fontes", 6),
]


def criar_base_anual():
    pilares = {}
    for codigo, nome, ordem in PILARES_FIXTURE:
        pilares[codigo] = Pilar.objects.create(codigo=codigo, nome=nome, ordem=ordem)
    for codigo, base, previstos, executados in PLANO_FIXTURE:
        for i, ano in enumerate(services.ANOS):
            PlanoAnual.objects.create(
                ano=ano, pilar=pilares[codigo], base=base,
                previsto=D(str(previstos[i])), executado=D(str(executados[i])),
            )
    return pilares


class PercentualFaixaTestes(SimpleTestCase):
    def test_percentual_basico(self):
        self.assertEqual(services.percentual(D(40), D(60)), D("66.66666666666666666666666667"))

    def test_percentual_inteiro(self):
        self.assertEqual(services.percentual(D(9), D(10)), D(90))

    def test_denominador_zero_retorna_none(self):
        self.assertIsNone(services.percentual(D(0), D(0)))
        self.assertIsNone(services.percentual(D(5), D(0)))

    def test_faixas(self):
        self.assertEqual(services.faixa(D(90)), "ok")
        self.assertEqual(services.faixa(D(100)), "ok")
        self.assertEqual(services.faixa(D("89.9")), "parcial")
        self.assertEqual(services.faixa(D(50)), "parcial")
        self.assertEqual(services.faixa(D("49.9")), "critica")
        self.assertEqual(services.faixa(D(0)), "critica")
        self.assertEqual(services.faixa(None), "neutra")

    def test_pct_inteiro_arredonda_meio_para_cima(self):
        self.assertEqual(services.pct_inteiro(D(40), D(60)), 67)
        self.assertEqual(services.pct_inteiro(D(2), D("7.75")), 26)
        self.assertEqual(services.pct_inteiro(D(0), D(0)), None)

    def test_rotulo_previsto_por_pilar(self):
        for codigo in ("PDI", "FORMACAO", "STARTUPS", "INFRA"):
            self.assertEqual(services.rotulo_previsto(codigo), "Projetado")
        self.assertEqual(services.rotulo_previsto("AT"), "Captado")
        self.assertEqual(services.rotulo_previsto("OUTRASFONTES"), "Captado")

    def test_rotulo_pilar_usa_sigla_pactuada(self):
        self.assertEqual(services.ROTULOS_PAINEL["FORMACAO"], "Formação FCRH")
        self.assertEqual(services.ROTULOS_PAINEL["STARTUPS"], "ACS")
        self.assertEqual(services.ROTULOS_PAINEL["AT"], "Associação Tecnológica (AT)")
        self.assertEqual(services.ROTULOS_PAINEL["OUTRASFONTES"], "Outras fontes")

    def test_painel_rejeita_base_e_ano_invalidos(self):
        with self.assertRaises(ValueError):
            services.painel(None, "invalida")
        with self.assertRaises(ValueError):
            services.painel(2030, "financeiro")


class PainelServicoTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        criar_base_anual()

    def test_cards_nos_10_estados(self):
        for (ano, base), esp in CARDS_ESPERADOS.items():
            with self.subTest(ano=ano, base=base):
                p = services.painel(None if ano == "todos" else ano, base)
                (e_ppi, v_ppi, pct_ppi, e_at, v_at, pct_at,
                 e_ou, v_ou, pct_ou, e_tot, v_tot, pct_tot) = esp
                (c_ppi, c_at, c_ou, c_tot) = p["cards"]
                self.assertEqual((c_ppi["executado"], c_ppi["previsto"], c_ppi["pct"]), (e_ppi, v_ppi, pct_ppi))
                self.assertEqual((c_at["executado"], c_at["previsto"], c_at["pct"]), (e_at, v_at, pct_at))
                self.assertEqual((c_ou["executado"], c_ou["previsto"], c_ou["pct"]), (e_ou, v_ou, pct_ou))
                self.assertEqual((c_tot["executado"], c_tot["previsto"], c_tot["pct"]), (e_tot, v_tot, pct_tot))

    def test_tabela_acumulada_confere_anexo_a(self):
        for base, esperado in (("financeiro", TABELA_TODOS_FIN), ("fisico", TABELA_TODOS_FIS)):
            with self.subTest(base=base):
                p = services.painel(None, base)
                linhas = [l for g in p["tabela"]["grupos"] for l in g["linhas"] if not l["grupo"]]
                self.assertEqual(len(linhas), 7)
                for obtida, (rot, prev, exe, pct, faixa) in zip(linhas, esperado):
                    self.assertEqual(obtida["rotulo"], rot)
                    self.assertEqual((obtida["previsto"], obtida["executado"]), (prev, exe))
                    self.assertEqual(obtida["saldo"], prev - exe)
                    self.assertEqual((obtida["pct"], obtida["faixa"]), (pct, faixa))

    def test_tabela_traz_grupos_41_42_43_e_total_ppi(self):
        p = services.painel(None, "financeiro")
        titulos = [g["titulo"] for g in p["tabela"]["grupos"]]
        self.assertEqual(titulos, [
            "4.1 PPI: projetado x executado",
            "4.2 Captação de recursos: captado x executado",
            "4.3 Outras fontes: captado x executado",
        ])
        totais = [l for g in p["tabela"]["grupos"] for l in g["linhas"] if l.get("total")]
        self.assertEqual(len(totais), 1)
        self.assertEqual(totais[0]["rotulo"], "Total PPI")

    def test_rodape_dos_graficos_usa_periodo_do_filtro(self):
        p = services.painel(2026, "financeiro")
        self.assertEqual(
            (p["graficos"]["ppi"]["rodape_pct"], p["graficos"]["at"]["rodape_pct"], p["graficos"]["outras"]["rodape_pct"]),
            (75, 33, 0),
        )
        p = services.painel(2026, "fisico")
        self.assertEqual(
            (p["graficos"]["ppi"]["rodape_pct"], p["graficos"]["at"]["rodape_pct"], p["graficos"]["outras"]["rodape_pct"]),
            (67, 33, 0),
        )

    def test_series_dos_graficos_incluem_acumulado(self):
        p = services.painel(None, "financeiro")
        self.assertEqual(p["graficos"]["ppi"]["serie_previsto"], [D(15), D(20), D(20), D(5), D(60)])
        self.assertEqual(p["graficos"]["ppi"]["serie_executado"], [D(10), D(15), D(15), D(0), D(40)])
        self.assertEqual(p["graficos"]["at"]["serie_previsto"], [D(1), D(2), D(3), D("1.75"), D("7.75")])

    def test_chips_e_rotulos_por_estado(self):
        p = services.painel(None, "financeiro")
        self.assertEqual(p["rotulo_periodo"], "Acumulado 2024 a 2027")
        self.assertEqual(p["unidade"], "R$ mi")
        p = services.painel(2026, "fisico")
        self.assertEqual(p["rotulo_periodo"], "Ano 3: 2026")
        self.assertEqual(p["unidade"], "metas")

    def test_painel_cabe_no_orcamento_de_queries(self):
        with self.assertNumQueries(1):
            services.painel(None, "financeiro")
        with self.assertNumQueries(1):
            services.painel(2026, "fisico")


class GeometriaGraficosTestes(SimpleTestCase):
    def test_fonte_tem_5_grupos_com_divisor_e_destaque(self):
        g = charts.geometria_fonte([15, 20, 20, 5, 60], [10, 15, 15, 0, 40], destaque=2)
        self.assertEqual((g["largura"], g["altura"]), (430, 268))
        self.assertEqual(len(g["grupos"]), 5)
        self.assertEqual([gr["divisor"] for gr in g["grupos"]], [False, False, False, False, True])
        self.assertEqual([gr["destaque"] for gr in g["grupos"]], [False, False, True, False, False])
        self.assertEqual([gr["opacidade"] for gr in g["grupos"]], [0.3, 0.3, 1, 0.3, 0.3])
        barras = [(gr["a"]["h"], gr["b"]["h"]) for gr in g["grupos"]]
        # altura proporcional ao valor (mesma escala p/ as duas séries)
        self.assertGreater(barras[4][0], barras[0][0])
        self.assertEqual(barras[3][1], charts.ALTURA_MINIMA)  # valor zero vira filete mínimo
        self.assertEqual(g["grupos"][0]["eixo"], ("Ano 1", "2024"))
        self.assertEqual(g["grupos"][4]["eixo"], ("Todos os anos", "2024 a 2027"))

    def test_fonte_sem_destaque_mostra_tudo(self):
        g = charts.geometria_fonte([1, 2, 3, 1.75, 7.75], [0, 1, 1, 0, 2], destaque=None)
        self.assertTrue(all(gr["opacidade"] == 1 for gr in g["grupos"]))
        self.assertTrue(all(gr["destaque"] is False for gr in g["grupos"]))

    def test_consolidado_tem_4_anos_x_3_series_com_fundo_no_destaque(self):
        g = charts.geometria_consolidado(
            {"PPI executado": [10, 15, 15, 0], "Captação AT executada": [0, 1, 1, 0],
             "Outras fontes executadas": [0, 0, 0, 0]},
            destaque=1,
        )
        self.assertEqual(len(g["grupos"]), 4)
        self.assertTrue(all(len(gr["barras"]) == 3 for gr in g["grupos"]))
        self.assertEqual([gr["fundo"] for gr in g["grupos"]], [False, True, False, False])
        self.assertEqual(g["grupos"][1]["eixo"], "Ano 2: 2025")
        self.assertEqual(len(g["linhas_grade"]), 5)


class SeedPlanoAnualTestes(TestCase):
    def test_seed_gera_48_linhas_e_idempotente(self):
        call_command("seed_demo")
        call_command("seed_demo")
        self.assertEqual(PlanoAnual.objects.count(), 48)

    def test_seed_reproduz_anexo_a(self):
        call_command("seed_demo")
        pdi = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        self.assertEqual((pdi.previsto, pdi.executado), (D(10), D(8)))
        at = PlanoAnual.objects.get(ano=2027, pilar__codigo="AT", base="financeiro")
        self.assertEqual((at.previsto, at.executado), (D("1.75"), D(0)))
        fcrh = PlanoAnual.objects.get(ano=2025, pilar__codigo="FORMACAO", base="fisico")
        self.assertEqual((fcrh.previsto, fcrh.executado), (D(5), D(3)))
        total = PlanoAnual.objects.filter(base="financeiro")
        from django.db.models import Sum
        soma = total.aggregate(p=Sum("previsto"), e=Sum("executado"))
        self.assertEqual((soma["p"], soma["e"]), (D("75.5"), D(42)))
