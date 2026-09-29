"""Testes do parser dos Indicadores do Termo de Retificação do PE (SDD §5).

Scaffolding em ``unittest`` (pytest não está disponível e o runner do
``manage.py test`` não coleta classe sem base); as asserções e valores
esperados vêm literalmente do brief.
"""

import unittest
from decimal import Decimal
from pathlib import Path

from apps.accountability.parsers.indicadores_pe import parse_indicadores_pe

ARQUIVO = (Path(__file__).resolve().parents[3] / "mockup" / "exemplos_arquivos"
           / "Indicadores Gerais do Termo de Retificação do PE.xlsx")


class ParseIndicadoresPeTestes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = parse_indicadores_pe(ARQUIVO)

    def test_dez_kpis_com_codigos_estaveis(self):
        assert [k["codigo"] for k in self.p["kpis"]] == [f"PE-{i:02d}" for i in range(1, 11)]

    def test_kpi1_valores_exatos(self):
        kpi = self.p["kpis"][0]
        assert kpi["nome"].startswith("Projetos de PD&I desenvolvidos")
        assert kpi["pilar"] == "PDI"
        assert kpi["unidade"] == "Número absoluto"
        assert [kpi[f"meta_{ano}"] for ano in (2024, 2025, 2026, 2027)] == [
            Decimal("5"), Decimal("5"), Decimal("5"), Decimal("3")]
        assert kpi["meta_total"] == Decimal("18")
        assert kpi["executado_2024"] == Decimal("5")
        assert kpi["executado_2025"] == Decimal("10")
        assert kpi["acumulado"] == Decimal("15")
        assert kpi["gap"] == Decimal("-3")
        assert kpi["projecao_2026"] == Decimal("2")
        assert kpi["projecao_2027"] == Decimal("0")

    def test_acoes_mapeadas_para_os_pilares_internos(self):
        por_pilar = {k["codigo"]: k["pilar"] for k in self.p["kpis"]}
        assert por_pilar["PE-01"] == "PDI"
        assert por_pilar["PE-02"] == "OUTRASFONTES"
        assert por_pilar["PE-03"] == "AT"
        assert por_pilar["PE-05"] == "STARTUPS"
        assert por_pilar["PE-07"] == "FORMACAO"
        assert por_pilar["PE-10"] == "INFRA"

    def test_arquivo_real_nao_gera_erro(self):
        assert self.p["erros"] == []
