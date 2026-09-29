"""Testes do parser do FINANCEIRO GERAL (SDD §4).

Scaffolding em ``unittest`` (o runner do ``manage.py test`` não injeta
``tmp_path``); as asserções e valores esperados vêm literalmente do brief.
"""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from apps.accountability.parsers.comum import normalizar, para_decimal
from apps.accountability.parsers.financeiro_geral import parse_financeiro_geral

ARQUIVO = (Path(__file__).resolve().parents[3] / "mockup" / "exemplos_arquivos"
           / "FINANCEIRO GERAL.xlsx")


def _resumo(payload, origem, codigo_pilar, ano=None):
    return next(r for r in payload["resumos"]
                if r["origem"] == origem and r["pilar"] == codigo_pilar and r["ano"] == ano)


def _projetos(payload, origem):
    return [p for p in payload["projetos"] if p["origem"] == origem]


class ParseFinanceiroGeralTestes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = parse_financeiro_geral(ARQUIVO)

    def test_linha_de_senhas(self):
        assert para_decimal("1.234,56") == Decimal("1234.56")
        assert para_decimal("#REF!") is None
        assert normalizar("  AFCCT / PD&I ") == "afcct / pd&i"

    def test_tab1_resumo_por_pilar(self):
        pdi = _resumo(self.p, "TAB. 1", "PDI")
        assert pdi["recurso_ou_meta"] == Decimal("29000000")
        assert pdi["realizado"] == Decimal("17675109.56")
        assert _resumo(self.p, "TAB. 1", "FORMACAO")["realizado"] == Decimal("7749636.72")
        assert _resumo(self.p, "TAB. 1", "STARTUPS")["realizado"] == Decimal("2251069.32")
        assert _resumo(self.p, "TAB. 1", "INFRA")["realizado"] == Decimal("7299414.35")

    def test_totais_de_reconciliacao_sao_linhas_distintas(self):
        assert _resumo(self.p, "TAB. 3", "PDI")["realizado"] == Decimal("17675109.56")
        assert _resumo(self.p, "TAB. 5", "FORMACAO")["realizado"] == Decimal("7749636.72")
        assert _resumo(self.p, "TAB. 8", "STARTUPS")["realizado"] == Decimal("2251069.32")

    def test_tab9_at_e_outras_fontes(self):
        at = _resumo(self.p, "TAB. 9", "AT")
        assert at["recurso_ou_meta"] == Decimal("7750000")
        assert at["captado"] == Decimal("5616700")
        assert at["captado_anos_1_2"] == Decimal("346200")
        assert at["realizado"] == Decimal("220597")
        assert _resumo(self.p, "TAB. 9", "OUTRASFONTES")["captado"] == Decimal("10226768")

    def test_totais_gerais_nao_geram_linha_de_pilar(self):
        assert not [r for r in self.p["resumos"] if r["pilar"] == "TOTAL"]

    def test_projetos_por_bloco(self):
        assert len(_projetos(self.p, "TAB. 2")) == 18
        assert len(_projetos(self.p, "TAB. 4")) == 8
        assert len(_projetos(self.p, "TAB. 6")) == 7
        primeiro = _projetos(self.p, "TAB. 2")[0]
        assert primeiro["nome"] == "Pós Processamento"
        assert primeiro["status"] == "Encerrado"
        assert primeiro["orcado"] == Decimal("3799447.4")
        assert primeiro["realizado"] == Decimal("3795618")

    def test_sem_valores_anuais_emite_aviso(self):
        assert not [r for r in self.p["resumos"] if r["ano"] is not None]
        assert any("TAB. 1.1" in a for a in self.p["avisos"])

    def test_tab7_ausente_gera_aviso_e_nao_erro(self):
        assert any("TAB. 7" in a for a in self.p["avisos"])
        assert self.p["erros"] == []

    def test_cabecalho_inesperado_vira_erro_com_linha(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as tmp_path:
            wb = Workbook()
            ws = wb.active
            ws.title = "FINANCEIRO "
            ws["C1"] = "TAB. 1 - VISÃO CONSOLIDADA"
            ws["C3"] = "COLOCA ERRADA"
            ws["C5"] = "AFCCT / PD&I"
            ws["D5"] = 29000000
            caminho = Path(tmp_path) / "errado.xlsx"
            wb.save(caminho)
            p = parse_financeiro_geral(caminho)
            assert p["erros"], "cabeçalho divergente deve virar erro"
            assert any("TAB. 1" in e for e in p["erros"])
