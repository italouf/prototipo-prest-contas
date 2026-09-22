"""Testes da geometria genérica de barras agrupadas (L20, TDD)."""
from django.test import SimpleTestCase

from apps.core import charts

MESES = [(m, "2026") for m in
         ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]]
DIMENSOES = {"largura": 1100, "altura": 280,
             "pad": {"esq": 52, "dir": 20, "topo": 26, "base": 50},
             "larg_barra_max": 44, "espaco": 10}


class GeometriaBarrasTestes(SimpleTestCase):
    def test_12_grupos_com_rotulos_e_destaque(self):
        g = charts.geometria_barras(
            MESES, [10] * 12, [5] * 12, destaque=5, **DIMENSOES)
        self.assertEqual((g["largura"], g["altura"]), (1100, 280))
        self.assertEqual(len(g["grupos"]), 12)
        self.assertEqual(g["grupos"][0]["eixo"], ("Jan", "2026"))
        self.assertEqual([gr["destaque"] for gr in g["grupos"]],
                         [i == 5 for i in range(12)])
        self.assertEqual([gr["opacidade"] for gr in g["grupos"]],
                         [1 if i == 5 else 0.3 for i in range(12)])
        self.assertTrue(all(gr["divisor"] is False for gr in g["grupos"]))

    def test_sem_destaque_mostra_tudo(self):
        g = charts.geometria_barras(
            MESES[:6], [1] * 6, [1] * 6, destaque=None, **DIMENSOES)
        self.assertTrue(all(gr["opacidade"] == 1 for gr in g["grupos"]))
        self.assertTrue(all(gr["destaque"] is False for gr in g["grupos"]))

    def test_zero_vira_filete_e_altura_e_proporcional(self):
        g = charts.geometria_barras(
            MESES[:3], [10, 0, 5], [4, 0, 5], destaque=None, **DIMENSOES)
        barras = [(gr["a"]["h"], gr["b"]["h"]) for gr in g["grupos"]]
        self.assertGreater(barras[0][0], barras[2][0])
        self.assertEqual(barras[1][0], charts.ALTURA_MINIMA)
        self.assertEqual(barras[1][1], charts.ALTURA_MINIMA)

    def test_numeros_saem_arredondados_sem_virgula(self):
        g = charts.geometria_barras(
            MESES[:2], [7.75, 1.75], [2, 0], destaque=0, **DIMENSOES)
        for gr in g["grupos"]:
            for barra in (gr["a"], gr["b"]):
                for chave in ("x", "y", "w", "h", "cx", "ry"):
                    self.assertNotIn(",", str(barra[chave]))

    def test_series_com_tamanho_divergente_rejeitadas(self):
        with self.assertRaises(ValueError):
            charts.geometria_barras(MESES[:3], [1, 2], [1, 2, 3], None, **DIMENSOES)

    def test_divisor_marca_categoria_acumulada(self):
        g = charts.geometria_barras(
            [("A", "1"), ("B", "2"), ("Total", "1 a 2")], [3, 4, 7], [2, 3, 5],
            destaque=None, divisor=2, **DIMENSOES)
        self.assertEqual([gr["divisor"] for gr in g["grupos"]],
                         [False, False, True])
