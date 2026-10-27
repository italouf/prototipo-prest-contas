"""Subtotal financeiro das fontes selecionadas, sem incluir recursos PPI."""
from decimal import Decimal

from django.test import SimpleTestCase

from .overview import subtotal_fontes


class SubtotalFontesTestes(SimpleTestCase):
    def setUp(self):
        self.at = {"recurso": Decimal("6000000"), "realizado": Decimal("200000"),
                   "projetado": None, "combinado": None}
        self.outras = {"recurso": Decimal("10000000"), "realizado": Decimal("300000"),
                       "projetado": None, "combinado": None}

    def test_subtotal_soma_fontes_e_calcula_percentual_sobre_total_captado(self):
        subtotal = subtotal_fontes([self.at, self.outras])
        self.assertEqual(subtotal["recurso"], Decimal("16000000"))
        self.assertEqual(subtotal["realizado"], Decimal("500000"))
        self.assertEqual(subtotal["diferenca"], Decimal("15500000"))
        self.assertEqual(subtotal["pct"], Decimal("3.125"))
        self.assertEqual(subtotal["faixa"], "critica")
        self.assertIsNone(subtotal["projetado"])
        self.assertIsNone(subtotal["combinado"])

    def test_subtotal_de_uma_fonte_respeita_selecao(self):
        subtotal = subtotal_fontes([self.at])
        self.assertEqual(subtotal["recurso"], self.at["recurso"])
        self.assertEqual(subtotal["realizado"], self.at["realizado"])

    def test_sem_fontes_nao_inventa_valores_zerados(self):
        subtotal = subtotal_fontes([])
        for campo in ("recurso", "realizado", "diferenca", "projetado", "combinado", "pct"):
            self.assertIsNone(subtotal[campo])
        self.assertEqual(subtotal["faixa"], "neutra")

    def test_captado_zero_nao_calcula_percentual(self):
        subtotal = subtotal_fontes([dict(self.at, recurso=Decimal(0))])
        self.assertIsNone(subtotal["pct"])
        self.assertEqual(subtotal["barra"], 0)

    def test_barra_limita_em_cem_e_preserva_percentual_real(self):
        subtotal = subtotal_fontes([dict(self.at, realizado=Decimal("9000000"))])
        self.assertEqual(subtotal["pct"], Decimal("150"))
        self.assertEqual(subtotal["barra"], 100)
